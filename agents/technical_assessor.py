"""
Technical Assessor Agent
-------------------------
Responsibilities:
  - Fetch job requirements for the target role
  - Run a skill gap analysis comparing candidate vs. requirements
  - Check market demand for key candidate skills
  - Produce a Match / No Match verdict with a score

Tools available:
  - search_job_requirements
  - run_skill_gap_analysis
  - get_market_demand
"""
import json
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent
from langchain_core.messages import HumanMessage

from tools.assessment_tools import search_job_requirements, run_skill_gap_analysis, get_market_demand
from state import RecruitmentState

_llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)

_SYSTEM_PROMPT = """You are a Technical Assessor Agent at a tech recruitment agency.

Your job is to evaluate how well a candidate's skills match the open role.

Follow these steps:
1. Use `search_job_requirements` with role="python developer" to get the required skills.
2. Use `run_skill_gap_analysis` passing the candidate's skills and the required skills you just retrieved.
3. Use `get_market_demand` for the top skill in the candidate's profile (if any).

After the tool calls, summarise:
- Required skills for the role
- Candidate's matched skills
- Missing skills
- Skill score (0-100)
- Final verdict: Match or No Match
"""

_agent = create_react_agent(
    model=_llm,
    tools=[search_job_requirements, run_skill_gap_analysis, get_market_demand],
    prompt=_SYSTEM_PROMPT,
)


def technical_assessor_node(state: RecruitmentState) -> dict:
    """LangGraph node — runs the Technical Assessor ReAct agent."""
    print("\n[Technical Assessor Agent] Evaluating candidate skills...")

    skills = state.get("skills_extracted", [])
    prompt_text = (
        f"Candidate application: {state['application']}\n"
        f"Skills already extracted by HR: {skills}"
    )

    result = _agent.invoke({
        "messages": [HumanMessage(content=prompt_text)]
    })

    # Parse tool call outputs
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

            if msg.name == "search_job_requirements" and isinstance(data, dict):
                required_skills = data.get("required_skills", [])

            elif msg.name == "run_skill_gap_analysis" and isinstance(data, dict):
                matched_skills = data.get("matched_skills", [])
                missing_skills = data.get("missing_skills", [])
                skill_score    = data.get("skill_score", 0)
                skill_match    = data.get("skill_match", "No Match")

    print(f"  Required skills: {required_skills}")
    print(f"  Matched skills : {matched_skills}")
    print(f"  Missing skills : {missing_skills}")
    print(f"  Score          : {skill_score}/100 → {skill_match}")

    return {
        "required_skills": required_skills,
        "matched_skills": matched_skills,
        "missing_skills": missing_skills,
        "skill_score": skill_score,
        "skill_match": skill_match,
        "messages": result["messages"],
    }
