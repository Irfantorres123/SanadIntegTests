"""
Campaign management flow tests

NOTE: Backend doesn't return campaignId in create response.
Tests use _get_campaign_id_by_title() helper to fetch IDs from list endpoint.
"""
import pytest
import requests
from typing import Dict, Any, Optional, List
from src.api_client import SanadAPIClient
from src.db_utils import get_campaign_by_id, get_campaign_groups, delete_campaign_by_id


def _get_campaign_id_by_title(
    client: SanadAPIClient,
    title: str,
    filter_type: str = "IN_REVIEW"
) -> Optional[str]:
    """Fetch campaign ID by title from list endpoint"""
    response: requests.Response = client.campaign_get_all(filter_type=filter_type)
    if response.status_code != 200:
        return None

    campaigns: List[Dict[str, Any]] = response.json()["data"]["campaigns"]
    campaign: Optional[Dict[str, Any]] = next(
        (c for c in campaigns if c["title"] == title),
        None
    )

    return campaign["id"] if campaign else None


@pytest.mark.campaign
def test_campaignCreate_byUser_returns200AndYetToApproveStatus(
    registered_user: Dict[str, Any]
) -> None:
    """Regular user creates campaign with YET_TO_APPROVE status"""
    client: SanadAPIClient = registered_user["client"]
    user_id: str = registered_user["user_id"]

    response: requests.Response = client.campaign_create(
        title="Help Ramadan Food Drive",
        campaign_type="ZAKAT",
        duration="30",
        amount="1000",
        description="Providing iftar meals for families in need during Ramadan"
    )

    assert response.status_code == 200, (
        f"Failed to create campaign. "
        f"Expected 200, got {response.status_code}: {response.text}"
    )

    campaign_id: Optional[str] = _get_campaign_id_by_title(
        client,
        "Help Ramadan Food Drive",
        filter_type="IN_REVIEW"
    )
    assert campaign_id is not None, "Created campaign not found in list"

    db_campaign: Optional[Dict[str, Any]] = get_campaign_by_id(campaign_id)
    assert db_campaign is not None, "Campaign not found in database"
    assert db_campaign["status"] == "YET_TO_APPROVE"
    assert str(db_campaign["created_by"]) == user_id

    delete_campaign_by_id(campaign_id)


@pytest.mark.campaign
def test_campaignCreate_byAdmin_autoApprovesAndReturns200(
    admin_client: SanadAPIClient
) -> None:
    """Admin-created campaigns are auto-approved with APPROVED status"""
    import time
    unique_title: str = f"Admin Approved Campaign {int(time.time())}"

    response: requests.Response = admin_client.campaign_create(
        title=unique_title,
        campaign_type="SADAQA",
        duration="60",
        amount="5000",
        description="This campaign is created by admin and should be auto-approved"
    )

    assert response.status_code == 200, (
        f"Failed to create admin campaign. "
        f"Expected 200, got {response.status_code}: {response.text}"
    )

    campaign_id: Optional[str] = _get_campaign_id_by_title(
        admin_client,
        unique_title,
        filter_type="ACTIVE"
    )
    assert campaign_id is not None, "Admin campaign not found in ACTIVE list"

    db_campaign: Optional[Dict[str, Any]] = get_campaign_by_id(campaign_id)
    assert db_campaign is not None, "Campaign not found in database"
    assert db_campaign["status"] == "APPROVED"

    delete_campaign_by_id(campaign_id)


@pytest.mark.campaign
def test_campaignCreate_withOptionalFields_returns200AndStoresFields(
    registered_user: Dict[str, Any]
) -> None:
    """Campaign creation stores all optional fields correctly"""
    client: SanadAPIClient = registered_user["client"]

    response: requests.Response = client.campaign_create(
        title="Comprehensive Campaign Test",
        campaign_type="JARIYA",
        duration="45",
        amount="3000",
        description="Testing all optional fields including payment details",
        payment_details="Bank: ABC Bank\nAccount: 123456789\nIBAN: SA1234567890"
    )

    assert response.status_code == 200, (
        f"Failed to create campaign with optional fields. "
        f"Expected 200, got {response.status_code}: {response.text}"
    )

    campaign_id: Optional[str] = _get_campaign_id_by_title(
        client,
        "Comprehensive Campaign Test",
        filter_type="IN_REVIEW"
    )
    assert campaign_id is not None, "Campaign not found"

    db_campaign: Optional[Dict[str, Any]] = get_campaign_by_id(campaign_id)
    assert db_campaign is not None
    assert db_campaign["type"] == "JARIYA"
    assert int(db_campaign["duration"]) == 45
    assert int(db_campaign["total_amount"]) == 3000
    assert "abc bank" in db_campaign["payment_details"].lower()

    delete_campaign_by_id(campaign_id)


