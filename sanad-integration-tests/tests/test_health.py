"""Health check and public endpoint tests"""
import pytest
import requests
from typing import Dict, Any
from src.api_client import SanadAPIClient


@pytest.mark.health
def test_healthEndpoint_withNoAuth_returns200(authless_client: SanadAPIClient) -> None:
    """Test backend health endpoint is publicly accessible"""
    response: requests.Response = authless_client.health_check()
    assert response.status_code == 200, (
        f"Health check failed. "
        f"Expected 200, got {response.status_code}: {response.text}"
    )

    data: Dict[str, Any] = response.json()
    assert "message" in data, "Health check response missing 'message' field"
