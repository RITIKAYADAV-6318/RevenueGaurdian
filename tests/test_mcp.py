"""
Revenue Guardian - MCP Tools Unit Tests
========================================

This module contains unit tests for the MCP tools registered on the server:
`read_crm`, `read_emails`, `read_calendar`, `send_email`, `schedule_meeting`,
`notify_slack`, and `save_logs`.
"""

import pytest

# Import MCP tools directly
from mcp.server import read_crm, read_emails, read_calendar, send_email, schedule_meeting, notify_slack, save_logs
from mcp.crm_tools import update_opportunity_stage
from services.audit_service import fetch_audit_logs


def test_read_crm_tool():
    """Verifies that the read_crm tool returns the seeded SQLite records."""
    data = read_crm()
    assert "leads" in data
    assert "opportunities" in data
    assert "tasks" in data
    
    # Assert specific records are fetched
    assert len(data["leads"]) == 3
    assert data["leads"][0]["name"] == "Sarah Jenkins"
    assert data["opportunities"][0]["name"] == "Acme Corp - Enterprise Expansion"


def test_update_crm_opportunity_tool():
    """Verifies that updating an opportunity modifies the database state."""
    # Run update
    result = update_opportunity_stage(opportunity_id="OPP_201", stage="Closed Won", deal_value=80000.0)
    assert result["status"] == "success"
    assert result["updated_fields"]["current_stage"] == "Closed Won"
    assert result["updated_fields"]["deal_value"] == 80000.0

    # Fetch and verify
    data = read_crm()
    acme_opp = next(o for o in data["opportunities"] if o["opportunity_id"] == "OPP_201")
    assert acme_opp["current_stage"] == "Closed Won"
    assert acme_opp["deal_value"] == 80000.0


def test_read_emails_tool():
    """Verifies that the read_emails tool returns threads."""
    threads = read_emails(max_results=5)
    assert isinstance(threads, list)
    assert len(threads) > 0
    assert threads[0]["subject"] == "Acme Corp - Contract Pricing Clarification"
    assert len(threads[0]["messages"]) == 2


def test_read_calendar_tool():
    """Verifies that the read_calendar tool returns events and availability."""
    data = read_calendar(max_results=5)
    assert "events" in data
    assert "free_busy" in data
    assert len(data["events"]) > 0
    assert data["events"][0]["title"] == "Acme Corp - Contract Renewal Discussion"


def test_send_email_tool():
    """Verifies that send_email returns delivery confirmation."""
    result = send_email(to_email="customer@client.com", subject="Test", body="Hello")
    assert result["status"] == "success"
    assert "successfully sent" in result["message"]


def test_schedule_meeting_tool():
    """Verifies that schedule_meeting inserts a new calendar event."""
    result = schedule_meeting(
        title="Emergency Sync",
        attendees=["cfo@guardian.com"],
        start_time="2026-07-01T10:00:00",
        end_time="2026-07-01T10:30:00",
        description="Discussing blockers."
    )
    assert result["status"] == "success"
    assert result["title"] == "Emergency Sync"
    assert "scheduled" in result["message"]


def test_notify_slack_tool():
    """Verifies that notify_slack returns dispatch confirmation."""
    result = notify_slack(channel="#alerts", message="Test Alert")
    assert result["status"] == "success"
    assert "dispatched" in result["message"] or "logged" in result["message"]


def test_save_logs_tool():
    """Verifies that save_logs persists the log to the audit database."""
    agent = "sentinel_agent"
    msg = "Usage spike detected for Globex."

    result = save_logs(agent_name=agent, log_message=msg)
    assert result["status"] == "success"
    assert result["log_id"] > 0

    # Query audit database to verify persistence
    db_logs = fetch_audit_logs(limit=5, actor=agent)
    assert len(db_logs) > 0
    assert db_logs[0]["details"] == msg
