"""
Key generation for Cloudflare Zero Trust connections.

- WireGuard keys: Curve25519 (via wg(8))
- MASQUE keys: ECDSA P-256 (via openssl)
"""

import base64
import os
import subprocess
import tempfile
from typing import Tuple


def generate_wireguard_keypair() -> Tuple[str, str]:
    """
    Generate a WireGuard (X25519) keypair via openssl.
    Returns (private_key_b64, public_key_b64) — raw 32-byte keys, base64-encoded.
    """
    # PKCS#8 DER for X25519 is exactly 48 bytes; raw private key = last 32 bytes
    pkcs8 = subprocess.run(
        ['openssl', 'genpkey', '-algorithm', 'X25519', '-outform', 'DER'],
        capture_output=True, check=True
    ).stdout
    # SubjectPublicKeyInfo DER is exactly 44 bytes; raw public key = last 32 bytes
    spki = subprocess.run(
        ['openssl', 'pkey', '-inform', 'DER', '-pubout', '-outform', 'DER'],
        input=pkcs8, capture_output=True, check=True
    ).stdout
    return base64.b64encode(pkcs8[-32:]).decode(), base64.b64encode(spki[-32:]).decode()


def generate_masque_keypair() -> Tuple[str, str, str]:
    """
    Generate an ECDSA P-256 keypair for MASQUE authentication.

    Returns:
        (private_key_der_b64, public_key_der_b64, public_key_pem)
        - private_key_der_b64: base64-encoded PKCS#8 DER EC private key (for storage)
        - public_key_der_b64: base64-encoded DER SubjectPublicKeyInfo (for WARP API enrollment)
        - public_key_pem: PEM public key (for endpoint pinning verification)
    """
    with tempfile.NamedTemporaryFile(delete=False) as f:
        keyfile = f.name
    os.chmod(keyfile, 0o600)
    try:
        subprocess.run(
            ['openssl', 'genpkey', '-algorithm', 'EC',
             '-pkeyopt', 'ec_paramgen_curve:P-256',
             '-outform', 'DER', '-out', keyfile],
            check=True, capture_output=True
        )
        with open(keyfile, 'rb') as f:
            priv_der = f.read()
        pub_der = subprocess.run(
            ['openssl', 'pkey', '-inform', 'DER', '-pubout', '-outform', 'DER', '-in', keyfile],
            check=True, capture_output=True
        ).stdout
        pub_pem = subprocess.run(
            ['openssl', 'pkey', '-inform', 'DER', '-pubout', '-outform', 'PEM', '-in', keyfile],
            check=True, capture_output=True
        ).stdout.decode()
    finally:
        os.unlink(keyfile)

    return (
        base64.b64encode(priv_der).decode(),
        base64.b64encode(pub_der).decode(),
        pub_pem,
    )


def load_masque_private_key(priv_der_b64: str) -> str:
    """Returns the base64-encoded DER key; passed opaquely to generate_self_signed_cert."""
    return priv_der_b64


def generate_self_signed_cert(priv_key_b64: str) -> bytes:
    """
    Generate a self-signed DER certificate for the MASQUE TLS client certificate.
    Cloudflare uses this during the TLS handshake to authenticate the device.
    """
    der = base64.b64decode(priv_key_b64)
    # Convert PKCS#8 DER → PEM so openssl req works on both OpenSSL and LibreSSL
    pem = subprocess.run(
        ['openssl', 'pkey', '-inform', 'DER', '-outform', 'PEM'],
        input=der, capture_output=True, check=True
    ).stdout
    with tempfile.NamedTemporaryFile(delete=False, suffix='.pem') as f:
        keyfile = f.name
        f.write(pem)
    os.chmod(keyfile, 0o600)
    try:
        return subprocess.run(
            ['openssl', 'req', '-x509',
             '-key', keyfile,
             '-subj', '/CN=cfzt-client',
             '-days', '3650',
             '-outform', 'DER'],
            capture_output=True, check=True
        ).stdout
    finally:
        os.unlink(keyfile)
