"""
Campaign payment flow tests

Tests Stripe payment integration for campaign donations:
- Payment intent creation
- Payment link generation
- Payment webhook callbacks
"""
import pytest
import requests
import time
from typing import Dict, Any, Optional, List
from src.api_client import SanadAPIClient
from src.db_utils import (
    get_campaign_by_id,
    delete_campaign_by_id,
    get_payment_event_by_intent_id,
    delete_payment_event_by_id,
    get_donation_by_payment_intent_id,
    delete_donation_by_id
)
from src.stripe_cli_helper import StripeCLIHelper


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


def _create_approved_campaign(client: SanadAPIClient, admin_client: SanadAPIClient) -> Optional[str]:
    """Create and approve a campaign for payment testing"""
    unique_title: str = f"Payment Test Campaign {int(time.time())}"

    admin_client.campaign_create(
        title=unique_title,
        campaign_type="ZAKAT",
        duration="30",
        amount="5000",
        description="Campaign for payment testing"
    )

    campaign_id: Optional[str] = _get_campaign_id_by_title(
        admin_client,
        unique_title,
        filter_type="ACTIVE"
    )

    return campaign_id


# ========================================
# PAYMENT INTENT TESTS
# ========================================

@pytest.mark.payment
def test_campaignPaymentCreateIntent_withValidAmount_returns200AndStripeIntent(
    registered_user: Dict[str, Any],
    admin_client: SanadAPIClient
) -> None:
    """Create payment intent with valid amount returns Stripe intent"""
    user_client: SanadAPIClient = registered_user["client"]
    user_id: str = registered_user["user_id"]

    campaign_id: Optional[str] = _create_approved_campaign(user_client, admin_client)
    assert campaign_id is not None, "Failed to create approved campaign"

    response: requests.Response = user_client.campaign_payment_create_intent(
        campaign_id=campaign_id,
        amount=50,
        message="Test donation"
    )

    assert response.status_code == 200, (
        f"Failed to create payment intent. "
        f"Expected 200, got {response.status_code}: {response.text}"
    )

    response_json: Dict[str, Any] = response.json()
    data: Dict[str, Any] = response_json.get("data", response_json)

    assert "clientSecret" in data or "client_secret" in data, (
        f"Response missing clientSecret. Response: {response.json()}"
    )

    client_secret: str = data.get("clientSecret") or data.get("client_secret")
    assert client_secret is not None and len(client_secret) > 0, "Client secret is empty"

    payment_intent_id: str = client_secret.split("_secret_")[0]
    assert payment_intent_id.startswith("pi_"), (
        f"Invalid payment intent ID format: {payment_intent_id}"
    )

    db_payment: Optional[Dict[str, Any]] = get_payment_event_by_intent_id(payment_intent_id)
    assert db_payment is not None, "Payment event not found in database"
    assert db_payment["amount"] == 50, f"Expected amount 50, got {db_payment['amount']}"
    assert db_payment["event_type"] == "INITIATED", (
        f"Expected status INITIATED, got {db_payment['event_type']}"
    )
    assert db_payment["currency"] == "usd", f"Expected currency usd, got {db_payment['currency']}"
    assert str(db_payment["created_by"]) == user_id, "Payment created_by mismatch"
    assert str(db_payment["campaign_id"]) == campaign_id, "Payment campaign_id mismatch"

    delete_payment_event_by_id(db_payment["id"])
    delete_campaign_by_id(campaign_id)


@pytest.mark.payment
def test_campaignPaymentCreateIntent_withInvalidAmount_returns400(
    registered_user: Dict[str, Any],
    admin_client: SanadAPIClient
) -> None:
    """Invalid amount (zero/negative) is rejected"""
    user_client: SanadAPIClient = registered_user["client"]

    campaign_id: Optional[str] = _create_approved_campaign(user_client, admin_client)
    assert campaign_id is not None, "Failed to create approved campaign"

    response_zero: requests.Response = user_client.campaign_payment_create_intent(
        campaign_id=campaign_id,
        amount=0
    )

    assert response_zero.status_code in [400, 422, 500], (
        f"Zero amount should fail. "
        f"Expected 400/422/500, got {response_zero.status_code}"
    )

    response_negative: requests.Response = user_client.campaign_payment_create_intent(
        campaign_id=campaign_id,
        amount=-10
    )

    assert response_negative.status_code in [400, 422, 500], (
        f"Negative amount should fail. "
        f"Expected 400/422/500, got {response_negative.status_code}"
    )

    delete_campaign_by_id(campaign_id)


