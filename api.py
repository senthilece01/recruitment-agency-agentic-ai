"""
Recruitment Agency — FastAPI REST Server
-----------------------------------------
Wraps the LangGraph multi-agent workflow with a production-quality HTTP API.
Candidate records are persisted to PostgreSQL via db.py.

Start with:
    uvicorn api:app --reload --port 8000

Endpoints:
    POST   /api/candidates/screen   — Run the full screening pipeline
    POST   /api/candidates/upload   — Upload a resume file and screen it
    GET    /api/candidates          — List all screened candidates (filterable)
    GET    /api/candidates/{id}     — Full state for a single candidate
    GET    /api/action-log          — Global action log (current session)
    GET    /api/stats               — Aggregate statistics (from DB)
    DELETE /api/candidates          — Clear all candidates (dev/demo use)
    GET    /health                  — Health check
"""

import io
import os
import uuid
from datetime import datetime, timezone
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi import status as status_module
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

load_dotenv()

# ---------------------------------------------------------------------------
# Database initialisation
# ---------------------------------------------------------------------------

def _try_init_db() -> bool:
    """Attempt to connect to PostgreSQL and create the schema. Returns True on success."""
    try:
        from db import init_db
        init_db()
        return True
    except Exception as exc:
        print(f"[WARNING] PostgreSQL unavailable — candidates will not be persisted: {exc}")
        return False


_DB_AVAILABLE = _try_init_db()

# In-memory fallback store used when Postgres is not configured/reachable
_FALLBACK_STORE: dict[str, dict] = {}

# ---------------------------------------------------------------------------
# FastAPI app + CORS
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Recruitment Agency AI API",
    description=(
        "REST interface to the LangGraph multi-agent recruitment screening workflow. "
        "Candidate records are persisted to PostgreSQL. "
        "Each POST /api/candidates/screen run is fully isolated."
    ),
    version="2.0.0",
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
        description="Role being applied for.",
        examples=["python developer"],
    )
    job_id: Optional[str] = Field(
        default=None,
        description="Internal job posting ID to match the candidate against.",
    )


class JobRequest(BaseModel):
    title: str = Field(..., description="Job title")
    department: str = Field(default="", description="Department")
    location: str = Field(default="Remote", description="Location")
    employment_type: str = Field(default="full-time", description="full-time | part-time | contract | internship")
    status: str = Field(default="current", description="current | upcoming | past")
    description: str = Field(default="", description="Full job description")
    required_skills: list[str] = Field(default=[], description="Required skills list")
    nice_to_have: list[str] = Field(default=[], description="Nice-to-have skills list")
    min_years: int = Field(default=0, description="Minimum years of experience")
    salary_range: str = Field(default="", description="Salary range string")
    posted_at: Optional[str] = Field(default=None, description="ISO datetime when the job was posted")
    closes_at: Optional[str] = Field(default=None, description="ISO datetime when the job closes")


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
    application_text: str = ""
    state: dict
    action_log: list[dict]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _require_openai_key() -> None:
    if not os.getenv("OPENAI_API_KEY"):
        raise HTTPException(
            status_code=status_module.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "OPENAI_API_KEY is not configured. "
                "Copy .env.example → .env, set your key, then restart."
            ),
        )


def _save_record(record: dict) -> None:
    if _DB_AVAILABLE:
        try:
            from db import save_candidate
            save_candidate(record)
            return
        except Exception as exc:
            print(f"[WARNING] DB write failed — falling back to memory: {exc}")
    _FALLBACK_STORE[record["id"]] = record


def _get_record(candidate_id: str) -> Optional[dict]:
    if _DB_AVAILABLE:
        try:
            from db import get_candidate
            return get_candidate(candidate_id)
        except Exception as exc:
            print(f"[WARNING] DB read failed: {exc}")
    return _FALLBACK_STORE.get(candidate_id)


def _list_records(decision: Optional[str] = None) -> list[dict]:
    if _DB_AVAILABLE:
        try:
            from db import list_candidates
            return list_candidates(decision=decision)
        except Exception as exc:
            print(f"[WARNING] DB list failed: {exc}")
    records = list(_FALLBACK_STORE.values())
    if decision:
        records = [r for r in records if r["state"].get("final_decision") == decision]
    return sorted(records, key=lambda r: r["screened_at"], reverse=True)


