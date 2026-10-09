# Environmental ESG Reporting Chatbot (MVP)

A Python chatbot using LangGraph + Groq. It can chat about environmental reporting and call the existing Environmental Report API when a user asks to generate a report.

## 1. Setup

Use Python 3.11 or 3.12 for the smoothest dependency compatibility.

```bash
python -m venv .venv
```

Windows PowerShell:
```powershell
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

Linux/macOS:
```bash
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Put your Groq API key and Supabase backend credentials in `.env`. The chatbot inserts a row into `public.esg_files` only after the report API confirms success and returns a PDF URL. The expected table columns are `report_name` and `url` (an `id` and `created_at` column with defaults are fine).

Required variables:
- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY`
- `ESG_FILES_TABLE=esg_files`

Never commit `.env` or expose the Supabase service-role key in frontend code.

## 2. Run locally

```bash
uvicorn api:app --reload --host 0.0.0.0 --port 8000
```

Open `http://127.0.0.1:8000/docs`.

## 3. Chat request

```bash
curl -X POST "http://127.0.0.1:8000/chat" \
  -H "Content-Type: application/json" \
  -d "{\"message\":\"Hello, what can you help me with?\"}"
```

Generate the environmental report:
```bash
curl -X POST "http://127.0.0.1:8000/chat" \
  -H "Content-Type: application/json" \
  -d "{\"message\":\"Generate the environmental report for project 1\",\"session_id\":\"demo-session\",\"project_id\":1}"
```

The response includes `session_id` and `reply`. Reuse the same `session_id` to continue a conversation.

## 4. Railway deployment

Build command:
```bash
pip install -r requirements.txt
```

Start command:
```bash
uvicorn api:app --host 0.0.0.0 --port $PORT
```

Add `GROQ_API_KEY`, `GROQ_MODEL`, `REPORT_API_BASE_URL`, `REPORT_API_TIMEOUT_SECONDS`, and `CORS_ORIGINS` under Railway Variables.

## 5. Current MVP limitations

- Conversation memory is in process memory. It resets when the server restarts or redeploys, and does not coordinate across multiple replicas.
- This MVP has no user authentication/authorization. Do not expose it to confidential company users/data until authentication and project-level access control are added.
- The API currently generates the report synchronously. A slow report generation may take several minutes.
- The report API may return a time-limited PDF URL. This chatbot passes the URL through and reports the expiry when available.
- The deployed report service uses synthetic pilot data in the provided example. The chatbot is instructed to label synthetic data clearly.