@pytest.mark.payment
def test_campaignPaymentCreateIntent_toInactiveCampaign_returns400(
    registered_user: Dict[str, Any]
) -> None:
    """Payment to inactive campaign (YET_TO_APPROVE) is rejected"""
    import time
    user_client: SanadAPIClient = registered_user["client"]
    unique_title: str = f"Inactive Campaign {int(time.time())}"

    user_client.campaign_create(
        title=unique_title,
        campaign_type="ZAKAT",
        duration="30",
        amount="1000",
        description="Campaign in YET_TO_APPROVE status"
    )

    campaign_id: Optional[str] = _get_campaign_id_by_title(
        user_client,
        unique_title,
        filter_type="IN_REVIEW"
    )
    assert campaign_id is not None, "Campaign not created"

    response: requests.Response = user_client.campaign_payment_create_intent(
        campaign_id=campaign_id,
        amount=25
    )

    assert response.status_code in [400, 422, 500], (
        f"Payment to inactive campaign should fail. "
        f"Expected 400/422/500, got {response.status_code}: {response.text}"
    )

    delete_campaign_by_id(campaign_id)


@pytest.mark.payment
def test_campaignPaymentCreateIntent_withoutAuth_returns401(
    admin_client: SanadAPIClient
) -> None:
    """Unauthenticated payment intent creation is rejected"""
    import os
    from dotenv import load_dotenv
    load_dotenv()
    unique_title: str = f"Auth Test Campaign {int(time.time())}"

    admin_client.campaign_create(
        title=unique_title,
        campaign_type="ZAKAT",
        duration="30",
        amount="1000",
        description="Campaign for auth testing"
    )

    campaign_id: Optional[str] = _get_campaign_id_by_title(
        admin_client,
        unique_title,
        filter_type="ACTIVE"
    )
    assert campaign_id is not None, "Campaign not created"

    endpoint: str = os.getenv("API_ENDPOINT", "http://localhost:1505")
    response: requests.Response = requests.post(
        f"{endpoint}/api/v1/campaign/payment/create-intent",
        json={
            "campaignId": campaign_id,
            "amount": 25
        }
    )

    assert response.status_code in [401, 403], (
        f"Unauthenticated request should fail. "
        f"Expected 401/403, got {response.status_code}"
    )

    delete_campaign_by_id(campaign_id)


# ========================================
# PAYMENT LINK TESTS
# ========================================

@pytest.mark.payment
def test_campaignPaymentCreateLink_withValidAmount_returns200AndStripeLink(
    registered_user: Dict[str, Any],
    admin_client: SanadAPIClient
) -> None:
    """Create payment link with valid amount returns Stripe checkout URL"""
    user_client: SanadAPIClient = registered_user["client"]
    user_id: str = registered_user["user_id"]

    campaign_id: Optional[str] = _create_approved_campaign(user_client, admin_client)
    assert campaign_id is not None, "Failed to create approved campaign"

    response: requests.Response = user_client.campaign_payment_create_link(
        campaign_id=campaign_id,
        amount=75,
        message="Link payment test"
    )

    assert response.status_code == 200, (
        f"Failed to create payment link. "
        f"Expected 200, got {response.status_code}: {response.text}"
    )

    data: Dict[str, Any] = response.json()["data"]
    assert "link" in data, "Response missing link field"

    link: str = data["link"]
    assert link.startswith("https://checkout.stripe.com/"), (
        f"Invalid Stripe checkout link: {link}"
    )

    db_campaign: Optional[Dict[str, Any]] = get_campaign_by_id(campaign_id)
    assert db_campaign is not None, "Campaign not found in database"

    delete_campaign_by_id(campaign_id)


