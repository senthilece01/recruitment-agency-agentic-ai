# Recruitment Agency — Agentic AI Candidate Screening

![Python](https://img.shields.io/badge/Python-3.11+-blue?logo=python)
![LangGraph](https://img.shields.io/badge/LangGraph-0.3+-green)
![LangChain](https://img.shields.io/badge/LangChain-0.3+-blue)
![OpenAI](https://img.shields.io/badge/OpenAI-GPT--4o--mini-purple?logo=openai)

A **true Agentic AI system** built with LangGraph where each agent has its own LLM instance, dedicated tools, a reasoning loop (ReAct), and a clear responsibility boundary. This is a step up from a simple conditional workflow — each agent autonomously decides _how_ to use its tools to accomplish its goal.

---

## What Makes This "Multi-Agent"?

| Feature         | This Project               |
| --------------- | -------------------------- |
| LLM calls       | 3 independent agents       |
| Tools per agent | 3 tools each               |
| Reasoning loop  | Yes (ReAct)                |
| Agent autonomy  | Yes                        |
| Memory/State    | Shared typed state         |
| Actions taken   | Emails, invites, audit log |

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    LANGGRAPH ORCHESTRATOR                │
│                                                         │
│  START                                                  │
│    │                                                    │
│    ▼                                                    │
│  ┌──────────────────────────────────────┐               │
│  │        HR SCREENER AGENT             │               │
│  │  Tools: parse_resume                 │               │
│  │         extract_years_of_experience  │               │
│  │         query_candidate_db           │               │
│  │  Output: skills, experience_level    │               │
│  └──────────────┬───────────────────────┘               │
│                 │                                       │
│                 ▼                                       │
│  ┌──────────────────────────────────────┐               │
│  │     TECHNICAL ASSESSOR AGENT         │               │
│  │  Tools: search_job_requirements      │               │
│  │         run_skill_gap_analysis       │               │
│  │         get_market_demand            │               │
│  │  Output: skill_match, skill_score    │               │
│  └──────────────┬───────────────────────┘               │
│                 │                                       │
│          route_decision()                               │
│         ┌──────┴──────┐                                 │
│      Match         No Match                             │
│         │         ┌───┴────┐                            │
│         │      Senior   Other                           │
│         │         │       │                             │
│         ▼         ▼       ▼                             │
│  ┌──────────────────────────────────────┐               │
│  │          RECRUITER AGENT             │               │
│  │  Tools: send_email                   │               │
│  │         create_calendar_invite       │               │
│  │         log_candidate_decision       │               │
│  │  Actions: email + invite / escalate  │               │
│  │           / rejection email          │               │
│  └──────────────┬───────────────────────┘               │
│                 │                                       │
│                END                                      │
└─────────────────────────────────────────────────────────┘
```

---

## Agent Details

### Agent 1 — HR Screener (`agents/hr_screener.py`)

**Goal**: Parse the incoming application and extract structured candidate data.

| Tool                          | What it does                                                         |
| ----------------------------- | -------------------------------------------------------------------- |
| `parse_resume`                | Extracts skill keywords from application text                        |
| `extract_years_of_experience` | Detects years of experience via regex → maps to Entry / Mid / Senior |
| `query_candidate_db`          | Checks in-memory DB for duplicate candidates                         |

**Outputs to state**: `skills_extracted`, `years_of_experience`, `experience_level`

---

### Agent 2 — Technical Assessor (`agents/technical_assessor.py`)

**Goal**: Determine if the candidate is technically suitable for the open role.

| Tool                      | What it does                                                    |
| ------------------------- | --------------------------------------------------------------- |
| `search_job_requirements` | Fetches required skills for the target role from mock job board |
| `run_skill_gap_analysis`  | Computes matched/missing skills and a 0–100 score               |
| `get_market_demand`       | Checks market demand for the candidate's top skill              |

**Outputs to state**: `required_skills`, `matched_skills`, `missing_skills`, `skill_score`, `skill_match`

---

### Agent 3 — Recruiter (`agents/recruiter.py`)

**Goal**: Take the final hiring action based on the previous agents' findings.

| Decision      | Condition                  | Actions                                        |
| ------------- | -------------------------- | ---------------------------------------------- |
| **Interview** | skill_match == "Match"     | Send invitation email + create calendar invite |
| **Escalate**  | No match + Senior-level    | Send escalation email to senior recruiter      |
| **Reject**    | No match + Entry/Mid-level | Send polite rejection email                    |

| Tool                     | What it does                                       |
| ------------------------ | -------------------------------------------------- |
| `send_email`             | Logs a mock email to the in-memory action log      |
| `create_calendar_invite` | Creates a mock calendar invite 3 business days out |
| `log_candidate_decision` | Records final decision to audit log                |

---

## Shared State (`state.py`)

```python
class RecruitmentState(TypedDict):
    application: str              # Input
    candidate_name: str           # HR Screener
    years_of_experience: int      # HR Screener
    skills_extracted: list[str]   # HR Screener
    experience_level: str         # HR Screener
    required_skills: list[str]    # Technical Assessor
    matched_skills: list[str]     # Technical Assessor
    missing_skills: list[str]     # Technical Assessor
    skill_match: str              # Technical Assessor
    skill_score: int              # Technical Assessor
    final_decision: str           # Recruiter
    action_taken: str             # Recruiter
    email_sent: bool              # Recruiter
    messages: list                # Shared agent message history
```

---

## Project Structure

```
recruitment_agency_workflow_v2/
├── agents/
│   ├── __init__.py
│   ├── hr_screener.py          # Agent 1 — HR Screener (ReAct)
│   ├── technical_assessor.py   # Agent 2 — Technical Assessor (ReAct)
│   └── recruiter.py            # Agent 3 — Recruiter (ReAct)
├── tools/
│   ├── __init__.py
│   ├── resume_tools.py         # parse_resume, query_candidate_db, extract_years_of_experience
│   ├── assessment_tools.py     # search_job_requirements, run_skill_gap_analysis, get_market_demand
│   └── communication_tools.py  # send_email, create_calendar_invite, log_candidate_decision
├── state.py                    # Shared RecruitmentState TypedDict
├── graph.py                    # LangGraph orchestrator — wires all agents
├── main.py                     # Entry point with 4 test candidates
├── requirements.txt
├── .env.example
└── .gitignore
```

---

## Test Cases

| Candidate      | Experience   | Skills                          | Expected Decision |
| -------------- | ------------ | ------------------------------- | ----------------- |
| 8yr Python Dev | Senior-level | Python, Django, FastAPI, Docker | **Interview**     |
| 10yr Java Dev  | Senior-level | Java, Spring, Kubernetes        | **Escalate**      |
| 1yr C++ Dev    | Entry-level  | C++                             | **Reject**        |
| 4yr Python Dev | Mid-level    | Python, FastAPI, PostgreSQL     | **Interview**     |

---

## Prerequisites

- Python 3.11+
- OpenAI API key

## Setup

```bash
# Clone the repo
git clone https://github.com/senthilece01/recruitment-agency-workflow-v2.git
cd recruitment-agency-workflow-v2

# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env and add your OPENAI_API_KEY
```

## Project Structure

```
recruitment_agency_workflow_v2/
├── agents/
│   ├── hr_screener.py          # Agent 1 — HR Screener (ReAct)
│   ├── technical_assessor.py   # Agent 2 — Technical Assessor (ReAct)
│   └── recruiter.py            # Agent 3 — Recruiter (ReAct)
├── tools/
│   ├── resume_tools.py         # parse_resume, query_candidate_db, extract_years_of_experience
│   ├── assessment_tools.py     # search_job_requirements, run_skill_gap_analysis, get_market_demand
│   └── communication_tools.py  # send_email, create_calendar_invite, log_candidate_decision
├── frontend/
│   └── index.html              # Single-file React dashboard (no build step)
├── state.py                    # Shared RecruitmentState TypedDict
├── graph.py                    # LangGraph orchestrator — wires all agents
├── api.py                      # FastAPI REST server
├── main.py                     # CLI entry point with 4 test candidates
├── requirements.txt
├── .env.example
└── .gitignore
```

---

## Running the System

### Option A — CLI (batch mode)

Runs all 4 test candidates and prints results to the terminal.

```bash
python main.py
```

### Option B — Full Stack (API + Dashboard)

#### 1. Start the Backend API

```bash
uvicorn api:app --reload --port 8000
```

The API server starts at **http://localhost:8000**

#### 2. Start the Frontend Dashboard

```bash
cd frontend
python3 -m http.server 3000
```

The dashboard opens at **http://localhost:3000**

---

## Frontend Dashboard

A rich, dark-themed React dashboard served as a single HTML file — no build step required.

**URL:** http://localhost:3000

### Pages

| Page                    | Description                                                                                                                             |
| ----------------------- | --------------------------------------------------------------------------------------------------------------------------------------- |
| **Dashboard**           | Animated stats counters, SVG donut chart, recent candidates table, 30s auto-refresh                                                     |
| **Screen Candidate**    | Job role selector, application textarea, 4 pre-fill test buttons, live 3-step pipeline progress animation, result card with skill chips |
| **Candidates Pipeline** | Filter tabs (All / Interview / Escalate / Reject), expandable candidate cards with skill scores                                         |
| **Action Log**          | Vertical timeline of emails sent, calendar invites created, and decisions logged                                                        |
| **Agent Architecture**  | Visual diagram of the 3-agent pipeline, state schema, decision routing table                                                            |

### Theme

Dark glassmorphism — `#0f0f1a` background, with colour-coded decisions:

| Decision  | Colour          |
| --------- | --------------- |
| Interview | Green `#06d6a0` |
| Escalate  | Blue `#00b4d8`  |
| Reject    | Red `#e94560`   |

---

## Backend API

A FastAPI REST server wrapping the LangGraph multi-agent workflow.

**Base URL:** http://localhost:8000

### Endpoints

#### Candidates

| Method | Endpoint                             | Description                                               |
| ------ | ------------------------------------ | --------------------------------------------------------- |
| `POST` | `/api/candidates/screen`             | Run the full 3-agent AI pipeline on a job application     |
| `GET`  | `/api/candidates`                    | List all screened candidates (newest first)               |
| `GET`  | `/api/candidates?decision=interview` | Filter by decision: `interview` \| `escalate` \| `reject` |
| `GET`  | `/api/candidates/{id}`               | Full state + action log for one candidate                 |

#### Observability

| Method | Endpoint          | Description                                               |
| ------ | ----------------- | --------------------------------------------------------- |
| `GET`  | `/api/action-log` | Global log of all emails, calendar invites, and decisions |
| `GET`  | `/api/stats`      | Aggregate counts and average skill score                  |

#### System

| Method   | Endpoint          | Description                                            |
| -------- | ----------------- | ------------------------------------------------------ |
| `GET`    | `/health`         | Health check — returns OpenAI key status, no LLM calls |
| `DELETE` | `/api/candidates` | Clear all candidates and reset action log (demo use)   |

### Request / Response Examples

#### Screen a Candidate

```bash
POST /api/candidates/screen
Content-Type: application/json

{
  "application_text": "I have 8 years of Python experience with FastAPI, Django, PostgreSQL and Docker.",
  "job_role": "python developer"
}
```

Response `201 Created`:

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "screened_at": "2026-05-28T03:46:54Z",
  "job_role": "python developer",
  "state": {
    "candidate_name": "Unknown",
    "years_of_experience": 8,
    "experience_level": "Senior-level",
    "skills_extracted": ["python", "fastapi", "django", "postgresql", "docker"],
    "required_skills": ["python", "django", "fastapi", "postgresql", "docker"],
    "matched_skills": ["python", "fastapi", "django", "postgresql", "docker"],
    "missing_skills": [],
    "skill_match": "Match",
    "skill_score": 100,
    "final_decision": "interview",
    "action_taken": "Sent interview invitation and scheduled calendar event.",
    "email_sent": true
  },
  "action_log": [
    {
      "type": "email",
      "to": "candidate@example.com",
      "subject": "Interview Invitation — Python Developer Role",
      "sent_at": "2026-05-28T03:46:54Z",
      "status": "sent (mock)"
    },
    {
      "type": "calendar_invite",
      "date": "2026-05-31",
      "time": "10:00 AM UTC",
      "status": "scheduled (mock)"
    },
    {
      "type": "decision",
      "decision": "interview",
      "reason": "100/100 skill match",
      "logged_at": "2026-05-28T03:46:54Z"
    }
  ]
}
```

#### Get Stats

```bash
GET /api/stats
```

Response:

```json
{
  "total": 4,
  "interviews": 2,
  "escalations": 1,
  "rejections": 1,
  "avg_skill_score": 65.0
}
```

#### Health Check

```bash
GET /health
```

Response:

```json
{
  "status": "ok",
  "openai_key_configured": true,
  "candidates_in_store": 4,
  "timestamp": "2026-05-28T03:46:54Z"
}
```

---

## API Documentation (Swagger)

FastAPI auto-generates interactive API documentation — no extra setup needed.

| UI             | URL                         | Description                                         |
| -------------- | --------------------------- | --------------------------------------------------- |
| **Swagger UI** | http://localhost:8000/docs  | Interactive — try endpoints directly in the browser |
| **ReDoc**      | http://localhost:8000/redoc | Clean reference documentation                       |

> These UIs are served automatically by FastAPI and require no files in the project directory.

---

## How the ReAct Loop Works

Each agent uses LangGraph's `create_react_agent` which implements the **ReAct (Reason + Act)** pattern:

```
Agent receives input
  → Thinks: "What tool should I use first?"
  → Calls tool
  → Observes result
  → Thinks: "What do I do next?"
  → Calls another tool (or finishes)
  → Returns final response
```

This is fundamentally different from a simple prompt → LLM call. The agent autonomously decides _which_ tools to use, _in what order_, and _when to stop_.

---

## Topics

`langgraph` `langchain` `openai` `multi-agent` `react-agent` `agentic-ai` `recruitment` `python` `llm` `tool-use`
