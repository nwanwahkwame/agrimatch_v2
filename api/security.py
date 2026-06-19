"""Shared security dependencies for FastAPI routes."""
import hmac
import os

from fastapi import Header, HTTPException

_INTERNAL_SECRET = os.getenv("INTERNAL_API_SECRET", "")


async def require_internal(x_api_secret: str = Header(default="")) -> None:
    """Reject requests that did not come through the Next.js proxy.

    The proxy injects X-Api-Secret from the INTERNAL_API_SECRET env var.
    If the env var is not set (local dev), all requests are allowed through.
    """
    if not _INTERNAL_SECRET:
        return  # dev mode — no secret configured
    if not hmac.compare_digest(x_api_secret, _INTERNAL_SECRET):
        raise HTTPException(status_code=403, detail="Forbidden")
