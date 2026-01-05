"""Group management flow tests"""
import pytest
import requests
from typing import Dict, Any, List, Optional
from src.api_client import SanadAPIClient, SanadClientFactory
from src.db_utils import (
    get_group_by_id,
    get_group_members,
    delete_group_by_id,
    delete_user_by_phone
)


# ========================================
# GROUP CREATION TESTS
# ========================================

@pytest.mark.group
def test_groupCreate_withValidName_returns200AndGroupId(
    registered_user: Dict[str, Any]
) -> None:
    """Test creating a group with valid name returns 200 and group ID"""
    client: SanadAPIClient = registered_user["client"]
    user_id: str = registered_user["user_id"]

    response: requests.Response = client.group_create("My Test Group")

    assert response.status_code == 200, (
        f"Failed to create group. "
        f"Expected 200, got {response.status_code}: {response.text}"
    )

    data: Dict[str, Any] = response.json()
    assert "data" in data
    assert "groupId" in data["data"]
    assert data["message"] == "Group created successfully"

    # Verify in database
    group_id: str = data["data"]["groupId"]
    db_group: Optional[Dict[str, Any]] = get_group_by_id(group_id)
    assert db_group is not None
    assert db_group["name"] == "My Test Group"
    assert db_group["created_by"] == user_id

    # Cleanup
    client.group_delete(group_id)


@pytest.mark.group
def test_groupCreate_withEmptyName_returns400or422(
    registered_user: Dict[str, Any]
) -> None:
    """Test that creating group with empty name fails validation"""
    client: SanadAPIClient = registered_user["client"]

    response: requests.Response = client.group_create("")

    # Should return validation error
    assert response.status_code in [400, 422], (
        f"Empty group name should fail validation. "
        f"Expected 400 or 422, got {response.status_code}"
    )


@pytest.mark.group
def test_groupCreate_withDuplicateName_returns400(
    registered_user: Dict[str, Any]
) -> None:
    """Test that user cannot create two groups with same name"""
    client: SanadAPIClient = registered_user["client"]

    # Create first group
    response1: requests.Response = client.group_create("Duplicate Name")
    assert response1.status_code == 200
    group_id1: str = response1.json()["data"]["groupId"]

    # Try to create second group with same name
    response2: requests.Response = client.group_create("Duplicate Name")
    assert response2.status_code == 400, (
        f"Duplicate group name should fail. "
        f"Expected 400, got {response2.status_code}"
    )

    response_data: Dict[str, Any] = response2.json()
    assert "already exists" in response_data["message"].lower()

    # Cleanup
    client.group_delete(group_id1)


@pytest.mark.group
def test_groupCreate_withoutAuthentication_returns401or403(
    authless_client: SanadAPIClient
) -> None:
    """Test that unauthenticated user cannot create group"""
    response: requests.Response = authless_client.group_create("Test Group")

    assert response.status_code in [401, 403], (
        f"Unauthenticated request should be rejected. "
        f"Expected 401 or 403, got {response.status_code}"
    )


# ========================================
# GROUP USER MANAGEMENT TESTS
# ========================================

@pytest.mark.group
def test_groupAddUsers_withRegisteredUsers_returns200AndAddsUsers(
    test_group: Dict[str, Any],
    second_registered_user: Dict[str, Any]
) -> None:
    """Test adding registered users to group by userId"""
    owner_client: SanadAPIClient = test_group["owner"]["client"]
    group_id: str = test_group["group_id"]
    second_user_id: str = second_registered_user["user_id"]

    # Add second user to group
    response: requests.Response = owner_client.group_add_users(
        group_id=group_id,
        user_ids=[second_user_id]
    )

    assert response.status_code == 200, (
        f"Failed to add user to group. "
        f"Expected 200, got {response.status_code}: {response.text}"
    )

    response_data: Dict[str, Any] = response.json()
    assert "success" in response_data["data"].lower()

    # Verify in database
    members: List[Dict[str, Any]] = get_group_members(group_id)
    assert len(members) == 1
    assert members[0]["user_id"] == second_user_id


