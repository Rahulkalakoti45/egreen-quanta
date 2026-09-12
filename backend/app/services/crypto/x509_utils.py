"""X.509 parsing and parameter extraction (uses ``cryptography``)."""

from __future__ import annotations

import datetime as dt
import hashlib
import re

from cryptography import x509
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import dsa, ec, ed448, ed25519, rsa
from cryptography.x509.oid import NameOID

from app.services.crypto.errors import MaterialParseError
from app.services.crypto.types import CertInfo, KeyParams

_PEM_CERT_RE = re.compile(rb"-----BEGIN CERTIFICATE-----.+?-----END CERTIFICATE-----", re.DOTALL)


def load_certificates(material: bytes) -> list[x509.Certificate]:
    """Load one or more certificates from PEM (possibly concatenated) or a single DER."""
    material = material.strip()
    certs: list[x509.Certificate] = []
    if b"-----BEGIN CERTIFICATE-----" in material:
        for block in _PEM_CERT_RE.findall(material):
            try:
                certs.append(x509.load_pem_x509_certificate(block))
            except ValueError as exc:
                raise MaterialParseError(f"Invalid PEM certificate: {exc}") from exc
    else:
        try:
            certs.append(x509.load_der_x509_certificate(material))
        except ValueError as exc:
            raise MaterialParseError(f"Invalid DER certificate: {exc}") from exc
    if not certs:
        raise MaterialParseError("No certificate found in supplied material")
    return certs


def load_certificate(material: bytes) -> x509.Certificate:
    return load_certificates(material)[0]


def load_public_key(material: bytes):
    material = material.strip()
    try:
        if b"-----BEGIN CERTIFICATE-----" in material:
            return load_certificate(material).public_key()
        if (
            b"-----BEGIN PUBLIC KEY-----" in material
            or b"-----BEGIN RSA PUBLIC KEY-----" in material
        ):
            return serialization.load_pem_public_key(material)
        # try DER SubjectPublicKeyInfo, then DER certificate
        try:
            return serialization.load_der_public_key(material)
        except ValueError:
            return x509.load_der_x509_certificate(material).public_key()
    except ValueError as exc:
        raise MaterialParseError(f"Could not load public key: {exc}") from exc


def key_params(public_key) -> KeyParams:
    if isinstance(public_key, rsa.RSAPublicKey):
        numbers = public_key.public_numbers()
        return KeyParams(key_type="rsa", key_bits=public_key.key_size, rsa_exponent=numbers.e)
    if isinstance(public_key, ec.EllipticCurvePublicKey):
        return KeyParams(
            key_type="ec", key_bits=public_key.curve.key_size, curve=public_key.curve.name
        )
    if isinstance(public_key, ed25519.Ed25519PublicKey):
        return KeyParams(key_type="ed25519", key_bits=256)
    if isinstance(public_key, ed448.Ed448PublicKey):
        return KeyParams(key_type="ed448", key_bits=456)
    if isinstance(public_key, dsa.DSAPublicKey):
        return KeyParams(key_type="dsa", key_bits=public_key.key_size)
    return KeyParams(key_type="unknown")


def spki_sha256(public_key) -> str:
    der = public_key.public_bytes(
        serialization.Encoding.DER,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    return hashlib.sha256(der).hexdigest()


def _name_str(name: x509.Name) -> str:
    return name.rfc4514_string()


def _aware(value: dt.datetime) -> dt.datetime:
    return value if value.tzinfo else value.replace(tzinfo=dt.UTC)


def cert_info(cert: x509.Certificate) -> CertInfo:
    pub = cert.public_key()

    is_ca = False
    try:
        bc = cert.extensions.get_extension_for_class(x509.BasicConstraints).value
        is_ca = bool(bc.ca)
    except x509.ExtensionNotFound:
        pass

    key_usage: list[str] = []
    try:
        ku = cert.extensions.get_extension_for_class(x509.KeyUsage).value
        for attr in (
            "digital_signature",
            "content_commitment",
            "key_encipherment",
            "data_encipherment",
            "key_agreement",
            "key_cert_sign",
            "crl_sign",
        ):
            try:
                present = bool(getattr(ku, attr))
            except ValueError:
                present = False  # e.g. encipher_only when key_agreement is unset
            if present:
                key_usage.append(attr)
    except x509.ExtensionNotFound:
        pass

    eku: list[str] = []
    try:
        for oid in cert.extensions.get_extension_for_class(x509.ExtendedKeyUsage).value:
            eku.append(getattr(oid, "_name", None) or oid.dotted_string)
    except x509.ExtensionNotFound:
        pass

    san: list[str] = []
    try:
        ext = cert.extensions.get_extension_for_class(x509.SubjectAlternativeName).value
        san = [str(getattr(g, "value", g)) for g in ext]
    except x509.ExtensionNotFound:
        pass

    subject = _name_str(cert.subject)
    issuer = _name_str(cert.issuer)

    sig_algo = getattr(cert.signature_algorithm_oid, "_name", None) or (
        cert.signature_algorithm_oid.dotted_string
    )

    return CertInfo(
        subject=subject,
        issuer=issuer,
        serial_hex=format(cert.serial_number, "x"),
        not_before=_aware(cert.not_valid_before_utc),
        not_after=_aware(cert.not_valid_after_utc),
        spki_sha256=spki_sha256(pub),
        sig_algo=sig_algo,
        key=key_params(pub),
        is_ca=is_ca,
        self_signed=(subject == issuer),
        key_usage=key_usage,
        ext_key_usage=eku,
        san=san,
        pem=cert.public_bytes(serialization.Encoding.PEM).decode("ascii"),
    )


def common_name(cert: x509.Certificate) -> str | None:
    try:
        value = cert.subject.get_attributes_for_oid(NameOID.COMMON_NAME)[0].value
    except (IndexError, ValueError):
        return None
    return value if isinstance(value, str) else value.decode("utf-8", "replace")
