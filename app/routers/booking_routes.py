"""
Booking routes — Google Calendar availability + event creation with Google Meet.

Endpoints:
  GET  /api/booking/availability   → free 60-min slots (Sun-Thu 09:00-18:00 Asia/Jerusalem)
  POST /api/booking/book           → create Calendar event + Meet link

Environment:
  GOOGLE_SERVICE_ACCOUNT_FILE  path to service account JSON (default /etc/secrets/google_service_account.json)
  BOOKING_CALENDAR_ID          calendar ID (default israel.growth.venture@gmail.com)
"""

import os
import logging
import json
from datetime import datetime, timedelta, timezone, date
from typing import Optional, List
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, EmailStr

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/booking", tags=["booking"])

# ── Constants ────────────────────────────────────────────────────────────────
CALENDAR_ID        = os.environ.get("BOOKING_CALENDAR_ID", "israel.growth.venture@gmail.com")
# The IGV Gmail calendar must be SHARED (edit access) with the service account email
# (visible in the service account JSON as "client_email").
# Share it in Google Calendar settings → "Share with specific people or groups".
SA_FILE            = os.environ.get("GOOGLE_SERVICE_ACCOUNT_FILE", "/etc/secrets/google_service_account.json")
IGV_EMAIL          = "israel.growth.venture@gmail.com"
SCOPES             = [
    "https://www.googleapis.com/auth/calendar",
]
WORK_DAYS          = {6, 0, 1, 2, 3}    # Sun=6, Mon=0, Tue=1, Wed=2, Thu=3
WORK_START_HOUR    = 9
WORK_END_HOUR      = 18
SLOT_MINUTES       = 60

# ── Google API client ────────────────────────────────────────────────────────

def _get_calendar_service():
    """Return an authenticated Google Calendar API service object, or raise."""
    try:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build

        if not os.path.exists(SA_FILE):
            logger.error(f"[booking] Service account file not found: {SA_FILE}")
            raise HTTPException(502, "Booking service not configured (missing credentials).")

        # Verify it looks like a service account (not an OAuth2 client secret)
        with open(SA_FILE) as f:
            raw = json.load(f)
        if raw.get("type") != "service_account":
            logger.error(f"[booking] Credential file is type={raw.get('type')!r}, expected 'service_account'.")
            raise HTTPException(502, "Booking service not configured (wrong credential type).")

        creds = service_account.Credentials.from_service_account_info(raw, scopes=SCOPES)
        service = build("calendar", "v3", credentials=creds, cache_discovery=False)
        return service
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception(f"[booking] Failed to initialize Google Calendar service: {exc}")
        raise HTTPException(502, f"Booking service error: {exc}")


def _all_slots(start_dt: datetime, end_dt: datetime, tz: ZoneInfo) -> List[dict]:
    """Generate all potential 60-min slots in working hours between start_dt and end_dt."""
    slots = []
    current = start_dt.astimezone(tz)
    while current < end_dt:
        # weekday(): Mon=0 … Sun=6
        if current.weekday() in WORK_DAYS:
            if WORK_START_HOUR <= current.hour < WORK_END_HOUR:
                slot_end = current + timedelta(minutes=SLOT_MINUTES)
                if slot_end.hour <= WORK_END_HOUR:
                    slots.append({
                        "start": current.isoformat(),
                        "end": slot_end.isoformat(),
                    })
        current += timedelta(minutes=SLOT_MINUTES)
    return slots


# ── GET /availability ────────────────────────────────────────────────────────

