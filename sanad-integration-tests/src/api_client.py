"""API Client for Sanad Backend Integration Tests"""
import json
import requests
from typing import Optional, Dict, Any, List


class SanadClientFactory:
    """Factory for creating SanadAPIClient instances with different authentication states"""

    def __init__(self, endpoint: str = "http://localhost:1505"):
        self.endpoint = endpoint

    def create_authenticated_admin_client(self, token: str, user_id: str) -> "SanadAPIClient":
        return SanadAPIClient(endpoint=self.endpoint, token=token, user_id=user_id, is_admin=True)

    def create_authenticated_user_client(self, token: str, user_id: str) -> "SanadAPIClient":
        return SanadAPIClient(endpoint=self.endpoint, token=token, user_id=user_id, is_admin=False)

    def create_authenticated_invited_user_client(self, token: str, user_id: str) -> "SanadAPIClient":
        return SanadAPIClient(endpoint=self.endpoint, token=token, user_id=user_id, is_admin=False)

    def create_unauthenticated_client(self) -> "SanadAPIClient":
        return SanadAPIClient(endpoint=self.endpoint)


class SanadAPIClient:
    """
    Immutable HTTP client for Sanad Backend API.
    Each client instance represents ONE user for its entire lifetime.
    """

    def __init__(
        self,
        endpoint: str,
        token: Optional[str] = None,
        user_id: Optional[str] = None,
        is_admin: bool = False
    ):
        object.__setattr__(self, "endpoint", endpoint)
        object.__setattr__(self, "user_id", user_id)
        object.__setattr__(self, "is_admin", is_admin)

        session = requests.Session()
        if token:
            if not token.startswith("Bearer "):
                token = f"Bearer {token}"
            session.headers.update({"Authorization": token})
            object.__setattr__(self, "token", token)
        else:
            object.__setattr__(self, "token", None)

        object.__setattr__(self, "session", session)

    def __setattr__(self, name: str, value: Any) -> None:
        _ = value
        raise AttributeError(
            f"Cannot modify attribute '{name}'. SanadAPIClient is immutable. "
            f"Create a new client instance using SanadClientFactory instead."
        )

    def health_check(self) -> requests.Response:
        return self.session.get(self._build_url("/health"))

    def admin_send_otp(self, phone: str) -> requests.Response:
        return self.session.post(
            self._build_url("/api/v1/admin/send-otp"),
            json={"phone": phone}
        )

    def admin_login(self, phone: str, verification_code: str) -> requests.Response:
        """Returns response with accessToken and userId. Does NOT modify this client."""
        return self.session.post(
            self._build_url("/api/v1/admin/login"),
            json={"phone": phone, "verificationCode": verification_code}
        )

    def admin_get_auth_user(self) -> requests.Response:
        return self.session.get(self._build_url("/api/v1/admin/get-auth-user"))

    def user_send_otp(
        self,
        phone: str,
        request_type: str,
        country_code: str = "+1"
    ) -> requests.Response:
        return self.session.post(
            self._build_url("/api/v1/user/send-otp"),
            json={
                "phone": phone,
                "requestType": request_type,
                "countryCode": country_code
            }
        )

    def user_register(
        self,
        phone: str,
        first_name: str,
        email: str,
        verification_code: str,
        last_name: str = "",
        country_code: str = "+1",
        fcm_token: Optional[str] = None
    ) -> requests.Response:
        """Returns response with accessToken and userId. Does NOT modify this client."""
        payload = {
            "phone": phone,
            "firstName": first_name,
            "lastName": last_name,
            "email": email,
            "verificationCode": verification_code,
            "countryCode": country_code
        }
        if fcm_token:
            payload["fcmToken"] = fcm_token

        return self.session.post(
            self._build_url("/api/v1/user/register"),
            json=payload
        )

    def user_login(
        self,
        phone: str,
        verification_code: str,
        country_code: str = "+1"
    ) -> requests.Response:
        """Returns response with accessToken and userId. Does NOT modify this client."""
        return self.session.post(
            self._build_url("/api/v1/user/login"),
            json={
                "phone": phone,
                "verificationCode": verification_code,
                "countryCode": country_code
            }
        )

    def user_get_auth_user(self) -> requests.Response:
        return self.session.get(self._build_url("/api/v1/user/get-auth-user"))

    def invite_contacts(self, contacts: List[Dict[str, str]]) -> requests.Response:
        return self.session.post(
            self._build_url("/api/v1/user/invite"),
            json={"contacts": contacts}
        )

    def get_all_otp(self) -> requests.Response:
        """Debug endpoint - returns all active OTP codes"""
        return self.session.get(self._build_url("/api/v1/user/get-all-otp"))

    def group_create(self, name: str) -> requests.Response:
        return self.session.post(
            self._build_url("/api/v1/group/create"),
            json={"name": name}
        )

    def group_add_users(
        self,
        group_id: str,
        user_ids: Optional[List[str]] = None,
        new_users: Optional[List[Dict[str, str]]] = None,
        group_name: Optional[str] = None
    ) -> requests.Response:
        """SYNC operation - unlisted users will be removed from group"""
        payload = {"groupId": group_id}
        if user_ids is not None:
            payload["userIds"] = user_ids
        if new_users is not None:
            payload["newUsers"] = new_users
        if group_name is not None:
            payload["groupName"] = group_name

        return self.session.post(
            self._build_url("/api/v1/group/add-users"),
            json=payload
        )

    def group_get_all(
        self,
        page_size: Optional[int] = None,
        page: Optional[int] = None
    ) -> requests.Response:
        payload = {}
        if page_size is not None:
            payload["pageSize"] = page_size
        if page is not None:
            payload["page"] = page

        return self.session.post(
            self._build_url("/api/v1/group/get-all"),
            json=payload
        )

    def group_get_users_to_add(
        self,
        group_id: Optional[str] = None,
        contact_list: Optional[List[Dict[str, str]]] = None
    ) -> requests.Response:
        payload = {}
        if group_id is not None:
            payload["groupId"] = group_id
        if contact_list is not None:
            payload["contactList"] = contact_list

        return self.session.post(
            self._build_url("/api/v1/group/get-users-to-add"),
            json=payload
        )

    def group_delete(self, group_id: str) -> requests.Response:
        return self.session.delete(
            self._build_url(f"/api/v1/group/delete/{group_id}")
        )

    def campaign_create(
        self,
        title: str,
        campaign_type: str,
        duration: str,
        amount: str,
        description: str,
        payment_details: Optional[str] = None,
        familiar_duration: Optional[str] = None,
        save_payment_details: bool = False,
        group_ids: Optional[List[str]] = None,
        user_ids: Optional[List[str]] = None,
        new_users: Optional[List[Dict[str, str]]] = None,
        image_file: Optional[str] = None
    ) -> requests.Response:
        """Uses multipart/form-data, not JSON"""
        data = {
            "title": title,
            "type": campaign_type,
            "duration": duration,
            "amount": amount,
            "description": description,
            "savePaymentDetails": "true" if save_payment_details else "false",
        }

        if payment_details is not None:
            data["paymentDetails"] = payment_details
        if familiar_duration is not None:
            data["familiarDuration"] = familiar_duration

        if group_ids:
            data["groupIds"] = json.dumps(group_ids)
        if user_ids:
            data["userIds"] = json.dumps(user_ids)
        if new_users:
            data["newUsers"] = json.dumps(new_users)

        files = None
        if image_file:
            files = {"image": open(image_file, "rb")}

        return self.session.post(
            self._build_url("/api/v1/campaign/create"),
            data=data,
            files=files
        )

    def campaign_get_all(
        self,
        filter_type: Optional[str] = None,
        campaign_type: Optional[str] = None,
        search_text: Optional[str] = None,
        page_size: int = 10,
        page: int = 1
    ) -> requests.Response:
        payload = {
            "pageSize": page_size,
            "page": page
        }
        if filter_type is not None:
            payload["filter"] = filter_type
        if campaign_type is not None:
            payload["campaignType"] = campaign_type
        if search_text is not None:
            payload["searchText"] = search_text

        return self.session.post(
            self._build_url("/api/v1/campaign/get-all"),
            json=payload
        )

    def campaign_get_one(self, campaign_id: str) -> requests.Response:
        return self.session.get(
            self._build_url(f"/api/v1/campaign/get-one/{campaign_id}")
        )

    def campaign_delete(self, campaign_id: str) -> requests.Response:
        return self.session.delete(
            self._build_url(f"/api/v1/campaign/delete/{campaign_id}")
        )

    def campaign_share(
        self,
        campaign_id: str,
        group_ids: Optional[List[str]] = None,
        user_ids: Optional[List[str]] = None,
        new_users: Optional[List[Dict[str, str]]] = None,
        message: Optional[str] = None
    ) -> requests.Response:
        payload = {
            "campaignId": campaign_id,
            "groupIds": group_ids or [],
            "userIds": user_ids or [],
            "newUsers": new_users or []
        }

        if message:
            payload["message"] = message

        return self.session.post(
            self._build_url("/api/v1/campaign/share"),
            json=payload
        )

    def _build_url(self, path: str) -> str:
        return f"{self.endpoint}{path}"
