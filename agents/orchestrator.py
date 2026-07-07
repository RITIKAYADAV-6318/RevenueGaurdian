"""
Revenue Guardian - Multi-Agent Orchestrator
===========================================

This module implements the central Orchestrator for the Revenue Guardian platform
using the Google Agent Development Kit (ADK).

It connects all specialized agents:
1. CRM Intelligence Agent (Data Extraction & Pipeline Audit)
2. Email Intelligence Agent (Sentiment, Urgency, & Intent)
3. Calendar Agent (Missed Meetings & Scheduling)
4. Revenue Prediction Agent (Win Probability, Churn Risk, & Forecasts)
5. Recovery Strategy Agent (Action Items & Confidence Scores)
6. Executive Summary Agent (Morning Briefing & KPIs)

Architecture & Flow:
--------------------
1.  **Concurrence (Phase 1: Extraction)**:
    Executes the CRM, Email, and Calendar agents in parallel using `asyncio.gather`
    to minimize latency.
2.  **Shared Context & Message Passing (Phase 2: Prediction)**:
    Collects Pydantic outputs from Phase 1, serializes them to JSON, and passes them
    into the prompt context of the Revenue Prediction Agent.
3.  **Synthesis (Phase 3: Recovery)**:
    Passes all previous findings (CRM, Email, Calendar, and Predictions) to the
    Recovery Strategy Agent to draft concrete action plans.
4.  **Presentation (Phase 4: Summary)**:
    Passes the complete history to the Executive Summary Agent to generate the
    final dashboard-ready morning briefing and KPIs.
5.  **Robust Error Handling**:
    If any agent fails (e.g., API timeout or database error), the Orchestrator catches
    the exception, logs it, and continues the pipeline in a degraded state (partial success),
    ensuring maximum system availability.
"""

import asyncio
import logging
from datetime import datetime
from typing import List, Optional, Any, Dict
from pydantic import BaseModel, Field

# Import core Google ADK components
from google.adk.agents import Agent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from agents.runner_utils import run_runner_and_get_response

# Import subagent factories
from agents.crm_agent import create_crm_agent, CRMAnalysisResult
from agents.email_agent import create_email_agent, EmailIntelligenceResult
from agents.calendar_agent import create_calendar_agent, CalendarAnalysisResult
from agents.prediction_agent import create_prediction_agent, PredictionAnalysisResult
from agents.recovery_agent import create_recovery_agent, RecoveryStrategyResult
from agents.summary_agent import create_summary_agent, ExecutiveSummaryResult

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("Orchestrator")


# ==========================================
# 1. Orchestration Output Schemas
# ==========================================

class OrchestratorFailureLog(BaseModel):
    """Logs a subagent failure during the orchestration run."""
    agent_name: str = Field(..., description="The name of the agent that failed.")
    error_message: str = Field(..., description="The exception or error message.")
    timestamp: str = Field(..., description="ISO timestamp of the failure.")


class OrchestrationRunResult(BaseModel):
    """The final response returned by the Orchestrator containing the unified results."""
    run_id: str = Field(..., description="Unique ID for this orchestration run.")
    status: str = Field(..., description="Run status: 'success', 'partial_success', or 'failed'.")
    timestamp: str = Field(..., description="ISO timestamp of the run completion.")
    
    # Subagent Results
    crm_analysis: Optional[CRMAnalysisResult] = Field(None, description="Output from the CRM Agent.")
    email_analysis: Optional[EmailIntelligenceResult] = Field(None, description="Output from the Email Agent.")
    calendar_analysis: Optional[CalendarAnalysisResult] = Field(None, description="Output from the Calendar Agent.")
    prediction_analysis: Optional[PredictionAnalysisResult] = Field(None, description="Output from the Prediction Agent.")
    recovery_strategy: Optional[RecoveryStrategyResult] = Field(None, description="Output from the Recovery Agent.")
    executive_summary: Optional[ExecutiveSummaryResult] = Field(None, description="Output from the Summary Agent.")
    
    # Failures encountered
    failures: List[OrchestratorFailureLog] = Field(default_factory=list, description="List of subagent failures during the run.")


# ==========================================
# 2. Central Orchestrator Engine
# ==========================================