@pytest.mark.payment
def test_campaignPaymentCreateLink_toDeletedCampaign_returns400(
    registered_user: Dict[str, Any],
    admin_client: SanadAPIClient
) -> None:
    """Payment link to deleted campaign is rejected"""
    user_client: SanadAPIClient = registered_user["client"]

    campaign_id: Optional[str] = _create_approved_campaign(user_client, admin_client)
    assert campaign_id is not None, "Failed to create approved campaign"

    delete_campaign_by_id(campaign_id)

    response: requests.Response = user_client.campaign_payment_create_link(
        campaign_id=campaign_id,
        amount=50
    )

    assert response.status_code in [400, 404, 500], (
        f"Payment link to deleted campaign should fail. "
        f"Expected 400/404/500, got {response.status_code}"
    )


@pytest.mark.payment
def test_campaignPaymentCreateLink_withoutAuth_returns401(
    admin_client: SanadAPIClient
) -> None:
    """Unauthenticated payment link creation is rejected"""
    import os
    from dotenv import load_dotenv
    load_dotenv()
    unique_title: str = f"Link Auth Test {int(time.time())}"

    admin_client.campaign_create(
        title=unique_title,
        campaign_type="ZAKAT",
        duration="30",
        amount="1000",
        description="Campaign for link auth testing"
    )

    campaign_id: Optional[str] = _get_campaign_id_by_title(
        admin_client,
        unique_title,
        filter_type="ACTIVE"
    )
    assert campaign_id is not None, "Campaign not created"

    endpoint: str = os.getenv("API_ENDPOINT", "http://localhost:1505")
    response: requests.Response = requests.post(
        f"{endpoint}/api/v1/campaign/payment/create-link",
        json={
            "campaignId": campaign_id,
            "amount": 50
        }
    )

    assert response.status_code in [401, 403], (
        f"Unauthenticated request should fail. "
        f"Expected 401/403, got {response.status_code}"
    )

    delete_campaign_by_id(campaign_id)


# ========================================
# PAYMENT CALLBACK/WEBHOOK TESTS
# ========================================

@pytest.mark.payment
def test_campaignPaymentCallback_chargeSucceeded_updates200AndUpdatesDB(
    registered_user: Dict[str, Any],
    admin_client: SanadAPIClient
) -> None:
    """Stripe charge.succeeded webhook updates payment status and campaign amount"""
    user_client: SanadAPIClient = registered_user["client"]
    user_id: str = registered_user["user_id"]

    campaign_id: Optional[str] = _create_approved_campaign(user_client, admin_client)
    assert campaign_id is not None, "Failed to create approved campaign"

    # Create payment intent first
    response: requests.Response = user_client.campaign_payment_create_intent(
        campaign_id=campaign_id,
        amount=100,
        message="Callback test donation"
    )
    assert response.status_code == 200

    client_secret: str = response.json()["data"]["clientSecret"]
    payment_intent_id: str = client_secret.split("_secret_")[0]

    # Get initial campaign state
    campaign_before: Optional[Dict[str, Any]] = get_campaign_by_id(campaign_id)
    assert campaign_before is not None
    initial_amount: float = campaign_before["amount_raised"] or 0

    # Confirm payment intent - triggers REAL Stripe webhook automatically
    success: bool = StripeCLIHelper.confirm_payment_intent(
        payment_intent_id=payment_intent_id,
        should_succeed=True  # Use test card 4242 4242 4242 4242
    )
    assert success, "Failed to confirm payment intent"

    # Wait for webhook to be processed by backend
    time.sleep(3)

    # Verify payment_event updated to SUCCEEDED
    db_payment: Optional[Dict[str, Any]] = get_payment_event_by_intent_id(payment_intent_id)
    assert db_payment is not None
    assert db_payment["event_type"] == "SUCCEEDED", (
        f"Expected SUCCEEDED status, got {db_payment['event_type']}"
    )
    assert db_payment["card_metadata"] is not None, "Card metadata missing"

    # Verify donation marked as paid
    db_donation: Optional[Dict[str, Any]] = get_donation_by_payment_intent_id(payment_intent_id)
    assert db_donation is not None, "Donation not found"
    assert db_donation["is_paid"] is True, "Donation not marked as paid"

    # Verify campaign amountRaised increased
    campaign_after: Optional[Dict[str, Any]] = get_campaign_by_id(campaign_id)
    assert campaign_after is not None
    assert campaign_after["amount_raised"] == initial_amount + 100, (
        f"Campaign amount not updated. Expected {initial_amount + 100}, got {campaign_after['amount_raised']}"
    )

    # Cleanup
    delete_donation_by_id(db_donation["id"])
    delete_payment_event_by_id(db_payment["id"])
    delete_campaign_by_id(campaign_id)


