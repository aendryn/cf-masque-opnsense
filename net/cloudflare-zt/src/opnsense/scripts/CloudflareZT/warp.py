#!/usr/local/bin/python3
"""
WARP device registration, enrollment, and key management backend.
Called by configd actions for register/enroll/rotatekey commands.
"""

import base64
import json
import os
import sys
import datetime
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.dirname(__file__))

from cfzt_api import register_device, enroll_masque_key, WarpAPIError
from cfzt_config import get_config
from cfzt_keys import generate_wireguard_keypair, generate_masque_keypair, generate_self_signed_cert, load_masque_private_key
from cfzt_secrets import set_secret, get_secret, del_secret

CONFIG_FILE = '/conf/config.xml'
RUNTIME_DIR = '/usr/local/etc/cloudflarezt'


def _update_config_xml(conn_uuid: str, updates: dict) -> None:
    """Write updated fields for a connection back into config.xml."""
    tree = ET.parse(CONFIG_FILE)
    root = tree.getroot()
    zt = root.find('.//CloudflareZT/connections')
    if zt is None:
        raise RuntimeError('CloudflareZT/connections not found in config.xml')
    conn = zt.find(f"connection[@uuid='{conn_uuid}']")
    if conn is None:
        raise RuntimeError(f'Connection {conn_uuid} not found in config.xml')

    for key, val in updates.items():
        el = conn.find(key)
        if el is None:
            el = ET.SubElement(conn, key)
        el.text = str(val)

    tmp = CONFIG_FILE + '.cloudflarezt.tmp'
    tree.write(tmp, encoding='utf-8', xml_declaration=True)
    os.replace(tmp, CONFIG_FILE)


def cmd_register(conn_uuid: str, jwt: str = '') -> dict:
    """
    Register a new WARP device for the given connection UUID.
    1. Generate WireGuard keypair (initial registration uses WireGuard key)
    2. POST to Cloudflare WARP /reg endpoint
    3. Immediately upgrade to MASQUE by enrolling ECDSA P-256 key
    4. Store secrets and update config.xml
    """
    cfg = get_config()
    conn = cfg['connections'].get(conn_uuid)
    if not conn:
        return {'result': 'failed', 'message': f'Connection {conn_uuid} not found'}

    if conn['protocol'] not in ('warp_masque', 'warp_wireguard'):
        return {'result': 'failed', 'message': f'Protocol {conn["protocol"]} does not use WARP registration'}

    device_name = conn.get('device_name', 'OPNsense-Router')

    try:
        # Step 1: Generate WireGuard keypair for initial registration
        wg_priv, wg_pub = generate_wireguard_keypair()

        # Step 2: Register with Cloudflare WARP API
        account_data = register_device(wg_pub, model='PC', locale='en_US', jwt=jwt)

        device_id = account_data.get('id', '')
        device_token = account_data.get('token', '')
        if not device_id or not device_token:
            return {'result': 'failed', 'message': 'Registration response missing id or token'}

        # Step 3: For MASQUE protocol, immediately enroll ECDSA key
        if conn['protocol'] == 'warp_masque':
            masque_priv_b64, masque_pub_b64, masque_pub_pem = generate_masque_keypair()
            updated = enroll_masque_key(device_id, device_token, masque_pub_b64, device_name)
        else:
            # WireGuard mode — keep wg key, re-enrollment not needed
            updated = account_data
            masque_priv_b64 = None
            masque_pub_pem = None

        # Extract assigned addresses and peer endpoint from response
        iface = updated.get('config', {}).get('interface', {}).get('addresses', {})
        peers = updated.get('config', {}).get('peers', [])
        peer = peers[0] if peers else {}
        endpoint_v4 = peer.get('endpoint', {}).get('v4', '').rstrip(':0')
        endpoint_v6_raw = peer.get('endpoint', {}).get('v6', '')
        # Strip brackets and port: [2606:...]:0 -> 2606:...
        endpoint_v6 = endpoint_v6_raw.lstrip('[').split(']:')[0] if endpoint_v6_raw else ''
        peer_pubkey = peer.get('public_key', '')

    except WarpAPIError as e:
        return {'result': 'failed', 'message': str(e)}
    except Exception as e:
        return {'result': 'failed', 'message': f'Unexpected error: {e}'}

    # Step 4: Store secrets
    set_secret(f'device_token_{conn_uuid}', device_token)
    if masque_priv_b64:
        set_secret(f'masque_privkey_{conn_uuid}', masque_priv_b64)
        # Store the TLS certificate DER (needed by cfzt-warp daemon)
        try:
            priv_key = load_masque_private_key(masque_priv_b64)
            cert_der = generate_self_signed_cert(priv_key)
            set_secret(f'masque_cert_{conn_uuid}', base64.b64encode(cert_der).decode())
        except Exception:
            pass
    if peer_pubkey:
        set_secret(f'endpoint_pubkey_{conn_uuid}', peer_pubkey)
    set_secret(f'wg_privkey_{conn_uuid}', wg_priv)

    # Step 5: Update config.xml with non-secret fields
    xml_updates = {
        'device_id': device_id,
        'device_token_ref': f'device_token_{conn_uuid}',
        'client_ipv4': iface.get('v4', ''),
        'client_ipv6': iface.get('v6', ''),
        'endpoint_v4': endpoint_v4,
        'endpoint_v6': endpoint_v6,
        'endpoint_pubkey_ref': f'endpoint_pubkey_{conn_uuid}',
        'wg_pubkey': wg_pub,
        'wg_peer_pubkey': peer_pubkey,
        'registration_status': 'enrolled' if masque_priv_b64 else 'registered',
        'last_key_rotation': datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
    }
    if masque_priv_b64:
        xml_updates['masque_privkey_ref'] = f'masque_privkey_{conn_uuid}'
        xml_updates['wg_privkey_ref'] = f'wg_privkey_{conn_uuid}'

    try:
        _update_config_xml(conn_uuid, xml_updates)
    except Exception as e:
        return {'result': 'failed', 'message': f'Config update failed: {e}'}

    return {
        'result': 'ok',
        'device_id': device_id,
        'client_ipv4': iface.get('v4', ''),
        'client_ipv6': iface.get('v6', ''),
        'endpoint_v4': endpoint_v4,
        'registration_status': xml_updates['registration_status'],
    }


