"""
Campaign bug verification tests

This file contains tests to verify specific bugs in the campaign functionality:
- BUG #8: Campaign end date calculation error (duration type mismatch)
- BUG #10: Duplicate campaigns in feed (no deduplication)

KNOWN LIMITATIONS:
- Uses raw session.put() calls because api_client.campaign_admin_update()
  doesn't exist yet
- Uses raw session.post() calls because api_client.campaign_share()
  doesn't exist yet
- Once API client methods are added, refactor to use them

TODO: Add these methods to api_client.py:
- campaign_admin_update(campaign_id, status, duration, ...)
- campaign_share(campaign_id, group_ids, user_ids, new_users)
"""

import pytest
import requests
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from src.api_client import SanadAPIClient
from src.db_utils import get_campaign_by_id, delete_campaign_by_id, get_user_edge_count


# ========================================
# BUG #8: CAMPAIGN END DATE CALCULATION ERROR
# ========================================

@pytest.mark.campaign
@pytest.mark.bug_verification
def test_bug8_adminApproveCampaign_withDurationTypeMismatch_returnsCorrectType(
    admin_client: SanadAPIClient,
    test_campaign: Dict[str, Any]
) -> None:
    """
    BUG #8: Verify end date calculation when admin approves with new duration

    Location: controllers.ts:1419-1443 - updateCampaignByAdmin()
    Root Cause: Type mismatch - req.body.duration is STRING but moment().add() expects NUMBER

    Expected Failure: End date will be incorrectly calculated due to STRING being passed to moment().add()

    If this test passes, the bug has been fixed.
    If this test fails, the bug is confirmed and end date calculation is incorrect.
    """
    campaign_id: str = test_campaign["campaign_id"]

    # Capture current time before approval
    approval_time_before: datetime = datetime.utcnow()

    # Admin updates campaign with new duration="45" AND approves it
    new_duration_str: str = "45"

    # Use raw session.put() because campaign_admin_update() doesn't exist yet
    response: requests.Response = admin_client.session.put(
        f"{admin_client.endpoint}/api/v1/campaign/admin/update",
        data={
            "campaignId": campaign_id,
            "status": "APPROVED",
            "duration": new_duration_str  # Sending as STRING
        }
    )

    # Capture time after approval
    approval_time_after: datetime = datetime.utcnow()

    if response.status_code != 200:
        pytest.skip(
            f"Cannot verify bug fix: Admin update endpoint returned "
            f"{response.status_code}: {response.text}. "
            f"Backend may need to be running or endpoint may have changed."
        )

    # Fetch campaign from database
    db_campaign: Optional[Dict[str, Any]] = get_campaign_by_id(campaign_id)
    assert db_campaign is not None, f"Campaign {campaign_id} not found in database"

    # Calculate expected end date: approval_time + 45 days
    expected_end_date_min: datetime = approval_time_before + timedelta(days=int(new_duration_str))
    expected_end_date_max: datetime = approval_time_after + timedelta(days=int(new_duration_str))

    # Parse actual end date from database
    actual_end_date_str: Any = db_campaign["end_date"]

    # Handle different datetime formats
    if isinstance(actual_end_date_str, str):
        # Remove timezone indicator if present
        actual_end_date_str = actual_end_date_str.replace("Z", "+00:00")
        try:
            actual_end_date: datetime = datetime.fromisoformat(actual_end_date_str)
        except ValueError:
            # Try parsing without timezone
            actual_end_date = datetime.strptime(
                actual_end_date_str.split("+")[0].split(".")[0],
                "%Y-%m-%d %H:%M:%S"
            )
    else:
        actual_end_date = actual_end_date_str

    # Remove timezone info for comparison
    if actual_end_date.tzinfo:
        actual_end_date = actual_end_date.replace(tzinfo=None)

    # BUG TEST: If bug exists, end date will be wrong
    # Allow 5 second tolerance for processing time
    is_within_expected_range: bool = (
        expected_end_date_min <= actual_end_date <= expected_end_date_max + timedelta(seconds=5)
    )

    # Diagnostic output for debugging
    print(f"\n=== BUG #8 VERIFICATION ===")
    print(f"New duration (STRING): '{new_duration_str}'")
    print(f"Expected end date: {expected_end_date_min} to {expected_end_date_max}")
    print(f"Actual end date: {actual_end_date}")
    print(f"Difference: {(actual_end_date - expected_end_date_min).total_seconds()} seconds")

    if not is_within_expected_range:
        print("BUG CONFIRMED: End date calculation is INCORRECT")
        print(f"   Expected: approval_time + {new_duration_str} days")
        print(f"   Got: {actual_end_date}")
        pytest.fail(
            f"BUG #8 CONFIRMED: End date calculation incorrect. "
            f"Expected between {expected_end_date_min} and {expected_end_date_max}, "
            f"got {actual_end_date}. "
            f"Duration field is likely being treated as string instead of int."
        )
    else:
        print("BUG FIXED: End date calculation is CORRECT")
        # Test passes - bug has been fixed


