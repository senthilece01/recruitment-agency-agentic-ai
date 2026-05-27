from typing import Annotated
from typing_extensions import TypedDict
from langgraph.graph.message import add_messages


class RecruitmentState(TypedDict):
    # Input
    application: str

    # Filled by HR Screener Agent
    candidate_name: str
    years_of_experience: int
    skills_extracted: list[str]
    experience_level: str       # Entry-level | Mid-level | Senior-level

    # Filled by Technical Assessor Agent
    required_skills: list[str]
    matched_skills: list[str]
    missing_skills: list[str]
    skill_match: str            # Match | No Match
    skill_score: int            # 0-100

    # Filled by Recruiter Agent
    final_decision: str         # interview | escalate | reject
    action_taken: str
    email_sent: bool

    # Shared agent message history
    messages: Annotated[list, add_messages]
