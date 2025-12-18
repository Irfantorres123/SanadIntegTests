"""Authentication flow tests for Sanad backend"""
import pytest


@pytest.mark.auth
def test_backend_health(api_client):
    """Test backend health endpoint"""
    response = api_client.health_check()
    assert response.status_code == 200
    data = response.json()
    assert "message" in data



@pytest.mark.auth
def test_user_send_otp_uninvited(api_client, test_user_phone):
    """Test that uninvited user cannot send OTP for registration"""
    response = api_client.user_send_otp(test_user_phone, "REGISTER")
    # Should fail because user is not invited
    assert response.status_code in [400, 404]


@pytest.mark.auth
def test_user_authentication_requires_token(api_client):
    """Test that protected endpoints require authentication"""
    # Try to access protected endpoint without token
    response = api_client.user_get_auth_user()
    assert response.status_code in [401, 403]
