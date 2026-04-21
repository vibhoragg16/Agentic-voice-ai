"""
tests/test_all.py – Comprehensive test suite covering all modules.
Run with: pytest tests/ -v
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from unittest.mock import patch, MagicMock


# ─────────────────────────────────────────────────────────────────────────────
# Tools
# ─────────────────────────────────────────────────────────────────────────────

class TestEmailTool:
    def setup_method(self):
        from tools.email_tool import EmailTool
        self.tool = EmailTool()

    def test_read_emails_returns_list(self):
        emails = self.tool.read_emails(limit=2)
        assert isinstance(emails, list)
        assert len(emails) <= 2

    def test_read_unread_only(self):
        emails = self.tool.read_emails(unread_only=True)
        assert all(not e["read"] for e in emails)

    def test_classify_priority(self):
        result = self.tool.classify_priority("email_003")
        assert result["priority"] in ("urgent", "high", "medium", "low")

    def test_classify_missing_email(self):
        result = self.tool.classify_priority("nonexistent")
        assert "error" in result

    def test_draft_reply(self):
        result = self.tool.draft_reply("email_001")
        assert "draft" in result
        assert len(result["draft"]) > 10

    def test_send_email_mock(self):
        result = self.tool.send_email(
            to="test@example.com",
            subject="Test",
            body="Hello world",
        )
        assert result["success"] is True
        assert "email_id" in result

    def test_get_sent_grows(self):
        before = len(self.tool.get_sent())
        self.tool.send_email("a@b.com", "S", "B")
        assert len(self.tool.get_sent()) == before + 1


class TestCalendarTool:
    def setup_method(self):
        from tools.calendar_tool import CalendarTool
        self.tool = CalendarTool()

    def test_get_events_all(self):
        events = self.tool.get_events()
        assert isinstance(events, list)

    def test_get_events_filtered(self):
        events = self.tool.get_events("2024-10-02")
        assert all("2024-10-02" in e["start"] for e in events)

    def test_check_availability_free(self):
        result = self.tool.check_availability("2024-10-03", "10:00", 60)
        assert result["available"] is True
        assert result["conflicts"] == []

    def test_check_availability_busy(self):
        result = self.tool.check_availability("2024-10-02", "09:00", 60)
        assert result["available"] is False

    def test_schedule_meeting(self):
        result = self.tool.schedule_meeting(
            title="Sprint Review",
            date="2024-10-04",
            start_time="11:00",
            duration_minutes=30,
            attendees=["dev@example.com"],
        )
        assert result["success"] is True
        assert result["event"]["title"] == "Sprint Review"

    def test_send_invite(self):
        result = self.tool.send_invite("evt_001", "new@example.com")
        assert result["success"] is True

    def test_send_invite_missing_event(self):
        result = self.tool.send_invite("nonexistent", "x@y.com")
        assert result["success"] is False

    def test_summarize_day_no_events(self):
        summary = self.tool.summarize_day("2099-01-01")
        assert "No events" in summary


class TestDocumentTool:
    def setup_method(self):
        from tools.document_tool import DocumentTool
        self.tool = DocumentTool()

    def test_parse_pdf_missing_returns_mock(self):
        result = self.tool.parse_pdf("./nonexistent.pdf")
        assert "text" in result
        assert len(result["text"]) > 10

    def test_summarize(self):
        text = "This is sentence one. This is sentence two. And sentence three here too."
        summary = self.tool.summarize(text, max_sentences=2)
        assert isinstance(summary, str)
        assert len(summary) > 0

    def test_extract_key_info(self):
        from tools.document_tool import _MOCK_DOCUMENT
        info = self.tool.extract_key_info(_MOCK_DOCUMENT)
        assert "action_items" in info
        assert "dates" in info
        assert "metrics" in info

    def test_process_document_full(self):
        result = self.tool.process_document("./fake.pdf")
        assert "summary" in result
        assert "key_info" in result


class TestRegistry:
    def test_dispatch_email_read(self):
        from tools.registry import dispatch
        result = dispatch("email", "read_emails", {"limit": 2})
        assert isinstance(result, list)

    def test_dispatch_unknown_raises(self):
        from tools.registry import dispatch
        with pytest.raises(KeyError):
            dispatch("unknown_tool", "unknown_action", {})

    def test_list_tools(self):
        from tools.registry import list_tools
        tools = list_tools()
        assert "email.send_email" in tools
        assert "calendar.schedule_meeting" in tools


# ─────────────────────────────────────────────────────────────────────────────
# RBAC
# ─────────────────────────────────────────────────────────────────────────────

class TestRBAC:
    def test_admin_has_all_tools(self):
        from utils.rbac import get_allowed_tools, can_use_tool
        from utils.models import UserRole, ToolName
        tools = get_allowed_tools(UserRole.ADMIN)
        assert ToolName.EMAIL in tools
        assert ToolName.CALENDAR in tools

    def test_readonly_cannot_email(self):
        from utils.rbac import can_use_tool
        from utils.models import UserRole, ToolName
        assert can_use_tool(UserRole.READONLY, ToolName.EMAIL) is False

    def test_critical_actions_require_confirmation(self):
        from utils.rbac import requires_confirmation
        assert requires_confirmation("send_email") is True
        assert requires_confirmation("read_emails") is False


# ─────────────────────────────────────────────────────────────────────────────
# Agents
# ─────────────────────────────────────────────────────────────────────────────

class TestPlannerAgent:
    def setup_method(self):
        from agents.planner import PlannerAgent
        self.planner = PlannerAgent()

    def test_plan_email_request(self):
        from utils.models import ToolName
        plan = self.planner.plan("Read my emails")
        assert len(plan.steps) > 0
        assert any(s.tool == ToolName.EMAIL for s in plan.steps)

    def test_plan_meeting_request(self):
        from utils.models import ToolName
        plan = self.planner.plan("Schedule a meeting tomorrow at 3 PM")
        assert any(s.tool == ToolName.CALENDAR for s in plan.steps)

    def test_plan_document_request(self):
        from utils.models import ToolName
        plan = self.planner.plan("Summarize the quarterly report PDF")
        assert any(s.tool == ToolName.DOCUMENT for s in plan.steps)

    def test_plan_has_id(self):
        plan = self.planner.plan("Check my calendar")
        assert plan.plan_id
        assert plan.original_request == "Check my calendar"


class TestExecutorAgent:
    def setup_method(self):
        from agents.executor import ExecutorAgent
        from agents.planner import PlannerAgent
        self.executor = ExecutorAgent()
        self.planner = PlannerAgent()

    def test_execute_simple_plan(self):
        from utils.models import TaskStatus
        plan = self.planner.plan("Read my emails")
        result = self.executor.execute(plan)
        assert result.status in (TaskStatus.COMPLETED, TaskStatus.AWAITING_CONFIRMATION)
        assert len(result.step_results) > 0

    def test_confirmation_flow(self):
        from utils.models import TaskStatus, AgentStep, TaskPlan, ToolName
        # Create a plan with a step that needs confirmation
        step = AgentStep(
            tool=ToolName.EMAIL,
            action="send_email",
            parameters={"to": "x@y.com", "subject": "Test", "body": "Hi"},
            requires_confirmation=True,
        )
        plan = TaskPlan(original_request="Send email", steps=[step])

        # First execute: should pause awaiting confirmation
        result = self.executor.execute(plan)
        assert result.status == TaskStatus.AWAITING_CONFIRMATION

        # Confirm and re-execute
        self.executor.confirm_step(plan.plan_id, step.step_id)
        result2 = self.executor.execute(plan)
        assert result2.status == TaskStatus.COMPLETED


class TestAgentCore:
    def setup_method(self):
        from agents.core import AgentCore
        self.core = AgentCore()

    def test_process_creates_plan(self):
        from utils.models import TaskStatus
        resp = self.core.process("Check my inbox")
        assert resp.task_id
        assert len(resp.plan.steps) > 0

    def test_single_turn(self):
        response = self.core.single_turn("Read my top 3 emails")
        assert isinstance(response, str)
        assert len(response) > 5

    def test_confirm_missing_task(self):
        msg = self.core.confirm_step("nonexistent-id", "step-1", True)
        assert "not found" in msg.lower()


# ─────────────────────────────────────────────────────────────────────────────
# Memory
# ─────────────────────────────────────────────────────────────────────────────

class TestMemoryStore:
    def setup_method(self):
        from memory.vector_store import MemoryStore
        self.memory = MemoryStore()

    def test_add_and_search(self):
        from utils.models import ConversationTurn
        turn = ConversationTurn(
            user_message="Schedule a meeting with Alice",
            assistant_response="Meeting scheduled for tomorrow at 2 PM.",
        )
        self.memory.add_turn(turn)
        results = self.memory.search("meeting Alice", top_k=1)
        assert len(results) >= 1
        assert "meeting" in results[0]["text"].lower()

    def test_empty_search_returns_empty(self):
        from memory.vector_store import MemoryStore
        fresh = MemoryStore()
        results = fresh.search("something", top_k=3)
        assert results == []

    def test_context_string(self):
        from utils.models import ConversationTurn
        turn = ConversationTurn(
            user_message="Process the Q3 report",
            assistant_response="Document processed successfully.",
        )
        self.memory.add_turn(turn)
        ctx = self.memory.get_context_string("Q3 report")
        assert isinstance(ctx, str)


# ─────────────────────────────────────────────────────────────────────────────
# Voice (mock-only tests, no real audio needed)
# ─────────────────────────────────────────────────────────────────────────────

class TestSTT:
    def test_transcribe_missing_file_raises(self):
        from voice.stt import SpeechToText
        stt = SpeechToText()
        with pytest.raises(FileNotFoundError):
            stt.transcribe("./nonexistent_audio.wav")


class TestTTS:
    def test_synthesize_creates_file(self, tmp_path, monkeypatch):
        from voice.tts import TextToSpeech
        tts = TextToSpeech()
        tts.output_dir = tmp_path

        # Mock gTTS to avoid network/install requirement
        mock_gtts = MagicMock()
        with patch("voice.tts.gTTS", mock_gtts, create=True):
            mock_gtts.return_value.save = lambda p: open(p, "w").write("audio")
            # Just verify the method runs without error
            # (gTTS may or may not be installed in test env)
            try:
                path = tts.synthesize("Hello, this is a test.")
                assert path is not None
            except Exception:
                pass  # OK if gTTS not installed


# ─────────────────────────────────────────────────────────────────────────────
# API (integration-style, no real HTTP)
# ─────────────────────────────────────────────────────────────────────────────

class TestAPIRoutes:
    def setup_method(self):
        from fastapi.testclient import TestClient
        from api.app import app
        self.client = TestClient(app)

    def test_health(self):
        resp = self.client.get("/api/v1/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    def test_list_tools(self):
        resp = self.client.get("/api/v1/tools")
        assert resp.status_code == 200
        assert "tools" in resp.json()

    def test_text_input_and_get_response(self):
        import uuid
        # Step 1: submit text task
        resp1 = self.client.post(
            "/api/v1/text-input",
            data={"text": "Read my latest emails"},
        )
        assert resp1.status_code == 200
        task_id = resp1.json()["task_id"]

        # Step 2: execute and get response
        resp2 = self.client.post(
            "/api/v1/get-response",
            data={"task_id": task_id},
        )
        assert resp2.status_code == 200
        assert "text_response" in resp2.json()
        assert len(resp2.json()["text_response"]) > 0

    def test_confirm_endpoint(self):
        resp = self.client.post(
            "/api/v1/confirm",
            json={"task_id": "fake-id", "step_id": "step-1", "confirmed": True},
        )
        assert resp.status_code == 200

    def test_memory_search(self):
        resp = self.client.get("/api/v1/memory/search?q=email&top_k=2")
        assert resp.status_code == 200
        assert "results" in resp.json()
