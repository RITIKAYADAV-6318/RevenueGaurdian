"""
Revenue Guardian - Revenue Prediction Agent
===========================================

This module implements the Revenue Prediction Agent using the Google Agent Development Kit (ADK).

The Revenue Prediction Agent is responsible for:
1. Fetching integrated data (CRM opportunities, Email sentiment, Calendar meetings).
2. Calculating the Win Probability for each active sales opportunity using a weighted risk/boost model.
3. Estimating the Revenue at Risk (churn risk) for existing customer accounts based on communication health.
4. Evaluating overall Pipeline Health metrics (total value, stalled percentage, health rating).
5. Generating a Revenue Forecast (Pessimistic, Expected, Optimistic) for the upcoming period.
6. Returning a structured PredictionAnalysisResult JSON payload containing the calculations and methodology.

Prediction Logic & Methodology:
-------------------------------
*   **Opportunity Win Probability**:
    *   *Baseline*: Set by pipeline stage (e.g., Discovery = 20%, Proposal = 50%, Negotiation = 80%).
    *   *Penalties*: Applied for negative signals (Stalled deal = -15%, Overdue follow-up = -10%, Negative email sentiment = -20%, Ghosted = -30%, Missed meeting = -15%).
    *   *Boosts*: Applied for positive signals (Eager/positive email tone = +15%, Upcoming meeting scheduled = +10%).
    *   *Bounds*: Clamped between 5% and 95%.
    *   *Expected Value*: Calculated as `Deal Value * Win Probability`.
*   **Revenue at Risk (Churn Risk)**:
    *   *Baseline*: 5% (natural churn baseline).
    *   *Risk Drivers*: Technical blocker = +40%, Negative sentiment/pricing objection = +30%, Missed meeting = +20%, Ghosted/no response = +25%.
    *   *Expected Loss*: Calculated as `Contract Value * Churn Risk Score`.
*   **Revenue Forecast**:
    *   *Expected*: Weighted sum of active deals (`Value * Win Prob`) + retaining contract value (`Value * (1 - Churn Risk)`).
    *   *Optimistic*: Sum of all deals with Win Prob > 40% at full value + 100% contract retention.
    *   *Pessimistic*: Sum of only high-probability deals (> 75%) + contract value minus all expected churn losses.
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
logger = logging.getLogger("RevenuePredictionAgent")


# ==========================================
# 1. Structured Output & Domain Schemas
# ==========================================

class OpportunityWinProbability(BaseModel):
    """Calculated win probability and drivers for an active sales opportunity."""
    opportunity_id: str = Field(..., description="Unique identifier for the opportunity.")
    name: str = Field(..., description="Name of the opportunity.")
    current_value: float = Field(..., description="Raw value of the deal in USD.")
    win_probability: float = Field(..., description="Calculated win probability (0.0 to 1.0).")
    risk_factors: List[str] = Field(default_factory=list, description="Negative factors depressing the win probability.")
    boost_factors: List[str] = Field(default_factory=list, description="Positive factors supporting the win probability.")
    calculated_expected_value: float = Field(..., description="Weighted expected value (current_value * win_probability).")


class RevenueAtRisk(BaseModel):
    """Estimated churn risk and financial impact for an active customer contract."""
    customer_name: str = Field(..., description="Name of the customer account.")
    contract_value: float = Field(..., description="Monthly or annual contract value in USD.")
    churn_risk_score: float = Field(..., description="Calculated probability of churn (0.0 to 1.0).")
    risk_drivers: List[str] = Field(default_factory=list, description="Key factors driving the churn risk.")
    expected_loss: float = Field(..., description="Weighted expected financial loss (contract_value * churn_risk_score).")


class PipelineHealthMetrics(BaseModel):
    """Aggregated health metrics of the active sales pipeline."""
    total_pipeline_value: float = Field(..., description="Total value of all active opportunities in the pipeline.")
    stalled_deal_percentage: float = Field(..., description="Percentage of total pipeline value that is currently stalled.")
    average_win_probability: float = Field(..., description="Weighted average win probability of the pipeline.")
    health_rating: str = Field(..., description="Overall pipeline health rating: 'Excellent', 'Good', 'Fair', or 'Poor'.")
    bottlenecks: List[str] = Field(default_factory=list, description="Identified operational bottlenecks.")


class RevenueForecast(BaseModel):
    """Multi-scenario revenue forecast for the upcoming period."""
    forecast_period: str = Field(..., description="The period for which the forecast is made (e.g., 'Next 30 Days').")
    pessimistic_forecast: float = Field(..., description="Conservative forecast assuming high churn and low deal closure.")
    expected_forecast: float = Field(..., description="Weighted forecast based on probabilities.")
    optimistic_forecast: float = Field(..., description="Aggressive forecast assuming high deal closure and zero churn.")
    forecast_drivers: List[str] = Field(default_factory=list, description="Key drivers behind the forecast scenarios.")


class PredictionAnalysisResult(BaseModel):
    """The structured report returned by the Prediction Agent to the Manager Agent."""
    timestamp: str = Field(..., description="ISO timestamp of when the analysis was performed.")
    opportunities_win_probability: List[OpportunityWinProbability] = Field(..., description="Win probability analysis for active opportunities.")
    revenue_at_risk: List[RevenueAtRisk] = Field(..., description="Churn risk analysis for active customer contracts.")
    pipeline_health: PipelineHealthMetrics = Field(..., description="Aggregated pipeline health metrics.")
    revenue_forecast: RevenueForecast = Field(..., description="Multi-scenario revenue forecast.")
    methodology_explanation: str = Field(..., description="Detailed mathematical explanation of the prediction logic.")


# ==========================================
# 2. Integrated Data Retrieval Tools
# ==========================================

# Mock database representing the unified state compiled from CRM, Email, and Calendar systems.
INTEGRATED_REVOPS_DATA = {
    "opportunities": [
        {
            "opportunity_id": "OPP_201",
            "name": "Acme Corp - Enterprise Expansion",
            "deal_value": 75000.0,
            "current_stage": "Proposal/Price Quote",
            "is_stalled": True,
            "overdue_tasks": 1,
            "email_sentiment": "negative",       # Pricing objection
            "email_intent": "pricing_inquiry",
            "missed_meetings": 1,                 # Bob missed the renewal discussion
            "is_ghosted": False
        },
        {
            "opportunity_id": "OPP_202",
            "name": "Globex - API Platform Migration",
            "deal_value": 120000.0,
            "current_stage": "Negotiation/Review",
            "is_stalled": False,
            "overdue_tasks": 1,                   # Overdue by 1 day
            "email_sentiment": "negative",       # Tech blocker (500 errors)
            "email_intent": "technical_blocker",
            "missed_meetings": 0,
            "is_ghosted": False
        },
        {
            "opportunity_id": "OPP_203",
            "name": "Initech - Security Module Add-on",
            "deal_value": 15000.0,
            "current_stage": "Discovery",
            "is_stalled": True,                   # Stalled 30 days in discovery
            "overdue_tasks": 0,
            "email_sentiment": "neutral",
            "email_intent": "unresponsive",
            "missed_meetings": 0,
            "is_ghosted": True                    # Ghosted sales rep for 20 days
        }
    ],
    "contracts": [
        {
            "customer_name": "Acme Corp",
            "contract_value": 60000.0,            # Annual contract value
            "has_pricing_discrepancy": False,
            "recent_sentiment": "negative",
            "recent_missed_meetings": 1,
            "recent_ghosting": False
        },
        {
            "customer_name": "Globex",
            "contract_value": 144000.0,
            "has_pricing_discrepancy": False,
            "recent_sentiment": "negative",       # Technical blocker
            "recent_missed_meetings": 0,
            "recent_ghosting": False
        },
        {
            "customer_name": "Initech",
            "contract_value": 24000.0,
            "has_pricing_discrepancy": False,
            "recent_sentiment": "neutral",
            "recent_missed_meetings": 0,
            "recent_ghosting": True               # Ghosting us
        }
    ]
}


def get_active_opportunities() -> List[Dict[str, Any]]:
    """
    Fetches the active opportunities along with their integrated email and calendar signals.

    Returns:
        A list of opportunities with enriched risk signals.
    """
    logger.info("Fetching enriched opportunity data...")
    return INTEGRATED_REVOPS_DATA["opportunities"]


def get_active_contracts() -> List[Dict[str, Any]]:
    """
    Fetches the active customer contracts along with their health indicators.

    Returns:
        A list of customer contracts with health indicators.
    """
    logger.info("Fetching active contract health data...")
    return INTEGRATED_REVOPS_DATA["contracts"]


# ==========================================
# 3. Agent Definition
# ==========================================

PREDICTION_AGENT_INSTRUCTION = """
You are the Revenue Prediction Agent, a specialized component of the "Revenue Guardian" platform.
Your objective is to run predictive financial models on active deals and customer contracts.