class RevOpsOrchestrator:
    """Coordinates the multi-agent execution pipeline using Google ADK."""

    def __init__(self, model_name: str = "gemini-2.0-flash"):
        """
        Initializes the Orchestrator with the specified Gemini model.
        
        Args:
            model_name: The Gemini model to use for all agents.
        """
        self.model_name = model_name
        self.session_service = InMemorySessionService()

        # Instantiate all subagents using their factory functions
        self.crm_agent = create_crm_agent(model_name=model_name)
        self.email_agent = create_email_agent(model_name=model_name)
        self.calendar_agent = create_calendar_agent(model_name=model_name)
        self.prediction_agent = create_prediction_agent(model_name=model_name)
        self.recovery_agent = create_recovery_agent(model_name=model_name)
        self.summary_agent = create_summary_agent(model_name=model_name)

    async def _run_agent(self, agent: Agent, prompt: str, session_id: str) -> Any:
        """
        Helper method to run a single ADK Agent using the Runner.

        Args:
            agent: The ADK Agent to execute.
            prompt: The prompt containing instructions and context.
            session_id: The session ID for the execution.

        Returns:
            The structured Pydantic output from the agent.
        """
        runner = Runner(agent=agent, session_service=self.session_service, app_name="revenue_guardian")
        raw = runner.run(user_id="system", session_id=session_id, new_message=prompt)
        response = await run_runner_and_get_response(raw)
        return response.structured_output

    async def execute_workflow(self, run_id: str) -> OrchestrationRunResult:
        """
        Executes the entire multi-agent RevOps workflow.

        Args:
            run_id: A unique identifier for this execution run.

        Returns:
            An OrchestrationRunResult containing the merged outputs and any failure logs.
        """
        logger.info(f"Starting RevOps Orchestrator Workflow. Run ID: {run_id}")
        
        # Centralized state (Shared Context)
        context = {
            "crm_analysis": None,
            "email_analysis": None,
            "calendar_analysis": None,
            "prediction_analysis": None,
            "recovery_strategy": None,
            "executive_summary": None
        }
        failures: List[OrchestratorFailureLog] = []

        # ==========================================
        # PHASE 1: Parallel Data Extraction
        # ==========================================
        logger.info("Executing Phase 1: Parallel extraction (CRM, Email, Calendar)...")
        
        # Define async tasks for the three extraction agents
        crm_prompt = "Perform a pipeline analysis on the CRM data as of 2026-06-30. Identify inactive leads, overdue tasks, and stalled opportunities."
        email_prompt = "Analyze all recent email threads as of 2026-06-30. Perform sentiment, urgency, and ghosting analysis."
        calendar_prompt = "Analyze calendar events as of 2026-06-30. Identify missed meetings, overdue follow-ups, and renewals."

        crm_task = self._run_agent(self.crm_agent, crm_prompt, f"{run_id}_crm")
        email_task = self._run_agent(self.email_agent, email_prompt, f"{run_id}_email")
        calendar_task = self._run_agent(self.calendar_agent, calendar_prompt, f"{run_id}_calendar")

        # Execute concurrently to minimize latency
        results = await asyncio.gather(crm_task, email_task, calendar_task, return_exceptions=True)

        # Process CRM Agent result
        if isinstance(results[0], Exception):
            logger.error(f"CRM Agent failed: {str(results[0])}")
            failures.append(OrchestratorFailureLog(
                agent_name="crm_intelligence_agent",
                error_message=str(results[0]),
                timestamp=datetime.utcnow().isoformat()
            ))
        else:
            context["crm_analysis"] = results[0]

        # Process Email Agent result
        if isinstance(results[1], Exception):
            logger.error(f"Email Agent failed: {str(results[1])}")
            failures.append(OrchestratorFailureLog(
                agent_name="email_intelligence_agent",
                error_message=str(results[1]),
                timestamp=datetime.utcnow().isoformat()
            ))
        else:
            context["email_analysis"] = results[1]

        # Process Calendar Agent result
        if isinstance(results[2], Exception):
            logger.error(f"Calendar Agent failed: {str(results[2])}")
            failures.append(OrchestratorFailureLog(
                agent_name="calendar_agent",
                error_message=str(results[2]),
                timestamp=datetime.utcnow().isoformat()
            ))
        else:
            context["calendar_analysis"] = results[2]

        # ==========================================
        # PHASE 2: Revenue Prediction (Message Passing)
        # ==========================================
        logger.info("Executing Phase 2: Revenue Prediction...")
        
        # Build prompt incorporating Phase 1 outputs (Shared Context Passing)
        prediction_prompt = (
            "Run the revenue prediction models as of 2026-06-30.\n\n"
            "Here is the context gathered from the other agents:\n"
            f"CRM Analysis: {context['crm_analysis'].model_dump_json() if context['crm_analysis'] else 'No data available due to agent failure.'}\n\n"
            f"Email Analysis: {context['email_analysis'].model_dump_json() if context['email_analysis'] else 'No data available due to agent failure.'}\n\n"
            f"Calendar Analysis: {context['calendar_analysis'].model_dump_json() if context['calendar_analysis'] else 'No data available due to agent failure.'}\n\n"
            "Calculate opportunity win probabilities, revenue at risk, and the 30-day forecast."
        )

        try:
            context["prediction_analysis"] = await self._run_agent(
                self.prediction_agent, prediction_prompt, f"{run_id}_prediction"
            )
        except Exception as e:
            logger.error(f"Prediction Agent failed: {str(e)}")
            failures.append(OrchestratorFailureLog(
                agent_name="revenue_prediction_agent",
                error_message=str(e),
                timestamp=datetime.utcnow().isoformat()
            ))

        # ==========================================
        # PHASE 3: Recovery Strategy (Synthesis)
        # ==========================================
        logger.info("Executing Phase 3: Recovery Strategy...")
        
        recovery_prompt = (
            "Determine the optimal recovery strategy for all at-risk accounts as of 2026-06-30.\n\n"
            "Here is the synthesized context from the previous agents:\n"
            f"CRM Analysis: {context['crm_analysis'].model_dump_json() if context['crm_analysis'] else 'N/A'}\n"
            f"Email Analysis: {context['email_analysis'].model_dump_json() if context['email_analysis'] else 'N/A'}\n"
            f"Calendar Analysis: {context['calendar_analysis'].model_dump_json() if context['calendar_analysis'] else 'N/A'}\n"
            f"Revenue Prediction: {context['prediction_analysis'].model_dump_json() if context['prediction_analysis'] else 'N/A'}\n\n"
            "Draft concrete actions (call, email, escalate, discount, reassign) with confidence scores and reasoning."
        )

        try:
            context["recovery_strategy"] = await self._run_agent(
                self.recovery_agent, recovery_prompt, f"{run_id}_recovery"
            )
        except Exception as e:
            logger.error(f"Recovery Agent failed: {str(e)}")
            failures.append(OrchestratorFailureLog(
                agent_name="recovery_strategy_agent",
                error_message=str(e),
                timestamp=datetime.utcnow().isoformat()
            ))

        # ==========================================
        # PHASE 4: Executive Summary (Presentation)
        # ==========================================
        logger.info("Executing Phase 4: Executive Summary...")
        
        summary_prompt = (
            "Generate the final dashboard-ready executive summary as of 2026-06-30.\n\n"
            "Here is the complete context compiled across all agents:\n"
            f"CRM Analysis: {context['crm_analysis'].model_dump_json() if context['crm_analysis'] else 'N/A'}\n"
            f"Email Analysis: {context['email_analysis'].model_dump_json() if context['email_analysis'] else 'N/A'}\n"
            f"Calendar Analysis: {context['calendar_analysis'].model_dump_json() if context['calendar_analysis'] else 'N/A'}\n"
            f"Revenue Prediction: {context['prediction_analysis'].model_dump_json() if context['prediction_analysis'] else 'N/A'}\n"
            f"Recovery Strategy: {context['recovery_strategy'].model_dump_json() if context['recovery_strategy'] else 'N/A'}\n\n"
            "Compile the Morning Briefing, Executive Report, Revenue Summary, High-Priority Deals, and Today's Recommendations."
        )

        try:
            context["executive_summary"] = await self._run_agent(
                self.summary_agent, summary_prompt, f"{run_id}_summary"
            )
        except Exception as e:
            logger.error(f"Summary Agent failed: {str(e)}")
            failures.append(OrchestratorFailureLog(
                agent_name="executive_summary_agent",
                error_message=str(e),
                timestamp=datetime.utcnow().isoformat()
            ))

        # ==========================================
        # Status Determination & Result Packaging
        # ==========================================
        # Determine the final run status
        if not failures:
            status = "success"
        elif len(failures) < 6:  # Some agents succeeded
            status = "partial_success"
        else:
            status = "failed"

        logger.info(f"Orchestrator Workflow completed. Status: {status}. Failures encountered: {len(failures)}")

        return OrchestrationRunResult(
            run_id=run_id,
            status=status,
            timestamp=datetime.utcnow().isoformat(),
            crm_analysis=context["crm_analysis"],
            email_analysis=context["email_analysis"],
            calendar_analysis=context["calendar_analysis"],
            prediction_analysis=context["prediction_analysis"],
            recovery_strategy=context["recovery_strategy"],
            executive_summary=context["executive_summary"],
            failures=failures
        )


