"""API Client for Sanad Backend Integration Tests"""
import requests
from typing import Optional, Dict, Any, List


class SanadAPIClient:
    """HTTP client for interacting with Sanad Backend API"""
    
    def __init__(self, base_url: str = "http://localhost:1505"):
        self.base_url = base_url
        self.session = requests.Session()
        self.token: Optional[str] = None
        self.user_id: Optional[str] = None
    
    def set_token(self, token: str, user_id: Optional[str] = None):
        """Set Bearer token for authenticated requests"""
        # Ensure token has Bearer prefix
        if token and not token.startswith("Bearer "):
            token = f"Bearer {token}"
        self.token = token
        self.user_id = user_id
        self.session.headers.update({"Authorization": token})
    
    def clear_token(self):
        """Clear authentication token"""
        self.token = None
        self.user_id = None
        self.session.headers.pop("Authorization", None)
    
    def health_check(self) -> requests.Response:
        """Check if backend is healthy"""
        return self.session.get(f"{self.base_url}/health")
    
    def admin_send_otp(self, phone: str) -> requests.Response:
        """Send OTP to admin phone"""
        return self.session.post(
            f"{self.base_url}/api/v1/admin/send-otp",
            json={"phone": phone}
        )
    
    def admin_login(self, phone: str, verification_code: str) -> requests.Response:
        """Login as admin with OTP"""
        response = self.session.post(
            f"{self.base_url}/api/v1/admin/login",
            json={"phone": phone, "verificationCode": verification_code}
        )
        if response.status_code == 200:
            response_data = response.json()
            # Handle nested response: {data: {accessToken, userId}}
            data = response_data.get("data", response_data)
            self.set_token(data.get("accessToken"), data.get("userId"))
        return response
    
    def admin_get_auth_user(self) -> requests.Response:
        """Get authenticated admin user details"""
        return self.session.get(f"{self.base_url}/api/v1/admin/get-auth-user")
    
    def user_send_otp(self, phone: str, request_type: str, country_code: str = "+1") -> requests.Response:
        """Send OTP for user registration or login"""
        return self.session.post(
            f"{self.base_url}/api/v1/user/send-otp",
            json={"phone": phone, "requestType": request_type, "countryCode": country_code}
        )
    
    def user_register(self, phone: str, first_name: str, email: str, verification_code: str,
                     last_name: str = "", country_code: str = "+1", fcm_token: Optional[str] = None) -> requests.Response:
        """Register new user with OTP"""
        payload = {"phone": phone, "firstName": first_name, "lastName": last_name,
                  "email": email, "verificationCode": verification_code, "countryCode": country_code}
        if fcm_token:
            payload["fcmToken"] = fcm_token
        response = self.session.post(f"{self.base_url}/api/v1/user/register", json=payload)
        if response.status_code == 200:
            response_data = response.json()
            # Handle nested response: {data: {accessToken, userId}}
            data = response_data.get("data", response_data)
            self.set_token(data.get("accessToken"), data.get("userId"))
        return response
    
    def user_login(self, phone: str, verification_code: str, country_code: str = "+1") -> requests.Response:
        """Login user with OTP"""
        response = self.session.post(
            f"{self.base_url}/api/v1/user/login",
            json={"phone": phone, "verificationCode": verification_code, "countryCode": country_code}
        )
        if response.status_code == 200:
            response_data = response.json()
            # Handle nested response: {data: {accessToken, userId}}
            data = response_data.get("data", response_data)
            self.set_token(data.get("accessToken"), data.get("userId"))
        return response
    
    def user_get_auth_user(self) -> requests.Response:
        """Get authenticated user details"""
        return self.session.get(f"{self.base_url}/api/v1/user/get-auth-user")
    
    def invite_contacts(self, contacts: List[Dict[str, str]]) -> requests.Response:
        """Invite contacts to register"""
        return self.session.post(f"{self.base_url}/api/v1/user/invite", json={"contacts": contacts})
    
    def get_all_otp(self) -> requests.Response:
        """Get all active OTPs (debug endpoint)"""
        return self.session.get(f"{self.base_url}/api/v1/user/get-all-otp")
