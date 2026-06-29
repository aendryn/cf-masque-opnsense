#!/usr/local/bin/python3
"""
Service lifecycle manager for Cloudflare Zero Trust connections.
Manages cfzt-warp (MASQUE/WireGuard) and cloudflared (tunnel) processes.
"""

import base64
import json
import os
import signal
import subprocess
import sys
import time
import tempfile

sys.path.insert(0, os.path.dirname(__file__))

from cfzt_config import get_config
from cfzt_secrets import set_secret, get_secret, del_secret

RUNTIME_DIR = '/usr/local/etc/cloudflarezt'
RUN_DIR = '/var/run'
CFZT_WARP_BIN = '/usr/local/sbin/cfzt-warp'
CLOUDFLARED_BIN = '/usr/local/bin/cloudflared'
MONITOR_PID = '/var/run/cfzt-monitor.pid'


def _pid_file(conn_uuid: str, proto: str) -> str:
    prefix = 'cfzt-warp' if proto in ('warp_masque', 'warp_wireguard') else 'cloudflared'
    return f'{RUN_DIR}/{prefix}-{conn_uuid}.pid'


def _read_pid(pid_file: str) -> int | None:
    try:
        with open(pid_file) as f:
            return int(f.read().strip())
    except (FileNotFoundError, ValueError):
        return None


def _is_running(pid: int | None) -> bool:
    if not pid:
        return False
    try:
        os.kill(pid, 0)
        return True
    except (ProcessLookupError, PermissionError):
        return False


def _write_warp_config(conn_uuid: str, conn: dict) -> str:
    """Write JSON config for cfzt-warp daemon. Returns path to config file."""
    os.makedirs(RUNTIME_DIR + '/connections', mode=0o700, exist_ok=True)
    path = f'{RUNTIME_DIR}/connections/{conn_uuid}.json'

    masque_priv = get_secret(f'masque_privkey_{conn_uuid}')
    masque_cert = get_secret(f'masque_cert_{conn_uuid}')
    endpoint_pubkey = get_secret(f'endpoint_pubkey_{conn_uuid}')
    wg_priv = get_secret(f'wg_privkey_{conn_uuid}')

    cfg = {
        'connection_uuid': conn_uuid,
        'protocol': conn['protocol'],
        'device_id': conn.get('device_id', ''),
        'client_ipv4': conn.get('client_ipv4', ''),
        'client_ipv6': conn.get('client_ipv6', ''),
        'endpoint_v4': conn.get('endpoint_v4', ''),
        'endpoint_v6': conn.get('endpoint_v6', ''),
        'endpoint_pubkey': endpoint_pubkey or '',
        'masque_private_key': masque_priv or '',
        'masque_cert_der': masque_cert or '',
        'wg_private_key': wg_priv or '',
        'wg_peer_pubkey': conn.get('wg_peer_pubkey', ''),
        'wg_peer_port': conn.get('wg_peer_port', 2408),
        'mtu': conn.get('mtu', 1280),
        'use_ipv6': conn.get('use_ipv6', False),
        'prefer_ipv6': conn.get('prefer_ipv6', False),
        'reconnect_delay': conn.get('reconnect_delay', 5),
        'always_reconnect': conn.get('always_reconnect', True),
        'http2_fallback': conn.get('http2_fallback', True),
        'tunnel_mode': conn.get('tunnel_mode', 'split'),
        'bind_interface': conn.get('bind_interface', ''),
        'pid_file': _pid_file(conn_uuid, conn['protocol']),
        'log_ident': f'cfzt-warp[{conn.get("name", conn_uuid[:8])}]',
    }

    tmp = path + '.tmp'
    with open(tmp, 'w') as f:
        json.dump(cfg, f, indent=2)
    os.chmod(tmp, 0o600)
    os.replace(tmp, path)
    return path


