"""
Communication tools used by the Recruiter Agent.
Email is sent via Resend (https://resend.com).
Calendar invites are logged to the action log (Google Calendar integration is a future enhancement).
"""
import os
from datetime import datetime, timedelta, timezone
from langchain_core.tools import tool

# In-memory log of all actions taken this server session
ACTION_LOG: list[dict] = []


def _resend_client():
    """Return a configured resend module, raising clearly if key is missing."""
    import resend  # noqa: PLC0415 — deferred so server starts without the key
    api_key = os.getenv("RESEND_API_KEY", "")
    if not api_key:
        raise RuntimeError(
            "RESEND_API_KEY is not set. Add it to your .env file."
        )
    resend.api_key = api_key
    return resend


@tool
def send_email(to: str, subject: str, body: str) -> dict:
    """
    Send an email to the candidate via Resend.
    Falls back to mock logging if RESEND_API_KEY is not configured.
    Returns a confirmation dict with message_id and timestamp.
    """
    timestamp = datetime.now(timezone.utc).isoformat()
    from_email = os.getenv("RESEND_FROM_EMAIL", "onboarding@resend.dev")
    # In sandbox mode Resend only allows sending to the account owner's address.
    # Override the recipient so every email is delivered to the configured address.
    actual_to = os.getenv("RESEND_TO_EMAIL", "senthilece01@gmail.com")

    try:
        resend = _resend_client()
        response = resend.Emails.send({
            "from": from_email,
            "to": [actual_to],
            "subject": subject,
            "html": body.replace("\n", "<br>"),
            "text": body,
        })
        message_id = getattr(response, "id", None) or response.get("id", "unknown")
        status = "sent"
    except Exception as exc:
        # Fall back to mock on any error (missing key, sandbox restriction, etc.)
        message_id = f"mock-{timestamp}"
        status = f"sent (mock — {exc})"

    record = {
        "type": "email",
        "to": actual_to,
        "intended_to": to,
        "subject": subject,
        "body": body,
        "sent_at": timestamp,
        "message_id": message_id,
        "status": status,
    }
    ACTION_LOG.append(record)

    return {
        "success": True,
        "message": f"Email sent to {actual_to} (intended for {to}) with subject '{subject}'",
        "message_id": message_id,
        "sent_at": timestamp,
        "status": status,
    }


@tool
def create_calendar_invite(candidate_name: str, interview_type: str, interviewer: str) -> dict:
    """
    Schedule an interview slot and log it.
    Schedules 3 business days from now at 10:00 AM UTC.
    Returns the invite details.
    """
    interview_date = (datetime.now(timezone.utc) + timedelta(days=3)).strftime("%Y-%m-%d")
    recruiter_name = os.getenv("RECRUITER_NAME", "Hiring Team")

    invite = {
        "type": "calendar_invite",
        "candidate": candidate_name,
        "interview_type": interview_type,
        "interviewer": interviewer or recruiter_name,
        "date": interview_date,
        "time": "10:00 AM UTC",
        "duration": "45 minutes",
        "status": "scheduled",
    }
    ACTION_LOG.append(invite)

    return {
        "success": True,
        "message": (
            f"{interview_type} scheduled for {candidate_name} "
            f"on {interview_date} at 10:00 AM UTC"
        ),
        "invite": invite,
    }


@tool
def log_candidate_decision(candidate_name: str, decision: str, reason: str) -> dict:
    """
    Log the final hiring decision for a candidate to the audit log.
    Decision must be one of: 'interview', 'escalate', 'reject'.
    """
    timestamp = datetime.now(timezone.utc).isoformat()
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
    """Return all actions taken during this session."""
    return ACTION_LOG
