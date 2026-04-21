"""
agents/planner.py – Planner Agent.
Receives user intent and decomposes it into an ordered list of tool steps.

Provider priority:
  1. Groq  (free)  – set GROQ_API_KEY in .env
  2. OpenAI (paid) – set OPENAI_API_KEY + LLM_PROVIDER=openai
  3. Mock / rule-based – no key needed, always works
"""
from __future__ import annotations
import json
import re
from typing import Any, Dict, List
from config import settings
from utils.logger import get_logger
from utils.models import AgentStep, TaskPlan, ToolName
from utils.rbac import requires_confirmation

logger = get_logger("agents.planner")

# ─── Prompt template ─────────────────────────────────────────────────────────
_SYSTEM_PROMPT = """You are an AI task planner for an enterprise workflow system.
Given a user request, produce a JSON plan with a list of steps.

Available tools:
- email: read_emails, classify_priority, draft_reply, send_email
- calendar: get_events, check_availability, schedule_meeting, send_invite, summarize_day
- document: parse_pdf, summarize, extract_key_info, process_document

Respond ONLY with a valid JSON object. No explanation, no markdown fences.
Format:
{
  "steps": [
    {
      "tool": "<tool_name>",
      "action": "<action_name>",
      "parameters": { "<key>": "<value>" },
      "depends_on": []
    }
  ]
}

Rules:
- tool must be one of: email, calendar, document
- action must match the list above exactly
- parameters must be a flat JSON object with string/number values
- depends_on is a list of step indices (integers) that must finish first
- Use only the steps actually needed – keep the plan short
"""

# ─── Example parameter shapes so LLM fills them correctly ────────────────────
_PARAM_HINTS = {
    "read_emails":        {"limit": 5, "unread_only": False},
    "classify_priority":  {"email_id": "email_001"},
    "draft_reply":        {"email_id": "email_001", "context": ""},
    "send_email":         {"to": "user@example.com", "subject": "Subject", "body": "Body"},
    "get_events":         {"date": "2024-10-02"},
    "check_availability": {"date": "2024-10-02", "start_time": "14:00", "duration_minutes": 60},
    "schedule_meeting":   {"title": "Meeting", "date": "2024-10-02", "start_time": "14:00",
                           "duration_minutes": 60, "attendees": ["team@example.com"]},
    "send_invite":        {"event_id": "evt_001", "attendee_email": "user@example.com"},
    "summarize_day":      {"date": "2024-10-02"},
    "parse_pdf":          {"file_path": "./data/sample.pdf"},
    "summarize":          {"text": ""},
    "extract_key_info":   {"text": ""},
    "process_document":   {"file_path": "./data/sample.pdf"},
}


