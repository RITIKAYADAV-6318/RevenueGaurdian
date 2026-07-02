"""
Revenue Guardian - CRM MCP Integration
======================================

This module provides database-driven CRM tools for the MCP server.

It is designed to be enterprise-grade, featuring:
1.  **SQLite Warehouse**: Manages a local SQLite database (`crm.db`) to simulate an enterprise
    CRM data warehouse (e.g., Salesforce/HubSpot synced to Snowflake or PostgreSQL).
2.  **Automatic Seeding**: Automatically creates tables and seeds them with mock data
    on first initialization.
3.  **Real SQL Queries**: Executes real SQL statements to read and write CRM data,
    providing a robust integration layer.

Exposed Tools:
--------------
*   `fetch_leads()`: Retrieves all active leads.
*   `fetch_opportunities()`: Retrieves all active opportunities.
*   `fetch_tasks()`: Retrieves all open sales tasks.
*   `update_opportunity_stage(opportunity_id, stage, value)`: Updates an opportunity's stage and value.
"""

import os
import sqlite3
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("CRMMCPTools")

DB_PATH = "crm.db"


# ==========================================
# 1. Database Initialization & Seeding
# ==========================================

def init_crm_database():
    """Initializes the SQLite database, creating tables and seeding mock data if empty."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Create Tables
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS leads (
            lead_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            company TEXT NOT NULL,
            last_activity_date TEXT NOT NULL,
            status TEXT NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS opportunities (
            opportunity_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            current_stage TEXT NOT NULL,
            stage_last_updated TEXT NOT NULL,
            deal_value REAL NOT NULL,
            owner_email TEXT NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            task_id TEXT PRIMARY KEY,
            opportunity_id TEXT NOT NULL,
            owner_email TEXT NOT NULL,
            task_description TEXT NOT NULL,
            due_date TEXT NOT NULL,
            status TEXT NOT NULL,
            FOREIGN KEY (opportunity_id) REFERENCES opportunities(opportunity_id)
        )
    """)
    
    conn.commit()

    # Check if data exists; if not, seed it
    cursor.execute("SELECT COUNT(*) FROM leads")
    if cursor.fetchone()[0] == 0:
        logger.info("Seeding CRM database with initial mock records...")
        
        # Seed Leads
        leads = [
            ("LD_101", "Sarah Jenkins", "Nexus Media", "2026-05-15", "Contacted"),
            ("LD_102", "Michael Chen", "Apex Logistics", "2026-06-28", "Working"),
            ("LD_103", "Elena Rostova", "Siberia Tech", "2026-04-10", "Qualified")
        ]
        cursor.executemany("INSERT INTO leads VALUES (?, ?, ?, ?, ?)", leads)

        # Seed Opportunities
        opportunities = [
            ("OPP_201", "Acme Corp - Enterprise Expansion", "Proposal/Price Quote", "2026-05-10", 75000.0, "alice.rep@guardian.com"),
            ("OPP_202", "Globex - API Platform Migration", "Negotiation/Review", "2026-06-25", 120000.0, "bob.rep@guardian.com"),
            ("OPP_203", "Initech - Security Module Add-on", "Discovery", "2026-06-01", 15000.0, "alice.rep@guardian.com")
        ]
        cursor.executemany("INSERT INTO opportunities VALUES (?, ?, ?, ?, ?, ?)", opportunities)

        # Seed Tasks
        tasks = [
            ("TSK_301", "OPP_201", "alice.rep@guardian.com", "Send revised SLA agreement", "2026-06-15", "Open"),
            ("TSK_302", "OPP_202", "bob.rep@guardian.com", "Follow up on security review sign-off", "2026-06-29", "Open"),
            ("TSK_303", "OPP_203", "alice.rep@guardian.com", "Schedule demo call", "2026-07-05", "Open")
        ]
        cursor.executemany("INSERT INTO tasks VALUES (?, ?, ?, ?, ?, ?)", tasks)
        
        conn.commit()

    conn.close()


# Initialize database on module load
init_crm_database()


# ==========================================
# 2. CRM MCP Tools
# ==========================================

def fetch_leads() -> List[Dict[str, Any]]:
    """
    Fetches all active leads from the CRM database.

    Returns:
        A list of dictionaries representing leads.
    """
    logger.info("SQL Query: SELECT * FROM leads")
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM leads")
    rows = cursor.fetchall()
    
    leads = [dict(row) for row in rows]
    conn.close()
    return leads


def fetch_opportunities() -> List[Dict[str, Any]]:
    """
    Fetches all active opportunities from the CRM database.

    Returns:
        A list of dictionaries representing opportunities.
    """
    logger.info("SQL Query: SELECT * FROM opportunities")
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM opportunities")
    rows = cursor.fetchall()
    
    opportunities = [dict(row) for row in rows]
    conn.close()
    return opportunities


def fetch_tasks() -> List[Dict[str, Any]]:
    """
    Fetches all open sales tasks from the CRM database.

    Returns:
        A list of dictionaries representing tasks.
    """
    logger.info("SQL Query: SELECT * FROM tasks")
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM tasks")
    rows = cursor.fetchall()
    
    tasks = [dict(row) for row in rows]
    conn.close()
    return tasks


def update_opportunity_stage(opportunity_id: str, stage: str, deal_value: Optional[float] = None) -> Dict[str, Any]:
    """
    Updates the pipeline stage and optionally the deal value of an active opportunity.

    Args:
        opportunity_id: The ID of the opportunity (e.g., 'OPP_201').
        stage: The new sales stage (e.g., 'Closed Won', 'Negotiation').
        deal_value: Optional new deal value in USD.

    Returns:
        A dictionary confirming the update status.
    """
    logger.info(f"SQL Update: Modify opportunity '{opportunity_id}' to stage '{stage}'")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    today_str = datetime.utcnow().date().isoformat()
    
    if deal_value is not None:
        cursor.execute("""
            UPDATE opportunities 
            SET current_stage = ?, stage_last_updated = ?, deal_value = ? 
            WHERE opportunity_id = ?
        """, (stage, today_str, deal_value, opportunity_id))
    else:
        cursor.execute("""
            UPDATE opportunities 
            SET current_stage = ?, stage_last_updated = ? 
            WHERE opportunity_id = ?
        """, (stage, today_str, opportunity_id))
        
    conn.commit()
    
    # Verify update
    cursor.execute("SELECT * FROM opportunities WHERE opportunity_id = ?", (opportunity_id,))
    row = cursor.fetchone()
    conn.close()
    
    if row:
        return {
            "status": "success",
            "opportunity_id": opportunity_id,
            "updated_fields": {
                "current_stage": stage,
                "stage_last_updated": today_str,
                "deal_value": deal_value if deal_value is not None else "unchanged"
            }
        }
    else:
        return {
            "status": "error",
            "message": f"Opportunity '{opportunity_id}' not found."
        }
