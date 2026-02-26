"""
Google Calendar OAuth client — Authorization Code Flow.

Stores the refresh_token in MongoDB (collection: integrations, doc _id='google_oauth').
Falls back to GOOGLE_REFRESH_TOKEN env var if MongoDB not available.

Usage:
    from app.services.google_calendar_client import build_calendar_service, get_connection_status

    service = await build_calendar_service()
    # then: service.events().insert(...)
"""

import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# ── Env / constants ───────────────────────────────────────────────────────────
GOOGLE_OAUTH_CLIENT_ID     = os.environ.get("GOOGLE_OAUTH_CLIENT_ID", "")
GOOGLE_OAUTH_CLIENT_SECRET = os.environ.get("GOOGLE_OAUTH_CLIENT_SECRET", "")
GOOGLE_OAUTH_REDIRECT_URI  = os.environ.get(
    "GOOGLE_OAUTH_REDIRECT_URI",
    "https://igv-cms-backend.onrender.com/api/google/oauth/callback"
)
GOOGLE_CALENDAR_ID = os.environ.get("GOOGLE_CALENDAR_ID", "primary")

SCOPES = [
    "https://www.googleapis.com/auth/calendar",
]

# MongoDB collection + doc id where the refresh token is stored
_MONGO_COLLECTION = "integrations"
_MONGO_DOC_ID     = "google_oauth"


# ── MongoDB helpers ───────────────────────────────────────────────────────────

def _get_db():
    """Return the Motor db instance from server globals, or None."""
    try:
        import importlib
        server_mod = importlib.import_module("server")
        return getattr(server_mod, "db", None)
    except Exception:
        return None


async def load_refresh_token() -> Optional[str]:
    """
    Load the stored Google refresh_token.
    Priority: MongoDB → GOOGLE_REFRESH_TOKEN env var.
    """
    db = _get_db()
    if db is not None:
        try:
            doc = await db[_MONGO_COLLECTION].find_one({"_id": _MONGO_DOC_ID})
            if doc and doc.get("refresh_token"):
                return doc["refresh_token"]
        except Exception as e:
            logger.warning(f"[gcal] MongoDB read failed, falling back to env: {e}")
    # Fallback: env var
    return os.environ.get("GOOGLE_REFRESH_TOKEN") or None


async def save_refresh_token(refresh_token: str) -> None:
    """
    Persist refresh_token to MongoDB (upsert) AND into the current process env
    so it survives for the lifetime of the process even if Mongo is slow.
    """
    os.environ["GOOGLE_REFRESH_TOKEN"] = refresh_token  # in-process cache
    db = _get_db()
    if db is not None:
        try:
            await db[_MONGO_COLLECTION].update_one(
                {"_id": _MONGO_DOC_ID},
                {"$set": {"refresh_token": refresh_token}},
                upsert=True,
            )
            logger.info("[gcal] refresh_token saved to MongoDB.")
        except Exception as e:
            logger.error(f"[gcal] Failed to save refresh_token to MongoDB: {e}")
    else:
        logger.warning("[gcal] No MongoDB — refresh_token only in process env (not persistent).")


async def delete_refresh_token() -> None:
    """Remove the stored refresh_token from MongoDB and env."""
    os.environ.pop("GOOGLE_REFRESH_TOKEN", None)
    db = _get_db()
    if db is not None:
        try:
            await db[_MONGO_COLLECTION].delete_one({"_id": _MONGO_DOC_ID})
            logger.info("[gcal] refresh_token deleted from MongoDB.")
        except Exception as e:
            logger.error(f"[gcal] Failed to delete refresh_token: {e}")


# ── Credentials / service ─────────────────────────────────────────────────────

def get_credentials_from_refresh_token(refresh_token: str):
    """
    Build a google.oauth2.credentials.Credentials object from a refresh token.
    Automatically refreshes the access token on first use.
    """
    from google.oauth2.credentials import Credentials
    return Credentials(
        token=None,
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=GOOGLE_OAUTH_CLIENT_ID,
        client_secret=GOOGLE_OAUTH_CLIENT_SECRET,
        scopes=SCOPES,
    )


async def build_calendar_service():
    """
    Builds and returns an authenticated Google Calendar API Resource.
    Raises RuntimeError if not connected (no refresh_token).
    """
    from googleapiclient.discovery import build
    import google.auth.transport.requests

    refresh_token = await load_refresh_token()
    if not refresh_token:
        raise RuntimeError("Google Calendar not connected. Visit /api/google/connect to authorise.")

    creds = get_credentials_from_refresh_token(refresh_token)
    # Eagerly refresh so we fail fast if the token is invalid/revoked
    request = google.auth.transport.requests.Request()
    creds.refresh(request)

    service = build("calendar", "v3", credentials=creds, cache_discovery=False)
    return service


async def get_connection_status() -> bool:
    """
    Returns True only if a refresh_token is stored, the OAuth app is configured,
    AND the token is actually valid (able to refresh).
    Clears the stored token if it is expired/revoked.
    """
    if not GOOGLE_OAUTH_CLIENT_ID or not GOOGLE_OAUTH_CLIENT_SECRET:
        return False
    token = await load_refresh_token()
    if not token:
        return False
    # Eagerly test the token so we don't lie to callers
    try:
        import google.auth.transport.requests
        creds = get_credentials_from_refresh_token(token)
        request = google.auth.transport.requests.Request()
        creds.refresh(request)
        return True
    except Exception as exc:
        logger.warning(f"[gcal] get_connection_status: token invalid ({exc}), clearing stored token.")
        await delete_refresh_token()
        return False
