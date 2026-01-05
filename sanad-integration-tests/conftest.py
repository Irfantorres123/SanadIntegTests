"""Pytest fixtures for Sanad integration tests"""
import pytest
import os
import uuid
from typing import Dict, Any, Generator
from dotenv import load_dotenv
from src.api_client import SanadClientFactory, SanadAPIClient
from src.db_utils import create_test_user, delete_user_by_phone, get_user_by_phone

load_dotenv()

@pytest.fixture(scope="session")
def backend_url() -> str:
    return os.getenv("BACKEND_URL", "http://localhost:1505")

@pytest.fixture(scope="session")
def client_factory(backend_url: str) -> SanadClientFactory:
    return SanadClientFactory(endpoint=backend_url)

@pytest.fixture(scope="session")
def root_user_phone() -> str:
    return os.getenv("TEST_ADMIN_PHONE", "+12025551234")

@pytest.fixture(scope="session")
def root_user_email() -> str:
    return os.getenv("TEST_ADMIN_EMAIL", "sunil@test.com")

@pytest.fixture(scope="session")
def test_otp() -> str:
    return os.getenv("TEST_OTP", "111111")

@pytest.fixture(scope="session")
def admin_phone() -> str:
    return os.getenv("TEST_ADMIN_PHONE", "+12025559999")

@pytest.fixture(scope="session")
def admin_email() -> str:
    return os.getenv("TEST_ADMIN_EMAIL", "admin@test.com")

@pytest.fixture(scope="session", autouse=True)
def setup_root_user(root_user_phone: str, root_user_email: str) -> Generator[None, None, None]:
    """Setup root user before all tests"""
    existing = get_user_by_phone(root_user_phone)
    if not existing:
        print(f"Creating root user: {root_user_phone}")
        create_test_user(
            phone=root_user_phone,
            first_name="Sunil",
            last_name="Test",
            email=root_user_email,
            created_by=None
        )
    else:
        print(f"Root user already exists: {root_user_phone}")
    yield

@pytest.fixture(scope="session", autouse=True)
def setup_admin_user(admin_phone: str, admin_email: str) -> Generator[None, None, None]:
    """Setup admin user before all tests. Admin users login via admin_send_otp/admin_login."""
    from src.db_utils import create_admin_user, get_user_by_phone

    existing = get_user_by_phone(admin_phone)
    if not existing:
        print(f"\n=== Creating admin user in database: {admin_phone} ===")
        create_admin_user(
            phone=admin_phone,
            first_name="Admin",
            last_name="User",
            email=admin_email
        )
        print(f"Admin user created successfully")
    else:
        print(f"Admin user already exists: {admin_phone}")
    yield

@pytest.fixture
def authless_client(client_factory: SanadClientFactory) -> SanadAPIClient:
    """Unauthenticated client for public endpoints"""
    return client_factory.create_unauthenticated_client()

@pytest.fixture
def admin_client(client_factory: SanadClientFactory, admin_phone: str, test_otp: str) -> SanadAPIClient:
    """Authenticated admin client"""
    authless = client_factory.create_unauthenticated_client()

    otp_response = authless.admin_send_otp(admin_phone)
    assert otp_response.status_code == 200, f"Failed to send OTP to admin: {otp_response.text}"

    login_response = authless.admin_login(admin_phone, test_otp)
    assert login_response.status_code == 200, f"Failed to login as admin: {login_response.text}"

    response_data = login_response.json()
    data = response_data.get("data", response_data)
    token = data.get("accessToken")
    user_id = data.get("userId") or data.get("id")

    if not user_id and token:
        import base64
        import json
        payload_b64 = token.split('.')[1]
        payload_b64 += '=' * (4 - len(payload_b64) % 4)
        payload_json = base64.b64decode(payload_b64)
        payload = json.loads(payload_json)
        user_id = payload.get("userId")

    return client_factory.create_authenticated_admin_client(token=token, user_id=user_id)

@pytest.fixture
def user_client(client_factory: SanadClientFactory, root_user_phone: str, test_otp: str) -> SanadAPIClient:
    """Authenticated regular user client"""
    authless = client_factory.create_unauthenticated_client()

    otp_response = authless.user_send_otp(root_user_phone, "LOGIN")
    assert otp_response.status_code == 200, f"Failed to send OTP to user: {otp_response.text}"

    login_response = authless.user_login(root_user_phone, test_otp)
    assert login_response.status_code == 200, f"Failed to login as user: {login_response.text}"

    response_data = login_response.json()
    data = response_data.get("data", response_data)

    return client_factory.create_authenticated_user_client(
        token=data.get("accessToken"),
        user_id=data.get("userId")
    )

