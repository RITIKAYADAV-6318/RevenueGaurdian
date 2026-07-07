"""
Revenue Guardian - Calendar Agent
==================================

This module implements the Calendar Agent using the Google Agent Development Kit (ADK).

The Calendar Agent is responsible for:
1. Reading Google Calendar events and availability (mocked here, but MCP-ready).
2. Detecting missed meetings (meetings that passed where a no-show was indicated or occurred).
3. Detecting overdue follow-ups (meetings in the past that required action items which remain uncompleted).
4. Identifying upcoming renewal meetings and recommending preparation steps.
5. Recommending meeting schedules for rescheduling or new engagements based on free/busy availability.
6. Returning a structured CalendarAnalysisResult JSON payload to the Manager Agent.

Design Decisions:
-----------------
*   **Decoupled Calendar Interface**: Calendar event fetching and availability queries are wrapped in ADK tools.
    In production, these tools will run on an MCP Google Calendar Server using official Google APIs.
*   **Semantic Meeting Audit**: Uses Gemini to analyze meeting descriptions, notes, and titles to detect no-shows,
    missed follow-ups, and renewal intent, which are difficult to extract with standard keyword searches.
*   **Structured Output**: Employs Pydantic models to enforce a strict schema on the calendar analysis, ensuring
    the Manager Agent can easily merge schedule data with CRM and Email findings.
"""

import logging
from typing import List, Optional, Any, Dict
from pydantic import BaseModel, Field

# Import core Google ADK components
from google.adk.agents import Agent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("CalendarAgent")


# ==========================================
# 1. Structured Output & Domain Schemas
# ==========================================

class MissedMeeting(BaseModel):
    """Represents a past meeting that was missed or had a no-show."""
    event_id: str = Field(..., description="Unique identifier for the calendar event.")
    title: str = Field(..., description="Title of the meeting.")
    attendees: List[str] = Field(..., description="Emails of the participants.")
    start_time: str = Field(..., description="ISO start time of the meeting.")
    reason_flagged: str = Field(..., description="Explanation of why this meeting is flagged as missed.")
    recommended_action: str = Field(..., description="AI recommendation (e.g., 'Send rescheduling link').")


class OverdueCalendarFollowUp(BaseModel):
    """Represents a meeting where follow-up action items are overdue."""
    event_id: str = Field(..., description="Unique identifier for the calendar event.")
    title: str = Field(..., description="Title of the meeting.")
    due_time: str = Field(..., description="ISO date/time when the follow-up was expected.")
    days_overdue: int = Field(..., description="Number of days elapsed since the meeting.")
    description: str = Field(..., description="Details of the follow-up task or action item.")


class UpcomingRenewalMeeting(BaseModel):
    """Represents an upcoming meeting focused on contract renewals."""
    event_id: str = Field(..., description="Unique identifier for the calendar event.")
    title: str = Field(..., description="Title of the renewal meeting.")
    customer_name: str = Field(..., description="Name of the customer or company.")
    scheduled_time: str = Field(..., description="ISO start time of the meeting.")
    days_until_meeting: int = Field(..., description="Number of days remaining until the meeting.")
    prep_recommendations: List[str] = Field(..., description="Recommended preparation steps (e.g., 'Review usage metrics').")


class MeetingRecommendation(BaseModel):
    """A recommended meeting slot based on availability and urgency."""
    customer_name: str = Field(..., description="Name of the customer or company.")
    reason: str = Field(..., description="Reason for recommending the meeting.")
    suggested_duration_minutes: int = Field(..., description="Recommended duration in minutes.")
    proposed_time_slots: List[str] = Field(..., description="ISO time slots available in our calendar.")


class CalendarAnalysisResult(BaseModel):
    """Structured report returned by the Calendar Agent to the Manager Agent."""
    timestamp: str = Field(..., description="ISO timestamp of when the analysis was performed.")
    missed_meetings: List[MissedMeeting] = Field(default_factory=list, description="List of detected missed meetings.")
    overdue_follow_ups: List[OverdueCalendarFollowUp] = Field(default_factory=list, description="List of overdue follow-ups.")
    upcoming_renewals: List[UpcomingRenewalMeeting] = Field(default_factory=list, description="List of upcoming renewal meetings.")
    meeting_recommendations: List[MeetingRecommendation] = Field(default_factory=list, description="List of suggested meetings to schedule.")
    summary: str = Field(..., description="High-level summary of calendar health and scheduling recommendations.")


# ==========================================
# 2. Mock Calendar Database & Tool Definitions
# ==========================================

