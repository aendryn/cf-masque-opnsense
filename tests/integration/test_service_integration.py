"""
Integration tests for service.py — exercises config writing and process management
without requiring actual cfzt-warp/cloudflared binaries or OPNsense.
"""

import base64
import json
import os
import sys
import tempfile
import textwrap
import unittest.mock as mock
import pytest

SCRIPTS_DIR = os.path.join(os.path.dirname(__file__),
    '../../net/cloudflare-zt/src/opnsense/scripts/CloudflareZT')
sys.path.insert(0, SCRIPTS_DIR)


@pytest.fixture(autouse=True)
def patch_runtime_dirs(tmp_path, monkeypatch):
    """Redirect all runtime file paths to tmp_path."""
    import service
    monkeypatch.setattr(service, 'RUNTIME_DIR', str(tmp_path / 'cloudflarezt'))
    monkeypatch.setattr(service, 'RUN_DIR', str(tmp_path / 'run'))
    monkeypatch.setattr(service, 'CFZT_WARP_BIN', str(tmp_path / 'cfzt-warp'))
    monkeypatch.setattr(service, 'CLOUDFLARED_BIN', str(tmp_path / 'cloudflared'))
    os.makedirs(str(tmp_path / 'run'), exist_ok=True)


@pytest.fixture()
def mock_secrets(monkeypatch):
    import service
    store = {}
    monkeypatch.setattr(service, 'get_secret', lambda k: store.get(k))
    monkeypatch.setattr(service, 'set_secret', lambda k, v: store.update({k: v}))
    monkeypatch.setattr(service, 'del_secret', lambda k: store.pop(k, None))
    return store


def _masque_conn(uuid='conn-1'):
    return {
        'enabled': True,
        'name': 'Test',
        'protocol': 'warp_masque',
        'device_id': 'dev-123',
        'client_ipv4': '100.96.0.1',
        'client_ipv6': 'fd01::1',
        'endpoint_v4': '162.159.198.1',
        'endpoint_v6': '',
        'mtu': 1280,
        'tunnel_mode': 'split',
        'reconnect_delay': 5,
        'always_reconnect': True,
        'http2_fallback': True,
        'use_ipv6': False,
        'prefer_ipv6': False,
        'bind_interface': '',
        'wg_peer_pubkey': '',
        'wg_peer_port': 2408,
        'registration_status': 'enrolled',
    }


def test_write_warp_config_creates_file(tmp_path, mock_secrets):
    import service
    conn = _masque_conn()
    path = service._write_warp_config('conn-1', conn)
    assert os.path.exists(path)
    with open(path) as f:
        data = json.load(f)
    assert data['connection_uuid'] == 'conn-1'
    assert data['protocol'] == 'warp_masque'
    assert data['client_ipv4'] == '100.96.0.1'


def test_write_warp_config_mode_600(tmp_path, mock_secrets):
    import service
    path = service._write_warp_config('conn-1', _masque_conn())
    mode = oct(os.stat(path).st_mode & 0o777)
    assert mode == '0o600'


def test_write_warp_config_includes_secrets(tmp_path, mock_secrets):
    import service
    mock_secrets['masque_privkey_conn-1'] = 'PRIVKEY'
    mock_secrets['masque_cert_conn-1'] = 'CERT'
    path = service._write_warp_config('conn-1', _masque_conn())
    with open(path) as f:
        data = json.load(f)
    assert data['masque_private_key'] == 'PRIVKEY'
    assert data['masque_cert_der'] == 'CERT'


def test_pid_file_name_warp():
    import service
    pf = service._pid_file('conn-1', 'warp_masque')
    assert 'cfzt-warp' in pf
    assert 'conn-1' in pf


def test_pid_file_name_cloudflared():
    import service
    pf = service._pid_file('conn-1', 'cloudflared')
    assert 'cloudflared' in pf


def test_is_running_no_pid():
    import service
    assert service._is_running(None) is False


def test_is_running_nonexistent_pid():
    import service
    # PID 1 is always init, PID 9999999 almost certainly doesn't exist
    # Use a fake large PID; kill(0) will raise ProcessLookupError
    assert service._is_running(9999999) is False


def test_start_connection_missing_binary(tmp_path, mock_secrets, monkeypatch):
    import service
    # Binary doesn't exist in tmp_path
    result = service.start_connection('conn-1', _masque_conn())
    assert result['result'] == 'failed'
    assert 'not found' in result['message']


def test_start_connection_not_registered(tmp_path, mock_secrets, monkeypatch):
    import service
    conn = _masque_conn()
    conn['registration_status'] = 'unregistered'
    result = service.start_connection('conn-1', conn)
    assert result['result'] == 'failed'
    assert 'register' in result['message'].lower()


def test_start_connection_already_running(tmp_path, mock_secrets, monkeypatch):
    import service
    # Simulate a running process by patching _is_running
    monkeypatch.setattr(service, '_is_running', lambda pid: True)
    monkeypatch.setattr(service, '_read_pid', lambda pf: 1234)
    result = service.start_connection('conn-1', _masque_conn())
    assert result['result'] == 'already_running'
    assert result['pid'] == 1234


def test_stop_connection_not_running(tmp_path, monkeypatch):
    import service
    monkeypatch.setattr(service, '_is_running', lambda pid: False)
    monkeypatch.setattr(service, '_read_pid', lambda pf: None)
    result = service.stop_connection('conn-1', _masque_conn())
    assert result['result'] == 'not_running'


def test_cmd_setsecret_roundtrip(tmp_path, monkeypatch):
    import service
    store = {}
    monkeypatch.setattr(service, 'set_secret', lambda k, v: store.update({k: v}))

    val = 'my-token-value'
    encoded = base64.b64encode(val.encode()).decode()
    result = json.loads(service.cmd_setsecret('mykey', encoded))
    assert result['result'] == 'ok'
    assert store['mykey'] == val


def test_cmd_setsecret_invalid_base64(tmp_path, monkeypatch):
    import service
    monkeypatch.setattr(service, 'set_secret', lambda k, v: None)
    result = json.loads(service.cmd_setsecret('k', 'not!!base64!!!'))
    assert result['result'] == 'failed'


def test_cmd_delsecret(tmp_path, monkeypatch):
    import service
    deleted = []
    monkeypatch.setattr(service, 'del_secret', lambda k: deleted.append(k))
    result = json.loads(service.cmd_delsecret('mykey'))
    assert result['result'] == 'ok'
    assert 'mykey' in deleted


def test_write_cloudflared_config(tmp_path, mock_secrets):
    import service
    conn = {
        'tunnel_id': 'tunnel-uuid-abc',
        'name': 'MyTunnel',
    }
    path = service._write_cloudflared_config('conn-1', conn)
    assert os.path.exists(path)
    content = open(path).read()
    assert 'tunnel-uuid-abc' in content
    assert 'pidfile' in content


def test_write_cloudflared_config_with_token(tmp_path, mock_secrets):
    import service
    mock_secrets['tunnel_token_conn-1'] = 'supersecret'
    conn = {'tunnel_id': 'tid', 'name': 'T'}
    path = service._write_cloudflared_config('conn-1', conn)
    content = open(path).read()
    assert 'credentials-file' in content
    creds_path = str(tmp_path / 'cloudflarezt' / 'tunnels' / 'conn-1-creds.json')
    assert os.path.exists(creds_path)
    creds = json.load(open(creds_path))
    assert creds['TunnelSecret'] == 'supersecret'


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
