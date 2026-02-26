"""
Google OAuth 2.0 routes — Authorization Code Flow for admin.

Mounted under /api/google

Endpoints:
  GET  /api/google/connect          — Redirect admin to Google consent page
  GET  /api/google/oauth/callback   — Exchange code → tokens, store refresh_token
  GET  /api/google/status           — Is Google Calendar connected?
  POST /api/google/disconnect       — Remove stored refresh_token

Auth guard: accepts either
  - A valid JWT Bearer token with role=admin (existing CRM auth)
  - Or header X-ADMIN-OAUTH-KEY matching env ADMIN_OAUTH_KEY
"""

import os
import logging
from typing import Optional

from fastapi import APIRouter, Request, HTTPException, Header, Depends
from fastapi.responses import RedirectResponse, HTMLResponse, JSONResponse

from app.services.google_calendar_client import (
    GOOGLE_OAUTH_CLIENT_ID,
    GOOGLE_OAUTH_CLIENT_SECRET,
    GOOGLE_OAUTH_REDIRECT_URI,
    SCOPES,
    save_refresh_token,
    delete_refresh_token,
    get_connection_status,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/google", tags=["google-oauth"])

ADMIN_OAUTH_KEY = os.environ.get("ADMIN_OAUTH_KEY", "")


# ── Auth guard ────────────────────────────────────────────────────────────────

async def _require_admin(
    request: Request,
    x_admin_oauth_key: Optional[str] = Header(default=None, alias="X-ADMIN-OAUTH-KEY"),
):
    """
    Accept either:
    1. Header X-ADMIN-OAUTH-KEY == ADMIN_OAUTH_KEY (env)
    2. Valid JWT Bearer with role=admin (existing CRM system)
    """
    # Method 1: secret header
    if ADMIN_OAUTH_KEY and x_admin_oauth_key == ADMIN_OAUTH_KEY:
        return {"method": "secret_key"}

    # Method 2: JWT Bearer
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
        try:
            import jwt
            jwt_secret = os.environ.get("JWT_SECRET")
            if not jwt_secret:
                raise HTTPException(500, "JWT_SECRET not configured")
            payload = jwt.decode(token, jwt_secret, algorithms=["HS256"])
            if payload.get("role") != "admin":
                raise HTTPException(403, "Admin role required")
            return {"method": "jwt", "email": payload.get("email")}
        except jwt.ExpiredSignatureError:
            raise HTTPException(401, "Token expired")
        except jwt.InvalidTokenError as e:
            raise HTTPException(401, f"Invalid token: {e}")

    raise HTTPException(401, "Missing or invalid admin credentials. Use X-ADMIN-OAUTH-KEY header or JWT Bearer.")


# ── OAuth flow helpers ────────────────────────────────────────────────────────

def _get_flow():
    """Build a Google OAuth2 InstalledAppFlow-style web server flow."""
    from google_auth_oauthlib.flow import Flow

    if not GOOGLE_OAUTH_CLIENT_ID or not GOOGLE_OAUTH_CLIENT_SECRET:
        raise HTTPException(503, "GOOGLE_OAUTH_CLIENT_ID / GOOGLE_OAUTH_CLIENT_SECRET not configured.")

    client_config = {
        "web": {
            "client_id":     GOOGLE_OAUTH_CLIENT_ID,
            "client_secret": GOOGLE_OAUTH_CLIENT_SECRET,
            "auth_uri":      "https://accounts.google.com/o/oauth2/auth",
            "token_uri":     "https://oauth2.googleapis.com/token",
            "redirect_uris": [GOOGLE_OAUTH_REDIRECT_URI],
        }
    }
    flow = Flow.from_client_config(
        client_config,
        scopes=SCOPES,
        redirect_uri=GOOGLE_OAUTH_REDIRECT_URI,
    )
    return flow


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/oauth/start")
@router.get("/connect")
async def google_connect(
    _admin=Depends(_require_admin),
):
    """
    Generate the Google OAuth consent URL and redirect the admin to it.
    access_type=offline + prompt=consent ensures we get a refresh_token.
    Accessible via /api/google/oauth/start or /api/google/connect.
    """
    flow = _get_flow()
    auth_url, _ = flow.authorization_url(
        access_type="offline",
        prompt="consent",
        include_granted_scopes="false",
    )
    logger.info(f"[google-oauth] Redirecting admin to Google consent: {auth_url[:80]}...")
    return RedirectResponse(auth_url)


@router.get("/oauth/connect/{admin_key}", include_in_schema=False)
async def oauth_connect_bootstrap(admin_key: str):
    """
    Bootstrap public — ouvrable directement dans un navigateur.
    Vérifie admin_key dans l'URL, puis redirige vers Google consent.
    Usage : /api/google/oauth/connect/<ADMIN_OAUTH_KEY>
    """
    if not ADMIN_OAUTH_KEY or admin_key != ADMIN_OAUTH_KEY:
        raise HTTPException(403, "Forbidden")
    flow = _get_flow()
    auth_url, _ = flow.authorization_url(
        access_type="offline",
        prompt="consent",
        include_granted_scopes="false",
    )
    logger.info("[google-oauth] Bootstrap redirect via URL key.")
    return RedirectResponse(auth_url)


@router.get("/oauth/callback")
async def google_oauth_callback(
    code: Optional[str] = None,
    error: Optional[str] = None,
    state: Optional[str] = None,
):
    """
    Google redirects here after admin consent.
    Exchanges the authorization code for tokens; stores the refresh_token.
    No auth guard here — Google drives the redirect itself.
    """
    if error:
        logger.error(f"[google-oauth] OAuth error from Google: {error}")
        return HTMLResponse(
            f"""<html><body style="font-family:sans-serif;padding:40px">
            <h2 style="color:red">❌ Erreur OAuth : {error}</h2>
            <p>Retournez sur le dashboard admin et réessayez.</p>
            </body></html>""",
            status_code=400,
        )

    if not code:
        raise HTTPException(400, "Missing authorization code from Google.")

    try:
        flow = _get_flow()
        flow.fetch_token(code=code)
        creds = flow.credentials
    except Exception as exc:
        logger.exception(f"[google-oauth] Token exchange failed: {exc}")
        raise HTTPException(502, f"Token exchange failed: {exc}")

    if not creds.refresh_token:
        logger.error("[google-oauth] No refresh_token returned — was prompt=consent omitted?")
        return HTMLResponse(
            """<html><body style="font-family:sans-serif;padding:40px">
            <h2 style="color:orange">⚠️ Pas de refresh_token</h2>
            <p>Google n'a pas retourné de refresh_token. 
            Déconnectez l'application sur <a href="https://myaccount.google.com/permissions" target="_blank">myaccount.google.com/permissions</a>
            puis relancez /api/google/connect.</p>
            </body></html>""",
            status_code=200,
        )

    await save_refresh_token(creds.refresh_token)
    logger.info("[google-oauth] refresh_token stored successfully.")

    return HTMLResponse(
        """<html><body style="font-family:sans-serif;padding:40px;background:#f0fdf4">
        <h2 style="color:#16a34a">✅ Google Agenda connecté !</h2>
        <p>Le refresh_token a été enregistré. Vous pouvez fermer cette fenêtre.</p>
        <p><a href="https://israelgrowthventure.com/admin/crm/settings" 
              style="color:#00318D">Retour au dashboard admin</a></p>
        </body></html>""",
        status_code=200,
    )


@router.get("/status")
async def google_status(_admin=Depends(_require_admin)):
    """Returns whether Google Calendar is currently connected."""
    connected = await get_connection_status()
    return {"connected": connected}


@router.post("/disconnect")
async def google_disconnect(_admin=Depends(_require_admin)):
    """Remove the stored refresh_token, effectively disconnecting Google Calendar."""
    await delete_refresh_token()
    logger.info("[google-oauth] Google Calendar disconnected by admin.")
    return {"connected": False}


# ── Temporary reconnect helper (time-based token, remove after reconnect) ─────

import time as _time
import hmac as _hmac
import hashlib as _hashlib

_TEMP_REAUTH_SEED = b"igv-gcal-reauth-seed-2026"  # hardcoded — change after reconnect


def _valid_temp_token(token: str) -> bool:
    """
    Validates a short-lived hex token computed as:
        HMAC-SHA256(seed, str(floor(unix_ts / 600)))[0:8]
    Valid for any of 5 consecutive 10-min windows (±20 min tolerance).
    """
    now_window = int(_time.time() // 600)
    for offset in (-2, -1, 0, 1, 2):
        t = str(now_window + offset).encode()
        expected = _hmac.new(_TEMP_REAUTH_SEED, t, _hashlib.sha256).hexdigest()[:8]
        if _hmac.compare_digest(token.lower(), expected):
            return True
    return False


@router.get("/oauth/temp-connect/{token}", include_in_schema=False)
async def oauth_temp_connect(token: str):
    """
    Temporary reconnect endpoint — no admin-auth required, protected by time-based token.
    Compute token locally:
        $t = [Math]::Floor([DateTimeOffset]::UtcNow.ToUnixTimeSeconds() / 600)
        $seed = [System.Text.Encoding]::UTF8.GetBytes("igv-gcal-reauth-seed-2026")
        $hmac = [System.Security.Cryptography.HMACSHA256]::new($seed)
        $hex  = [BitConverter]::ToString($hmac.ComputeHash([System.Text.Encoding]::UTF8.GetBytes("$t"))) -replace '-',''
        Write-Host $hex.Substring(0,8).ToLower()
    Then visit: /api/google/oauth/temp-connect/{token}
    REMOVE THIS ENDPOINT after Google Calendar is reconnected.
    """
    if not _valid_temp_token(token):
        raise HTTPException(403, "Invalid or expired reauth token.")
    if not GOOGLE_OAUTH_CLIENT_ID or not GOOGLE_OAUTH_CLIENT_SECRET:
        raise HTTPException(503, "Google OAuth not configured (missing client_id/secret).")
    flow = _get_flow()
    auth_url, _ = flow.authorization_url(
        access_type="offline",
        prompt="consent",
        include_granted_scopes="false",
    )
    logger.info("[google-oauth] Temp-connect redirect to Google consent.")
    return RedirectResponse(auth_url)
