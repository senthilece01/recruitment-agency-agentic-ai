"""
Recruiter Agent
---------------
Responsibilities:
  - Read the HR Screener and Technical Assessor outputs from state
  - Make the final hiring decision: interview | escalate | reject
  - Send the appropriate email to the candidate
  - Schedule a calendar invite (if shortlisted)
  - Log the decision to the audit log

Tools available:
  - send_email
  - create_calendar_invite
  - log_candidate_decision
"""
import json
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent
from langchain_core.messages import HumanMessage

from tools.communication_tools import send_email, create_calendar_invite, log_candidate_decision
from state import RecruitmentState

_llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)

_SYSTEM_PROMPT = """You are a Recruiter Agent at a tech recruitment agency.

You will receive a candidate profile with the following fields:
- experience_level: Entry-level | Mid-level | Senior-level
- skill_match: Match | No Match
- skill_score: 0-100
- candidate_name: name or "Unknown"

Apply this decision logic:
- If skill_match == "Match" → decision = "interview"
  → Send a warm interview invitation email
  → Create a calendar invite (interview_type = "HR Interview", interviewer = "Sarah (HR)")
- If skill_match == "No Match" AND experience_level == "Senior-level" → decision = "escalate"
  → Send an email informing the candidate the profile is being reviewed by a senior recruiter
  → No calendar invite needed
- Otherwise → decision = "reject"
  → Send a polite rejection email thanking them for applying

Always:
1. Use `send_email` to notify the candidate.
2. Use `create_calendar_invite` only when decision = "interview".
3. Use `log_candidate_decision` to record the final decision.

Use "candidate@example.com" as the email address if none is available.
"""

_agent = create_react_agent(
    model=_llm,
    tools=[send_email, create_calendar_invite, log_candidate_decision],
    prompt=_SYSTEM_PROMPT,
)


def recruiter_node(state: RecruitmentState) -> dict:
    """LangGraph node — runs the Recruiter ReAct agent."""
    print("\n[Recruiter Agent] Taking final action...")

    prompt_text = (
        f"Candidate Name    : {state.get('candidate_name', 'Unknown')}\n"
        f"Experience Level  : {state.get('experience_level', 'Unknown')}\n"
        f"Skill Match       : {state.get('skill_match', 'No Match')}\n"
        f"Skill Score       : {state.get('skill_score', 0)}/100\n"
        f"Matched Skills    : {state.get('matched_skills', [])}\n"
        f"Missing Skills    : {state.get('missing_skills', [])}\n"
        f"Original Application: {state.get('application', '')}"
    )

    result = _agent.invoke({
        "messages": [HumanMessage(content=prompt_text)]
    })

    final_decision = "reject"
    action_taken   = result["messages"][-1].content
    email_sent     = False

    for msg in result["messages"]:
        if hasattr(msg, "name"):
            try:
                data = json.loads(msg.content) if isinstance(msg.content, str) else msg.content
            except Exception:
                continue

            if msg.name == "send_email" and isinstance(data, dict) and data.get("success"):
                email_sent = True

            elif msg.name == "log_candidate_decision" and isinstance(data, dict):
                final_decision = data.get("decision", "reject")

    print(f"  Decision       : {final_decision}")
    print(f"  Email sent     : {email_sent}")

    return {
        "final_decision": final_decision,
        "action_taken": action_taken,
        "email_sent": email_sent,
        "messages": result["messages"],
    }