def _write_cloudflared_config(conn_uuid: str, conn: dict) -> str:
    """Write YAML config for cloudflared daemon."""
    os.makedirs(RUNTIME_DIR + '/tunnels', mode=0o700, exist_ok=True)
    path = f'{RUNTIME_DIR}/tunnels/{conn_uuid}.yml'
    tunnel_token = get_secret(f'tunnel_token_{conn_uuid}')

    content = f'tunnel: {conn.get("tunnel_id", "")}\n'
    if tunnel_token:
        content += f'credentials-file: {RUNTIME_DIR}/tunnels/{conn_uuid}-creds.json\n'
        # Write credentials file
        creds = {'AccountTag': '', 'TunnelID': conn.get('tunnel_id', ''), 'TunnelSecret': tunnel_token}
        creds_path = f'{RUNTIME_DIR}/tunnels/{conn_uuid}-creds.json'
        with open(creds_path, 'w') as f:
            json.dump(creds, f)
        os.chmod(creds_path, 0o600)

    content += 'ingress:\n  - service: http_status:404\n'
    content += f'logfile: /var/log/cloudflared-{conn_uuid}.log\n'
    content += f'pidfile: {_pid_file(conn_uuid, "cloudflared")}\n'

    tmp = path + '.tmp'
    with open(tmp, 'w') as f:
        f.write(content)
    os.chmod(tmp, 0o600)
    os.replace(tmp, path)
    return path


