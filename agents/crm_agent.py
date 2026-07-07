"""
Revenue Guardian - CRM Intelligence Agent
==========================================

This module implements the CRM Intelligence Agent using the Google Agent Development Kit (ADK).

The CRM Intelligence Agent is responsible for:
1. Reading raw CRM data (leads, opportunities, tasks) from the CRM system (mocked here).
2. Detecting inactive leads (no activity in > 30 days).
3. Identifying overdue follow-ups (next action date is in the past).
4. Identifying stalled opportunities (stuck in a pipeline stage longer than the stage threshold).
5. Prioritizing deals using a weighted scoring model based on deal value, stage, and risk.
6. Returning a structured CRMAnalysisResult JSON payload to the Manager Agent.

Design Decisions:
-----------------
*   **Structured Outputs**: Returns a highly detailed Pydantic model (`CRMAnalysisResult`) containing structured lists
    of inactive leads, overdue tasks, stalled deals, and prioritized opportunities.
*   **Decoupled CRM Mocking**: CRM queries are wrapped in ADK tools. In production, these tools would call
    an MCP CRM Server (e.g., interfacing with HubSpot or Salesforce APIs).
*   **Enterprise-Grade Analysis**: Implements clear business logic thresholds (e.g., 30 days inactive, 14 days stalled
    for early stages, 30 days stalled for late stages) and a transparent priority scoring algorithm.
"""

import logging
from datetime import datetime, date
from typing import List, Optional, Any, Dict
from pydantic import BaseModel, Field

# Import core Google ADK components
from google.adk.agents import Agent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("CRMIntelligenceAgent")


# ==========================================
# 1. Structured Output & Domain Schemas
# ==========================================

class InactiveLead(BaseModel):
    """Represents a lead with no recent activity."""
    lead_id: str = Field(..., description="Unique identifier for the lead.")
    name: str = Field(..., description="Full name of the lead contact.")
    company: str = Field(..., description="Company name associated with the lead.")
    last_activity_date: str = Field(..., description="ISO date of the last recorded interaction.")
    days_inactive: int = Field(..., description="Number of days elapsed since the last activity.")
    recommended_action: str = Field(..., description="AI-recommended re-engagement strategy.")


class OverdueFollowUp(BaseModel):
    """Represents a sales task or follow-up that is past its scheduled date."""
    task_id: str = Field(..., description="Unique identifier for the task.")
    opportunity_name: str = Field(..., description="Name of the associated opportunity.")
    owner_email: str = Field(..., description="Email of the sales representative owning this task.")
    task_description: str = Field(..., description="Description of the scheduled follow-up activity.")
    due_date: str = Field(..., description="ISO date when the task was due.")
    days_overdue: int = Field(..., description="Number of days the task is overdue.")


class StalledOpportunity(BaseModel):
    """Represents a deal that has been stuck in a pipeline stage too long."""
    opportunity_id: str = Field(..., description="Unique identifier for the opportunity.")
    name: str = Field(..., description="Name of the opportunity.")
    current_stage: str = Field(..., description="Current sales pipeline stage.")
    days_in_stage: int = Field(..., description="Number of days the deal has remained in the current stage.")
    deal_value: float = Field(..., description="Estimated value of the deal in USD.")
    risk_factor: str = Field(..., description="Risk assessment explaining why the deal is stalled.")


class PrioritizedDeal(BaseModel):
    """Represents a high-priority opportunity ranked by value and urgency."""
    opportunity_id: str = Field(..., description="Unique identifier for the opportunity.")
    name: str = Field(..., description="Name of the opportunity.")
    deal_value: float = Field(..., description="Value of the deal in USD.")
    priority_score: int = Field(..., description="Calculated priority score (1-100) based on value and urgency.")
    priority_reasoning: str = Field(..., description="Explanation of why this deal is prioritized.")
    next_step: str = Field(..., description="Immediate next action required to move the deal forward.")


