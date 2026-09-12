"""CMS / PKCS#7 SignedData parsing and verification (detached or attached).

Built on ``asn1crypto`` for the structure and ``cryptography`` for the primitives.
Supports the common case: a single RSA/ECDSA signer with signed attributes.
"""

from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass, field

from asn1crypto import cms as asn1_cms
from cryptography import x509
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes as c_hashes
from cryptography.hazmat.primitives.asymmetric import ec, ed448, ed25519, padding, rsa

from app.services.crypto.errors import MaterialParseError, UnsupportedAlgorithmError
from app.services.crypto.hashes import cryptography_hash
from app.services.crypto.hashes import digest as raw_digest
from app.services.crypto.x509_utils import cert_info

_HASH_BY_OID_NAME = {
    "md5": "md5",
    "sha1": "sha1",
    "sha224": "sha224",
    "sha256": "sha256",
    "sha384": "sha384",
    "sha512": "sha512",
    "sha3_256": "sha3-256",
    "sha3_384": "sha3-384",
    "sha3_512": "sha3-512",
}

# id-aa-signatureTimeStampToken
_TSTOKEN_OID = "1.2.840.113549.1.9.16.2.14"


@dataclass(slots=True)
class CmsResult:
    verified: bool
    detached: bool
    digest_alg: str
    signature_alg: str
    signer_cert_pem: str | None
    signer_info: dict | None
    signing_time: dt.datetime | None
    tsa_present: bool
    content: bytes | None
    errors: list[str] = field(default_factory=list)
    extra_certs_pem: list[str] = field(default_factory=list)


_EOL_RE = re.compile(rb"\r\n|\r|\n")


def _smime_canonical(data: bytes) -> bytes:
    """S/MIME text canonicalisation (RFC 5751 §3.1.1): every line ending -> CRLF.

    Signers such as ``cryptography``'s PKCS7 builder canonicalise the content this
    way before computing ``messageDigest`` unless a binary flag is set, so a
    verifier has to try this form too or it rejects every text-mode detached
    signature.
    """
    return _EOL_RE.sub(b"\r\n", data)


def _digest_matches(md_attr: bytes, content: bytes, hash_name: str) -> bool:
    """True if the CMS messageDigest matches the content as binary *or* as
    S/MIME-canonicalised text."""
    if md_attr == raw_digest(content, hash_name):
        return True
    canon = _smime_canonical(content)
    return canon != content and md_attr == raw_digest(canon, hash_name)


def _load_signed_data(blob: bytes) -> asn1_cms.SignedData:
    try:
        info = asn1_cms.ContentInfo.load(blob)
    except ValueError as exc:
        raise MaterialParseError(f"Not valid CMS/PKCS#7 DER: {exc}") from exc
    if info["content_type"].native != "signed_data":
        raise MaterialParseError(
            f"CMS content type is {info['content_type'].native!r}, expected signed_data"
        )
    return info["content"]


def _certs(signed_data: asn1_cms.SignedData) -> list[x509.Certificate]:
    out: list[x509.Certificate] = []
    for entry in signed_data["certificates"]:
        if entry.name == "certificate":
            out.append(x509.load_der_x509_certificate(entry.chosen.dump()))
    return out


def _match_signer(
    signer_info: asn1_cms.SignerInfo, certs: list[x509.Certificate]
) -> x509.Certificate | None:
    sid = signer_info["sid"]
    if sid.name == "issuer_and_serial_number":
        serial = sid.chosen["serial_number"].native
        for c in certs:
            if c.serial_number == serial:
                return c
    else:  # subject_key_identifier
        want = sid.chosen.native
        for c in certs:
            try:
                ext = c.extensions.get_extension_for_class(x509.SubjectKeyIdentifier)
                if ext.value.digest == want:
                    return c
            except x509.ExtensionNotFound:
                continue
    return certs[0] if certs else None


def _hash_name(oid_native: str) -> str:
    return _HASH_BY_OID_NAME.get(oid_native.replace("-", "_"), "sha256")


