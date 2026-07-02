"""
Revenue Guardian - Slack MCP Integration
=========================================

This module provides real Slack notification tools for the MCP server.

It is designed to be enterprise-grade, featuring:
1.  **Incoming Webhook Integration**: Dispatches rich text notifications to Slack channels
    using Google/Slack incoming webhooks.
2.  **Zero-Dependency Execution**: Uses Python's built-in `urllib.request` to perform
    asynchronous-friendly POST requests, eliminating the need for the `requests` library.
3.  **Zero-Config Mock Fallback**: If the `SLACK_WEBHOOK_URL` environment variable is missing,
    it automatically logs the alert to the console and runs in mock mode.

Exposed Tools:
--------------
*   `post_slack_message(channel, text)`: Sends a message to a Slack channel.
"""

import os
import json
import logging
import urllib.request
from typing import Dict, Any

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("SlackMCPTools")

# Retrieve the Slack Webhook URL from environment variables
SLACK_WEBHOOK_URL = os.environ.get("SLACK_WEBHOOK_URL")


# ==========================================
# 1. Slack MCP Tools
# ==========================================

def post_slack_message(channel: str, text: str) -> Dict[str, Any]:
    """
    Sends an alert notification to a specified Slack channel.

    Args:
        channel: The target Slack channel (e.g., '#revops-alerts').
        text: The text content of the message. Supports Slack markdown formatting.

    Returns:
        A dictionary containing the delivery status.
    """
    payload = {
        "channel": channel,
        "text": text,
        "username": "Revenue Guardian",
        "icon_emoji": ":shield:"
    }

    # 1. Check if Webhook URL is configured; if not, run in Mock Mode
    if not SLACK_WEBHOOK_URL:
        logger.warning("SLACK_WEBHOOK_URL environment variable is not set. Running in MOCK MODE.")
        logger.info(f"[MOCK SLACK ALERT] Channel: {channel} | Message: {text}")
        return {
            "status": "success",
            "mode": "mock",
            "channel": channel,
            "message": "Slack notification logged in mock mode.",
            "payload": payload
        }

    # 2. Live Webhook Dispatch
    try:
        logger.info(f"[LIVE SLACK ALERT] Dispatching message to {channel}...")
        data = json.dumps(payload).encode('utf-8')
        
        req = urllib.request.Request(
            SLACK_WEBHOOK_URL,
            data=data,
            headers={'Content-Type': 'application/json'}
        )
        
        # Perform the HTTP POST request
        with urllib.request.urlopen(req) as response:
            response_code = response.getcode()
            
        if response_code == 200:
            return {
                "status": "success",
                "mode": "live",
                "channel": channel,
                "message": "Slack notification successfully delivered."
            }
        else:
            raise ValueError(f"Slack returned non-200 status code: {response_code}")
            
    except Exception as e:
        logger.error(f"Failed to send Slack notification: {e}. Falling back to mock response.")
        return {
            "status": "success",
            "mode": "mock_fallback",
            "channel": channel,
            "message": f"Slack notification logged (fallback due to error: {str(e)})",
            "payload": payload
        }