You have access to two tools:
1. `get_active_opportunities`: Fetches active deals with integrated risk signals.
2. `get_active_contracts`: Fetches active customer contracts with health signals.

Perform the following calculations:

1. **Opportunity Win Probability**:
   For each opportunity:
   - Start with a baseline probability based on stage: 'Discovery' = 0.20, 'Proposal/Price Quote' = 0.50, 'Negotiation/Review' = 0.80.
   - Apply penalties: Stalled = -0.15, Overdue tasks = -0.10, Negative email sentiment = -0.20, Ghosted = -0.30, Missed meetings = -0.15.
   - Apply boosts: Positive email sentiment = +0.15.
   - Clamp the final probability between 0.05 and 0.95.
   - Document the specific risk/boost factors applied.
   - Calculate the expected value: `deal_value * win_probability`.

2. **Revenue at Risk (Churn Risk)**:
   For each contract:
   - Start with a baseline churn risk of 0.05 (5%).
   - Add risk drivers: Technical blocker = +0.40, Negative sentiment/pricing objection = +0.30, Missed meeting = +0.20, Ghosting = +0.25.
   - Calculate the expected loss: `contract_value * churn_risk_score`.
   - Document the specific drivers.

3. **Pipeline Health Metrics**:
   - Calculate `total_pipeline_value` (sum of all deal values).
   - Calculate `stalled_deal_percentage` (value of stalled deals / total pipeline value).
   - Calculate `average_win_probability` (weighted average: sum(expected_value) / total_pipeline_value).
   - Determine `health_rating`:
     * Excellent: Stalled < 10% and Avg Win Prob > 60%
     * Good: Stalled < 25% and Avg Win Prob > 45%
     * Fair: Stalled < 40% and Avg Win Prob > 30%
     * Poor: Otherwise.
   - Identify bottlenecks based on stalled deals, overdue tasks, or technical blockers.

