"""
Google OAuth 2.0 routes — Authorization Code Flow (confidential client, NO PKCE).

WHY NO PKCE:
  PKCE is designed for PUBLIC clients (SPA, mobile) that cannot hold a client_secret.
  This backend IS a confidential client — it stores GOOGLE_OAUTH_CLIENT_SECRET securely.
  google-auth-oauthlib ≥1.0 auto-generates a code_verifier inside the Flow instance on
  authorization_url(); recreating a new Flow in the callback loses that verifier and
  Google returns "invalid_grant: Missing code verifier".
  Fix: build the auth URL manually and exchange the code via direct HTTP POST — no Flow
  object in the callback, no PKCE, no state mismatch possible.

Mounted under /api/google

Endpoints:
  GET  /api/google/oauth/connect/{key}  — Bootstrap: redirect to Google (URL-key auth)
  GET  /api/google/oauth/start-now      — Same via ?key= query param
  GET  /api/google/oauth/start          — Redirect (JWT/header auth)
  GET  /api/google/connect              — Redirect alias (JWT/header auth)
  GET  /api/google/oauth-url            — Return consent URL as JSON (SPA helper)
  GET  /api/google/oauth/callback       — Receive code, exchange → refresh_token (NO PKCE)
  GET  /api/google/status               — Is Google Calendar connected?
  POST /api/google/disconnect           — Remove stored refresh_token
"""

import os
import logging
from typing import Optional
from urllib.parse import urlencode

import httpx
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

ADMIN_OAUTH_KEY       = os.environ.get("ADMIN_OAUTH_KEY", "")
_GOOGLE_AUTH_URI      = "https://accounts.google.com/o/oauth2/v2/auth"
_GOOGLE_TOKEN_URI     = "https://oauth2.googleapis.com/token"


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


# ── Auth URL builder (NO PKCE) ────────────────────────────────────────────────

def _build_auth_url() -> str:
    """
    Build the Google consent URL manually.
    We deliberately do NOT use google-auth-oauthlib Flow.authorization_url() because
    version ≥1.0 auto-injects a PKCE code_challenge that we cannot honour at callback
    time (stateless server → new Flow object = code_verifier gone → invalid_grant).
    A confidential client with client_secret does not need PKCE.
    """
    if not GOOGLE_OAUTH_CLIENT_ID or not GOOGLE_OAUTH_CLIENT_SECRET:
        raise HTTPException(503, "GOOGLE_OAUTH_CLIENT_ID / GOOGLE_OAUTH_CLIENT_SECRET not configured.")

    scope = " ".join(SCOPES)
    params = {
        "client_id":     GOOGLE_OAUTH_CLIENT_ID,
        "redirect_uri":  GOOGLE_OAUTH_REDIRECT_URI,
        "response_type": "code",
        "scope":         scope,
        "access_type":   "offline",
        "prompt":        "consent",
        # NO code_challenge / code_challenge_method — confidential client, PKCE not needed
    }
    url = f"{_GOOGLE_AUTH_URI}?{urlencode(params)}"
    logger.info(
        "[google-oauth] Auth URL built (no PKCE). "
        f"redirect_uri={GOOGLE_OAUTH_REDIRECT_URI}"
    )
    return url


# ── Token exchange helper (direct HTTP POST, NO PKCE) ─────────────────────────

