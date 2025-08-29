"""App configuration.

"""

# pyright: reportMissingImports=false
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    user_agent: str = "MandelaReport/0.1 (+mailto:you@example.com)"
    request_timeout: int = 15
    max_response_mb: int = 5
    obey_robots: bool = True
    allow_wayback: bool = True
    same_domain_only: bool = False
    summary_provider: str = "auto"  # auto|llm|rule
    llm_base_url: str = "http://llm:8085/v1"

    # Retention & housekeeping
    retention_enabled: bool = True
    retention_days: int = 180  # ~6 months
    retention_interval_hours: int = 24  # how often to run purge
    vacuum_after_purge: bool = True

    model_config = SettingsConfigDict(
        env_prefix="APP__",
        env_file=".env",
        case_sensitive=False,
    )


def get_settings() -> Settings:
    return Settings()
