"""
Key generation for Cloudflare Zero Trust connections.

- WireGuard keys: Curve25519 (via wg(8) or cryptography library)
- MASQUE keys: ECDSA P-256 (via cryptography library)
"""

import base64
import os
import subprocess
import tempfile
from typing import Tuple

from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import serialization


def generate_wireguard_keypair() -> Tuple[str, str]:
    """
    Generate a WireGuard keypair using wg(8) if available,
    falling back to the cryptography library.
    Returns (private_key_b64, public_key_b64).
    """
    try:
        priv = subprocess.run(
            ['wg', 'genkey'], capture_output=True, check=True
        ).stdout.strip().decode()
        pub = subprocess.run(
            ['wg', 'pubkey'], input=priv.encode(), capture_output=True, check=True
        ).stdout.strip().decode()
        return priv, pub
    except (FileNotFoundError, subprocess.CalledProcessError):
        pass

    # Pure-python fallback using cryptography library's X25519
    from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey
    priv_key = X25519PrivateKey.generate()
    priv_bytes = priv_key.private_bytes(
        serialization.Encoding.Raw,
        serialization.PrivateFormat.Raw,
        serialization.NoEncryption(),
    )
    pub_bytes = priv_key.public_key().public_bytes(
        serialization.Encoding.Raw,
        serialization.PublicFormat.Raw,
    )
    return base64.b64encode(priv_bytes).decode(), base64.b64encode(pub_bytes).decode()


def generate_masque_keypair() -> Tuple[str, str, str]:
    """
    Generate an ECDSA P-256 keypair for MASQUE authentication.

    Returns:
        (private_key_der_b64, public_key_der_b64, public_key_pem)
        - private_key_der_b64: base64-encoded DER EC private key (for storage)
        - public_key_der_b64: base64-encoded DER SubjectPublicKeyInfo (for WARP API enrollment)
        - public_key_pem: PEM public key (for endpoint pinning verification)
    """
    priv_key = ec.generate_private_key(ec.SECP256R1())

    priv_der = priv_key.private_bytes(
        serialization.Encoding.DER,
        serialization.PrivateFormat.TraditionalOpenSSL,
        serialization.NoEncryption(),
    )
    pub_der = priv_key.public_key().public_bytes(
        serialization.Encoding.DER,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    pub_pem = priv_key.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode()

    return (
        base64.b64encode(priv_der).decode(),
        base64.b64encode(pub_der).decode(),
        pub_pem,
    )


def load_masque_private_key(priv_der_b64: str):
    """Load ECDSA private key from base64-encoded DER."""
    from cryptography.hazmat.primitives.serialization import load_der_private_key
    der = base64.b64decode(priv_der_b64)
    return load_der_private_key(der, password=None)


def generate_self_signed_cert(priv_key) -> bytes:
    """
    Generate a self-signed DER certificate for the MASQUE TLS client certificate.
    Cloudflare uses this during the TLS handshake to authenticate the device.
    """
    from cryptography import x509
    from cryptography.x509.oid import NameOID
    from cryptography.hazmat.primitives import hashes
    import datetime

    now = datetime.datetime.now(datetime.timezone.utc)
    subject = x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, 'cfzt-client'),
    ])
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(subject)
        .public_key(priv_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now)
        .not_valid_after(now + datetime.timedelta(days=3650))
        .sign(priv_key, hashes.SHA256())
    )
    return cert.public_bytes(serialization.Encoding.DER)
