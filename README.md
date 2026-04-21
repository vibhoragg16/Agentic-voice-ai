# 🎙️ Voice-Enabled Agentic AI for Enterprise Workflow Automation

A production-ready, modular multi-agent AI system that accepts **voice or text input**, decomposes tasks using an LLM, executes them through enterprise tools (email, calendar, documents), and returns a **voice response**.

---

## Architecture

```
User Voice/Text
      │
      ▼
┌─────────────────────────────────────────────────────────┐
│                    FastAPI Backend                       │
│  /voice-input  /process-task  /get-response  /confirm   │
└──────────────────────┬──────────────────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────────────────┐
│                    Agent Core                            │
│                                                          │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────┐  │
│  │   Planner   │→ │  Executor   │→ │   Validator     │  │
│  │   Agent     │  │   Agent     │  │   Agent         │  │
│  └─────────────┘  └─────────────┘  └─────────────────┘  │
└──────────────────────┬───────────────────────────────────┘
                       │
          ┌────────────┼────────────┐
          ▼            ▼            ▼
    ┌──────────┐ ┌──────────┐ ┌──────────┐
    │  Email   │ │ Calendar │ │ Document │
    │  Tool    │ │  Tool    │ │  Tool    │
    └──────────┘ └──────────┘ └──────────┘
          │
          ▼
    ┌──────────┐   ┌───────────┐
    │  Memory  │   │   Voice   │
    │  (FAISS) │   │ STT / TTS │
    └──────────┘   └───────────┘
```

---

## Project Structure

```
agentic_voice_ai/
├── voice/
│   ├── stt.py          # Whisper speech-to-text
│   ├── tts.py          # gTTS / ElevenLabs text-to-speech
│   └── pipeline.py     # End-to-end voice pipeline
├── agents/
│   ├── core.py         # Orchestrator (Planner → Executor → Validator)
│   ├── planner.py      # LLM-based task decomposition
│   ├── executor.py     # Tool execution with retry + confirmation
│   └── validator.py    # Result validation + NL response generation
├── tools/
│   ├── email_tool.py   # Email read / classify / draft / send
│   ├── calendar_tool.py# Availability / schedule / invite
│   ├── document_tool.py# PDF parse / summarise / extract
│   └── registry.py     # Central tool dispatcher
├── memory/
│   └── vector_store.py # FAISS / ChromaDB conversation memory
├── api/
│   ├── app.py          # FastAPI application factory
│   └── routes.py       # All API endpoints
├── utils/
│   ├── models.py       # Shared Pydantic data models
│   ├── rbac.py         # Role-based access control
│   └── logger.py       # Loguru logging setup
├── frontend/
│   └── App.jsx         # React dashboard (optional)
├── tests/
│   └── test_all.py     # Full test suite
├── main.py             # Entry point
├── config.py           # Centralised settings
├── requirements.txt
└── .env.example
```

---

## Quick Start

### 1. Clone & Setup

```bash
git clone <repo-url>
cd agentic_voice_ai

python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure

```bash
cp .env.example .env
# Edit .env and set your OPENAI_API_KEY
```

Minimum required `.env`:
```
OPENAI_API_KEY=sk-your-key-here
```

Everything else has sensible defaults (mock providers, gTTS, FAISS).

### 3. Run

```bash
python main.py
# or
uvicorn main:app --reload
```

API available at: **http://localhost:8000**  
Interactive docs: **http://localhost:8000/docs**

---

## API Endpoints

| Method | Endpoint              | Description                                         |
|--------|-----------------------|-----------------------------------------------------|
| GET    | `/api/v1/health`      | Liveness check                                      |
| POST   | `/api/v1/voice-input` | Upload audio → transcript + task_id                 |
| POST   | `/api/v1/text-input`  | Submit text directly → plan + task_id               |
| POST   | `/api/v1/process-task`| Plan a task (voice task_id + optional text)         |
| POST   | `/api/v1/get-response`| Execute plan → text response + audio URL            |
| POST   | `/api/v1/confirm`     | Approve or deny a critical step                     |
| GET    | `/api/v1/tools`       | List all registered tools                           |
| GET    | `/api/v1/memory/search?q=...` | Search conversation memory             |
| GET    | `/api/v1/audio/{file}`| Serve generated TTS audio                           |

---

## Usage Examples

### Via curl

```bash
# Text input
curl -X POST http://localhost:8000/api/v1/text-input \
  -F "text=Read my unread emails and summarise them"