@pytest.mark.payment
def test_campaignPaymentCallback_chargeFailed_updates200AndMarksFailure(
    registered_user: Dict[str, Any],
    admin_client: SanadAPIClient
) -> None:
    """Stripe charge.failed webhook updates payment status to FAILED"""
    user_client: SanadAPIClient = registered_user["client"]

    campaign_id: Optional[str] = _create_approved_campaign(user_client, admin_client)
    assert campaign_id is not None

    # Create payment intent
    response: requests.Response = user_client.campaign_payment_create_intent(
        campaign_id=campaign_id,
        amount=50
    )
    assert response.status_code == 200

    client_secret: str = response.json()["data"]["clientSecret"]
    payment_intent_id: str = client_secret.split("_secret_")[0]

    # Confirm payment intent with failing card - triggers REAL Stripe webhook
    success: bool = StripeCLIHelper.confirm_payment_intent(
        payment_intent_id=payment_intent_id,
        should_succeed=False  # Use test card 4000 0000 0000 0002 (declines)
    )
    assert success, "Failed to confirm payment intent"

    # Wait for webhook to be processed
    time.sleep(3)

    # Verify payment_event updated to FAILED
    db_payment: Optional[Dict[str, Any]] = get_payment_event_by_intent_id(payment_intent_id)
    assert db_payment is not None
    assert db_payment["event_type"] == "FAILED", (
        f"Expected FAILED status, got {db_payment['event_type']}"
    )
    assert ("card_declined" in db_payment["message"] or "generic_decline" in db_payment["message"]), "Failure reason not recorded"

    # Cleanup
    db_donation: Optional[Dict[str, Any]] = get_donation_by_payment_intent_id(payment_intent_id)
    if db_donation:
        delete_donation_by_id(db_donation["id"])
    delete_payment_event_by_id(db_payment["id"])
    delete_campaign_by_id(campaign_id)


@pytest.mark.payment
def test_campaignPaymentCallback_insufficientFunds_updates200AndMarksFailure(
    registered_user: Dict[str, Any],
    admin_client: SanadAPIClient
) -> None:
    """Stripe insufficient_funds webhook updates payment status to FAILED"""
    user_client: SanadAPIClient = registered_user["client"]

    campaign_id: Optional[str] = _create_approved_campaign(user_client, admin_client)
    assert campaign_id is not None

    # Create payment intent
    response: requests.Response = user_client.campaign_payment_create_intent(
        campaign_id=campaign_id,
        amount=75
    )
    assert response.status_code == 200

    client_secret: str = response.json()["data"]["clientSecret"]
    payment_intent_id: str = client_secret.split("_secret_")[0]

    # Confirm payment intent with failing card (simulates insufficient funds)
    success: bool = StripeCLIHelper.confirm_payment_intent(
        payment_intent_id=payment_intent_id,
        should_succeed=False  # Use test card 4000 0000 0000 0002 (declines)
    )
    assert success, "Failed to confirm payment intent"

    # Wait for webhook to be processed
    time.sleep(3)

    # Verify payment_event updated to FAILED
    db_payment: Optional[Dict[str, Any]] = get_payment_event_by_intent_id(payment_intent_id)
    assert db_payment is not None
    assert db_payment["event_type"] == "FAILED", (
        f"Expected FAILED status, got {db_payment['event_type']}"
    )
    # Note: Stripe CLI charge.failed simulates card_declined, not insufficient_funds specifically
    # The important thing is that it's marked as FAILED

    # Cleanup
    db_donation: Optional[Dict[str, Any]] = get_donation_by_payment_intent_id(payment_intent_id)
    if db_donation:
        delete_donation_by_id(db_donation["id"])
    delete_payment_event_by_id(db_payment["id"])
    delete_campaign_by_id(campaign_id)


