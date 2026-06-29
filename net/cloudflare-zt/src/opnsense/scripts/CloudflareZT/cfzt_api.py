#!/usr/local/bin/python3
"""
Cloudflare WARP device registration API client.

API base: https://api.cloudflareclient.com
Version: v0a4471
Protocol details from reverse engineering of official WARP clients.
"""

import base64
import hashlib
import json
import os
import random
import string
import sys
import time
import uuid
import urllib.request
import urllib.error
import urllib.parse
from typing import Optional

# WARP consumer API (mobile client protocol)
WARP_API_BASE = 'https://api.cloudflareclient.com'
WARP_API_VERSION = 'v0a4471'

WARP_HEADERS = {
    'User-Agent': 'WARP for Android',
    'CF-Client-Version': 'a-6.35-4471',
    'Content-Type': 'application/json; charset=UTF-8',
    'Connection': 'Keep-Alive',
}

# Cloudflare Zero Trust dashboard API
CF_API_BASE = 'https://api.cloudflare.com/client/v4'


class WarpAPIError(Exception):
    def __init__(self, status: int, body: dict):
        self.status = status
        self.errors = body.get('errors', [])
        msg = body.get('message', '') or (self.errors[0].get('message', '') if self.errors else 'API error')
        super().__init__(f'HTTP {status}: {msg}')


def _warp_request(method: str, path: str, body: Optional[dict] = None,
                  token: Optional[str] = None, jwt: Optional[str] = None) -> dict:
    url = f'{WARP_API_BASE}/{WARP_API_VERSION}/{path.lstrip("/")}'
    data = json.dumps(body).encode('utf-8') if body else None
    req = urllib.request.Request(url, data=data, method=method)
    for k, v in WARP_HEADERS.items():
        req.add_header(k, v)
    if token:
        req.add_header('Authorization', f'Bearer {token}')
    if jwt:
        req.add_header('CF-Access-Jwt-Assertion', jwt)

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body_bytes = e.read()
        try:
            err = json.loads(body_bytes)
        except Exception:
            err = {'message': body_bytes.decode('utf-8', errors='replace')}
        raise WarpAPIError(e.code, err)


def _random_android_serial(length: int = 16) -> str:
    chars = string.ascii_uppercase + string.digits
    return ''.join(random.choices(chars, k=length))


def register_device(wg_pubkey_b64: str, model: str = 'PC',
                    locale: str = 'en_US', jwt: str = '',
                    service_token_id: str = '', service_token_secret: str = '') -> dict:
    """
    Register a new WARP device using a WireGuard public key.

    For Zero Trust org enrollment pass either:
    - jwt: team JWT from browser login (CF-Access-Jwt-Assertion header)
    - service_token_id + service_token_secret: headless MDM enrollment
      (requires "Service Auth" policy, not "Allow", on the enrollment rule)

    Returns account data including device ID and access token.
    """
    payload = {
        'key': wg_pubkey_b64,
        'install_id': str(uuid.uuid4()),
        'fcm_token': '',
        'tos': time.strftime('%Y-%m-%dT%H:%M:%S.000Z', time.gmtime()),
        'model': model,
        'serial_number': _random_android_serial(),
        'os_version': 'FreeBSD',
        'key_type': 'curve25519',
        'tunnel_type': 'wireguard',
        'locale': locale,
    }
    if service_token_id and service_token_secret:
        payload['auth_client_id'] = service_token_id
        payload['auth_client_secret'] = service_token_secret
    return _warp_request('POST', '/reg', body=payload, jwt=jwt or None)


def enroll_masque_key(device_id: str, device_token: str,
                      masque_pubkey_der_b64: str, device_name: str = '') -> dict:
    """
    Switch a registered device from WireGuard to MASQUE mode by enrolling
    an ECDSA P-256 public key (DER-encoded, base64).
    Returns updated account data including assigned IPs and Cloudflare peer endpoint.
    """
    payload: dict = {
        'key': masque_pubkey_der_b64,
        'key_type': 'secp256r1',
        'tunnel_type': 'masque',
    }
    if device_name:
        payload['name'] = device_name
    return _warp_request('PATCH', f'/reg/{device_id}', body=payload, token=device_token)


def get_account(device_id: str, device_token: str) -> dict:
    return _warp_request('GET', f'/reg/{device_id}/account', token=device_token)


def update_license_key(device_id: str, device_token: str, license_key: str) -> dict:
    return _warp_request('PUT', f'/reg/{device_id}/account',
                         body={'license': license_key}, token=device_token)


def get_devices(device_id: str, device_token: str) -> list:
    result = _warp_request('GET', f'/reg/{device_id}/account/devices', token=device_token)
    return result if isinstance(result, list) else []


# ---------------------------------------------------------------------------
# Cloudflare Zero Trust dashboard API helpers
# ---------------------------------------------------------------------------

