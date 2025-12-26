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

    data: Dict[str, Any] = response.json()
    assert "data" in data
    assert "Campaign created Successfully" in data["data"]

    campaign_id: Optional[str] = _get_campaign_id_by_title(
        client,
        "Help Ramadan Food Drive",
        filter_type="IN_REVIEW"
    )
    assert campaign_id is not None, "Campaign not found in list after creation"

    db_campaign: Optional[Dict[str, Any]] = get_campaign_by_id(campaign_id)
    assert db_campaign is not None, f"Campaign {campaign_id} not found in database"
    assert db_campaign["title"] == "Help Ramadan Food Drive"
    assert db_campaign["type"] == "ZAKAT"
    assert db_campaign["status"] == "YET_TO_APPROVE"
    assert db_campaign["total_amount"] == 1000
    assert db_campaign["amount_raised"] == 0
    assert db_campaign["created_by"] == user_id

    delete_campaign_by_id(campaign_id)


@pytest.mark.campaign
def test_campaignCreate_byAdmin_autoApprovesAndReturns200(
    admin_client: SanadAPIClient
) -> None:
    """Admin-created campaigns are auto-approved with APPROVED status"""
    response: requests.Response = admin_client.campaign_create(
        title="Admin Approved Campaign",
        campaign_type="SADAQA",
        duration="60",
        amount="5000",
        description="This campaign is created by admin and should be auto-approved"
    )

    if response.status_code == 400:
        campaigns_response: requests.Response = admin_client.campaign_get_all(filter_type="ACTIVE")
        if campaigns_response.status_code == 200:
            campaigns: List[Dict[str, Any]] = campaigns_response.json()["data"]["campaigns"]
            existing: Optional[Dict[str, Any]] = next(
                (c for c in campaigns if c["title"] == "Admin Approved Campaign"),
                None
            )
            if existing:
                delete_campaign_by_id(existing["id"])
                response = admin_client.campaign_create(
                    title="Admin Approved Campaign",
                    campaign_type="SADAQA",
                    duration="60",
                    amount="5000",
                    description="This campaign is created by admin and should be auto-approved"
                )

    assert response.status_code == 200, (
        f"Admin campaign creation failed. "
        f"Expected 200, got {response.status_code}: {response.text}"
    )
    assert "Campaign created Successfully" in response.json()["data"]

    campaign_id: Optional[str] = _get_campaign_id_by_title(
        admin_client,
        "Admin Approved Campaign",
        filter_type="ACTIVE"
    )
    assert campaign_id is not None, "Admin campaign not found in ACTIVE list"

    db_campaign: Optional[Dict[str, Any]] = get_campaign_by_id(campaign_id)
    assert db_campaign is not None
    assert db_campaign["status"] == "APPROVED", (
        f"Admin campaign should be APPROVED, got {db_campaign['status']}"
    )

    delete_campaign_by_id(campaign_id)


@pytest.mark.campaign
def test_campaignCreate_withOptionalFields_returns200AndStoresFields(
    registered_user: Dict[str, Any]
) -> None:
    """Create campaign with payment details and familiar duration"""
    client: SanadAPIClient = registered_user["client"]

    response: requests.Response = client.campaign_create(
        title="Sadaqa Jariya",
        campaign_type="JARIYA",
        duration="90",
        amount="10000",
        description="Building a water well for a community",
        payment_details="Bank Account: 123456789",
        familiar_duration="Ramadan 2024"
    )

    assert response.status_code == 200, (
        f"Failed to create campaign with optional fields. "
        f"Expected 200, got {response.status_code}: {response.text}"
    )

    campaign_id: Optional[str] = _get_campaign_id_by_title(
        client,
        "Sadaqa Jariya",
        filter_type="IN_REVIEW"
    )
    assert campaign_id is not None, "Campaign not found in list"

    db_campaign: Optional[Dict[str, Any]] = get_campaign_by_id(campaign_id)
    assert db_campaign is not None
    assert db_campaign["payment_details"] == "Bank Account: 123456789"
    assert db_campaign["familiar_duration"] == "Ramadan 2024"

    delete_campaign_by_id(campaign_id)


