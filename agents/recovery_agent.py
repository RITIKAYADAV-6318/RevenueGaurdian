"""
Revenue Guardian - Recovery Strategy Agent
===========================================

This module implements the Recovery Strategy Agent using the Google Agent Development Kit (ADK).

The Recovery Strategy Agent is responsible for:
1. Fetching structured analysis reports from the CRM, Email, Calendar, and Revenue Prediction agents.
2. Evaluating risks across all systems (e.g., billing disputes, technical blockers, ghosting, missed meetings).
3. Formulating an optimal recovery strategy by selecting from a list of predefined actions:
   - Call Customer
   - Send Follow-up
   - Schedule Meeting
   - Escalate to Manager
   - Offer Discount
   - Reassign Opportunity
4. Explaining WHY each action is recommended based on the synthesized signals.
5. Computing a confidence score (0.0 to 1.0) for each recommendation.
6. Returning a structured RecoveryStrategyResult JSON payload to the Manager Agent.

Design Decisions:
-----------------
*   **Decoupled Signal Aggregation**: The agent aggregates signals using ADK tools that return mock data representing
    the output of other agents. In production, the Manager Agent passes these outputs directly or the tools query
    the centralized PostgreSQL state database.
*   **Reasoning-First Recommendation**: Leverages Gemini's reasoning capabilities to cross-reference signals. For example,
    if a customer has a technical blocker (Email) and a high contract value (CRM), the agent recommends
    'Escalate to Manager' and 'Schedule Meeting' with high confidence.
*   **Structured Output**: Employs Pydantic models to ensure the resulting action plan is type-safe and ready for the
    human-in-the-loop dashboard.
"""

import logging
from typing import List, Optional, Any, Dict
from pydantic import BaseModel, Field

# Import core Google ADK components
from google.adk.agents import Agent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from agents.runner_utils import run_runner_and_get_response

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("RecoveryStrategyAgent")


# ==========================================
# 1. Structured Output & Domain Schemas
# ==========================================

class RecoveryAction(BaseModel):
    """A recommended action to recover a deal or account at risk."""
    action_type: str = Field(..., description="Action type: 'call_customer', 'send_follow_up', 'schedule_meeting', 'escalate_manager', 'offer_discount', or 'reassign_opportunity'.")
    target_entity: str = Field(..., description="The name of the customer or opportunity this action targets.")
    description: str = Field(..., description="Detailed description of the recommended action.")
    confidence_score: float = Field(..., description="Confidence score of this recommendation (0.0 to 1.0).")
    reasoning: str = Field(..., description="Detailed explanation of WHY this recommendation is made based on the inputs.")
    priority_level: str = Field(..., description="Priority: 'high', 'medium', or 'low'.")
    execution_payload: Dict[str, Any] = Field(..., description="Payload details for execution (e.g., recipient email, discount percentage, escalation notes).")


class RecoveryStrategyResult(BaseModel):
    """The structured report returned by the Recovery Agent to the Manager Agent."""
    timestamp: str = Field(..., description="ISO timestamp of when the analysis was performed.")
    recommended_actions: List[RecoveryAction] = Field(..., description="List of recommended recovery actions.")
    overall_recovery_viability: float = Field(..., description="Estimate of overall recovery viability across all accounts (0.0 to 1.0).")
    executive_summary: str = Field(..., description="High-level summary of the recovery strategy and key focal points.")


# ==========================================
# 2. Mock Analysis Retrieval Tools
# ==========================================

