"""Module 6 - tamper-evident audit log.

``record()`` appends a hash-chained row; ``verify_chain()`` recomputes the chain and
reports the first break; ``create_anchor()`` writes (and optionally Ed25519-signs) the
current head; ``export_range()`` produces an offline-verifiable slice.
"""

from app.services.audit.chain import (
    create_anchor,
    export_range,
    record,
    verify_chain,
)

__all__ = ["create_anchor", "export_range", "record", "verify_chain"]
