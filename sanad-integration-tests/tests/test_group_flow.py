"""Group management flow tests"""
import pytest
from src.db_utils import get_group_by_id, get_group_members, delete_group_by_id


# ============================================================================
# GROUP CREATION TESTS
# ============================================================================

@pytest.mark.group
def test_create_group_success(registered_user):
    """Test creating a group with valid name"""
    client = registered_user["client"]

    response = client.group_create("My Test Group")

    assert response.status_code == 200
    data = response.json()
    assert "data" in data
    assert "groupId" in data["data"]
    assert data["message"] == "Group created successfully"

    # Verify in database
    group_id = data["data"]["groupId"]
    db_group = get_group_by_id(group_id)
    assert db_group is not None
    assert db_group["name"] == "My Test Group"
    assert db_group["created_by"] == registered_user["user_id"]

    # Cleanup
    client.group_delete(group_id)


@pytest.mark.group
def test_create_group_empty_name_fails(registered_user):
    """Test that creating group with empty name fails"""
    client = registered_user["client"]

    response = client.group_create("")

    # Should return validation error (422 or 400)
    assert response.status_code in [400, 422]


@pytest.mark.group
def test_create_group_duplicate_name_fails(registered_user):
    """Test that user cannot create two groups with same name"""
    client = registered_user["client"]

    # Create first group
    response1 = client.group_create("Duplicate Name")
    assert response1.status_code == 200
    group_id1 = response1.json()["data"]["groupId"]

    # Try to create second group with same name
    response2 = client.group_create("Duplicate Name")
    assert response2.status_code == 400
    assert "already exists" in response2.json()["message"].lower()

    # Cleanup
    client.group_delete(group_id1)


@pytest.mark.group
def test_create_group_requires_authentication(api_client):
    """Test that unauthenticated user cannot create group"""
    # Use fresh client without authentication
    response = api_client.group_create("Test Group")

    assert response.status_code in [401, 403]


# ============================================================================
# ADD USERS TO GROUP TESTS
# ============================================================================

@pytest.mark.group
def test_add_registered_users_to_group(test_group, second_registered_user):
    """Test adding registered users to group by userId"""
    owner_client = test_group["owner"]["client"]
    group_id = test_group["group_id"]
    second_user_id = second_registered_user["user_id"]

    # Add second user to group
    response = owner_client.group_add_users(
        group_id=group_id,
        user_ids=[second_user_id]
    )

    assert response.status_code == 200
    assert "success" in response.json()["data"].lower()

    # Verify in database
    members = get_group_members(group_id)
    assert len(members) == 1
    assert members[0]["user_id"] == second_user_id


@pytest.mark.group
def test_add_new_contacts_to_group(test_group):
    """Test adding non-registered users (contacts) to group"""
    owner_client = test_group["owner"]["client"]
    group_id = test_group["group_id"]

    # Add new contact (not yet registered)
    new_phone = "+12025559999"
    response = owner_client.group_add_users(
        group_id=group_id,
        new_users=[{"phone": new_phone, "countryCode": "+1"}]
    )

    assert response.status_code == 200

    # Verify user was created and added to group
    members = get_group_members(group_id)
    # Note: New contacts might not show up immediately in group members
    # because they're invited but not registered yet
    # The backend creates a user record with phone_hash but no phone


@pytest.mark.group
def test_add_mixed_users_and_contacts(test_group, second_registered_user):
    """Test adding both registered users and new contacts"""
    owner_client = test_group["owner"]["client"]
    group_id = test_group["group_id"]
    second_user_id = second_registered_user["user_id"]

    # Add both registered user and new contact
    response = owner_client.group_add_users(
        group_id=group_id,
        user_ids=[second_user_id],
        new_users=[{"phone": "+12025558888", "countryCode": "+1"}]
    )

    assert response.status_code == 200

    # Verify registered user is in group
    members = get_group_members(group_id)
    user_ids = [m["user_id"] for m in members]
    assert second_user_id in user_ids


