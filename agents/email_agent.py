"""
Revenue Guardian - Email Intelligence Agent
===========================================

This module implements the Email Intelligence Agent using the Google Agent Development Kit (ADK).

The Email Intelligence Agent is responsible for:
1. Fetching recent email threads (mocked here, but MCP-ready for Gmail integration).
2. Performing sentiment analysis on the customer's last email.
3. Conducting urgency detection to flag critical client issues.
4. Performing ghosting detection (determining if a client has gone silent after a sales outreach or vice-versa).
5. Classifying customer intent (e.g., pricing negotiation, technical blocker, unsubscribe, general interest).
6. Drafting personalized follow-up emails tailored to the thread's context, sentiment, and urgency.
7. Returning a structured EmailIntelligenceResult JSON payload to the Manager Agent.

Design Decisions:
-----------------
*   **Decoupled Email Interface**: Email fetch and draft actions are wrapped in ADK tools. In production, these
    tools will run on an MCP Gmail Server utilizing official Google APIs.
*   **Contextual Sentiment & Intent Reasoning**: Uses Gemini's advanced reasoning capabilities to extract fine-grained
    customer sentiment (e.g., frustrated, eager) and classify intent accurately without relying on brittle regex.
*   **Structured Output**: Employs Pydantic models to enforce a strict schema on the email analysis and drafted replies,
    preventing hallucinations in downstream systems.
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
logger = logging.getLogger("EmailIntelligenceAgent")


# ==========================================
# 1. Structured Output & Domain Schemas
# ==========================================

class EmailAnalysis(BaseModel):
    """Detailed analysis and drafted response for a single email thread."""
    thread_id: str = Field(..., description="Unique identifier for the email thread.")
    subject: str = Field(..., description="Subject line of the email thread.")
    last_sender: str = Field(..., description="Sender of the last email in the thread.")
    sentiment: str = Field(..., description="Customer sentiment: 'positive', 'neutral', or 'negative'.")
    urgency_level: str = Field(..., description="Urgency: 'high', 'medium', or 'low'.")
    intent: str = Field(..., description="Classified intent (e.g., 'pricing_inquiry', 'technical_blocker', 'unresponsive', 'renewal').")
    is_ghosted: bool = Field(..., description="True if the customer has not responded for more than 5 days.")
    ghosting_details: Optional[str] = Field(None, description="Detailed explanation of the ghosting status.")
    key_points: List[str] = Field(default_factory=list, description="Key points extracted from the conversation history.")
    suggested_follow_up_draft: str = Field(..., description="A drafted, personalized follow-up email ready for HITL approval.")


class EmailIntelligenceResult(BaseModel):
    """The structured report returned by the Email Agent to the Manager Agent."""
    timestamp: str = Field(..., description="ISO timestamp of the analysis.")
    analyzed_threads: List[EmailAnalysis] = Field(default_factory=list, description="List of analyzed email threads.")
    requires_immediate_action_count: int = Field(..., description="Number of threads flagged with high urgency.")
    summary: str = Field(..., description="High-level executive summary of customer communications and sentiment trends.")


# ==========================================
# 2. Mock Email Database & Tool Definitions
# ==========================================

# Mock email threads database representing common B2B customer scenarios.
MOCK_EMAIL_DATABASE = [
    {
        "thread_id": "TH_001",
        "subject": "Acme Corp - Contract Pricing Clarification",
        "messages": [
            {
                "sender": "alice.rep@guardian.com",
                "recipient": "bob.admin@acme.com",
                "date": "2026-06-20T10:00:00",
                "body": "Hi Bob, I wanted to follow up on the contract pricing we sent over last week. Let me know if you have any questions."
            },
            {
                "sender": "bob.admin@acme.com",
                "recipient": "alice.rep@guardian.com",
                "date": "2026-06-29T14:30:00",
                "body": "Hi Alice, we reviewed the proposal. The pricing seems a bit high, especially the overage charge of $0.10/unit. Can we negotiate this? Also, we need this resolved by Friday because our current billing cycle ends."
            }
        ]
    },
    {
        "thread_id": "TH_002",
        "subject": "Globex Migration Technical blocker",
        "messages": [
            {
                "sender": "charlie.tech@globex.com",
                "recipient": "support@guardian.com",
                "date": "2026-06-28T09:15:00",
                "body": "We are trying to migrate our database to your API but we keep getting 500 errors on the batch endpoint. This is blocking our entire team. Please help!"
            }
        ]
    },
    {
        "thread_id": "TH_003",
        "subject": "Initech - Follow up on demo",
        "messages": [
            {
                "sender": "alice.rep@guardian.com",
                "recipient": "dave.manager@initech.com",
                "date": "2026-06-10T11:00:00",
                "body": "Hi Dave, great speaking with you on the demo. Let me know if you would like to set up a deep dive."
            }
            # No reply from Dave since June 10. (Current date is 2026-06-30). Ghosted!
        ]
    }
]


def get_recent_emails() -> List[Dict[str, Any]]:
    """
    Fetches recent email threads from the inbox.
    
    Returns:
        A list of dictionaries representing email threads.
    """
    logger.info("Fetching recent email threads...")
    return MOCK_EMAIL_DATABASE


def create_gmail_draft(thread_id: str, draft_body: str) -> Dict[str, Any]:
    """
    Creates a draft reply for a specific email thread in Gmail.

    Args:
        thread_id: The ID of the thread to reply to.
        draft_body: The body content of the draft email.

    Returns:
        A dictionary confirming the draft creation.
    """
    logger.info(f"Creating Gmail draft for thread {thread_id}...")
    return {
        "status": "success",
        "thread_id": thread_id,
        "message": "Draft created successfully in Gmail."
    }


# ==========================================
# 3. Agent Definition
# ==========================================

EMAIL_AGENT_INSTRUCTION = """
You are the Email Intelligence Agent, a specialized component of the "Revenue Guardian" platform.
Your objective is to analyze B2B customer email threads to identify risks, sentiments, and required actions.

