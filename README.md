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

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env and add your OPENAI_API_KEY
```

## Run

```bash
python main.py
```

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
