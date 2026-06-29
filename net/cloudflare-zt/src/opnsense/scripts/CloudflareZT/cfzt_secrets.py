"""
Encrypted secrets store for Cloudflare Zero Trust plugin.

Secrets (API tokens, private keys, device tokens) are stored in
/usr/local/etc/cloudflarezt/secrets.json, encrypted with AES-256-GCM.
The encryption key is derived from the machine's host key via HKDF-SHA256.
"""

import json
import os
import struct
import hashlib
import hmac

SECRETS_DIR = '/usr/local/etc/cloudflarezt'
SECRETS_FILE = os.path.join(SECRETS_DIR, 'secrets.json')
HOST_KEY_FILE = '/etc/rc.conf.d/opnsense_host_key'

# Salt scoped to this plugin so key material doesn't cross to other plugins
_HKDF_SALT = b'cloudflare-zt-plugin-v1'
_HKDF_INFO = b'secrets-encryption-key'
_KEY_LEN = 32  # AES-256


def _derive_key() -> bytes:
    """Derive a 256-bit encryption key from the machine host key via HKDF-SHA256."""
    # Source material: /etc/hostid if available, else fallback to hostname+machine-id
    ikm = b''
    for candidate in ['/etc/hostid', '/etc/machine-id', '/etc/rc.conf.d/opnsense_host_key']:
        try:
            with open(candidate, 'rb') as f:
                ikm = f.read().strip()
                if ikm:
                    break
        except OSError:
            continue

    if not ikm:
        raise RuntimeError('Cannot find host identity material for key derivation')

    # HKDF-Extract
    prk = hmac.new(_HKDF_SALT, ikm, hashlib.sha256).digest()
    # HKDF-Expand (one block, T(1))
    t1 = hmac.new(prk, _HKDF_INFO + b'\x01', hashlib.sha256).digest()
    return t1[:_KEY_LEN]


def _aes_gcm_encrypt(key: bytes, plaintext: bytes) -> bytes:
    """Encrypt plaintext with AES-256-GCM. Returns nonce+ciphertext+tag."""
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    nonce = os.urandom(12)
    ct = AESGCM(key).encrypt(nonce, plaintext, None)
    return nonce + ct


def _aes_gcm_decrypt(key: bytes, blob: bytes) -> bytes:
    """Decrypt AES-256-GCM blob (nonce+ciphertext+tag)."""
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    nonce, ct = blob[:12], blob[12:]
    return AESGCM(key).decrypt(nonce, ct, None)


def _load_raw() -> dict:
    try:
        with open(SECRETS_FILE, 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _save_raw(data: dict) -> None:
    os.makedirs(SECRETS_DIR, mode=0o700, exist_ok=True)
    tmp = SECRETS_FILE + '.tmp'
    with open(tmp, 'w') as f:
        json.dump(data, f)
    os.chmod(tmp, 0o600)
    os.replace(tmp, SECRETS_FILE)
    os.chmod(SECRETS_FILE, 0o600)


def set_secret(key: str, value: str) -> None:
    """Store a secret value encrypted under the given key."""
    enc_key = _derive_key()
    blob = _aes_gcm_encrypt(enc_key, value.encode('utf-8'))
    data = _load_raw()
    data[key] = blob.hex()
    _save_raw(data)


def get_secret(key: str) -> str | None:
    """Retrieve and decrypt a secret. Returns None if not found."""
    data = _load_raw()
    if key not in data:
        return None
    try:
        enc_key = _derive_key()
        blob = bytes.fromhex(data[key])
        return _aes_gcm_decrypt(enc_key, blob).decode('utf-8')
    except Exception:
        return None


def del_secret(key: str) -> None:
    """Delete a secret."""
    data = _load_raw()
    data.pop(key, None)
    _save_raw(data)


def has_secret(key: str) -> bool:
    return key in _load_raw()
