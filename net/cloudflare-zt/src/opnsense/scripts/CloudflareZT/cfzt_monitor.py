#!/usr/local/bin/python3
"""
Cloudflare Zero Trust health monitoring daemon.

Polls connection health at a configurable interval, restarts failed
connections, and sends OPNsense notifications on failure/recovery.

Runs as a standalone daemon; managed via cfzt-monitor configd actions.
PID file: /var/run/cfzt-monitor.pid
"""

import json
import os
import signal
import sys
import syslog
import time

sys.path.insert(0, os.path.dirname(__file__))

from cfzt_config import get_config

PID_FILE = '/var/run/cfzt-monitor.pid'
RUN_DIR = '/var/run'

_running = True


def _pid_file(conn_uuid: str, proto: str) -> str:
    prefix = 'cfzt-warp' if proto in ('warp_masque', 'warp_wireguard') else 'cloudflared'
    return f'{RUN_DIR}/{prefix}-{conn_uuid}.pid'


def _read_pid(path: str) -> int | None:
    try:
        return int(open(path).read().strip())
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


def _restart_connection(conn_uuid: str) -> None:
    import subprocess
    syslog.syslog(syslog.LOG_WARNING,
                  f'cfzt-monitor: restarting failed connection {conn_uuid}')
    try:
        subprocess.run(
            ['/usr/local/sbin/configctl', 'cloudflarezt', 'startconn', conn_uuid],
            capture_output=True, timeout=30,
        )
    except Exception as e:
        syslog.syslog(syslog.LOG_ERR,
                      f'cfzt-monitor: restart of {conn_uuid} failed: {e}')


def _send_notification(subject: str, body: str) -> None:
    """Send OPNsense system notification (non-blocking best-effort)."""
    try:
        import subprocess
        subprocess.run(
            ['/usr/local/opnsense/scripts/OPNsense/Notifications/send.py',
             subject, body],
            capture_output=True, timeout=10,
        )
    except Exception:
        pass


def _write_pid() -> None:
    with open(PID_FILE, 'w') as f:
        f.write(str(os.getpid()))
    os.chmod(PID_FILE, 0o644)


def _remove_pid() -> None:
    try:
        os.unlink(PID_FILE)
    except FileNotFoundError:
        pass


def _handle_signal(sig, _frame) -> None:
    global _running
    _running = False


def run_monitor() -> None:
    global _running

    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)

    syslog.openlog('cfzt-monitor', syslog.LOG_PID, syslog.LOG_DAEMON)
    _write_pid()
    syslog.syslog(syslog.LOG_INFO, 'cfzt-monitor: started')

    # Track per-connection state to detect transitions (up→down, down→up)
    last_status: dict[str, bool] = {}

    try:
        while _running:
            try:
                cfg = get_config()
            except Exception as e:
                syslog.syslog(syslog.LOG_ERR, f'cfzt-monitor: config read failed: {e}')
                time.sleep(30)
                continue

            if not cfg['general']['enabled']:
                time.sleep(30)
                continue

            interval = max(5, cfg.get('monitoring', {}).get('health_check_interval', 30))
            notify_fail = cfg.get('monitoring', {}).get('notify_on_failure', True)
            notify_recv = cfg.get('monitoring', {}).get('notify_on_recovery', True)

            for uuid, conn in cfg['connections'].items():
                if not conn.get('enabled'):
                    continue

                pid = _read_pid(_pid_file(uuid, conn['protocol']))
                running = _is_running(pid)
                was_running = last_status.get(uuid)

                if not running and conn.get('registration_status') in ('enrolled', 'registered'):
                    # Connection should be up but isn't
                    if was_running is True:
                        # Transitioned from up to down
                        syslog.syslog(syslog.LOG_WARNING,
                                      f'cfzt-monitor: connection {conn["name"]} went down')
                        if notify_fail:
                            _send_notification(
                                f'Cloudflare ZT: {conn["name"]} disconnected',
                                f'Connection {conn["name"]} ({uuid}) is no longer running. '
                                f'Protocol: {conn["protocol"]}. Auto-restarting.',
                            )
                        _restart_connection(uuid)
                    elif was_running is None:
                        # First check and already down — restart silently
                        _restart_connection(uuid)

                elif running and was_running is False:
                    # Recovered
                    syslog.syslog(syslog.LOG_INFO,
                                  f'cfzt-monitor: connection {conn["name"]} recovered')
                    if notify_recv:
                        _send_notification(
                            f'Cloudflare ZT: {conn["name"]} reconnected',
                            f'Connection {conn["name"]} ({uuid}) is running again.',
                        )

                last_status[uuid] = running

            # Sleep in short increments so SIGTERM is handled promptly
            elapsed = 0
            while _running and elapsed < interval:
                time.sleep(min(5, interval - elapsed))
                elapsed += 5

    finally:
        _remove_pid()
        syslog.syslog(syslog.LOG_INFO, 'cfzt-monitor: stopped')


if __name__ == '__main__':
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'start'

    if cmd == 'status':
        pid = _read_pid(PID_FILE)
        if _is_running(pid):
            print(json.dumps({'running': True, 'pid': pid}))
        else:
            print(json.dumps({'running': False}))
        sys.exit(0)

    if cmd == 'stop':
        pid = _read_pid(PID_FILE)
        if _is_running(pid):
            import signal as _sig
            os.kill(pid, _sig.SIGTERM)
            print(json.dumps({'result': 'ok', 'pid': pid}))
        else:
            print(json.dumps({'result': 'not_running'}))
        sys.exit(0)

    run_monitor()
