"""
utils/rbac.py – Role-Based Access Control (simulation for enterprise features).
Maps roles to allowed tools and actions.
"""
from typing import Set
from utils.models import UserRole, ToolName


# Permissions: role → set of allowed tool names
_ROLE_PERMISSIONS: dict[UserRole, Set[ToolName]] = {
    UserRole.ADMIN:    {ToolName.EMAIL, ToolName.CALENDAR, ToolName.DOCUMENT, ToolName.SEARCH},
    UserRole.MANAGER:  {ToolName.EMAIL, ToolName.CALENDAR, ToolName.DOCUMENT, ToolName.SEARCH},
    UserRole.EMPLOYEE: {ToolName.EMAIL, ToolName.CALENDAR, ToolName.DOCUMENT},
    UserRole.READONLY: {ToolName.DOCUMENT, ToolName.SEARCH},
}

# Actions that always require human confirmation regardless of role
_CRITICAL_ACTIONS: Set[str] = {
    "send_email",
    "schedule_meeting",
    "send_invite",
    "delete_event",
}


def can_use_tool(role: UserRole, tool: ToolName) -> bool:
    """Return True if the role is allowed to use the given tool."""
    return tool in _ROLE_PERMISSIONS.get(role, set())


def requires_confirmation(action: str) -> bool:
    """Return True if the action must be confirmed before execution."""
    return action in _CRITICAL_ACTIONS


def get_allowed_tools(role: UserRole) -> Set[ToolName]:
    """Return the full set of tools accessible to a role."""
    return _ROLE_PERMISSIONS.get(role, set())