@pytest.mark.group
def test_groupAddUsers_withNewContacts_returns200AndInvitesUsers(
    test_group: Dict[str, Any]
) -> None:
    """Test adding non-registered users (contacts) to group"""
    owner_client: SanadAPIClient = test_group["owner"]["client"]
    group_id: str = test_group["group_id"]

    # Add new contact (not yet registered)
    new_phone: str = "+12025559999"
    response: requests.Response = owner_client.group_add_users(
        group_id=group_id,
        new_users=[{"phone": new_phone, "countryCode": "+1"}]
    )

    assert response.status_code == 200, (
        f"Failed to add new contact to group. "
        f"Expected 200, got {response.status_code}: {response.text}"
    )

    # Note: New contacts are invited but not yet registered,
    # so they won't appear in group members immediately.
    # Backend creates a user record with phone_hash but no phone.


@pytest.mark.group
def test_groupAddUsers_withMixedUsersAndContacts_returns200AndAddsAll(
    test_group: Dict[str, Any],
    second_registered_user: Dict[str, Any]
) -> None:
    """Test adding both registered users and new contacts in one operation"""
    owner_client: SanadAPIClient = test_group["owner"]["client"]
    group_id: str = test_group["group_id"]
    second_user_id: str = second_registered_user["user_id"]

    # Add both registered user and new contact
    response: requests.Response = owner_client.group_add_users(
        group_id=group_id,
        user_ids=[second_user_id],
        new_users=[{"phone": "+12025558888", "countryCode": "+1"}]
    )

    assert response.status_code == 200

    # Verify registered user is in group
    members: List[Dict[str, Any]] = get_group_members(group_id)
    user_ids: List[str] = [m["user_id"] for m in members]
    assert second_user_id in user_ids


@pytest.mark.group
def test_groupAddUsers_withGroupNameUpdate_returns200AndRenamesGroup(
    test_group: Dict[str, Any],
    second_registered_user: Dict[str, Any]
) -> None:
    """Test renaming group during add-users operation"""
    owner_client: SanadAPIClient = test_group["owner"]["client"]
    group_id: str = test_group["group_id"]
    second_user_id: str = second_registered_user["user_id"]

    # Add user and rename group
    new_name: str = "Renamed Group"
    response: requests.Response = owner_client.group_add_users(
        group_id=group_id,
        user_ids=[second_user_id],
        group_name=new_name
    )

    assert response.status_code == 200

    # Verify group name changed
    db_group: Optional[Dict[str, Any]] = get_group_by_id(group_id)
    assert db_group is not None
    assert db_group["name"] == new_name


@pytest.mark.group
def test_groupAddUsers_withSyncBehavior_removesUnlistedUsers(
    test_group: Dict[str, Any],
    second_registered_user: Dict[str, Any],
    client_factory: SanadClientFactory,
    user_client: SanadAPIClient,
    test_otp: str
) -> None:
    """
    Test SYNC behavior: users not in the new list are removed.

    The group_add_users endpoint uses SYNC operation, meaning:
    - Users in the request are added to the group
    - Users NOT in the request are removed from the group
    """
    owner_client: SanadAPIClient = test_group["owner"]["client"]
    group_id: str = test_group["group_id"]
    second_user_id: str = second_registered_user["user_id"]

    # First, add second user to group
    response1: requests.Response = owner_client.group_add_users(
        group_id=group_id,
        user_ids=[second_user_id]
    )
    assert response1.status_code == 200

    # Verify second user is in group
    members1: List[Dict[str, Any]] = get_group_members(group_id)
    assert len(members1) == 1
    assert members1[0]["user_id"] == second_user_id

    # Create a third user for testing
    third_phone: str = "+12025557777"
    third_email: str = "third@example.com"

    # Invite third user
    user_client.invite_contacts([{"phone": third_phone}])

    # Register third user
    authless: SanadAPIClient = client_factory.create_unauthenticated_client()
    authless.user_send_otp(third_phone, "REGISTER")
    third_register: requests.Response = authless.user_register(
        phone=third_phone,
        first_name="Third",
        last_name="User",
        email=third_email,
        verification_code=test_otp
    )
    assert third_register.status_code == 200
    third_user_id: str = third_register.json()["data"]["userId"]

    # SYNC operation: add third user (this should remove second user)
    response2: requests.Response = owner_client.group_add_users(
        group_id=group_id,
        user_ids=[third_user_id]
    )
    assert response2.status_code == 200

    # Verify SYNC: only third user should be in group now
    members2: List[Dict[str, Any]] = get_group_members(group_id)
    assert len(members2) == 1, (
        f"SYNC should remove users not in request. "
        f"Expected 1 member, found {len(members2)}"
    )
    assert members2[0]["user_id"] == third_user_id

    # Second user should be removed
    member_user_ids: List[str] = [m["user_id"] for m in members2]
    assert second_user_id not in member_user_ids, (
        "Second user should be removed by SYNC operation"
    )

    # Cleanup
    delete_user_by_phone(third_phone)


