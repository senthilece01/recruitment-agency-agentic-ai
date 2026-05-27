"""
HR Screener Agent
-----------------
Responsibilities:
  - Parse the incoming job application
  - Extract candidate skills and years of experience
  - Categorize the candidate as Entry-level, Mid-level, or Senior-level
  - Query the candidate DB to check for duplicates

Tools available:
  - parse_resume
  - query_candidate_db
  - extract_years_of_experience
"""
import os
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent
from langchain_core.messages import HumanMessage

from tools.resume_tools import parse_resume, query_candidate_db, extract_years_of_experience
from state import RecruitmentState

_llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)

_SYSTEM_PROMPT = """You are an experienced HR Screener Agent at a tech recruitment agency.

Your job is to analyse a job application and extract structured information.

Follow these steps using the tools available to you:
1. Use `parse_resume` to extract skills from the application text.
2. Use `extract_years_of_experience` to determine years of experience and experience level.
3. Use `query_candidate_db` to check if the candidate already exists (use any name you can infer, or "Unknown" if none found).

After using the tools, respond with a structured summary containing:
- Candidate name (infer from text or use "Unknown")
- Extracted skills (list)
- Years of experience (integer)
- Experience level (Entry-level | Mid-level | Senior-level)
"""

_agent = create_react_agent(
    model=_llm,
    tools=[parse_resume, query_candidate_db, extract_years_of_experience],
    prompt=_SYSTEM_PROMPT,
)


def hr_screener_node(state: RecruitmentState) -> dict:
    """LangGraph node — runs the HR Screener ReAct agent."""
    print("\n[HR Screener Agent] Analysing application...")

    result = _agent.invoke({
        "messages": [HumanMessage(content=state["application"])]
    })

    # Extract the final text response
    final_message = result["messages"][-1].content

    # Parse tool outputs from intermediate messages to populate state fields
    skills_extracted: list[str] = []
    years_of_experience: int = 0
    experience_level: str = "Entry-level"

    for msg in result["messages"]:
        if hasattr(msg, "name"):
            import json
            try:
                data = json.loads(msg.content) if isinstance(msg.content, str) else msg.content
            except Exception:
                continue

            if msg.name == "parse_resume" and isinstance(data, dict):
                skills_extracted = data.get("extracted_skills", [])

            elif msg.name == "extract_years_of_experience" and isinstance(data, dict):
                years_of_experience = data.get("years_of_experience", 0)
                experience_level    = data.get("experience_level", "Entry-level")

    print(f"  Skills found   : {skills_extracted}")
    print(f"  Experience     : {years_of_experience} year(s) → {experience_level}")

    return {
        "skills_extracted": skills_extracted,
        "years_of_experience": years_of_experience,
        "experience_level": experience_level,
        "candidate_name": "Unknown",
        "messages": result["messages"],
    }