def _run_pipeline(application_text: str, job_role: str, job_id: Optional[str] = None) -> ScreenResponse:
    """Core: run the LangGraph pipeline and persist the result."""
    try:
        from graph import app as langgraph_app
        import tools.communication_tools as comm_tools
    except Exception as exc:
        raise HTTPException(
            status_code=status_module.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to load LangGraph workflow: {exc}",
        ) from exc

    log_start_index = len(comm_tools.ACTION_LOG)

    try:
        result: dict = langgraph_app.invoke({
            "application": application_text,
            "job_id": job_id or "",
        })
    except Exception as exc:
        raise HTTPException(
            status_code=status_module.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"LangGraph pipeline error: {exc}",
        ) from exc

    candidate_action_log: list[dict] = list(comm_tools.ACTION_LOG[log_start_index:])

    candidate_id = str(uuid.uuid4())
    screened_at = datetime.now(timezone.utc).isoformat()

    serialisable_state = {k: v for k, v in result.items() if k != "messages"}

    record = {
        "id":               candidate_id,
        "screened_at":      screened_at,
        "job_role":         job_role,
        "job_id":           job_id,
        "application_text": application_text,
        "state":            serialisable_state,
        "action_log":       candidate_action_log,
    }

    _save_record(record)

    return ScreenResponse(
        id=candidate_id,
        screened_at=screened_at,
        job_role=job_role,
        application_text=application_text,
        state=serialisable_state,
        action_log=candidate_action_log,
    )


def _extract_text_from_file(filename: str, content: bytes) -> str:
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

    if ext == "pdf":
        try:
            from pypdf import PdfReader
            reader = PdfReader(io.BytesIO(content))
            return "\n".join(page.extract_text() or "" for page in reader.pages).strip()
        except Exception as exc:
            raise HTTPException(
                status_code=status_module.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Could not parse PDF: {exc}",
            ) from exc

    if ext in {"docx", "doc"}:
        try:
            import docx
            doc = docx.Document(io.BytesIO(content))
            return "\n".join(p.text for p in doc.paragraphs).strip()
        except Exception as exc:
            raise HTTPException(
                status_code=status_module.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Could not parse DOCX: {exc}",
            ) from exc

    try:
        return content.decode("utf-8", errors="replace").strip()
    except Exception as exc:
        raise HTTPException(
            status_code=status_module.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Could not decode file as text: {exc}",
        ) from exc


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/health", tags=["System"], summary="Health check")
def health_check() -> dict:
    total = 0
    if _DB_AVAILABLE:
        try:
            from db import get_stats
            total = get_stats()["total"]
        except Exception:
            total = len(_FALLBACK_STORE)
    else:
        total = len(_FALLBACK_STORE)

    return {
        "status": "ok",
        "openai_key_configured": bool(os.getenv("OPENAI_API_KEY")),
        "resend_key_configured": bool(os.getenv("RESEND_API_KEY")),
        "tavily_key_configured": bool(os.getenv("TAVILY_API_KEY")),
        "database": "postgresql" if _DB_AVAILABLE else "in-memory fallback",
        "candidates_in_store": total,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.post(
    "/api/candidates/screen",
    response_model=ScreenResponse,
    status_code=status_module.HTTP_201_CREATED,
    tags=["Candidates"],
    summary="Screen a candidate through the full AI pipeline",
)
def screen_candidate(request: ScreenRequest) -> ScreenResponse:
    """
    Run the LangGraph multi-agent pipeline on a job application.

    Pipeline stages:
    1. **HR Screener** — extracts skills and years of experience
    2. **Technical Assessor** — matches candidate against the internal JD (job_id)
    3. **Recruiter** — decides interview / escalate / reject, sends email via Resend

    Results are persisted to PostgreSQL.
    """
    _require_openai_key()
    return _run_pipeline(request.application_text, request.job_role, request.job_id)


@app.post(
    "/api/candidates/upload",
    response_model=ScreenResponse,
    status_code=status_module.HTTP_201_CREATED,
    tags=["Candidates"],
    summary="Upload a resume file and screen it through the full AI pipeline",
)
async def upload_and_screen(
    file: UploadFile = File(..., description="Resume file — PDF, DOCX, or TXT"),
    job_role: str = "python developer",
    job_id: Optional[str] = None,
) -> ScreenResponse:
    """
    Accept a resume file (PDF / DOCX / TXT), extract its text, then run the
    full LangGraph pipeline exactly as POST /api/candidates/screen does.
    """
    _require_openai_key()

    content = await file.read()
    if not content:
        raise HTTPException(
            status_code=status_module.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty.",
        )

    application_text = _extract_text_from_file(file.filename or "resume.txt", content)
    if len(application_text) < 10:
        raise HTTPException(
            status_code=status_module.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Could not extract sufficient text from the uploaded file.",
        )

    return _run_pipeline(application_text, job_role, job_id)


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
    ),
) -> list[CandidateSummary]:
    if decision is not None and decision not in VALID_DECISIONS:
        raise HTTPException(
            status_code=status_module.HTTP_400_BAD_REQUEST,
            detail=f"Invalid decision filter '{decision}'. Must be one of: {sorted(VALID_DECISIONS)}",
        )

    records = _list_records(decision=decision)

    return [
        CandidateSummary(
            id=r["id"],
            screened_at=r["screened_at"],
            job_role=r["job_role"],
            candidate_name=r["state"].get("candidate_name", "Unknown"),
            experience_level=r["state"].get("experience_level", "Unknown"),
            skill_match=r["state"].get("skill_match", "Unknown"),
            skill_score=r["state"].get("skill_score", 0),
            final_decision=r["state"].get("final_decision", ""),
            email_sent=r["state"].get("email_sent", False),
        )
        for r in records
    ]


