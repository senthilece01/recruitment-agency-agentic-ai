# Multi-Agent Systems with LangGraph — Deep Dive

> A comprehensive explanation of what multi-agent AI means, how LangGraph enables it,
> and how this project implements a true multi-agent recruitment workflow.

---

## Table of Contents

1. [What is a Multi-Agent System?](#1-what-is-a-multi-agent-system)
2. [Single LLM Call vs Agent vs Multi-Agent](#2-single-llm-call-vs-agent-vs-multi-agent)
3. [How LangGraph Enables Multi-Agent Systems](#3-how-langgraph-enables-multi-agent-systems)
4. [The ReAct Pattern — How Each Agent Thinks](#4-the-react-pattern--how-each-agent-thinks)
5. [This Project — Architecture Overview](#5-this-project--architecture-overview)
6. [Agent 1 — HR Screener](#6-agent-1--hr-screener)
7. [Agent 2 — Technical Assessor](#7-agent-2--technical-assessor)
8. [Agent 3 — Recruiter](#8-agent-3--recruiter)
9. [Shared State — How Agents Communicate](#9-shared-state--how-agents-communicate)
10. [Orchestrator Graph — How Agents Are Wired](#10-orchestrator-graph--how-agents-are-wired)
11. [End-to-End Flow — Step by Step](#11-end-to-end-flow--step-by-step)
12. [Decision Routing Logic](#12-decision-routing-logic)
13. [Test Cases and Expected Outcomes](#13-test-cases-and-expected-outcomes)
14. [v1 vs v2 — What Changed and Why](#14-v1-vs-v2--what-changed-and-why)
15. [Key LangGraph Concepts Used](#15-key-langgraph-concepts-used)

---

## 1. What is a Multi-Agent System?

A **multi-agent system (MAS)** is an architecture where multiple independent AI agents
collaborate to solve a problem that would be too complex, too broad, or too risky
for a single agent to handle alone.

Each agent in the system:

- Has a **specific, bounded responsibility** (single-responsibility principle)
- Has its own **set of tools** it can use
- Has its own **LLM instance** with a tailored system prompt
- Runs its own **internal reasoning loop**
- Reads from and writes to a **shared state** to pass context to other agents

Think of it like a company department structure:

```
Company (Orchestrator)
  ├── HR Department    (Agent 1 — screens candidates)
  ├── Tech Department  (Agent 2 — assesses skills)
  └── Recruitment Desk (Agent 3 — takes final action)
```

Each department does its own job. The output of one department becomes the
input context for the next.

---

## 2. Single LLM Call vs Agent vs Multi-Agent

Understanding the spectrum of complexity helps clarify what "multi-agent" truly means.

### Level 1 — Single LLM Call

```python
response = llm.invoke("Is this candidate suitable? " + resume_text)
```

- One prompt, one response
- No tools, no memory, no reasoning loop
- Stateless — each call is independent
- Suitable for: simple classification, summarisation

### Level 2 — Single Agent with Tools (ReAct)

```python
agent = create_react_agent(llm, tools=[search, calculator])
agent.invoke({"messages": [HumanMessage("Research this candidate")]})
```

- One LLM with multiple tools
- Autonomous tool selection and sequencing
- Internal reasoning loop (think → act → observe → repeat)
- Suitable for: tasks requiring information gathering

### Level 3 — Multi-Agent System (This Project)

```
Agent 1 (HR Screener) → Agent 2 (Technical Assessor) → Agent 3 (Recruiter)
```

- Multiple independent agents, each with their own LLM + tools
- Each agent has a clearly scoped responsibility
- Agents communicate through a shared typed state
- An orchestrator (LangGraph StateGraph) coordinates execution order
- Suitable for: complex workflows with distinct phases, parallel workstreams,
  or tasks requiring domain specialisation

### Comparison Table

| Dimension             | Single LLM Call | Single Agent   | Multi-Agent (This Project) |
|-----------------------|-----------------|----------------|----------------------------|
| LLM instances         | 1               | 1              | 3 (one per agent)          |
| Tools available       | None            | Shared pool    | Dedicated per agent        |
| Reasoning loop        | No              | Yes (ReAct)    | Yes (per agent)            |
| Specialisation        | None            | Partial        | Full (bounded scope)       |
| Inter-agent comms     | N/A             | N/A            | Shared state               |
| Scalability           | Low             | Medium         | High                       |
| Failure isolation     | None            | None           | Per-agent                  |
| Parallelisable        | No              | No             | Yes (with LangGraph)       |

---

## 3. How LangGraph Enables Multi-Agent Systems

LangGraph is a framework built on top of LangChain that models AI workflows as
**directed graphs** — nodes are processing steps (agents, functions), edges are
transitions between them.

### Core concepts

#### StateGraph
The central object. You define:
- A **state schema** (TypedDict) that all nodes share
- **Nodes** — functions or agents that read/write the state
- **Edges** — connections between nodes (fixed or conditional)

```python
from langgraph.graph import StateGraph, START, END

workflow = StateGraph(RecruitmentState)
workflow.add_node("hr_screener", hr_screener_node)
workflow.add_node("technical_assessor", technical_assessor_node)
workflow.add_node("recruiter", recruiter_node)
```

#### Edges and Conditional Edges

Fixed edges always go to the next node:
```python
workflow.add_edge("hr_screener", "technical_assessor")
```

Conditional edges route based on state:
```python
workflow.add_conditional_edges("technical_assessor", route_decision)
```

#### `create_react_agent`

LangGraph's prebuilt function that wraps an LLM + tools into a ReAct agent:

```python
from langgraph.prebuilt import create_react_agent

agent = create_react_agent(
    model=llm,
    tools=[tool_1, tool_2, tool_3],
    prompt="You are a specialist who..."
)
```

The agent internally runs a mini-graph:
```
input → llm_call → [tool_calls?] → tool_execution → llm_call → ... → final_response
```

---

## 4. The ReAct Pattern — How Each Agent Thinks

**ReAct** stands for **Re**asoning + **Act**ing. It is the core reasoning pattern
used by each agent in this project.

### The Loop

```
┌─────────────────────────────────────────┐
│                                         │
│  1. THINK  — "What do I need to do?"   │
│       ↓                                 │
│  2. ACT    — "Call tool X with args Y" │
│       ↓                                 │
│  3. OBSERVE — "The tool returned Z"    │
│       ↓                                 │
│  4. THINK  — "Now what?"               │
│       ↓                                 │
│  5. ACT / FINISH                        │
│                                         │
└─────────────────────────────────────────┘
```

### Concrete Example — HR Screener Agent

Given input: `"I have 8 years of experience in Python and Django"`

```
THINK:  I need to parse this resume first.
ACT:    Call parse_resume("I have 8 years of experience in Python and Django")
OBSERVE: {"extracted_skills": ["python", "django"], "summary": "Found 2 skills"}

THINK:  Now extract years of experience.
ACT:    Call extract_years_of_experience("I have 8 years of experience...")
OBSERVE: {"years_of_experience": 8, "experience_level": "Senior-level"}

THINK:  Check if candidate exists in DB.
ACT:    Call query_candidate_db("Unknown")
OBSERVE: {"found": false, "message": "Candidate not found, will be added as new"}

THINK:  I have all the information I need. I can summarise now.
FINISH: Returns structured summary with skills + experience level
```

This is fundamentally different from a single prompt. The agent **autonomously
decides** the sequence of tool calls based on its observations.

---

## 5. This Project — Architecture Overview

```
 INPUT: Job application text (free-form string)
        │
        ▼
┌────────────────────────────────────────────────────────────────┐
│                    LANGGRAPH ORCHESTRATOR                      │
│                      (graph.py)                                │
│                                                                │
│  ┌─────────────────────────────────────────────────────────┐  │
│  │               AGENT 1: HR SCREENER                      │  │
│  │               agents/hr_screener.py                     │  │
│  │                                                         │  │
│  │  LLM: gpt-4o-mini   System Prompt: HR specialist        │  │
│  │  Tools:                                                  │  │
│  │    ● parse_resume           → extract skill keywords    │  │
│  │    ● extract_years_of_exp   → detect experience level   │  │
│  │    ● query_candidate_db     → check for duplicates      │  │
│  │                                                         │  │
│  │  Writes to state:                                       │  │
│  │    skills_extracted, years_of_experience, experience_level│  │
│  └────────────────────────┬────────────────────────────────┘  │
│                           │ (fixed edge)                       │
│  ┌────────────────────────▼────────────────────────────────┐  │
│  │           AGENT 2: TECHNICAL ASSESSOR                   │  │
│  │           agents/technical_assessor.py                  │  │
│  │                                                         │  │
│  │  LLM: gpt-4o-mini   System Prompt: Tech assessor        │  │
│  │  Tools:                                                  │  │
│  │    ● search_job_requirements → fetch role requirements  │  │
│  │    ● run_skill_gap_analysis  → compare skills, score    │  │
│  │    ● get_market_demand       → market context           │  │
│  │                                                         │  │
│  │  Reads from state: skills_extracted                     │  │
│  │  Writes to state:                                       │  │
│  │    required_skills, matched_skills, missing_skills,     │  │
│  │    skill_score, skill_match                             │  │
│  └────────────────────────┬────────────────────────────────┘  │
│                           │ (conditional edge)                 │
│                    route_decision()                            │
│              ┌────────────┼────────────┐                       │
│           Match      Senior+NoMatch  Other                     │
│              │            │            │                       │
│              └────────────▼────────────┘                       │
│  ┌─────────────────────────────────────────────────────────┐  │
│  │               AGENT 3: RECRUITER                        │  │
│  │               agents/recruiter.py                       │  │
│  │                                                         │  │
│  │  LLM: gpt-4o-mini   System Prompt: Recruiter specialist │  │
│  │  Tools:                                                  │  │
│  │    ● send_email              → notify candidate         │  │
│  │    ● create_calendar_invite  → schedule interview       │  │
│  │    ● log_candidate_decision  → audit trail              │  │
│  │                                                         │  │
│  │  Reads from state: experience_level, skill_match, score │  │
│  │  Writes to state:                                       │  │
│  │    final_decision, action_taken, email_sent             │  │
│  └────────────────────────┬────────────────────────────────┘  │
│                           │                                    │
└───────────────────────────┼────────────────────────────────────┘
                            │
                           END
        │
        ▼
 OUTPUT: Updated RecruitmentState with all fields populated
```

---

## 6. Agent 1 — HR Screener

**File**: [agents/hr_screener.py](agents/hr_screener.py)

### Responsibility
Extract structured information from the raw application text.
This agent does NOT judge the candidate — it only gathers facts.

### System Prompt (summarised)
> "You are an experienced HR Screener. Parse the application,
> extract skills, determine experience level, and check the candidate DB.
> Do not make hiring decisions — only gather data."

### Tools

| Tool | Input | Output |
|------|-------|--------|
| `parse_resume` | application text | `{extracted_skills, summary}` |
| `extract_years_of_experience` | application text | `{years_of_experience, experience_level}` |
| `query_candidate_db` | candidate name | `{found, record}` |

### State contributions
```python
{
  "skills_extracted":    ["python", "django", "fastapi"],
  "years_of_experience": 8,
  "experience_level":    "Senior-level",
  "candidate_name":      "Unknown"
}
```

### Why a separate agent for this?
In a real system, parsing resumes could involve:
- PDF text extraction
- NLP named-entity recognition
- Database lookups across multiple sources
- Deduplication checks

Keeping this isolated means the HR Screener can be upgraded (e.g., swap mock
tools for real PDF parsing) without touching the rest of the system.

---

## 7. Agent 2 — Technical Assessor

**File**: [agents/technical_assessor.py](agents/technical_assessor.py)

### Responsibility
Evaluate the technical fit of the candidate against the open role requirements.
This agent is domain-aware — it knows what skills are needed and can score candidates.

### System Prompt (summarised)
> "You are a Technical Assessor. Fetch the job requirements, run a skill gap
> analysis against the candidate's skills, and produce a Match/No Match verdict
> with a 0-100 score."

### Tools

| Tool | Input | Output |
|------|-------|--------|
| `search_job_requirements` | role name | `{required_skills, nice_to_have, min_years}` |
| `run_skill_gap_analysis` | candidate skills + required skills | `{matched, missing, score, verdict}` |
| `get_market_demand` | skill name | `{demand, avg_salary, trend}` |

### Scoring logic (inside `run_skill_gap_analysis`)

```
score = (matched_skills / required_skills) × 100

score ≥ 60  →  "Match"
score < 60  →  "No Match"
```

### State contributions
```python
{
  "required_skills": ["python", "django", "fastapi", "postgresql", "docker"],
  "matched_skills":  ["python", "django", "fastapi"],
  "missing_skills":  ["postgresql", "docker"],
  "skill_score":     60,
  "skill_match":     "Match"
}
```

### Why a separate agent for this?
The technical assessment is a completely different concern from HR screening.
In a real system this agent could:
- Query live job boards (LinkedIn, Indeed)
- Run actual coding challenges
- Compare against industry benchmarks
- Use a different, more technical LLM model

Separation means you can tune the Technical Assessor independently.

---

## 8. Agent 3 — Recruiter

**File**: [agents/recruiter.py](agents/recruiter.py)

### Responsibility
Take the **final action** based on the complete picture built by the first two agents.
This is the only agent that performs real-world side effects (emails, calendar, audit log).

### System Prompt (summarised)
> "You are a Recruiter. Based on skill_match and experience_level, decide:
> interview / escalate / reject. Then send the appropriate email, create a
> calendar invite if needed, and log the decision."

### Decision logic

```
skill_match == "Match"
    → decision = "interview"
    → send_email (invitation)
    → create_calendar_invite (HR Interview with Sarah)
    → log_candidate_decision

skill_match == "No Match" AND experience_level == "Senior-level"
    → decision = "escalate"
    → send_email (senior recruiter review notification)
    → log_candidate_decision

Otherwise (No Match + Entry/Mid-level)
    → decision = "reject"
    → send_email (polite rejection)
    → log_candidate_decision
```

### Tools

| Tool | What it does (mock) |
|------|---------------------|
| `send_email` | Appends email record to in-memory `ACTION_LOG` |
| `create_calendar_invite` | Appends invite record, schedules 3 business days out |
| `log_candidate_decision` | Appends audit record with timestamp |

### State contributions
```python
{
  "final_decision": "interview",
  "action_taken":   "Interview scheduled, email sent to candidate.",
  "email_sent":     True
}
```

### Why a separate agent for this?
Actions have side effects. Keeping all communication and logging in one agent:
- Makes it easy to audit what was sent
- Lets you swap mock tools for real integrations (Resend, Google Calendar)
- Prevents other agents from accidentally firing emails mid-workflow

---

## 9. Shared State — How Agents Communicate

Agents do **not** call each other directly. They communicate exclusively through
the **shared `RecruitmentState`**.

This is a key design principle in LangGraph multi-agent systems:

```
Agent 1 → writes to state → Agent 2 reads state → writes to state → Agent 3 reads state
```

### Full state schema

```python
# state.py
class RecruitmentState(TypedDict):

    # ── Input ──────────────────────────────────────────────────
    application: str                # Raw application text (input)

    # ── HR Screener outputs ────────────────────────────────────
    candidate_name: str             # Inferred or "Unknown"
    years_of_experience: int        # Numeric years
    skills_extracted: list[str]     # All detected skill keywords
    experience_level: str           # Entry-level | Mid-level | Senior-level

    # ── Technical Assessor outputs ─────────────────────────────
    required_skills: list[str]      # Skills required for the role
    matched_skills:  list[str]      # Intersection of candidate + required
    missing_skills:  list[str]      # Required skills the candidate lacks
    skill_match:     str            # Match | No Match
    skill_score:     int            # 0–100

    # ── Recruiter outputs ──────────────────────────────────────
    final_decision:  str            # interview | escalate | reject
    action_taken:    str            # Description of action taken
    email_sent:      bool           # Whether an email was sent

    # ── Shared message history ─────────────────────────────────
    messages: Annotated[list, add_messages]  # All agent messages merged
```

### Why TypedDict?

TypedDict gives:
- **Type safety** — catch state field errors early
- **Clarity** — every agent knows exactly what it can read/write
- **Documentation** — the state schema is self-documenting

---

## 10. Orchestrator Graph — How Agents Are Wired

**File**: [graph.py](graph.py)

The orchestrator is a `StateGraph` that defines the execution order and routing.

```python
workflow = StateGraph(RecruitmentState)

# Register the three agent nodes
workflow.add_node("hr_screener",        hr_screener_node)
workflow.add_node("technical_assessor", technical_assessor_node)
workflow.add_node("recruiter",          recruiter_node)

# Fixed edges — always execute in this order
workflow.add_edge(START,          "hr_screener")
workflow.add_edge("hr_screener",  "technical_assessor")

# Conditional edge — routes based on state after Technical Assessor
workflow.add_conditional_edges("technical_assessor", route_decision)

# Recruiter always ends the workflow
workflow.add_edge("recruiter", END)
```

### Visual graph

```
START
  │
  ▼
hr_screener ──────────────────────────────────────────►  (fixed edge)
  │
  ▼
technical_assessor ────────────────────────────────────►  (fixed edge)
  │
  ▼
route_decision()   ─── "Match" ─────────────────────────►
                   ─── "Senior + No Match" ──────────────►  recruiter
                   ─── "Other" ─────────────────────────►
                                                           │
                                                           ▼
                                                          END
```

### The `route_decision` function

```python
def route_decision(state: RecruitmentState) -> str:
    skill_match      = state.get("skill_match", "No Match")
    experience_level = state.get("experience_level", "Entry-level")

    if skill_match == "Match":
        return "recruiter"          # → interview path

    if experience_level == "Senior-level":
        return "recruiter"          # → escalate path

    return "recruiter"              # → reject path
```

Note: all three paths route to the same Recruiter node in this design.
The **Recruiter Agent itself** reads the state and decides which action to take.
This separates routing logic (graph layer) from business logic (agent layer).

---

## 11. End-to-End Flow — Step by Step

Let's trace a complete run for:

> `"I have 8 years of experience in Python, Django, FastAPI, PostgreSQL, and Docker."`

### Step 1 — Input enters the graph

```python
app.invoke({"application": "I have 8 years of experience in Python..."})
```

State at this point:
```
application = "I have 8 years of experience in Python..."
(all other fields: empty / default)
```

---

### Step 2 — HR Screener Agent runs

**Internal ReAct loop:**

```
THINK:  Parse the resume first.
ACT:    parse_resume("I have 8 years of experience in Python, Django...")
OBSERVE: {extracted_skills: ["python", "django", "fastapi", "postgresql", "docker"]}

THINK:  Now extract years and level.
ACT:    extract_years_of_experience("I have 8 years...")
OBSERVE: {years_of_experience: 8, experience_level: "Senior-level"}

THINK:  Check candidate DB.
ACT:    query_candidate_db("Unknown")
OBSERVE: {found: false, message: "Will be added as new"}

FINISH: Structured summary ready.
```

**State after HR Screener:**
```
skills_extracted    = ["python", "django", "fastapi", "postgresql", "docker"]
years_of_experience = 8
experience_level    = "Senior-level"
candidate_name      = "Unknown"
```

---

### Step 3 — Technical Assessor Agent runs

**Internal ReAct loop:**

```
THINK:  Fetch job requirements for Python Developer role.
ACT:    search_job_requirements("python developer")
OBSERVE: {required_skills: ["python", "django", "fastapi", "postgresql", "docker"]}

THINK:  Run skill gap analysis.
ACT:    run_skill_gap_analysis(
          candidate_skills=["python", "django", "fastapi", "postgresql", "docker"],
          required_skills=["python", "django", "fastapi", "postgresql", "docker"]
        )
OBSERVE: {matched: ["python","django","fastapi","postgresql","docker"],
          missing: [], score: 100, skill_match: "Match"}

THINK:  Check market demand for Python.
ACT:    get_market_demand("python")
OBSERVE: {demand: "Very High", avg_salary: "$120,000", trend: "Growing"}

FINISH: Summary ready.
```

**State after Technical Assessor:**
```
required_skills = ["python", "django", "fastapi", "postgresql", "docker"]
matched_skills  = ["python", "django", "fastapi", "postgresql", "docker"]
missing_skills  = []
skill_score     = 100
skill_match     = "Match"
```

---

### Step 4 — Router evaluates state

```python
route_decision(state)
# skill_match == "Match" → returns "recruiter"
```

---

### Step 5 — Recruiter Agent runs

**Internal ReAct loop:**

```
THINK:  skill_match=Match → interview decision.
ACT:    send_email(
          to="candidate@example.com",
          subject="Interview Invitation — Python Developer Role",
          body="Congratulations! We'd like to invite you for an HR interview..."
        )
OBSERVE: {success: true, sent_at: "2026-05-27T10:30:00"}

THINK:  Create calendar invite since it's an interview.
ACT:    create_calendar_invite(
          candidate_name="Unknown",
          interview_type="HR Interview",
          interviewer="Sarah (HR)"
        )
OBSERVE: {success: true, date: "2026-05-30", time: "10:00 AM UTC"}

THINK:  Log the decision for audit.
ACT:    log_candidate_decision(
          candidate_name="Unknown",
          decision="interview",
          reason="100/100 skill match — all required Python Developer skills present"
        )
OBSERVE: {success: true, logged_at: "2026-05-27T10:30:01"}

FINISH: All actions complete.
```

**State after Recruiter:**
```
final_decision = "interview"
email_sent     = True
action_taken   = "Interview scheduled, email sent, calendar invite created."
```

---

### Step 6 — Graph reaches END

The complete, populated state is returned to the caller in `main.py`.

---

## 12. Decision Routing Logic

All possible outcomes and their conditions:

```
┌──────────────────────┬────────────────────┬──────────────┬──────────────────────────────┐
│ Candidate Profile    │ skill_match        │ exp_level    │ Outcome                      │
├──────────────────────┼────────────────────┼──────────────┼──────────────────────────────┤
│ Python dev, 8yrs     │ Match (100/100)    │ Senior       │ INTERVIEW (email + calendar) │
│ Python dev, 4yrs     │ Match (60/100)     │ Mid-level    │ INTERVIEW (email + calendar) │
│ Java dev, 10yrs      │ No Match (0/100)   │ Senior       │ ESCALATE (senior recruiter)  │
│ C++ dev, 1yr         │ No Match (0/100)   │ Entry-level  │ REJECT (polite email)        │
│ C++ dev, 5yrs        │ No Match (0/100)   │ Mid-level    │ REJECT (polite email)        │
└──────────────────────┴────────────────────┴──────────────┴──────────────────────────────┘
```

---

## 13. Test Cases and Expected Outcomes

Defined in [main.py](main.py):

### Test 1 — Senior Python Developer → INTERVIEW
```
Input  : "8 years experience, Python, Django, FastAPI, PostgreSQL, Docker"
HR     : Senior-level, 8 years, skills: [python, django, fastapi, postgresql, docker]
Tech   : Score 100/100, Match
Action : Email invitation + Calendar invite (HR Interview, 3 days out)
```

### Test 2 — Senior Java Developer → ESCALATE
```
Input  : "10 years experience, Java, Spring Boot, SQL, Kubernetes"
HR     : Senior-level, 10 years, skills: [java, sql, kubernetes]
Tech   : Score 0/100 (no Python skills), No Match
Action : Escalation email to senior recruiter
```

### Test 3 — Entry-level C++ Developer → REJECT
```
Input  : "1 year experience, C++, data structures"
HR     : Entry-level, 1 year, skills: [c++]
Tech   : Score 0/100, No Match
Action : Polite rejection email
```

### Test 4 — Mid-level Python Developer → INTERVIEW
```
Input  : "4 years experience, Python, FastAPI, PostgreSQL"
HR     : Mid-level, 4 years, skills: [python, fastapi, postgresql]
Tech   : Score 60/100 (python, fastapi, postgresql matched; django, docker missing), Match
Action : Email invitation + Calendar invite (HR Interview, 3 days out)
```

---

## 14. v1 vs v2 — What Changed and Why

### v1 — Simple Conditional Workflow (recruitment_agency_workflow.ipynb)

```python
# All nodes use the same shared llm instance
llm = ChatOpenAI()

# Nodes are plain Python functions with a single LLM call each
def categorize_experience(state):
    prompt = ChatPromptTemplate.from_template("Categorise: {application}")
    return {"experience_level": (prompt | llm).invoke(...).content}

def assess_skillset(state):
    prompt = ChatPromptTemplate.from_template("Assess skills: {application}")
    return {"skill_match": (prompt | llm).invoke(...).content}
```

**Limitations:**
- No tools — agents cannot look anything up or take actions
- No ReAct loop — each node is one prompt → one response
- No side effects — no emails, no logs, no real actions
- Hard to extend — adding a new capability means editing a function

---

### v2 — True Multi-Agent System (this project)

```python
# Each agent has its own LLM, tools, and system prompt
hr_agent = create_react_agent(
    model=ChatOpenAI(model="gpt-4o-mini"),
    tools=[parse_resume, extract_years_of_experience, query_candidate_db],
    prompt="You are an HR Screener..."
)

technical_agent = create_react_agent(
    model=ChatOpenAI(model="gpt-4o-mini"),
    tools=[search_job_requirements, run_skill_gap_analysis, get_market_demand],
    prompt="You are a Technical Assessor..."
)

recruiter_agent = create_react_agent(
    model=ChatOpenAI(model="gpt-4o-mini"),
    tools=[send_email, create_calendar_invite, log_candidate_decision],
    prompt="You are a Recruiter..."
)
```

**What changed:**

| Dimension | v1 | v2 |
|---|---|---|
| Architecture | Single graph, simple functions | Multi-agent graph, ReAct agents |
| Tools | None | 3 tools per agent (9 total) |
| Reasoning | Single LLM call per node | Full ReAct loop per agent |
| Side effects | None | Emails, calendar, audit log |
| State richness | 4 fields | 15 fields |
| Extensibility | Modify functions | Swap/add tools or agents |
| Real-world readiness | Prototype | Production-extensible |

---

## 15. Key LangGraph Concepts Used

### `StateGraph`
The graph container. Holds nodes, edges, and the state schema.

### `TypedDict` State
Strongly-typed shared state. Every agent reads and writes to this.

### `create_react_agent`
Builds a ReAct agent from an LLM + tools. Manages the internal
think → act → observe loop automatically.

### `@tool` decorator
Converts a plain Python function into a LangChain tool that an agent
can discover and call.

```python
from langchain_core.tools import tool

@tool
def parse_resume(application_text: str) -> dict:
    """Parse a job application and extract skills."""
    ...
```

The docstring becomes the tool description — the LLM reads it to decide
whether to call the tool.

### `add_messages` reducer
Merges message lists from multiple agents into a single shared history.

```python
messages: Annotated[list, add_messages]
```

Without this, writing to `messages` from multiple agents would overwrite
instead of append.

### `add_conditional_edges`
Routes execution to different nodes based on a function that inspects state.

```python
workflow.add_conditional_edges("technical_assessor", route_decision)
```

### `workflow.compile()`
Validates the graph and returns a runnable `CompiledGraph` with `.invoke()`,
`.stream()`, and `.astream()` methods.

---

## Summary

This project demonstrates that a **true multi-agent system** is defined by:

1. **Independent agents** — each with its own LLM, tools, and responsibility
2. **ReAct reasoning** — agents think and act autonomously, not just respond
3. **Shared typed state** — the medium through which agents communicate
4. **Orchestrated execution** — a graph that defines order and routing
5. **Real side effects** — agents take actions, not just produce text

LangGraph makes all of this possible by treating AI workflows as **graphs**,
giving you full control over execution order, state management, and agent
boundaries — while `create_react_agent` handles the internal reasoning loop
for each agent automatically.