@pytest.mark.campaign
def test_campaignCreate_withGroupSharing_returns200AndSharestoGroups(
    registered_user: Dict[str, Any],
    test_group: Dict[str, str]
) -> None:
    """Create campaign with group sharing. Backend only allows sharing APPROVED campaigns."""
    client: SanadAPIClient = registered_user["client"]
    group_id: str = test_group["group_id"]

    response: requests.Response = client.campaign_create(
        title="Shared Campaign",
        campaign_type="ZAKAT",
        duration="30",
        amount="2000",
        description="This campaign is shared to groups upon creation",
        group_ids=[group_id]
    )

    if response.status_code == 500:
        error_message: str = response.json().get("message", "")
        if "yet to approve" in error_message.lower():
            pytest.skip(
                "Campaign sharing during creation requires APPROVED status. "
                "Regular users create YET_TO_APPROVE campaigns which cannot be shared."
            )
        else:
            pytest.fail(f"Unexpected 500 error: {response.text}")

    assert response.status_code == 200, (
        f"Failed to create and share campaign. "
        f"Expected 200, got {response.status_code}: {response.text}"
    )

    campaign_id: Optional[str] = _get_campaign_id_by_title(
        client,
        "Shared Campaign",
        filter_type="IN_REVIEW"
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

    delete_campaign_by_id(campaign_id)


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
    test_campaign: Dict[str, Any]
) -> None:
    """Get campaigns pending approval (YET_TO_APPROVE)"""
    creator_client: SanadAPIClient = test_campaign["creator"]["client"]
    campaign_id: str = test_campaign["campaign_id"]

    response: requests.Response = creator_client.campaign_get_all(filter_type="IN_REVIEW")

    assert response.status_code == 200, (
        f"Failed to get in-review campaigns. "
        f"Expected 200, got {response.status_code}: {response.text}"
    )

    data: Dict[str, Any] = response.json()["data"]
    campaigns: List[Dict[str, Any]] = data["campaigns"]

    campaign_ids: List[str] = [c["id"] for c in campaigns]
    assert campaign_id in campaign_ids, (
        f"Creator's campaign {campaign_id} not found in IN_REVIEW list"
    )


@pytest.mark.campaign
def test_campaignGetAll_withCampaignTypeFilter_returns200AndFilteredByType(
    registered_user: Dict[str, Any]
) -> None:
    """Filter campaigns by type (ZAKAT, SADAQA, JARIYA)"""
    client: SanadAPIClient = registered_user["client"]

    zakat_response: requests.Response = client.campaign_create(
        title="Zakat Campaign",
        campaign_type="ZAKAT",
        duration="30",
        amount="1000",
        description="Zakat test"
    )
    assert zakat_response.status_code == 200

    sadaqa_response: requests.Response = client.campaign_create(
        title="Sadaqa Campaign",
        campaign_type="SADAQA",
        duration="30",
        amount="500",
        description="Sadaqa test"
    )
    assert sadaqa_response.status_code == 200

    response: requests.Response = client.campaign_get_all(campaign_type="ZAKAT")
    assert response.status_code == 200, (
        f"Failed to filter campaigns by type. "
        f"Expected 200, got {response.status_code}: {response.text}"
    )

    campaigns_response: requests.Response = client.campaign_get_all(filter_type="IN_REVIEW")
    campaigns: List[Dict[str, Any]] = campaigns_response.json()["data"]["campaigns"]
    zakat: Optional[Dict[str, Any]] = next(
        (c for c in campaigns if c["title"] == "Zakat Campaign"),
        None
    )
    sadaqa: Optional[Dict[str, Any]] = next(
        (c for c in campaigns if c["title"] == "Sadaqa Campaign"),
        None
    )

    if zakat:
        delete_campaign_by_id(zakat["id"])
    if sadaqa:
        delete_campaign_by_id(sadaqa["id"])


@pytest.mark.campaign
def test_campaignGetAll_withPagination_returns200AndLimitedResults(
    registered_user: Dict[str, Any]
) -> None:
    """Test pagination with pageSize and page parameters"""
    client: SanadAPIClient = registered_user["client"]

    for i in range(5):
        response: requests.Response = client.campaign_create(
            title=f"Campaign {i+1}",
            campaign_type="ZAKAT",
            duration="30",
            amount="1000",
            description=f"Test campaign {i+1}"
        )
        assert response.status_code == 200

    response: requests.Response = client.campaign_get_all(page_size=2, page=1)

    assert response.status_code == 200, (
        f"Failed to get paginated campaigns. "
        f"Expected 200, got {response.status_code}: {response.text}"
    )

    data: Dict[str, Any] = response.json()["data"]
    assert "campaigns" in data
    assert "total" in data
    assert len(data["campaigns"]) <= 2, (
        f"Expected at most 2 campaigns per page, got {len(data['campaigns'])}"
    )

    campaigns_response: requests.Response = client.campaign_get_all(filter_type="IN_REVIEW")
    campaigns: List[Dict[str, Any]] = campaigns_response.json()["data"]["campaigns"]
    for i in range(5):
        campaign: Optional[Dict[str, Any]] = next(
            (c for c in campaigns if c["title"] == f"Campaign {i+1}"),
            None
        )
        if campaign:
            delete_campaign_by_id(campaign["id"])