class PlannerAgent:
    """Breaks a natural language request into executable AgentSteps."""

    def __init__(self) -> None:
        self._client = None

    def _get_client(self):
        """
        Lazy-load LLM client. Supports Groq and OpenAI via the same
        openai-compatible SDK (both use openai.OpenAI with a custom base_url).
        """
        if self._client is not None:
            return self._client

        if not settings.use_llm:
            self._client = "mock"
            logger.info("No LLM API key found – using rule-based planner")
            return self._client

        try:
            from openai import OpenAI
            if settings.llm_provider == "groq":
                self._client = OpenAI(
                    api_key=settings.groq_api_key,
                    base_url="https://api.groq.com/openai/v1",
                )
                logger.info(f"Planner using Groq ({settings.groq_model})")
            else:
                self._client = OpenAI(api_key=settings.openai_api_key)
                logger.info(f"Planner using OpenAI ({settings.openai_model})")
        except ImportError:
            logger.warning("openai package not installed – using rule-based planner")
            self._client = "mock"

        return self._client

    # ── LLM planning ─────────────────────────────────────────────────────────

    def _plan_with_llm(self, user_request: str, context: str) -> List[Dict]:
        """Call Groq/OpenAI to generate a structured step plan."""
        client = self._get_client()
        if client == "mock":
            return self._rule_based_plan(user_request)

        # Enrich the prompt with today's date and param hints
        from datetime import date
        today = date.today().isoformat()
        user_msg = (
            f"Today's date: {today}\n"
            f"Parameter shapes for reference: {json.dumps(_PARAM_HINTS, indent=2)}\n\n"
            f"Relevant context from memory:\n{context or 'None'}\n\n"
            f"User request: {user_request}"
        )

        try:
            response = client.chat.completions.create(
                model=settings.active_llm_model,
                messages=[
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user",   "content": user_msg},
                ],
                temperature=settings.llm_temperature,
                max_tokens=700,
            )
            raw = response.choices[0].message.content.strip()
            # Strip markdown fences that some models still add
            raw = re.sub(r"```json|```", "", raw).strip()
            data = json.loads(raw)
            steps = data.get("steps", [])
            logger.info(f"LLM returned {len(steps)} steps")
            return steps
        except json.JSONDecodeError as e:
            logger.warning(f"LLM returned invalid JSON ({e}); falling back to rules")
            return self._rule_based_plan(user_request)
        except Exception as e:
            logger.warning(f"LLM planning failed ({e}); falling back to rules")
            return self._rule_based_plan(user_request)

    # ── Rule-based fallback ───────────────────────────────────────────────────

    def _rule_based_plan(self, request: str) -> List[Dict]:
        """
        Keyword-based task decomposition used when no LLM key is configured.
        Handles the most common enterprise voice commands.
        """
        from datetime import date, timedelta
        import re as _re

        req = request.lower()
        steps: List[Dict] = []

        # ── Resolve date from request ─────────────────────────────────────────
        today = date.today()
        if "tomorrow" in req:
            target_date = (today + timedelta(days=1)).isoformat()
        elif "today" in req:
            target_date = today.isoformat()
        elif "next week" in req:
            target_date = (today + timedelta(days=7)).isoformat()
        else:
            target_date = today.isoformat()

        # ── Resolve time from request ─────────────────────────────────────────
        time_match = _re.search(r"(\d{1,2})(?::(\d{2}))?\s*(am|pm)?", req)
        if time_match:
            hour = int(time_match.group(1))
            minute = time_match.group(2) or "00"
            meridiem = time_match.group(3) or ""
            if meridiem == "pm" and hour != 12:
                hour += 12
            elif meridiem == "am" and hour == 12:
                hour = 0
            start_time = f"{hour:02d}:{minute}"
        else:
            start_time = "10:00"

        # ── Email branch ──────────────────────────────────────────────────────
        if any(kw in req for kw in ["email", "mail", "inbox", "message"]):
            if any(kw in req for kw in ["summarize", "summary", "summarise"]):
                steps.append({"tool": "email", "action": "read_emails",
                               "parameters": {"limit": 10, "unread_only": False},
                               "depends_on": []})
            elif any(kw in req for kw in ["unread", "new"]):
                steps.append({"tool": "email", "action": "read_emails",
                               "parameters": {"limit": 10, "unread_only": True},
                               "depends_on": []})
            elif any(kw in req for kw in ["send", "reply", "respond"]):
                steps.append({"tool": "email", "action": "send_email",
                               "parameters": {"to": "recipient@example.com",
                                              "subject": "Re: Your message",
                                              "body": "Thank you for your email. I will review and respond shortly."},
                               "depends_on": []})
            elif any(kw in req for kw in ["draft"]):
                steps.append({"tool": "email", "action": "draft_reply",
                               "parameters": {"email_id": "email_001", "context": ""},
                               "depends_on": []})
            elif any(kw in req for kw in ["priorit", "urgent", "important"]):
                steps.append({"tool": "email", "action": "read_emails",
                               "parameters": {"limit": 10}, "depends_on": []})
                steps.append({"tool": "email", "action": "classify_priority",
                               "parameters": {"email_id": "email_001"}, "depends_on": []})
            else:
                steps.append({"tool": "email", "action": "read_emails",
                               "parameters": {"limit": 5}, "depends_on": []})

        # ── Calendar branch ───────────────────────────────────────────────────
        if any(kw in req for kw in ["meeting", "schedule", "calendar", "book", "appointment"]):
            # Extract meeting title from request
            title = "Team Meeting"
            for phrase in ["schedule a", "book a", "set up a", "arrange a", "create a"]:
                if phrase in req:
                    after = req.split(phrase)[-1].strip()
                    # Take first 4 words as title
                    words = after.split()[:4]
                    candidate = " ".join(words).title()
                    if len(candidate) > 3:
                        title = candidate
                    break

            if any(kw in req for kw in ["check", "available", "free", "busy"]):
                steps.append({"tool": "calendar", "action": "check_availability",
                              "parameters": {"date": target_date, "start_time": start_time,
                                             "duration_minutes": 60}, "depends_on": []})
            elif any(kw in req for kw in ["today's", "today", "show", "list", "what"]):
                steps.append({"tool": "calendar", "action": "summarize_day",
                              "parameters": {"date": target_date}, "depends_on": []})
            else:
                steps.append({"tool": "calendar", "action": "check_availability",
                              "parameters": {"date": target_date, "start_time": start_time,
                                             "duration_minutes": 60}, "depends_on": []})
                steps.append({"tool": "calendar", "action": "schedule_meeting",
                              "parameters": {"title": title, "date": target_date,
                                             "start_time": start_time, "duration_minutes": 60,
                                             "attendees": ["team@example.com"],
                                             "location": "Virtual"},
                              "depends_on": []})

        # ── Document branch ───────────────────────────────────────────────────
        if any(kw in req for kw in ["document", "report", "pdf", "file", "summarize", "summary"]):
            if not any(kw in req for kw in ["email", "meeting"]):  # avoid double-adding
                steps.append({"tool": "document", "action": "process_document",
                               "parameters": {"file_path": "./data/sample.pdf"},
                               "depends_on": []})

        # ── Cross-tool: email + calendar ──────────────────────────────────────
        if (any(kw in req for kw in ["email", "mail"]) and
                any(kw in req for kw in ["meeting", "calendar", "schedule"])):
            # Already have both sets of steps above
            pass

        # ── Default fallback ──────────────────────────────────────────────────
        if not steps:
            steps.append({"tool": "email", "action": "read_emails",
                           "parameters": {"limit": 5}, "depends_on": []})

        return steps

    # ── Public API ────────────────────────────────────────────────────────────

    def plan(self, user_request: str, context: str = "") -> TaskPlan:  # noqa: E501
        """
        Create a TaskPlan for the given user request.

        Args:
            user_request: Natural language request
            context:      Optional context from memory

        Returns:
            TaskPlan with ordered AgentSteps
        """
        logger.info(f"Planning: '{user_request[:80]}'")
        raw_steps = self._plan_with_llm(user_request, context)

        steps: List[AgentStep] = []
        for raw in raw_steps:
            tool = raw.get("tool", "email")
            action = raw.get("action", "read_emails")
            step = AgentStep(
                tool=ToolName(tool),
                action=action,
                parameters=raw.get("parameters", {}),
                depends_on=raw.get("depends_on", []),
                requires_confirmation=requires_confirmation(action),
            )
            steps.append(step)

        plan = TaskPlan(original_request=user_request, steps=steps)
        logger.info(f"Plan {plan.plan_id}: {len(steps)} steps")
        return plan


# Module-level singleton
planner = PlannerAgent()