class CRMAnalysisResult(BaseModel):
    """Structured report returned by the CRM Agent to the Manager Agent."""
    timestamp: str = Field(..., description="ISO timestamp of when the analysis was performed.")
    inactive_leads: List[InactiveLead] = Field(default_factory=list, description="List of inactive leads detected.")
    overdue_follow_ups: List[OverdueFollowUp] = Field(default_factory=list, description="List of overdue follow-ups.")
    stalled_opportunities: List[StalledOpportunity] = Field(default_factory=list, description="List of stalled deals.")
    prioritized_deals: List[PrioritizedDeal] = Field(default_factory=list, description="Top deals prioritized for action.")
    executive_summary: str = Field(..., description="Executive summary of the CRM database health and key alerts.")


# ==========================================
# 2. Mock CRM Data & Tool Definitions
# ==========================================

# Mock CRM Database representing an enterprise pipeline
MOCK_CRM_DATABASE = {
    "leads": [
        {
            "lead_id": "LD_101",
            "name": "Sarah Jenkins",
            "company": "Nexus Media",
            "last_activity_date": "2026-05-15",  # Highly inactive (current date is 2026-06-30)
            "status": "Contacted"
        },
        {
            "lead_id": "LD_102",
            "name": "Michael Chen",
            "company": "Apex Logistics",
            "last_activity_date": "2026-06-28",  # Recently active
            "status": "Working"
        },
        {
            "lead_id": "LD_103",
            "name": "Elena Rostova",
            "company": "Siberia Tech",
            "last_activity_date": "2026-04-10",  # Stale lead
            "status": "Qualified"
        }
    ],
    "opportunities": [
        {
            "opportunity_id": "OPP_201",
            "name": "Acme Corp - Enterprise Expansion",
            "current_stage": "Proposal/Price Quote",
            "stage_last_updated": "2026-05-10",  # Stalled (stuck > 50 days)
            "deal_value": 75000.0,
            "owner_email": "alice.rep@guardian.com"
        },
        {
            "opportunity_id": "OPP_202",
            "name": "Globex - API Platform Migration",
            "current_stage": "Negotiation/Review",
            "stage_last_updated": "2026-06-25",  # Active deal
            "deal_value": 120000.0,
            "owner_email": "bob.rep@guardian.com"
        },
        {
            "opportunity_id": "OPP_203",
            "name": "Initech - Security Module Add-on",
            "current_stage": "Discovery",
            "stage_last_updated": "2026-06-01",  # Stalled (stuck 30 days in discovery)
            "deal_value": 15000.0,
            "owner_email": "alice.rep@guardian.com"
        }
    ],
    "tasks": [
        {
            "task_id": "TSK_301",
            "opportunity_id": "OPP_201",
            "opportunity_name": "Acme Corp - Enterprise Expansion",
            "owner_email": "alice.rep@guardian.com",
            "task_description": "Send revised SLA agreement",
            "due_date": "2026-06-15",  # Overdue
            "status": "Open"
        },
        {
            "task_id": "TSK_302",
            "opportunity_id": "OPP_202",
            "opportunity_name": "Globex - API Platform Migration",
            "owner_email": "bob.rep@guardian.com",
            "task_description": "Follow up on security review sign-off",
            "due_date": "2026-06-29",  # Overdue (by 1 day)
            "status": "Open"
        },
        {
            "task_id": "TSK_303",
            "opportunity_id": "OPP_203",
            "opportunity_name": "Initech - Security Module Add-on",
            "owner_email": "alice.rep@guardian.com",
            "task_description": "Schedule demo call",
            "due_date": "2026-07-05",  # Future task
            "status": "Open"
        }
    ]
}


def get_crm_leads() -> List[Dict[str, Any]]:
    """
    Retrieves the raw list of leads from the CRM system.
    
    Returns:
        A list of dictionaries representing leads.
    """
    logger.info("Fetching leads from CRM...")
    return MOCK_CRM_DATABASE["leads"]