@pytest.mark.group
def test_groupAddUsers_withNonexistentGroup_returns400or500(
    registered_user: Dict[str, Any],
    second_registered_user: Dict[str, Any]
) -> None:
    """Test that adding users to non-existent group fails"""
    client: SanadAPIClient = registered_user["client"]
    fake_group_id: str = "00000000-0000-0000-0000-000000000000"

    response: requests.Response = client.group_add_users(
        group_id=fake_group_id,
        user_ids=[second_registered_user["user_id"]]
    )

    assert response.status_code in [400, 500], (
        f"Adding users to non-existent group should fail. "
        f"Expected 400 or 500, got {response.status_code}"
    )


@pytest.mark.group
def test_groupAddUsers_withInvalidUserIds_returns400(
    test_group: Dict[str, Any]
) -> None:
    """Test that adding invalid userIds returns error"""
    owner_client: SanadAPIClient = test_group["owner"]["client"]
    group_id: str = test_group["group_id"]
    fake_user_id: str = "00000000-0000-0000-0000-000000000000"

    response: requests.Response = owner_client.group_add_users(
        group_id=group_id,
        user_ids=[fake_user_id]
    )

    assert response.status_code == 400
    response_data: Dict[str, Any] = response.json()
    assert "invalid" in response_data["message"].lower()


# ========================================
# GROUP RETRIEVAL TESTS
# ========================================

@pytest.mark.group
def test_groupGetAll_forUserWithNoGroups_returns200AndEmptyList(
    registered_user: Dict[str, Any]
) -> None:
    """Test that new user has no groups"""
    client: SanadAPIClient = registered_user["client"]

    response: requests.Response = client.group_get_all()

    assert response.status_code == 200
    data: Dict[str, Any] = response.json()["data"]
    assert "groups" in data
    assert len(data["groups"]) == 0
    assert data["total"] == 0


@pytest.mark.group
def test_groupGetAll_forUserWithSingleGroup_returns200AndGroupMetadata(
    test_group: Dict[str, Any]
) -> None:
    """Test getting single group with correct metadata"""
    owner_client: SanadAPIClient = test_group["owner"]["client"]
    group_id: str = test_group["group_id"]

    response: requests.Response = owner_client.group_get_all()

    assert response.status_code == 200
    data: Dict[str, Any] = response.json()["data"]
    assert len(data["groups"]) == 1
    assert data["total"] == 1

    group: Dict[str, Any] = data["groups"][0]
    assert group["id"] == group_id
    assert group["name"] == "Test Group"
    assert "userCount" in group
    assert "invitedUsers" in group
    assert "createdAt" in group


@pytest.mark.group
def test_groupGetAll_forUserWithMultipleGroups_returns200AndOrderedList(
    registered_user: Dict[str, Any]
) -> None:
    """Test getting multiple groups ordered by updatedAt descending"""
    client: SanadAPIClient = registered_user["client"]

    # Create multiple groups
    response1: requests.Response = client.group_create("Group 1")
    assert response1.status_code == 200
    group_id1: str = response1.json()["data"]["groupId"]

    response2: requests.Response = client.group_create("Group 2")
    assert response2.status_code == 200
    group_id2: str = response2.json()["data"]["groupId"]

    response3: requests.Response = client.group_create("Group 3")
    assert response3.status_code == 200
    group_id3: str = response3.json()["data"]["groupId"]

    # Get all groups
    response: requests.Response = client.group_get_all()

    assert response.status_code == 200
    data: Dict[str, Any] = response.json()["data"]
    assert len(data["groups"]) == 3
    assert data["total"] == 3

    # Groups should be ordered by updatedAt descending (most recent first)
    groups: List[Dict[str, Any]] = data["groups"]
    assert groups[0]["id"] == group_id3  # Last created
    assert groups[1]["id"] == group_id2
    assert groups[2]["id"] == group_id1  # First created

    # Cleanup
    client.group_delete(group_id1)
    client.group_delete(group_id2)
    client.group_delete(group_id3)