# Returns: { "task_id": "abc123", "plan": {...} }

curl -X POST http://localhost:8000/api/v1/get-response \
  -F "task_id=abc123"

# Returns: { "text_response": "...", "audio_url": "/audio/tts_xxx.mp3", ... }
```

```bash
# Voice input
curl -X POST http://localhost:8000/api/v1/voice-input \
  -F "audio=@recording.wav"
```

```bash
# Confirm a critical action
curl -X POST http://localhost:8000/api/v1/confirm \
  -H "Content-Type: application/json" \
  -d '{"task_id":"abc123","step_id":"step_001","confirmed":true}'
```

### Via Python

```python
import httpx

# Single-turn (programmatic)
from agents.core import agent_core

response = agent_core.single_turn("Schedule a team meeting tomorrow at 3 PM")
print(response)
```

---

## Voice Providers

### Speech-to-Text
| Provider | Config | Notes |
|----------|--------|-------|
| Whisper (default) | `WHISPER_MODEL=base` | Local, free, runs offline |
| Larger models | `WHISPER_MODEL=medium` | More accurate, slower |

### Text-to-Speech
| Provider | Config | Notes |
|----------|--------|-------|
| gTTS (default) | `TTS_PROVIDER=gtts` | Free, requires internet |
| ElevenLabs | `TTS_PROVIDER=elevenlabs` | High quality, paid API |

---

## Tool Providers

### Email
```
EMAIL_PROVIDER=mock    # In-memory mock (default)
EMAIL_PROVIDER=smtp    # Real SMTP (configure SMTP_HOST, etc.)
```

### Calendar
```
CALENDAR_PROVIDER=mock    # In-memory mock (default)
CALENDAR_PROVIDER=google  # Google Calendar API
```

---

## Memory Backends

```
VECTOR_STORE=faiss    # Local FAISS index (default)
VECTOR_STORE=chroma   # ChromaDB with persistence
```

---

## Running Tests

```bash
pytest tests/ -v

# With coverage
pip install pytest-cov
pytest tests/ -v --cov=. --cov-report=term-missing
```

---

## Frontend Dashboard (Optional)

The React dashboard in `frontend/App.jsx` connects to the API.

```bash
# Using Vite
npm create vite@latest dashboard -- --template react
cp frontend/App.jsx dashboard/src/App.jsx
cd dashboard && npm install && npm run dev
```

Features:
- Voice recording with mic button
- Text input mode
- Real-time plan & step visualization
- Human-in-the-loop confirmation UI
- Conversation history
- Audio playback for TTS responses

---

## Enterprise Features

| Feature | Implementation |
|---------|---------------|
| **RBAC** | `utils/rbac.py` – role → allowed tools mapping |
| **Audit Logging** | `utils/logger.py` – `AUDIT` tag written to `logs/audit.log` |
| **Human-in-the-Loop** | `agents/executor.py` – pauses on critical actions |
| **Retry Logic** | `tenacity` – 3 attempts with exponential backoff |
| **Error Handling** | Per-step results + global FastAPI exception handler |

---

## Extending the System

### Add a new tool

1. Create `tools/my_tool.py` with a class + module singleton
2. Register in `tools/registry.py`:
   ```python
   ("my_tool", "my_action"): my_tool.my_action,
   ```
3. Add to `ToolName` enum in `utils/models.py`
4. Update RBAC in `utils/rbac.py` if needed

### Swap to a different LLM

Update `.env`:
```
LLM_MODEL=gpt-4o
```
Or modify `agents/planner.py` and `agents/validator.py` to use any LangChain-compatible provider.

---

## Logs

```
logs/
├── app.log      # Full debug log (rotated at 10 MB)
└── audit.log    # Critical actions only (retained 90 days)
```

---

## License

MIT