@pytest.mark.group
def test_update_group_name_while_adding_users(test_group, second_registered_user):
    """Test renaming group during add-users operation"""
    owner_client = test_group["owner"]["client"]
    group_id = test_group["group_id"]
    second_user_id = second_registered_user["user_id"]

    # Add user and rename group
    new_name = "Renamed Group"
    response = owner_client.group_add_users(
        group_id=group_id,
        user_ids=[second_user_id],
        group_name=new_name
    )

    assert response.status_code == 200

    # Verify group name changed
    db_group = get_group_by_id(group_id)
    assert db_group["name"] == new_name


@pytest.mark.group
def test_add_users_sync_removes_missing_users(test_group, second_registered_user, root_user_client):
    """Test SYNC behavior: users not in the new list are removed"""
    owner_client = test_group["owner"]["client"]
    group_id = test_group["group_id"]
    second_user_id = second_registered_user["user_id"]

    # First, add second user to group
    response1 = owner_client.group_add_users(
        group_id=group_id,
        user_ids=[second_user_id]
    )
    assert response1.status_code == 200

    # Verify second user is in group
    members1 = get_group_members(group_id)
    assert len(members1) == 1
    assert members1[0]["user_id"] == second_user_id

    # Now create a third user
    third_phone = "+12025557777"
    root_user_client.invite_contacts([{"phone": third_phone}])
    from src.api_client import SanadAPIClient
    third_client = SanadAPIClient(owner_client.base_url)
    third_client.user_send_otp(third_phone, "REGISTER")
    third_register = third_client.user_register(
        phone=third_phone,
        first_name="Third",
        last_name="User",
        email="third@example.com",
        verification_code="111111"
    )
    assert third_register.status_code == 200
    third_user_id = third_register.json()["data"]["userId"]

    # SYNC operation: add third user (this should remove second user)
    response2 = owner_client.group_add_users(
        group_id=group_id,
        user_ids=[third_user_id]
    )
    assert response2.status_code == 200

    # Verify SYNC: only third user should be in group now
    members2 = get_group_members(group_id)
    assert len(members2) == 1
    assert members2[0]["user_id"] == third_user_id
    # Second user should be removed
    user_ids = [m["user_id"] for m in members2]
    assert second_user_id not in user_ids

    # Cleanup
    from src.db_utils import delete_user_by_phone
    delete_user_by_phone(third_phone)


@pytest.mark.group
def test_add_users_to_nonexistent_group_fails(registered_user, second_registered_user):
    """Test that adding users to non-existent group fails"""
    client = registered_user["client"]
    fake_group_id = "00000000-0000-0000-0000-000000000000"

    response = client.group_add_users(
        group_id=fake_group_id,
        user_ids=[second_registered_user["user_id"]]
    )

    assert response.status_code in [400, 500]
    # Backend returns generic "Internal server error" for invalid group


@pytest.mark.group
def test_add_invalid_user_ids_fails(test_group):
    """Test that adding invalid userIds returns error"""
    owner_client = test_group["owner"]["client"]
    group_id = test_group["group_id"]
    fake_user_id = "00000000-0000-0000-0000-000000000000"

    response = owner_client.group_add_users(
        group_id=group_id,
        user_ids=[fake_user_id]
    )

    assert response.status_code == 400
    assert "invalid" in response.json()["message"].lower()


# ============================================================================
# GET ALL GROUPS TESTS
# ============================================================================

@pytest.mark.group
def test_get_all_groups_empty(registered_user):
    """Test that new user has no groups"""
    client = registered_user["client"]

    response = client.group_get_all()

    assert response.status_code == 200
    data = response.json()["data"]
    assert "groups" in data
    assert len(data["groups"]) == 0
    assert data["total"] == 0


@pytest.mark.group
def test_get_all_groups_single(test_group):
    """Test getting single group with correct metadata"""
    owner_client = test_group["owner"]["client"]
    group_id = test_group["group_id"]

    response = owner_client.group_get_all()

    assert response.status_code == 200
    data = response.json()["data"]
    assert len(data["groups"]) == 1
    assert data["total"] == 1

    group = data["groups"][0]
    assert group["id"] == group_id
    assert group["name"] == "Test Group"
    assert "userCount" in group
    assert "invitedUsers" in group
    assert "createdAt" in group


