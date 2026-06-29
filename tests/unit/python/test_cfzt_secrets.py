"""Unit tests for cfzt_secrets encrypted secrets store."""

import base64
import os
import sys
import tempfile
import pytest

# Point to the plugin scripts directory
sys.path.insert(0, os.path.join(os.path.dirname(__file__),
    '../../../net/cloudflare-zt/src/opnsense/scripts/CloudflareZT'))


def _patch_secrets(tmp_path, monkeypatch):
    """Redirect secrets to a temp directory and stub key derivation."""
    secrets_file = str(tmp_path / 'secrets.json')
    monkeypatch.setattr('cfzt_secrets.SECRETS_FILE', secrets_file)
    monkeypatch.setattr('cfzt_secrets.SECRETS_DIR', str(tmp_path))

    # Provide a deterministic key instead of reading /etc/hostid
    fixed_key = os.urandom(32)
    monkeypatch.setattr('cfzt_secrets._derive_key', lambda: fixed_key)
    return fixed_key


def test_set_and_get_secret(tmp_path, monkeypatch):
    import cfzt_secrets
    _patch_secrets(tmp_path, monkeypatch)

    cfzt_secrets.set_secret('test_key', 'super-secret-value')
    assert cfzt_secrets.get_secret('test_key') == 'super-secret-value'


def test_get_missing_secret_returns_none(tmp_path, monkeypatch):
    import cfzt_secrets
    _patch_secrets(tmp_path, monkeypatch)

    assert cfzt_secrets.get_secret('nonexistent') is None


def test_del_secret(tmp_path, monkeypatch):
    import cfzt_secrets
    _patch_secrets(tmp_path, monkeypatch)

    cfzt_secrets.set_secret('ephemeral', 'value')
    assert cfzt_secrets.has_secret('ephemeral')
    cfzt_secrets.del_secret('ephemeral')
    assert not cfzt_secrets.has_secret('ephemeral')
    assert cfzt_secrets.get_secret('ephemeral') is None


def test_overwrite_secret(tmp_path, monkeypatch):
    import cfzt_secrets
    _patch_secrets(tmp_path, monkeypatch)

    cfzt_secrets.set_secret('key', 'first')
    cfzt_secrets.set_secret('key', 'second')
    assert cfzt_secrets.get_secret('key') == 'second'


def test_multiple_secrets_independent(tmp_path, monkeypatch):
    import cfzt_secrets
    _patch_secrets(tmp_path, monkeypatch)

    cfzt_secrets.set_secret('alpha', 'value-alpha')
    cfzt_secrets.set_secret('beta', 'value-beta')
    assert cfzt_secrets.get_secret('alpha') == 'value-alpha'
    assert cfzt_secrets.get_secret('beta') == 'value-beta'


def test_secrets_file_mode(tmp_path, monkeypatch):
    """Secrets file must be mode 0600."""
    import cfzt_secrets
    _patch_secrets(tmp_path, monkeypatch)

    cfzt_secrets.set_secret('k', 'v')
    stat = os.stat(cfzt_secrets.SECRETS_FILE)
    assert oct(stat.st_mode & 0o777) == oct(0o600)


def test_unicode_secret(tmp_path, monkeypatch):
    import cfzt_secrets
    _patch_secrets(tmp_path, monkeypatch)

    value = '🔑 secret with unicode: ñoño'
    cfzt_secrets.set_secret('unicode_key', value)
    assert cfzt_secrets.get_secret('unicode_key') == value


def test_wrong_key_fails_decryption(tmp_path, monkeypatch):
    """Tampered encryption key must not decrypt successfully."""
    import cfzt_secrets
    key1 = _patch_secrets(tmp_path, monkeypatch)
    cfzt_secrets.set_secret('secure', 'plaintext')

    # Swap to a different key
    monkeypatch.setattr('cfzt_secrets._derive_key', lambda: os.urandom(32))
    # Should return None (decrypt fails → returns None, not raises)
    result = cfzt_secrets.get_secret('secure')
    assert result is None


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