# ==========================================
# 3. Demonstration Entrypoint
# ==========================================

async def main():
    """Demonstrates a complete orchestration run."""
    orchestrator = RevOpsOrchestrator()
    run_id = f"run_{int(datetime.utcnow().timestamp())}"
    
    # Run the workflow
    result = await orchestrator.execute_workflow(run_id)
    
    print("\n==============================================")
    print(f"ORCHESTRATION RUN COMPLETED: {result.status.upper()}")
    print(f"Run ID: {result.run_id}")
    print(f"Timestamp: {result.timestamp}")
    print("==============================================")
    
    if result.failures:
        print("\nFailures Encountered:")
        for failure in result.failures:
            print(f"- {failure.agent_name}: {failure.error_message}")
            
    if result.executive_summary:
        print("\n--- MORNING BRIEFING ---")
        print(result.executive_summary.morning_briefing)
        
        print("\n--- REVENUE SUMMARY ---")
        rev = result.executive_summary.revenue_summary
        print(f"Total ARR: ${rev.total_arr:,.2f}")
        print(f"Revenue at Risk: ${rev.revenue_at_risk:,.2f}")
        print(f"30-Day Forecast: ${rev.forecasted_revenue_next_30_days:,.2f}")
        print(f"Unbilled Overages: ${rev.unbilled_overages:,.2f}")
        
        print("\n--- TODAY'S RECOMMENDATIONS ---")
        for rec in result.executive_summary.todays_recommendations:
            print(f"[{rec.urgency.upper()}] {rec.action_type.replace('_', ' ').title()} - {rec.target}")
            print(f"  Description: {rec.description}")
            print(f"  Impact Value: ${rec.impact_value:,.2f}")


if __name__ == "__main__":
    # To run this file directly: python -m agents.orchestrator
    asyncio.run(main())
