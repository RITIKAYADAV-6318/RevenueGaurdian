"""
Revenue Guardian - Executive Summary Agent
===========================================

This module implements the Executive Summary Agent using the Google Agent Development Kit (ADK).

The Executive Summary Agent is responsible for:
1. Fetching structured reports from the CRM, Email, Calendar, Revenue Prediction, and Recovery Strategy agents.
2. Synthesizing all findings into a dashboard-ready executive overview.
3. Generating a "Morning Briefing" (a concise 3-sentence summary of the day's outlook for quick review).
4. Compiling a detailed "Executive Report" in markdown format highlighting operational performance and risks.
5. Summarizing key revenue metrics (ARR, Revenue at Risk, 30-day forecast, unbilled overages).
6. Highlighting the top high-priority deals requiring immediate attention.
7. Filtering and presenting "Today's Recommendations" ranked by financial impact and urgency.
8. Calculating an overall "Business Health Score" (0 to 100) based on contract health and pipeline viability.
9. Returning a structured ExecutiveSummaryResult JSON payload to the Manager Agent.

Design Decisions:
-----------------
*   **High-Impact Synthesis**: The agent acts as the final aggregator in the multi-agent hierarchy. It consumes
    the raw analytical outputs of the other agents and translates them into business-level language.
*   **Dashboard-Ready Structures**: The output schema is designed to map directly to UI widgets, such as KPIs
    (health score, ARR, risk), charts (revenue breakdown), and lists (priority deals, action items).
*   **Google ADK Agent**: Built as an ADK Agent using Gemini to perform the final qualitative synthesis and
    markdown formatting of the executive report.
"""

import logging
from typing import List, Optional, Any, Dict
from pydantic import BaseModel, Field

# Import core Google ADK components
from google.adk.agents import Agent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from agents.runner_utils import make_new_message, run_runner_and_get_response

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ExecutiveSummaryAgent")


# ==========================================
# 1. Structured Output & Domain Schemas
# ==========================================

class ExecutiveRevenueSummary(BaseModel):
    """Key revenue figures synthesized for executive review."""
    total_arr: float = Field(..., description="Total Annual Recurring Revenue (ARR) in USD.")
    revenue_at_risk: float = Field(..., description="Total active contract revenue currently at risk of churn in USD.")
    forecasted_revenue_next_30_days: float = Field(..., description="Expected revenue forecasted to close in the next 30 days in USD.")
    unbilled_overages: float = Field(..., description="Total unbilled usage overages detected across all accounts in USD.")


class HighPriorityDealSummary(BaseModel):
    """Summary of a high-value deal requiring executive attention."""
    opportunity_id: str = Field(..., description="Unique identifier for the opportunity.")
    name: str = Field(..., description="Name of the opportunity.")
    value: float = Field(..., description="Raw deal value in USD.")
    win_probability: float = Field(..., description="Win probability (0.0 to 1.0).")
    primary_risk: str = Field(..., description="Primary risk factor associated with the deal.")
    recommended_action: str = Field(..., description="Immediate action recommended for today.")


class TodayRecommendation(BaseModel):
    """An action item scheduled for today's queue."""
    action_type: str = Field(..., description="Type of action (e.g., 'call', 'email', 'meeting', 'escalate').")
    target: str = Field(..., description="Target company or contact name.")
    description: str = Field(..., description="Short description of the action.")
    impact_value: float = Field(..., description="Estimated financial impact of this action in USD.")
    urgency: str = Field(..., description="Urgency: 'high', 'medium', or 'low'.")


class ExecutiveSummaryResult(BaseModel):
    """Dashboard-ready report returned by the Executive Summary Agent."""
    timestamp: str = Field(..., description="ISO timestamp of when the summary was generated.")
    business_health_score: int = Field(..., description="Overall business health score (0-100) based on pipeline and churn risk.")
    morning_briefing: str = Field(..., description="A short, punchy 3-sentence summary for a quick morning read.")
    executive_report: str = Field(..., description="A detailed, markdown-formatted report on overall business performance and operational risks.")
    revenue_summary: ExecutiveRevenueSummary = Field(..., description="Key revenue numbers.")
    high_priority_deals: List[HighPriorityDealSummary] = Field(..., description="Top deals requiring immediate attention.")
    todays_recommendations: List[TodayRecommendation] = Field(..., description="Action items for today.")


# ==========================================
# 2. Mock Reports Retrieval Tools
# ==========================================

# Mock reports compiled from CRM, Email, Calendar, Prediction, and Recovery agents.
MOCK_ALL_AGENT_REPORTS = {
    "crm": {
        "inactive_leads": [{"name": "Sarah Jenkins", "company": "Nexus Media", "days_inactive": 46}],
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
        "missed_meetings": [{"event_id": "EV_001", "title": "Acme Corp - Contract Renewal Discussion", "attendees": ["bob.admin@acme.com"], "reason_flagged": "Bob did not show up."}],
        "overdue_follow_ups": [{"event_id": "EV_002", "title": "Globex - Post-Migration Support Check-in", "days_overdue": 2, "description": "Send migration checklist to Charlie."}]
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
        ],
        "pipeline_health": {
            "total_pipeline_value": 210000.0,
            "stalled_deal_percentage": 42.8,
            "average_win_probability": 45.0,
            "health_rating": "Fair"
        },
        "revenue_forecast": {
            "pessimistic_forecast": 110000.0,
            "expected_forecast": 184800.0,
            "optimistic_forecast": 245000.0
        }
    },
    "recovery": {
        "recommended_actions": [
            {"action_type": "offer_discount", "target_entity": "Acme Corp", "description": "Offer a 15% discount on overages to close the Q3 renewal.", "confidence_score": 0.90, "priority_level": "high", "impact_value": 75000.0},
            {"action_type": "escalate_manager", "target_entity": "Globex", "description": "Escalate the batch API 500 error technical blocker to the Engineering Director.", "confidence_score": 0.95, "priority_level": "high", "impact_value": 120000.0},
            {"action_type": "reassign_opportunity", "target_entity": "Initech", "description": "Reassign the Security Module opportunity from Alice to a senior Account Executive due to 20-day ghosting.", "confidence_score": 0.75, "priority_level": "medium", "impact_value": 15000.0}
        ]
    }
}


