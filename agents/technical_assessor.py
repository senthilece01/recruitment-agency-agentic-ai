"""
Technical Assessor Agent
-------------------------
Responsibilities:
  - Fetch the JD for the given job_id from the internal jobs database
  - Run a skill gap analysis comparing candidate skills vs. JD requirements
  - Produce a Match / No Match verdict with a score (0-100)

Tools available:
  - get_job_requirements   — fetch JD from PostgreSQL by job_id
  - run_skill_gap_analysis — compare candidate vs. required skills
  - list_current_jobs      — fallback: list available jobs if job_id is unknown
"""
import json
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent
from langchain_core.messages import HumanMessage

from tools.assessment_tools import get_job_requirements, run_skill_gap_analysis, list_current_jobs
from state import RecruitmentState

_llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)

_SYSTEM_PROMPT = """You are a Technical Assessor Agent at a tech recruitment agency.

Your job is to evaluate how well a candidate's skills match an internal job posting.

Follow these steps exactly:
1. Call `get_job_requirements` with the job_id provided in the prompt to fetch the JD.
2. Call `run_skill_gap_analysis` passing:
   - candidate_skills: the list of skills extracted from the resume
   - required_skills: the required_skills returned from step 1
3. Summarise the result:
   - Job title and required skills
   - Candidate matched skills
   - Missing skills
   - Skill score (0-100)
   - Final verdict: Match or No Match

If the job_id is not found, call `list_current_jobs` and note which jobs are available.
Do NOT use any external search or web data.
"""

_agent = create_react_agent(
    model=_llm,
    tools=[get_job_requirements, run_skill_gap_analysis, list_current_jobs],
    prompt=_SYSTEM_PROMPT,
)


def technical_assessor_node(state: RecruitmentState) -> dict:
    """LangGraph node — runs the Technical Assessor ReAct agent."""
    print("\n[Technical Assessor Agent] Evaluating candidate against internal JD...")

    skills = state.get("skills_extracted", [])
    job_id = state.get("job_id", "")

    prompt_text = (
        f"Job ID            : {job_id}\n"
        f"Candidate skills  : {skills}\n"
        f"Candidate application:\n{state['application']}"
    )

    result = _agent.invoke({
        "messages": [HumanMessage(content=prompt_text)]
    })

    job_title: str = ""
    required_skills: list[str] = []
    matched_skills:  list[str] = []
    missing_skills:  list[str] = []
    skill_score: int = 0
    skill_match: str = "No Match"

    for msg in result["messages"]:
        if hasattr(msg, "name"):
            try:
                data = json.loads(msg.content) if isinstance(msg.content, str) else msg.content
            except Exception:
                continue

            if msg.name == "get_job_requirements" and isinstance(data, dict):
                required_skills = data.get("required_skills", [])
                job_title       = data.get("title", "")

            elif msg.name == "run_skill_gap_analysis" and isinstance(data, dict):
                matched_skills = data.get("matched_skills", [])
                missing_skills = data.get("missing_skills", [])
                skill_score    = data.get("skill_score", 0)
                skill_match    = data.get("skill_match", "No Match")

    print(f"  Job              : {job_title} ({job_id})")
    print(f"  Required skills  : {required_skills}")
    print(f"  Matched skills   : {matched_skills}")
    print(f"  Missing skills   : {missing_skills}")
    print(f"  Score            : {skill_score}/100 → {skill_match}")

    return {
        "job_title":       job_title,
        "required_skills": required_skills,
        "matched_skills":  matched_skills,
        "missing_skills":  missing_skills,
        "skill_score":     skill_score,
        "skill_match":     skill_match,
        "messages":        result["messages"],
    }