def get_crm_opportunities() -> List[Dict[str, Any]]:
    """
    Retrieves the raw list of active opportunities from the CRM system.
    
    Returns:
        A list of dictionaries representing opportunities.
    """
    logger.info("Fetching opportunities from CRM...")
    return MOCK_CRM_DATABASE["opportunities"]


def get_crm_tasks() -> List[Dict[str, Any]]:
    """
    Retrieves the raw list of open sales tasks from the CRM system.
    
    Returns:
        A list of dictionaries representing tasks.
    """
    logger.info("Fetching sales tasks from CRM...")
    return MOCK_CRM_DATABASE["tasks"]


# ==========================================
# 3. Agent Definition
# ==========================================

CRM_AGENT_INSTRUCTION = """
You are the CRM Intelligence Agent, a specialized component of the "Revenue Guardian" platform.
Your objective is to analyze CRM data to identify operational bottlenecks and revenue risks.

You have access to three tools:
1. `get_crm_leads`: Fetches raw lead data.
2. `get_crm_opportunities`: Fetches active deal opportunities.
3. `get_crm_tasks`: Fetches open sales follow-up tasks.

Perform the following analysis:
1. **Inactive Leads**: A lead is inactive if the last activity was more than 30 days before 2026-06-30. Identify these leads and recommend a re-engagement strategy.
2. **Overdue Follow-ups**: Identify tasks where the due date is before 2026-06-30. Calculate how many days they are overdue.
3. **Stalled Opportunities**: An opportunity is stalled if it has been in the same stage for too long:
   - More than 14 days in 'Discovery'.
   - More than 30 days in 'Proposal/Price Quote' or 'Negotiation/Review'.
   Calculate the days in the current stage based on the `stage_last_updated` compared to 2026-06-30. Explain the risk.
4. **Prioritize Deals**: Score the opportunities from 1 to 100.
   - High value deals (e.g. > $50,000) get higher base scores.
   - Stalled status or overdue tasks increase the urgency (higher priority).
   - Provide a clear next step for each prioritized deal.

Return the completed analysis matching the CRMAnalysisResult output schema.
"""

def create_crm_agent(model_name: str = "gemini-2.0-flash") -> Agent:
    """
    Factory function to create the CRM Intelligence Agent.

    Args:
        model_name: The name of the Gemini model (default: gemini-2.0-flash).

    Returns:
        An instantiated Google ADK Agent.
    """
    return Agent(
        name="crm_intelligence_agent",
        model=model_name,
        instruction=CRM_AGENT_INSTRUCTION,
        description="Analyzes CRM pipelines to detect inactive leads, stalled deals, and overdue tasks.",
        tools=[
            get_crm_leads,
            get_crm_opportunities,
            get_crm_tasks
        ],
        output_schema=CRMAnalysisResult
    )


# ==========================================
# 4. Programmatic Execution Runner
# ==========================================

async def run_crm_analysis(model_name: str = "gemini-2.0-flash") -> CRMAnalysisResult:
    """
    Programmatically executes the CRM Intelligence Agent.

    Args:
        model_name: The Gemini model to use.

    Returns:
        A structured CRMAnalysisResult containing the pipeline analysis.
    """
    agent = create_crm_agent(model_name=model_name)
    session_service = InMemorySessionService()
    runner = Runner(agent=agent, session_service=session_service, app_name="revenue_guardian")

    prompt = (
        "Perform a pipeline analysis on the CRM data as of 2026-06-30. "
        "Identify all inactive leads, overdue tasks, and stalled opportunities, "
        "and provide a prioritized list of deals requiring action."
    )

    logger.info("Executing CRM Intelligence Agent analysis...")
    response = await runner.run(
        session_id="crm_analysis_session",
        user_prompt=prompt
    )

    return response.structured_output
