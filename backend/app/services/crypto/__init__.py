"""Module 2 — cryptographic verification core.

Deterministic, offline-by-default verification of digital signatures and X.509 trust:

* ``rsa_ecc``     — RSA (PSS / PKCS#1 v1.5), ECDSA, EdDSA raw-signature verification
* ``x509_utils``  — certificate parsing and parameter extraction
* ``x509_chain``  — path building + validation against a configured trust store
* ``revocation``  — CRL / OCSP (SSRF-guarded, opt-in network)
* ``weak_algo``   — maps extracted parameters to threat findings
* ``jws`` / ``cms_pkcs7`` / ``pdf_pades`` — signed-envelope parsers
* ``engine``      — orchestrates the above into a ``VerificationResult``
"""
