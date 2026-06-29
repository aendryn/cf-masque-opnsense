#!/usr/local/bin/python3
"""
Health monitoring, diagnostics, and log retrieval for Cloudflare Zero Trust.
"""

import json
import os
import re
import subprocess
import sys
import time
import urllib.request
import urllib.error

sys.path.insert(0, os.path.dirname(__file__))

from cfzt_config import get_config

RUN_DIR = '/var/run'
LOG_DIR = '/var/log'

# Cloudflare WARP endpoints for connectivity checks
PROBE_TARGETS = [
    ('162.159.198.1', 443, 'udp', 'MASQUE QUIC primary (UDP 443)'),
    ('162.159.198.2', 443, 'tcp', 'MASQUE HTTP/2 fallback (TCP 443)'),
    ('1.1.1.1', 443, 'tcp', 'Cloudflare DNS'),
    ('cloudflareaccess.com', 443, 'tcp', 'Cloudflare Access'),
]


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


def _tcp_probe(host: str, port: int, timeout: float = 3.0) -> tuple[bool, float]:
    """Probe TCP connectivity. Returns (reachable, latency_ms)."""
    import socket
    t0 = time.monotonic()
    try:
        s = socket.create_connection((host, port), timeout=timeout)
        s.close()
        return True, (time.monotonic() - t0) * 1000
    except (OSError, socket.timeout):
        return False, 0.0


def _udp_probe(host: str, port: int, timeout: float = 3.0) -> tuple[bool, float]:
    """Send a UDP datagram and check for ICMP unreachable or silence."""
    import socket
    t0 = time.monotonic()
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(timeout)
        s.sendto(b'\x00' * 16, (host, port))
        # We can't truly confirm UDP reachability without protocol support,
        # but absence of ICMP unreachable within timeout is a good signal
        try:
            s.recv(64)
        except socket.timeout:
            pass  # No ICMP unreachable — likely reachable
        s.close()
        return True, (time.monotonic() - t0) * 1000
    except OSError:
        return False, 0.0


def cmd_ping() -> dict:
    """Probe Cloudflare endpoints for connectivity."""
    results = []
    for host, port, proto, label in PROBE_TARGETS:
        if proto == 'tcp':
            ok, latency = _tcp_probe(host, port)
        else:
            ok, latency = _udp_probe(host, port)
        results.append({
            'target': f'{host}:{port}/{proto}',
            'description': label,
            'reachable': ok,
            'latency_ms': round(latency, 1) if ok else None,
        })
    return {'result': 'ok', 'probes': results}


def _get_interface_stats(ifname: str) -> dict:
    """Read interface statistics from ifconfig."""
    try:
        out = subprocess.run(
            ['ifconfig', ifname], capture_output=True, text=True, timeout=5
        ).stdout
        # Parse inet addresses
        addrs = re.findall(r'inet6?\s+([\da-f\.:]+)', out)
        # Parse rx/tx bytes (netstat style not available via ifconfig directly)
        return {'interface': ifname, 'addresses': addrs, 'raw': out.strip()}
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return {'interface': ifname, 'error': 'ifconfig failed'}


def _get_routes_for_interface(ifname: str) -> list:
    """List routes using the given interface."""
    try:
        out = subprocess.run(
            ['netstat', '-rn', '-f', 'inet'], capture_output=True, text=True, timeout=5
        ).stdout
        routes = []
        for line in out.splitlines():
            if ifname in line:
                routes.append(line.strip())
        return routes
    except Exception:
        return []