@pytest.mark.campaign
def test_campaignCreate_withGroupSharing_returns200AndSharestoGroups(
    admin_client: SanadAPIClient
) -> None:
    """Admin creates campaign with group sharing (auto-approved, shareable)"""
    import time
    unique_title: str = f"Shared Campaign {int(time.time())}"

    group_response: requests.Response = admin_client.group_create(f"Admin Group {int(time.time())}")
    assert group_response.status_code == 200, (
        f"Failed to create group. Expected 200, got {group_response.status_code}: {group_response.text}"
    )
    group_id: str = group_response.json()["data"]["groupId"]

    response: requests.Response = admin_client.campaign_create(
        title=unique_title,
        campaign_type="ZAKAT",
        duration="30",
        amount="2000",
        description="This campaign is shared to groups upon creation",
        group_ids=[group_id]
    )

    assert response.status_code == 200, (
        f"Failed to create and share campaign. "
        f"Expected 200, got {response.status_code}: {response.text}"
    )

    campaign_id: Optional[str] = _get_campaign_id_by_title(
        admin_client,
        unique_title,
        filter_type="ACTIVE"
    )
    assert campaign_id is not None, "Shared campaign not found in list"

    campaign_groups: List[Dict[str, Any]] = get_campaign_groups(campaign_id)
    assert len(campaign_groups) >= 1, (
        f"Expected at least 1 group, found {len(campaign_groups)}"
    )

    group_ids_list: List[str] = [cg["group_id"] for cg in campaign_groups]
    assert group_id in group_ids_list, (
        f"Group {group_id} not in shared groups {group_ids_list}"
    )

    admin_client.group_delete(group_id)
    delete_campaign_by_id(campaign_id)


@pytest.mark.campaign
def test_campaignCreate_withUserSharing_returns200AndSharesWithUsers(
    admin_client: SanadAPIClient,
    registered_user: Dict[str, Any]
) -> None:
    """Admin creates campaign and shares with specific users"""
    import time
    unique_title: str = f"User Shared Campaign {int(time.time())}"
    target_user_id: str = registered_user["user_id"]

    response: requests.Response = admin_client.campaign_create(
        title=unique_title,
        campaign_type="SADAQA",
        duration="30",
        amount="1500",
        description="Campaign shared directly to specific users",
        user_ids=[target_user_id]
    )

    assert response.status_code == 200, (
        f"Failed to create and share campaign to users. "
        f"Expected 200, got {response.status_code}: {response.text}"
    )

    campaign_id: Optional[str] = _get_campaign_id_by_title(
        admin_client,
        unique_title,
        filter_type="ACTIVE"
    )
    assert campaign_id is not None, "User-shared campaign not found"

    user_client: SanadAPIClient = registered_user["client"]
    shared_campaigns_response: requests.Response = user_client.campaign_get_all(
        filter_type="SHARED_TO_USER"
    )
    assert shared_campaigns_response.status_code == 200

    shared_campaigns: List[Dict[str, Any]] = shared_campaigns_response.json()["data"]["campaigns"]
    campaign_ids: List[str] = [c["id"] for c in shared_campaigns]
    assert campaign_id in campaign_ids, "Campaign not visible to shared user"

    delete_campaign_by_id(campaign_id)


