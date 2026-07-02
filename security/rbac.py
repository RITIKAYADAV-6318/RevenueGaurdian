"""
Revenue Guardian - Role-Based Access Control (RBAC)
====================================================

This module implements the authorization layer (RBAC) for the Revenue Guardian platform,
separating authorization logic from authentication.

Features:
1.  **Role Enum**: Defines explicit user roles (`CFO`, `REVOPS_MANAGER`, `SALES_REP`, `CS_REP`).
2.  **Permission Enum**: Defines granular system permissions (e.g., `RUN_AUDIT`, `APPROVE_BILLING`).
3.  **Permission-to-Role Mapping**: A centralized dictionary mapping permissions to authorized roles.
4.  **Role Enforcement Decorator**: A generic Python decorator (`enforce_permission`) to secure
    any function based on the current user's role.
"""

import logging
from enum import Enum
from functools import wraps
from typing import List, Dict, Any, Callable

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("SecurityRBAC")


# ==========================================
# 1. Roles & Permissions Definitions
# ==========================================

class UserRole(str, Enum):
    """Supported roles within the enterprise RevOps platform."""
    CFO = "CFO"
    REVOPS_MANAGER = "RevOps_Manager"
    SALES_REP = "Sales_Rep"
    CS_REP = "CS_Rep"


class Permission(str, Enum):
    """Granular permissions protecting system actions."""
    VIEW_DASHBOARD = "view_dashboard"
    RUN_AUDIT = "run_audit"
    APPROVE_BILLING = "approve_billing"
    APPROVE_EMAIL = "approve_email"
    UPDATE_CRM = "update_crm"
    BYPASS_APPROVALS = "bypass_approvals"


# Centralized Access Control List (ACL) mapping permissions to authorized roles
PERMISSION_MAP: Dict[Permission, List[UserRole]] = {
    Permission.VIEW_DASHBOARD: [
        UserRole.CFO, 
        UserRole.REVOPS_MANAGER, 
        UserRole.SALES_REP, 
        UserRole.CS_REP
    ],
    Permission.RUN_AUDIT: [
        UserRole.REVOPS_MANAGER
    ],
    Permission.APPROVE_BILLING: [
        UserRole.CFO, 
        UserRole.REVOPS_MANAGER
    ],
    Permission.APPROVE_EMAIL: [
        UserRole.REVOPS_MANAGER, 
        UserRole.SALES_REP, 
        UserRole.CS_REP
    ],
    Permission.UPDATE_CRM: [
        UserRole.REVOPS_MANAGER, 
        UserRole.SALES_REP
    ],
    Permission.BYPASS_APPROVALS: [
        # Reserved for break-glass scenarios, no default roles
    ]
}


# ==========================================
# 2. Authorization Helpers
# ==========================================

def has_permission(user_role: str, permission: Permission) -> bool:
    """
    Checks if a given role is authorized for a specific permission.

    Args:
        user_role: The role string associated with the user.
        permission: The Permission enum being checked.

    Returns:
        True if authorized, False otherwise.
    """
    try:
        role_enum = UserRole(user_role)
    except ValueError:
        logger.warning(f"Attempted check with invalid role: {user_role}")
        return False
        
    authorized_roles = PERMISSION_MAP.get(permission, [])
    return role_enum in authorized_roles


# ==========================================
# 3. Role Enforcement Decorator
# ==========================================

def enforce_permission(permission: Permission):
    """
    A decorator to enforce permission checks on functions.
    
    The decorated function must accept a keyword argument 'current_user' 
    which is a dictionary containing a 'role' key.

    Example Usage:
        @enforce_permission(Permission.APPROVE_BILLING)
        def process_stripe_refund(invoice_id: str, current_user: dict):
            ...
    """
    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            current_user = kwargs.get("current_user")
            if not current_user or "role" not in current_user:
                raise PermissionError(
                    f"Access Denied to '{func.__name__}': No 'current_user' with a valid role provided."
                )
                
            user_role = current_user["role"]
            if not has_permission(user_role, permission):
                logger.warning(
                    f"Access Denied: User '{current_user.get('username')}' with role '{user_role}' "
                    f"attempted to execute '{func.__name__}' which requires '{permission.value}' permission."
                )
                raise PermissionError(
                    f"Access Denied: Role '{user_role}' does not have '{permission.value}' permission."
                )
                
            return func(*args, **kwargs)
        return wrapper
    return decorator
