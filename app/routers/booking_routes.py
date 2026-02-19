"""
Booking routes — Google Calendar availability + event creation with Google Meet.

Uses OAuth Authorization Code Flow (user credentials stored as refresh_token).
This allows creating Google Meet links on plain Gmail — no Workspace required.

Endpoints:
  GET  /api/booking/availability  → free slots (Sun–Thu, 12:00–19:00 Asia/Jerusalem)
  POST /api/booking/book          → create Calendar event + Google Meet link
  GET  /api/booking/version       → deployed version + google connection status

Environment variables (all optional, have defaults):
  GOOGLE_CALENDAR_ID          calendar to use (default: "primary")
  BOOKING_TZ                  timezone string   (default: "Asia/Jerusalem")
  BOOKING_DAYS_ENABLED        comma-separated weekday numbers, Sun=0 (default: "0,1,2,3,4")
  BOOKING_START_HOUR          "HH:MM" (default: "12:00")
  BOOKING_END_HOUR            "HH:MM" (default: "19:00")
  BOOKING_SLOT_MINUTES        slot duration in minutes (default: "60")
  BOOKING_MIN_NOTICE_HOURS    min hours ahead (default: "12")
  BOOKING_LOOKAHEAD_DAYS      days ahead to scan (default: "14")
"""

import os
import logging
import uuid
from datetime import datetime, timedelta
from typing import Optional, List
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, EmailStr

from app.services.google_calendar_client import (
    build_calendar_service,
    get_connection_status,
    GOOGLE_CALENDAR_ID,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/booking", tags=["booking"])

# ── Env-driven config ─────────────────────────────────────────────────────────
_BOOKING_TZ          = os.environ.get("BOOKING_TZ", "Asia/Jerusalem")
_DAYS_RAW            = os.environ.get("BOOKING_DAYS_ENABLED", "0,1,2,3,4")
_WORK_DAYS: set      = {int(d.strip()) for d in _DAYS_RAW.split(",") if d.strip().isdigit()}
_START_HOUR, _START_MIN = (int(x) for x in os.environ.get("BOOKING_START_HOUR", "12:00").split(":"))
_END_HOUR,   _END_MIN   = (int(x) for x in os.environ.get("BOOKING_END_HOUR",   "19:00").split(":"))
_SLOT_MINUTES        = int(os.environ.get("BOOKING_SLOT_MINUTES",      "60"))
_MIN_NOTICE_HOURS    = int(os.environ.get("BOOKING_MIN_NOTICE_HOURS",  "12"))
_LOOKAHEAD_DAYS      = int(os.environ.get("BOOKING_LOOKAHEAD_DAYS",    "14"))

# Business rule: audits require at least 48h notice (hard-coded, not overridable by env var)
_HARD_MIN_NOTICE_HOURS = 48

# Convert BOOKING_DAYS (Sun=0 … Sat=6) to Python weekday() (Mon=0 … Sun=6)
# Sun(0)→6, Mon(1)→0, Tue(2)→1, Wed(3)→2, Thu(4)→3, Fri(5)→4, Sat(6)→5
_PYTHON_WORK_DAYS = {(d - 1) % 7 for d in _WORK_DAYS}


# ── Slot generator ───────────────────────────────────────────────────────────

def _generate_slots(start_search: datetime, end_search: datetime, tz: ZoneInfo) -> List[dict]:
    """Generate all candidate slots within working days / hours."""
    slots = []
    current = start_search.astimezone(tz)
    # Round up to next slot boundary
    if current.minute != 0 or current.second != 0 or current.microsecond != 0:
        current = current.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)

    while current < end_search:
        if current.weekday() in _PYTHON_WORK_DAYS:
            slot_start_mins = current.hour * 60 + current.minute
            work_start_mins = _START_HOUR * 60 + _START_MIN
            work_end_mins   = _END_HOUR   * 60 + _END_MIN
            if work_start_mins <= slot_start_mins and slot_start_mins + _SLOT_MINUTES <= work_end_mins:
                slot_end = current + timedelta(minutes=_SLOT_MINUTES)
                slots.append({"start": current.isoformat(), "end": slot_end.isoformat()})
        current += timedelta(minutes=_SLOT_MINUTES)
    return slots


# ── GET /version ─────────────────────────────────────────────────────────────

@router.get("/version")
async def booking_version():
    """Canary endpoint — returns deployed version + Google connection status."""
    connected = await get_connection_status()
    return {"version": "v6-oauth", "commit": "pending", "googleConnected": connected}


# ── GET /availability ────────────────────────────────────────────────────────

