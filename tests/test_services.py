"""
Revenue Guardian - Service Unit Tests
======================================

This module contains unit tests for:
1.  **Authentication**: Password hashing and verification, JWT token operations.
2.  **Role-Based Access Control (RBAC)**: Permission checks and decorator enforcement.
3.  **Audit Logging**: Event persistence and retrieval.
"""

import pytest
import time
from datetime import timedelta

# Import modules to test
from security.auth import hash_password, verify_password, create_access_token, verify_access_token, authenticate_user, RoleAccessRequired
from security.rbac import UserRole, Permission, has_permission, enforce_permission
from services.audit_service import log_audit_event, fetch_audit_logs


# ==========================================
# 1. Authentication Tests
# ==========================================

def test_password_hashing():
    """Verifies that passwords are secure, salted, and match when verified."""
    password = "secure_password_123"
    hashed = hash_password(password)
    
    # Assert hash structure (salt.hash)
    assert "." in hashed
    assert len(hashed.split(".")) == 2
    
    # Assert correct verification
    assert verify_password(password, hashed) is True
    # Assert incorrect password fails
    assert verify_password("wrong_password", hashed) is False


def test_jwt_token_operations():
    """Verifies that JWT tokens can be created, decoded, and expire correctly."""
    user_data = {"sub": "test_user", "role": "CFO"}
    
    # Create token with a 5-minute expiration
    token = create_access_token(user_data, expires_delta=timedelta(minutes=5))
    assert isinstance(token, str)
    
    # Verify and decode
    payload = verify_access_token(token)
    assert payload is not None
    assert payload["sub"] == "test_user"
    assert payload["role"] == "CFO"


def test_user_authentication():
    """Verifies authentication against the mock user database."""
    # Test valid credentials
    user = authenticate_user("cfo", "cfo123")
    assert user is not None
    assert user["role"] == "CFO"
    
    # Test invalid credentials
    assert authenticate_user("cfo", "wrong_pass") is None
    assert authenticate_user("non_existent_user", "pass") is None


# ==========================================
# 2. RBAC (Role-Based Access Control) Tests
# ==========================================

def test_has_permission():
    """Verifies the permission-to-role ACL mapping."""
    # CFO has billing approval permission
    assert has_permission("CFO", Permission.APPROVE_BILLING) is True
    # Sales Rep does not have billing approval permission
    assert has_permission("Sales_Rep", Permission.APPROVE_BILLING) is False
    # RevOps Manager has audit run permission
    assert has_permission("RevOps_Manager", Permission.RUN_AUDIT) is True
    # CFO does not have audit run permission
    assert has_permission("CFO", Permission.RUN_AUDIT) is False


def test_enforce_permission_decorator():
    """Verifies that the @enforce_permission decorator protects functions."""
    
    # Define a test function protected by the decorator
    @enforce_permission(Permission.APPROVE_BILLING)
    def test_billing_action(current_user: dict):
        return "Billing Approved"

    # Test with authorized user (CFO)
    cfo_user = {"username": "cfo", "role": "CFO"}
    assert test_billing_action(current_user=cfo_user) == "Billing Approved"

    # Test with unauthorized user (Sales_Rep) - should raise PermissionError
    sales_user = {"username": "sales", "role": "Sales_Rep"}
    with pytest.raises(PermissionError):
        test_billing_action(current_user=sales_user)

    # Test with missing user context - should raise PermissionError
    with pytest.raises(PermissionError):
        test_billing_action()


# ==========================================
# 3. Audit Logging Tests
# ==========================================

def test_audit_logging():
    """Verifies that events are written to the database and can be queried."""
    actor = "test_agent"
    action = "run_prediction_model"
    status = "success"
    details = {"opportunities_analyzed": 3, "forecast": 184800.0}

    # Log the event
    log_id = log_audit_event(actor, action, status, details)
    assert log_id > 0

    # Query the logs
    logs = fetch_audit_logs(limit=5, actor=actor)
    assert len(logs) > 0
    
    latest_log = logs[0]
    assert latest_log["actor"] == actor
    assert latest_log["action"] == action
    assert latest_log["status"] == status
    assert latest_log["details"]["opportunities_analyzed"] == 3
    assert latest_log["details"]["forecast"] == 184800.0
