"""
Seed the jobs table with sample current, upcoming, and past job postings.

Run with:
    .venv/bin/python seed_jobs.py
"""
import uuid
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv

load_dotenv()

from db import init_db, save_job

_NOW = datetime.now(timezone.utc)


JOBS = [
    # ── CURRENT ──────────────────────────────────────────────────────────────
    {
        "id": str(uuid.uuid4()),
        "title": "Senior Python Developer",
        "department": "Engineering",
        "location": "Remote",
        "employment_type": "full-time",
        "status": "current",
        "description": (
            "We are looking for a Senior Python Developer to join our backend team. "
            "You will design and build scalable APIs, own microservices, and mentor junior engineers. "
            "Strong experience with FastAPI or Django, PostgreSQL, and cloud deployment is required."
        ),
        "required_skills": ["python", "fastapi", "postgresql", "docker", "aws"],
        "nice_to_have": ["kubernetes", "redis", "celery", "terraform"],
        "min_years": 5,
        "salary_range": "$120,000 – $150,000",
        "posted_at": (_NOW - timedelta(days=10)).isoformat(),
        "closes_at": (_NOW + timedelta(days=20)).isoformat(),
    },
    {
        "id": str(uuid.uuid4()),
        "title": "React Frontend Engineer",
        "department": "Product",
        "location": "Hybrid – Sydney, AU",
        "employment_type": "full-time",
        "status": "current",
        "description": (
            "Join our product team to build beautiful, responsive UIs using React and TypeScript. "
            "You will collaborate closely with designers and backend engineers to deliver delightful user experiences. "
            "Experience with Next.js and Tailwind CSS is a plus."
        ),
        "required_skills": ["javascript", "react", "typescript", "css"],
        "nice_to_have": ["nextjs", "tailwind", "jest", "graphql"],
        "min_years": 3,
        "salary_range": "$95,000 – $120,000",
        "posted_at": (_NOW - timedelta(days=5)).isoformat(),
        "closes_at": (_NOW + timedelta(days=25)).isoformat(),
    },
    {
        "id": str(uuid.uuid4()),
        "title": "ML Engineer – NLP",
        "department": "AI Research",
        "location": "Remote",
        "employment_type": "full-time",
        "status": "current",
        "description": (
            "We are growing our AI Research team and need an ML Engineer with deep NLP expertise. "
            "You will fine-tune LLMs, build RAG pipelines, and integrate AI capabilities into our products. "
            "Familiarity with LangChain or LangGraph is highly desirable."
        ),
        "required_skills": ["python", "machine learning", "nlp", "deep learning", "sql"],
        "nice_to_have": ["langchain", "langgraph", "aws", "docker", "spark"],
        "min_years": 4,
        "salary_range": "$140,000 – $180,000",
        "posted_at": (_NOW - timedelta(days=3)).isoformat(),
        "closes_at": (_NOW + timedelta(days=27)).isoformat(),
    },
    {
        "id": str(uuid.uuid4()),
        "title": "DevOps / Platform Engineer",
        "department": "Infrastructure",
        "location": "Remote",
        "employment_type": "full-time",
        "status": "current",
        "description": (
            "We need an experienced DevOps engineer to manage our cloud infrastructure on AWS. "
            "You will own CI/CD pipelines, Kubernetes clusters, and observability tooling. "
            "Terraform and Ansible experience is required."
        ),
        "required_skills": ["aws", "docker", "kubernetes", "terraform", "ansible"],
        "nice_to_have": ["gcp", "python", "kafka", "airflow"],
        "min_years": 4,
        "salary_range": "$115,000 – $140,000",
        "posted_at": (_NOW - timedelta(days=7)).isoformat(),
        "closes_at": (_NOW + timedelta(days=23)).isoformat(),
    },

    # ── UPCOMING ─────────────────────────────────────────────────────────────
    {
        "id": str(uuid.uuid4()),
        "title": "Full-Stack Engineer (Go + React)",
        "department": "Engineering",
        "location": "London, UK",
        "employment_type": "full-time",
        "status": "upcoming",
        "description": (
            "Starting Q3 2026, we will be hiring a Full-Stack Engineer to help launch our European platform. "
            "You will build high-performance Go services and React frontends. "
            "Strong REST and gRPC API design skills are essential."
        ),
        "required_skills": ["go", "react", "rest", "grpc", "postgresql"],
        "nice_to_have": ["typescript", "docker", "kubernetes", "redis"],
        "min_years": 3,
        "salary_range": "£85,000 – £110,000",
        "posted_at": (_NOW + timedelta(days=15)).isoformat(),
        "closes_at": (_NOW + timedelta(days=60)).isoformat(),
    },
    {
        "id": str(uuid.uuid4()),
        "title": "Data Engineer – Kafka & Spark",
        "department": "Data Platform",
        "location": "Remote",
        "employment_type": "full-time",
        "status": "upcoming",
        "description": (
            "Opening soon: Data Engineer role on our growing Data Platform team. "
            "You will design real-time streaming pipelines using Kafka and Spark, "
            "and build robust dbt models for our analytics warehouse."
        ),
        "required_skills": ["python", "kafka", "spark", "sql", "airflow"],
        "nice_to_have": ["dbt", "aws", "postgresql", "docker"],
        "min_years": 3,
        "salary_range": "$110,000 – $135,000",
        "posted_at": (_NOW + timedelta(days=20)).isoformat(),
        "closes_at": (_NOW + timedelta(days=65)).isoformat(),
    },
    {
        "id": str(uuid.uuid4()),
        "title": "Junior Frontend Developer",
        "department": "Product",
        "location": "Sydney, AU (Onsite)",
        "employment_type": "full-time",
        "status": "upcoming",
        "description": (
            "We will be opening a Junior Frontend position to support our expanding product team. "
            "Ideal for a recent graduate with React and JavaScript experience who wants to grow fast."
        ),
        "required_skills": ["javascript", "react", "css"],
        "nice_to_have": ["typescript", "tailwind", "jest"],
        "min_years": 0,
        "salary_range": "$65,000 – $80,000",
        "posted_at": (_NOW + timedelta(days=10)).isoformat(),
        "closes_at": (_NOW + timedelta(days=50)).isoformat(),
    },

    # ── PAST ─────────────────────────────────────────────────────────────────
    {
        "id": str(uuid.uuid4()),
        "title": "Backend Engineer – Node.js",
        "department": "Engineering",
        "location": "Remote",
        "employment_type": "full-time",
        "status": "past",
        "description": (
            "This role has been filled. We hired a Node.js backend engineer to build "
            "GraphQL APIs and event-driven microservices using Kafka."
        ),
        "required_skills": ["nodejs", "javascript", "graphql", "mongodb", "kafka"],
        "nice_to_have": ["typescript", "docker", "aws", "redis"],
        "min_years": 3,
        "salary_range": "$100,000 – $125,000",
        "posted_at": (_NOW - timedelta(days=90)).isoformat(),
        "closes_at": (_NOW - timedelta(days=30)).isoformat(),
    },
    {
        "id": str(uuid.uuid4()),
        "title": "QA Automation Engineer",
        "department": "Quality",
        "location": "Remote",
        "employment_type": "contract",
        "status": "past",
        "description": (
            "Closed role. We contracted a QA Automation Engineer for a 6-month engagement "
            "to build end-to-end test suites using Pytest and Playwright."
        ),
        "required_skills": ["python", "pytest", "rest", "sql"],
        "nice_to_have": ["javascript", "jest", "docker"],
        "min_years": 2,
        "salary_range": "$85,000 – $100,000",
        "posted_at": (_NOW - timedelta(days=120)).isoformat(),
        "closes_at": (_NOW - timedelta(days=60)).isoformat(),
    },
    {
        "id": str(uuid.uuid4()),
        "title": "Rust Systems Engineer",
        "department": "Infrastructure",
        "location": "Remote",
        "employment_type": "full-time",
        "status": "past",
        "description": (
            "Position closed. We were seeking a Rust engineer to build high-performance "
            "networking components. The role has been successfully filled."
        ),
        "required_skills": ["rust", "grpc", "docker", "aws"],
        "nice_to_have": ["go", "kubernetes", "kafka"],
        "min_years": 5,
        "salary_range": "$130,000 – $160,000",
        "posted_at": (_NOW - timedelta(days=150)).isoformat(),
        "closes_at": (_NOW - timedelta(days=90)).isoformat(),
    },
]


def seed():
    print("Initialising schema...")
    init_db()

    print(f"Seeding {len(JOBS)} jobs...")
    for job in JOBS:
        save_job(job)
        status_label = f"[{job['status'].upper()}]"
        print(f"  {status_label:12} {job['title']}")

    print("\nDone. Jobs seeded successfully.")


if __name__ == "__main__":
    seed()
