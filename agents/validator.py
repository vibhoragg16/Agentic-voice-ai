"""
agents/validator.py – Validator Agent.
Reviews TaskResult and produces a coherent natural-language response.

Provider priority: Groq (free) → OpenAI (paid) → rule-based (no key)
"""
from __future__ import annotations
import json
from config import settings
from utils.logger import get_logger
from utils.models import TaskPlan, TaskResult, TaskStatus

logger = get_logger("agents.validator")

_SYSTEM_PROMPT = """You are a helpful enterprise AI assistant.
A set of automated tasks has just been executed. Summarise what happened in 2-4 clear, friendly sentences.
Focus on: what was done, key results (numbers, names, titles), and any next steps.
Write in plain English. Do not mention tool names, step IDs, or technical details."""


class ValidatorAgent:
    """Validates execution results and synthesises a user-facing response."""

    def __init__(self) -> None:
        self._client = None

    def _get_client(self):
        if self._client is not None:
            return self._client

        if not settings.use_llm:
            self._client = "mock"
            return self._client

        try:
            from openai import OpenAI
            if settings.llm_provider == "groq":
                self._client = OpenAI(
                    api_key=settings.groq_api_key,
                    base_url="https://api.groq.com/openai/v1",
                )
            else:
                self._client = OpenAI(api_key=settings.openai_api_key)
        except ImportError:
            self._client = "mock"
        return self._client

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _results_summary(self, result: TaskResult) -> str:
        lines = [f"Overall status: {result.status}"]
        for sr in result.step_results:
            status = "SUCCESS" if sr.success else f"FAILED: {sr.error}"
            out = ""
            if sr.output:
                if isinstance(sr.output, (dict, list)):
                    out = json.dumps(sr.output, default=str)[:300]
                else:
                    out = str(sr.output)[:300]
            lines.append(f"  Step {sr.step_id}: {status} | output: {out}")
        return "\n".join(lines)

    # ── LLM response ──────────────────────────────────────────────────────────

    def _llm_response(self, plan: TaskPlan, result: TaskResult) -> str:
        client = self._get_client()
        if client == "mock":
            return self._rule_based_response(plan, result)

        summary = self._results_summary(result)
        user_msg = (
            f"User request: \"{plan.original_request}\"\n\n"
            f"Execution results:\n{summary}"
        )
        try:
            response = client.chat.completions.create(
                model=settings.active_llm_model,
                messages=[
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user",   "content": user_msg},
                ],
                temperature=0.4,
                max_tokens=300,
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            logger.warning(f"LLM validation failed ({e}); using rule-based")
            return self._rule_based_response(plan, result)

    # ── Rule-based fallback ───────────────────────────────────────────────────

    def _rule_based_response(self, plan: TaskPlan, result: TaskResult) -> str:
        """Rich template response that extracts real values from step outputs."""
        successes = [r for r in result.step_results if r.success]
        failures  = [r for r in result.step_results if not r.success and
                     not (r.error and "confirmation" in (r.error or ""))]
        pending   = [r for r in result.step_results
                     if r.error and "confirmation" in (r.error or "")]

        parts: list[str] = []

        if pending:
            parts.append(
                f"I've prepared {len(pending)} action(s) that need your approval before proceeding. "
                "Please click Approve or Deny for each step below."
            )

        for sr in successes:
            out = sr.output
            if isinstance(out, list):
                # Email list result
                parts.append(
                    f"Found {len(out)} email(s). "
                    + (f"Most recent: \"{out[0].get('subject','?')}\" from {out[0].get('from','?')}."
                       if out else "")
                )
            elif isinstance(out, dict):
                # Calendar availability
                if "available" in out:
                    if out["available"]:
                        parts.append(
                            f"The time slot on {out.get('date')} at {out.get('start_time')} "
                            f"is free for {out.get('duration_minutes')} minutes."
                        )
                    else:
                        parts.append(
                            f"There's a conflict at {out.get('start_time')} on {out.get('date')}: "
                            f"{', '.join(out.get('conflicts', []))}. You may want to choose a different time."
                        )
                # Meeting scheduled
                elif "event" in out:
                    ev = out["event"]
                    parts.append(
                        f"Meeting \"{ev.get('title')}\" scheduled on {ev.get('start','?')[:10]} "
                        f"at {ev.get('start','?')[11:16]}."
                    )
                # Email sent
                elif out.get("success") and "email_id" in out:
                    parts.append(f"Email sent to {out.get('to')} (ID: {out.get('email_id')}).")
                # Invite sent
                elif "invite_sent_to" in out:
                    parts.append(f"Invite sent to {out['invite_sent_to']} for \"{out.get('event_title')}\".")
                # Priority classification
                elif "priority" in out:
                    parts.append(
                        f"Email \"{out.get('subject','?')}\" classified as {out.get('priority').upper()} priority."
                    )
                # Document result
                elif "summary" in out:
                    parts.append(f"Document processed. Summary: {out['summary'][:200]}")
                # Draft reply
                elif "draft" in out:
                    parts.append(f"Draft reply prepared for email to {out.get('to','?')}.")
            elif isinstance(out, str):
                # Calendar summarize_day returns a string
                parts.append(out)

        if failures:
            parts.append(f"{len(failures)} step(s) failed. Please check your configuration.")

        if result.status == TaskStatus.COMPLETED and not parts:
            parts.append("All tasks completed successfully.")

        return " ".join(parts) or "Task processing complete."

    # ── Public API ────────────────────────────────────────────────────────────

    def validate_and_respond(self, plan: TaskPlan, result: TaskResult) -> str:
        logger.info(f"Validating plan {plan.plan_id} (status={result.status})")
        response = self._llm_response(plan, result)
        result.final_response = response
        logger.info(f"Response: '{response[:100]}'")
        return response


# Module-level singleton
validator = ValidatorAgent()
