"""Reusable constrained field types."""

from __future__ import annotations

import re
from typing import Annotated

from pydantic import AfterValidator

# Deliberately permissive: a SOC platform is frequently deployed on internal networks
# where operator mailboxes live on RFC-6761 special-use domains (``@company.local``,
# ``@corp.test``). We require a sane ``local@domain.tld`` shape and normalise case,
# but do not enforce public deliverability.
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _normalize_email(value: str) -> str:
    value = value.strip().lower()
    if not _EMAIL_RE.match(value) or len(value) > 254:
        raise ValueError("not a valid email address")
    return value


Email = Annotated[str, AfterValidator(_normalize_email)]
