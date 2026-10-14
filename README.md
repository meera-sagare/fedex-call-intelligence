# ABC Call Intelligence

AI-powered post-call automation for the ABC Collections / Accounts Receivable team. Each customer call is
turned into structured, Oracle-ready documentation, so collectors spend less time on notes and more time with customers.

For every call the application:

- **Transcribes** uploaded recordings (Whisper, running locally)
- **Generates a call log summary** and **interaction notes**
- **Captures payment commitments** (amount, due date, method, invoices, confidence), **risks**
  (dispute, financial hardship, broken promise, escalation, churn) and **follow-up actions**
- **Scores sentiment** (Positive / Neutral / Negative, −1…1) and classifies the **call outcome**
- **Stores** everything as structured columns in PostgreSQL
- Rolls it up into **portfolio and management insights** (AR, overdue, open promises to pay, top risks, sentiment mix)

## Stack

| Layer    | Technology |
|----------|------------|
| Frontend | Angular 22 (standalone components, signals), SCSS |
| Backend  | Python 3.12+, FastAPI, SQLAlchemy 2 |
| Database | PostgreSQL 17 |
| AI       | Anthropic Claude (`claude-opus-5-5`) with structured outputs; offline rule-based analyzer as fallback |
| Speech   | faster-whisper (optional) |

## Screens

1. **Welcome page:** pick the collector, see portfolio KPIs, the collector's customers (sorted by overdue
   amount, searchable and filterable by status), top risks and upcoming payment commitments.
2. **Customer page:** the customer name on a purple banner. The left ⅔ shows customer details (full name, phone,
   alternate phone, email, address, shipping/home/office addresses, status) and the AR snapshot. The right ⅓
   lists call logs up to today. Clicking a call log opens its **call log summary and analysis**. A call is analyzed
   the first time it is opened and the result is saved. Collectors can also log a new call from a recording
   and/or a transcript.

Theme: white background, brand purple (`#4D148C`) titles, brand orange (`#FF6200`) subtitles, black body text.

## Quick start (Docker)

```bash
cp backend/.env.example .env           # optional: add ANTHROPIC_API_KEY to use Claude
docker compose up -d --build
```

- App: http://localhost:8080
- API docs (Swagger): http://localhost:8000/docs

On first start the database is seeded with 3 collectors, 12 customer accounts and 21 sample collections calls.
Older calls are pre-analyzed. Recent calls are analyzed when you open them.

> The backend image installs Whisper for audio transcription (~1 GB). To build without it:
> `docker compose build --build-arg INSTALL_TRANSCRIPTION=false backend`. Uploads that include a
> transcript still work.

## Local development

```bash
# Database
docker compose up -d db

# Backend (http://localhost:8000)
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt          # + requirements-transcription.txt for audio
cp .env.example .env
uvicorn app.main:app --reload

# Frontend (http://localhost:4200, proxies /api to :8000)
cd frontend
npm install
npm start
```

## AI analysis

`backend/app/services/analyzer.py` has two engines behind one Pydantic contract (`CallAnalysis`):

| `AI_ENGINE` | Behaviour |
|-------------|-----------|
| `auto` (default) | Uses Claude when `ANTHROPIC_API_KEY` is set and falls back to the rule-based engine if the API call fails |
| `claude` | Always Claude. Failures are recorded on the call log as `Failed` |
| `rules` | Offline keyword/regex analyzer only (no external calls) |

The Claude engine uses structured outputs (`messages.parse` with the `CallAnalysis` schema), so responses are
always valid JSON matching the database fields. It also enables server-side refusal fallback. The prompt contains
collections domain guidance (PTP rules, dispute types, resolving relative dates against the call date). Each
call log records which engine produced it (`analysis_engine`).

## API

| Method | Path | Purpose |
|--------|------|---------|
| GET  | `/api/collectors` | Collectors |
| GET  | `/api/collectors/{id}/customers?search=&status=` | A collector's customers |
| GET  | `/api/customers/{id}` | Customer details |
| GET  | `/api/customers/{id}/call-logs` | Call logs up to today, newest first |
| POST | `/api/customers/{id}/call-logs` | Multipart: `audio` and/or `transcript`, `direction`. Transcribes, analyzes and stores |
| GET  | `/api/call-logs/{id}` | Call log with analysis (analyzes on first open) |
| POST | `/api/call-logs/{id}/analyze` | Re-run analysis |
| GET  | `/api/insights/portfolio?collector_id=` | Portfolio insights (omit `collector_id` for the management view) |
| GET  | `/api/health` | Health and active AI engine |

## Data model

- `collectors`: id, full_name, email, region
- `customers`: contact fields (full name, phone, alternate phone, email, address, shipping/home/office address),
  status, AR balance, overdue amount, days past due, risk level, last contact date
- `call_logs`: call metadata, transcript, **`call_log_summary`**, **`interaction_notes`**, sentiment and score,
  call outcome, dispute flag, `payment_commitments` / `risks` / `follow_up_actions` (JSONB), analysis status,
  engine and timestamp

Tables are created automatically on startup.

## Tests

```bash
cd backend && pytest                 # 21 tests: analyzer rules, Claude adapter (mocked), API endpoints
cd frontend && npx ng test --watch=false   # component tests (welcome, customer detail)
```

## Project layout

```
backend/
  app/
    main.py              FastAPI app, CORS, startup (create tables + seed)
    models.py            SQLAlchemy models
    schemas.py           API schemas + CallAnalysis contract
    routers/             collectors, customers, call_logs, insights
    services/
      analyzer.py        Claude + rule-based analysis engines
      transcriber.py     Whisper speech-to-text
      call_service.py    Runs analysis and writes results to the call log
    seed.py              Demo data
  tests/
frontend/
  src/app/
    core/                API service, models, collector context
    pages/welcome/       Welcome / portfolio page
    pages/customer-detail/
docker-compose.yml
```

## Publishing to GitHub

```bash
git remote add origin https://github.com/<you>/abc-call-intelligence.git
git push -u origin main
```

## Roadmap ideas

- Write interaction notes back to Oracle Collections (AR) through its REST API, not only to PostgreSQL
- ABC SSO in place of the collector selector
- Speaker diarization for recordings (collector vs. customer)
- Broken-promise tracking against cash receipts; supervisor dashboards across regions
