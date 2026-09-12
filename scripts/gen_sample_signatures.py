#!/usr/bin/env python3
"""Generate sample signed artifacts for demos, manual testing and the load script.

    python scripts/gen_sample_signatures.py        # writes to datasets/documents/

Produces, from the in-memory demo PKI (see gen_test_pki.py):

  raw/*.json     - detached raw-signature bundles for POST /api/v1/signatures/verify
                   (RSA-PSS, RSA-PKCS1v15, ECDSA P-256, Ed25519, plus a *tampered*
                   bundle whose payload no longer matches the signature)
  jws/*.txt      - compact JWS tokens (ES256, RS256) + a tampered ES256 token
  cms/*          - detached CMS/PKCS#7 signatures (DER + PEM) with the signed data
  pdf/*.pdf      - PAdES-signed PDF (best effort; skipped if pyHanko API differs)
  manifest.json  - every sample, the endpoint that consumes it, expected verdict

Everything here is demo material — the keys are throwaway.
"""

from __future__ import annotations

import base64
import datetime as dt
import json
from pathlib import Path
from typing import Any

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, ed25519, padding, rsa
from cryptography.hazmat.primitives.serialization import pkcs7
from cryptography.x509 import load_pem_x509_certificate
from gen_test_pki import DemoPKI, Issued
from gen_test_pki import main as gen_test_pki_main

REPO = Path(__file__).resolve().parents[1]
CERTS = REPO / "datasets" / "certs"
OUT = REPO / "datasets" / "documents"
MESSAGE = b"Egreen Quanta sample document. This text's integrity is protected by a signature.\n"


def load_persisted_pki() -> DemoPKI:
    """Load the demo PKI written by ``scripts/gen_test_pki.py`` (generating it
    first if absent).

    The sample signatures MUST be made with the *same* keys that end up in
    ``datasets/certs/`` — that root is what ``make seed`` installs as a trust
    anchor, so a signature made with a fresh throwaway PKI could never verify
    as trusted.
    """
    if not (CERTS / "manifest.json").exists():
        gen_test_pki_main()

    def _issued(cert_file: str, key_file: str) -> Issued:
        cert = load_pem_x509_certificate((CERTS / cert_file).read_bytes())
        key = serialization.load_pem_private_key((CERTS / key_file).read_bytes(), password=None)
        return Issued(cert, key)

    manifest = json.loads((CERTS / "manifest.json").read_text())
    root = _issued(manifest["root"], manifest["root"].replace(".pem", ".key"))
    inter = _issued(manifest["intermediate"], manifest["intermediate"].replace(".pem", ".key"))
    leaves = {
        name: _issued(entry["cert"], entry["key"]) for name, entry in manifest["leaves"].items()
    }
    return DemoPKI(root=root, intermediate=inter, leaves=leaves)


def _b64(data: bytes) -> str:
    return base64.b64encode(data).decode()


def _pem(cert) -> str:
    return cert.public_bytes(serialization.Encoding.PEM).decode()


def _sign_raw(
    key: Any, message: bytes, *, hash_name: str = "sha256", rsa_pad: str = "pss"
) -> bytes:
    halg = {
        "sha256": hashes.SHA256(),
        "sha384": hashes.SHA384(),
        "sha512": hashes.SHA512(),
    }[hash_name]
    if isinstance(key, rsa.RSAPrivateKey):
        pad = (
            padding.PSS(mgf=padding.MGF1(halg), salt_length=padding.PSS.DIGEST_LENGTH)
            if rsa_pad == "pss"
            else padding.PKCS1v15()
        )
        return key.sign(message, pad, halg)
    if isinstance(key, ec.EllipticCurvePrivateKey):
        return key.sign(message, ec.ECDSA(halg))
    if isinstance(key, ed25519.Ed25519PrivateKey):
        return key.sign(message)
    raise TypeError(f"unsupported key type {type(key)!r}")