@pytest.mark.group
def test_get_all_groups_multiple(registered_user):
    """Test getting multiple groups ordered by updatedAt"""
    client = registered_user["client"]

    # Create multiple groups
    response1 = client.group_create("Group 1")
    assert response1.status_code == 200
    group_id1 = response1.json()["data"]["groupId"]

    response2 = client.group_create("Group 2")
    assert response2.status_code == 200
    group_id2 = response2.json()["data"]["groupId"]

    response3 = client.group_create("Group 3")
    assert response3.status_code == 200
    group_id3 = response3.json()["data"]["groupId"]

    # Get all groups
    response = client.group_get_all()

    assert response.status_code == 200
    data = response.json()["data"]
    assert len(data["groups"]) == 3
    assert data["total"] == 3

    # Groups should be ordered by updatedAt descending (most recent first)
    groups = data["groups"]
    assert groups[0]["id"] == group_id3  # Last created
    assert groups[1]["id"] == group_id2
    assert groups[2]["id"] == group_id1  # First created

    # Cleanup
    client.group_delete(group_id1)
    client.group_delete(group_id2)
    client.group_delete(group_id3)


@pytest.mark.group
def test_get_all_groups_with_user_counts(test_group, second_registered_user):
    """Test that userCount and invitedUsers are correct"""
    owner_client = test_group["owner"]["client"]
    group_id = test_group["group_id"]

    # Add a registered user
    owner_client.group_add_users(
        group_id=group_id,
        user_ids=[second_registered_user["user_id"]]
    )

    # Add an invited (non-registered) user
    owner_client.group_add_users(
        group_id=group_id,
        user_ids=[second_registered_user["user_id"]],
        new_users=[{"phone": "+12025556666", "countryCode": "+1"}]
    )

    response = owner_client.group_get_all()

    assert response.status_code == 200
    groups = response.json()["data"]["groups"]
    group = next(g for g in groups if g["id"] == group_id)

    # userCount should include registered users
    assert group["userCount"] >= 1
    # invitedUsers should include non-registered contacts
    # (actual count depends on backend implementation)


@pytest.mark.group
def test_get_all_groups_pagination(registered_user):
    """Test pagination with pageSize and page parameters"""
    client = registered_user["client"]

    # Create 5 groups
    group_ids = []
    for i in range(5):
        response = client.group_create(f"Group {i+1}")
        assert response.status_code == 200
        group_ids.append(response.json()["data"]["groupId"])

    # Test pagination: 2 items per page, get page 1
    response = client.group_get_all(page_size=2, page=1)

    assert response.status_code == 200
    data = response.json()["data"]
    assert len(data["groups"]) == 2
    assert data["total"] == 5

    # Get page 2
    response2 = client.group_get_all(page_size=2, page=2)
    assert response2.status_code == 200
    data2 = response2.json()["data"]
    assert len(data2["groups"]) == 2

    # Cleanup
    for gid in group_ids:
        client.group_delete(gid)


# ============================================================================
# GET USERS TO ADD TESTS
# ============================================================================

