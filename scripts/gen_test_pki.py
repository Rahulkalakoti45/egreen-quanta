#!/usr/bin/env python3
"""Generate a self-contained demo PKI for Egreen Quanta.

    python scripts/gen_test_pki.py            # writes PEMs to datasets/certs/

Produces a root CA, an intermediate CA, and a set of leaf certificates that exercise
the detection rules (healthy, weak key, weak digest, expired, EdDSA). The building
blocks are importable so the test-suite can reuse them in-memory.
"""

from __future__ import annotations

import datetime as dt
import json
from dataclasses import dataclass, field
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, ed25519, rsa
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID

_ONE_DAY = dt.timedelta(days=1)
_NOW = dt.datetime.now(dt.UTC)


def _name(cn: str, org: str = "Egreen Quanta Demo") -> x509.Name:
    return x509.Name(
        [
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, org),
            x509.NameAttribute(NameOID.COMMON_NAME, cn),
        ]
    )


def _rsa(bits: int):
    return rsa.generate_private_key(public_exponent=65537, key_size=bits)


@dataclass
class Issued:
    cert: x509.Certificate
    key: object

    @property
    def cert_pem(self) -> str:
        return self.cert.public_bytes(serialization.Encoding.PEM).decode()

    @property
    def key_pem(self) -> str:
        return self.key.private_bytes(  # type: ignore[attr-defined]
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        ).decode()


@dataclass
class DemoPKI:
    root: Issued
    intermediate: Issued
    leaves: dict[str, Issued] = field(default_factory=dict)

    def chain_pem(self, leaf_name: str) -> str:
        return self.leaves[leaf_name].cert_pem + self.intermediate.cert_pem + self.root.cert_pem


def _sign(
    subject: x509.Name,
    subject_key,
    issuer_name: x509.Name,
    issuer_key,
    *,
    is_ca: bool,
    not_before: dt.datetime,
    not_after: dt.datetime,
    path_length: int | None = None,
    digest: hashes.HashAlgorithm | None = hashes.SHA256(),
    ekus: list[x509.ObjectIdentifier] | None = None,
) -> x509.Certificate:
    builder = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer_name)
        .public_key(subject_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(not_before)
        .not_valid_after(not_after)
        .add_extension(x509.BasicConstraints(ca=is_ca, path_length=path_length), critical=True)
    )
    if is_ca:
        builder = builder.add_extension(
            x509.KeyUsage(
                digital_signature=False,
                content_commitment=False,
                key_encipherment=False,
                data_encipherment=False,
                key_agreement=False,
                key_cert_sign=True,
                crl_sign=True,
                encipher_only=False,
                decipher_only=False,
            ),
            critical=True,
        )
    else:
        builder = builder.add_extension(
            x509.KeyUsage(
                digital_signature=True,
                content_commitment=True,
                key_encipherment=False,
                data_encipherment=False,
                key_agreement=False,
                key_cert_sign=False,
                crl_sign=False,
                encipher_only=False,
                decipher_only=False,
            ),
            critical=True,
        )
        if ekus:
            builder = builder.add_extension(x509.ExtendedKeyUsage(ekus), critical=False)
    is_eddsa = isinstance(issuer_key, ed25519.Ed25519PrivateKey)
    return builder.sign(issuer_key, None if is_eddsa else digest)


def build_demo_pki() -> DemoPKI:
    # --- root ---
    root_key = _rsa(4096)
    root_name = _name("Egreen Quanta Demo Root CA")
    root_cert = _sign(
        root_name,
        root_key,
        root_name,
        root_key,
        is_ca=True,
        not_before=_NOW - dt.timedelta(days=1000),
        not_after=_NOW + dt.timedelta(days=3650),
        path_length=1,
    )
    root = Issued(root_cert, root_key)

    # --- intermediate ---
    inter_key = _rsa(3072)
    inter_name = _name("Egreen Quanta Demo Issuing CA")
    inter_cert = _sign(
        inter_name,
        inter_key,
        root_name,
        root_key,
        is_ca=True,
        not_before=_NOW - dt.timedelta(days=900),
        not_after=_NOW + dt.timedelta(days=1825),
        path_length=0,
    )
    intermediate = Issued(inter_cert, inter_key)

    leaves: dict[str, Issued] = {}

    def issue(
        tag: str,
        key,
        *,
        digest: hashes.HashAlgorithm | None = hashes.SHA256(),
        nb: dt.datetime = _NOW - _ONE_DAY,
        na: dt.datetime = _NOW + dt.timedelta(days=365),
    ) -> None:
        cert = _sign(
            _name(f"Egreen Demo {tag}"),
            key,
            inter_name,
            inter_key,
            is_ca=False,
            not_before=nb,
            not_after=na,
            digest=digest,
            ekus=[ExtendedKeyUsageOID.EMAIL_PROTECTION, ExtendedKeyUsageOID.CODE_SIGNING],
        )
        leaves[tag] = Issued(cert, key)

    issue("healthy-ec", ec.generate_private_key(ec.SECP256R1()))
    issue("healthy-rsa", _rsa(3072))
    issue("healthy-ed25519", ed25519.Ed25519PrivateKey.generate())
    issue("weak-key-rsa1024", _rsa(1024))
    # NB: modern `cryptography` refuses to *sign* certs with SHA-1, so a genuine
    # SHA-1-signed cert is provided as a static vector in datasets/certs/ instead.
    issue(
        "expired",
        ec.generate_private_key(ec.SECP256R1()),
        nb=_NOW - dt.timedelta(days=400),
        na=_NOW - dt.timedelta(days=35),
    )

    return DemoPKI(root=root, intermediate=intermediate, leaves=leaves)


def main() -> None:
    out = Path(__file__).resolve().parents[1] / "datasets" / "certs"
    out.mkdir(parents=True, exist_ok=True)
    pki = build_demo_pki()

    (out / "root-ca.pem").write_text(pki.root.cert_pem)
    (out / "root-ca.key").write_text(pki.root.key_pem)
    (out / "issuing-ca.pem").write_text(pki.intermediate.cert_pem)
    (out / "issuing-ca.key").write_text(pki.intermediate.key_pem)

    manifest = {"root": "root-ca.pem", "intermediate": "issuing-ca.pem", "leaves": {}}
    for name, issued in pki.leaves.items():
        (out / f"leaf-{name}.pem").write_text(issued.cert_pem)
        (out / f"leaf-{name}.key").write_text(issued.key_pem)
        (out / f"chain-{name}.pem").write_text(pki.chain_pem(name))
        manifest["leaves"][name] = {
            "cert": f"leaf-{name}.pem",
            "key": f"leaf-{name}.key",
            "chain": f"chain-{name}.pem",
        }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2))
    print(f"[gen_test_pki] wrote demo PKI to {out}")


if __name__ == "__main__":
    main()
