
import os
from uuid import uuid4
from typing import Optional

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage
from langchain_core.tools import tool
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import create_react_agent

load_dotenv()

# --------------------------------------------------
# CONFIGURATION
# --------------------------------------------------

APP_NAME = "Environmental ESG Reporting Chatbot"

REPORT_API_BASE_URL = os.getenv(
    "REPORT_API_BASE_URL",
    "https://environment-api-production.up.railway.app"
).rstrip("/")

SUPABASE_URL = os.getenv("SUPABASE_URL", "").rstrip("/")
SUPABASE_SERVICE_ROLE_KEY = os.getenv(
    "SUPABASE_SERVICE_ROLE_KEY", ""
)
ESG_FILES_TABLE = os.getenv("ESG_FILES_TABLE", "esg_files")

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_MODEL = os.getenv(
    "GROQ_MODEL",
    "openai/gpt-oss-120b"
)

REPORT_API_TIMEOUT = float(
    os.getenv("REPORT_API_TIMEOUT_SECONDS", "300")
)

if not GROQ_API_KEY:
    raise RuntimeError("GROQ_API_KEY is missing from .env")


# --------------------------------------------------
# SUPABASE HELPERS
# --------------------------------------------------

def supabase_headers():
    return {
        "apikey": SUPABASE_SERVICE_ROLE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def save_esg_file(
    report_name: str,
    pdf_url: str,
    report_json: dict
) -> dict:
    """Save a generated report to public.esg_files."""

    if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
        return {
            "saved": False,
            "error": "Supabase credentials are not configured."
        }

    endpoint = (
        f"{SUPABASE_URL}/rest/v1/{ESG_FILES_TABLE}"
    )

    row = {
        "report_name": report_name,
        "url": pdf_url,
        "report_json": report_json,
    }

    try:
        response = httpx.post(
            endpoint,
            headers={
                **supabase_headers(),
                "Prefer": "return=representation",
            },
            json=row,
            timeout=30,
        )

        response.raise_for_status()

        saved_rows = response.json()

        return {
            "saved": True,
            "report": saved_rows[0] if saved_rows else row,
        }

    except httpx.HTTPStatusError as exc:
        return {
            "saved": False,
            "error": f"Supabase returned HTTP {exc.response.status_code}.",
            "details": exc.response.text[:1000],
        }

    except httpx.HTTPError as exc:
        return {
            "saved": False,
            "error": "Could not connect to Supabase.",
            "details": str(exc),
        }


def fetch_saved_reports(query: str = "") -> dict:
    """Retrieve previously generated reports from Supabase."""

    if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
        return {
            "success": False,
            "error": "Supabase credentials are not configured."
        }

    endpoint = (
        f"{SUPABASE_URL}/rest/v1/{ESG_FILES_TABLE}"
    )

    params = {
        "select": "id,report_name,url,report_json,created_at",
        "order": "created_at.desc",
        "limit": "10",
    }

    if query.strip():
        params["report_name"] = f"ilike.*{query.strip()}*"

    try:
        response = httpx.get(
            endpoint,
            headers=supabase_headers(),
            params=params,
            timeout=30,
        )

        response.raise_for_status()
        rows = response.json()

        return {
            "success": True,
            "count": len(rows),
            "reports": rows,
        }

    except httpx.HTTPStatusError as exc:
        return {
            "success": False,
            "error": f"Supabase returned HTTP {exc.response.status_code}.",
            "details": exc.response.text[:1000],
        }

    except httpx.HTTPError as exc:
        return {
            "success": False,
            "error": "Could not retrieve saved reports.",
            "details": str(exc),
        }


# --------------------------------------------------
# TOOL 1: GENERATE ENVIRONMENTAL REPORT
# --------------------------------------------------

@tool
def generate_environment_report(project_id: int = 1) -> dict:
    """
    Generate an environmental ESG/BRSR Principle 6 report
    using the existing Environmental Report API.

    Use this tool when the user asks to generate or regenerate
    an environmental report.
    """

    url = (
        f"{REPORT_API_BASE_URL}/api/reports/{project_id}"
    )

    try:
        response = httpx.post(
            url,
            headers={"accept": "application/json"},
            content=b"",
            timeout=REPORT_API_TIMEOUT,
        )

        response.raise_for_status()
        payload = response.json()

    except httpx.TimeoutException:
        return {
            "success": False,
            "error": (
                "Report generation timed out. Check the report "
                "service before attempting another generation."
            ),
        }

    except httpx.HTTPStatusError as exc:
        return {
            "success": False,
            "error": f"Report API returned HTTP {exc.response.status_code}.",
            "details": exc.response.text[:1000],
        }

    except (httpx.HTTPError, ValueError) as exc:
        return {
            "success": False,
            "error": "Could not contact or parse the report API.",
            "details": str(exc),
        }

    if not payload.get("success"):
        return {
            "success": False,
            "error": "The report API did not confirm successful generation.",
            "api_response": payload,
        }

    report = payload.get("report") or {}
    pdf_url = payload.get("pdf_url")

    project_name = (
        report.get("project_name")
        or f"Project {project_id}"
    )

    reporting_period = report.get("reporting_period")

    report_name = (
        f"{project_name} - Environmental ESG Report"
    )

    if reporting_period:
        report_name += f" ({reporting_period})"

    # Save only after confirmed report generation.
    if pdf_url:
        database_result = save_esg_file(
            report_name=report_name,
            pdf_url=pdf_url,
            report_json=report,
        )
    else:
        database_result = {
            "saved": False,
            "error": "The report API did not return a PDF URL.",
        }

    
    return {
    "success": True,
    "project_id": project_id,
    "project_name": project_name,
    "report_name": report_name,
    "reporting_period": reporting_period,
    "synthetic_data": report.get("synthetic_data"),
    "pdf_url": pdf_url,
    "pdf_url_expires_in_seconds": payload.get(
        "pdf_url_expires_in_seconds"
    ),
    "database_saved": database_result.get("saved", False),
    "database_error": (
        database_result.get("error")
        if not database_result.get("saved")
        else None
    ),
    "data_gaps_count": len(report.get("data_gaps", [])),
    "validation_warnings_count": len(
        report.get("validation_warnings", [])
    ),
    "message": (
        "Report generated successfully. "
        "The complete JSON was retained for database storage."
    ),
}



# --------------------------------------------------
# TOOL 2: RETRIEVE SAVED REPORTS
# --------------------------------------------------

@tool
def search_saved_esg_reports(query: str = "") -> dict:
    """
    Find previously generated reports saved in Supabase.

    Use this tool when users ask to list old reports, find a
    report, retrieve its PDF URL, or ask about saved report data.

    The query optionally filters reports by report name.
    """

    return fetch_saved_reports(query)


# --------------------------------------------------
# LANGGRAPH CHATBOT
# --------------------------------------------------

SYSTEM_PROMPT = """
You are an Environmental ESG Reporting Assistant.

You help employees and management understand environmental
metrics, ESG reports, and BRSR Principle 6.

TOOLS:

1. generate_environment_report
Use this when the user explicitly asks to create, generate,
or regenerate an environmental report.

2. search_saved_esg_reports
Use this when the user asks about previously generated reports,
saved report links, or existing report data.

RULES:

- If the user requests a report without specifying a project,
  use project_id=1.
- Never claim a report was generated unless the tool succeeds.
- After generation, share the PDF URL and a concise summary.
- If database_save.saved is true, confirm that the report was
  saved to Supabase.
- If report generation succeeds but saving fails, clearly
  explain that the report exists but was not saved to the table.
- When discussing an old report, use the JSON returned from
  Supabase rather than generating another report.
- Do not claim a saved report was found unless the retrieval
  tool returns it.
- Signed PDF URLs may expire. Mention the expiry if provided.
- Synthetic data must be clearly identified as illustrative.
- Never treat missing values as zero.
- Never invent environmental measurements, approvals, or
  compliance status.
- Keep responses conversational and concise.
"""

model = ChatGroq(
    model=GROQ_MODEL,
    api_key=GROQ_API_KEY,
    temperature=0.2,
)

checkpointer = MemorySaver()

agent = create_react_agent(
    model=model,
    tools=[
        generate_environment_report,
        search_saved_esg_reports,
    ],
    checkpointer=checkpointer,
    prompt=SYSTEM_PROMPT,
)


# --------------------------------------------------
# FASTAPI APPLICATION
# --------------------------------------------------

app = FastAPI(
    title=APP_NAME,
    version="0.2.0",
    description=(
        "Conversational environmental ESG reporting chatbot"
    ),
)

cors_origins = [
    item.strip()
    for item in os.getenv("CORS_ORIGINS", "*").split(",")
    if item.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=False if "*" in cors_origins else True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    message: str = Field(
        ...,
        min_length=1,
        max_length=10000,
    )
    session_id: Optional[str] = Field(
        default=None,
        max_length=200,
    )
    project_id: int = Field(
        default=1,
        ge=1,
    )


class ChatResponse(BaseModel):
    success: bool
    session_id: str
    reply: str


@app.get("/")
def root():
    return {
        "message": "Environmental ESG chatbot is running.",
        "docs": "/docs",
        "chat_endpoint": "/chat",
    }


@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": APP_NAME,
        "report_api": REPORT_API_BASE_URL,
    }


@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest):

    session_id = request.session_id or str(uuid4())

    user_message = request.message

    if request.project_id != 1:
        user_message += (
            f"\n\nThe selected project ID is "
            f"{request.project_id}. Use this ID if generating "
            f"a report."
        )

    config = {
        "configurable": {
            "thread_id": session_id
        }
    }

    try:
        result = agent.invoke(
            {
                "messages": [
                    HumanMessage(content=user_message)
                ]
            },
            config=config,
        )

        messages = result.get("messages", [])

        last_ai_message = next(
            (
                message
                for message in reversed(messages)
                if getattr(message, "type", "") == "ai"
                and getattr(message, "content", None)
            ),
            None,
        )

        if last_ai_message is None:
            raise RuntimeError(
                "The assistant did not return a response."
            )

        content = last_ai_message.content

        if isinstance(content, str):
            reply = content
        elif isinstance(content, list):
            reply = "\n".join(
                part.get("text", "")
                for part in content
                if isinstance(part, dict)
                and part.get("text")
            )
        else:
            reply = str(content)

        return ChatResponse(
            success=True,
            session_id=session_id,
            reply=reply or "Please try asking your question again.",
        )

    except Exception as exc:
        # Details are kept in server logs rather than exposed
        # to the client.
        print(f"Chatbot error: {type(exc).__name__}: {exc}")

        raise HTTPException(
            status_code=502,
            detail=(
                "Chatbot processing failed. "
                "Check the server terminal for details."
            ),
        )