# ========================================
# BUG #10: DUPLICATE CAMPAIGNS IN FEED
# ========================================

@pytest.mark.campaign
@pytest.mark.bug_verification
def test_bug10_campaignShare_toSameUserMultipleTimes_deduplicatesUserEdge(
    registered_user: Dict[str, Any],
    second_registered_user: Dict[str, Any],
    third_user: Dict[str, Any],
    approved_campaign: Dict[str, Any]
) -> None:
    """
    BUG #10: Verify campaigns don't appear multiple times when shared by different users

    Location: controllers.ts:247-269 - getCampaigns() with sharedToUser filter
    Root Cause: No deduplication when multiple users share same campaign

    Expected Failure: Same campaign appears multiple times in the list

    If this test passes, the bug has been fixed and campaigns are deduplicated.
    If this test fails, the bug is confirmed and duplicates appear in the feed.
    """
    campaign_id: str = approved_campaign["campaign_id"]

    # User C will receive the campaign from both User A and User B
    user_a_client: SanadAPIClient = registered_user["client"]
    user_b_client: SanadAPIClient = second_registered_user["client"]
    user_c: Dict[str, Any] = third_user
    user_c_id: str = user_c["user_id"]
    user_c_client: SanadAPIClient = user_c["client"]

    # User A shares campaign to User C
    # Use raw session.post() because campaign_share() doesn't exist yet
    share_response_a: requests.Response = user_a_client.session.post(
        f"{user_a_client.endpoint}/api/v1/campaign/share",
        json={
            "campaignId": campaign_id,
            "groupIds": [],
            "userIds": [user_c_id],
            "newUsers": []
        }
    )

    if share_response_a.status_code != 200:
        pytest.skip(
            f"Cannot verify bug fix: Share endpoint (User A) returned "
            f"{share_response_a.status_code}: {share_response_a.text}. "
            f"Backend may need to be running or endpoint may have changed."
        )

    print(f"\n=== User A shared campaign {campaign_id} to User C ===")

    # User B also shares the SAME campaign to User C
    share_response_b: requests.Response = user_b_client.session.post(
        f"{user_b_client.endpoint}/api/v1/campaign/share",
        json={
            "campaignId": campaign_id,
            "groupIds": [],
            "userIds": [user_c_id],
            "newUsers": []
        }
    )

    if share_response_b.status_code != 200:
        pytest.skip(
            f"Cannot verify bug fix: Share endpoint (User B) returned "
            f"{share_response_b.status_code}: {share_response_b.text}. "
            f"Backend may need to be running or endpoint may have changed."
        )

    print(f"=== User B shared campaign {campaign_id} to User C ===")

    # Verify 2 UserEdge records exist in database
    share_count: int = get_user_edge_count(campaign_id, user_c_id)
    print(f"=== UserEdge records for campaign {campaign_id} shared to User C: {share_count} ===")

    assert share_count == 2, (
        f"Expected 2 share records in UserEdge table, found {share_count}. "
        f"Test setup failed - campaign should be shared twice."
    )

    # User C fetches campaigns with filter="SHARED_TO_USER"
    campaigns_response: requests.Response = user_c_client.campaign_get_all(filter_type="SHARED_TO_USER")

    assert campaigns_response.status_code == 200, (
        f"Failed to get campaigns for User C. "
        f"Expected 200, got {campaigns_response.status_code}: {campaigns_response.text}"
    )

    campaigns_data: Dict[str, Any] = campaigns_response.json()["data"]
    campaigns: List[Dict[str, Any]] = campaigns_data["campaigns"]

    # Count how many times our campaign appears in the list
    campaign_ids: List[str] = [c["id"] for c in campaigns]
    occurrences: int = campaign_ids.count(campaign_id)

    print(f"\n=== BUG #10 VERIFICATION ===")
    print(f"Campaign {campaign_id} shared by 2 users (A and B) to User C")
    print(f"UserEdge records: {share_count}")
    print(f"Occurrences in SHARED_TO_USER list: {occurrences}")
    print(f"Total campaigns in list: {len(campaigns)}")
    print(f"Unique campaigns: {len(set(campaign_ids))}")

    if occurrences > 1:
        print(f"BUG CONFIRMED: Campaign appears {occurrences} times (DUPLICATE!)")
        pytest.fail(
            f"BUG #10 CONFIRMED: Campaign {campaign_id} appears {occurrences} times in SHARED_TO_USER list. "
            f"Expected 1 occurrence (deduplicated), but found {occurrences}. "
            f"Root cause: No deduplication in controllers.ts:264-266. "
            f"Backend should use DISTINCT or GROUP BY to deduplicate campaigns."
        )
    elif occurrences == 1:
        print("BUG FIXED: Campaign appears exactly once (deduplicated correctly)")
        # Test passes - bug has been fixed
    else:
        print("WARNING: Campaign not found in SHARED_TO_USER list at all")
        pytest.fail(
            f"Campaign {campaign_id} not found in SHARED_TO_USER list for User C. "
            f"Expected 1 occurrence but found 0. Sharing may not be working correctly."
        )
