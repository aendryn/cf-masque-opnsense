"""
Encrypted secrets store for Cloudflare Zero Trust plugin.

Secrets (API tokens, private keys, device tokens) are stored in
/usr/local/etc/cloudflarezt/secrets.json, encrypted with AES-256-CBC + HMAC-SHA256.
The encryption key is derived from the machine's host key via HKDF-SHA256.
"""

import json
import os
import subprocess
import hashlib
import hmac

SECRETS_DIR = '/usr/local/etc/cloudflarezt'
SECRETS_FILE = os.path.join(SECRETS_DIR, 'secrets.json')

_HKDF_SALT = b'cloudflare-zt-plugin-v1'
_ENC_INFO  = b'secrets-enc-key'
_AUTH_INFO = b'secrets-auth-key'


def _derive_keys() -> tuple:
    """Derive AES-256 enc key and HMAC-SHA256 auth key from host identity via HKDF-SHA256."""
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
    prk = hmac.new(_HKDF_SALT, ikm, hashlib.sha256).digest()
    enc_key  = hmac.new(prk, _ENC_INFO  + b'\x01', hashlib.sha256).digest()
    auth_key = hmac.new(prk, _AUTH_INFO + b'\x01', hashlib.sha256).digest()
    return enc_key, auth_key


def _encrypt(plaintext: bytes) -> bytes:
    """AES-256-CBC + HMAC-SHA256 (encrypt-then-MAC). Returns iv+mac+ciphertext."""
    enc_key, auth_key = _derive_keys()
    iv = os.urandom(16)
    proc = subprocess.run(
        ['openssl', 'enc', '-aes-256-cbc',
         '-K', enc_key.hex(), '-iv', iv.hex(), '-nosalt'],
        input=plaintext, capture_output=True, check=True
    )
    ct = proc.stdout
    mac = hmac.new(auth_key, iv + ct, hashlib.sha256).digest()
    return iv + mac + ct


def _decrypt(blob: bytes) -> bytes:
    """Verify HMAC then AES-256-CBC decrypt."""
    enc_key, auth_key = _derive_keys()
    iv, mac, ct = blob[:16], blob[16:48], blob[48:]
    expected = hmac.new(auth_key, iv + ct, hashlib.sha256).digest()
    if not hmac.compare_digest(mac, expected):
        raise ValueError('MAC verification failed')
    proc = subprocess.run(
        ['openssl', 'enc', '-d', '-aes-256-cbc',
         '-K', enc_key.hex(), '-iv', iv.hex(), '-nosalt'],
        input=ct, capture_output=True, check=True
    )
    return proc.stdout


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
    blob = _encrypt(value.encode('utf-8'))
    data = _load_raw()
    data[key] = blob.hex()
    _save_raw(data)


def get_secret(key: str) -> str | None:
    """Retrieve and decrypt a secret. Returns None if not found."""
    data = _load_raw()
    if key not in data:
        return None
    try:
        blob = bytes.fromhex(data[key])
        return _decrypt(blob).decode('utf-8')
    except Exception:
        return None


def del_secret(key: str) -> None:
    """Delete a secret."""
    data = _load_raw()
    data.pop(key, None)
    _save_raw(data)


def has_secret(key: str) -> bool:
    return key in _load_raw()
