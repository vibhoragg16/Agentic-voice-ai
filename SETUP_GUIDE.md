# 🚀 Complete Setup Guide – No Paid APIs Required

This guide gets the project running using **Groq** (free LLM) + **Whisper** (local STT) + **gTTS** (free TTS).

---

## What You Need

| Component | Tool | Cost | Needs Internet? |
|-----------|------|------|-----------------|
| LLM Brain | Groq (llama3-8b) | **Free** | Yes (API call) |
| Speech-to-Text | Whisper (local) | **Free** | No (runs on CPU) |
| Text-to-Speech | gTTS | **Free** | Yes (Google TTS) |
| Email/Calendar | Mock demo data | **Free** | No |
| Memory | In-memory search | **Free** | No |

**Only one thing to sign up for: Groq (free, takes 2 minutes)**

---

## Step 1 – Get Your Free Groq API Key

1. Open **https://console.groq.com** in your browser
2. Click **Sign Up** (use Google/GitHub login – no credit card)
3. In the dashboard, click **"API Keys"** in the left sidebar
4. Click **"Create API Key"** → give it any name → click Create
5. Copy the key – it looks like: `gsk_abc123xyz...`

> ⚠️ The key is shown only once. Copy it now.

---

## Step 2 – Install System Dependencies

### Linux (Ubuntu / Debian)
```bash
sudo apt update
sudo apt install python3 python3-pip python3-venv ffmpeg git -y
```

### macOS
```bash
# Install Homebrew first if you don't have it: https://brew.sh
brew install python ffmpeg git
```

### Windows
```powershell
# Install Python from https://python.org (tick "Add to PATH")
# Install ffmpeg from https://ffmpeg.org/download.html
# Or use Chocolatey:
choco install python ffmpeg git
```

> ffmpeg is required by Whisper for audio file decoding.

---

## Step 3 – Download and Set Up the Project

```bash
# 1. Navigate to the project folder
cd agentic_voice_ai

# 2. Create a virtual environment (keeps dependencies isolated)
python -m venv venv

# 3. Activate it
source venv/bin/activate          # Linux / Mac
# venv\Scripts\activate           # Windows (use this line instead)

# 4. Install dependencies
pip install -r requirements.txt
```

> First install takes 3–5 minutes (Whisper model files download on first run).

---

## Step 4 – Create Your .env File

```bash
# Copy the template
cp .env.example .env
```

Now open `.env` in any text editor and:

1. **Replace** `gsk_paste_your_groq_key_here` with your real Groq key
2. That's it – everything else has working defaults

Your `.env` should look like this:
```
LLM_PROVIDER=groq
GROQ_API_KEY=gsk_abc123yourkeyhere...
GROQ_MODEL=llama3-8b-8192

WHISPER_MODEL=tiny
TTS_PROVIDER=gtts
VECTOR_STORE=simple
EMAIL_PROVIDER=mock
CALENDAR_PROVIDER=mock
APP_ENV=development
LOG_LEVEL=INFO
AUDIO_OUTPUT_DIR=./data/audio
UPLOAD_DIR=./data/uploads
MAX_AUDIO_SIZE_MB=25
```

---

## Step 5 – Run the Server

```bash
python main.py
```

You should see:
```
INFO  Starting Voice Agentic AI — env=development
INFO  Uvicorn running on http://0.0.0.0:8000
```

Open your browser and go to:
- **http://localhost:8000/docs** → Interactive API (Swagger UI)
- **http://localhost:8000/api/v1/health** → Should return `{"status": "ok"}`

---

## Step 6 – Try It Out

### Option A: Swagger UI (easiest)

1. Open **http://localhost:8000/docs**
2. Click **POST /api/v1/text-input** → **Try it out**
3. Enter a request like one of these:
   ```
   Show me my unread emails
   Schedule a meeting tomorrow at 2 PM with the team
   Summarize the quarterly report
   Check my calendar for today
   ```
4. Click **Execute**
5. Copy the `task_id` from the response
6. Click **POST /api/v1/get-response** → **Try it out**
7. Paste the `task_id` → **Execute**
8. You'll get a text response + audio URL

---

### Option B: curl Commands

```bash
# Schedule a meeting
curl -X POST http://localhost:8000/api/v1/text-input \
  -F "text=Schedule a team meeting tomorrow at 3 PM"

# Returns something like: {"task_id": "abc-123", "plan": {...}}

# Get the response (use task_id from above)
curl -X POST http://localhost:8000/api/v1/get-response \
  -F "task_id=abc-123"
```

---

### Option C: Python Script

