from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials
from fastapi.testclient import TestClient

from app.auth.dependencies import UserContext, get_current_user
from app.main import app


@pytest.mark.asyncio
async def test_get_current_user_missing_credentials():
    """Test that missing credentials raises 401 Unauthorized."""
    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(credentials=None)
    assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
    assert "Missing authorization token" in exc_info.value.detail


@pytest.mark.asyncio
async def test_get_current_user_empty_token():
    """Test that an empty bearer token string raises 401 Unauthorized."""
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials="   ")
    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(credentials=credentials)
    assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.asyncio
@patch("app.auth.dependencies.get_supabase_client")
async def test_get_current_user_valid_token(mock_get_supabase):
    """Test that a valid JWT token returns a populated UserContext."""
    mock_user = MagicMock()
    mock_user.id = "12345678-1234-1234-1234-1234567890ab"
    mock_user.email = "analyst@driftwood.com"

    mock_response = MagicMock()
    mock_response.user = mock_user

    mock_client = MagicMock()
    mock_client.auth.get_user.return_value = mock_response
    mock_get_supabase.return_value = mock_client

    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials="valid-token")
    user_context = await get_current_user(credentials=credentials)

    assert isinstance(user_context, UserContext)
    assert user_context.id == "12345678-1234-1234-1234-1234567890ab"
    assert user_context.email == "analyst@driftwood.com"
    assert user_context.access_token == "valid-token"
    mock_client.auth.get_user.assert_called_once_with(jwt="valid-token")


@pytest.mark.asyncio
@patch("app.auth.dependencies.get_supabase_client")
async def test_get_current_user_invalid_token(mock_get_supabase):
    """Test that an invalid token raises 401 Unauthorized."""
    mock_client = MagicMock()
    mock_client.auth.get_user.side_effect = Exception("Invalid token")
    mock_get_supabase.return_value = mock_client

    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials="invalid-token")
    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(credentials=credentials)

    assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
    assert "Invalid or expired access token" in exc_info.value.detail


def test_me_endpoint_unauthorized():
    """Test GET /me endpoint returns 401 when no token is passed."""
    client = TestClient(app)
    response = client.get("/me")
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@patch("app.auth.dependencies.get_supabase_client")
def test_me_endpoint_authorized(mock_get_supabase):
    """Test GET /me endpoint returns user info when a valid token is passed."""
    mock_user = MagicMock()
    mock_user.id = "user-uuid-123"
    mock_user.email = "test@driftwood.com"

    mock_response = MagicMock()
    mock_response.user = mock_user

    mock_client = MagicMock()
    mock_client.auth.get_user.return_value = mock_response
    mock_get_supabase.return_value = mock_client

    client = TestClient(app)
    response = client.get("/me", headers={"Authorization": "Bearer valid-jwt-token"})

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"id": "user-uuid-123", "email": "test@driftwood.com"}
