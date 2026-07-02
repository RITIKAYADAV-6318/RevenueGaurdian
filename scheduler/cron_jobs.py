"""
Revenue Guardian - Autonomous Daily Workflow Scheduler
=======================================================

This module implements the daily scheduling system for the Revenue Guardian platform,
running under the "Antigravity" agentic runtime.

The workflow executes every morning at 8:00 AM (local time):
1.  **Read CRM**: Fetches the latest leads, deals, and tasks.
2.  **Read Gmail**: Fetches recent customer email threads.
3.  **Read Calendar**: Fetches meeting logs and availability.
4.  **Run All Agents**: Executes the `RevOpsOrchestrator` to coordinate the Auditor,
    Sentinel, Sales Assistant, Prediction, and Recovery agents.
5.  **Generate Dashboard**: Dispatches the final KPI payload to the database/dashboard.
6.  **Notify Manager**: Dispatches a morning briefing alert to Slack (#revops-alerts).
7.  **Generate Executive Report**: Saves a markdown-formatted report to the local file system.
8.  **Sleep**: Suspends execution until the next morning at 8:00 AM.

Scheduling Options:
-------------------
1.  **Application-Level (FastAPI Background Task)**:
    Runs as an asynchronous background loop in the FastAPI application.
2.  **System-Level (Antigravity `/schedule` Command)**:
    Can be scheduled natively in the Antigravity platform using the `/schedule` command,
    which registers a persistent background cron job.
"""

import asyncio
import logging
from datetime import datetime, time, timedelta
from typing import Optional

# Import the Orchestrator
from agents.orchestrator import RevOpsOrchestrator
from mcp.server import notify_slack, generate_dashboard

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("WorkflowScheduler")


# ==========================================
# 1. Daily Autonomous Workflow
# ==========================================

async def run_daily_revops_workflow(run_id: Optional[str] = None):
    """
    Executes the complete end-to-end Revenue Guardian workflow.
    
    This function coordinates the reading, analysis, prediction, recovery,
    dashboard generation, and notification dispatch.
    """
    if not run_id:
        run_id = f"daily_run_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
        
    logger.info(f"Triggering Autonomous Daily Workflow. Run ID: {run_id}")
    
    try:
        # 1. Instantiate the Orchestrator
        orchestrator = RevOpsOrchestrator()
        
        # 2. Run all agents (this automatically reads CRM, Gmail, and Calendar via MCP tools)
        logger.info("[1/5] Running multi-agent analysis...")
        result = await orchestrator.execute_workflow(run_id)
        
        if result.status == "failed":
            raise RuntimeError("All critical subagents failed during execution.")
            
        # 3. Generate Dashboard
        if result.executive_summary:
            logger.info("[2/5] Updating executive dashboard...")
            dashboard_payload = result.executive_summary.model_dump()
            generate_dashboard(summary_data=dashboard_payload)
            
            # 4. Generate Executive Report
            logger.info("[3/5] Saving executive markdown report...")
            report_filename = f"docs/reports/executive_report_{datetime.utcnow().strftime('%Y%m%d')}.md"
            os_path = os_path_check = os_path_create = "docs/reports"
            os.makedirs(os_path, exist_ok=True)
            with open(report_filename, "w") as f:
                f.write(result.executive_summary.executive_report)
                
            # 5. Notify Manager via Slack
            logger.info("[4/5] Sending Morning Briefing alert to Slack...")
            slack_message = (
                f"*Morning Briefing - Revenue Guardian* :shield:\n"
                f"*Business Health Score*: `{result.executive_summary.business_health_score}/100` | "
                f"*Total ARR*: `${result.executive_summary.revenue_summary.total_arr:,.2f}`\n"
                f"*Revenue at Risk*: `${result.executive_summary.revenue_summary.revenue_at_risk:,.2f}`\n\n"
                f"*Summary*:\n{result.executive_summary.morning_briefing}\n\n"
                f"Please log in to the dashboard to review today's recommendations."
            )
            notify_slack(channel="#revops-alerts", message=slack_message)
            
        logger.info(f"[5/5] Autonomous Daily Workflow completed successfully. Status: {result.status}")
        
    except Exception as e:
        logger.error(f"Daily workflow execution failed: {e}")
        # Send failure alert to Slack
        try:
            notify_slack(
                channel="#revops-alerts", 
                message=f":warning: *Alert*: Autonomous Daily Workflow failed. Error: `{str(e)}`"
            )
        except Exception as slack_err:
            logger.error(f"Failed to send Slack failure notification: {slack_err}")


# ==========================================
# 2. Asynchronous Loop Scheduler
# ==========================================

async def start_scheduling_loop():
    """
    Asynchronous loop that calculates the time remaining until the next
    morning at 8:00 AM and sleeps, waking up to execute the workflow.
    """
    logger.info("Initializing RevOps daily scheduling loop (Target: 08:00 AM daily)...")
    target_time = time(8, 0, 0)  # 8:00 AM
    
    while True:
        now = datetime.now()
        target_datetime = datetime.combine(now.date(), target_time)
        
        # If 8:00 AM has already passed today, target 8:00 AM tomorrow
        if now.time() >= target_time:
            target_datetime += timedelta(days=1)
            
        seconds_to_sleep = (target_datetime - now).total_seconds()
        
        logger.info(f"Scheduling loop sleeping for {seconds_to_sleep:.2f} seconds (until {target_datetime})...")
        
        # Sleep until 8:00 AM
        await asyncio.sleep(seconds_to_sleep)
        
        # Wake up and execute the workflow
        logger.info("Target time reached. Waking up to run daily workflow...")
        await run_daily_revops_workflow()
        
        # Sleep for a short buffer to prevent double triggers
        await asyncio.sleep(60)


# ==========================================
# 3. Helper to Create Report Directories
# ==========================================
import os
os.makedirs("docs/reports", exist_ok=True)