def _cf_request(method: str, path: str, api_token: str,
                body: Optional[dict] = None) -> dict:
    url = f'{CF_API_BASE}/{path.lstrip("/")}'
    data = json.dumps(body).encode('utf-8') if body else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header('Authorization', f'Bearer {api_token}')
    req.add_header('Content-Type', 'application/json')
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body_bytes = e.read()
        try:
            err = json.loads(body_bytes)
        except Exception:
            err = {'success': False, 'errors': [{'message': body_bytes.decode('utf-8', errors='replace')}]}
        raise WarpAPIError(e.code, {'message': str(err.get('errors', [{'message': ''}])[0].get('message', ''))})


def validate_api_token(api_token: str) -> dict:
    """Validate a Cloudflare API token. Returns {'valid': bool, 'message': str}."""
    try:
        result = _cf_request('GET', '/user/tokens/verify', api_token)
        if result.get('success'):
            return {'result': 'valid', 'status': result.get('result', {}).get('status')}
        return {'result': 'invalid', 'message': str(result.get('errors', ''))}
    except WarpAPIError as e:
        return {'result': 'invalid', 'message': str(e)}


def list_tunnels(account_id: str, api_token: str) -> list:
    result = _cf_request('GET', f'/accounts/{account_id}/cfd_tunnel', api_token)
    return result.get('result', [])


def create_tunnel(account_id: str, api_token: str, name: str) -> dict:
    import secrets as _secrets
    tunnel_secret = base64.b64encode(_secrets.token_bytes(32)).decode()
    result = _cf_request('POST', f'/accounts/{account_id}/cfd_tunnel', api_token,
                         body={'name': name, 'tunnel_secret': tunnel_secret})
    return result.get('result', {})


def get_tunnel_token(account_id: str, api_token: str, tunnel_id: str) -> str:
    result = _cf_request('GET', f'/accounts/{account_id}/cfd_tunnel/{tunnel_id}/token', api_token)
    return result.get('result', '')


def delete_tunnel(account_id: str, api_token: str, tunnel_id: str) -> dict:
    result = _cf_request('DELETE', f'/accounts/{account_id}/cfd_tunnel/{tunnel_id}', api_token)
    return result.get('result', {})


def rotate_tunnel_secret(account_id: str, api_token: str, tunnel_id: str) -> dict:
    import secrets as _secrets
    new_secret = base64.b64encode(_secrets.token_bytes(32)).decode()
    result = _cf_request('PATCH', f'/accounts/{account_id}/cfd_tunnel/{tunnel_id}', api_token,
                         body={'tunnel_secret': new_secret})
    return result.get('result', {})


def list_tunnel_connections(account_id: str, api_token: str, tunnel_id: str) -> list:
    result = _cf_request('GET', f'/accounts/{account_id}/cfd_tunnel/{tunnel_id}/connections', api_token)
    return result.get('result', [])


# ---------------------------------------------------------------------------
# Device registration management (Zero Trust dashboard API)
# ---------------------------------------------------------------------------

def list_registrations(account_id: str, api_token: str) -> list:
    result = _cf_request('GET', f'/accounts/{account_id}/devices/registrations', api_token)
    return result.get('result', [])


def delete_registration(account_id: str, api_token: str, registration_id: str) -> dict:
    result = _cf_request('DELETE',
                         f'/accounts/{account_id}/devices/registrations/{registration_id}',
                         api_token)
    return result.get('result', {})


def list_physical_devices(account_id: str, api_token: str) -> list:
    result = _cf_request('GET', f'/accounts/{account_id}/devices/physical-devices', api_token)
    return result.get('result', [])


def revoke_device(account_id: str, api_token: str, device_id: str) -> dict:
    result = _cf_request('POST',
                         f'/accounts/{account_id}/devices/physical-devices/{device_id}/revoke',
                         api_token)
    return result.get('result', {})


# ---------------------------------------------------------------------------
# CLI entry point for configd
# ---------------------------------------------------------------------------

def cmd_validatetoken(uuid: str):
    from cfzt_config import get_config
    from cfzt_secrets import get_secret

    cfg = get_config()
    org = cfg['organizations'].get(uuid)
    if not org:
        print(json.dumps({'result': 'failed', 'message': 'Organization not found'}))
        return

    token_ref = org.get('api_token_ref', f'org_apitoken_{uuid}')
    api_token = get_secret(token_ref)
    if not api_token:
        print(json.dumps({'result': 'failed', 'message': 'No API token stored'}))
        return

    result = validate_api_token(api_token)
    print(json.dumps(result))


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print(json.dumps({'result': 'failed', 'message': 'No command'}))
        sys.exit(1)

    cmd = sys.argv[1]
    args = sys.argv[2:]

    os.chdir(os.path.dirname(__file__))

    if cmd == 'validatetoken' and args:
        cmd_validatetoken(args[0])
    else:
        print(json.dumps({'result': 'failed', 'message': f'Unknown command: {cmd}'}))
        sys.exit(1)