def _raw_bundles(pki: DemoPKI, manifest: list[dict]) -> None:
    d = OUT / "raw"
    d.mkdir(parents=True, exist_ok=True)

    cases = [
        (
            "rsa-pss",
            pki.leaves["healthy-rsa"],
            {"hash_alg": "sha256", "padding": "pss"},
        ),
        (
            "rsa-pkcs1v15",
            pki.leaves["healthy-rsa"],
            {"hash_alg": "sha256", "padding": "pkcs1v15"},
        ),
        (
            "ecdsa-p256",
            pki.leaves["healthy-ec"],
            {"hash_alg": "sha256", "padding": None},
        ),
        ("ed25519", pki.leaves["healthy-ed25519"], {"hash_alg": None, "padding": None}),
    ]
    for name, issued, opts in cases:
        rsa_pad = opts["padding"] or "pss"
        sig = _sign_raw(
            issued.key, MESSAGE, hash_name=opts["hash_alg"] or "sha256", rsa_pad=rsa_pad
        )
        bundle = {
            "data_b64": _b64(MESSAGE),
            "signature_b64": _b64(sig),
            "hash_alg": opts["hash_alg"],
            "padding": opts["padding"],
            "certificate_pem": pki.chain_pem(
                {
                    "rsa-pss": "healthy-rsa",
                    "rsa-pkcs1v15": "healthy-rsa",
                    "ecdsa-p256": "healthy-ec",
                    "ed25519": "healthy-ed25519",
                }[name]
            ),
        }
        (d / f"{name}.json").write_text(json.dumps(bundle, indent=2))
        manifest.append(
            {
                "file": f"raw/{name}.json",
                "endpoint": "POST /api/v1/signatures/verify",
                "body": "the file contents verbatim",
                "expected": "signature valid; verdict=valid once the demo root CA is "
                "a trust anchor (make seed), else indeterminate. Low risk.",
            }
        )

    # tampered: valid signature, but the payload has been altered by one word.
    good = pki.leaves["healthy-ec"]
    sig = _sign_raw(good.key, MESSAGE, hash_name="sha256")
    tampered = {
        "data_b64": _b64(MESSAGE.replace(b"protected", b"unprotected")),
        "signature_b64": _b64(sig),
        "hash_alg": "sha256",
        "padding": None,
        "certificate_pem": pki.chain_pem("healthy-ec"),
    }
    (d / "tampered.json").write_text(json.dumps(tampered, indent=2))
    manifest.append(
        {
            "file": "raw/tampered.json",
            "endpoint": "POST /api/v1/signatures/verify",
            "body": "the file contents verbatim",
            "expected": "verified=false (T01 signature mismatch), alert raised",
        }
    )


def _jws_tokens(pki: DemoPKI, manifest: list[dict]) -> None:
    import jwt

    d = OUT / "jws"
    d.mkdir(parents=True, exist_ok=True)
    now = dt.datetime.now(tz=dt.UTC)
    digest = hashes.Hash(hashes.SHA256())
    digest.update(MESSAGE)
    claims = {
        "iss": "egreen-quanta-demo",
        "sub": "sample-document",
        "iat": int(now.timestamp()),
        "exp": int((now + dt.timedelta(days=3650)).timestamp()),
        "doc_sha256": digest.finalize().hex(),
    }

    # Embed the signer chain as x5c so the verifier can actually check the
    # signature (and so tampering is detectable) without a side-channel key.
    def _x5c(name: str) -> list[str]:
        chain = [pki.leaves[name].cert, pki.intermediate.cert, pki.root.cert]
        return [
            base64.b64encode(c.public_bytes(serialization.Encoding.DER)).decode() for c in chain
        ]

    es256 = jwt.encode(
        claims,
        pki.leaves["healthy-ec"].key_pem,
        algorithm="ES256",
        headers={"x5c": _x5c("healthy-ec")},
    )
    rs256 = jwt.encode(
        claims,
        pki.leaves["healthy-rsa"].key_pem,
        algorithm="RS256",
        headers={"x5c": _x5c("healthy-rsa")},
    )
    (d / "es256.txt").write_text(es256)
    (d / "rs256.txt").write_text(rs256)

    # tampered: swap a byte in the payload segment so the signature no longer matches.
    head, payload, sig = es256.split(".")
    bad_payload = payload[:-4] + ("A" if payload[-4] != "A" else "B") + payload[-3:]
    (d / "es256-tampered.txt").write_text(f"{head}.{bad_payload}.{sig}")

    for name, key_src, verdict in [
        ("es256", "healthy-ec", "verified=true"),
        ("rs256", "healthy-rsa", "verified=true"),
        ("es256-tampered", "healthy-ec", "verified=false, alert raised"),
    ]:
        manifest.append(
            {
                "file": f"jws/{name}.txt",
                "endpoint": "POST /api/v1/signatures/verify-document (kind=jws)",
                "public_key_pem": _pem(pki.leaves[key_src].cert),
                "expected": verdict,
            }
        )


