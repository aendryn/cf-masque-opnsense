"""
Integration tests for warp.py registration and key rotation flows.
All Cloudflare API calls are mocked; no network access required.
"""

import base64
import datetime
import json
import os
import sys
import tempfile
import textwrap
import unittest.mock as mock
import xml.etree.ElementTree as ET
import pytest

SCRIPTS_DIR = os.path.join(os.path.dirname(__file__),
    '../../net/cloudflare-zt/src/opnsense/scripts/CloudflareZT')
sys.path.insert(0, SCRIPTS_DIR)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def config_xml(tmp_path):
    """Minimal config.xml with one warp_masque connection."""
    content = textwrap.dedent("""\
        <?xml version="1.0"?>
        <opnsense>
          <OPNsense>
            <CloudflareZT>
              <general><enabled>1</enabled></general>
              <connections>
                <connection uuid="conn-test">
                  <enabled>1</enabled>
                  <name>Test</name>
                  <protocol>warp_masque</protocol>
                  <organization_ref>org-test</organization_ref>
                  <registration_status>unregistered</registration_status>
                  <mtu>1280</mtu>
                  <reconnect_delay>5</reconnect_delay>
                  <key_rotation_days>30</key_rotation_days>
                  <wg_peer_port>2408</wg_peer_port>
                  <always_reconnect>1</always_reconnect>
                </connection>
              </connections>
            </CloudflareZT>
          </OPNsense>
        </opnsense>
    """)
    path = tmp_path / 'config.xml'
    path.write_text(content)
    return str(path)


@pytest.fixture(autouse=True)
def patch_config_file(config_xml, monkeypatch):
    """Point both cfzt_config and warp at the temp config.xml."""
    import cfzt_config
    import warp
    monkeypatch.setattr(cfzt_config, 'CONFIG_FILE', config_xml)
    monkeypatch.setattr(warp, 'CONFIG_FILE', config_xml)


@pytest.fixture()
def mock_store(monkeypatch):
    """In-memory secret store, patches warp module's imported names."""
    import warp
    store = {}
    monkeypatch.setattr(warp, 'set_secret', lambda k, v: store.update({k: v}))
    monkeypatch.setattr(warp, 'get_secret', lambda k: store.get(k))
    monkeypatch.setattr(warp, 'del_secret', lambda k: store.pop(k, None))
    return store


FAKE_REG_RESPONSE = {
    'id': 'device-abc-123',
    'token': 'token-xyz-789',
    'config': {
        'peers': [{
            'public_key': 'PeerPubKey123==',
            'endpoint': {
                'host': '162.159.198.1',
                'v4': '162.159.198.1:2408',
                'v4_endpoint': '162.159.198.1:2408',
            },
        }],
        'interface': {
            'addresses': {'v4': '100.96.0.5', 'v6': 'fd01::5'},
        },
    },
}

FAKE_ENROLL_RESPONSE = {
    'id': 'device-abc-123',
    'config': {
        'peers': [{
            'public_key': 'NewPeerPubKey==',
            'endpoint': {'host': '162.159.198.1', 'v4': '162.159.198.1:2408'},
        }],
        'interface': {
            'addresses': {'v4': '100.96.0.5', 'v6': 'fd01::5'},
        },
    },
}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_cmd_register_updates_config_xml(mock_store, config_xml):
    import warp

    with mock.patch.object(warp, 'register_device', return_value=FAKE_REG_RESPONSE), \
         mock.patch.object(warp, 'enroll_masque_key', return_value=FAKE_ENROLL_RESPONSE):
        result = warp.cmd_register('conn-test', jwt=None)

    assert result.get('result') == 'ok', result

    tree = ET.parse(config_xml)
    conn = tree.getroot().find('.//connection[@uuid="conn-test"]')
    assert conn is not None
    assert conn.findtext('device_id') == 'device-abc-123'
    assert conn.findtext('client_ipv4') == '100.96.0.5'
    assert conn.findtext('registration_status') == 'enrolled'


