"""
Entry point for the Recruitment Agency Multi-Agent Workflow.
Run: python main.py
"""
import os
from dotenv import load_dotenv

load_dotenv()

from graph import app
from tools.communication_tools import get_action_log

if not os.getenv("OPENAI_API_KEY"):
    raise EnvironmentError("OPENAI_API_KEY is not set. Copy .env.example → .env and add your key.")

# ---------------------------------------------------------------------------
# Test candidates
# ---------------------------------------------------------------------------
TEST_APPLICATIONS = [
    {
        "label": "Senior Python Developer (should → interview)",
        "text": "I have 8 years of experience in software engineering. "
                "I specialise in Python, Django, FastAPI, PostgreSQL, and Docker. "
                "I've led teams of 5+ engineers and deployed production microservices on AWS.",
    },
    {
        "label": "Senior Java Developer (should → escalate)",
        "text": "I have 10 years of experience building enterprise applications using Java and Spring Boot. "
                "I have strong skills in SQL, Microservices, and Kubernetes.",
    },
    {
        "label": "Entry-level C++ Developer (should → reject)",
        "text": "I am a fresh graduate with 1 year of experience in C++ and data structures. "
                "I am eager to learn and grow in a software engineering role.",
    },
    {
        "label": "Mid-level Python Developer (should → interview)",
        "text": "I have 4 years of experience working with Python, FastAPI, and PostgreSQL. "
                "I have built REST APIs and worked with Docker containers.",
    },
]


def run_screening(label: str, application_text: str) -> None:
    print("\n" + "=" * 70)
    print(f"CANDIDATE: {label}")
    print("=" * 70)
    print(f"Application: {application_text}\n")

    result = app.invoke({"application": application_text})

    print("\n--- FINAL RESULT ---")
    print(f"Experience Level : {result.get('experience_level', 'N/A')}")
    print(f"Skill Match      : {result.get('skill_match', 'N/A')} ({result.get('skill_score', 0)}/100)")
    print(f"Decision         : {result.get('final_decision', 'N/A').upper()}")
    print(f"Email Sent       : {result.get('email_sent', False)}")


if __name__ == "__main__":
    for candidate in TEST_APPLICATIONS:
        run_screening(candidate["label"], candidate["text"])

    print("\n\n" + "=" * 70)
    print("ACTION LOG (all emails, invites, decisions)")
    print("=" * 70)
    for entry in get_action_log():
        print(entry)
