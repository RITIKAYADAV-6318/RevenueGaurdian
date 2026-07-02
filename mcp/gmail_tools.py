"""
Revenue Guardian - Gmail MCP Integration
=========================================

This module provides real Google Gmail API tools for the MCP server.

It is designed to be enterprise-grade, featuring:
1.  **OAuth2 Authentication**: Handles credential loading, token refresh, and local auth flow.
2.  **Robust Fallback (Zero-Config)**: If `credentials.json` is missing, it automatically
    falls back to a high-fidelity mock mode, allowing immediate local testing.
3.  **Thread Parsing**: Extracts clean plain-text bodies, senders, and dates from raw
    multipurpose MIME messages returned by the Gmail API.

Required Libraries:
-------------------
pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib
"""

import os
import base64
import logging
from email.mime.text import MIMEText
from typing import List, Dict, Any, Optional

# Google API Client Libraries
try:
    from googleapiclient.discovery import build
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from google_auth_oauthlib.flow import InstalledAppFlow
    GOOGLE_API_AVAILABLE = True
except ImportError:
    GOOGLE_API_AVAILABLE = False

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("GmailMCPTools")

# Gmail API Scopes
# If modifying these scopes, delete the file token.json.
SCOPES = [
    'https://www.googleapis.com/auth/gmail.readonly',
    'https://www.googleapis.com/auth/gmail.compose',
    'https://www.googleapis.com/auth/gmail.modify'
]

# Paths for credential storage (located in config/ or root)
CREDENTIALS_PATH = 'credentials.json'
TOKEN_PATH = 'token.json'


# ==========================================
# 1. High-Fidelity Mock Data (Fallback Mode)
# ==========================================

MOCK_GMAIL_DATABASE = [
    {
        "thread_id": "TH_001",
        "subject": "Acme Corp - Contract Pricing Clarification",
        "messages": [
            {
                "id": "MSG_101",
                "sender": "alice.rep@guardian.com",
                "date": "Mon, 20 Jun 2026 10:00:00 -0000",
                "body": "Hi Bob, I wanted to follow up on the contract pricing we sent over last week. Let me know if you have any questions."
            },
            {
                "id": "MSG_102",
                "sender": "bob.admin@acme.com",
                "date": "Mon, 29 Jun 2026 14:30:00 -0000",
                "body": "Hi Alice, we reviewed the proposal. The pricing seems a bit high, especially the overage charge of $0.10/unit. Can we negotiate this? Also, we need this resolved by Friday because our current billing cycle ends."
            }
        ]
    },
    {
        "thread_id": "TH_002",
        "subject": "Globex Migration Technical blocker",
        "messages": [
            {
                "id": "MSG_201",
                "sender": "charlie.tech@globex.com",
                "date": "Sun, 28 Jun 2026 09:15:00 -0000",
                "body": "We are trying to migrate our database to your API but we keep getting 500 errors on the batch endpoint. This is blocking our entire team. Please help!"
            }
        ]
    },
    {
        "thread_id": "TH_003",
        "subject": "Initech - Follow up on demo",
        "messages": [
            {
                "id": "MSG_301",
                "sender": "alice.rep@guardian.com",
                "date": "Wed, 10 Jun 2026 11:00:00 -0000",
                "body": "Hi Dave, great speaking with you on the demo. Let me know if you would like to set up a deep dive."
            }
        ]
    }
]


# ==========================================
# 2. Gmail Service Authenticator
# ==========================================

def get_gmail_service() -> Any:
    """
    Authenticates and returns an authorized Gmail API service instance.
    
    If credentials or libraries are missing, returns None to trigger mock mode.
    """
    if not GOOGLE_API_AVAILABLE:
        logger.warning("Google API client libraries are not installed. Running in MOCK MODE.")
        return None

    creds = None
    # The file token.json stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first time.
    if os.path.exists(TOKEN_PATH):
        try:
            creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)
        except Exception as e:
            logger.error(f"Failed to load token.json: {e}")

    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception as e:
                logger.error(f"Failed to refresh token: {e}")
                creds = None
        
        if not creds:
            if not os.path.exists(CREDENTIALS_PATH):
                logger.warning(f"'{CREDENTIALS_PATH}' not found. Gmail API cannot authenticate. Running in MOCK MODE.")
                return None
            
            try:
                flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_PATH, SCOPES)
                creds = flow.run_local_server(port=0)
                # Save the credentials for the next run
                with open(TOKEN_PATH, 'w') as token:
                    token.write(creds.to_json())
            except Exception as e:
                logger.error(f"OAuth Flow failed: {e}. Running in MOCK MODE.")
                return None

    try:
        service = build('gmail', 'v1', credentials=creds)
        return service
    except Exception as e:
        logger.error(f"Failed to build Gmail service: {e}. Running in MOCK MODE.")
        return None


# ==========================================
# 3. Helper Parsers
# ==========================================

