"""
PostgreSQL database layer for the Recruitment AI system.

Schema
------
  jobs
    id               UUID PRIMARY KEY
    title            TEXT
    department       TEXT
    location         TEXT
    employment_type  TEXT          -- full-time | part-time | contract | internship
    status           TEXT          -- current | upcoming | past
    description      TEXT
    required_skills  JSONB         -- list[str]
    nice_to_have     JSONB         -- list[str]
    min_years        INT
    salary_range     TEXT
    posted_at        TIMESTAMPTZ
    closes_at        TIMESTAMPTZ

  candidates
    id           UUID PRIMARY KEY
    screened_at  TIMESTAMPTZ
    job_role     TEXT
    job_id       TEXT              -- FK reference to jobs.id (nullable)
    state        JSONB             -- serialised RecruitmentState (no messages)
    action_log   JSONB             -- per-candidate action log entries

Usage
-----
  from db import init_db, save_candidate, get_candidate, list_candidates, get_stats
  from db import save_job, get_job, list_jobs, delete_job

Call `init_db()` once at startup (idempotent — uses CREATE TABLE IF NOT EXISTS).
"""
import json
import os
from contextlib import contextmanager
from typing import Optional

import psycopg2
import psycopg2.extras
from psycopg2.pool import ThreadedConnectionPool

_pool: Optional[ThreadedConnectionPool] = None

# ---------------------------------------------------------------------------
# Connection pool
# ---------------------------------------------------------------------------

def _get_pool() -> ThreadedConnectionPool:
    global _pool
    if _pool is None:
        url = os.getenv("DATABASE_URL")
        if not url:
            raise RuntimeError(
                "DATABASE_URL is not set. Add it to your .env file.\n"
                "Example: postgresql://user:password@localhost:5432/recruitment_ai"
            )
        _pool = ThreadedConnectionPool(minconn=1, maxconn=10, dsn=url)
    return _pool


@contextmanager
def _conn():
    pool = _get_pool()
    conn = pool.getconn()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        pool.putconn(conn)


# ---------------------------------------------------------------------------
# Schema initialisation
# ---------------------------------------------------------------------------

