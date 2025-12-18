"""Pytest fixtures for Sanad integration tests"""
import pytest
import os
import uuid
from dotenv import load_dotenv
from src.api_client import SanadAPIClient
from src.db_utils import create_test_user, delete_user_by_phone, get_user_by_phone

load_dotenv()

@pytest.fixture(scope="session")
def backend_url():
    """Backend API base URL"""
    return os.getenv("BACKEND_URL", "http://localhost:1505")

@pytest.fixture(scope="session")
def root_user_phone():
    """Root user phone number (the first user who can invite others)"""
    return os.getenv("TEST_ADMIN_PHONE", "+12025551234")

@pytest.fixture(scope="session")
def root_user_email():
    """Root user email"""
    return os.getenv("TEST_ADMIN_EMAIL", "sunil@test.com")

@pytest.fixture(scope="session")
def test_otp():
    """Test OTP code (works in development mode)"""
    return os.getenv("TEST_OTP", "111111")

@pytest.fixture(scope="session", autouse=True)
def setup_root_user(root_user_phone, root_user_email):
    """Setup root user before all tests (first user in system)"""
    # Check if root user already exists
    existing = get_user_by_phone(root_user_phone)
    if not existing:
        print(f"Creating root user: {root_user_phone}")
        create_test_user(
            phone=root_user_phone,
            first_name="Sunil",
            last_name="Test",
            email=root_user_email,
            created_by=None  # NULL = root user
        )
    else:
        print(f"Root user already exists: {root_user_phone}")
    
    yield
    
    # Cleanup after all tests (optional - comment out to keep root user)
    # delete_user_by_phone(root_user_phone)

@pytest.fixture
def api_client(backend_url):
    """Fresh API client for each test"""
    return SanadAPIClient(backend_url)

@pytest.fixture
def root_user_client(api_client, root_user_phone, test_otp):
    """Authenticated root user API client (uses user endpoints, not admin)"""
    # Send OTP
    otp_response = api_client.user_send_otp(root_user_phone, "LOGIN")
    assert otp_response.status_code == 200, f"Failed to send OTP to root user: {otp_response.text}"
    
    # Login as regular user
    login_response = api_client.user_login(root_user_phone, test_otp)
    assert login_response.status_code == 200, f"Failed to login as root user: {login_response.text}"
    
    return api_client

@pytest.fixture
def test_user_phone():
    """Generate unique test user phone number"""
    # Use +1202555 prefix for test numbers (valid DC area code)
    random_suffix = str(uuid.uuid4().int)[:4]
    return f"+1202555{random_suffix}"

@pytest.fixture
def test_user_email():
    """Generate unique test user email"""
    random_id = uuid.uuid4().hex[:8]
    return f"test.{random_id}@example.com"

@pytest.fixture
def invited_user(root_user_client, test_user_phone):
    """Pre-invited user (not yet registered)"""
    response = root_user_client.invite_contacts([{"phone": test_user_phone}])
    assert response.status_code == 200, f"Failed to invite user: {response.text}"
    
    yield {"phone": test_user_phone}
    
    # Cleanup
    delete_user_by_phone(test_user_phone)

@pytest.fixture
def registered_user(api_client, invited_user, test_user_email, test_otp):
    """Fully registered user"""
    phone = invited_user["phone"]
    
    # Send OTP
    otp_response = api_client.user_send_otp(phone, "REGISTER")
    assert otp_response.status_code == 200, f"Failed to send OTP: {otp_response.text}"
    
    # Register
    register_response = api_client.user_register(
        phone=phone,
        first_name="Test",
        last_name="User",
        email=test_user_email,
        verification_code=test_otp
    )
    assert register_response.status_code == 200, f"Failed to register: {register_response.text}"

    response_data = register_response.json()
    # Handle nested response: {data: {accessToken, userId}}
    user_data = response_data.get("data", response_data)

    yield {
        "phone": phone,
        "email": test_user_email,
        "user_id": user_data.get("userId"),
        "access_token": user_data.get("accessToken"),
        "client": api_client
    }
    
    # Cleanup
    delete_user_by_phone(phone)