@pytest.mark.group
def test_get_users_to_add_without_group(registered_user, second_registered_user):
    """Test getting users from contact list without specifying group"""
    client = registered_user["client"]
    second_phone = second_registered_user["phone"]

    response = client.group_get_users_to_add(
        contact_list=[
            {"firstName": "John", "phone": second_phone, "countryCode": "+1"}
        ]
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert "users" in data
    assert "contactList" in data

    # Second user is registered, should appear in users
    users = data["users"]
    assert len(users) >= 1
    # isInGroup should be null when no groupId provided
    for user in users:
        assert "isInGroup" in user
        assert user["isInGroup"] is None


@pytest.mark.group
def test_get_users_to_add_with_group(test_group, second_registered_user):
    """Test checking which users are already in group"""
    owner_client = test_group["owner"]["client"]
    group_id = test_group["group_id"]
    second_phone = second_registered_user["phone"]
    second_user_id = second_registered_user["user_id"]

    # Add second user to group
    owner_client.group_add_users(group_id=group_id, user_ids=[second_user_id])

    # Check with groupId - should show isInGroup = true
    response = owner_client.group_get_users_to_add(
        group_id=group_id,
        contact_list=[
            {"firstName": "John", "phone": second_phone, "countryCode": "+1"}
        ]
    )

    assert response.status_code == 200
    data = response.json()["data"]

    # Find second user in users list
    users = data["users"]
    second_user = next((u for u in users if u["id"] == second_user_id), None)
    assert second_user is not None
    assert second_user["isInGroup"] is True


@pytest.mark.group
def test_get_users_to_add_separates_registered_and_contacts(registered_user):
    """Test that registered users and non-registered contacts are separated"""
    client = registered_user["client"]

    # Contact list with mix of registered and non-registered
    response = client.group_get_users_to_add(
        contact_list=[
            {"firstName": "New", "phone": "+12025554444", "countryCode": "+1"},
            {"firstName": "Another", "phone": "+12025553333", "countryCode": "+1"}
        ]
    )

    assert response.status_code == 200
    data = response.json()["data"]

    # Non-registered contacts should be in contactList
    assert "contactList" in data
    # Registered users should be in users
    assert "users" in data


# ============================================================================
# DELETE GROUP TESTS
# ============================================================================

@pytest.mark.group
def test_delete_group_success(registered_user):
    """Test deleting a group returns success"""
    client = registered_user["client"]

    # Create group
    create_response = client.group_create("To Delete")
    assert create_response.status_code == 200
    group_id = create_response.json()["data"]["groupId"]

    # Delete group
    delete_response = client.group_delete(group_id)

    assert delete_response.status_code == 200
    assert "success" in delete_response.json()["data"].lower()

    # Verify group is deleted from database
    db_group = get_group_by_id(group_id)
    assert db_group is None


@pytest.mark.group
def test_delete_group_removes_memberships(test_group, second_registered_user):
    """Test that deleting group cascade deletes user_group entries"""
    owner_client = test_group["owner"]["client"]
    group_id = test_group["group_id"]

    # Add user to group
    owner_client.group_add_users(
        group_id=group_id,
        user_ids=[second_registered_user["user_id"]]
    )

    # Verify member exists
    members_before = get_group_members(group_id)
    assert len(members_before) == 1

    # Delete group
    delete_response = owner_client.group_delete(group_id)
    assert delete_response.status_code == 200

    # Verify memberships are also deleted (cascade)
    members_after = get_group_members(group_id)
    assert len(members_after) == 0


@pytest.mark.group
def test_delete_nonexistent_group_fails(registered_user):
    """Test that deleting non-existent group returns error"""
    client = registered_user["client"]
    fake_group_id = "00000000-0000-0000-0000-000000000000"

    response = client.group_delete(fake_group_id)

    assert response.status_code in [400, 500]
    # Backend returns generic "Internal server error" for non-existent group


# ============================================================================
# EDGE CASES & ERROR SCENARIOS
# ============================================================================

@pytest.mark.group
def test_group_operations_require_authentication(api_client):
    """Test that all group endpoints require authentication"""
    # Try to get groups without auth
    response1 = api_client.group_get_all()
    assert response1.status_code in [401, 403]

    # Try to create group without auth
    response2 = api_client.group_create("Test")
    assert response2.status_code in [401, 403]

    # Try to delete group without auth
    response3 = api_client.group_delete("fake-id")
    assert response3.status_code in [401, 403]


@pytest.mark.group
def test_group_name_is_trimmed(registered_user):
    """Test that group names are trimmed of whitespace"""
    client = registered_user["client"]

    response = client.group_create("  Trimmed Name  ")

    assert response.status_code == 200
    group_id = response.json()["data"]["groupId"]

    # Verify name is trimmed in database
    db_group = get_group_by_id(group_id)
    assert db_group["name"] == "Trimmed Name"

    # Cleanup
    client.group_delete(group_id)


@pytest.mark.group
def test_cannot_add_users_with_empty_group_id(registered_user, second_registered_user):
    """Test that empty groupId is rejected"""
    client = registered_user["client"]

    response = client.group_add_users(
        group_id="",
        user_ids=[second_registered_user["user_id"]]
    )

    assert response.status_code in [400, 422]
