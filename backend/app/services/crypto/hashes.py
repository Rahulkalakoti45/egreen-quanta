"""Digest helpers and the weak-hash registry."""

from __future__ import annotations

import hashlib
from collections.abc import Callable

from cryptography.hazmat.primitives import hashes as c_hashes

from app.services.crypto.errors import UnsupportedAlgorithmError

# Normalised name -> (hashlib name, cryptography HashAlgorithm factory)
_SUPPORTED: dict[str, str] = {
    "md5": "md5",
    "sha1": "sha1",
    "sha224": "sha224",
    "sha256": "sha256",
    "sha384": "sha384",
    "sha512": "sha512",
    "sha3-256": "sha3_256",
    "sha3-384": "sha3_384",
    "sha3-512": "sha3_512",
}

# Digests that must never be trusted for signatures (collision-broken / deprecated).
WEAK_HASHES: frozenset[str] = frozenset({"md5", "sha1", "sha224"})

_CRYPTOGRAPHY_HASHES: dict[str, Callable[[], c_hashes.HashAlgorithm]] = {
    "sha1": c_hashes.SHA1,
    "sha224": c_hashes.SHA224,
    "sha256": c_hashes.SHA256,
    "sha384": c_hashes.SHA384,
    "sha512": c_hashes.SHA512,
    "sha3-256": c_hashes.SHA3_256,
    "sha3-384": c_hashes.SHA3_384,
    "sha3-512": c_hashes.SHA3_512,
}


def normalize_hash_name(name: str) -> str:
    n = name.strip().lower().replace("_", "-")
    n = n.replace("sha-", "sha")  # "sha-256" -> "sha256"
    if n.startswith("sha3") and "-" not in n:
        n = n.replace("sha3", "sha3-")
    if n not in _SUPPORTED:
        raise UnsupportedAlgorithmError(f"Unsupported hash algorithm: {name}")
    return n


def digest(data: bytes, algorithm: str) -> bytes:
    name = normalize_hash_name(algorithm)
    return hashlib.new(_SUPPORTED[name], data).digest()


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def cryptography_hash(name: str) -> c_hashes.HashAlgorithm:
    n = normalize_hash_name(name)
    factory = _CRYPTOGRAPHY_HASHES.get(n)
    if factory is None:
        raise UnsupportedAlgorithmError(f"Hash not usable for signatures: {name}")
    return factory()


def is_weak_hash(name: str) -> bool:
    try:
        return normalize_hash_name(name) in WEAK_HASHES
    except UnsupportedAlgorithmError:
        return True