def start_connection(conn_uuid: str, conn: dict) -> dict:
    proto = conn['protocol']
    pid_file = _pid_file(conn_uuid, proto)
    pid = _read_pid(pid_file)

    if _is_running(pid):
        return {'result': 'already_running', 'pid': pid}

    if conn.get('registration_status') not in ('enrolled', 'registered') and proto != 'cloudflared':
        return {'result': 'failed', 'message': 'Device not registered. Run register first.'}

    if proto in ('warp_masque', 'warp_wireguard'):
        if not os.path.exists(CFZT_WARP_BIN):
            return {'result': 'failed', 'message': f'{CFZT_WARP_BIN} not found'}
        cfg_path = _write_warp_config(conn_uuid, conn)
        proc = subprocess.Popen(
            [CFZT_WARP_BIN, '--config', cfg_path, '--daemon'],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        # Give daemon a moment to write its PID file
        time.sleep(0.5)
        return {'result': 'ok', 'pid': proc.pid}

    elif proto == 'cloudflared':
        if not os.path.exists(CLOUDFLARED_BIN):
            return {'result': 'failed', 'message': f'{CLOUDFLARED_BIN} not found'}
        cfg_path = _write_cloudflared_config(conn_uuid, conn)
        proc = subprocess.Popen(
            [CLOUDFLARED_BIN, 'tunnel', '--config', cfg_path, 'run'],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        time.sleep(0.5)
        return {'result': 'ok', 'pid': proc.pid}

    return {'result': 'failed', 'message': f'Unknown protocol: {proto}'}


def stop_connection(conn_uuid: str, conn: dict) -> dict:
    proto = conn.get('protocol', 'warp_masque')
    pid_file = _pid_file(conn_uuid, proto)
    pid = _read_pid(pid_file)

    if not _is_running(pid):
        return {'result': 'not_running'}

    try:
        os.kill(pid, signal.SIGTERM)
        for _ in range(50):
            time.sleep(0.1)
            if not _is_running(pid):
                break
        else:
            os.kill(pid, signal.SIGKILL)
    except ProcessLookupError:
        pass

    try:
        os.unlink(pid_file)
    except FileNotFoundError:
        pass

    return {'result': 'ok'}


def cmd_start() -> str:
    cfg = get_config()
    if not cfg['general']['enabled']:
        return 'disabled'
    results = []
    for uuid, conn in cfg['connections'].items():
        if conn['enabled']:
            r = start_connection(uuid, conn)
            results.append(f"{conn['name']}: {r['result']}")
    return 'started: ' + ', '.join(results) if results else 'no connections'


def cmd_stop() -> str:
    cfg = get_config()
    results = []
    for uuid, conn in cfg['connections'].items():
        r = stop_connection(uuid, conn)
        results.append(f"{conn['name']}: {r['result']}")
    return 'stopped: ' + ', '.join(results) if results else 'no connections'


def cmd_restart() -> str:
    cmd_stop()
    time.sleep(1)
    return cmd_start()


def cmd_status() -> str:
    cfg = get_config()
    if not cfg['general']['enabled']:
        return 'disabled'
    active = 0
    total = 0
    for uuid, conn in cfg['connections'].items():
        if not conn['enabled']:
            continue
        total += 1
        pid = _read_pid(_pid_file(uuid, conn['protocol']))
        if _is_running(pid):
            active += 1
    if total == 0:
        return 'no connections configured'
    return f'running ({active}/{total} connections active)'


def cmd_allstatus() -> dict:
    cfg = get_config()
    result = {'overall': 'disabled' if not cfg['general']['enabled'] else 'running', 'connections': {}}
    for uuid, conn in cfg['connections'].items():
        pid = _read_pid(_pid_file(uuid, conn['protocol']))
        running = _is_running(pid)
        result['connections'][uuid] = {
            'name': conn['name'],
            'protocol': conn['protocol'],
            'status': 'connected' if running else ('stopped' if conn['enabled'] else 'disabled'),
            'pid': pid if running else None,
            'client_ipv4': conn.get('client_ipv4', ''),
            'uptime': _get_uptime(pid) if running else None,
        }
    return result


def _get_uptime(pid: int | None) -> str | None:
    if not pid:
        return None
    try:
        import subprocess
        out = subprocess.run(['ps', '-o', 'etime=', '-p', str(pid)],
                             capture_output=True, text=True).stdout.strip()
        return out or None
    except Exception:
        return None


def cmd_connstatus(conn_uuid: str) -> dict:
    cfg = get_config()
    conn = cfg['connections'].get(conn_uuid)
    if not conn:
        return {'result': 'not_found'}
    pid = _read_pid(_pid_file(conn_uuid, conn['protocol']))
    running = _is_running(pid)
    return {
        'result': 'ok',
        'uuid': conn_uuid,
        'name': conn['name'],
        'protocol': conn['protocol'],
        'status': 'connected' if running else 'stopped',
        'pid': pid if running else None,
        'client_ipv4': conn.get('client_ipv4', ''),
        'client_ipv6': conn.get('client_ipv6', ''),
        'registration_status': conn.get('registration_status', 'unregistered'),
        'uptime': _get_uptime(pid) if running else None,
    }


def cmd_startconn(conn_uuid: str) -> str:
    cfg = get_config()
    conn = cfg['connections'].get(conn_uuid)
    if not conn:
        return json.dumps({'result': 'failed', 'message': 'Connection not found'})
    return json.dumps(start_connection(conn_uuid, conn))


def cmd_stopconn(conn_uuid: str) -> str:
    cfg = get_config()
    conn = cfg['connections'].get(conn_uuid)
    if not conn:
        return json.dumps({'result': 'failed', 'message': 'Connection not found'})
    return json.dumps(stop_connection(conn_uuid, conn))


def cmd_setsecret(key: str, value_b64: str) -> str:
    try:
        value = base64.b64decode(value_b64).decode('utf-8')
        set_secret(key, value)
        return json.dumps({'result': 'ok'})
    except Exception as e:
        return json.dumps({'result': 'failed', 'message': str(e)})


def cmd_delsecret(key: str) -> str:
    del_secret(key)
    return json.dumps({'result': 'ok'})


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('no command')
        sys.exit(1)

    os.chdir(os.path.dirname(__file__))
    cmd = sys.argv[1]
    args = sys.argv[2:]

    if cmd == 'start':
        print(cmd_start())
    elif cmd == 'stop':
        print(cmd_stop())
    elif cmd == 'restart':
        print(cmd_restart())
    elif cmd == 'status':
        print(cmd_status())
    elif cmd == 'allstatus':
        print(json.dumps(cmd_allstatus()))
    elif cmd == 'startconn' and args:
        print(cmd_startconn(args[0]))
    elif cmd == 'stopconn' and args:
        print(cmd_stopconn(args[0]))
    elif cmd == 'connstatus' and args:
        print(json.dumps(cmd_connstatus(args[0])))
    elif cmd == 'setsecret' and len(args) >= 2:
        print(cmd_setsecret(args[0], args[1]))
    elif cmd == 'delsecret' and args:
        print(cmd_delsecret(args[0]))
    else:
        print(json.dumps({'result': 'failed', 'message': f'Unknown command: {cmd}'}))
        sys.exit(1)
