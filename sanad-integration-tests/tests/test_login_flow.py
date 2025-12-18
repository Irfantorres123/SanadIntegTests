"""User login flow tests"""
import pytest


@pytest.mark.login
def test_registered_user_can_send_login_otp(api_client, registered_user):
    """Test that registered user can request OTP for login"""
    phone = registered_user["phone"]
    
    # Create fresh client (not authenticated)
    fresh_client = api_client.__class__(api_client.base_url)
    
    response = fresh_client.user_send_otp(phone, "LOGIN")
    assert response.status_code == 200


@pytest.mark.login
def test_registered_user_can_login(api_client, registered_user, test_otp):
    """Test that registered user can login with OTP"""
    phone = registered_user["phone"]
    
    # Create fresh client
    fresh_client = api_client.__class__(api_client.base_url)
    
    # Send OTP
    otp_response = fresh_client.user_send_otp(phone, "LOGIN")
    assert otp_response.status_code == 200
    
    # Login
    login_response = fresh_client.user_login(phone, test_otp)
    assert login_response.status_code == 200

    # Verify nested response structure
    response_data = login_response.json()
    assert "data" in response_data
    data = response_data["data"]
    assert "accessToken" in data
    assert "userId" in data
    assert data["userId"] == registered_user["user_id"]
    # Note: Backend returns token WITHOUT "Bearer " prefix
    assert len(data["accessToken"]) > 0


@pytest.mark.login
def test_login_with_invalid_otp_fails(api_client, registered_user):
    """Test that login fails with invalid OTP"""
    phone = registered_user["phone"]
    fresh_client = api_client.__class__(api_client.base_url)
    
    # Send OTP
    fresh_client.user_send_otp(phone, "LOGIN")
    
    # Try to login with wrong OTP
    response = fresh_client.user_login(phone, "999999")
    assert response.status_code in [400, 401]


@pytest.mark.login
def test_unregistered_user_cannot_login(api_client, invited_user, test_otp):
    """Test that invited but unregistered user cannot login"""
    phone = invited_user["phone"]
    
    # Try to login (should fail because user is not registered)
    response = api_client.user_login(phone, test_otp)
    assert response.status_code in [400, 404]


@pytest.mark.login
def test_logged_in_user_can_get_profile(api_client, registered_user, test_otp):
    """Test that logged-in user can access their profile"""
    phone = registered_user["phone"]
    email = registered_user["email"]
    
    # Create fresh client and login
    fresh_client = api_client.__class__(api_client.base_url)
    fresh_client.user_send_otp(phone, "LOGIN")
    fresh_client.user_login(phone, test_otp)
    
    # Get user profile
    response = fresh_client.user_get_auth_user()
    assert response.status_code == 200

    response_data = response.json()
    assert "data" in response_data
    data = response_data["data"]
    assert data["phone"] == phone
    assert data["email"] == email
    # Backend returns camelCase fields, not snake_case
    assert data["firstName"] == "Test"
    assert data["lastName"] == "User"


@pytest.mark.login
def test_jwt_persists_across_requests(registered_user):
    """Test that JWT token works for multiple authenticated requests"""
    client = registered_user["client"]

    # Make multiple authenticated requests
    for _ in range(3):
        response = client.user_get_auth_user()
        assert response.status_code == 200
        response_data = response.json()
        assert "data" in response_data
        data = response_data["data"]
        assert data["phone"] == registered_user["phone"]