@app.get(
    "/api/candidates/{candidate_id}",
    response_model=ScreenResponse,
    tags=["Candidates"],
    summary="Get full state for a single candidate",
)
def get_candidate(candidate_id: str) -> ScreenResponse:
    record = _get_record(candidate_id)
    if record is None:
        raise HTTPException(
            status_code=status_module.HTTP_404_NOT_FOUND,
            detail=f"Candidate '{candidate_id}' not found.",
        )
    return ScreenResponse(
        id=record["id"],
        screened_at=record["screened_at"],
        job_role=record["job_role"],
        application_text=record.get("application_text", ""),
        state=record["state"],
        action_log=record["action_log"],
    )


@app.get(
    "/api/action-log",
    tags=["Observability"],
    summary="Return the global action log (current server session)",
)
def get_global_action_log() -> dict:
    try:
        from tools.communication_tools import ACTION_LOG
    except Exception as exc:
        raise HTTPException(
            status_code=status_module.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Could not load communication_tools: {exc}",
        ) from exc

    return {"total": len(ACTION_LOG), "entries": list(ACTION_LOG)}


@app.get(
    "/api/stats",
    tags=["Observability"],
    summary="Aggregate screening statistics",
)
def get_stats() -> dict:
    if _DB_AVAILABLE:
        try:
            from db import get_stats as db_stats
            return db_stats()
        except Exception as exc:
            print(f"[WARNING] DB stats failed: {exc}")

    # Fallback — compute from in-memory store
    records = list(_FALLBACK_STORE.values())
    total = len(records)
    if total == 0:
        return {"total": 0, "interviews": 0, "escalations": 0, "rejections": 0, "avg_skill_score": 0.0}

    interviews  = sum(1 for r in records if r["state"].get("final_decision") == "interview")
    escalations = sum(1 for r in records if r["state"].get("final_decision") == "escalate")
    rejections  = sum(1 for r in records if r["state"].get("final_decision") == "reject")
    scores = [r["state"].get("skill_score", 0) for r in records if isinstance(r["state"].get("skill_score"), (int, float))]
    avg = round(sum(scores) / len(scores), 2) if scores else 0.0

    return {
        "total": total,
        "interviews": interviews,
        "escalations": escalations,
        "rejections": rejections,
        "avg_skill_score": avg,
    }


@app.delete(
    "/api/candidates",
    status_code=status_module.HTTP_200_OK,
    tags=["System"],
    summary="Clear all candidates (dev/demo reset)",
)
def clear_all_candidates() -> dict:
    cleared = 0

    if _DB_AVAILABLE:
        try:
            from db import clear_candidates
            cleared = clear_candidates()
        except Exception as exc:
            print(f"[WARNING] DB clear failed: {exc}")

    fallback_count = len(_FALLBACK_STORE)
    _FALLBACK_STORE.clear()
    cleared += fallback_count

    try:
        from tools.communication_tools import ACTION_LOG
        ACTION_LOG.clear()
    except Exception:
        pass

    return {
        "cleared": cleared,
        "message": f"Deleted {cleared} candidate record(s) and reset the action log.",
    }


