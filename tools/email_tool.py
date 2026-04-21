"""
tools/email_tool.py – Email tool for reading, drafting, and sending emails.
Uses a mock provider by default; swap EMAIL_PROVIDER=smtp for real delivery.
"""
from __future__ import annotations
import uuid
from datetime import datetime
from typing import Any, Dict, List
from config import settings
from utils.logger import get_logger
from utils.models import Priority

logger = get_logger("tools.email")

# ─── Mock data store ──────────────────────────────────────────────────────────
_MOCK_INBOX: List[Dict[str, Any]] = [
    {
        "id": "email_001",
        "from": "alice@example.com",
        "subject": "Q3 Report Review",
        "body": "Hi, please review the Q3 report and share your feedback by Friday.",
        "priority": Priority.HIGH,
        "timestamp": "2024-10-01T09:00:00Z",
        "read": False,
    },
    {
        "id": "email_002",
        "from": "bob@example.com",
        "subject": "Team Lunch",
        "body": "Are you joining the team lunch this Thursday?",
        "priority": Priority.LOW,
        "timestamp": "2024-10-01T10:30:00Z",
        "read": True,
    },
    {
        "id": "email_003",
        "from": "ceo@example.com",
        "subject": "URGENT: Board Meeting Prep",
        "body": "We need the slides ready for tomorrow's board meeting. Please prioritise.",
        "priority": Priority.URGENT,
        "timestamp": "2024-10-01T11:00:00Z",
        "read": False,
    },
]

_SENT_EMAILS: List[Dict[str, Any]] = []


class EmailTool:
    """Provides email read / classify / draft / send capabilities."""

    # ── Read ─────────────────────────────────────────────────────────────────

    def read_emails(self, limit: int = 10, unread_only: bool = False) -> List[Dict]:
        """Fetch emails from inbox."""
        logger.info(f"Reading emails (limit={limit}, unread_only={unread_only})")
        emails = _MOCK_INBOX if not unread_only else [e for e in _MOCK_INBOX if not e["read"]]
        return emails[:limit]

    def get_email(self, email_id: str) -> Dict | None:
        """Fetch a single email by ID."""
        return next((e for e in _MOCK_INBOX if e["id"] == email_id), None)

    # ── Classify ──────────────────────────────────────────────────────────────

    def classify_priority(self, email_id: str) -> Dict[str, str]:
        """
        Classify the priority of an email based on keywords.
        In production, replace with LLM-based classification.
        """
        email = self.get_email(email_id)
        if not email:
            return {"error": f"Email {email_id} not found"}

        subject = email["subject"].lower()
        body = email["body"].lower()
        text = subject + " " + body

        if any(kw in text for kw in ["urgent", "asap", "immediately", "critical"]):
            priority = Priority.URGENT
        elif any(kw in text for kw in ["high", "important", "priority", "board"]):
            priority = Priority.HIGH
        elif any(kw in text for kw in ["lunch", "optional", "fyi", "casual"]):
            priority = Priority.LOW
        else:
            priority = Priority.MEDIUM

        logger.info(f"Classified email {email_id} as {priority}")
        return {"email_id": email_id, "priority": priority, "subject": email["subject"]}

    # ── Draft ─────────────────────────────────────────────────────────────────

    def draft_reply(self, email_id: str, context: str = "") -> Dict[str, str]:
        """Generate a draft reply for the given email."""
        email = self.get_email(email_id)
        if not email:
            return {"error": f"Email {email_id} not found"}

        # Template-based draft (swap with LLM call in production)
        draft = (
            f"Hi {email['from'].split('@')[0].capitalize()},\n\n"
            f"Thank you for your email regarding '{email['subject']}'.\n"
            f"{context if context else 'I will review this and get back to you shortly.'}\n\n"
            "Best regards,\n[Your Name]"
        )

        logger.info(f"Drafted reply for email {email_id}")
        return {"email_id": email_id, "draft": draft, "to": email["from"]}

    # ── Send ──────────────────────────────────────────────────────────────────

    def send_email(
        self, to: str, subject: str, body: str, cc: str = ""
    ) -> Dict[str, Any]:
        """
        Send an email.
        Mock mode: appends to _SENT_EMAILS list.
        SMTP mode: uses smtplib (configure via .env).
        """
        email_record = {
            "id": f"sent_{uuid.uuid4().hex[:6]}",
            "to": to,
            "cc": cc,
            "subject": subject,
            "body": body,
            "sent_at": datetime.utcnow().isoformat(),
            "provider": settings.email_provider,
        }

        if settings.email_provider == "smtp":
            self._send_smtp(to, subject, body, cc)
        else:
            # Mock send
            _SENT_EMAILS.append(email_record)
            logger.warning(f"AUDIT – Email sent to {to}: subject='{subject}'")

        logger.info(f"Email sent to {to} (id={email_record['id']})")
        return {"success": True, "email_id": email_record["id"], "to": to}

    def _send_smtp(self, to: str, subject: str, body: str, cc: str) -> None:
        import smtplib
        from email.mime.text import MIMEText
        msg = MIMEText(body)
        msg["Subject"] = subject
        msg["From"] = settings.smtp_user if hasattr(settings, "smtp_user") else "noreply@example.com"
        msg["To"] = to
        if cc:
            msg["Cc"] = cc
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
            server.starttls()
            server.login(settings.smtp_user, settings.smtp_password)
            server.send_message(msg)

    def get_sent(self) -> List[Dict]:
        """Return all sent emails (mock only)."""
        return _SENT_EMAILS


# Module-level singleton
email_tool = EmailTool()