@pytest.fixture
def invited_user_client(
    client_factory: SanadClientFactory,
    user_client: SanadAPIClient,
    test_otp: str
) -> Generator[SanadAPIClient, None, None]:
    """Authenticated invited user client. Cleans up after test."""
    phone = f"+1202555{uuid.uuid4().int % 10000:04d}"
    email = f"invited.{uuid.uuid4().hex[:8]}@example.com"

    invite_response = user_client.invite_contacts([{"phone": phone}])
    assert invite_response.status_code == 200, f"Failed to invite user: {invite_response.text}"

    authless = client_factory.create_unauthenticated_client()

    otp_response = authless.user_send_otp(phone, "REGISTER")
    assert otp_response.status_code == 200, f"Failed to send OTP: {otp_response.text}"

    register_response = authless.user_register(
        phone=phone,
        first_name="Invited",
        last_name="User",
        email=email,
        verification_code=test_otp
    )
    assert register_response.status_code == 200, f"Failed to register: {register_response.text}"

    response_data = register_response.json()
    data = response_data.get("data", response_data)

    invited_client = client_factory.create_authenticated_invited_user_client(
        token=data.get("accessToken"),
        user_id=data.get("userId")
    )

    yield invited_client
    delete_user_by_phone(phone)

@pytest.fixture
def api_client(client_factory: SanadClientFactory) -> SanadAPIClient:
    """Legacy: Use authless_client instead"""
    return client_factory.create_unauthenticated_client()

@pytest.fixture
def root_user_client(
    client_factory: SanadClientFactory,
    api_client: SanadAPIClient,
    root_user_phone: str,
    test_otp: str
) -> SanadAPIClient:
    """Legacy: Use user_client instead"""
    otp_response = api_client.user_send_otp(root_user_phone, "LOGIN")
    assert otp_response.status_code == 200, f"Failed to send OTP to root user: {otp_response.text}"

    login_response = api_client.user_login(root_user_phone, test_otp)
    assert login_response.status_code == 200, f"Failed to login as root user: {login_response.text}"

    response_data = login_response.json()
    data = response_data.get("data", response_data)

    return client_factory.create_authenticated_user_client(
        token=data.get("accessToken"),
        user_id=data.get("userId")
    )

@pytest.fixture
def test_user_phone() -> str:
    random_suffix = str(uuid.uuid4().int)[:4]
    return f"+1202555{random_suffix}"

@pytest.fixture
def test_user_email() -> str:
    random_id = uuid.uuid4().hex[:8]
    return f"test.{random_id}@example.com"

@pytest.fixture
def invited_user(
    root_user_client: SanadAPIClient,
    test_user_phone: str
) -> Generator[Dict[str, str], None, None]:
    """Pre-invited user (not yet registered)"""
    response = root_user_client.invite_contacts([{"phone": test_user_phone}])
    assert response.status_code == 200, f"Failed to invite user: {response.text}"

    yield {"phone": test_user_phone}
    delete_user_by_phone(test_user_phone)

@pytest.fixture
def registered_user(
    client_factory: SanadClientFactory,
    api_client: SanadAPIClient,
    invited_user: Dict[str, str],
    test_user_email: str,
    test_otp: str
) -> Generator[Dict[str, Any], None, None]:
    """Fully registered user with authenticated client"""
    phone = invited_user["phone"]

    otp_response = api_client.user_send_otp(phone, "REGISTER")
    assert otp_response.status_code == 200, f"Failed to send OTP: {otp_response.text}"

    register_response = api_client.user_register(
        phone=phone,
        first_name="Test",
        last_name="User",
        email=test_user_email,
        verification_code=test_otp
    )
    assert register_response.status_code == 200, f"Failed to register: {register_response.text}"

    response_data = register_response.json()
    user_data = response_data.get("data", response_data)

    authenticated_client = client_factory.create_authenticated_user_client(
        token=user_data.get("accessToken"),
        user_id=user_data.get("userId")
    )

    yield {
        "phone": phone,
        "email": test_user_email,
        "user_id": user_data.get("userId"),
        "access_token": user_data.get("accessToken"),
        "client": authenticated_client
    }

    delete_user_by_phone(phone)

