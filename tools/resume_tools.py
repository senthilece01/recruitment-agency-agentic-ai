"""
Mock resume tools used by the HR Screener Agent.
In production these would parse PDFs, query a real DB, etc.
"""
from langchain_core.tools import tool

# In-memory candidate database
CANDIDATE_DB = [
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
    # Mock extraction — in production this would use an NLP pipeline or LLM
    skills_keywords = [
        "python", "java", "javascript", "typescript", "c++", "c#", "go", "rust",
        "react", "node", "django", "fastapi", "flask", "spring", "sql", "nosql",
        "mongodb", "postgresql", "aws", "gcp", "azure", "docker", "kubernetes",
        "machine learning", "deep learning", "nlp", "langchain", "langgraph",
    ]

    text_lower = application_text.lower()
    found_skills = [skill for skill in skills_keywords if skill in text_lower]

    return {
        "raw_text": application_text,
        "extracted_skills": found_skills,
        "summary": f"Application parsed. Found {len(found_skills)} skill(s): {', '.join(found_skills) or 'none detected'}.",
    }


@tool
def query_candidate_db(candidate_name: str) -> dict:
    """
    Query the in-memory candidate database to check if a candidate already exists.
    Returns candidate record or a 'not found' response.
    """
    for candidate in CANDIDATE_DB:
        if candidate_name.lower() in candidate["name"].lower():
            return {"found": True, "record": candidate}
    return {"found": False, "record": None, "message": "Candidate not found in database. Will be added as new."}


@tool
def extract_years_of_experience(application_text: str) -> dict:
    """
    Extract the number of years of experience from application text.
    Returns years as an integer and the detected experience level.
    """
    import re

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

    if years == 0:
        level = "Entry-level"
    elif years <= 3:
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
