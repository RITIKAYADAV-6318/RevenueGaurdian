"""
Revenue Guardian - Audit Logging Service
=========================================

This module implements the Audit Logging Service for the Revenue Guardian platform,
providing a tamper-evident, queryable audit trail for compliance and debugging.

Features:
1.  **Database Integration**: Writes audit logs to the SQLite database (`crm.db`).
2.  **Structured Log Payload**: Each entry captures:
    - Timestamp (UTC)
    - Actor (e.g., `admin`, `cfo`, `revops_orchestrator`, `gmail_mcp`)
    - Action (e.g., `approve_invoice`, `run_audit`, `authenticate_user`)
    - Status (`success`, `failed`, `warning`)
    - Details (JSON or text payload containing metadata)
3.  **Audit Trail Queries**: Methods to fetch logs filtered by actor, action, or date.
"""

import sqlite3
import json
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("AuditService")

DB_PATH = "crm.db"


# ==========================================
# 1. Database Setup
# ==========================================

def init_audit_log_database():
    """Creates the audit_logs table if it does not exist."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS audit_logs (
            log_id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            actor TEXT NOT NULL,
            action TEXT NOT NULL,
            status TEXT NOT NULL,
            details TEXT
        )
    """)
    conn.commit()
    conn.close()


# Initialize table on module load
init_audit_log_database()


# ==========================================
# 2. Audit Logging Operations
# ==========================================

def log_audit_event(actor: str, action: str, status: str, details: Any = None) -> int:
    """
    Persists a structured audit event to the database and logs it to the console.

    Args:
        actor: The entity performing the action (e.g., 'cfo', 'sentinel_agent').
        action: The action performed (e.g., 'approve_stripe_charge').
        status: The outcome: 'success', 'failed', or 'warning'.
        details: Optional dictionary or string containing metadata.

    Returns:
        The ID of the inserted log row.
    """
    timestamp = datetime.utcnow().isoformat()
    
    # Serialize details to JSON if it's a dict/list
    details_str = ""
    if details is not None:
        if isinstance(details, (dict, list)):
            details_str = json.dumps(details)
        else:
            details_str = str(details)

    # Log to console
    log_msg = f"Audit Log | Actor: {actor} | Action: {action} | Status: {status} | Details: {details_str}"
    if status == "failed":
        logger.error(log_msg)
    elif status == "warning":
        logger.warning(log_msg)
    else:
        logger.info(log_msg)

    # Persist to SQLite
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO audit_logs (timestamp, actor, action, status, details)
            VALUES (?, ?, ?, ?, ?)
        """, (timestamp, actor, action, status, details_str))
        conn.commit()
        log_id = cursor.lastrowid
        conn.close()
        return log_id
    except Exception as e:
        logger.error(f"Failed to persist audit log to database: {e}")
        return -1


def fetch_audit_logs(
    limit: int = 100, 
    actor: Optional[str] = None, 
    status: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Retrieves recent audit logs from the database, optionally filtered.

    Args:
        limit: Maximum number of logs to return.
        actor: Optional actor filter.
        status: Optional status filter.

    Returns:
        A list of dictionaries representing the audit logs.
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    query = "SELECT * FROM audit_logs"
    params = []
    conditions = []

    if actor:
        conditions.append("actor = ?")
        params.append(actor)
    if status:
        conditions.append("status = ?")
        params.append(status)

    if conditions:
        query += " WHERE " + " AND ".join(conditions)

    query += " ORDER BY timestamp DESC LIMIT ?"
    params.append(limit)

    cursor.execute(query, params)
    rows = cursor.fetchall()
    
    logs = []
    for row in rows:
        log_dict = dict(row)
        # Attempt to parse details back into a dictionary if it's valid JSON
        details = log_dict.get("details", "")
        if details.startswith("{") or details.startswith("["):
            try:
                log_dict["details"] = json.loads(details)
            except json.JSONDecodeError:
                pass
        logs.append(log_dict)

    conn.close()
    return logs