def cmd_diagnostics(conn_uuid: str) -> dict:
    """Run full diagnostics for a connection."""
    if conn_uuid == 'all':
        cfg = get_config()
        return {
            'result': 'ok',
            'connections': {
                uuid: cmd_diagnostics(uuid)
                for uuid in cfg['connections']
            }
        }

    cfg = get_config()
    conn = cfg['connections'].get(conn_uuid)
    if not conn:
        return {'result': 'not_found', 'uuid': conn_uuid}

    proto = conn['protocol']
    pid_file = _pid_file(conn_uuid, proto)
    pid = _read_pid(pid_file)
    running = _is_running(pid)

    # Derive interface name: cfzt0, cfzt1, etc.
    # cfzt-warp writes its interface name to a state file
    iface_file = f'/var/run/cfzt-iface-{conn_uuid}'
    ifname = None
    try:
        with open(iface_file) as f:
            ifname = f.read().strip()
    except FileNotFoundError:
        pass

    diag = {
        'result': 'ok',
        'uuid': conn_uuid,
        'name': conn['name'],
        'protocol': proto,
        'process': {
            'running': running,
            'pid': pid,
            'pid_file': pid_file,
        },
        'registration': {
            'status': conn.get('registration_status', 'unregistered'),
            'device_id': conn.get('device_id', ''),
            'client_ipv4': conn.get('client_ipv4', ''),
            'client_ipv6': conn.get('client_ipv6', ''),
            'endpoint_v4': conn.get('endpoint_v4', ''),
        },
        'interface': _get_interface_stats(ifname) if ifname else {'error': 'interface unknown'},
        'routes': _get_routes_for_interface(ifname) if ifname else [],
        'connectivity': cmd_ping(),
    }

    return diag


def cmd_stats(conn_uuid: str) -> dict:
    """Return traffic statistics for a connection."""
    cfg = get_config()
    conn = cfg['connections'].get(conn_uuid)
    if not conn:
        return {'result': 'not_found'}

    iface_file = f'/var/run/cfzt-iface-{conn_uuid}'
    try:
        with open(iface_file) as f:
            ifname = f.read().strip()
    except FileNotFoundError:
        return {'result': 'ok', 'stats': None, 'message': 'Interface not yet available'}

    try:
        out = subprocess.run(
            ['netstat', '-I', ifname, '-b', '-n'], capture_output=True, text=True, timeout=5
        ).stdout
        lines = [l for l in out.splitlines() if ifname in l]
        return {'result': 'ok', 'interface': ifname, 'raw': '\n'.join(lines)}
    except Exception as e:
        return {'result': 'error', 'message': str(e)}


def _syslog_entries(ident_pattern: str, lines: int) -> list:
    """Read recent syslog entries matching ident_pattern."""
    log_files = ['/var/log/system.log', '/var/log/messages']
    entries = []
    for lf in log_files:
        try:
            # Use grep to filter — avoids reading whole file into Python
            out = subprocess.run(
                ['grep', '-a', ident_pattern, lf],
                capture_output=True, text=True, timeout=10
            ).stdout
            entries.extend(out.splitlines())
        except (FileNotFoundError, subprocess.TimeoutExpired):
            continue
    # Deduplicate and take tail
    return entries[-lines:]


def cmd_logs(conn_uuid: str, lines: int = 100) -> dict:
    if conn_uuid == 'all':
        entries = _syslog_entries('cfzt-warp\\|cloudflared', lines)
        return {'result': 'ok', 'entries': entries}

    cfg = get_config()
    conn = cfg['connections'].get(conn_uuid)
    if not conn:
        return {'result': 'not_found'}

    name = conn.get('name', conn_uuid[:8])
    entries = _syslog_entries(f'cfzt-warp\\[{name}\\]\\|cloudflared-{conn_uuid}', lines)

    # Also check dedicated log file for cloudflared
    if conn['protocol'] == 'cloudflared':
        log_file = f'/var/log/cloudflared-{conn_uuid}.log'
        try:
            out = subprocess.run(
                ['tail', '-n', str(lines), log_file],
                capture_output=True, text=True, timeout=5
            ).stdout
            entries.extend(out.splitlines())
            entries = entries[-lines:]
        except FileNotFoundError:
            pass

    return {'result': 'ok', 'connection': name, 'entries': entries}


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print(json.dumps({'result': 'failed', 'message': 'No command'}))
        sys.exit(1)

    os.chdir(os.path.dirname(__file__))
    cmd = sys.argv[1]
    args = sys.argv[2:]

    if cmd == 'ping':
        print(json.dumps(cmd_ping()))
    elif cmd == 'diagnostics' and args:
        print(json.dumps(cmd_diagnostics(args[0])))
    elif cmd == 'stats' and args:
        print(json.dumps(cmd_stats(args[0])))
    elif cmd == 'logs' and args:
        lines = int(args[1]) if len(args) > 1 else 100
        print(json.dumps(cmd_logs(args[0], lines)))
    else:
        print(json.dumps({'result': 'failed', 'message': f'Unknown command: {cmd}'}))
        sys.exit(1)
