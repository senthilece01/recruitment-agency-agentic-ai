"""
Technical assessment tools used by the Technical Assessor Agent.
Job requirements are fetched from the internal jobs database (PostgreSQL).
Skill gap analysis runs locally against the fetched JD.
Tavily is no longer used — all JD data comes from internal job postings.
"""
from langchain_core.tools import tool


@tool
def get_job_requirements(job_id: str) -> dict:
    """
    Fetch the job description and required skills for a given job_id from the
    internal jobs database. Returns the full JD including required_skills,
    nice_to_have, min_years, title, and description.
    """
    try:
        from db import get_job
        job = get_job(job_id)
        if job:
            return {
                "found": True,
                "job_id": job["id"],
                "title": job["title"],
                "description": job["description"],
                "required_skills": job["required_skills"],
                "nice_to_have": job.get("nice_to_have", []),
                "min_years_required": job.get("min_years", 0),
                "source": "internal_db",
            }
        return {
            "found": False,
            "job_id": job_id,
            "message": f"No job found with id '{job_id}' in the database.",
            "required_skills": [],
            "nice_to_have": [],
            "min_years_required": 0,
            "source": "internal_db",
        }
    except Exception as exc:
        return {
            "found": False,
            "job_id": job_id,
            "message": f"Database error: {exc}",
            "required_skills": [],
            "nice_to_have": [],
            "min_years_required": 0,
            "source": "error",
        }


@tool
def run_skill_gap_analysis(candidate_skills: list[str], required_skills: list[str]) -> dict:
    """
    Compare candidate skills against required skills from the JD and compute a match score.
    Returns matched skills, missing skills, score (0-100), and match verdict.
    """
    candidate_set = {s.lower().strip() for s in candidate_skills}
    required_set  = {s.lower().strip() for s in required_skills}

    matched = list(candidate_set & required_set)
    missing = list(required_set - candidate_set)

    score   = int((len(matched) / len(required_set)) * 100) if required_set else 0
    verdict = "Match" if score >= 60 else "No Match"

    return {
        "matched_skills": matched,
        "missing_skills": missing,
        "skill_score": score,
        "skill_match": verdict,
        "summary": (
            f"Matched {len(matched)}/{len(required_set)} required skills. "
            f"Score: {score}/100 → {verdict}"
        ),
    }


@tool
def list_current_jobs() -> list[dict]:
    """
    Return all currently active job postings from the internal database.
    Useful for the agent to present available roles or select the right job_id.
    """
    try:
        from db import list_jobs
        jobs = list_jobs(status="current")
        return [
            {
                "job_id": j["id"],
                "title": j["title"],
                "department": j["department"],
                "required_skills": j["required_skills"],
                "min_years": j["min_years"],
            }
            for j in jobs
        ]
    except Exception as exc:
        return [{"error": str(exc)}]
