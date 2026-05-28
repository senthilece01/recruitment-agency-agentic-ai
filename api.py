"""
Recruitment Agency — FastAPI REST Server
-----------------------------------------
Wraps the LangGraph multi-agent workflow with a production-quality HTTP API.

Start with:
    uvicorn api:app --reload --port 8000

Endpoints:
    POST   /api/candidates/screen   — Run the full screening pipeline
    GET    /api/candidates          — List all screened candidates (filterable)
    GET    /api/candidates/{id}     — Full state for a single candidate
    GET    /api/action-log          — Global action log (all runs)
    GET    /api/stats               — Aggregate statistics
    DELETE /api/candidates          — Reset in-memory store (demo use)
    GET    /health                  — Health check
"""

import os
import uuid
from datetime import datetime, timezone
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

load_dotenv()

# ---------------------------------------------------------------------------
# FastAPI app + CORS
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Recruitment Agency AI API",
    description=(
        "REST interface to the LangGraph multi-agent recruitment screening workflow. "
        "Each POST /api/candidates/screen run is fully isolated: action-log entries "
        "are attributed only to the candidate that generated them."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# In-memory candidate store  { uuid_str -> candidate_record }
# ---------------------------------------------------------------------------

CANDIDATES_STORE: dict[str, dict] = {}

# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------

VALID_DECISIONS = {"interview", "escalate", "reject"}


class ScreenRequest(BaseModel):
    application_text: str = Field(
        ...,
        min_length=10,
        description="Full text of the candidate's job application or résumé.",
        examples=["I have 8 years of Python experience with FastAPI, Django and AWS."],
    )
    job_role: str = Field(
        default="python developer",
        description="Role being applied for (informational — passed along in metadata).",
        examples=["python developer"],
    )


class CandidateSummary(BaseModel):
    id: str
    screened_at: str
    job_role: str
    candidate_name: str
    experience_level: str
    skill_match: str
    skill_score: int
    final_decision: str
    email_sent: bool


class ScreenResponse(BaseModel):
    id: str
    screened_at: str
    job_role: str
    state: dict
    action_log: list[dict]


# ---------------------------------------------------------------------------
# Helper — OpenAI key guard
# ---------------------------------------------------------------------------

def _require_openai_key() -> None:
    """Raise HTTP 503 if the OpenAI API key is not configured."""
    if not os.getenv("OPENAI_API_KEY"):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "OPENAI_API_KEY is not configured on this server. "
                "Copy .env.example → .env and set your key, then restart."
            ),
        )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@app.get("/health", tags=["System"], summary="Health check")
def health_check() -> dict:
    """
    Returns the service status and whether the OpenAI key is present.
    Does NOT make any LLM calls — safe to poll from load balancers.
    """
    return {
        "status": "ok",
        "openai_key_configured": bool(os.getenv("OPENAI_API_KEY")),
        "candidates_in_store": len(CANDIDATES_STORE),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.post(
    "/api/candidates/screen",
    response_model=ScreenResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Candidates"],
    summary="Screen a candidate through the full AI pipeline",
)
def screen_candidate(request: ScreenRequest) -> ScreenResponse:
    """
    Run the LangGraph multi-agent pipeline on a job application.

    Pipeline stages:
    1. **HR Screener** — extracts skills and years of experience
    2. **Technical Assessor** — runs skill-gap analysis and produces a score
    3. **Recruiter** — decides interview / escalate / reject, sends mock email

    The `action_log` in the response contains **only** actions generated
    during this specific run (email sends, calendar invites, decision records).

    Returns the full `RecruitmentState` plus per-candidate action log entries.
    """
    _require_openai_key()

    # Deferred import — only load LangGraph machinery when the key is present
    # so the server still starts cleanly even without a key configured.
    try:
        from graph import app as langgraph_app
        import tools.communication_tools as comm_tools
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to load LangGraph workflow: {exc}",
        ) from exc

    # --- Action-log isolation -------------------------------------------
    # Capture the current length of the global log before this run so we
    # can slice out only the entries produced during this candidate's run.
    log_start_index = len(comm_tools.ACTION_LOG)

    # --- Run the graph --------------------------------------------------
    try:
        result: dict = langgraph_app.invoke(
            {"application": request.application_text}
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"LangGraph pipeline error: {exc}",
        ) from exc

    # --- Capture per-candidate log entries ------------------------------
    candidate_action_log: list[dict] = list(
        comm_tools.ACTION_LOG[log_start_index:]
    )

    # --- Build candidate record -----------------------------------------
    candidate_id = str(uuid.uuid4())
    screened_at = datetime.now(timezone.utc).isoformat()

    # Strip the LangChain message objects from the persisted state — they
    # are not JSON-serialisable and are not useful to API consumers.
    serialisable_state = {
        k: v
        for k, v in result.items()
        if k != "messages"
    }

    record = {
        "id": candidate_id,
        "screened_at": screened_at,
        "job_role": request.job_role,
        "state": serialisable_state,
        "action_log": candidate_action_log,
    }

    CANDIDATES_STORE[candidate_id] = record

    return ScreenResponse(
        id=candidate_id,
        screened_at=screened_at,
        job_role=request.job_role,
        state=serialisable_state,
        action_log=candidate_action_log,
    )