# Mock reports compiled from the other specialized agents.
MOCK_AGENT_REPORTS = {
    "crm": {
        "inactive_leads": [
            {"lead_id": "LD_101", "name": "Sarah Jenkins", "company": "Nexus Media", "days_inactive": 46}
        ],
        "stalled_opportunities": [
            {"opportunity_id": "OPP_201", "name": "Acme Corp - Enterprise Expansion", "current_stage": "Proposal/Price Quote", "days_in_stage": 50, "deal_value": 75000.0},
            {"opportunity_id": "OPP_203", "name": "Initech - Security Module Add-on", "current_stage": "Discovery", "days_in_stage": 30, "deal_value": 15000.0}
        ]
    },
    "email": {
        "analyzed_threads": [
            {"thread_id": "TH_001", "subject": "Acme Corp - Contract Pricing Clarification", "sentiment": "negative", "intent": "pricing_inquiry", "is_ghosted": False, "key_points": ["Bob thinks pricing is high", "Objecting to $0.10 overage charge", "Needs resolution by Friday"]},
            {"thread_id": "TH_002", "subject": "Globex Migration Technical blocker", "sentiment": "negative", "intent": "technical_blocker", "is_ghosted": False, "key_points": ["Getting 500 errors on batch API endpoint", "Blocking their migration team"]},
            {"thread_id": "TH_003", "subject": "Initech - Follow up on demo", "sentiment": "neutral", "intent": "unresponsive", "is_ghosted": True, "key_points": ["Last outreach on June 10", "No response in 20 days"]}
        ]
    },
    "calendar": {
        "missed_meetings": [
            {"event_id": "EV_001", "title": "Acme Corp - Contract Renewal Discussion", "attendees": ["bob.admin@acme.com"], "reason_flagged": "Bob did not show up."}
        ],
        "overdue_follow_ups": [
            {"event_id": "EV_002", "title": "Globex - Post-Migration Support Check-in", "days_overdue": 2, "description": "Send migration checklist to Charlie."}
        ]
    },
    "prediction": {
        "opportunities_win_probability": [
            {"opportunity_id": "OPP_201", "name": "Acme Corp - Enterprise Expansion", "win_probability": 0.35, "expected_value": 26250.0},
            {"opportunity_id": "OPP_202", "name": "Globex - API Platform Migration", "win_probability": 0.55, "expected_value": 66000.0},
            {"opportunity_id": "OPP_203", "name": "Initech - Security Module Add-on", "win_probability": 0.15, "expected_value": 2250.0}
        ],
        "revenue_at_risk": [
            {"customer_name": "Acme Corp", "contract_value": 60000.0, "churn_risk_score": 0.35, "expected_loss": 21000.0},
            {"customer_name": "Globex", "contract_value": 144000.0, "churn_risk_score": 0.45, "expected_loss": 64800.0},
            {"customer_name": "Initech", "contract_value": 24000.0, "churn_risk_score": 0.30, "expected_loss": 7200.0}
        ]
    }
}


def get_crm_analysis_report() -> Dict[str, Any]:
    """Retrieves the analysis report from the CRM Intelligence Agent."""
    logger.info("Fetching CRM Agent report...")
    return MOCK_AGENT_REPORTS["crm"]


def get_email_analysis_report() -> Dict[str, Any]:
    """Retrieves the analysis report from the Email Intelligence Agent."""
    logger.info("Fetching Email Agent report...")
    return MOCK_AGENT_REPORTS["email"]


def get_calendar_analysis_report() -> Dict[str, Any]:
    """Retrieves the analysis report from the Calendar Agent."""
    logger.info("Fetching Calendar Agent report...")
    return MOCK_AGENT_REPORTS["calendar"]


def get_revenue_prediction_report() -> Dict[str, Any]:
    """Retrieves the predictive analysis report from the Revenue Prediction Agent."""
    logger.info("Fetching Revenue Prediction Agent report...")
    return MOCK_AGENT_REPORTS["prediction"]


# ==========================================
# 3. Agent Definition
# ==========================================

