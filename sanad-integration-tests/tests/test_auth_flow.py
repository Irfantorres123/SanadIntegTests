"""Authentication flow tests for Sanad backend"""
import pytest
import requests
from typing import Dict, Any
from src.api_client import SanadAPIClient


@pytest.mark.auth
def test_sendOtp_forUninvitedUser_returns400or404(
    authless_client: SanadAPIClient,
    test_user_phone: str
) -> None:
    """Test that uninvited user cannot send OTP for registration"""
    response: requests.Response = authless_client.user_send_otp(test_user_phone, "REGISTER")

    # Should fail because user is not invited
    assert response.status_code in [400, 404]


# ========================================
# PARAMETRIZED PROTECTED ENDPOINT TESTS
# ========================================

@pytest.mark.auth
@pytest.mark.parametrize("endpoint_method,endpoint_kwargs", [
    # User endpoints
    ("user_get_auth_user", {}),
    ("invite_contacts", {"contacts": []}),
    ("group_create", {"name": "Test"}),
    ("group_get_all", {}),
    ("group_delete", {"group_id": "dummy-id"}),
    ("group_get_users_to_add", {}),
    ("campaign_get_all", {}),
    ("campaign_get_one", {"campaign_id": "dummy-id"}),
    ("campaign_delete", {"campaign_id": "dummy-id"}),
    ("campaign_share", {"campaign_id": "dummy-id"}),
])
def test_protectedUserEndpoints_withoutAuthentication_returns401or403(
    authless_client: SanadAPIClient,
    endpoint_method: str,
    endpoint_kwargs: Dict[str, Any]
) -> None:
    """
    Test that all protected user endpoints require authentication.

    This parametrized test ensures that any endpoint requiring authentication
    properly rejects unauthenticated requests with 401 or 403 status codes.
    """
    method = getattr(authless_client, endpoint_method)
    response: requests.Response = method(**endpoint_kwargs)

    assert response.status_code in [401, 403], (
        f"Endpoint {endpoint_method} should require authentication "
        f"but returned {response.status_code}"
    )


@pytest.mark.auth
@pytest.mark.parametrize("endpoint_method,endpoint_kwargs", [
    ("admin_get_auth_user", {}),
])
def test_protectedAdminEndpoints_withoutAuthentication_returns401or403(
    authless_client: SanadAPIClient,
    endpoint_method: str,
    endpoint_kwargs: Dict[str, Any]
) -> None:
    """
    Test that all protected admin endpoints require authentication.

    This parametrized test ensures that admin-only endpoints properly reject
    unauthenticated requests with 401 or 403 status codes.
    """
    method = getattr(authless_client, endpoint_method)
    response: requests.Response = method(**endpoint_kwargs)

    assert response.status_code in [401, 403], (
        f"Admin endpoint {endpoint_method} should require authentication "
        f"but returned {response.status_code}"
    )


# ========================================
# ADMIN AUTHENTICATION TESTS
# ========================================

@pytest.mark.auth
def test_adminClient_canAccessAdminEndpoints_returns200(
    admin_client: SanadAPIClient
) -> None:
    """Test that authenticated admin client can access admin endpoints"""
    response: requests.Response = admin_client.admin_get_auth_user()
    assert response.status_code == 200

    data: Dict[str, Any] = response.json()
    assert "data" in data

    # Verify admin client attributes
    assert admin_client.token is not None
    assert admin_client.user_id is not None
    assert admin_client.is_admin is True


# ========================================
# USER AUTHENTICATION TESTS
# ========================================

@pytest.mark.auth
def test_userClient_canAccessUserEndpoints_returns200(
    user_client: SanadAPIClient
) -> None:
    """Test that authenticated user client can access user endpoints"""
    response: requests.Response = user_client.user_get_auth_user()
    assert response.status_code == 200

    data: Dict[str, Any] = response.json()
    assert "data" in data

    # Verify user client attributes
    assert user_client.token is not None
    assert user_client.user_id is not None
    assert user_client.is_admin is False


@pytest.mark.auth
def test_invitedUserClient_canAccessUserEndpoints_returns200(
    invited_user_client: SanadAPIClient
) -> None:
    """Test that authenticated invited user client can access user endpoints"""
    response: requests.Response = invited_user_client.user_get_auth_user()
    assert response.status_code == 200

    data: Dict[str, Any] = response.json()
    assert "data" in data

    # Verify invited user client attributes
    assert invited_user_client.token is not None
    assert invited_user_client.user_id is not None
    assert invited_user_client.is_admin is False


# ========================================
# CLIENT IMMUTABILITY TESTS
# ========================================

@pytest.mark.auth
def test_clientImmutability_attemptToModifyToken_raisesAttributeError(
    user_client: SanadAPIClient
) -> None:
    """Test that clients are immutable and cannot have token modified"""
    with pytest.raises(AttributeError, match="Cannot modify attribute 'token'"):
        user_client.token = "new_token"  # type: ignore


@pytest.mark.auth
def test_clientImmutability_attemptToModifyUserId_raisesAttributeError(
    user_client: SanadAPIClient
) -> None:
    """Test that clients are immutable and cannot have user_id modified"""
    with pytest.raises(AttributeError, match="Cannot modify attribute 'user_id'"):
        user_client.user_id = "new_user_id"  # type: ignore


@pytest.mark.auth
def test_clientImmutability_attemptToModifyEndpoint_raisesAttributeError(
    user_client: SanadAPIClient
) -> None:
    """Test that clients are immutable and cannot have endpoint modified"""
    with pytest.raises(AttributeError, match="Cannot modify attribute 'endpoint'"):
        user_client.endpoint = "http://different.com"  # type: ignore
