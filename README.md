# CamGuard — Agentic Fall Triage & Response System

An AI-powered caregiver camera system that detects falls, triages incidents, and orchestrates emergency response using Gemini as an agentic planner, ElevenLabs for voice, Twilio for alerts, and Snowflake for logging and self-optimization.

## Architecture

```
Edge Camera → POST /api/telemetry → FastAPI Backend
                                        ├── Gemini (planner agent)
                                        ├── ElevenLabs (TTS)
                                        ├── Twilio (SMS + Voice)
                                        ├── Snowflake (logging + optimization)
                                        ├── WebSocket → Next.js Frontend
                                        └── SQLite/Postgres (operational DB)
```

## Quick Start

### 1. Clone and set up environment

```bash
git clone <repo-url> && cd CamGuard
make setup   # creates .env files from examples
```

### 2. Fill in API keys

Edit `backend/.env`:
```
GEMINI_API_KEY=your-gemini-api-key
ELEVENLABS_API_KEY=your-elevenlabs-api-key
TWILIO_ACCOUNT_SID=your-twilio-sid
TWILIO_AUTH_TOKEN=your-twilio-token
TWILIO_FROM_NUMBER=+1234567890
SNOWFLAKE_ACCOUNT=your-account
SNOWFLAKE_USER=your-user
SNOWFLAKE_PASSWORD=your-password
PUBLIC_BASE_URL=https://your-public-url.com
```

Edit `frontend/.env`:
```
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
NEXT_PUBLIC_WS_URL=ws://localhost:8000/ws
```

### 3. Run with Docker Compose

```bash
docker compose up --build
```

Or run locally:

```bash
# Terminal 1: Backend
cd backend
pip install -r requirements.txt
cp .env.example .env  # fill in keys
uvicorn app:app --host 0.0.0.0 --port 8000 --reload

# Terminal 2: Frontend
cd frontend
npm install
cp .env.example .env
npm run dev
```

### 4. Open the app

- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- API Docs: http://localhost:8000/docs

### 5. Run demos

```bash
# Prevention demo (bed edge risk)
curl -X POST http://localhost:8000/api/demo/prevention | python3 -m json.tool

# Fall incident demo
curl -X POST http://localhost:8000/api/demo/fall | python3 -m json.tool
```

Or use the dashboard "Run Fall Demo" / "Run Prevention Demo" buttons.

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check with integration status |
| POST | `/api/cameras/register` | Register a new camera |
| GET | `/api/cameras` | List all cameras |
| GET | `/api/cameras/{id}` | Camera detail |
| PATCH | `/api/cameras/{id}` | Update camera config |
| GET | `/api/cameras/{id}/config` | Get merged config |
| POST | `/api/telemetry` | Ingest telemetry from edge |
| GET | `/api/incidents` | List incidents (filterable) |
| GET | `/api/incidents/{id}` | Incident detail |
| POST | `/api/incidents/{id}/ack` | Acknowledge incident |
| POST | `/api/incidents/{id}/false_alarm` | Mark false alarm |
| POST | `/api/incidents/{id}/translate` | Translate summary |
| POST | `/api/incidents/{id}/tts` | Text-to-speech (returns MP3) |
| GET | `/api/incidents/{id}/timeline` | Incident timeline events |
| GET | `/api/incidents/{id}/plan` | Plan history |
| GET | `/api/incidents/{id}/frames` | Evidence frames |
| GET | `/api/incidents/{id}/summary` | Generated summary |
| POST | `/api/agent/monitoring-instructions` | AI chat instructions |
| POST | `/api/demo/prevention` | Trigger prevention demo |
| POST | `/api/demo/fall` | Trigger fall demo |
| POST | `/twilio/voice/{id}` | Twilio voice webhook |
| POST | `/twilio/dtmf/{id}` | Twilio DTMF webhook |
| WS | `/ws` | WebSocket realtime events |

## Twilio Webhook Setup

1. Set `PUBLIC_BASE_URL` in `.env` to your public URL (use ngrok for local dev)
2. In Twilio console, set voice webhook URL to `{PUBLIC_BASE_URL}/twilio/voice/{incident_id}`
3. DTMF digits: 1=Ack, 2=Will call, 3=Escalate, 4=False alarm

## Snowflake Verification

After running a demo, verify Snowflake writes:

```sql
SELECT * FROM incident_timeline_sf ORDER BY ts DESC LIMIT 10;
SELECT * FROM incident_plans_sf ORDER BY ts DESC LIMIT 5;
SELECT * FROM action_log_sf ORDER BY ts DESC LIMIT 10;
SELECT * FROM agent_logs ORDER BY ts DESC LIMIT 5;
SELECT * FROM config_suggestions_sf ORDER BY ts DESC LIMIT 5;
SELECT * FROM config_applied_sf ORDER BY ts DESC LIMIT 5;
```

## Curl Examples

```bash
# Health check
curl http://localhost:8000/health

# Register a camera
curl -X POST http://localhost:8000/api/cameras/register \
  -H "Content-Type: application/json" \
  -d '{"name": "Bedroom Cam", "room_type": "bedroom", "primary_contact": "+1234567890"}'

# Run fall demo
curl -X POST http://localhost:8000/api/demo/fall

# List incidents
curl http://localhost:8000/api/incidents

# Acknowledge an incident
curl -X POST http://localhost:8000/api/incidents/{INCIDENT_ID}/ack \
  -H "Content-Type: application/json" \
  -d '{"ack_by": "nurse"}'

# Translate incident
curl -X POST http://localhost:8000/api/incidents/{INCIDENT_ID}/translate \
  -H "Content-Type: application/json" \
  -d '{"target_language": "es"}'

# Text-to-speech
curl -X POST http://localhost:8000/api/incidents/{INCIDENT_ID}/tts \
  -H "Content-Type: application/json" \
  --output incident.mp3

# AI monitoring instruction
curl -X POST http://localhost:8000/api/agent/monitoring-instructions \
  -H "Content-Type: application/json" \
  -d '{"text": "She is dizzy tonight, watch for falls", "priority": "high"}'

# WebSocket test (use websocat)
websocat ws://localhost:8000/ws
```

## Tech Stack

**Backend:** Python 3.11, FastAPI, SQLAlchemy 2.0, Pydantic v2, APScheduler, httpx
**Frontend:** Next.js 14 (App Router), TypeScript, TailwindCSS, Lucide Icons
**AI:** Gemini 2.5 Flash Lite (fast), Gemini 2.5 Pro (strong), ElevenLabs TTS
**Alerts:** Twilio SMS + Programmable Voice with DTMF
**Data:** Snowflake (logging + self-optimization), SQLite/PostgreSQL (operational)
**Deploy:** Docker Compose, DigitalOcean ready

## Run Checklist

1. Copy `.env.example` to `.env` for backend and frontend
2. Fill in API keys (Gemini, ElevenLabs, Twilio, Snowflake)
3. Run `docker compose up --build` (or run backend + frontend locally)
4. Open http://localhost:3000
5. Log in with any email and PIN
6. Click **Run Fall Demo** on the dashboard
7. See an incident appear with severity, plan, and reasons
8. Click **Translate** to translate the summary
9. Click **Read Aloud** to hear the TTS audio
10. Check Snowflake tables for logged events
11. Press **Acknowledge** and confirm escalation stops
