"""Application configuration, loaded from environment / .env (see repo-root .env.example)."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_INSECURE_SECRET = "dev-only-insecure-change-me-32bytes-minimum"  # noqa: S105

BACKEND_DIR = Path(__file__).resolve().parents[2]
REPO_ROOT = BACKEND_DIR.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(REPO_ROOT / ".env", BACKEND_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # ---- App ----
    app_env: Literal["dev", "test", "prod"] = "dev"
    app_name: str = "Egreen Quanta"
    api_v1_prefix: str = "/api/v1"
    log_level: str = "INFO"
    log_json: bool = False

    # ---- Database ----
    database_url: str = "sqlite+aiosqlite:///./var/dev.db"

    # ---- Security / auth ----
    # Dev-only fallback; MUST be overridden via env in any non-dev deployment
    # (fail-closed check in _enforce_prod_secrets below).
    secret_key: str = _INSECURE_SECRET
    jwt_algorithm: Literal["HS256", "RS256"] = "HS256"
    jwt_private_key_path: str | None = None
    jwt_public_key_path: str | None = None
    access_token_ttl: int = 900
    refresh_token_ttl: int = 1_209_600
    password_argon2_time_cost: int = 3
    password_argon2_memory_cost: int = 65_536
    password_argon2_parallelism: int = 2
    totp_issuer: str = "EgreenQuanta"
    login_max_attempts: int = 5
    login_lockout_seconds: int = 300

    # ---- CORS ----
    cors_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:5173", "http://localhost:8080"]
    )
    # Host/:authority allow-list for TrustedHostMiddleware (prod only). "*" disables the check.
    allowed_hosts: list[str] = Field(default_factory=lambda: ["*"])

    # ---- Audit ----
    audit_signing_key: str | None = None
    audit_anchor_cron: str = "0 2 * * *"

    # ---- Artifact storage ----
    store_artifacts: bool = False
    artifact_enc_key: str | None = None
    max_upload_mb: int = 25

    # ---- Revocation / outbound ----
    outbound_revocation: bool = False
    revocation_timeout_seconds: int = 5
    revocation_max_response_kb: int = 1024
    trusted_tsa_urls: list[str] = Field(default_factory=list)

    # ---- Quantum-inspired ----
    quantum_default_sweeps: int = 2000
    quantum_default_restarts: int = 8
    quantum_trotter_slices: int = 20
    quantum_seed: int = 1337
    qc_year_assumption: int = 2035

    # ---- ML (optional, local) ----
    ml_enabled: bool = False
    ml_model_dir: str = "./var/models"
    ml_anomaly_weight: float = 0.2

    # ---- Background jobs ----
    redis_url: str | None = None
    scheduler_enabled: bool = True
    audit_anchor_enabled: bool = True
    audit_anchor_interval_hours: float = 24.0
    retention_days: int = 0  # 0 = keep everything

    # ---- Notifications (optional) ----
    notify_high_severity: bool = False
    notify_email_to: str | None = None
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_user: str | None = None
    smtp_password: str | None = None
    smtp_from: str = "egreen-quanta@localhost"
    slack_webhook: str | None = None

    @field_validator("cors_origins", "trusted_tsa_urls", "allowed_hosts", mode="before")
    @classmethod
    def _split_csv(cls, value: object) -> object:
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    @model_validator(mode="after")
    def _enforce_prod_secrets(self) -> Settings:
        """Fail closed: never boot a prod instance with the shipped dev secret."""
        if self.app_env == "prod":
            if self.secret_key == _INSECURE_SECRET or len(self.secret_key) < 32:
                raise ValueError(
                    "SECRET_KEY must be set to a strong (>=32 char) value when APP_ENV=prod"
                )
            if self.store_artifacts and not self.artifact_enc_key:
                raise ValueError("ARTIFACT_ENC_KEY is required when STORE_ARTIFACTS=true")
        return self

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")

    @property
    def is_prod(self) -> bool:
        return self.app_env == "prod"

    @property
    def is_test(self) -> bool:
        return self.app_env == "test"

    @property
    def model_dir_path(self) -> Path:
        p = Path(self.ml_model_dir)
        return p if p.is_absolute() else (BACKEND_DIR / p)

    def sqlite_path(self) -> Path | None:
        """Filesystem path of the SQLite DB file, if the URL is SQLite."""
        if not self.is_sqlite:
            return None
        tail = self.database_url.split(":///", 1)[-1]
        p = Path(tail)
        return p if p.is_absolute() else (BACKEND_DIR / p)


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
