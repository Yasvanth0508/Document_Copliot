from functools import lru_cache
from typing import Any

from supabase import Client, create_client
from supabase.lib.client_options import ClientOptions

from app.config import settings


@lru_cache(maxsize=1)
def get_supabase_admin_client() -> Client:
    """Returns a Supabase client configured with the service_role key.

    PRIVILEGED: This client bypasses RLS and should ONLY be used on the backend
    for administrative or background tasks where user context is explicitly managed.
    """
    return create_client(
        supabase_url=settings.SUPABASE_URL,
        supabase_key=settings.SUPABASE_SERVICE_ROLE_KEY,
    )


def get_supabase_client() -> Client:
    """Returns a standard Supabase client configured with the anon key."""
    return create_client(
        supabase_url=settings.SUPABASE_URL,
        supabase_key=settings.SUPABASE_ANON_KEY,
    )


def get_user_supabase_client(access_token: str) -> Client:
    """Returns a user-scoped Supabase client initialized with the user's JWT access token.

    DB calls made with this client inherit the authenticated user's RLS policies.
    """
    options = ClientOptions(
        headers={"Authorization": f"Bearer {access_token}"}
    )
    return create_client(
        supabase_url=settings.SUPABASE_URL,
        supabase_key=settings.SUPABASE_ANON_KEY,
        options=options,
    )