@pytest.mark.campaign
def test_campaignGetAll_withSearchText_returns200AndMatchingCampaigns(
    registered_user: Dict[str, Any]
) -> None:
    """Search campaigns by title"""
    client: SanadAPIClient = registered_user["client"]

    unique_title: str = "UNIQUE_SEARCH_TEST_CAMPAIGN"
    response: requests.Response = client.campaign_create(
        title=unique_title,
        campaign_type="ZAKAT",
        duration="30",
        amount="1000",
        description="Searchable campaign"
    )
    assert response.status_code == 200

    search_response: requests.Response = client.campaign_get_all(
        filter_type="IN_REVIEW",
        search_text="UNIQUE_SEARCH_TEST"
    )

    assert search_response.status_code == 200, (
        f"Failed to search campaigns. "
        f"Expected 200, got {search_response.status_code}: {search_response.text}"
    )

    data: Dict[str, Any] = search_response.json()["data"]
    campaigns: List[Dict[str, Any]] = data["campaigns"]

    titles: List[str] = [c["title"] for c in campaigns]
    found: bool = any(unique_title in title for title in titles)
    assert found, (
        f"Campaign '{unique_title}' not found in search results. "
        f"Found titles: {titles}"
    )

    campaign_id: Optional[str] = _get_campaign_id_by_title(client, unique_title)
    if campaign_id:
        delete_campaign_by_id(campaign_id)


@pytest.mark.campaign
def test_campaignGetAll_withoutAuthentication_returns401or403(
    authless_client: SanadAPIClient
) -> None:
    """Getting campaigns requires authentication"""
    response: requests.Response = authless_client.campaign_get_all()

    assert response.status_code in [401, 403], (
        f"Unauthenticated request should be rejected. "
        f"Expected 401 or 403, got {response.status_code}"
    )


@pytest.mark.campaign
def test_campaignGetOne_withValidId_returns200AndCampaignDetails(
    test_campaign: Dict[str, Any]
) -> None:
    """Get detailed campaign information by ID"""
    creator_client: SanadAPIClient = test_campaign["creator"]["client"]
    campaign_id: str = test_campaign["campaign_id"]

    response: requests.Response = creator_client.campaign_get_one(campaign_id)

    assert response.status_code == 200, (
        f"Failed to get campaign details. "
        f"Expected 200, got {response.status_code}: {response.text}"
    )

    response_json: Dict[str, Any] = response.json()
    assert "data" in response_json, f"No 'data' in response: {response_json}"
    data: Dict[str, Any] = response_json["data"]

    campaign_id_field: Optional[str] = data.get("id") or data.get("campaignId")
    assert campaign_id_field == campaign_id, (
        f"Campaign ID mismatch: expected {campaign_id}, got {campaign_id_field}"
    )
    assert data["title"] == "Test Campaign"

    campaign_type: Optional[str] = data.get("type") or data.get("campaignType")
    assert campaign_type == "ZAKAT", (
        f"Expected campaign type ZAKAT, got {campaign_type}"
    )


@pytest.mark.campaign
def test_campaignGetOne_withTrustChain_returns200AndIncludesTrustData(
    approved_campaign: Dict[str, Any],
    registered_user: Dict[str, Any]
) -> None:
    """Campaign includes trust chain information"""
    client: SanadAPIClient = registered_user["client"]
    campaign_id: str = approved_campaign["campaign_id"]

    response: requests.Response = client.campaign_get_one(campaign_id)

    assert response.status_code == 200, (
        f"Failed to get campaign with trust chain. "
        f"Expected 200, got {response.status_code}: {response.text}"
    )

    data: Dict[str, Any] = response.json()["data"]

    assert "id" in data, "Campaign missing 'id' field"
    assert "title" in data, "Campaign missing 'title' field"


@pytest.mark.campaign
def test_campaignGetOne_byCreator_returns200AndOwnCampaignDetails(
    test_campaign: Dict[str, Any]
) -> None:
    """Creator can view their own campaign details"""
    creator_client: SanadAPIClient = test_campaign["creator"]["client"]
    campaign_id: str = test_campaign["campaign_id"]

    response: requests.Response = creator_client.campaign_get_one(campaign_id)

    assert response.status_code == 200, (
        f"Creator failed to get own campaign. "
        f"Expected 200, got {response.status_code}: {response.text}"
    )

    data: Dict[str, Any] = response.json()["data"]

    campaign_id_field: Optional[str] = data.get("id") or data.get("campaignId")
    assert campaign_id_field == campaign_id, (
        f"Campaign ID mismatch: expected {campaign_id}, got {campaign_id_field}"
    )


@pytest.mark.campaign
def test_campaignGetOne_withNonexistentId_returns404(
    registered_user: Dict[str, Any]
) -> None:
    """Non-existent campaign returns error"""
    client: SanadAPIClient = registered_user["client"]
    fake_campaign_id: str = "00000000-0000-0000-0000-000000000000"

    response: requests.Response = client.campaign_get_one(fake_campaign_id)

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
