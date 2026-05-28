"""
Resume tools used by the HR Screener Agent.
Candidate DB queries hit PostgreSQL via db.py (with in-memory fallback).
"""
import re
from langchain_core.tools import tool

# Skill vocabulary the parser recognises
_SKILL_KEYWORDS = [
    "python", "java", "javascript", "typescript", "c++", "c#", "go", "rust",
    "react", "vue", "angular", "node", "nodejs", "django", "fastapi", "flask",
    "spring", "sql", "nosql", "mongodb", "postgresql", "mysql", "redis",
    "aws", "gcp", "azure", "docker", "kubernetes", "terraform", "ansible",
    "machine learning", "deep learning", "nlp", "langchain", "langgraph",
    "graphql", "rest", "grpc", "kafka", "spark", "airflow", "dbt",
    "next.js", "nextjs", "tailwind", "jest", "pytest", "celery",
]

# Fallback in-memory list used when DB is unavailable
_MEMORY_CANDIDATES = [
    {"name": "Alice Johnson", "email": "alice@example.com", "status": "new"},
    {"name": "Bob Smith",     "email": "bob@example.com",   "status": "new"},
    {"name": "Carol White",   "email": "carol@example.com", "status": "new"},
]


@tool
def parse_resume(application_text: str) -> dict:
    """
    Parse a job application text and extract structured candidate information.
    Returns candidate name, listed skills, and a summary.
    """
    text_lower = application_text.lower()
    found_skills = [skill for skill in _SKILL_KEYWORDS if skill in text_lower]

    return {
        "raw_text": application_text,
        "extracted_skills": found_skills,
        "summary": (
            f"Application parsed. Found {len(found_skills)} skill(s): "
            f"{', '.join(found_skills) or 'none detected'}."
        ),
    }


@tool
def query_candidate_db(candidate_name: str) -> dict:
    """
    Check whether a candidate already exists in the database.
    Queries PostgreSQL; falls back to in-memory list if DB is unavailable.
    Returns the candidate record or a 'not found' response.
    """
    # Try PostgreSQL first
    try:
        from db import query_candidate_by_name
        record = query_candidate_by_name(candidate_name)
        if record:
            state = record.get("state", {})
            return {
                "found": True,
                "record": {
                    "name":     state.get("candidate_name", candidate_name),
                    "job_role": record.get("job_role", ""),
                    "decision": state.get("final_decision", ""),
                    "screened_at": record.get("screened_at", ""),
                },
            }
        return {
            "found": False,
            "record": None,
            "message": "Candidate not found in database. Will be added as new.",
        }
    except Exception:
        pass  # DB unavailable — use in-memory fallback

    for candidate in _MEMORY_CANDIDATES:
        if candidate_name.lower() in candidate["name"].lower():
            return {"found": True, "record": candidate}

    return {
        "found": False,
        "record": None,
        "message": "Candidate not found. Will be added as new.",
    }


@tool
def extract_years_of_experience(application_text: str) -> dict:
    """
    Extract the number of years of experience from application text.
    Returns years as an integer and the detected experience level.
    """
    text_lower = application_text.lower()
    patterns = [
        r"(\d+)\+?\s*years?\s*of\s*experience",
        r"(\d+)\+?\s*years?\s*experience",
        r"experience\s*of\s*(\d+)\+?\s*years?",
        r"(\d+)\+?\s*yrs?\s*of\s*experience",
    ]

    years = 0
    for pattern in patterns:
        match = re.search(pattern, text_lower)
        if match:
            years = int(match.group(1))
            break

    if years <= 3:
        level = "Entry-level"
    elif years <= 7:
        level = "Mid-level"
    else:
        level = "Senior-level"

    return {
        "years_of_experience": years,
        "experience_level": level,
        "note": f"Detected {years} year(s) of experience → {level}",
    }