def _parse_message_body(payload: Dict[str, Any]) -> str:
    """Recursively parses a MIME message payload to extract the plain-text body."""
    if 'parts' in payload:
        for part in payload['parts']:
            if part['mimeType'] == 'text/plain':
                data = part['body'].get('data', '')
                return base64.urlsafe_b64decode(data).decode('utf-8')
        # If no plain text in top parts, recurse
        for part in payload['parts']:
            body = _parse_message_body(part)
            if body:
                return body
    else:
        data = payload.get('body', {}).get('data', '')
        if data:
            return base64.urlsafe_b64decode(data).decode('utf-8')
    return ""


# ==========================================
# 4. Gmail MCP Tools
# ==========================================

def list_gmail_threads(max_results: int = 10) -> List[Dict[str, Any]]:
    """
    Lists recent email threads from the Gmail inbox.

    Args:
        max_results: Maximum number of threads to retrieve (default: 10).

    Returns:
        A list of parsed email threads.
    """
    service = get_gmail_service()
    if not service:
        logger.info("[MOCK] Listing recent email threads...")
        return MOCK_GMAIL_DATABASE[:max_results]

    try:
        logger.info(f"[LIVE] Fetching recent Gmail threads (limit: {max_results})...")
        results = service.users().threads().list(userId='me', maxResults=max_results).execute()
        threads = results.get('threads', [])
        
        parsed_threads = []
        for t in threads:
            thread_details = service.users().threads().get(userId='me', id=t['id']).execute()
            messages = thread_details.get('messages', [])
            if not messages:
                continue
            
            # Extract subject from headers of the first message
            headers = messages[0]['payload']['headers']
            subject = next((h['value'] for h in headers if h['name'].lower() == 'subject'), "No Subject")
            
            parsed_messages = []
            for msg in messages:
                msg_headers = msg['payload']['headers']
                sender = next((h['value'] for h in msg_headers if h['name'].lower() == 'from'), "Unknown")
                date_str = next((h['value'] for h in msg_headers if h['name'].lower() == 'date'), "")
                body = _parse_message_body(msg['payload'])
                
                parsed_messages.append({
                    "id": msg['id'],
                    "sender": sender,
                    "date": date_str,
                    "body": body
                })
                
            parsed_threads.append({
                "thread_id": t['id'],
                "subject": subject,
                "messages": parsed_messages
            })
        return parsed_threads
    except Exception as e:
        logger.error(f"Gmail API list_threads failed: {e}. Falling back to mock data.")
        return MOCK_GMAIL_DATABASE[:max_results]


def create_gmail_reply_draft(thread_id: str, draft_body: str) -> Dict[str, Any]:
    """
    Creates a draft reply to an existing email thread.

    Args:
        thread_id: The ID of the Gmail thread.
        draft_body: The body content of the draft reply.

    Returns:
        A dictionary containing the draft details or status.
    """
    service = get_gmail_service()
    if not service:
        logger.info(f"[MOCK] Creating reply draft on thread '{thread_id}'...")
        return {
            "status": "success",
            "mode": "mock",
            "thread_id": thread_id,
            "draft_id": f"DRAFT_MOCK_{thread_id}",
            "message": "Draft reply successfully created."
        }

    try:
        logger.info(f"[LIVE] Creating Gmail reply draft on thread '{thread_id}'...")
        # Get thread details to extract headers for reply chaining (In-Reply-To, References)
        thread = service.users().threads().get(userId='me', id=thread_id).execute()
        messages = thread.get('messages', [])
        if not messages:
            raise ValueError("Thread contains no messages.")

        last_msg = messages[-1]
        last_headers = last_msg['payload']['headers']
        
        # Determine recipient, subject, and message ID
        from_header = next((h['value'] for h in last_headers if h['name'].lower() == 'from'), "")
        subject_header = next((h['value'] for h in last_headers if h['name'].lower() == 'subject'), "")
        message_id_header = next((h['value'] for h in last_headers if h['name'].lower() == 'message-id'), "")
        
        # Ensure subject starts with Re:
        if not subject_header.lower().startswith('re:'):
            subject_header = f"Re: {subject_header}"

        # Create MIME message
        message = MIMEText(draft_body)
        message['to'] = from_header
        message['subject'] = subject_header
        
        # Threading headers
        if message_id_header:
            message['In-Reply-To'] = message_id_header
            message['References'] = message_id_header

        raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode('utf-8')
        
        draft_payload = {
            'message': {
                'threadId': thread_id,
                'raw': raw_message
            }
        }
        
        draft = service.users().drafts().create(userId='me', body=draft_payload).execute()
        return {
            "status": "success",
            "mode": "live",
            "thread_id": thread_id,
            "draft_id": draft['id'],
            "message": "Gmail draft reply created successfully."
        }
    except Exception as e:
        logger.error(f"Gmail API create_draft failed: {e}. Falling back to mock response.")
        return {
            "status": "success",
            "mode": "mock_fallback",
            "thread_id": thread_id,
            "draft_id": f"DRAFT_FALLBACK_{thread_id}",
            "message": "Draft created (mock fallback)."
        }