@pytest.fixture
def second_registered_user(
    client_factory: SanadClientFactory,
    root_user_client: SanadAPIClient,
    test_otp: str
) -> Generator[Dict[str, Any], None, None]:
    """Second registered user for multi-user tests"""
    phone = f"+1202555{uuid.uuid4().int % 10000:04d}"
    email = f"user2.{uuid.uuid4().hex[:8]}@example.com"

    root_user_client.invite_contacts([{"phone": phone}])

    fresh_client = client_factory.create_unauthenticated_client()

    fresh_client.user_send_otp(phone, "REGISTER")
    register_response = fresh_client.user_register(
        phone=phone,
        first_name="Second",
        last_name="User",
        email=email,
        verification_code=test_otp
    )
    assert register_response.status_code == 200

    user_data = register_response.json()["data"]

    authenticated_client = client_factory.create_authenticated_user_client(
        token=user_data["accessToken"],
        user_id=user_data["userId"]
    )

    yield {
        "phone": phone,
        "email": email,
        "user_id": user_data["userId"],
        "access_token": user_data["accessToken"],
        "client": authenticated_client
    }

    delete_user_by_phone(phone)

@pytest.fixture
def third_user(
    client_factory: SanadClientFactory,
    root_user_client: SanadAPIClient,
    test_otp: str
) -> Generator[Dict[str, Any], None, None]:
    """Third registered user for multi-user tests"""
    phone = f"+1202555{uuid.uuid4().int % 10000:04d}"
    email = f"user3.{uuid.uuid4().hex[:8]}@example.com"

    root_user_client.invite_contacts([{"phone": phone}])

    fresh_client = client_factory.create_unauthenticated_client()

    fresh_client.user_send_otp(phone, "REGISTER")
    register_response = fresh_client.user_register(
        phone=phone,
        first_name="Third",
        last_name="User",
        email=email,
        verification_code=test_otp
    )
    assert register_response.status_code == 200

    user_data = register_response.json()["data"]

    authenticated_client = client_factory.create_authenticated_user_client(
        token=user_data["accessToken"],
        user_id=user_data["userId"]
    )

    yield {
        "phone": phone,
        "email": email,
        "user_id": user_data["userId"],
        "access_token": user_data["accessToken"],
        "client": authenticated_client
    }

    delete_user_by_phone(phone)

@pytest.fixture
def test_group(registered_user: Dict[str, Any]) -> Generator[Dict[str, Any], None, None]:
    """Test group for registered user"""
    client = registered_user["client"]

    response = client.group_create("Test Group")
    assert response.status_code == 200

    group_data = response.json()["data"]
    group_id = group_data["groupId"]

    yield {
        "group_id": group_id,
        "name": "Test Group",
        "owner": registered_user
    }

    try:
        client.group_delete(group_id)
    except:
        pass

@pytest.fixture
def test_campaign(registered_user: Dict[str, Any]) -> Generator[Dict[str, Any], None, None]:
    """Test campaign for registered user"""
    client = registered_user["client"]

    response = client.campaign_create(
        title="Test Campaign",
        campaign_type="ZAKAT",
        duration="30",
        amount="1000",
        description="This is a test campaign for integration testing"
    )
    assert response.status_code == 200

    campaigns_response = client.campaign_get_all(filter_type="IN_REVIEW")
    assert campaigns_response.status_code == 200
    campaigns = campaigns_response.json()["data"]["campaigns"]

    campaign = next((c for c in campaigns if c["title"] == "Test Campaign"), None)
    assert campaign is not None, "Created campaign not found"
    campaign_id = campaign["id"]

    yield {
        "campaign_id": campaign_id,
        "title": "Test Campaign",
        "type": "ZAKAT",
        "amount": 1000,
        "creator": registered_user
    }

    try:
        from src.db_utils import delete_campaign_by_id
        delete_campaign_by_id(campaign_id)
    except:
        pass

@pytest.fixture
def approved_campaign(root_user_client: SanadAPIClient) -> Generator[Dict[str, Any], None, None]:
    """Approved campaign created by root user"""
    response = root_user_client.campaign_create(
        title="Approved Campaign",
        campaign_type="SADAQA",
        duration="60",
        amount="5000",
        description="This is an approved campaign created by admin"
    )
    assert response.status_code == 200

    campaigns_response = root_user_client.campaign_get_all(filter_type="ACTIVE")
    assert campaigns_response.status_code == 200
    campaigns = campaigns_response.json()["data"]["campaigns"]

    campaign = next((c for c in campaigns if c["title"] == "Approved Campaign"), None)
    assert campaign is not None, "Created campaign not found"
    campaign_id = campaign["id"]

    yield {
        "campaign_id": campaign_id,
        "title": "Approved Campaign",
        "type": "SADAQA",
        "amount": 5000,
        "creator": "root"
    }

    try:
        from src.db_utils import delete_campaign_by_id
        delete_campaign_by_id(campaign_id)
    except:
        pass