@router.get("/availability")
async def get_availability(
    days:     int = Query(default=None, ge=1, le=60),
    duration: int = Query(default=None),
):
    """Return free slots filtered against Google Calendar busy times."""
    if not await get_connection_status():
        raise HTTPException(
            503,
            "Google Calendar not connected. Admin must visit /api/google/connect.",
        )

    effective_days = days or _LOOKAHEAD_DAYS
    tz        = ZoneInfo(_BOOKING_TZ)
    now       = datetime.now(tz)
    # Enforce 48h minimum: take the stricter of the two values
    start_search = now + timedelta(hours=max(_MIN_NOTICE_HOURS, _HARD_MIN_NOTICE_HOURS))
    end_search   = now + timedelta(days=effective_days)

    candidates = _generate_slots(start_search, end_search, tz)
    if not candidates:
        return {"slots": []}

    utc = ZoneInfo("UTC")
    try:
        service = await build_calendar_service()
        fb = service.freebusy().query(body={
            "timeMin":  start_search.astimezone(utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "timeMax":  end_search.astimezone(utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "timeZone": "UTC",
            "items":    [{"id": GOOGLE_CALENDAR_ID}],
        }).execute()
        busy_list = fb.get("calendars", {}).get(GOOGLE_CALENDAR_ID, {}).get("busy", [])
    except RuntimeError as e:
        raise HTTPException(503, str(e))
    except Exception as exc:
        logger.exception(f"[booking] freebusy failed: {exc}")
        return {"slots": [], "warning": str(exc)}

    busy_intervals = [
        (
            datetime.fromisoformat(b["start"].replace("Z", "+00:00")),
            datetime.fromisoformat(b["end"].replace("Z", "+00:00")),
        )
        for b in busy_list
    ]

    free = [
        s for s in candidates
        if not any(
            datetime.fromisoformat(s["start"]) < b_end and datetime.fromisoformat(s["end"]) > b_start
            for b_start, b_end in busy_intervals
        )
    ]
    return {"slots": free}


# ── POST /book ───────────────────────────────────────────────────────────────

class BookingRequest(BaseModel):
    start: str
    end:   str
    email: EmailStr
    name:  Optional[str] = None
    phone: Optional[str] = None
    topic: Optional[str] = "audit"


@router.post("/book")
async def create_booking(body: BookingRequest):
    """
    Create a Google Calendar event with a Google Meet link (OAuth user credentials).
    Returns { eventId, meetLink, htmlLink, start, end }.
    """
    # Step 1: Parse datetime (fast, no I/O)
    try:
        start_dt = datetime.fromisoformat(body.start)
        end_dt   = datetime.fromisoformat(body.end)
    except ValueError:
        raise HTTPException(422, "start/end must be ISO 8601 datetime strings.")

    # Step 2: 48h business rule guard — BEFORE Google Calendar check (anti-bypass)
    tz_j     = ZoneInfo(_BOOKING_TZ)
    now_tz   = datetime.now(tz_j)
    if start_dt.tzinfo is None:
        # Naive datetime: assume BOOKING_TZ (document assumption in log)
        start_dt = start_dt.replace(tzinfo=tz_j)
        logger.warning(
            f"[booking] start_time '{body.start}' had no timezone info; "
            f"assumed {_BOOKING_TZ}"
        )
    threshold_48h = now_tz + timedelta(hours=_HARD_MIN_NOTICE_HOURS)
    if start_dt.astimezone(tz_j) < threshold_48h:
        logger.warning(
            f"[booking] REFUSED: slot {start_dt.isoformat()} < 48h threshold "
            f"({threshold_48h.isoformat()}) requested by {body.email}"
        )
        raise HTTPException(
            400,
            "Ce cr\u00e9neau n'est pas r\u00e9servable : d\u00e9lai minimum 48h."
        )

    # Step 3: Google Calendar connectivity
    if not await get_connection_status():
        raise HTTPException(
            503,
            "Google Calendar not connected. L'admin doit connecter Google Agenda.",
        )


    utc = ZoneInfo("UTC")

    # Re-verify the slot is still free
    try:
        service = await build_calendar_service()
        fb = service.freebusy().query(body={
            "timeMin":  start_dt.astimezone(utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "timeMax":  end_dt.astimezone(utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "timeZone": "UTC",
            "items":    [{"id": GOOGLE_CALENDAR_ID}],
        }).execute()
        busy = fb.get("calendars", {}).get(GOOGLE_CALENDAR_ID, {}).get("busy", [])
        if busy:
            raise HTTPException(409, "Ce créneau vient d'être réservé. Veuillez en choisir un autre.")
    except HTTPException:
        raise
    except Exception as exc:
        logger.warning(f"[booking] pre-book freebusy check failed (non-fatal): {exc}")

    attendee_name = body.name or body.email.split("@")[0]

    event_body = {
        "summary": "Audit IGV – Implantation en Israël",
        "description": (
            f"Client : {attendee_name}\n"
            f"Email  : {body.email}\n"
            + (f"Tél.   : {body.phone}\n" if body.phone else "")
            + f"Sujet  : {body.topic or 'audit'}\n"
            + "Paiement confirmé."
        ),
        "start": {"dateTime": start_dt.isoformat(), "timeZone": _BOOKING_TZ},
        "end":   {"dateTime": end_dt.isoformat(),   "timeZone": _BOOKING_TZ},
        "attendees": [{"email": body.email, "displayName": attendee_name}],
        "conferenceData": {
            "createRequest": {
                "requestId": str(uuid.uuid4()),
                "conferenceSolutionKey": {"type": "hangoutsMeet"},
            }
        },
        "reminders": {"useDefault": True},
    }

    try:
        created = service.events().insert(
            calendarId=GOOGLE_CALENDAR_ID,
            body=event_body,
            conferenceDataVersion=1,
            sendUpdates="all",
        ).execute()
    except Exception as exc:
        logger.exception(f"[booking] events.insert failed: {exc}")
        raise HTTPException(502, f"Impossible de créer l'événement : {exc}")

    meet_link = (
        created.get("conferenceData", {})
               .get("entryPoints", [{}])[0]
               .get("uri", "")
    ) or created.get("htmlLink", "")

    start_formatted = start_dt.strftime("%d/%m/%Y à %H:%M")

    try:
        await _send_booking_confirmation(
            to_email=body.email,
            name=attendee_name,
            start_fmt=start_formatted,
            meet_link=meet_link,
        )
    except Exception as mail_exc:
        logger.warning(f"[booking] Confirmation email failed (non-fatal): {mail_exc}")

    return {
        "eventId":  created.get("id"),
        "meetLink": meet_link,
        "htmlLink": created.get("htmlLink"),
        "start":    created["start"]["dateTime"],
        "end":      created["end"]["dateTime"],
    }


# ── Confirmation email ───────────────────────────────────────────────────────

async def _send_booking_confirmation(to_email: str, name: str, start_fmt: str, meet_link: str):
    """Send a booking confirmation email via OVH SMTP."""
    import aiosmtplib
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText

    smtp_host     = os.getenv("SMTP_HOST", "ssl0.ovh.net")
    smtp_port     = int(os.getenv("SMTP_PORT", "465"))
    smtp_user     = os.getenv("SMTP_USER", "contact@israelgrowthventure.com")
    smtp_password = os.getenv("SMTP_PASSWORD")
    smtp_from     = os.getenv("SMTP_FROM", "contact@israelgrowthventure.com")

    if not smtp_password:
        logger.warning("[booking] SMTP_PASSWORD not set, skipping confirmation email.")
        return

    subject = f"Confirmation de votre rendez-vous IGV – {start_fmt}"
    plain   = (
        f"Bonjour {name},\n\n"
        f"Votre rendez-vous d'audit IGV est confirmé pour le {start_fmt}.\n\n"
        + (f"Lien Google Meet : {meet_link}\n\n" if meet_link else "")
        + "À bientôt,\nL'équipe Israel Growth Venture\ncontact@israelgrowthventure.com\n"
    )
    meet_btn = (
        f"<p><a href='{meet_link}' style='background:#00318D;color:white;"
        f"padding:10px 20px;border-radius:8px;text-decoration:none;"
        f"display:inline-block;margin-top:8px;'>Rejoindre Google Meet</a></p>"
        if meet_link else ""
    )
    html = f"""
    <html><body style="font-family:Arial,sans-serif;color:#222;">
    <h2 style="color:#00318D;">Rendez-vous confirmé !</h2>
    <p>Bonjour <strong>{name}</strong>,</p>
    <p>Votre session d'audit <strong>Implantation en Israël</strong> est confirmée :</p>
    <p style="font-size:18px;font-weight:bold;color:#00318D;">{start_fmt}</p>
    {meet_btn}
    <p style="margin-top:24px;color:#555;font-size:13px;">Une question ? Répondez à cet email ou écrivez-nous à
    <a href="mailto:contact@israelgrowthventure.com">contact@israelgrowthventure.com</a>.</p>
    <p style="color:#555;font-size:13px;">L'équipe Israel Growth Venture</p>
    </body></html>
    """

    msg = MIMEMultipart("alternative")
    msg["Subject"]  = subject
    msg["From"]     = f"Israel Growth Venture <{smtp_from}>"
    msg["To"]       = to_email
    msg["Reply-To"] = smtp_from
    msg.attach(MIMEText(plain, "plain"))
    msg.attach(MIMEText(html, "html"))

    await aiosmtplib.send(
        msg,
        hostname=smtp_host,
        port=smtp_port,
        username=smtp_user,
        password=smtp_password,
        use_tls=True,
    )
