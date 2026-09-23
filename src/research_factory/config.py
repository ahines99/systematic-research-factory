"""Typed configuration. Values come from environment variables (prefix ``RSF_``) or ``.env``.

Secrets are never given defaults and are never logged.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class StatisticalThresholds(BaseModel):
    """Decision thresholds for the statistical review. Configuration, not code."""

    min_observations: int = 252
    min_newey_west_t: float = 3.0
    min_deflated_sharpe: float = 0.95
    bootstrap_confidence: float = 0.95
    bootstrap_samples: int = 2000
    require_ci_lower_above_zero: bool = True
    max_delay_sharpe_decay: float = 0.5  # Sharpe may lose at most this fraction with one extra day of delay


class RetryPolicy(BaseModel):
    max_attempts: int = 3
    base_delay_seconds: float = 0.05
    max_delay_seconds: float = 2.0
    timeout_seconds: float = 120.0


class Budgets(BaseModel):
    max_tokens_per_run: int = 60_000
    max_cost_usd_per_run: float = 1.00
    max_cost_usd_per_day: float = 10.00
    max_guest_live_runs_per_day: int = 3
    step_latency_target_seconds: float = 60.0


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="RSF_", env_file=".env", env_nested_delimiter="__", extra="ignore"
    )

    environment: str = "development"
    database_url: str = "sqlite:///var/rsf.db"
    blob_store: str = Field(
        default="file://var/blobs", description="file://<dir>, memory://, or s3://<bucket>"
    )
    s3_endpoint_url: str | None = None
    s3_access_key_id: SecretStr | None = None
    s3_secret_access_key: SecretStr | None = None

    model_provider: str = Field(default="rules", description="'rules' (deterministic, no API) or 'anthropic'")
    anthropic_model: str = "claude-sonnet-5"
    anthropic_api_key: SecretStr | None = Field(default=None, validation_alias="ANTHROPIC_API_KEY")

    sec_user_agent: str | None = Field(
        default=None,
        description="Required for live EDGAR calls: '<organization> <contact email>' per SEC fair-access policy",
    )
    sec_max_requests_per_second: float = 5.0
    edgar_cache_dir: Path = Path("var/edgar-cache")

    log_level: str = "INFO"
    log_json: bool = True

    thresholds: StatisticalThresholds = StatisticalThresholds()
    retry: RetryPolicy = RetryPolicy()
    budgets: Budgets = Budgets()

    allowed_source_hosts: tuple[str, ...] = ("data.sec.gov", "www.sec.gov")


def get_settings() -> Settings:
    return Settings()