# ---------------------------------------------------------------------------
# Jobs endpoints
# ---------------------------------------------------------------------------

VALID_STATUSES = {"current", "upcoming", "past"}


@app.get(
    "/api/jobs",
    tags=["Jobs"],
    summary="List all job postings",
)
def list_jobs(
    status: Optional[str] = Query(
        default=None,
        description="Filter by status: current | upcoming | past",
    ),
) -> list[dict]:
    if status is not None and status not in VALID_STATUSES:
        raise HTTPException(
            status_code=status_module.HTTP_400_BAD_REQUEST,
            detail=f"Invalid status '{status}'. Must be one of: {sorted(VALID_STATUSES)}",
        )
    try:
        from db import list_jobs as db_list_jobs
        return db_list_jobs(status=status)
    except Exception as exc:
        raise HTTPException(
            status_code=status_module.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Could not fetch jobs: {exc}",
        ) from exc


@app.get(
    "/api/jobs/{job_id}",
    tags=["Jobs"],
    summary="Get a single job posting",
)
def get_job(job_id: str) -> dict:
    try:
        from db import get_job as db_get_job
        job = db_get_job(job_id)
    except Exception as exc:
        raise HTTPException(
            status_code=status_module.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {exc}",
        ) from exc
    if job is None:
        raise HTTPException(
            status_code=status_module.HTTP_404_NOT_FOUND,
            detail=f"Job '{job_id}' not found.",
        )
    return job


@app.post(
    "/api/jobs",
    status_code=status_module.HTTP_201_CREATED,
    tags=["Jobs"],
    summary="Create a new job posting",
)
def create_job(request: JobRequest) -> dict:
    from db import save_job as db_save_job
    job_id = str(uuid.uuid4())
    posted_at = request.posted_at or datetime.now(timezone.utc).isoformat()
    job = {
        "id":              job_id,
        "title":           request.title,
        "department":      request.department,
        "location":        request.location,
        "employment_type": request.employment_type,
        "status":          request.status,
        "description":     request.description,
        "required_skills": request.required_skills,
        "nice_to_have":    request.nice_to_have,
        "min_years":       request.min_years,
        "salary_range":    request.salary_range,
        "posted_at":       posted_at,
        "closes_at":       request.closes_at,
    }
    try:
        db_save_job(job)
    except Exception as exc:
        raise HTTPException(
            status_code=status_module.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Could not save job: {exc}",
        ) from exc
    return job


@app.put(
    "/api/jobs/{job_id}",
    tags=["Jobs"],
    summary="Update an existing job posting",
)
def update_job(job_id: str, request: JobRequest) -> dict:
    from db import get_job as db_get_job, save_job as db_save_job
    existing = db_get_job(job_id)
    if existing is None:
        raise HTTPException(
            status_code=status_module.HTTP_404_NOT_FOUND,
            detail=f"Job '{job_id}' not found.",
        )
    updated = {
        "id":              job_id,
        "title":           request.title,
        "department":      request.department,
        "location":        request.location,
        "employment_type": request.employment_type,
        "status":          request.status,
        "description":     request.description,
        "required_skills": request.required_skills,
        "nice_to_have":    request.nice_to_have,
        "min_years":       request.min_years,
        "salary_range":    request.salary_range,
        "posted_at":       request.posted_at or existing["posted_at"],
        "closes_at":       request.closes_at,
    }
    try:
        db_save_job(updated)
    except Exception as exc:
        raise HTTPException(
            status_code=status_module.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Could not update job: {exc}",
        ) from exc
    return updated


@app.delete(
    "/api/jobs/{job_id}",
    tags=["Jobs"],
    summary="Delete a job posting",
)
def delete_job(job_id: str) -> dict:
    from db import delete_job as db_delete_job
    try:
        deleted = db_delete_job(job_id)
    except Exception as exc:
        raise HTTPException(
            status_code=status_module.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Could not delete job: {exc}",
        ) from exc
    if not deleted:
        raise HTTPException(
            status_code=status_module.HTTP_404_NOT_FOUND,
            detail=f"Job '{job_id}' not found.",
        )
    return {"deleted": True, "job_id": job_id}


# ---------------------------------------------------------------------------
# Global exception handler
# ---------------------------------------------------------------------------

@app.exception_handler(Exception)
async def unhandled_exception_handler(request, exc: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=status_module.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "success": False,
            "error": "An unexpected server error occurred.",
            "detail": str(exc),
        },
    )