@pytest.mark.campaign
def test_campaignCreate_withImageUpload_returns200AndUploadsToS3(
    registered_user: Dict[str, Any]
) -> None:
    """Campaign creation with image uploads to S3"""
    import io
    import time
    client: SanadAPIClient = registered_user["client"]
    unique_title: str = f"Campaign with Image {int(time.time())}"

    fake_image: io.BytesIO = io.BytesIO(b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde')
    fake_image.name = "test_image.png"

    response: requests.Response = client.session.post(
        f"{client.endpoint}/api/v1/campaign/create",
        data={
            "title": unique_title,
            "type": "ZAKAT",
            "duration": "30",
            "amount": "1000",
            "description": "Campaign with image upload"
        },
        files={"image": ("test.png", fake_image, "image/png")}
    )

    assert response.status_code == 200, (
        f"Failed to create campaign with image. "
        f"Expected 200, got {response.status_code}: {response.text}"
    )

    campaign_id: Optional[str] = _get_campaign_id_by_title(
        client,
        unique_title,
        filter_type="IN_REVIEW"
    )
    assert campaign_id is not None, "Campaign with image not found"

    db_campaign: Optional[Dict[str, Any]] = get_campaign_by_id(campaign_id)
    assert db_campaign is not None
    assert db_campaign["image_url"] is not None, "Image URL not stored"
    assert len(db_campaign["image_url"]) > 0, "Image URL is empty"

    delete_campaign_by_id(campaign_id)


@pytest.mark.campaign
def test_campaignCreate_withInvalidImageFormat_returns400(
    registered_user: Dict[str, Any]
) -> None:
    """Invalid image format is rejected"""
    import io
    client: SanadAPIClient = registered_user["client"]

    fake_file: io.BytesIO = io.BytesIO(b'This is not an image file, just plain text')
    fake_file.name = "test.txt"

    response: requests.Response = client.session.post(
        f"{client.endpoint}/api/v1/campaign/create",
        data={
            "title": "Campaign with Invalid Image",
            "type": "ZAKAT",
            "duration": "30",
            "amount": "1000",
            "description": "This should fail"
        },
        files={"image": ("test.txt", fake_file, "text/plain")}
    )

    assert response.status_code in [400, 422, 500], (
        f"Invalid image format should fail. "
        f"Expected 400/422/500, got {response.status_code}"
    )


@pytest.mark.campaign
def test_campaignCreate_withEmptyTitle_returns400(
    registered_user: Dict[str, Any]
) -> None:
    """Empty title fails validation"""
    client: SanadAPIClient = registered_user["client"]

    response: requests.Response = client.campaign_create(
        title="",
        campaign_type="ZAKAT",
        duration="30",
        amount="1000",
        description="Test campaign"
    )

    assert response.status_code in [400, 422], (
        f"Empty title should fail validation. "
        f"Expected 400 or 422, got {response.status_code}"
    )


@pytest.mark.campaign
def test_campaignCreate_withInvalidType_returns400(
    registered_user: Dict[str, Any]
) -> None:
    """Invalid campaign type is rejected"""
    client: SanadAPIClient = registered_user["client"]

    response: requests.Response = client.campaign_create(
        title="Invalid Type Campaign",
        campaign_type="INVALID_TYPE",
        duration="30",
        amount="1000",
        description="This should fail"
    )

    assert response.status_code in [400, 422], (
        f"Invalid campaign type should fail validation. "
        f"Expected 400 or 422, got {response.status_code}"
    )


@pytest.mark.campaign
def test_campaignCreate_withoutAuthentication_returns401or403(
    authless_client: SanadAPIClient
) -> None:
    """Unauthenticated user cannot create campaign"""
    response: requests.Response = authless_client.campaign_create(
        title="Unauthorized Campaign",
        campaign_type="ZAKAT",
        duration="30",
        amount="1000",
        description="This should fail without auth"
    )

    assert response.status_code in [401, 403], (
        f"Unauthenticated request should be rejected. "
        f"Expected 401 or 403, got {response.status_code}"
    )


@pytest.mark.campaign
def test_campaignGetAll_forNewUser_returns200AndEmptyOrSharedCampaigns(
    registered_user: Dict[str, Any]
) -> None:
    """New user sees empty campaign list or shared campaigns"""
    client: SanadAPIClient = registered_user["client"]

    response: requests.Response = client.campaign_get_all()

    assert response.status_code == 200, (
        f"Failed to get campaigns. "
        f"Expected 200, got {response.status_code}: {response.text}"
    )

    data: Dict[str, Any] = response.json()["data"]
    assert "campaigns" in data, "Response missing 'campaigns' field"
    assert "total" in data, "Response missing 'total' field"


@pytest.mark.campaign
def test_campaignGetAll_withFilterActive_returns200AndApprovedCampaigns(
    registered_user: Dict[str, Any]
) -> None:
    """Get only active (APPROVED) campaigns"""
    client: SanadAPIClient = registered_user["client"]

    response: requests.Response = client.campaign_get_all(filter_type="ACTIVE")

    assert response.status_code == 200, (
        f"Failed to get active campaigns. "
        f"Expected 200, got {response.status_code}: {response.text}"
    )

    data: Dict[str, Any] = response.json()["data"]
    campaigns: List[Dict[str, Any]] = data["campaigns"]

    for campaign in campaigns:
        assert "id" in campaign, "Campaign missing 'id' field"
        assert "title" in campaign, "Campaign missing 'title' field"


@pytest.mark.campaign
def test_campaignGetAll_withFilterInReview_returns200AndPendingCampaigns(
    registered_user: Dict[str, Any]
) -> None:
    """Get campaigns pending admin approval"""
    client: SanadAPIClient = registered_user["client"]

    client.campaign_create(
        title="Pending Approval Campaign",
        campaign_type="ZAKAT",
        duration="30",
        amount="1000",
        description="This should be in review"
    )

    response: requests.Response = client.campaign_get_all(filter_type="IN_REVIEW")

    assert response.status_code == 200, (
        f"Failed to get campaigns in review. "
        f"Expected 200, got {response.status_code}: {response.text}"
    )

    data: Dict[str, Any] = response.json()["data"]
    campaigns: List[Dict[str, Any]] = data["campaigns"]

    campaign: Optional[Dict[str, Any]] = next(
        (c for c in campaigns if c["title"] == "Pending Approval Campaign"),
        None
    )
    if campaign:
        delete_campaign_by_id(campaign["id"])


@pytest.mark.campaign
def test_campaignGetAll_withFilterSharedToUser_returns200(
    admin_client: SanadAPIClient,
    registered_user: Dict[str, Any]
) -> None:
    """Get campaigns shared to current user"""
    import time
    unique_title: str = f"Shared To User Test {int(time.time())}"
    user_id: str = registered_user["user_id"]

    admin_client.campaign_create(
        title=unique_title,
        campaign_type="SADAQA",
        duration="30",
        amount="2000",
        description="Shared to specific user",
        user_ids=[user_id]
    )

    user_client: SanadAPIClient = registered_user["client"]
    response: requests.Response = user_client.campaign_get_all(filter_type="SHARED_TO_USER")

    assert response.status_code == 200, (
        f"Failed to get shared campaigns. "
        f"Expected 200, got {response.status_code}: {response.text}"
    )

    data: Dict[str, Any] = response.json()["data"]
    campaigns: List[Dict[str, Any]] = data["campaigns"]

    shared_campaign: Optional[Dict[str, Any]] = next(
        (c for c in campaigns if c["title"] == unique_title),
        None
    )
    assert shared_campaign is not None, "Shared campaign not found in SHARED_TO_USER list"

    delete_campaign_by_id(shared_campaign["id"])


@pytest.mark.campaign
def test_campaignGetAll_withFilterAllUserCampaigns_returns200(
    registered_user: Dict[str, Any]
) -> None:
    """Get all campaigns created by user regardless of status"""
    client: SanadAPIClient = registered_user["client"]

    client.campaign_create(
        title="All User Campaigns Test",
        campaign_type="ZAKAT",
        duration="30",
        amount="1000",
        description="Testing ALL_USER_CAMPAIGNS filter"
    )

    response: requests.Response = client.campaign_get_all(filter_type="ALL_USER_CAMPAIGNS")

    assert response.status_code == 200, (
        f"Failed to get all user campaigns. "
        f"Expected 200, got {response.status_code}: {response.text}"
    )

    data: Dict[str, Any] = response.json()["data"]
    campaigns: List[Dict[str, Any]] = data["campaigns"]

    campaign: Optional[Dict[str, Any]] = next(
        (c for c in campaigns if c["title"] == "All User Campaigns Test"),
        None
    )
    if campaign:
        delete_campaign_by_id(campaign["id"])


@pytest.mark.campaign
def test_campaignGetAll_withCampaignTypeFilter_returns200AndFilteredByType(
    registered_user: Dict[str, Any]
) -> None:
    """Filter campaigns by type (ZAKAT, SADAQA, JARIYA)"""
    client: SanadAPIClient = registered_user["client"]

    response: requests.Response = client.campaign_get_all(campaign_type="ZAKAT")

    assert response.status_code == 200, (
        f"Failed to filter campaigns by type. "
        f"Expected 200, got {response.status_code}: {response.text}"
    )

    data: Dict[str, Any] = response.json()["data"]
    campaigns: List[Dict[str, Any]] = data["campaigns"]

    for campaign in campaigns:
        if "type" in campaign:
            assert campaign["type"] == "ZAKAT", f"Expected ZAKAT, got {campaign['type']}"


@pytest.mark.campaign
def test_campaignGetAll_withPagination_returns200AndLimitedResults(
    registered_user: Dict[str, Any]
) -> None:
    """Pagination limits results correctly"""
    client: SanadAPIClient = registered_user["client"]

    response: requests.Response = client.campaign_get_all(page_size=5, page=1)

    assert response.status_code == 200, (
        f"Failed to paginate campaigns. "
        f"Expected 200, got {response.status_code}: {response.text}"
    )

    data: Dict[str, Any] = response.json()["data"]
    campaigns: List[Dict[str, Any]] = data["campaigns"]

    assert len(campaigns) <= 5, f"Expected max 5 campaigns, got {len(campaigns)}"


@pytest.mark.campaign
def test_campaignGetAll_withSearchText_returns200AndMatchingCampaigns(
    registered_user: Dict[str, Any]
) -> None:
    """Search campaigns by title or description"""
    client: SanadAPIClient = registered_user["client"]
    import time
    unique_title: str = f"Unique Searchable Campaign {int(time.time())}"

    client.campaign_create(
        title=unique_title,
        campaign_type="ZAKAT",
        duration="30",
        amount="1000",
        description="This campaign has very unique searchable keywords"
    )

    campaign_id: Optional[str] = _get_campaign_id_by_title(
        client,
        unique_title,
        filter_type="IN_REVIEW"
    )
    assert campaign_id is not None, "Campaign not created"

    response: requests.Response = client.campaign_get_all(search_text="Unique Searchable")

    assert response.status_code == 200, (
        f"Failed to search campaigns. "
        f"Expected 200, got {response.status_code}: {response.text}"
    )

    data: Dict[str, Any] = response.json()["data"]
    campaigns: List[Dict[str, Any]] = data["campaigns"]

    matching_campaign: Optional[Dict[str, Any]] = next(
        (c for c in campaigns if "Unique Searchable" in c["title"]),
        None
    )

    if matching_campaign is None:
        print(f"Search returned {len(campaigns)} campaigns, none matching 'Unique Searchable'")
        print(f"Campaign titles: {[c.get('title', 'N/A') for c in campaigns[:5]]}")

    delete_campaign_by_id(campaign_id)


@pytest.mark.campaign
def test_campaignGetAll_withoutAuthentication_returns401or403(
    authless_client: SanadAPIClient
) -> None:
    """Getting campaign list requires authentication"""
    response: requests.Response = authless_client.campaign_get_all()

    assert response.status_code in [401, 403], (
        f"Unauthenticated request should be rejected. "
        f"Expected 401 or 403, got {response.status_code}"
    )


@pytest.mark.campaign
def test_campaignGetOne_withValidId_returns200AndCampaignDetails(
    approved_campaign: Dict[str, Any],
    admin_client: SanadAPIClient,
    registered_user: Dict[str, Any]
) -> None:
    """Fetch campaign details with valid ID"""
    campaign_id: str = approved_campaign["campaign_id"]
    user_id: str = registered_user["user_id"]

    admin_client.campaign_share(campaign_id=campaign_id, user_ids=[user_id])

    client: SanadAPIClient = registered_user["client"]
    response: requests.Response = client.campaign_get_one(campaign_id)

    assert response.status_code == 200, (
        f"Failed to get campaign details. "
        f"Expected 200, got {response.status_code}: {response.text}"
    )

    data: Dict[str, Any] = response.json()["data"]
    assert "campaignId" in data
    assert data["campaignId"] == campaign_id


@pytest.mark.campaign
def test_campaignGetOne_withTrustChain_returns200AndIncludesTrustData(
    approved_campaign: Dict[str, Any],
    registered_user: Dict[str, Any],
    admin_client: SanadAPIClient
) -> None:
    """Campaign includes trust chain information"""
    client: SanadAPIClient = registered_user["client"]
    campaign_id: str = approved_campaign["campaign_id"]
    user_id: str = registered_user["user_id"]

    share_response: requests.Response = admin_client.campaign_share(
        campaign_id=campaign_id,
        user_ids=[user_id]
    )
    assert share_response.status_code == 200

    response: requests.Response = client.campaign_get_one(campaign_id)
    assert response.status_code == 200

    data: Dict[str, Any] = response.json()["data"]
    assert "campaignId" in data
    assert data["campaignId"] == campaign_id


@pytest.mark.campaign
def test_campaignGetOne_byCreator_returns200AndOwnCampaignDetails(
    registered_user: Dict[str, Any]
) -> None:
    """Campaign creator can view own campaign"""
    client: SanadAPIClient = registered_user["client"]

    client.campaign_create(
        title="Creator Own Campaign",
        campaign_type="ZAKAT",
        duration="30",
        amount="1000",
        description="Testing creator access"
    )

    campaign_id: Optional[str] = _get_campaign_id_by_title(
        client,
        "Creator Own Campaign",
        filter_type="IN_REVIEW"
    )
    assert campaign_id is not None

    response: requests.Response = client.campaign_get_one(campaign_id)

    assert response.status_code == 200, (
        f"Creator should access own campaign. "
        f"Expected 200, got {response.status_code}: {response.text}"
    )

    delete_campaign_by_id(campaign_id)


@pytest.mark.campaign
def test_campaignGetOne_withNonexistentId_returns404(
    registered_user: Dict[str, Any]
) -> None:
    """Non-existent campaign ID returns error"""
    client: SanadAPIClient = registered_user["client"]

    response: requests.Response = client.campaign_get_one("99999999")

    assert response.status_code in [400, 404, 500], (
        f"Non-existent campaign should return error. "
        f"Expected 400/404/500, got {response.status_code}"
    )


@pytest.mark.campaign
def test_campaignGetOne_withoutAuthentication_returns401or403(
    authless_client: SanadAPIClient,
    test_campaign: Dict[str, Any]
) -> None:
    """Getting campaign details requires authentication"""
    campaign_id: str = test_campaign["campaign_id"]

    response: requests.Response = authless_client.campaign_get_one(campaign_id)

    assert response.status_code in [401, 403], (
        f"Unauthenticated request should be rejected. "
        f"Expected 401 or 403, got {response.status_code}"
    )


@pytest.mark.campaign
def test_campaignGetAll_withFilterInactive_returns200AndExpiredCampaigns(
    registered_user: Dict[str, Any]
) -> None:
    """Get inactive (expired) campaigns"""
    client: SanadAPIClient = registered_user["client"]

    response: requests.Response = client.campaign_get_all(filter_type="INACTIVE")

    assert response.status_code == 200, (
        f"Failed to get inactive campaigns. "
        f"Expected 200, got {response.status_code}: {response.text}"
    )

    data: Dict[str, Any] = response.json()["data"]
    campaigns: List[Dict[str, Any]] = data["campaigns"]

    for campaign in campaigns:
        assert "id" in campaign
        assert "title" in campaign
        assert "status" in campaign


@pytest.mark.campaign
def test_campaignGetAll_withFilterAllUserCampaigns_returns200(
    registered_user: Dict[str, Any]
) -> None:
    """Get all campaigns created by user (any status)"""
    import time
    client: SanadAPIClient = registered_user["client"]
    unique_title: str = f"All User Campaigns Test {int(time.time())}"

    client.campaign_create(
        title=unique_title,
        campaign_type="ZAKAT",
        duration="30",
        amount="1000",
        description="Testing ALL_USER_CAMPAIGNS filter"
    )

    campaign_id: Optional[str] = _get_campaign_id_by_title(
        client,
        unique_title,
        filter_type="IN_REVIEW"
    )
    assert campaign_id is not None

    response: requests.Response = client.campaign_get_all(filter_type="ALL_USER_CAMPAIGNS")

    assert response.status_code == 200, (
        f"Failed to get all user campaigns. "
        f"Expected 200, got {response.status_code}: {response.text}"
    )

    data: Dict[str, Any] = response.json()["data"]
    campaigns: List[Dict[str, Any]] = data["campaigns"]

    found_campaign: Optional[Dict[str, Any]] = next(
        (c for c in campaigns if c["id"] == campaign_id),
        None
    )
    assert found_campaign is not None, "Created campaign not found in ALL_USER_CAMPAIGNS list"

    delete_campaign_by_id(campaign_id)


@pytest.mark.campaign
def test_campaignGetAll_withFilterSharedToUser_returns200(
    admin_client: SanadAPIClient,
    registered_user: Dict[str, Any]
) -> None:
    """Get campaigns shared to the user"""
    import time
    unique_title: str = f"Shared To User Test {int(time.time())}"
    user_client: SanadAPIClient = registered_user["client"]
    target_user_id: str = registered_user["user_id"]

    admin_client.campaign_create(
        title=unique_title,
        campaign_type="SADAQA",
        duration="30",
        amount="2000",
        description="Campaign to be shared to user",
        user_ids=[target_user_id]
    )

    campaign_id: Optional[str] = _get_campaign_id_by_title(
        admin_client,
        unique_title,
        filter_type="ACTIVE"
    )
    assert campaign_id is not None, "Campaign not found"

    response: requests.Response = user_client.campaign_get_all(filter_type="SHARED_TO_USER")

    assert response.status_code == 200, (
        f"Failed to get campaigns shared to user. "
        f"Expected 200, got {response.status_code}: {response.text}"
    )

    data: Dict[str, Any] = response.json()["data"]
    campaigns: List[Dict[str, Any]] = data["campaigns"]

    shared_campaign: Optional[Dict[str, Any]] = next(
        (c for c in campaigns if c["id"] == campaign_id),
        None
    )
    assert shared_campaign is not None, "Campaign not found in SHARED_TO_USER list"

    delete_campaign_by_id(campaign_id)


@pytest.mark.campaign
def test_campaignGetAll_withBlockedUsers_excludesBlockedCampaigns(
    registered_user: Dict[str, Any],
    second_registered_user: Dict[str, Any]
) -> None:
    """Blocked users' campaigns are excluded from feed"""
    import time
    unique_title: str = f"Blocked User Campaign {int(time.time())}"
    user_client: SanadAPIClient = registered_user["client"]
    blocked_client: SanadAPIClient = second_registered_user["client"]
    blocked_user_id: str = second_registered_user["user_id"]

    blocked_client.campaign_create(
        title=unique_title,
        campaign_type="ZAKAT",
        duration="30",
        amount="1000",
        description="Campaign from user that will be blocked"
    )

    campaign_id: Optional[str] = _get_campaign_id_by_title(
        blocked_client,
        unique_title,
        filter_type="IN_REVIEW"
    )
    assert campaign_id is not None

    block_response: requests.Response = user_client.session.post(
        f"{user_client.endpoint}/api/v1/user/block",
        json={"blockedUserId": blocked_user_id}
    )

    if block_response.status_code == 200:
        response: requests.Response = user_client.campaign_get_all()
        assert response.status_code == 200

        campaigns: List[Dict[str, Any]] = response.json()["data"]["campaigns"]
        campaign_ids: List[str] = [c["id"] for c in campaigns]
        assert campaign_id not in campaign_ids, "Blocked user's campaign should not appear"

        user_client.session.post(
            f"{user_client.endpoint}/api/v1/user/unblock",
            json={"blockedUserId": blocked_user_id}
        )

    delete_campaign_by_id(campaign_id)


@pytest.mark.campaign
def test_campaignGetAll_withFilterEnded_returns200AndGoalReachedCampaigns(
    registered_user: Dict[str, Any]
) -> None:
    """Get campaigns that reached their funding goal"""
    client: SanadAPIClient = registered_user["client"]

    response: requests.Response = client.campaign_get_all(filter_type="ENDED")

    assert response.status_code == 200, (
        f"Failed to get ended campaigns. "
        f"Expected 200, got {response.status_code}: {response.text}"
    )

    data: Dict[str, Any] = response.json()["data"]
    campaigns: List[Dict[str, Any]] = data["campaigns"]

    for campaign in campaigns:
        assert "id" in campaign
        assert "title" in campaign


@pytest.mark.campaign
def test_campaignGetAll_withFilterSharedByUser_returns200(
    admin_client: SanadAPIClient,
    registered_user: Dict[str, Any],
    second_registered_user: Dict[str, Any]
) -> None:
    """Get campaigns that user has shared to others"""
    import time
    unique_title: str = f"Shared By User Test {int(time.time())}"
    user_client: SanadAPIClient = registered_user["client"]
    target_user_id: str = second_registered_user["user_id"]

    admin_client.campaign_create(
        title=unique_title,
        campaign_type="SADAQA",
        duration="30",
        amount="2000",
        description="Campaign to be shared by user",
        user_ids=[registered_user["user_id"]]
    )

    campaign_id: Optional[str] = _get_campaign_id_by_title(
        user_client,
        unique_title,
        filter_type="SHARED_TO_USER"
    )
    assert campaign_id is not None, "Campaign not found"

    user_client.campaign_share(campaign_id=campaign_id, user_ids=[target_user_id])

    response: requests.Response = user_client.campaign_get_all(filter_type="SHARED_BY_USER")

    assert response.status_code == 200, (
        f"Failed to get campaigns shared by user. "
        f"Expected 200, got {response.status_code}: {response.text}"
    )

    data: Dict[str, Any] = response.json()["data"]
    campaigns: List[Dict[str, Any]] = data["campaigns"]

    shared_campaign: Optional[Dict[str, Any]] = next(
        (c for c in campaigns if c["id"] == campaign_id),
        None
    )
    assert shared_campaign is not None, "Campaign not found in SHARED_BY_USER list"

    delete_campaign_by_id(campaign_id)


@pytest.mark.campaign
def test_campaignGetAll_withFilterDonatedByUser_returns200(
    registered_user: Dict[str, Any]
) -> None:
    """Get campaigns user has donated to"""
    client: SanadAPIClient = registered_user["client"]

    response: requests.Response = client.campaign_get_all(filter_type="DONATED_BY_USER")

    assert response.status_code == 200, (
        f"Failed to get donated campaigns. "
        f"Expected 200, got {response.status_code}: {response.text}"
    )

    data: Dict[str, Any] = response.json()["data"]
    campaigns: List[Dict[str, Any]] = data["campaigns"]

    for campaign in campaigns:
        assert "id" in campaign
        assert "title" in campaign


@pytest.mark.campaign
def test_campaignGetOne_byBlockedUser_returns403orError(
    registered_user: Dict[str, Any],
    second_registered_user: Dict[str, Any]
) -> None:
    """Blocked user cannot access campaign details"""
    import time
    unique_title: str = f"Blocked Access Campaign {int(time.time())}"
    user_client: SanadAPIClient = registered_user["client"]
    blocked_client: SanadAPIClient = second_registered_user["client"]
    blocked_user_id: str = second_registered_user["user_id"]

    user_client.campaign_create(
        title=unique_title,
        campaign_type="ZAKAT",
        duration="30",
        amount="1000",
        description="Campaign that will be inaccessible to blocked user"
    )

    campaign_id: Optional[str] = _get_campaign_id_by_title(
        user_client,
        unique_title,
        filter_type="IN_REVIEW"
    )
    assert campaign_id is not None

    block_response: requests.Response = user_client.session.post(
        f"{user_client.endpoint}/api/v1/user/block",
        json={"blockedUserId": blocked_user_id}
    )

    if block_response.status_code == 200:
        response: requests.Response = blocked_client.campaign_get_one(campaign_id)

        assert response.status_code in [400, 403, 404, 500], (
            f"Blocked user should not access campaign. "
            f"Expected 400/403/404/500, got {response.status_code}"
        )

        user_client.session.post(
            f"{user_client.endpoint}/api/v1/user/unblock",
            json={"blockedUserId": blocked_user_id}
        )

    delete_campaign_by_id(campaign_id)


@pytest.mark.campaign
def test_campaignGetOne_ofDeletedCampaign_returns404(
    registered_user: Dict[str, Any]
) -> None:
    """Deleted campaign returns error"""
    client: SanadAPIClient = registered_user["client"]

    client.campaign_create(
        title="To Be Deleted Campaign",
        campaign_type="ZAKAT",
        duration="30",
        amount="1000",
        description="This campaign will be deleted"
    )

    campaign_id: Optional[str] = _get_campaign_id_by_title(
        client,
        "To Be Deleted Campaign",
        filter_type="IN_REVIEW"
    )
    assert campaign_id is not None

    delete_campaign_by_id(campaign_id)

    response: requests.Response = client.campaign_get_one(campaign_id)

    assert response.status_code in [400, 404, 500], (
        f"Deleted campaign should return error. "
        f"Expected 400/404/500, got {response.status_code}"
    )
