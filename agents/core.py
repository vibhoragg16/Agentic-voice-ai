"""
agents/core.py – Agent Core.
Orchestrates Planner → Executor → Validator pipeline.
Also manages memory retrieval and task state.
"""
from __future__ import annotations
import uuid
from datetime import datetime
from typing import Dict, Tuple
from agents.planner import planner
from agents.executor import executor
from agents.validator import validator
from memory.vector_store import memory
from utils.logger import get_logger
from utils.models import (
    ConversationTurn, TaskPlan, TaskResult, TaskStatus,
    ProcessTaskResponse, GetResponseResponse,
)

logger = get_logger("agents.core")


class AgentCore:
    """
    Central orchestrator for the multi-agent system.
    Maintains in-memory task state (plan_id → (plan, result)).
    """

    def __init__(self) -> None:
        # In production, persist this to a database
        self._tasks: Dict[str, Tuple[TaskPlan, TaskResult]] = {}

    # ── Main entry points ─────────────────────────────────────────────────────

    def process(self, user_request: str, task_id: str | None = None) -> ProcessTaskResponse:
        """
        Stage 1: Plan the task (does NOT execute yet).
        Returns the plan and flags any steps that need confirmation.

        Args:
            user_request: Natural language input from the user
            task_id:      Optional pre-assigned task ID

        Returns:
            ProcessTaskResponse with the plan and confirmation flags
        """
        task_id = task_id or str(uuid.uuid4())
        logger.info(f"Processing task {task_id}: '{user_request[:80]}'")

        # Retrieve relevant context from memory
        context = memory.get_context_string(user_request, top_k=2)

        # Plan
        plan = planner.plan(user_request, context)

        # Create initial (pending) result
        result = TaskResult(plan_id=plan.plan_id, status=TaskStatus.PENDING)
        self._tasks[task_id] = (plan, result)

        # Identify steps needing confirmation
        pending = [s.step_id for s in plan.steps if s.requires_confirmation]
        # Pre-request confirmations in executor so it tracks them
        for step_id in pending:
            executor.request_confirmation(plan.plan_id, step_id)

        return ProcessTaskResponse(
            task_id=task_id,
            plan=plan,
            status=TaskStatus.PENDING,
            requires_confirmation=bool(pending),
            pending_confirmations=pending,
        )

    def execute_task(self, task_id: str) -> GetResponseResponse:
        """
        Stage 2: Execute the plan and validate the result.

        Args:
            task_id: ID returned from process()

        Returns:
            GetResponseResponse with text and optional audio URL
        """
        if task_id not in self._tasks:
            return GetResponseResponse(
                task_id=task_id,
                status=TaskStatus.FAILED,
                text_response="Task not found. Please submit a new request.",
            )

        plan, _ = self._tasks[task_id]

        # Execute
        result = executor.execute(plan)
        self._tasks[task_id] = (plan, result)

        # Validate → natural language response
        response_text = validator.validate_and_respond(plan, result)

        # Store in memory
        turn = ConversationTurn(
            user_message=plan.original_request,
            assistant_response=response_text,
            task_plan_id=plan.plan_id,
        )
        memory.add_turn(turn)

        return GetResponseResponse(
            task_id=task_id,
            status=result.status,
            text_response=response_text,
            step_results=result.step_results,
        )

    def confirm_step(self, task_id: str, step_id: str, confirmed: bool) -> str:
        """
        Handle human-in-the-loop confirmation for a step.

        Args:
            task_id:   Task ID
            step_id:   Step ID to confirm or deny
            confirmed: True = proceed, False = deny

        Returns:
            Status message
        """
        if task_id not in self._tasks:
            return "Task not found."
        plan, _ = self._tasks[task_id]

        if confirmed:
            executor.confirm_step(plan.plan_id, step_id)
            return f"Step {step_id} confirmed. You may now execute the task."
        else:
            executor.deny_step(plan.plan_id, step_id)
            return f"Step {step_id} denied. It will be skipped during execution."

    def single_turn(self, user_request: str) -> str:
        """
        Convenience method: plan + auto-confirm + execute + respond in one call.
        Useful for non-critical requests or testing.

        Returns:
            Natural language response text
        """
        resp = self.process(user_request)
        task_id = resp.task_id
        plan, _ = self._tasks[task_id]

        # Auto-confirm all steps (no human gate in single-turn mode)
        for step in plan.steps:
            if step.requires_confirmation:
                executor.confirm_step(plan.plan_id, step.step_id)

        result_resp = self.execute_task(task_id)
        return result_resp.text_response

    def get_task(self, task_id: str) -> Tuple[TaskPlan, TaskResult] | None:
        return self._tasks.get(task_id)


# Module-level singleton
agent_core = AgentCore()
