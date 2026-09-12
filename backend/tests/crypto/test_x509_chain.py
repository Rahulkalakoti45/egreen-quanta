"""X.509 chain building + validation."""

from __future__ import annotations

import datetime as dt

from app.services.crypto.x509_chain import build_and_validate


def test_trusted_chain(demo_pki) -> None:
    leaf = demo_pki.leaves["healthy-ec"].cert
    chain, findings = build_and_validate(
        leaf,
        extra_certs=[demo_pki.intermediate.cert],
        trust_anchors=[demo_pki.root.cert],
    )
    assert chain.status == "trusted"
    assert chain.trust_anchor_spki
    assert len(chain.chain) == 3
    assert not findings


def test_untrusted_root(demo_pki) -> None:
    leaf = demo_pki.leaves["healthy-ec"].cert
    chain, findings = build_and_validate(
        leaf,
        extra_certs=[demo_pki.intermediate.cert, demo_pki.root.cert],
        trust_anchors=[],
    )
    assert chain.status == "untrusted"
    assert any(f.code == "T07" for f in findings)


def test_incomplete_chain(demo_pki) -> None:
    leaf = demo_pki.leaves["healthy-rsa"].cert
    chain, findings = build_and_validate(
        leaf,
        extra_certs=[],  # intermediate missing
        trust_anchors=[demo_pki.root.cert],
    )
    assert chain.status == "incomplete"
    assert any(f.code == "T06" for f in findings)


def test_expired_leaf_flagged(demo_pki) -> None:
    leaf = demo_pki.leaves["expired"].cert
    chain, findings = build_and_validate(
        leaf,
        extra_certs=[demo_pki.intermediate.cert],
        trust_anchors=[demo_pki.root.cert],
        at_time=dt.datetime.now(dt.UTC),
    )
    assert chain.status == "trusted"  # chains fine, but…
    assert any(f.code == "T08" for f in findings)


def test_validity_respects_at_time(demo_pki) -> None:
    leaf = demo_pki.leaves["expired"].cert
    # at a time when the cert was still valid
    when = leaf.not_valid_before_utc + dt.timedelta(days=1)
    _, findings = build_and_validate(
        leaf,
        extra_certs=[demo_pki.intermediate.cert],
        trust_anchors=[demo_pki.root.cert],
        at_time=when,
    )
    assert not any(f.code == "T08" for f in findings)