def _verify_primitive(
    cert: x509.Certificate, signed_bytes: bytes, signature: bytes, hash_name: str, sig_alg: str
) -> bool:
    pub = cert.public_key()
    if hash_name in {"md5", "md2"}:
        # We must be able to *verify* legacy weak-digest signatures in order to flag them.
        halg: c_hashes.HashAlgorithm = c_hashes.MD5()  # noqa: S303
    else:
        try:
            halg = cryptography_hash(hash_name)
        except UnsupportedAlgorithmError:
            halg = c_hashes.SHA256()
    try:
        if isinstance(pub, rsa.RSAPublicKey):
            pad = (
                padding.PSS(mgf=padding.MGF1(halg), salt_length=padding.PSS.DIGEST_LENGTH)
                if "pss" in sig_alg
                else padding.PKCS1v15()
            )
            pub.verify(signature, signed_bytes, pad, halg)
        elif isinstance(pub, ec.EllipticCurvePublicKey):
            pub.verify(signature, signed_bytes, ec.ECDSA(halg))
        elif isinstance(pub, ed25519.Ed25519PublicKey | ed448.Ed448PublicKey):
            pub.verify(signature, signed_bytes)
        else:
            return False
        return True
    except InvalidSignature:
        return False


def verify_cms(blob: bytes, *, external_content: bytes | None = None) -> CmsResult:
    signed_data = _load_signed_data(blob)
    certs = _certs(signed_data)

    encap = signed_data["encap_content_info"]
    embedded = encap["content"].native if encap["content"] else None
    content = embedded if embedded is not None else external_content
    detached = embedded is None

    signer_infos = signed_data["signer_infos"]
    if len(signer_infos) == 0:
        return CmsResult(
            False, detached, "", "", None, None, None, False, content, ["no SignerInfo present"]
        )
    si = signer_infos[0]
    digest_alg = si["digest_algorithm"]["algorithm"].native
    hash_name = _hash_name(digest_alg)
    sig_alg = si["signature_algorithm"]["algorithm"].native

    signer_cert = _match_signer(si, certs)
    errors: list[str] = []
    if signer_cert is None:
        errors.append("signer certificate not found in the CMS")

    signing_time: dt.datetime | None = None
    tsa_present = False
    signed_attrs = si["signed_attrs"]

    if signed_attrs and signed_attrs.native:
        md_attr = None
        for attr in signed_attrs:
            name = attr["type"].native
            if name == "message_digest":
                md_attr = attr["values"][0].native
            elif name == "signing_time":
                signing_time = attr["values"][0].native
        if content is None:
            errors.append("detached CMS but no content supplied to check the message digest")
        elif md_attr is not None and not _digest_matches(md_attr, content, hash_name):
            errors.append("messageDigest attribute does not match the content")
        signed_bytes = signed_attrs.untag().dump()
        signed_candidates = [signed_bytes]
    else:
        if content is None:
            errors.append("no signed attributes and no content to verify against")
            signed_candidates = [b""]
        else:
            # Signature is directly over the content: try binary and canonical text.
            signed_candidates = [content]
            canon = _smime_canonical(content)
            if canon != content:
                signed_candidates.append(canon)

    unsigned_attrs = si["unsigned_attrs"]
    if unsigned_attrs and unsigned_attrs.native:
        for attr in unsigned_attrs:
            if attr["type"].dotted == _TSTOKEN_OID:
                tsa_present = True

    verified = False
    if signer_cert is not None and not errors:
        sig_value = si["signature"].native
        verified = any(
            _verify_primitive(signer_cert, candidate, sig_value, hash_name, sig_alg)
            for candidate in signed_candidates
        )
        if not verified:
            errors.append("signer signature does not verify")

    return CmsResult(
        verified=verified,
        detached=detached,
        digest_alg=hash_name,
        signature_alg=sig_alg,
        signer_cert_pem=cert_info(signer_cert).pem if signer_cert else None,
        signer_info=cert_info(signer_cert).as_dict() if signer_cert else None,
        signing_time=signing_time,
        tsa_present=tsa_present,
        content=content,
        errors=errors,
        extra_certs_pem=[
            cert_info(c).pem for c in certs if signer_cert is None or c is not signer_cert
        ],
    )