4. **Revenue Forecast (Next 30 Days)**:
   - Calculate three scenarios:
     * `expected_forecast`: Sum of all opportunity expected values + Sum of all contract values * (1 - churn_risk_score).
     * `optimistic_forecast`: Sum of all opportunity deal values (where win_probability > 0.40) + 100% of contract values.
     * `pessimistic_forecast`: Sum of only high-probability opportunity expected values (win_probability > 0.70) + Sum of contract values * (1 - expected_loss_ratio, assuming worst-case churn).
   - Detail the forecast drivers.

Return the completed analysis matching the PredictionAnalysisResult output schema.
"""

def create_prediction_agent(model_name: str = "gemini-2.0-flash") -> Agent:
    """
    Factory function to create the Revenue Prediction Agent.

    Args:
        model_name: The name of the Gemini model (default: gemini-2.0-flash).

    Returns:
        An instantiated Google ADK Agent.
    """
    return Agent(
        name="revenue_prediction_agent",
        model=model_name,
        instruction=PREDICTION_AGENT_INSTRUCTION,
        description="Calculates deal win probabilities, revenue at risk, pipeline health, and multi-scenario forecasts.",
        tools=[
            get_active_opportunities,
            get_active_contracts
        ],
        output_schema=PredictionAnalysisResult
    )


# ==========================================
# 4. Programmatic Execution Runner
# ==========================================

async def run_prediction_analysis(model_name: str = "gemini-2.0-flash") -> PredictionAnalysisResult:
    """
    Programmatically executes the Revenue Prediction Agent.

    Args:
        model_name: The Gemini model to use.

    Returns:
        A structured PredictionAnalysisResult containing the predictive models.
    """
    agent = create_prediction_agent(model_name=model_name)
    session_service = InMemorySessionService()
    runner = Runner(agent=agent, session_service=session_service)

    prompt = (
        "Run the revenue prediction models on the active opportunities and customer contracts. "
        "Calculate opportunity win probabilities, revenue at risk, pipeline health, "
        "and generate a 30-day revenue forecast. Explain the methodology in detail."
    )

    logger.gc = logger.info("Executing Revenue Prediction Agent analysis...")
    response = await runner.run(
        session_id="prediction_analysis_session",
        user_prompt=prompt
    )

    return response.structured_output
 Pals
