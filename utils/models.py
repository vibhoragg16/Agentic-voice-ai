"""
utils/models.py – Shared Pydantic models used across the entire application.
"""
from __future__ import annotations
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
import uuid


# ─── Enums ────────────────────────────────────────────────────────────────────

class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    AWAITING_CONFIRMATION = "awaiting_confirmation"
    COMPLETED = "completed"
    FAILED = "failed"

class Priority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"

class ToolName(str, Enum):
    EMAIL = "email"
    CALENDAR = "calendar"
    DOCUMENT = "document"
    SEARCH = "search"

class UserRole(str, Enum):
    ADMIN = "admin"
    MANAGER = "manager"
    EMPLOYEE = "employee"
    READONLY = "readonly"


# ─── Core Models ──────────────────────────────────────────────────────────────

class AgentStep(BaseModel):
    """A single step produced by the Planner Agent."""
    step_id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    tool: ToolName
    action: str
    parameters: Dict[str, Any] = Field(default_factory=dict)
    depends_on: List[str] = Field(default_factory=list)  # step_ids
    requires_confirmation: bool = False


class TaskPlan(BaseModel):
    """Full plan returned by the Planner Agent."""
    plan_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    original_request: str
    steps: List[AgentStep]
    created_at: datetime = Field(default_factory=datetime.utcnow)


class StepResult(BaseModel):
    """Result of executing a single AgentStep."""
    step_id: str
    success: bool
    output: Any
    error: Optional[str] = None
    executed_at: datetime = Field(default_factory=datetime.utcnow)


class TaskResult(BaseModel):
    """Aggregated result of an entire TaskPlan execution."""
    plan_id: str
    status: TaskStatus
    step_results: List[StepResult] = Field(default_factory=list)
    final_response: str = ""
    completed_at: Optional[datetime] = None


class ConversationTurn(BaseModel):
    """A single user→assistant exchange stored in memory."""
    turn_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_message: str
    assistant_response: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    task_plan_id: Optional[str] = None


# ─── API Schemas ──────────────────────────────────────────────────────────────

class VoiceInputResponse(BaseModel):
    """Response after /voice-input processes audio."""
    transcript: str
    task_id: str
    status: TaskStatus


class ProcessTaskResponse(BaseModel):
    """Response from /process-task."""
    task_id: str
    plan: TaskPlan
    status: TaskStatus
    requires_confirmation: bool = False
    pending_confirmations: List[str] = Field(default_factory=list)


class GetResponseResponse(BaseModel):
    """Response from /get-response."""
    task_id: str
    status: TaskStatus
    text_response: str
    audio_url: Optional[str] = None
    step_results: List[StepResult] = Field(default_factory=list)


class ConfirmActionRequest(BaseModel):
    task_id: str
    step_id: str
    confirmed: bool