def _cms_signatures(pki: DemoPKI, manifest: list[dict]) -> None:
    d = OUT / "cms"
    d.mkdir(parents=True, exist_ok=True)
    (d / "message.txt").write_bytes(MESSAGE)

    signer = pki.leaves["healthy-rsa"]
    builder = (
        pkcs7.PKCS7SignatureBuilder()
        .set_data(MESSAGE)
        .add_signer(signer.cert, signer.key, hashes.SHA256())
        .add_certificate(pki.intermediate.cert)
    )
    der = builder.sign(
        serialization.Encoding.DER,
        [pkcs7.PKCS7Options.DetachedSignature, pkcs7.PKCS7Options.Binary],
    )
    (d / "message.p7s").write_bytes(der)
    manifest.append(
        {
            "file": "cms/message.p7s",
            "data_file": "cms/message.txt",
            "endpoint": "POST /api/v1/signatures/verify-document (kind=cms, detached)",
            "expected": "signature valid, signer chain reported "
            "(verdict=valid with the demo root as a trust anchor)",
        }
    )


def _pades_pdf(pki: DemoPKI, manifest: list[dict]) -> None:
    """Best-effort: pyHanko's signing API changes between releases; skip on mismatch."""
    d = OUT / "pdf"
    try:
        import io
        import tempfile

        from cryptography.hazmat.primitives.serialization import (
            BestAvailableEncryption,
            pkcs12,
        )
        from pyhanko.pdf_utils.incremental_writer import IncrementalPdfFileWriter
        from pyhanko.sign import signers
        from pyhanko.sign.fields import SigFieldSpec, append_signature_field

        # Smallest structurally-valid one-page PDF pyHanko will accept.
        minimal_pdf = (
            b"%PDF-1.7\n"
            b"1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
            b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
            b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 612 792]>>endobj\n"
            b"xref\n0 4\n0000000000 65535 f \n"
            b"0000000009 00000 n \n0000000052 00000 n \n0000000101 00000 n \n"
            b"trailer<</Size 4/Root 1 0 R>>\nstartxref\n164\n%%EOF\n"
        )

        signer_leaf = pki.leaves["healthy-rsa"]
        passphrase = b"demo"
        pfx = pkcs12.serialize_key_and_certificates(
            name=b"egreen-demo",
            key=signer_leaf.key,
            cert=signer_leaf.cert,
            cas=[pki.intermediate.cert, pki.root.cert],
            encryption_algorithm=BestAvailableEncryption(passphrase),
        )
        with tempfile.NamedTemporaryFile(suffix=".p12", delete=False) as tf:
            tf.write(pfx)
            pfx_path = tf.name
        try:
            cms_signer = signers.SimpleSigner.load_pkcs12(pfx_file=pfx_path, passphrase=passphrase)
        finally:
            Path(pfx_path).unlink(missing_ok=True)
        if cms_signer is None:
            raise RuntimeError("SimpleSigner.load_pkcs12 returned None")

        w = IncrementalPdfFileWriter(io.BytesIO(minimal_pdf))
        append_signature_field(w, SigFieldSpec(sig_field_name="Signature1"))
        out = signers.sign_pdf(
            w,
            signers.PdfSignatureMetadata(field_name="Signature1", md_algorithm="sha256"),
            signer=cms_signer,
        )
        d.mkdir(parents=True, exist_ok=True)
        (d / "signed.pdf").write_bytes(out.getvalue())
        manifest.append(
            {
                "file": "pdf/signed.pdf",
                "endpoint": "POST /api/v1/signatures/verify-document (kind=pdf)",
                "expected": "verified=true, PAdES signature over the whole file",
            }
        )
        print("[gen_sample_signatures] wrote pdf/signed.pdf")
    except Exception as exc:
        print(f"[gen_sample_signatures] skipped PDF sample ({type(exc).__name__}: {exc})")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    pki = load_persisted_pki()
    manifest: list[dict] = []

    _raw_bundles(pki, manifest)
    _jws_tokens(pki, manifest)
    _cms_signatures(pki, manifest)
    _pades_pdf(pki, manifest)

    (OUT / "manifest.json").write_text(
        json.dumps(
            {
                "generated": dt.datetime.now(tz=dt.UTC).isoformat(),
                "message": MESSAGE.decode(),
                "note": "Demo signatures over throwaway keys. Regenerate with "
                "scripts/gen_sample_signatures.py.",
                "samples": manifest,
            },
            indent=2,
        )
    )
    print(f"[gen_sample_signatures] wrote {len(manifest)} samples to {OUT}")


if __name__ == "__main__":
    main()