```python
import httpx

BASE = "http://localhost:8000/api/v1"

requests_to_try = [
    "Show me my unread emails",
    "Schedule a team standup tomorrow at 10 AM",
    "Summarize the quarterly report",
    "Check my availability this week",
    "Read my high priority emails",
]

for request in requests_to_try:
    # Step 1: Submit request
    r1 = httpx.post(f"{BASE}/text-input", data={"text": request})
    task_id = r1.json()["task_id"]
    
    # Step 2: Execute and get response
    r2 = httpx.post(f"{BASE}/get-response", data={"task_id": task_id})
    result = r2.json()
    
    print(f"\n📝 Request: {request}")
    print(f"🤖 Response: {result['text_response']}")
    print(f"📊 Status: {result['status']}")
    if result.get("audio_url"):
        print(f"🔊 Audio: http://localhost:8000{result['audio_url']}")
```

Save as `try_it.py` and run: `python try_it.py`

---

## What Each Request Does

| You say | What happens |
|---------|-------------|
| "Show me my emails" | Reads 5 emails from demo inbox |
| "Show unread emails" | Filters to unread emails only |
| "Summarize my emails" | Reads all emails + summarises |
| "Schedule a meeting tomorrow at 2 PM" | Checks availability → creates event |
| "Check my calendar today" | Lists today's scheduled events |
| "Am I free tomorrow at 3 PM?" | Checks that specific time slot |
| "Summarize the quarterly report" | Parses PDF → extracts summary + key info |
| "Draft a reply to email_001" | Creates a draft reply |
| "What are my high priority emails?" | Reads + classifies by priority |

---

## Voice Input (Optional)

To use actual voice, you need a microphone and the frontend dashboard.

### Quick voice test via API:

```bash
# Record a WAV file (Linux, needs arecord)
arecord -d 5 -f cd test.wav

# Or use any audio file (mp3, wav, m4a, webm)
curl -X POST http://localhost:8000/api/v1/voice-input \
  -F "audio=@test.wav"
# Returns transcript + task_id

# Then execute it
curl -X POST http://localhost:8000/api/v1/get-response \
  -F "task_id=RETURNED_TASK_ID"
```

### Run the React dashboard:

```bash
# Install Node.js from https://nodejs.org if you don't have it

npm create vite@latest dashboard -- --template react
cd dashboard
cp ../frontend/App.jsx src/App.jsx
npm install
npm run dev
# Opens at http://localhost:5173
```

---

## Human-in-the-Loop Confirmations

Actions like "send email" and "schedule meeting" require approval before executing.

When you call `/get-response`, if the response has:
```json
"status": "awaiting_confirmation"
```

You need to confirm the pending steps:

```bash
# Approve the step
curl -X POST http://localhost:8000/api/v1/confirm \
  -H "Content-Type: application/json" \
  -d '{"task_id": "YOUR_TASK_ID", "step_id": "STEP_ID", "confirmed": true}'

# Then call get-response again to complete execution
curl -X POST http://localhost:8000/api/v1/get-response \
  -F "task_id=YOUR_TASK_ID"
```

---

## Troubleshooting

### "No module named 'openai'"
```bash
pip install -r requirements.txt
```

### "ffmpeg not found" (Whisper error)
```bash
sudo apt install ffmpeg        # Linux
brew install ffmpeg            # Mac
choco install ffmpeg           # Windows
```

### Groq API errors
- Check your key starts with `gsk_`
- Verify at https://console.groq.com that the key is active
- Free tier has rate limits: ~30 requests/min, resets every minute

### Port 8000 already in use
```bash
# Change the port
uvicorn main:app --port 8001 --reload
```

### Whisper downloading model slowly
- First run downloads the tiny model (~39 MB) – normal
- Model is cached in `~/.cache/whisper/` – only downloads once

---

## Groq Free Tier Limits

| Limit | Value |
|-------|-------|
| Requests per minute | 30 |
| Tokens per minute | 14,400 |
| Tokens per day | 500,000 |
| Cost | **$0** |

For normal usage (scheduling meetings, reading emails), you'll never hit these limits.

---

## Running Tests

```bash
pytest tests/ -v
```

Expected output:
```
tests/test_all.py::TestEmailTool::test_read_emails_returns_list PASSED
tests/test_all.py::TestCalendarTool::test_schedule_meeting PASSED
...
30+ tests PASSED
```

---

## Project Structure Quick Reference

```
agentic_voice_ai/
├── .env                 ← YOUR CONFIG (create from .env.example)
├── main.py              ← Start here: python main.py
├── config.py            ← All settings in one place
├── agents/
│   ├── core.py          ← Orchestrator (start → plan → execute → respond)
│   ├── planner.py       ← Groq LLM breaks request into steps
│   ├── executor.py      ← Runs each step, handles confirmations
│   └── validator.py     ← Groq LLM writes the final response
├── tools/
│   ├── email_tool.py    ← Read/classify/draft/send emails
│   ├── calendar_tool.py ← Check/schedule/invite calendar
│   └── document_tool.py ← Parse/summarize PDFs
├── voice/
│   ├── stt.py           ← Whisper (local speech recognition)
│   └── tts.py           ← gTTS (text to speech)
├── api/
│   └── routes.py        ← FastAPI endpoints
└── tests/
    └── test_all.py      ← pytest test suite
```
