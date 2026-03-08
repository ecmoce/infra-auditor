"""Aggregator server configuration."""

import os
from dataclasses import dataclass, field
from typing import List


@dataclass
class Settings:
    """Server configuration loaded from environment variables."""

    # Server
    host: str = "0.0.0.0"
    port: int = 8443
    debug: bool = False

    # Database
    db_path: str = "infra_auditor.db"

    # Security
    api_keys: List[str] = field(default_factory=list)
    cors_origins: List[str] = field(default_factory=lambda: ["*"])

    # Rate limiting
    rate_limit_per_minute: int = 60

    # Data retention
    retention_days: int = 30

    @classmethod
    def from_env(cls) -> "Settings":
        """Load settings from environment variables."""
        api_keys_str = os.getenv("INFRA_AUDITOR_API_KEYS", "")
        api_keys = [k.strip() for k in api_keys_str.split(",") if k.strip()]

        cors_str = os.getenv("INFRA_AUDITOR_CORS_ORIGINS", "*")
        cors_origins = [o.strip() for o in cors_str.split(",") if o.strip()]

        return cls(
            host=os.getenv("INFRA_AUDITOR_HOST", "0.0.0.0"),
            port=int(os.getenv("INFRA_AUDITOR_PORT", "8443")),
            debug=os.getenv("INFRA_AUDITOR_DEBUG", "").lower() in (
                "1", "true", "yes"
            ),
            db_path=os.getenv(
                "INFRA_AUDITOR_DB_PATH", "infra_auditor.db"
            ),
            api_keys=api_keys,
            cors_origins=cors_origins,
            rate_limit_per_minute=int(
                os.getenv("INFRA_AUDITOR_RATE_LIMIT", "60")
            ),
            retention_days=int(
                os.getenv("INFRA_AUDITOR_RETENTION_DAYS", "30")
            ),
        )


def get_settings() -> Settings:
    """Get application settings (singleton-like via module cache)."""
    return Settings.from_env()
