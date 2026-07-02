"""
Revenue Guardian - Secure Configuration
========================================

This module implements the secure configuration layer for the Revenue Guardian platform.

It features:
1.  **Automated `.env` Loading**: A lightweight, zero-dependency parser that reads
    environment variables from a local `.env` file on startup.
2.  **Type-Safe Validation**: Uses Pydantic to parse, cast, and validate configuration
    variables (e.g., converting token expiration minutes to an integer).
3.  **Fail-Fast Security Checks**: Validates that critical keys (like the Gemini API Key)
    are present and warns against using default keys in production.
"""

import os
import logging
from typing import Optional
from pydantic import BaseModel, Field

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ConfigSettings")


# ==========================================
# 1. Zero-Dependency .env Loader
# ==========================================

def load_dotenv(dotenv_path: str = ".env") -> None:
    """
    Reads a .env file and loads the key-value pairs into os.environ.
    Does not overwrite existing environment variables.
    """
    if not os.path.exists(dotenv_path):
        logger.warning(f"No '{dotenv_path}' file found. Using system environment variables.")
        return

    logger.info(f"Loading environment variables from {dotenv_path}...")
    with open(dotenv_path, "r") as f:
        for line in f:
            line = line.strip()
            # Ignore empty lines and comments
            if not line or line.startswith("#"):
                continue
            
            # Parse KEY=VALUE
            if "=" in line:
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                
                # Set in environment if not already set
                if key not in os.environ:
                    os.environ[key] = value


# Trigger .env loading on module import
load_dotenv()


# ==========================================
# 2. Settings Schema & Validation
# ==========================================

class Settings(BaseModel):
    """Structured configuration settings for the Revenue Guardian platform."""
    
    # API Credentials
    gemini_api_key: str = Field(
        default="", 
        description="Google Gemini/Vertex AI API Key.",
        json_schema_extra={"env": "GEMINI_API_KEY"}
    )
    slack_webhook_url: Optional[str] = Field(
        default=None, 
        description="Slack Incoming Webhook URL for alerts.",
        json_schema_extra={"env": "SLACK_WEBHOOK_URL"}
    )
    
    # Database Settings
    database_url: str = Field(
        default="sqlite:///crm.db", 
        description="Database connection string.",
        json_schema_extra={"env": "DATABASE_URL"}
    )
    
    # JWT Authentication Security
    jwt_secret_key: str = Field(
        default="INSECURE_DEFAULT_REVOPS_SECRET_KEY_CHANGE_THIS_IN_PRODUCTION", 
        description="Secret key used to sign JWT tokens.",
        json_schema_extra={"env": "JWT_SECRET_KEY"}
    )
    jwt_algorithm: str = Field(
        default="HS256", 
        description="Signature algorithm for JWTs.",
        json_schema_extra={"env": "JWT_ALGORITHM"}
    )
    access_token_expire_minutes: int = Field(
        default=60, 
        description="JWT token expiration duration in minutes.",
        json_schema_extra={"env": "ACCESS_TOKEN_EXPIRE_MINUTES"}
    )
    
    # Model Configurations
    model_name: str = Field(
        default="gemini-2.0-flash", 
        description="Default Gemini model for ADK agents.",
        json_schema_extra={"env": "GEMINI_MODEL_NAME"}
    )
    temperature: float = Field(
        default=0.2, 
        description="Sampling temperature for agent reasoning.",
        json_schema_extra={"env": "GEMINI_TEMPERATURE"}
    )

    def validate_security(self) -> None:
        """Runs post-initialization security checks."""
        # 1. Warn if Gemini key is missing
        if not self.gemini_api_key:
            logger.warning(
                "❌ GEMINI_API_KEY is not set. ADK Agents will fail to execute. "
                "Please add your API key to the .env file."
            )
            
        # 2. Prevent using default JWT key in production
        if self.jwt_secret_key == "INSECURE_DEFAULT_REVOPS_SECRET_KEY_CHANGE_THIS_IN_PRODUCTION":
            logger.warning(
                "⚠️ Using the default JWT_SECRET_KEY. This is highly insecure for production. "
                "Generate a secure key using: openssl rand -hex 32"
            )


# ==========================================
# 3. Singleton Instance
# ==========================================

# Helper function to instantiate settings with environment overrides
def get_settings() -> Settings:
    """Instantiates and returns the validated Settings singleton."""
    settings = Settings(
        gemini_api_key=os.environ.get("GEMINI_API_KEY", ""),
        slack_webhook_url=os.environ.get("SLACK_WEBHOOK_URL"),
        database_url=os.environ.get("DATABASE_URL", "sqlite:///crm.db"),
        jwt_secret_key=os.environ.get("JWT_SECRET_KEY", "INSECURE_DEFAULT_REVOPS_SECRET_KEY_CHANGE_THIS_IN_PRODUCTION"),
        jwt_algorithm=os.environ.get("JWT_ALGORITHM", "HS256"),
        access_token_expire_minutes=int(os.environ.get("ACCESS_TOKEN_EXPIRE_MINUTES", "60")),
        model_name=os.environ.get("GEMINI_MODEL_NAME", "gemini-2.0-flash"),
        temperature=float(os.environ.get("GEMINI_TEMPERATURE", "0.2"))
    )
    settings.validate_security()
    return settings


# Create a single global settings instance
settings = get_settings()