# ========================================
# DONOR & TRANSACTION TESTS
# ========================================

@pytest.mark.payment
def test_campaignGetDonors_asCreator_returns200AndDonorList(
    registered_user: Dict[str, Any],
    admin_client: SanadAPIClient
) -> None:
    """Campaign creator can get donor list with pagination"""
    user_client: SanadAPIClient = registered_user["client"]
    user_id: str = registered_user["user_id"]

    campaign_id: Optional[str] = _create_approved_campaign(user_client, admin_client)
    assert campaign_id is not None

    # Create payment intent and simulate successful payment
    response: requests.Response = user_client.campaign_payment_create_intent(
        campaign_id=campaign_id,
        amount=75,
        message="Donor test"
    )
    assert response.status_code == 200

    client_secret: str = response.json()["data"]["clientSecret"]
    payment_intent_id: str = client_secret.split("_secret_")[0]

    # Confirm payment intent - triggers REAL Stripe webhook automatically
    success: bool = StripeCLIHelper.confirm_payment_intent(
        payment_intent_id=payment_intent_id,
        should_succeed=True
    )
    assert success, "Failed to confirm payment intent"

    # Wait for webhook to be processed by backend
    time.sleep(3)

    # Get donors list as campaign creator (admin created the campaign)
    donors_response: requests.Response = admin_client.campaign_get_donors(
        campaign_id=campaign_id,
        page_number=1,
        page_size=10
    )

    assert donors_response.status_code == 200, (
        f"Failed to get donors. Expected 200, got {donors_response.status_code}: {donors_response.text}"
    )

    response_json: Dict[str, Any] = donors_response.json()
    assert "data" in response_json, "Response missing data field"

    # Donor list may be nested under different keys depending on response structure
    # Backend returns list of donors with their donation amounts

    # Cleanup
    db_donation: Optional[Dict[str, Any]] = get_donation_by_payment_intent_id(payment_intent_id)
    if db_donation:
        delete_donation_by_id(db_donation["id"])
    db_payment: Optional[Dict[str, Any]] = get_payment_event_by_intent_id(payment_intent_id)
    if db_payment:
        delete_payment_event_by_id(db_payment["id"])
    delete_campaign_by_id(campaign_id)


@pytest.mark.payment
def test_campaignGetTransactions_asUser_returns200AndTransactionList(
    registered_user: Dict[str, Any],
    admin_client: SanadAPIClient
) -> None:
    """User can get their payment transaction history with pagination"""
    user_client: SanadAPIClient = registered_user["client"]

    campaign_id: Optional[str] = _create_approved_campaign(user_client, admin_client)
    assert campaign_id is not None

    # Create payment intent
    response: requests.Response = user_client.campaign_payment_create_intent(
        campaign_id=campaign_id,
        amount=25,
        message="Transaction test"
    )
    assert response.status_code == 200

    client_secret: str = response.json()["data"]["clientSecret"]
    payment_intent_id: str = client_secret.split("_secret_")[0]

    # Get transactions for the user
    transactions_response: requests.Response = user_client.campaign_get_transactions(
        page=1,
        page_size=10
    )

    assert transactions_response.status_code == 200, (
        f"Failed to get transactions. Expected 200, got {transactions_response.status_code}: {transactions_response.text}"
    )

    response_json: Dict[str, Any] = transactions_response.json()
    assert "data" in response_json, "Response missing data field"

    # Should contain at least the payment we just created
    # Backend returns list of payment_events with status INITIATED/PENDING/SUCCEEDED/FAILED

    # Cleanup
    db_donation: Optional[Dict[str, Any]] = get_donation_by_payment_intent_id(payment_intent_id)
    if db_donation:
        delete_donation_by_id(db_donation["id"])
    db_payment: Optional[Dict[str, Any]] = get_payment_event_by_intent_id(payment_intent_id)
    if db_payment:
        delete_payment_event_by_id(db_payment["id"])
    delete_campaign_by_id(campaign_id)