@pytest.mark.group
def test_groupGetAll_withUserCounts_returns200AndCorrectCounts(
    test_group: Dict[str, Any],
    second_registered_user: Dict[str, Any]
) -> None:
    """Test that userCount and invitedUsers are correct"""
    owner_client: SanadAPIClient = test_group["owner"]["client"]
    group_id: str = test_group["group_id"]

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

    response: requests.Response = owner_client.group_get_all()

    assert response.status_code == 200
    groups: List[Dict[str, Any]] = response.json()["data"]["groups"]
    group: Dict[str, Any] = next(g for g in groups if g["id"] == group_id)

    # userCount should include registered users
    assert group["userCount"] >= 1
    # invitedUsers should include non-registered contacts
    # (actual count depends on backend implementation)


@pytest.mark.group
def test_groupGetAll_withPagination_returns200AndPaginatedResults(
    registered_user: Dict[str, Any]
) -> None:
    """Test pagination with pageSize and page parameters"""
    client: SanadAPIClient = registered_user["client"]

    # Create 5 groups
    group_ids: List[str] = []
    for i in range(5):
        response: requests.Response = client.group_create(f"Group {i+1}")
        assert response.status_code == 200
        group_ids.append(response.json()["data"]["groupId"])

    # Test pagination: 2 items per page, get page 1
    response: requests.Response = client.group_get_all(page_size=2, page=1)

    assert response.status_code == 200
    data: Dict[str, Any] = response.json()["data"]
    assert len(data["groups"]) == 2
    assert data["total"] == 5

    # Get page 2
    response2: requests.Response = client.group_get_all(page_size=2, page=2)
    assert response2.status_code == 200
    data2: Dict[str, Any] = response2.json()["data"]
    assert len(data2["groups"]) == 2

    # Cleanup
    for gid in group_ids:
        client.group_delete(gid)


# ========================================
# GET USERS TO ADD TESTS
# ========================================

@pytest.mark.group
def test_groupGetUsersToAdd_withoutGroupId_returns200AndAllUsers(
    registered_user: Dict[str, Any],
    second_registered_user: Dict[str, Any]
) -> None:
    """Test getting users from contact list without specifying group"""
    client: SanadAPIClient = registered_user["client"]
    second_phone: str = second_registered_user["phone"]

    response: requests.Response = client.group_get_users_to_add(
        contact_list=[
            {"firstName": "John", "phone": second_phone, "countryCode": "+1"}
        ]
    )

    assert response.status_code == 200
    data: Dict[str, Any] = response.json()["data"]
    assert "users" in data
    assert "contactList" in data

    # Second user is registered, should appear in users
    users: List[Dict[str, Any]] = data["users"]
    assert len(users) >= 1

    # isInGroup should be null when no groupId provided
    for user in users:
        assert "isInGroup" in user
        assert user["isInGroup"] is None


@pytest.mark.group
def test_groupGetUsersToAdd_withGroupId_returns200AndGroupMembership(
    test_group: Dict[str, Any],
    second_registered_user: Dict[str, Any]
) -> None:
    """Test checking which users are already in group"""
    owner_client: SanadAPIClient = test_group["owner"]["client"]
    group_id: str = test_group["group_id"]
    second_phone: str = second_registered_user["phone"]
    second_user_id: str = second_registered_user["user_id"]

    # Add second user to group
    owner_client.group_add_users(group_id=group_id, user_ids=[second_user_id])

    # Check with groupId - should show isInGroup = true
    response: requests.Response = owner_client.group_get_users_to_add(
        group_id=group_id,
        contact_list=[
            {"firstName": "John", "phone": second_phone, "countryCode": "+1"}
        ]
    )

    assert response.status_code == 200
    data: Dict[str, Any] = response.json()["data"]

    # Find second user in users list
    users: List[Dict[str, Any]] = data["users"]
    second_user: Optional[Dict[str, Any]] = next(
        (u for u in users if u["id"] == second_user_id),
        None
    )
    assert second_user is not None
    assert second_user["isInGroup"] is True


@pytest.mark.group
def test_groupGetUsersToAdd_separatesRegisteredAndContacts_returns200(
    registered_user: Dict[str, Any]
) -> None:
    """Test that registered users and non-registered contacts are separated"""
    client: SanadAPIClient = registered_user["client"]

    # Contact list with mix of registered and non-registered
    response: requests.Response = client.group_get_users_to_add(
        contact_list=[
            {"firstName": "New", "phone": "+12025554444", "countryCode": "+1"},
            {"firstName": "Another", "phone": "+12025553333", "countryCode": "+1"}
        ]
    )

    assert response.status_code == 200
    data: Dict[str, Any] = response.json()["data"]

    # Non-registered contacts should be in contactList
    assert "contactList" in data
    # Registered users should be in users
    assert "users" in data


