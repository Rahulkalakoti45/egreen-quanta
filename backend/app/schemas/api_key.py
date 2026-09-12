"""API-key schemas."""

from __future__ import annotations

import datetime as dt

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.enums import ApiKeyScope


class ApiKeyCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    scopes: list[ApiKeyScope] = Field(min_length=1)
    expires_in_days: int | None = Field(default=None, ge=1, le=3650)


class ApiKeyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    prefix: str
    scopes: list[str]
    created_by: str | None
    last_used_at: dt.datetime | None
    expires_at: dt.datetime | None
    revoked_at: dt.datetime | None
    created_at: dt.datetime

    @field_validator("scopes", mode="before")
    @classmethod
    def _split_scopes(cls, value: object) -> object:
        # ORM stores scopes as a comma-separated string.
        if isinstance(value, str):
            return [s for s in value.split(",") if s]
        return value


class ApiKeyCreatedOut(ApiKeyOut):
    """Returned once, on creation — carries the plaintext key."""

    api_key: str