async def _exchange_code_for_tokens(code: str) -> dict:
    """
    Exchange a Google authorization code for access + refresh tokens.
    Uses direct HTTP POST — no Flow object, no PKCE code_verifier.
    Correct for confidential (server-side) OAuth 2.0 clients.
    """
    logger.info("[google-oauth] Exchanging auth code via direct POST to token endpoint…")

    payload = {
        "code":          code,
        "client_id":     GOOGLE_OAUTH_CLIENT_ID,
        "client_secret": GOOGLE_OAUTH_CLIENT_SECRET,
        "redirect_uri":  GOOGLE_OAUTH_REDIRECT_URI,
        "grant_type":    "authorization_code",
        # NO code_verifier — we never sent code_challenge in the auth URL
    }

    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(_GOOGLE_TOKEN_URI, data=payload)

    logger.info(f"[google-oauth] Token endpoint responded HTTP {resp.status_code}")

    if resp.status_code != 200:
        body = resp.text[:300]
        logger.error(f"[google-oauth] Token exchange FAILED: {body}")
        raise RuntimeError(f"HTTP {resp.status_code}: {body}")

    tokens = resp.json()
    logger.info(
        "[google-oauth] Token exchange OK. refresh_token present: %s",
        bool(tokens.get("refresh_token")),
    )
    return tokens


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/oauth-url")
async def get_oauth_url(_admin=Depends(_require_admin)):
    """
    Returns the Google OAuth consent URL as JSON so the SPA can open it.
    GET /api/google/oauth-url  →  { "auth_url": "https://accounts.google.com/..." }
    """
    auth_url = _build_auth_url()
    logger.info(f"[google-oauth] Returning OAuth URL to SPA: {auth_url[:80]}…")
    return JSONResponse({"auth_url": auth_url})


@router.get("/oauth/start")
@router.get("/connect")
async def google_connect(_admin=Depends(_require_admin)):
    """
    Redirect admin to Google consent page (JWT Bearer or header key auth).
    Accessible via /api/google/oauth/start or /api/google/connect.
    """
    auth_url = _build_auth_url()
    logger.info(f"[google-oauth] Authenticated start → redirecting to Google consent.")
    return RedirectResponse(auth_url)


@router.get("/oauth/start-now", include_in_schema=False)
async def oauth_connect_query(key: str = ""):
    """
    Bootstrap via ?key= query param — no auth header needed, usable in any browser.
    Usage: /api/google/oauth/start-now?key=<ADMIN_OAUTH_KEY>
    """
    if not ADMIN_OAUTH_KEY or key != ADMIN_OAUTH_KEY:
        raise HTTPException(403, "Forbidden: wrong or missing key")
    auth_url = _build_auth_url()
    logger.info("[google-oauth] Bootstrap redirect (query key).")
    return RedirectResponse(auth_url)


@router.get("/oauth/connect/{admin_key}", include_in_schema=False)
async def oauth_connect_bootstrap(admin_key: str):
    """
    Bootstrap via URL path param — clé dans l'URL.
    Usage: /api/google/oauth/connect/<ADMIN_OAUTH_KEY>
    """
    if not ADMIN_OAUTH_KEY or admin_key != ADMIN_OAUTH_KEY:
        raise HTTPException(403, "Forbidden")
    auth_url = _build_auth_url()
    logger.info("[google-oauth] Bootstrap redirect (URL key).")
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

    # ── Direct HTTP POST to Google — NO PKCE, confidential client ────────────
    try:
        tokens = await _exchange_code_for_tokens(code)
    except Exception as exc:
        logger.error(f"[google-oauth] Token exchange exception: {exc}")
        return HTMLResponse(
            f"""<html><body style="font-family:sans-serif;padding:40px">
            <h2 style="color:red">❌ Échec échange de code</h2>
            <pre style="background:#fee2e2;padding:12px;border-radius:6px;white-space:pre-wrap">{exc}</pre>
            <p>Vérifiez que le Redirect URI dans Google Cloud Console correspond à :
            <br><code>{GOOGLE_OAUTH_REDIRECT_URI}</code></p>
            </body></html>""",
            status_code=502,
        )

    refresh_token = tokens.get("refresh_token")

    if not refresh_token:
        logger.warning("[google-oauth] No refresh_token returned — may already be authorized. Revoke and retry.")
        return HTMLResponse(
            f"""<html><body style="font-family:sans-serif;padding:40px">
            <h2 style="color:orange">⚠️ Pas de refresh_token retourné</h2>
            <p>Google ne retourne un refresh_token qu'à la <strong>première</strong> autorisation
            (ou après révocation explicite).</p>
            <p>Révoquez l'accès sur
            <a href="https://myaccount.google.com/permissions" target="_blank">
            myaccount.google.com/permissions</a> puis relancez.</p>
            </body></html>""",
            status_code=200,
        )

    await save_refresh_token(refresh_token)
    logger.info("[google-oauth] ✅ refresh_token stored in MongoDB + env.")

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