def cmd_enroll(conn_uuid: str) -> dict:
    """
    Re-enroll a MASQUE key for an existing registration.
    Generates a new ECDSA keypair and updates Cloudflare without re-registering.
    """
    cfg = get_config()
    conn = cfg['connections'].get(conn_uuid)
    if not conn:
        return {'result': 'failed', 'message': f'Connection {conn_uuid} not found'}

    device_id = conn.get('device_id', '')
    if not device_id:
        return {'result': 'failed', 'message': 'Device not registered yet. Run register first.'}

    device_token = get_secret(f'device_token_{conn_uuid}')
    if not device_token:
        return {'result': 'failed', 'message': 'Device token not found in secrets store'}

    try:
        masque_priv_b64, masque_pub_b64, masque_pub_pem = generate_masque_keypair()
        device_name = conn.get('device_name', 'OPNsense-Router')
        updated = enroll_masque_key(device_id, device_token, masque_pub_b64, device_name)
    except WarpAPIError as e:
        return {'result': 'failed', 'message': str(e)}
    except Exception as e:
        return {'result': 'failed', 'message': f'Unexpected error: {e}'}

    set_secret(f'masque_privkey_{conn_uuid}', masque_priv_b64)
    try:
        priv_key = load_masque_private_key(masque_priv_b64)
        cert_der = generate_self_signed_cert(priv_key)
        set_secret(f'masque_cert_{conn_uuid}', base64.b64encode(cert_der).decode())
    except Exception:
        pass

    # Update endpoint pubkey in case it changed
    peers = updated.get('config', {}).get('peers', [])
    peer = peers[0] if peers else {}
    peer_pubkey = peer.get('public_key', '')
    if peer_pubkey:
        set_secret(f'endpoint_pubkey_{conn_uuid}', peer_pubkey)

    try:
        _update_config_xml(conn_uuid, {
            'masque_privkey_ref': f'masque_privkey_{conn_uuid}',
            'endpoint_pubkey_ref': f'endpoint_pubkey_{conn_uuid}',
            'registration_status': 'enrolled',
            'last_key_rotation': datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
        })
    except Exception as e:
        return {'result': 'failed', 'message': f'Config update failed: {e}'}

    return {'result': 'ok', 'registration_status': 'enrolled'}


def cmd_rotatekey(conn_uuid: str) -> dict:
    """Rotate the MASQUE key: generate new keypair, enroll, update config."""
    return cmd_enroll(conn_uuid)


def cmd_rotatekeyscheck() -> dict:
    """Check all connections for keys due for rotation. Returns list of UUIDs needing rotation."""
    cfg = get_config()
    now = datetime.datetime.now(datetime.timezone.utc)
    due = []

    for uuid, conn in cfg['connections'].items():
        if not conn.get('auto_rotate_keys'):
            continue
        if conn.get('registration_status') not in ('enrolled', 'registered'):
            continue

        last = conn.get('last_key_rotation', '')
        days = conn.get('key_rotation_days', 30)
        if not last:
            due.append({'uuid': uuid, 'name': conn['name'], 'reason': 'never rotated'})
            continue
        try:
            last_dt = datetime.datetime.strptime(last, '%Y-%m-%dT%H:%M:%SZ').replace(
                tzinfo=datetime.timezone.utc)
            if (now - last_dt).days >= days:
                due.append({'uuid': uuid, 'name': conn['name'],
                            'days_since_rotation': (now - last_dt).days})
        except ValueError:
            due.append({'uuid': uuid, 'name': conn['name'], 'reason': 'invalid rotation date'})

    # Auto-rotate any that are due
    results = []
    for item in due:
        result = cmd_rotatekey(item['uuid'])
        results.append({'uuid': item['uuid'], 'name': item['name'], 'result': result})

    return {'checked': len(cfg['connections']), 'rotated': len(due), 'results': results}


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print(json.dumps({'result': 'failed', 'message': 'No command'}))
        sys.exit(1)

    os.chdir(os.path.dirname(__file__))
    cmd = sys.argv[1]
    args = sys.argv[2:]

    dispatch = {
        'register': lambda: cmd_register(args[0], args[1] if len(args) > 1 else ''),
        'enroll': lambda: cmd_enroll(args[0]),
        'rotatekey': lambda: cmd_rotatekey(args[0]),
        'rotatekeyscheck': lambda: cmd_rotatekeyscheck(),
    }

    if cmd not in dispatch or (cmd != 'rotatekeyscheck' and not args):
        print(json.dumps({'result': 'failed', 'message': f'Unknown command or missing args: {cmd}'}))
        sys.exit(1)

    print(json.dumps(dispatch[cmd]()))
