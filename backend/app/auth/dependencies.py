import structlog
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from app.database.supabase import get_supabase_client

logger = structlog.get_logger(__name__)

security_bearer = HTTPBearer(auto_error=False)


class UserContext(BaseModel):
    """Authenticated user context derived from verified Supabase JWT."""

    id: str
    email: str
    access_token: str


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security_bearer),
) -> UserContext:
    """FastAPI dependency that extracts and verifies Supabase JWT access token.

    Returns UserContext if valid.
    Raises 401 Unauthorized if token is missing, invalid, or expired.
    """
    if not credentials or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authorization token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials.strip()
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization token format",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        supabase = get_supabase_client()
        response = supabase.auth.get_user(jwt=token)
        user = response.user if response else None

        if not user or not user.id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired access token",
                headers={"WWW-Authenticate": "Bearer"},
            )

        return UserContext(
            id=str(user.id),
            email=user.email or "",
            access_token=token,
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.warning("Supabase auth token verification failed", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired access token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
