"""
Mock technical assessment tools used by the Technical Assessor Agent.
In production these would query job boards, run real skill tests, etc.
"""
from langchain_core.tools import tool

# Mock job requirements database per role
JOB_REQUIREMENTS_DB = {
    "python developer": {
        "required_skills": ["python", "django", "fastapi", "postgresql", "docker"],
        "nice_to_have": ["kubernetes", "aws", "redis", "celery"],
        "min_years": 2,
    },
    "frontend developer": {
        "required_skills": ["javascript", "react", "typescript", "css", "html"],
        "nice_to_have": ["nextjs", "tailwind", "jest"],
        "min_years": 1,
    },
    "ml engineer": {
        "required_skills": ["python", "machine learning", "deep learning", "nlp", "sql"],
        "nice_to_have": ["langchain", "langgraph", "aws", "docker"],
        "min_years": 3,
    },
    "default": {
        "required_skills": ["python"],
        "nice_to_have": [],
        "min_years": 0,
    },
}

# Mock market demand data
MARKET_DEMAND = {
    "python": {"demand": "Very High", "avg_salary": "$120,000", "trend": "Growing"},
    "java":   {"demand": "High",      "avg_salary": "$115,000", "trend": "Stable"},
    "javascript": {"demand": "Very High", "avg_salary": "$110,000", "trend": "Growing"},
    "react":  {"demand": "Very High", "avg_salary": "$118,000", "trend": "Growing"},
    "c++":    {"demand": "Medium",    "avg_salary": "$105,000", "trend": "Stable"},
    "default":{"demand": "Medium",    "avg_salary": "$90,000",  "trend": "Stable"},
}


@tool
def search_job_requirements(role: str = "python developer") -> dict:
    """
    Search mock job board for requirements of a given role.
    Returns required skills, nice-to-have skills, and minimum years of experience.
    """
    role_key = role.lower().strip()
    requirements = JOB_REQUIREMENTS_DB.get(role_key, JOB_REQUIREMENTS_DB["default"])
    return {
        "role": role,
        "required_skills": requirements["required_skills"],
        "nice_to_have": requirements["nice_to_have"],
        "min_years_required": requirements["min_years"],
    }


@tool
def run_skill_gap_analysis(candidate_skills: list[str], required_skills: list[str]) -> dict:
    """
    Compare candidate's skills against required skills and compute a match score.
    Returns matched skills, missing skills, score (0-100), and match verdict.
    """
    candidate_set = {s.lower().strip() for s in candidate_skills}
    required_set  = {s.lower().strip() for s in required_skills}

    matched  = list(candidate_set & required_set)
    missing  = list(required_set - candidate_set)

    score = int((len(matched) / len(required_set)) * 100) if required_set else 0
    verdict = "Match" if score >= 60 else "No Match"

    return {
        "matched_skills": matched,
        "missing_skills": missing,
        "skill_score": score,
        "skill_match": verdict,
        "summary": f"Matched {len(matched)}/{len(required_set)} required skills. Score: {score}/100 → {verdict}",
    }


@tool
def get_market_demand(skill: str) -> dict:
    """
    Retrieve mock market demand data for a given skill.
    Returns demand level, average salary, and market trend.
    """
    data = MARKET_DEMAND.get(skill.lower().strip(), MARKET_DEMAND["default"])
    return {
        "skill": skill,
        "market_demand": data["demand"],
        "avg_salary": data["avg_salary"],
        "trend": data["trend"],
    }