RECOVERY_AGENT_INSTRUCTION = """
You are the Recovery Strategy Agent, a specialized component of the "Revenue Guardian" platform.
Your objective is to synthesize risk signals from CRM, Email, Calendar, and Revenue Predictions,
and determine the optimal recovery strategy for each at-risk opportunity or customer account.

You have access to four tools:
1. `get_crm_analysis_report`
2. `get_email_analysis_report`
3. `get_calendar_analysis_report`
4. `get_revenue_prediction_report`

Your Recommendation Engine should evaluate:
- **Acme Corp**: 
  - *Signals*: Stalled deal ($75k, 50 days), missed renewal meeting by Bob, pricing objection (frustrated by $0.10 overage), win probability dropped to 35%, expected churn loss is $21k.
  - *Actions*: Propose 'offer_discount' (to resolve the overage pricing dispute), 'schedule_meeting' (to reschedule the missed renewal discussion), and 'call_customer' (due to high value and Friday deadline).
- **Globex**:
  - *Signals*: $120k active deal, technical blocker (500 errors on batch API), overdue calendar checklist follow-up, win probability 55%, high expected churn loss ($64.8k).
  - *Actions*: Propose 'escalate_manager' (to technical support/engineering manager to resolve the API blocker immediately) and 'send_follow_up' (to send the overdue migration checklist).
- **Initech**:
  - *Signals*: $15k deal stalled in Discovery (30 days), customer has ghosted us for 20 days, win probability dropped to 15%.
  - *Actions*: Propose 'reassign_opportunity' (since the current rep is making no progress and the customer is unresponsive, a new rep might re-engage) or 'send_follow_up' (a break-up email).

For every recommended action, you MUST:
1. Specify the `action_type` (must be one of: 'call_customer', 'send_follow_up', 'schedule_meeting', 'escalate_manager', 'offer_discount', 'reassign_opportunity').
2. Provide a detailed, context-aware `description` of the action.
3. Assign a `confidence_score` (0.0 to 1.0) indicating how strongly you recommend this action.
4. Provide a clear, data-driven `reasoning` explaining WHY the action is recommended, referencing specific signals (e.g., "Since Globex is blocked by 500 errors on a $120k deal, we must escalate to engineering...").
5. Determine the `priority_level` ('high', 'medium', 'low').
6. Provide an `execution_payload` with concrete parameters.

Return the completed strategy matching the RecoveryStrategyResult output schema.
"""

def create_recovery_agent(model_name: str = "gemini-2.0-flash") -> Agent:
    """
    Factory function to create the Recovery Strategy Agent.

    Args:
        model_name: The name of the Gemini model (default: gemini-2.0-flash).

    Returns:
        An instantiated Google ADK Agent.
    """
    return Agent(
        name="recovery_strategy_agent",
        model=model_name,
        instruction=RECOVERY_AGENT_INSTRUCTION,
        description="Synthesizes multi-system risk reports to draft concrete recovery actions and calculate confidence scores.",
        tools=[
            get_crm_analysis_report,
            get_email_analysis_report,
            get_calendar_analysis_report,
            get_revenue_prediction_report
        ],
        output_schema=RecoveryStrategyResult
    )


# ==========================================
# 4. Programmatic Execution Runner
# ==========================================

async def run_recovery_analysis(model_name: str = "gemini-2.0-flash") -> RecoveryStrategyResult:
    """
    Programmatically executes the Recovery Strategy Agent.

    Args:
        model_name: The Gemini model to use.

    Returns:
        A structured RecoveryStrategyResult containing the action recommendations.
    """
    agent = create_recovery_agent(model_name=model_name)
    session_service = InMemorySessionService()
    runner = Runner(agent=agent, session_service=session_service, app_name="revenue_guardian")

    prompt = (
        "Analyze the reports from the CRM, Email, Calendar, and Revenue Prediction agents. "
        "Formulate a comprehensive recovery strategy for all at-risk accounts, "
        "drafting specific actions with confidence scores and detailed justifications."
    )

    logger.info("Executing Recovery Strategy Agent analysis...")
    raw = runner.run(
        user_id="system",
        session_id="recovery_analysis_session",
        new_message=prompt
    )

    response = await run_runner_and_get_response(raw)
    return response.structured_output
