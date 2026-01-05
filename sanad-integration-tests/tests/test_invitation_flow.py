"""Invitation and registration flow tests"""
import pytest
import hashlib
import requests
from typing import Dict, Any, Optional
from src.api_client import SanadAPIClient, SanadClientFactory
from src.db_utils import get_user_by_phone, delete_user_by_phone


@pytest.mark.invitation
def test_inviteContacts_withSingleContact_returns200AndCreatesUser(
    user_client: SanadAPIClient,
    test_user_phone: str
) -> None:
    """Test inviting a single contact creates user in database"""
    response: requests.Response = user_client.invite_contacts([{"phone": test_user_phone}])
    assert response.status_code == 200

    # Verify user created in database
    user: Optional[Dict[str, Any]] = get_user_by_phone(test_user_phone)
    assert user is not None
    assert user["phone"] is None  # Phone not set until registration
    assert user["phone_hash"] == hashlib.sha256(test_user_phone.encode()).hexdigest()

    # Cleanup
    delete_user_by_phone(test_user_phone)


@pytest.mark.invitation
def test_inviteContacts_withMultipleContacts_returns200AndCreatesAllUsers(
    user_client: SanadAPIClient
) -> None:
    """Test inviting multiple contacts at once creates all users"""
    phones: list[str] = ["+12025551111", "+12025552222", "+12025553333"]
    contacts: list[Dict[str, str]] = [{"phone": phone} for phone in phones]

    response: requests.Response = user_client.invite_contacts(contacts)
    assert response.status_code == 200

    # Verify all users created
    for phone in phones:
        user: Optional[Dict[str, Any]] = get_user_by_phone(phone)
        assert user is not None
        delete_user_by_phone(phone)


@pytest.mark.invitation
def test_sendOtp_forInvitedUser_returns200(
    authless_client: SanadAPIClient,
    invited_user: Dict[str, str]
) -> None:
    """Test that invited user can request OTP for registration"""
    phone: str = invited_user["phone"]

    response: requests.Response = authless_client.user_send_otp(phone, "REGISTER")
    assert response.status_code == 200


@pytest.mark.invitation
def test_userRegister_forInvitedUser_returns200AndToken(
    client_factory: SanadClientFactory,
    authless_client: SanadAPIClient,
    invited_user: Dict[str, str],
    test_user_email: str,
    test_otp: str
) -> None:
    """Test that invited user can complete registration and receive token"""
    phone: str = invited_user["phone"]

    # Send OTP
    otp_response: requests.Response = authless_client.user_send_otp(phone, "REGISTER")
    assert otp_response.status_code == 200

    # Register
    register_response: requests.Response = authless_client.user_register(
        phone=phone,
        first_name="John",
        last_name="Doe",
        email=test_user_email,
        verification_code=test_otp
    )

    assert register_response.status_code == 200
    response_data: Dict[str, Any] = register_response.json()

    # Verify nested response structure
    assert "data" in response_data
    data: Dict[str, Any] = response_data["data"]
    assert "accessToken" in data
    assert "userId" in data
    assert len(data["accessToken"]) > 0

    # Verify can create authenticated client
    authenticated_client: SanadAPIClient = client_factory.create_authenticated_user_client(
        token=data["accessToken"],
        user_id=data["userId"]
    )
    profile_response: requests.Response = authenticated_client.user_get_auth_user()
    assert profile_response.status_code == 200

    # Verify user details updated in database
    user: Optional[Dict[str, Any]] = get_user_by_phone(phone)
    assert user is not None
    assert user["phone"] == phone
    assert user["first_name"] == "John"
    assert user["last_name"] == "Doe"
    assert user["email"] == test_user_email


@pytest.mark.invitation
def test_userRegister_withInvalidOtp_returns400or401(
    authless_client: SanadAPIClient,
    invited_user: Dict[str, str],
    test_user_email: str
) -> None:
    """Test that registration fails with invalid OTP"""
    phone: str = invited_user["phone"]

    # Send OTP
    authless_client.user_send_otp(phone, "REGISTER")

    # Try to register with wrong OTP
    response: requests.Response = authless_client.user_register(
        phone=phone,
        first_name="John",
        last_name="Doe",
        email=test_user_email,
        verification_code="999999"
    )

    assert response.status_code in [400, 401]


@pytest.mark.invitation
def test_sendOtp_forUninvitedUser_returns400(
    authless_client: SanadAPIClient,
    test_user_phone: str
) -> None:
    """Test that uninvited user cannot send OTP for registration"""
    # Try to send OTP without invitation - should fail
    # Backend validation: "Only invited users can register"
    otp_response: requests.Response = authless_client.user_send_otp(test_user_phone, "REGISTER")
    assert otp_response.status_code == 400


@pytest.mark.invitation
def test_userRegister_forUninvitedUser_returns200InDevMode(
    authless_client: SanadAPIClient,
    test_user_phone: str,
    test_user_email: str,
    test_otp: str
) -> None:
    """
    Test that uninvited user CAN register directly in development mode.

    In development mode, the backend auto-creates users on registration.
    Send OTP still requires invitation, but registration endpoint allows self-registration.
    """
    # Register without invitation (no OTP sending needed in dev mode)
    response: requests.Response = authless_client.user_register(
        phone=test_user_phone,
        first_name="Dev",
        last_name="User",
        email=test_user_email,
        verification_code=test_otp  # Use test OTP "111111"
    )

    # In dev mode, registration succeeds (backend creates user on-the-fly)
    assert response.status_code == 200

    # Cleanup
    delete_user_by_phone(test_user_phone)


@pytest.mark.invitation
def test_inviteContacts_byRegisteredUser_returns200AndCreatesUsers(
    registered_user: Dict[str, Any],
    test_otp: str
) -> None:
    """Test that newly registered user can invite other users"""
    client: SanadAPIClient = registered_user["client"]
    new_phone: str = "+12025559876"

    # Invite another user
    response: requests.Response = client.invite_contacts([{"phone": new_phone}])
    assert response.status_code == 200

    # Verify invited user exists in database
    invited: Optional[Dict[str, Any]] = get_user_by_phone(new_phone)
    assert invited is not None
    assert invited["phone"] is None  # Not yet registered, only invited
    assert invited["created_by"] is not None  # Should have a creator

    # Cleanup
    delete_user_by_phone(new_phone)


@pytest.mark.invitation
def test_invitedUserClient_canAccessUserEndpoints_returns200(
    invited_user_client: SanadAPIClient
) -> None:
    """Test that invited user client fixture provides authenticated access"""
    # The invited_user_client fixture creates and registers a user automatically
    response: requests.Response = invited_user_client.user_get_auth_user()
    assert response.status_code == 200

    data: Dict[str, Any] = response.json()["data"]
    assert data["firstName"] == "Invited"
    assert data["lastName"] == "User"

    # Verify client is immutable
    with pytest.raises(AttributeError):
        invited_user_client.token = "new_token"  # type: ignore
