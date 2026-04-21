"""
tools/registry.py – Central registry mapping tool names + actions to callables.
The Executor Agent uses this to dispatch tool calls without hard-coding logic.
"""
from __future__ import annotations
from typing import Any, Callable, Dict
from tools.email_tool import email_tool
from tools.calendar_tool import calendar_tool
from tools.document_tool import document_tool
from utils.logger import get_logger

logger = get_logger("tools.registry")

# Format: (tool_name, action) → callable
_REGISTRY: Dict[tuple[str, str], Callable[..., Any]] = {
    # Email
    ("email", "read_emails"):      email_tool.read_emails,
    ("email", "get_email"):        email_tool.get_email,
    ("email", "classify_priority"): email_tool.classify_priority,
    ("email", "draft_reply"):      email_tool.draft_reply,
    ("email", "send_email"):       email_tool.send_email,
    # Calendar
    ("calendar", "get_events"):         calendar_tool.get_events,
    ("calendar", "check_availability"): calendar_tool.check_availability,
    ("calendar", "schedule_meeting"):   calendar_tool.schedule_meeting,
    ("calendar", "send_invite"):        calendar_tool.send_invite,
    ("calendar", "summarize_day"):      calendar_tool.summarize_day,
    # Document
    ("document", "parse_pdf"):       document_tool.parse_pdf,
    ("document", "summarize"):       document_tool.summarize,
    ("document", "extract_key_info"): document_tool.extract_key_info,
    ("document", "process_document"): document_tool.process_document,
}


def dispatch(tool: str, action: str, parameters: Dict[str, Any]) -> Any:
    """
    Look up and call the registered function for (tool, action).

    Args:
        tool:       Tool name (e.g. 'email')
        action:     Action name (e.g. 'send_email')
        parameters: Keyword arguments to pass to the callable

    Returns:
        The callable's return value

    Raises:
        KeyError if (tool, action) is not registered
    """
    key = (tool, action)
    fn = _REGISTRY.get(key)
    if fn is None:
        available = [f"{t}.{a}" for t, a in _REGISTRY]
        raise KeyError(
            f"Unknown tool/action: {tool}.{action}. "
            f"Available: {available}"
        )
    logger.info(f"Dispatching: {tool}.{action}({list(parameters.keys())})")
    return fn(**parameters)


def list_tools() -> list[str]:
    """Return list of all registered 'tool.action' strings."""
    return [f"{t}.{a}" for t, a in _REGISTRY]