@router.get("/availability")
async def get_availability(
    days:     int    = Query(default=14, ge=1, le=60, description="Number of days ahead to scan"),
    duration: int    = Query(default=60, description="Slot duration in minutes (ignored, always 60)"),
    tz:       str    = Query(default="Asia/Jerusalem", description="Client timezone for display"),
):
    """
    Return free 60-min slots in working hours (Sun–Thu, 09:00–18:00 Asia/Jerusalem)
    for the next `days` days, filtered against Google Calendar busy times.
    """
    try:
        user_tz = ZoneInfo(tz)
    except Exception:
        user_tz = ZoneInfo("Asia/Jerusalem")

    israel_tz   = ZoneInfo("Asia/Jerusalem")
    now_il      = datetime.now(israel_tz)
    # Round up to next full hour so we never return a past slot
    start_search = now_il.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
    end_search   = start_search + timedelta(days=days)

    # Build all candidate slots
    candidates = _all_slots(start_search, end_search, israel_tz)
    if not candidates:
        return {"slots": []}

    # Fetch busy times from Google Calendar
    try:
        service = _get_calendar_service()
        freebusy_body = {
            "timeMin":  start_search.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "timeMax":  end_search.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "timeZone": "UTC",
            "items":    [{"id": CALENDAR_ID}],
        }
        fb_result = service.freebusy().query(body=freebusy_body).execute()
        busy_list = fb_result.get("calendars", {}).get(CALENDAR_ID, {}).get("busy", [])
    except HTTPException as he:
        # Calendar not configured → return empty list so UI degrades gracefully
        logger.warning(f"[booking] Calendar not available ({he.detail}), returning empty slots.")
        return {"slots": [], "warning": he.detail}
    except Exception as exc:
        logger.exception(f"[booking] freebusy API call failed: {exc}")
        # Return empty list + warning instead of crashing the page
        return {"slots": [], "warning": str(exc)}

    # Parse busy intervals
    busy_intervals = []
    for b in busy_list:
        b_start = datetime.fromisoformat(b["start"].replace("Z", "+00:00"))
        b_end   = datetime.fromisoformat(b["end"].replace("Z", "+00:00"))
        busy_intervals.append((b_start, b_end))

    # Filter out busy slots
    free_slots = []
    for slot in candidates:
        s_start = datetime.fromisoformat(slot["start"])
        s_end   = datetime.fromisoformat(slot["end"])
        busy = any(
            s_start < b_end and s_end > b_start
            for b_start, b_end in busy_intervals
        )
        if not busy:
            # Return in user timezone for display
            free_slots.append({
                "start": s_start.astimezone(user_tz).isoformat(),
                "end":   s_end.astimezone(user_tz).isoformat(),
            })

    return {"slots": free_slots}


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
    Create a Google Calendar event with Google Meet conference.
    Invites both the client and IGV.
    Returns { eventId, meetLink, htmlLink, start, end }.
    """
    # Validate ISO datetimes
    try:
        start_dt = datetime.fromisoformat(body.start)
        end_dt   = datetime.fromisoformat(body.end)
    except ValueError:
        raise HTTPException(422, "start/end must be ISO 8601 datetime strings.")

    attendee_name = body.name or body.email.split("@")[0]

    event_body = {
        "summary":     f"IGV Audit – {attendee_name}",
        "description": (
            f"Audit d'implantation en Israël\n"
            f"Client : {attendee_name}\n"
            f"Email  : {body.email}\n"
            + (f"Tél.   : {body.phone}\n" if body.phone else "")
            + f"Sujet  : {body.topic or 'audit'}\n"
        ),
        "start": {
            "dateTime": start_dt.isoformat(),
            "timeZone": "Asia/Jerusalem",
        },
        "end": {
            "dateTime": end_dt.isoformat(),
            "timeZone": "Asia/Jerusalem",
        },
        "attendees": [
            {"email": body.email,  "displayName": attendee_name},
            {"email": IGV_EMAIL,   "displayName": "Israel Growth Venture"},
        ],
        "conferenceData": {
            "createRequest": {
                "requestId":             f"igv-{int(start_dt.timestamp())}",
                "conferenceSolutionKey": {"type": "hangoutsMeet"},
            }
        },
        "reminders": {
            "useDefault": False,
            "overrides":  [
                {"method": "email",  "minutes": 24 * 60},
                {"method": "popup",  "minutes": 15},
            ],
        },
        "sendUpdates": "all",
    }

    try:
        service = _get_calendar_service()
        created = service.events().insert(
            calendarId=CALENDAR_ID,
            body=event_body,
            conferenceDataVersion=1,
            sendUpdates="all",
        ).execute()
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception(f"[booking] Failed to create event: {exc}")
        raise HTTPException(502, f"Could not create calendar event: {exc}")

    meet_link = (
        created.get("conferenceData", {})
               .get("entryPoints", [{}])[0]
               .get("uri", "")
    )

    return {
        "eventId":  created.get("id"),
        "meetLink": meet_link,
        "htmlLink": created.get("htmlLink"),
        "start":    created["start"]["dateTime"],
        "end":      created["end"]["dateTime"],
    }
