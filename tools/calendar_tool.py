"""
tools/calendar_tool.py – Calendar tool for availability checking, scheduling, and invites.
Uses a mock store by default; extend with Google Calendar API for production.
"""
from __future__ import annotations
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from utils.logger import get_logger

logger = get_logger("tools.calendar")

# ─── Mock calendar store ──────────────────────────────────────────────────────
_EVENTS: List[Dict[str, Any]] = [
    {
        "id": "evt_001",
        "title": "Weekly Standup",
        "start": "2024-10-02T09:00:00Z",
        "end":   "2024-10-02T09:30:00Z",
        "attendees": ["alice@example.com", "bob@example.com"],
        "location": "Zoom",
    },
    {
        "id": "evt_002",
        "title": "Product Review",
        "start": "2024-10-02T14:00:00Z",
        "end":   "2024-10-02T15:00:00Z",
        "attendees": ["ceo@example.com"],
        "location": "Conference Room A",
    },
]


class CalendarTool:
    """Provides calendar availability, scheduling, and invite capabilities."""

    # ── Read ─────────────────────────────────────────────────────────────────

    def get_events(self, date: str | None = None) -> List[Dict]:
        """Return all events, optionally filtered by date prefix (YYYY-MM-DD)."""
        if date:
            return [e for e in _EVENTS if e["start"].startswith(date)]
        return list(_EVENTS)

    def check_availability(
        self, date: str, start_time: str, duration_minutes: int = 60
    ) -> Dict[str, Any]:
        """
        Check whether a time slot is free.

        Args:
            date:             ISO date string (YYYY-MM-DD)
            start_time:       HH:MM (24-hour)
            duration_minutes: Length of the proposed meeting

        Returns:
            dict with 'available' bool and 'conflicts' list
        """
        slot_start = datetime.fromisoformat(f"{date}T{start_time}:00")
        slot_end   = slot_start + timedelta(minutes=duration_minutes)

        conflicts = []
        for event in _EVENTS:
            evt_start = datetime.fromisoformat(event["start"].replace("Z", ""))
            evt_end   = datetime.fromisoformat(event["end"].replace("Z", ""))
            # Overlap detection
            if not (slot_end <= evt_start or slot_start >= evt_end):
                conflicts.append(event["title"])

        available = len(conflicts) == 0
        logger.info(
            f"Availability check {date} {start_time} ({duration_minutes}min): "
            f"{'FREE' if available else 'BUSY – ' + str(conflicts)}"
        )
        return {
            "date": date,
            "start_time": start_time,
            "duration_minutes": duration_minutes,
            "available": available,
            "conflicts": conflicts,
        }

    # ── Schedule ─────────────────────────────────────────────────────────────

    def schedule_meeting(
        self,
        title: str,
        date: str,
        start_time: str,
        duration_minutes: int = 60,
        attendees: Optional[List[str]] = None,
        location: str = "Virtual",
    ) -> Dict[str, Any]:
        """
        Create a new calendar event.

        Returns:
            dict with the new event details
        """
        attendees = attendees or []
        slot_start = f"{date}T{start_time}:00Z"
        slot_end_dt = datetime.fromisoformat(f"{date}T{start_time}:00") + timedelta(minutes=duration_minutes)
        slot_end = slot_end_dt.strftime("%Y-%m-%dT%H:%M:%SZ")

        event = {
            "id": f"evt_{uuid.uuid4().hex[:6]}",
            "title": title,
            "start": slot_start,
            "end":   slot_end,
            "attendees": attendees,
            "location": location,
            "created_at": datetime.utcnow().isoformat(),
        }
        _EVENTS.append(event)
        logger.warning(f"AUDIT – Meeting scheduled: '{title}' on {date} at {start_time}")
        logger.info(f"Event created: {event['id']} – {title}")
        return {"success": True, "event": event}

    # ── Invites ───────────────────────────────────────────────────────────────

    def send_invite(self, event_id: str, attendee_email: str) -> Dict[str, Any]:
        """
        Send a calendar invite to an attendee (mock: just records it).
        In production, integrate with Google Calendar or Exchange.
        """
        event = next((e for e in _EVENTS if e["id"] == event_id), None)
        if not event:
            return {"success": False, "error": f"Event {event_id} not found"}

        if attendee_email not in event["attendees"]:
            event["attendees"].append(attendee_email)

        logger.warning(f"AUDIT – Invite sent: event={event_id}, to={attendee_email}")
        return {
            "success": True,
            "event_id": event_id,
            "invite_sent_to": attendee_email,
            "event_title": event["title"],
        }

    # ── Summary ───────────────────────────────────────────────────────────────

    def summarize_day(self, date: str) -> str:
        """Return a human-readable summary of the day's schedule."""
        events = self.get_events(date)
        if not events:
            return f"No events scheduled for {date}."
        lines = [f"Schedule for {date}:"]
        for e in events:
            start = e["start"][11:16]
            end   = e["end"][11:16]
            lines.append(f"  • {start}–{end}: {e['title']} @ {e.get('location','TBD')}")
        return "\n".join(lines)


# Module-level singleton
calendar_tool = CalendarTool()
