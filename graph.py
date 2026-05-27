"""
Orchestrator Graph
------------------
Wires the three agents into a LangGraph StateGraph pipeline:

  START
    ↓
  hr_screener_agent         (parse resume, extract skills & experience)
    ↓
  technical_assessor_agent  (skill gap analysis, match score)
    ↓
  route_decision()          (conditional edge)
    ├── "interview" ──────→ recruiter_agent → END
    ├── "escalate"  ──────→ recruiter_agent → END
    └── "reject"    ──────→ recruiter_agent → END
"""
from langgraph.graph import StateGraph, START, END

from state import RecruitmentState
from agents import hr_screener_node, technical_assessor_node, recruiter_node


def route_decision(state: RecruitmentState) -> str:
    """
    Conditional router after the Technical Assessor.
    Routes to the Recruiter regardless of outcome — the Recruiter
    agent itself applies the correct action based on state values.
    """
    skill_match      = state.get("skill_match", "No Match")
    experience_level = state.get("experience_level", "Entry-level")

    if skill_match == "Match":
        print("\n[Router] Skill match found → scheduling HR interview")
        return "recruiter"

    if experience_level == "Senior-level":
        print("\n[Router] No skill match but Senior-level → escalating to senior recruiter")
        return "recruiter"

    print("\n[Router] No match, not senior → rejecting application")
    return "recruiter"


def build_graph() -> StateGraph:
    workflow = StateGraph(RecruitmentState)

    # Register nodes
    workflow.add_node("hr_screener",          hr_screener_node)
    workflow.add_node("technical_assessor",   technical_assessor_node)
    workflow.add_node("recruiter",            recruiter_node)

    # Define edges
    workflow.add_edge(START,                  "hr_screener")
    workflow.add_edge("hr_screener",          "technical_assessor")
    workflow.add_conditional_edges("technical_assessor", route_decision)
    workflow.add_edge("recruiter",            END)

    return workflow.compile()


# Compiled app — import and call .invoke() from main.py
app = build_graph()
