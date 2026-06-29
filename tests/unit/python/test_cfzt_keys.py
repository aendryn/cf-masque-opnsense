"""Unit tests for key generation functions."""

import base64
import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__),
    '../../../net/cloudflare-zt/src/opnsense/scripts/CloudflareZT'))


def test_generate_masque_keypair():
    from cfzt_keys import generate_masque_keypair
    priv_b64, pub_b64, pub_pem = generate_masque_keypair()

    # All three should be non-empty strings
    assert priv_b64 and isinstance(priv_b64, str)
    assert pub_b64 and isinstance(pub_b64, str)
    assert pub_pem and '-----BEGIN PUBLIC KEY-----' in pub_pem

    # Should be valid base64
    priv_der = base64.b64decode(priv_b64)
    pub_der = base64.b64decode(pub_b64)
    assert len(priv_der) > 0
    assert len(pub_der) > 0


def test_masque_keypair_unique():
    from cfzt_keys import generate_masque_keypair
    priv1, pub1, _ = generate_masque_keypair()
    priv2, pub2, _ = generate_masque_keypair()
    assert priv1 != priv2
    assert pub1 != pub2


def test_load_masque_private_key():
    from cfzt_keys import generate_masque_keypair, load_masque_private_key
    from cryptography.hazmat.primitives.asymmetric import ec

    priv_b64, _, _ = generate_masque_keypair()
    key = load_masque_private_key(priv_b64)

    assert isinstance(key.curve, ec.SECP256R1)


def test_generate_self_signed_cert():
    from cfzt_keys import generate_masque_keypair, load_masque_private_key, generate_self_signed_cert
    from cryptography import x509

    priv_b64, _, _ = generate_masque_keypair()
    key = load_masque_private_key(priv_b64)
    cert_der = generate_self_signed_cert(key)

    assert isinstance(cert_der, bytes)
    assert len(cert_der) > 0

    # Parse and verify it's a valid certificate
    cert = x509.load_der_x509_certificate(cert_der)
    assert cert.subject == cert.issuer  # self-signed


def test_wireguard_keypair_fallback():
    """WireGuard keypair generation works even when wg(8) is unavailable."""
    from cfzt_keys import generate_wireguard_keypair
    import unittest.mock as mock

    # Force FileNotFoundError to simulate missing wg binary
    with mock.patch('subprocess.run', side_effect=FileNotFoundError):
        priv, pub = generate_wireguard_keypair()

    assert priv and isinstance(priv, str)
    assert pub and isinstance(pub, str)
    # Both should be valid base64
    base64.b64decode(priv)
    base64.b64decode(pub)


def test_wireguard_keypair_uses_wg_when_available():
    """When wg(8) is available, use it."""
    from cfzt_keys import generate_wireguard_keypair
    import subprocess
    import unittest.mock as mock

    # Only test this if wg is actually present
    try:
        subprocess.run(['wg', 'genkey'], capture_output=True, check=True)
    except (FileNotFoundError, subprocess.CalledProcessError):
        pytest.skip('wg(8) not available')

    priv, pub = generate_wireguard_keypair()
    assert priv and pub
    # WireGuard keys are 44-char base64
    assert len(priv) == 44
    assert len(pub) == 44


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