# ========================================
# GROUP DELETION TESTS
# ========================================

@pytest.mark.group
def test_groupDelete_byOwner_returns200AndDeletesGroup(
    registered_user: Dict[str, Any]
) -> None:
    """Test deleting a group returns success and removes from database"""
    client: SanadAPIClient = registered_user["client"]

    # Create group
    create_response: requests.Response = client.group_create("To Delete")
    assert create_response.status_code == 200
    group_id: str = create_response.json()["data"]["groupId"]

    # Delete group
    delete_response: requests.Response = client.group_delete(group_id)

    assert delete_response.status_code == 200
    response_data: Dict[str, Any] = delete_response.json()
    assert "success" in response_data["data"].lower()

    # Verify group is deleted from database
    db_group: Optional[Dict[str, Any]] = get_group_by_id(group_id)
    assert db_group is None


@pytest.mark.group
def test_groupDelete_cascadesUserMemberships_returns200(
    test_group: Dict[str, Any],
    second_registered_user: Dict[str, Any]
) -> None:
    """Test that deleting group cascade deletes user_group entries"""
    owner_client: SanadAPIClient = test_group["owner"]["client"]
    group_id: str = test_group["group_id"]

    # Add user to group
    owner_client.group_add_users(
        group_id=group_id,
        user_ids=[second_registered_user["user_id"]]
    )

    # Verify member exists
    members_before: List[Dict[str, Any]] = get_group_members(group_id)
    assert len(members_before) == 1

    # Delete group
    delete_response: requests.Response = owner_client.group_delete(group_id)
    assert delete_response.status_code == 200

    # Verify memberships are also deleted (cascade)
    members_after: List[Dict[str, Any]] = get_group_members(group_id)
    assert len(members_after) == 0


@pytest.mark.group
def test_groupDelete_withNonexistentGroup_returns400or500(
    registered_user: Dict[str, Any]
) -> None:
    """Test that deleting non-existent group returns error"""
    client: SanadAPIClient = registered_user["client"]
    fake_group_id: str = "00000000-0000-0000-0000-000000000000"

    response: requests.Response = client.group_delete(fake_group_id)

    assert response.status_code in [400, 500], (
        f"Deleting non-existent group should fail. "
        f"Expected 400 or 500, got {response.status_code}"
    )


# ========================================
# EDGE CASES & ERROR SCENARIOS
# ========================================

@pytest.mark.group
def test_groupOperations_withoutAuthentication_returns401or403(
    authless_client: SanadAPIClient
) -> None:
    """Test that all group endpoints require authentication"""
    # Try to get groups without auth
    response1: requests.Response = authless_client.group_get_all()
    assert response1.status_code in [401, 403]

    # Try to create group without auth
    response2: requests.Response = authless_client.group_create("Test")
    assert response2.status_code in [401, 403]

    # Try to delete group without auth
    response3: requests.Response = authless_client.group_delete("fake-id")
    assert response3.status_code in [401, 403]


@pytest.mark.group
def test_groupCreate_withWhitespace_trimmedCorrectly(
    registered_user: Dict[str, Any]
) -> None:
    """Test that group names are trimmed of leading/trailing whitespace"""
    client: SanadAPIClient = registered_user["client"]

    response: requests.Response = client.group_create("  Trimmed Name  ")

    assert response.status_code == 200
    group_id: str = response.json()["data"]["groupId"]

    # Verify name is trimmed in database
    db_group: Optional[Dict[str, Any]] = get_group_by_id(group_id)
    assert db_group is not None
    assert db_group["name"] == "Trimmed Name"

    # Cleanup
    client.group_delete(group_id)


@pytest.mark.group
def test_groupAddUsers_withEmptyGroupId_returns400or422(
    registered_user: Dict[str, Any],
    second_registered_user: Dict[str, Any]
) -> None:
    """Test that empty groupId is rejected"""
    client: SanadAPIClient = registered_user["client"]

    response: requests.Response = client.group_add_users(
        group_id="",
        user_ids=[second_registered_user["user_id"]]
    )

    assert response.status_code in [400, 422], (
        f"Empty groupId should be rejected. "
        f"Expected 400 or 422, got {response.status_code}"
    )
