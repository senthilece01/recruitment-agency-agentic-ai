"""
Mock communication tools used by the Recruiter Agent.
In production these would use Resend/SMTP for email and Google Calendar API.
"""
from datetime import datetime, timedelta
from langchain_core.tools import tool

# In-memory log of all actions taken
ACTION_LOG: list[dict] = []


@tool
def send_email(to: str, subject: str, body: str) -> dict:
    """
    Send an email to the candidate (mock — logs to memory instead of real sending).
    Returns confirmation with timestamp.
    """
    timestamp = datetime.utcnow().isoformat()
    record = {
        "type": "email",
        "to": to,
        "subject": subject,
        "body": body,
        "sent_at": timestamp,
        "status": "sent (mock)",
    }
    ACTION_LOG.append(record)

    return {
        "success": True,
        "message": f"Email sent to {to} with subject '{subject}'",
        "sent_at": timestamp,
    }


@tool
def create_calendar_invite(candidate_name: str, interview_type: str, interviewer: str) -> dict:
    """
    Create a calendar invite for an interview (mock — logs to memory).
    Schedules 3 business days from now at 10:00 AM UTC.
    Returns invite details.
    """
    interview_date = (datetime.utcnow() + timedelta(days=3)).strftime("%Y-%m-%d")
    invite = {
        "type": "calendar_invite",
        "candidate": candidate_name,
        "interview_type": interview_type,
        "interviewer": interviewer,
        "date": interview_date,
        "time": "10:00 AM UTC",
        "duration": "45 minutes",
        "location": "Google Meet (mock link: meet.google.com/mock-link)",
        "status": "scheduled (mock)",
    }
    ACTION_LOG.append(invite)

    return {
        "success": True,
        "message": f"{interview_type} scheduled for {candidate_name} on {interview_date} at 10:00 AM UTC",
        "invite": invite,
    }


@tool
def log_candidate_decision(candidate_name: str, decision: str, reason: str) -> dict:
    """
    Log the final hiring decision for a candidate to the in-memory audit log.
    Decision must be one of: 'interview', 'escalate', 'reject'.
    """
    timestamp = datetime.utcnow().isoformat()
    record = {
        "type": "decision",
        "candidate": candidate_name,
        "decision": decision,
        "reason": reason,
        "logged_at": timestamp,
    }
    ACTION_LOG.append(record)

    return {
        "success": True,
        "decision": decision,
        "logged_at": timestamp,
        "message": f"Decision '{decision}' logged for {candidate_name}.",
    }


def get_action_log() -> list[dict]:
    """Return all actions taken during this session (for display in main.py)."""
    return ACTION_LOG