def get_all_subagent_reports() -> Dict[str, Any]:
    """
    Fetches the combined outputs from all RevOps subagents.
    
    Returns:
        A dictionary containing CRM, Email, Calendar, Prediction, and Recovery reports.
    """
    logger.info("Fetching subagent reports...")
    return MOCK_ALL_AGENT_REPORTS


# ==========================================
# 3. Agent Definition
# ==========================================

SUMMARY_AGENT_INSTRUCTION = """
You are the Executive Summary Agent, the final synthesizer of the "Revenue Guardian" platform.
Your objective is to consume all subagent reports and compile a dashboard-ready ExecutiveSummaryResult.

You have access to the tool:
1. `get_all_subagent_reports`: Fetches the compiled reports from all other agents.

Perform the following tasks:

1. **Calculate Business Health Score (0-100)**:
   - Start with a base of 100.
   - Subtract:
     * 10 points if Pipeline Health rating is 'Fair', 25 points if 'Poor'.
     * 5 points for each high-urgency/negative-sentiment thread.
     * 5 points for each missed meeting or overdue task.
     * 15 points if the average win probability is under 50%.
   - Clamp the score between 0 and 100.

2. **Draft the Morning Briefing**:
   - Write a highly concise, punchy 3-sentence summary of the day's outlook.
   - Sentence 1: State the overall business health and active pipeline value.
   - Sentence 2: Highlight the most critical risk (e.g., Globex API blocker or Acme pricing dispute).
   - Sentence 3: State the primary action required today to secure revenue.

3. **Compile the Executive Report**:
   - Write a comprehensive, markdown-formatted report.
   - Include sections:
     * ## Executive Overview (current health score, ARR, and next 30 days outlook)
     * ## High-Risk Accounts (break down Acme, Globex, Initech with their specific risk drivers)
     * ## Pipeline & Forecast Analysis (discuss stalled percentage, win probabilities, and forecast scenarios)
     * ## Recommended Immediate Actions (bulleted list of high-impact tasks)

4. **Summarize Revenue Metrics**:
   - `total_arr`: Set to $228,000 (sum of Acme, Globex, Initech contract values: 60k + 144k + 24k).
   - `revenue_at_risk`: Sum of expected losses from predictions ($21,000 + $64,800 + $7,200 = $93,000).
   - `forecasted_revenue_next_30_days`: Expected forecast from predictions ($184,800).
   - `unbilled_overages`: Calculate total overages (Acme has 5,000 units overage @ $0.10/unit = $500).

5. **Summarize High-Priority Deals**:
   - Map active opportunities from predictions.
   - Populate `opportunity_id`, `name`, `value`, `win_probability`.
   - Identify `primary_risk` (e.g., Acme = 'Pricing dispute & missed meeting', Globex = 'Technical API blocker', Initech = 'Ghosted 20 days').
   - Link `recommended_action` from recovery strategies.

6. **Filter Today's Recommendations**:
   - Map the recommended actions from the recovery report.
   - Populate `action_type`, `target` (target_entity), `description`, `impact_value`, `urgency` (priority_level).

Return the completed summary matching the ExecutiveSummaryResult output schema.
"""

def create_summary_agent(model_name: str = "gemini-2.0-flash") -> Agent:
    """
    Factory function to create the Executive Summary Agent.

    Args:
        model_name: The name of the Gemini model (default: gemini-2.0-flash).

    Returns:
        An instantiated Google ADK Agent.
    """
    return Agent(
        name="executive_summary_agent",
        model=model_name,
        instruction=SUMMARY_AGENT_INSTRUCTION,
        description="Synthesizes all subagent findings to generate dashboard-ready executive summaries, KPIs, and reports.",
        tools=[get_all_subagent_reports],
        output_schema=ExecutiveSummaryResult
    )


# ==========================================
# 4. Programmatic Execution Runner
# ==========================================

async def run_executive_summary(model_name: str = "gemini-2.0-flash") -> ExecutiveSummaryResult:
    """
    Programmatically executes the Executive Summary Agent.

    Args:
        model_name: The Gemini model to use.

    Returns:
        A structured ExecutiveSummaryResult containing the executive reports and metrics.
    """
    agent = create_summary_agent(model_name=model_name)
    session_service = InMemorySessionService()
    runner = Runner(
        agent=agent,
        session_service=session_service,
        app_name="revenue_guardian",
        auto_create_session=True,
    )

    prompt = (
        "Synthesize all subagent reports as of 2026-06-30. "
        "Calculate the Business Health Score, draft the Morning Briefing and Executive Report, "
        "and compile the Revenue Summary, High-Priority Deals, and Today's Recommendations."
    )

    logger.info("Executing Executive Summary Agent analysis...")
    new_message = make_new_message(prompt, role="user")
    raw = runner.run(
        user_id="system",
        session_id="executive_summary_session",
        new_message=new_message
    )

    response = await run_runner_and_get_response(raw)
    return response.structured_output