You have access to two tools:
1. `get_recent_emails`: Fetches recent email threads.
2. `create_gmail_draft`: Creates a draft email in the inbox.

Perform the following analysis for every email thread returned by `get_recent_emails` as of 2026-06-30:
1. **Sentiment Analysis**: Assess the tone of the customer's last message. Is it positive, neutral, or negative (e.g. frustrated)?
2. **Urgency Detection**: Flag threads as 'high', 'medium', or 'low' urgency. Hard deadlines or blocking technical issues constitute 'high' urgency.
3. **Ghosting Detection**:
   - Check if the last email was sent by us (the sales rep) and has received no response for more than 5 days.
   - Set `is_ghosted` to True if this condition is met and explain it in `ghosting_details`.
4. **Intent Classification**: Classify the customer's intent (e.g., 'pricing_inquiry', 'technical_blocker', 'unresponsive', 'renewal').
5. **Key Points**: Extract 2-3 key points from the thread.
6. **Draft Follow-up**: Draft a highly personalized follow-up email.
   - If they are negotiating pricing, offer to schedule a call to discuss custom terms.
   - If they have a technical blocker, express empathy, state that the support team is investigating, and offer immediate assistance.
   - If they have ghosted us, draft a polite re-engagement email asking if their priorities have shifted.

Return the completed analysis matching the EmailIntelligenceResult output schema.
"""

def create_email_agent(model_name: str = "gemini-2.0-flash") -> Agent:
    """
    Factory function to create the Email Intelligence Agent.

    Args:
        model_name: The name of the Gemini model (default: gemini-2.0-flash).

    Returns:
        An instantiated Google ADK Agent.
    """
    return Agent(
        name="email_intelligence_agent",
        model=model_name,
        instruction=EMAIL_AGENT_INSTRUCTION,
        description="Analyzes customer emails for sentiment, urgency, intent, and ghosting, and drafts replies.",
        tools=[
            get_recent_emails,
            create_gmail_draft
        ],
        output_schema=EmailIntelligenceResult
    )


# ==========================================
# 4. Programmatic Execution Runner
# ==========================================

async def run_email_analysis(model_name: str = "gemini-2.0-flash") -> EmailIntelligenceResult:
    """
    Programmatically executes the Email Intelligence Agent.

    Args:
        model_name: The Gemini model to use.

    Returns:
        A structured EmailIntelligenceResult containing the email analysis.
    """
    agent = create_email_agent(model_name=model_name)
    session_service = InMemorySessionService()
    runner = Runner(agent=agent, session_service=session_service)

    prompt = (
        "Analyze all recent email threads as of 2026-06-30. "
        "Perform sentiment analysis, urgency detection, ghosting detection, "
        "and draft personalized replies for each thread."
    )

    logger.info("Executing Email Intelligence Agent analysis...")
    response = await runner.run(
        session_id="email_analysis_session",
        user_prompt=prompt
    )

    return response.structured_output
