import os
import time
import base64

import httpx

TOKEN_URL = "https://api.canva.com/rest/v1/oauth/token"

_cached_token: str | None = None
_token_expiry: float = 0


async def get_access_token() -> str:
    """Return a valid Canva access token, refreshing if needed."""
    global _cached_token, _token_expiry

    if _cached_token and time.time() < _token_expiry:
        return _cached_token

    client_id = os.environ.get("CANVA_CLIENT_ID")
    client_secret = os.environ.get("CANVA_CLIENT_SECRET")
    refresh_token = os.environ.get("CANVA_REFRESH_TOKEN")

    if not all([client_id, client_secret, refresh_token]):
        raise RuntimeError(
            "CANVA_CLIENT_ID, CANVA_CLIENT_SECRET, and CANVA_REFRESH_TOKEN "
            "environment variables are required"
        )

    basic = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            TOKEN_URL,
            headers={
                "Authorization": f"Basic {basic}",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            data={
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
            },
        )
        resp.raise_for_status()
        data = resp.json()

    _cached_token = data["access_token"]
    _token_expiry = time.time() + data.get("expires_in", 14400) - 60

    # Update refresh token if rotated
    new_refresh = data.get("refresh_token")
    if new_refresh:
        os.environ["CANVA_REFRESH_TOKEN"] = new_refresh

    return _cached_token


async def canva_client() -> httpx.AsyncClient:
    """Return an httpx client with Canva auth headers."""
    token = await get_access_token()
    return httpx.AsyncClient(
        base_url="https://api.canva.com/rest/v1",
        headers={"Authorization": f"Bearer {token}"},
        timeout=30.0,
    )