# Mock calendar database representing meetings and availability
MOCK_CALENDAR_DATABASE = {
    "events": [
        {
            "event_id": "EV_001",
            "title": "Acme Corp - Contract Renewal Discussion",
            "attendees": ["alice.rep@guardian.com", "bob.admin@acme.com"],
            "start_time": "2026-06-25T14:00:00",
            "end_time": "2026-06-25T14:45:00",
            "description": "Discussing renewal for Q3. Note: Bob did not show up. Need to reschedule.",
            "status": "confirmed"
        },
        {
            "event_id": "EV_002",
            "title": "Globex - Post-Migration Support Check-in",
            "attendees": ["alice.rep@guardian.com", "charlie.tech@globex.com"],
            "start_time": "2026-06-28T11:00:00",
            "end_time": "2026-06-28T11:30:00",
            "description": "Follow up: Send migration checklist to Charlie.",
            "status": "confirmed"
        },
        {
            "event_id": "EV_003",
            "title": "Initech - Q3 Renewal & Expansion Review",
            "attendees": ["alice.rep@guardian.com", "dave.manager@initech.com"],
            "start_time": "2026-07-05T10:00:00",
            "end_time": "2026-07-05T11:00:00",
            "description": "Reviewing renewal options and expansion into security modules.",
            "status": "confirmed"
        }
    ],
    "free_busy": [
        {"start_time": "2026-07-01T09:00:00", "end_time": "2026-07-01T12:00:00"},
        {"start_time": "2026-07-01T13:00:00", "end_time": "2026-07-01T15:00:00"},
        {"start_time": "2026-07-02T10:00:00", "end_time": "2026-07-02T12:00:00"}
    ]
}


def get_calendar_events() -> List[Dict[str, Any]]:
    """
    Fetches calendar events for the past 7 days and next 7 days.
    
    Returns:
        A list of dictionaries representing calendar events.
    """
    logger.info("Fetching calendar events...")
    return MOCK_CALENDAR_DATABASE["events"]


def get_free_busy_slots() -> List[Dict[str, Any]]:
    """
    Retrieves available open time slots (free times) in our calendar.

    Returns:
        A list of dictionaries representing open time slots.
    """
    logger.info("Fetching free/busy availability...")
    return MOCK_CALENDAR_DATABASE["free_busy"]


# ==========================================
# 3. Agent Definition
# ==========================================

CALENDAR_AGENT_INSTRUCTION = """
You are the Calendar Agent, a specialized component of the "Revenue Guardian" platform.
Your objective is to analyze calendar events and availability to optimize customer engagement and renewal timelines.

You have access to two tools:
1. `get_calendar_events`: Fetches recent and upcoming meetings.
2. `get_free_busy_slots`: Fetches open slots in our calendar.

Perform the following analysis as of 2026-06-30:
1. **Missed Meetings**: Check past meetings where the description indicates a no-show (e.g., "did not show up").
   - Populate `missed_meetings` list and recommend a rescheduling action.
2. **Overdue Follow-ups**: Check past meetings (before 2026-06-30) that have "Follow up" or action items in the description.
   - If the current date is after the meeting and the action is uncompleted, flag it in `overdue_follow_ups` and calculate `days_overdue`.
3. **Upcoming Renewal Meetings**: Identify future meetings (after 2026-06-30) that discuss "renewal".
   - Flag them in `upcoming_renewals`, calculate `days_until_meeting`, and provide 2-3 preparation recommendations (e.g., 'Review usage data', 'Check open support tickets').
4. **Meeting Recommendations**: Recommends times to schedule meetings:
   - For any missed meetings, suggest rescheduling.
   - For any upcoming renewals, suggest prep syncs.
   - Retrieve open slots from `get_free_busy_slots` and propose them as `proposed_time_slots`.

Return the completed analysis matching the CalendarAnalysisResult output schema.
"""

def create_calendar_agent(model_name: str = "gemini-2.0-flash") -> Agent:
    """
    Factory function to create the Calendar Agent.

    Args:
        model_name: The name of the Gemini model (default: gemini-2.0-flash).

    Returns:
        An instantiated Google ADK Agent.
    """
    return Agent(
        name="calendar_agent",
        model=model_name,
        instruction=CALENDAR_AGENT_INSTRUCTION,
        description="Analyzes calendar events for missed meetings, renewal syncs, and suggests optimal scheduling.",
        tools=[
            get_calendar_events,
            get_free_busy_slots
        ],
        output_schema=CalendarAnalysisResult
    )


# ==========================================
# 4. Programmatic Execution Runner
# ==========================================

async def run_calendar_analysis(model_name: str = "gemini-2.0-flash") -> CalendarAnalysisResult:
    """
    Programmatically executes the Calendar Agent.

    Args:
        model_name: The Gemini model to use.

    Returns:
        A structured CalendarAnalysisResult containing the calendar analysis.
    """
    agent = create_calendar_agent(model_name=model_name)
    session_service = InMemorySessionService()
    runner = Runner(agent=agent, session_service=session_service, app_name="revenue_guardian")

    prompt = (
        "Analyze all calendar events and availability as of 2026-06-30. "
        "Identify missed meetings, overdue follow-ups, upcoming renewals, "
        "and recommend optimal meeting slots to reschedule or prepare."
    )

    logger.info("Executing Calendar Agent analysis...")
    response = await runner.run(
        user_id="system",
        session_id="calendar_analysis_session",
        new_message=prompt
    )

    return response.structured_output
