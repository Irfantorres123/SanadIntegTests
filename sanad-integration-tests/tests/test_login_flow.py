"""User login flow tests"""
import pytest
import requests
from typing import Dict, Any
from src.api_client import SanadAPIClient, SanadClientFactory


@pytest.mark.login
def test_sendOtp_forRegisteredUser_returns200(
    authless_client: SanadAPIClient,
    registered_user: Dict[str, Any]
) -> None:
    """Test that registered user can request OTP for login"""
    phone: str = registered_user["phone"]

    response: requests.Response = authless_client.user_send_otp(phone, "LOGIN")
    assert response.status_code == 200


@pytest.mark.login
def test_userLogin_withValidOtp_returns200AndToken(
    client_factory: SanadClientFactory,
    authless_client: SanadAPIClient,
    registered_user: Dict[str, Any],
    test_otp: str
) -> None:
    """Test that registered user can login with OTP and receive token"""
    phone: str = registered_user["phone"]
    expected_user_id: str = registered_user["user_id"]

    # Send OTP
    otp_response: requests.Response = authless_client.user_send_otp(phone, "LOGIN")
    assert otp_response.status_code == 200

    # Login
    login_response: requests.Response = authless_client.user_login(phone, test_otp)
    assert login_response.status_code == 200

    # Verify nested response structure
    response_data: Dict[str, Any] = login_response.json()
    assert "data" in response_data

    data: Dict[str, Any] = response_data["data"]
    assert "accessToken" in data
    assert "userId" in data
    assert data["userId"] == expected_user_id
    assert len(data["accessToken"]) > 0

    # Verify can create authenticated client with returned token
    authenticated_client: SanadAPIClient = client_factory.create_authenticated_user_client(
        token=data["accessToken"],
        user_id=data["userId"]
    )
    profile_response: requests.Response = authenticated_client.user_get_auth_user()
    assert profile_response.status_code == 200


@pytest.mark.login
def test_userLogin_withInvalidOtp_returns400or401(
    authless_client: SanadAPIClient,
    registered_user: Dict[str, Any]
) -> None:
    """Test that login fails with invalid OTP"""
    phone: str = registered_user["phone"]

    # Send valid OTP first
    authless_client.user_send_otp(phone, "LOGIN")

    # Try to login with wrong OTP
    response: requests.Response = authless_client.user_login(phone, "999999")
    assert response.status_code in [400, 401]


@pytest.mark.login
def test_userLogin_forUnregisteredUser_returns400or404(
    authless_client: SanadAPIClient,
    invited_user: Dict[str, str],
    test_otp: str
) -> None:
    """Test that invited but unregistered user cannot login"""
    phone: str = invited_user["phone"]

    # Try to login (should fail because user is not registered)
    response: requests.Response = authless_client.user_login(phone, test_otp)
    assert response.status_code in [400, 404]


@pytest.mark.login
def test_getAuthUser_withAuthenticatedClient_returns200AndProfile(
    client_factory: SanadClientFactory,
    authless_client: SanadAPIClient,
    registered_user: Dict[str, Any],
    test_otp: str
) -> None:
    """Test that logged-in user can access their profile"""
    phone: str = registered_user["phone"]
    email: str = registered_user["email"]

    # Login to get token
    authless_client.user_send_otp(phone, "LOGIN")
    login_response: requests.Response = authless_client.user_login(phone, test_otp)
    data: Dict[str, Any] = login_response.json()["data"]

    # Create authenticated client
    authenticated_client: SanadAPIClient = client_factory.create_authenticated_user_client(
        token=data["accessToken"],
        user_id=data["userId"]
    )

    # Get user profile
    response: requests.Response = authenticated_client.user_get_auth_user()
    assert response.status_code == 200

    response_data: Dict[str, Any] = response.json()
    assert "data" in response_data

    profile_data: Dict[str, Any] = response_data["data"]
    assert profile_data["phone"] == phone
    assert profile_data["email"] == email
    assert profile_data["firstName"] == "Test"
    assert profile_data["lastName"] == "User"


@pytest.mark.login
def test_jwtToken_persistsAcrossMultipleRequests_returns200(
    registered_user: Dict[str, Any]
) -> None:
    """Test that JWT token works for multiple authenticated requests"""
    client: SanadAPIClient = registered_user["client"]
    expected_phone: str = registered_user["phone"]

    # Make multiple authenticated requests
    for _ in range(3):
        response: requests.Response = client.user_get_auth_user()
        assert response.status_code == 200

        response_data: Dict[str, Any] = response.json()
        assert "data" in response_data

        data: Dict[str, Any] = response_data["data"]
        assert data["phone"] == expected_phone


@pytest.mark.login
def test_loginFlow_createsImmutableClient_cannotModifyToken(
    client_factory: SanadClientFactory,
    authless_client: SanadAPIClient,
    root_user_phone: str,
    test_otp: str
) -> None:
    """
    Test that login flow creates immutable authenticated client.

    Demonstrates the immutable pattern:
    1. Use authless client to login
    2. Extract token from response
    3. Create NEW authenticated client with factory
    4. Original authless client remains unauthenticated
    """
    # Step 1: Send OTP using authless client
    otp_response: requests.Response = authless_client.user_send_otp(root_user_phone, "LOGIN")
    assert otp_response.status_code == 200

    # Step 2: Login using authless client
    login_response: requests.Response = authless_client.user_login(root_user_phone, test_otp)
    assert login_response.status_code == 200

    # Step 3: Extract token and user_id
    data: Dict[str, Any] = login_response.json()["data"]
    token: str = data["accessToken"]
    user_id: str = data["userId"]

    # Step 4: Create NEW authenticated client (immutable pattern)
    authenticated_client: SanadAPIClient = client_factory.create_authenticated_user_client(
        token=token,
        user_id=user_id
    )

    # Step 5: Verify the new client can access protected endpoints
    auth_response: requests.Response = authenticated_client.user_get_auth_user()
    assert auth_response.status_code == 200

    # Step 6: Original authless client is still unauthenticated
    authless_response: requests.Response = authless_client.user_get_auth_user()
    assert authless_response.status_code in [401, 403]

    # Step 7: Authenticated client is immutable
    with pytest.raises(AttributeError):
        authenticated_client.token = "new_token"  # type: ignore