_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS jobs (
    id               TEXT        PRIMARY KEY,
    title            TEXT        NOT NULL,
    department       TEXT        NOT NULL DEFAULT '',
    location         TEXT        NOT NULL DEFAULT '',
    employment_type  TEXT        NOT NULL DEFAULT 'full-time',
    status           TEXT        NOT NULL DEFAULT 'current',
    description      TEXT        NOT NULL DEFAULT '',
    required_skills  JSONB       NOT NULL DEFAULT '[]',
    nice_to_have     JSONB       NOT NULL DEFAULT '[]',
    min_years        INT         NOT NULL DEFAULT 0,
    salary_range     TEXT        NOT NULL DEFAULT '',
    posted_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    closes_at        TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_jobs_status
    ON jobs (status);

CREATE INDEX IF NOT EXISTS idx_jobs_posted_at
    ON jobs (posted_at DESC);

CREATE TABLE IF NOT EXISTS candidates (
    id               TEXT PRIMARY KEY,
    screened_at      TIMESTAMPTZ NOT NULL,
    job_role         TEXT        NOT NULL,
    application_text TEXT        NOT NULL DEFAULT '',
    screening_status TEXT        NOT NULL DEFAULT 'pending',
    state            JSONB       NOT NULL DEFAULT '{}',
    action_log       JSONB       NOT NULL DEFAULT '[]'
);

CREATE INDEX IF NOT EXISTS idx_candidates_screened_at
    ON candidates (screened_at DESC);

CREATE INDEX IF NOT EXISTS idx_candidates_decision
    ON candidates ((state->>'final_decision'));


-- idx_candidates_job_id created via migration in init_db()
"""


def init_db() -> None:
    """Create the schema if it does not already exist. Safe to call on every startup."""
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(_CREATE_TABLE)
            # Idempotent migrations for existing candidates table
            cur.execute("""
                ALTER TABLE candidates
                ADD COLUMN IF NOT EXISTS job_id TEXT REFERENCES jobs(id) ON DELETE SET NULL;
            """)
            cur.execute("""
                ALTER TABLE candidates
                ADD COLUMN IF NOT EXISTS application_text TEXT NOT NULL DEFAULT '';
            """)
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_candidates_job_id ON candidates (job_id);
            """)
            cur.execute("""
                ALTER TABLE candidates
                ADD COLUMN IF NOT EXISTS screening_status TEXT NOT NULL DEFAULT 'pending';
            """)
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_candidates_screening_status
                ON candidates (screening_status);
            """)
            # Backfill existing rows that still have 'pending'
            cur.execute("""
                UPDATE candidates
                SET screening_status = state->>'final_decision'
                WHERE screening_status = 'pending'
                  AND state->>'final_decision' IS NOT NULL;
            """)


# ---------------------------------------------------------------------------
# CRUD helpers
# ---------------------------------------------------------------------------

def save_candidate(record: dict) -> None:
    """
    Upsert a candidate record.

    `record` must have keys: id, screened_at, job_role, state, action_log.
    Optional key: job_id (references jobs.id).
    """
    state = record["state"]
    screening_status = state.get("final_decision", "pending") if isinstance(state, dict) else "pending"

    sql = """
        INSERT INTO candidates (id, screened_at, job_role, job_id, application_text, screening_status, state, action_log)
        VALUES (%(id)s, %(screened_at)s, %(job_role)s, %(job_id)s, %(application_text)s, %(screening_status)s, %(state)s, %(action_log)s)
        ON CONFLICT (id) DO UPDATE
            SET state            = EXCLUDED.state,
                action_log       = EXCLUDED.action_log,
                application_text = EXCLUDED.application_text,
                screening_status = EXCLUDED.screening_status;
    """
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, {
                "id":               record["id"],
                "screened_at":      record["screened_at"],
                "job_role":         record["job_role"],
                "job_id":           record.get("job_id"),
                "application_text": record.get("application_text", ""),
                "screening_status": screening_status,
                "state":            json.dumps(record["state"]),
                "action_log":       json.dumps(record["action_log"]),
            })


def get_candidate(candidate_id: str) -> Optional[dict]:
    """Return the full record for `candidate_id`, or None if not found."""
    sql = "SELECT id, screened_at, job_role, state, action_log FROM candidates WHERE id = %s"
    with _conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, (candidate_id,))
            row = cur.fetchone()
    if row is None:
        return None
    return _row_to_record(dict(row))


def list_candidates(decision: Optional[str] = None) -> list[dict]:
    """
    Return summary records for all candidates, newest first.
    Pass `decision` to filter by screening_status column.
    """
    if decision:
        sql = """
            SELECT id, screened_at, job_role, job_id, application_text, screening_status, state, action_log
            FROM   candidates
            WHERE  screening_status = %s
            ORDER  BY screened_at DESC
        """
        params = (decision,)
    else:
        sql = """
            SELECT id, screened_at, job_role, job_id, application_text, screening_status, state, action_log
            FROM   candidates
            ORDER  BY screened_at DESC
        """
        params = ()

    with _conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()

    return [_row_to_record(dict(r)) for r in rows]


def get_stats() -> dict:
    """Return aggregate screening statistics."""
    sql = """
        SELECT
            COUNT(*)                                              AS total,
            COUNT(*) FILTER (WHERE state->>'final_decision' = 'interview')  AS interviews,
            COUNT(*) FILTER (WHERE state->>'final_decision' = 'escalate')   AS escalations,
            COUNT(*) FILTER (WHERE state->>'final_decision' = 'reject')     AS rejections,
            ROUND(
                AVG((state->>'skill_score')::numeric), 2
            )                                                     AS avg_skill_score
        FROM candidates
    """
    with _conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql)
            row = dict(cur.fetchone())

    return {
        "total":          int(row["total"] or 0),
        "interviews":     int(row["interviews"] or 0),
        "escalations":    int(row["escalations"] or 0),
        "rejections":     int(row["rejections"] or 0),
        "avg_skill_score": float(row["avg_skill_score"] or 0.0),
    }


def clear_candidates() -> int:
    """Delete all candidate records. Returns the number of rows deleted."""
    sql = "DELETE FROM candidates"
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
            return cur.rowcount


def query_candidate_by_name(name: str) -> Optional[dict]:
    """
    Return the first candidate whose name (in state->>'candidate_name')
    contains `name` (case-insensitive). Used by resume_tools.
    """
    sql = """
        SELECT id, screened_at, job_role, state, action_log
        FROM   candidates
        WHERE  LOWER(state->>'candidate_name') LIKE LOWER(%s)
        LIMIT  1
    """
    with _conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, (f"%{name}%",))
            row = cur.fetchone()
    if row is None:
        return None
    return _row_to_record(dict(row))


# ---------------------------------------------------------------------------
# Internal helper
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Jobs CRUD
# ---------------------------------------------------------------------------

def save_job(job: dict) -> None:
    """Upsert a job posting. `job` must include: id, title, status, required_skills."""
    sql = """
        INSERT INTO jobs (
            id, title, department, location, employment_type, status,
            description, required_skills, nice_to_have, min_years,
            salary_range, posted_at, closes_at
        )
        VALUES (
            %(id)s, %(title)s, %(department)s, %(location)s, %(employment_type)s,
            %(status)s, %(description)s, %(required_skills)s, %(nice_to_have)s,
            %(min_years)s, %(salary_range)s, %(posted_at)s, %(closes_at)s
        )
        ON CONFLICT (id) DO UPDATE SET
            title           = EXCLUDED.title,
            department      = EXCLUDED.department,
            location        = EXCLUDED.location,
            employment_type = EXCLUDED.employment_type,
            status          = EXCLUDED.status,
            description     = EXCLUDED.description,
            required_skills = EXCLUDED.required_skills,
            nice_to_have    = EXCLUDED.nice_to_have,
            min_years       = EXCLUDED.min_years,
            salary_range    = EXCLUDED.salary_range,
            posted_at       = EXCLUDED.posted_at,
            closes_at       = EXCLUDED.closes_at;
    """
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, {
                "id":              job["id"],
                "title":           job["title"],
                "department":      job.get("department", ""),
                "location":        job.get("location", ""),
                "employment_type": job.get("employment_type", "full-time"),
                "status":          job.get("status", "current"),
                "description":     job.get("description", ""),
                "required_skills": json.dumps(job.get("required_skills", [])),
                "nice_to_have":    json.dumps(job.get("nice_to_have", [])),
                "min_years":       job.get("min_years", 0),
                "salary_range":    job.get("salary_range", ""),
                "posted_at":       job.get("posted_at"),
                "closes_at":       job.get("closes_at"),
            })


def get_job(job_id: str) -> Optional[dict]:
    """Return a single job by id, or None."""
    sql = "SELECT * FROM jobs WHERE id = %s"
    with _conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, (job_id,))
            row = cur.fetchone()
    return _row_to_job(dict(row)) if row else None


def list_jobs(status: Optional[str] = None) -> list[dict]:
    """List all jobs, optionally filtered by status (current|upcoming|past)."""
    if status:
        sql = "SELECT * FROM jobs WHERE status = %s ORDER BY posted_at DESC"
        params = (status,)
    else:
        sql = "SELECT * FROM jobs ORDER BY posted_at DESC"
        params = ()
    with _conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()
    return [_row_to_job(dict(r)) for r in rows]


def delete_job(job_id: str) -> bool:
    """Delete a job by id. Returns True if a row was deleted."""
    sql = "DELETE FROM jobs WHERE id = %s"
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (job_id,))
            return cur.rowcount > 0


def _row_to_job(row: dict) -> dict:
    """Normalise a DB jobs row."""
    required_skills = row["required_skills"] if isinstance(row["required_skills"], list) else json.loads(row["required_skills"] or "[]")
    nice_to_have    = row["nice_to_have"]    if isinstance(row["nice_to_have"],    list) else json.loads(row["nice_to_have"]    or "[]")
    posted_at  = row["posted_at"]
    closes_at  = row["closes_at"]
    if hasattr(posted_at, "isoformat"):
        posted_at = posted_at.isoformat()
    if closes_at and hasattr(closes_at, "isoformat"):
        closes_at = closes_at.isoformat()
    return {
        "id":              row["id"],
        "title":           row["title"],
        "department":      row["department"],
        "location":        row["location"],
        "employment_type": row["employment_type"],
        "status":          row["status"],
        "description":     row["description"],
        "required_skills": required_skills,
        "nice_to_have":    nice_to_have,
        "min_years":       row["min_years"],
        "salary_range":    row["salary_range"],
        "posted_at":       posted_at,
        "closes_at":       closes_at,
    }


def _row_to_record(row: dict) -> dict:
    """Normalise a DB row into the shape expected by the API layer."""
    state      = row["state"]      if isinstance(row["state"],      dict) else json.loads(row["state"])
    action_log = row["action_log"] if isinstance(row["action_log"], list) else json.loads(row["action_log"])
    screened_at = row["screened_at"]
    # psycopg2 returns datetime objects for TIMESTAMPTZ; convert to ISO string
    if hasattr(screened_at, "isoformat"):
        screened_at = screened_at.isoformat()

    return {
        "id":               row["id"],
        "screened_at":      screened_at,
        "job_role":         row["job_role"],
        "job_id":           row.get("job_id"),
        "application_text": row.get("application_text", ""),
        "screening_status": row.get("screening_status", state.get("final_decision", "pending")),
        "state":            state,
        "action_log":       action_log,
    }