def test_cmd_register_stores_secrets(mock_store, config_xml):
    import warp

    with mock.patch.object(warp, 'register_device', return_value=FAKE_REG_RESPONSE), \
         mock.patch.object(warp, 'enroll_masque_key', return_value=FAKE_ENROLL_RESPONSE):
        warp.cmd_register('conn-test', jwt=None)

    assert 'wg_privkey_conn-test' in mock_store
    assert 'masque_privkey_conn-test' in mock_store
    assert 'masque_cert_conn-test' in mock_store
    assert 'device_token_conn-test' in mock_store


def test_cmd_register_api_failure(mock_store):
    import warp
    from cfzt_api import WarpAPIError

    with mock.patch.object(warp, 'register_device', side_effect=WarpAPIError(403, {'message': 'HTTP 403'})):
        result = warp.cmd_register('conn-test', jwt=None)

    assert result.get('result') == 'failed'
    assert '403' in result.get('message', '')


def test_cmd_register_connection_not_found(mock_store):
    import warp

    result = warp.cmd_register('nonexistent-uuid', jwt=None)
    assert result.get('result') == 'failed'


def test_cmd_rotatekey_generates_new_masque_keys(mock_store, config_xml):
    """rotatekey re-enrolls a new MASQUE keypair."""
    import warp

    mock_store['device_token_conn-test'] = 'old-token'
    mock_store['masque_privkey_conn-test'] = 'old-priv'

    # Pre-set device_id and registration_status in XML
    tree = ET.parse(config_xml)
    conn = tree.getroot().find('.//connection[@uuid="conn-test"]')
    ET.SubElement(conn, 'device_id').text = 'device-abc-123'
    conn.find('registration_status').text = 'enrolled'
    tree.write(config_xml, xml_declaration=True, encoding='unicode')

    with mock.patch.object(warp, 'enroll_masque_key', return_value=FAKE_ENROLL_RESPONSE):
        result = warp.cmd_rotatekey('conn-test')

    assert result.get('result') == 'ok', result
    assert mock_store.get('masque_privkey_conn-test') != 'old-priv'


def test_update_config_xml_atomic(config_xml):
    import warp

    warp._update_config_xml('conn-test', {
        'client_ipv4': '10.0.0.1',
        'registration_status': 'enrolled',
    })

    tree = ET.parse(config_xml)
    conn = tree.getroot().find('.//connection[@uuid="conn-test"]')
    assert conn.findtext('client_ipv4') == '10.0.0.1'
    assert conn.findtext('registration_status') == 'enrolled'


def test_update_config_xml_unknown_uuid_raises(config_xml):
    import warp

    with pytest.raises(RuntimeError, match='not found'):
        warp._update_config_xml('no-such-uuid', {'client_ipv4': '10.0.0.1'})


def test_cmd_rotatekeyscheck_skips_fresh_keys(mock_store, config_xml):
    """rotatekeyscheck does not rotate when last_key_rotation is recent."""
    import warp

    mock_store['device_token_conn-test'] = 'token'
    now_str = datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')

    tree = ET.parse(config_xml)
    conn = tree.getroot().find('.//connection[@uuid="conn-test"]')
    conn.find('registration_status').text = 'enrolled'
    ET.SubElement(conn, 'last_key_rotation').text = now_str
    ET.SubElement(conn, 'auto_rotate_keys').text = '1'
    tree.write(config_xml, xml_declaration=True, encoding='unicode')

    with mock.patch.object(warp, 'enroll_masque_key') as m:
        result = warp.cmd_rotatekeyscheck()

    m.assert_not_called()
    assert result['rotated'] == 0


def test_cmd_rotatekeyscheck_rotates_expired_keys(mock_store, config_xml):
    """rotatekeyscheck rotates when last rotation is past threshold."""
    import warp

    mock_store['device_token_conn-test'] = 'token'
    old_str = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=31)).strftime('%Y-%m-%dT%H:%M:%SZ')

    tree = ET.parse(config_xml)
    conn = tree.getroot().find('.//connection[@uuid="conn-test"]')
    conn.find('registration_status').text = 'enrolled'
    ET.SubElement(conn, 'last_key_rotation').text = old_str
    ET.SubElement(conn, 'auto_rotate_keys').text = '1'
    tree.write(config_xml, xml_declaration=True, encoding='unicode')

    with mock.patch.object(warp, 'enroll_masque_key', return_value=FAKE_ENROLL_RESPONSE):
        result = warp.cmd_rotatekeyscheck()

    assert result['rotated'] == 1


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