@app.get(
    "/api/candidates",
    response_model=list[CandidateSummary],
    tags=["Candidates"],
    summary="List all screened candidates",
)
def list_candidates(
    decision: Optional[str] = Query(
        default=None,
        description="Filter by final decision: interview | escalate | reject",
        examples=["interview"],
    ),
) -> list[CandidateSummary]:
    """
    Return summary records for every screened candidate, newest first.

    Use the optional `?decision=` query parameter to filter by the
    recruiter's final decision (`interview`, `escalate`, or `reject`).
    """
    if decision is not None and decision not in VALID_DECISIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid decision filter '{decision}'. Must be one of: {sorted(VALID_DECISIONS)}",
        )

    summaries: list[CandidateSummary] = []
    for record in CANDIDATES_STORE.values():
        state = record["state"]
        final_decision = state.get("final_decision", "")

        if decision is not None and final_decision != decision:
            continue

        summaries.append(
            CandidateSummary(
                id=record["id"],
                screened_at=record["screened_at"],
                job_role=record["job_role"],
                candidate_name=state.get("candidate_name", "Unknown"),
                experience_level=state.get("experience_level", "Unknown"),
                skill_match=state.get("skill_match", "Unknown"),
                skill_score=state.get("skill_score", 0),
                final_decision=final_decision,
                email_sent=state.get("email_sent", False),
            )
        )

    # Newest first
    summaries.sort(key=lambda s: s.screened_at, reverse=True)
    return summaries


@app.get(
    "/api/candidates/{candidate_id}",
    response_model=ScreenResponse,
    tags=["Candidates"],
    summary="Get full state for a single candidate",
)
def get_candidate(candidate_id: str) -> ScreenResponse:
    """
    Return the complete `RecruitmentState` and per-candidate action log
    for the given UUID.  Returns 404 if the candidate is not found.
    """
    record = CANDIDATES_STORE.get(candidate_id)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Candidate '{candidate_id}' not found.",
        )

    return ScreenResponse(
        id=record["id"],
        screened_at=record["screened_at"],
        job_role=record["job_role"],
        state=record["state"],
        action_log=record["action_log"],
    )


@app.get(
    "/api/action-log",
    tags=["Observability"],
    summary="Return the global action log",
)
def get_global_action_log() -> dict:
    """
    Return every entry ever appended to `ACTION_LOG` across all screening
    runs since the server started.  Entries are in chronological order.

    Each entry is one of:
    - `{"type": "email", "to": ..., "subject": ..., "body": ..., "sent_at": ...}`
    - `{"type": "calendar_invite", "candidate": ..., "date": ..., ...}`
    - `{"type": "decision", "candidate": ..., "decision": ..., "reason": ..., ...}`
    """
    try:
        from tools.communication_tools import ACTION_LOG
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Could not load communication_tools module: {exc}",
        ) from exc

    return {
        "total": len(ACTION_LOG),
        "entries": list(ACTION_LOG),
    }


@app.get(
    "/api/stats",
    tags=["Observability"],
    summary="Aggregate screening statistics",
)
def get_stats() -> dict:
    """
    Return aggregate counts and metrics across all candidates screened
    during the current server session.

    Fields:
    - `total` — total candidates screened
    - `interviews` — count with `final_decision == "interview"`
    - `escalations` — count with `final_decision == "escalate"`
    - `rejections` — count with `final_decision == "reject"`
    - `avg_skill_score` — mean `skill_score` across all candidates (0 if none)
    """
    records = list(CANDIDATES_STORE.values())
    total = len(records)

    if total == 0:
        return {
            "total": 0,
            "interviews": 0,
            "escalations": 0,
            "rejections": 0,
            "avg_skill_score": 0.0,
        }

    interviews = sum(
        1 for r in records if r["state"].get("final_decision") == "interview"
    )
    escalations = sum(
        1 for r in records if r["state"].get("final_decision") == "escalate"
    )
    rejections = sum(
        1 for r in records if r["state"].get("final_decision") == "reject"
    )

    skill_scores = [
        r["state"].get("skill_score", 0)
        for r in records
        if isinstance(r["state"].get("skill_score"), (int, float))
    ]
    avg_skill_score = round(sum(skill_scores) / len(skill_scores), 2) if skill_scores else 0.0

    return {
        "total": total,
        "interviews": interviews,
        "escalations": escalations,
        "rejections": rejections,
        "avg_skill_score": avg_skill_score,
    }


@app.delete(
    "/api/candidates",
    status_code=status.HTTP_200_OK,
    tags=["System"],
    summary="Clear all candidates (demo reset)",
)
def clear_candidates() -> dict:
    """
    Wipe the in-memory `CANDIDATES_STORE`.  Also clears the global
    `ACTION_LOG` in `communication_tools` so action-log isolation
    remains accurate after the reset.

    **For demo / development use only.**  This operation is irreversible.
    """
    cleared_count = len(CANDIDATES_STORE)
    CANDIDATES_STORE.clear()

    try:
        from tools.communication_tools import ACTION_LOG
        ACTION_LOG.clear()
    except Exception:
        pass  # Non-fatal — store is already cleared

    return {
        "cleared": cleared_count,
        "message": f"Deleted {cleared_count} candidate record(s) and reset the action log.",
    }


# ---------------------------------------------------------------------------
# Global exception handler — ensures all unhandled errors return JSON
# ---------------------------------------------------------------------------

@app.exception_handler(Exception)
async def unhandled_exception_handler(request, exc: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "success": False,
            "error": "An unexpected server error occurred.",
            "detail": str(exc),
        },
    )
