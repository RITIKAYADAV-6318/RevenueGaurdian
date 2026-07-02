"""
Revenue Guardian - Security & Authentication
=============================================

This module implements JWT (JSON Web Token) authentication and Role-Based
Access Control (RBAC) for the Revenue Guardian platform.

Features:
1.  **Secure Password Hashing**: Uses Python's built-in `hashlib.pbkdf2_hmac` with
    SHA256, salting, and 100,000 iterations (highly secure, zero-dependency).
2.  **JWT Token Management**: Encodes and decodes JWT tokens with expiration times.
3.  **Role-Based Access Control (RBAC)**: Defines roles (`RevOps_Manager`, `CFO`, `Sales_Rep`)
    and provides decorators/dependency helpers to restrict endpoint access.
4.  **Mock User Database**: Pre-seeded users for local demonstration:
    - Username: `admin` | Password: `admin123` | Role: `RevOps_Manager`
    - Username: `cfo`   | Password: `cfo123`   | Role: `CFO`
    - Username: `sales` | Password: `sales123` | Role: `Sales_Rep`

Required Libraries (if running live JWT):
------------------------------------------
pip install PyJWT
"""

import os
import jwt
import hashlib
import secrets
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("SecurityAuth")

# Security Configurations
SECRET_KEY = os.environ.get("JWT_SECRET_KEY", secrets.token_hex(32))
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

# ==========================================
# 1. Password Hashing (PBKDF2)
# ==========================================

def hash_password(password: str, salt: Optional[bytes] = None) -> str:
    """
    Hashes a password using PBKDF2-HMAC-SHA256 with a secure salt.

    Args:
        password: The plain-text password.
        salt: Optional salt bytes. If None, a new salt is generated.

    Returns:
        A string containing the salt and hash in hex format: 'salt.hash'.
    """
    if not salt:
        salt = secrets.token_bytes(16)
        
    # 100,000 iterations is the OWASP recommendation for PBKDF2-SHA256
    key = hashlib.pbkdf2_hmac(
        'sha256',
        password.encode('utf-8'),
        salt,
        100000
    )
    return f"{salt.hex()}.{key.hex()}"


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verifies a plain-text password against a hashed password.

    Args:
        plain_password: The plain-text password.
        hashed_password: The stored hashed password in 'salt.hash' format.

    Returns:
        True if the password is correct, False otherwise.
    """
    try:
        salt_hex, _ = hashed_password.split('.')
        salt = bytes.fromhex(salt_hex)
        # Re-hash the plain password using the extracted salt
        rehashed = hash_password(plain_password, salt)
        return rehashed == hashed_password
    except Exception as e:
        logger.error(f"Password verification error: {e}")
        return False


# ==========================================
# 2. Mock User Database
# ==========================================

# Pre-hash the passwords for our mock database
MOCK_USERS_DB = {
    "admin": {
        "username": "admin",
        "hashed_password": hash_password("admin123"),
        "role": "RevOps_Manager",
        "email": "admin@guardian.com"
    },
    "cfo": {
        "username": "cfo",
        "hashed_password": hash_password("cfo123"),
        "role": "CFO",
        "email": "cfo@guardian.com"
    },
    "sales": {
        "username": "sales",
        "hashed_password": hash_password("sales123"),
        "role": "Sales_Rep",
        "email": "sales@guardian.com"
    }
}


# ==========================================
# 3. JWT Token Operations
# ==========================================

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Generates a JWT access token containing the user identity and role.

    Args:
        data: The payload data (e.g., {"sub": "username", "role": "CFO"}).
        expires_delta: Optional expiration time delta.

    Returns:
        The encoded JWT token string.
    """
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def verify_access_token(token: str) -> Optional[Dict[str, Any]]:
    """
    Decodes and validates a JWT access token.

    Args:
        token: The JWT token string.

    Returns:
        The decoded payload dictionary if valid, None otherwise.
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        logger.warning("JWT token has expired.")
        return None
    except jwt.PyJWTError as e:
        logger.warning(f"Invalid JWT token: {e}")
        return None


# ==========================================
# 4. Role-Based Access Control (RBAC)
# ==========================================

def authenticate_user(username: str, password: str) -> Optional[Dict[str, Any]]:
    """
    Authenticates a user against the mock database.

    Args:
        username: The user's login username.
        password: The user's plain-text password.

    Returns:
        The user record dictionary if authenticated, None otherwise.
    """
    user = MOCK_USERS_DB.get(username)
    if not user:
        return None
    if verify_password(password, user["hashed_password"]):
        return user
    return None


class RoleAccessRequired:
    """
    FastAPI dependency helper to enforce role-based access.
    
    Example Usage:
        @app.post("/api/billing/adjust")
        def adjust_billing(user = Depends(RoleAccessRequired(["CFO", "RevOps_Manager"]))):
            ...
    """
    def __init__(self, allowed_roles: List[str]):
        self.allowed_roles = allowed_roles

    def __call__(self, token: str) -> Dict[str, Any]:
        """
        Validates the token and verifies the user's role.

        Args:
            token: The bearer token passed in the request header.

        Raises:
            PermissionError: If the role is not authorized.
            ValueError: If the token is invalid.
        """
        payload = verify_access_token(token)
        if not payload:
            raise ValueError("Could not validate credentials.")
            
        user_role = payload.get("role")
        if user_role not in self.allowed_roles:
            raise PermissionError(
                f"Role '{user_role}' is not authorized. Requires one of: {self.allowed_roles}"
            )
            
        return payload
