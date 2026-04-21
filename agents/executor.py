"""
agents/executor.py – Executor Agent.
Iterates through a TaskPlan, dispatches tool calls, handles retries,
and pauses for human confirmation on critical actions.
"""
from __future__ import annotations
from datetime import datetime
from typing import Dict, List, Set
from tenacity import retry, stop_after_attempt, wait_exponential
from tools.registry import dispatch
from utils.logger import get_logger
from utils.models import AgentStep, StepResult, TaskPlan, TaskResult, TaskStatus

logger = get_logger("agents.executor")


class ExecutorAgent:
    """
    Executes a TaskPlan step by step.
    - Respects dependency ordering (depends_on)
    - Retries transient failures (up to 3 attempts)
    - Pauses execution when human confirmation is required
    """

    def __init__(self) -> None:
        # Tracks steps that are awaiting user confirmation
        self._pending_confirmations: Dict[str, Set[str]] = {}  # plan_id → {step_ids}
        self._confirmed: Dict[str, Set[str]] = {}              # plan_id → {step_ids}
        self._denied: Dict[str, Set[str]] = {}

    # ── Confirmation management ───────────────────────────────────────────────

    def request_confirmation(self, plan_id: str, step_id: str) -> None:
        self._pending_confirmations.setdefault(plan_id, set()).add(step_id)

    def confirm_step(self, plan_id: str, step_id: str) -> None:
        self._pending_confirmations.get(plan_id, set()).discard(step_id)
        self._confirmed.setdefault(plan_id, set()).add(step_id)
        logger.warning(f"AUDIT – Step confirmed: plan={plan_id}, step={step_id}")

    def deny_step(self, plan_id: str, step_id: str) -> None:
        self._pending_confirmations.get(plan_id, set()).discard(step_id)
        self._denied.setdefault(plan_id, set()).add(step_id)
        logger.warning(f"AUDIT – Step denied: plan={plan_id}, step={step_id}")

    def is_confirmed(self, plan_id: str, step_id: str) -> bool:
        return step_id in self._confirmed.get(plan_id, set())

    def is_denied(self, plan_id: str, step_id: str) -> bool:
        return step_id in self._denied.get(plan_id, set())

    def get_pending(self, plan_id: str) -> Set[str]:
        return self._pending_confirmations.get(plan_id, set())

    # ── Step execution ────────────────────────────────────────────────────────

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=4))
    def _execute_step(self, step: AgentStep) -> StepResult:
        """Execute a single step with retry logic."""
        logger.info(f"Executing step {step.step_id}: {step.tool}.{step.action}")
        try:
            output = dispatch(step.tool, step.action, step.parameters)
            logger.info(f"Step {step.step_id} succeeded")
            return StepResult(step_id=step.step_id, success=True, output=output)
        except Exception as e:
            logger.error(f"Step {step.step_id} failed: {e}")
            raise  # Let tenacity handle retries

    # ── Plan execution ────────────────────────────────────────────────────────

    def execute(self, plan: TaskPlan) -> TaskResult:
        """
        Execute all steps in a TaskPlan.

        Steps that require_confirmation and have not been confirmed yet
        are skipped and added to pending_confirmations.

        Args:
            plan: TaskPlan from the Planner Agent

        Returns:
            TaskResult with status and per-step results
        """
        result = TaskResult(
            plan_id=plan.plan_id,
            status=TaskStatus.RUNNING,
            step_results=[],
        )

        completed_step_ids: Set[str] = set()

        for step in plan.steps:
            # ── Dependency check ──────────────────────────────────────────
            if step.depends_on:
                unmet = [d for d in step.depends_on if d not in completed_step_ids]
                if unmet:
                    logger.warning(f"Step {step.step_id} skipped – unmet deps: {unmet}")
                    result.step_results.append(
                        StepResult(step_id=step.step_id, success=False,
                                   output=None, error=f"Unmet dependencies: {unmet}")
                    )
                    continue

            # ── Confirmation check ────────────────────────────────────────
            if step.requires_confirmation:
                if self.is_denied(plan.plan_id, step.step_id):
                    result.step_results.append(
                        StepResult(step_id=step.step_id, success=False,
                                   output=None, error="Step denied by user")
                    )
                    continue
                if not self.is_confirmed(plan.plan_id, step.step_id):
                    self.request_confirmation(plan.plan_id, step.step_id)
                    logger.info(f"Step {step.step_id} awaiting confirmation")
                    result.status = TaskStatus.AWAITING_CONFIRMATION
                    result.step_results.append(
                        StepResult(step_id=step.step_id, success=False,
                                   output=None,
                                   error="Awaiting human confirmation")
                    )
                    continue

            # ── Execute ───────────────────────────────────────────────────
            try:
                step_result = self._execute_step(step)
                result.step_results.append(step_result)
                if step_result.success:
                    completed_step_ids.add(step.step_id)
            except Exception as e:
                result.step_results.append(
                    StepResult(step_id=step.step_id, success=False,
                               output=None, error=str(e))
                )

        # Determine final status
        if result.status != TaskStatus.AWAITING_CONFIRMATION:
            failures = [r for r in result.step_results if not r.success]
            result.status = TaskStatus.FAILED if len(failures) == len(plan.steps) else TaskStatus.COMPLETED

        result.completed_at = datetime.utcnow()
        logger.info(f"Plan {plan.plan_id} finished – status={result.status}")
        return result


# Module-level singleton
executor = ExecutorAgent()
