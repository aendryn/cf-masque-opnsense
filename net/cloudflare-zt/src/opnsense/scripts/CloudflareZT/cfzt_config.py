"""
Read OPNsense config.xml and return structured CloudflareZT configuration.
"""

import xml.etree.ElementTree as ET
import os

CONFIG_FILE = '/conf/config.xml'


def _parse_bool(val) -> bool:
    return str(val).strip() in ('1', 'true', 'yes')


def get_config() -> dict:
    """Parse CloudflareZT section from config.xml."""
    try:
        tree = ET.parse(CONFIG_FILE)
        root = tree.getroot()
    except Exception as e:
        raise RuntimeError(f'Failed to parse config.xml: {e}')

    zt = root.find('.//CloudflareZT')
    if zt is None:
        return {'general': {'enabled': False}, 'organizations': {}, 'connections': {}, 'split_tunnel_rules': {}, 'dns': {}, 'monitoring': {}}

    def text(node, tag, default=''):
        el = node.find(tag)
        return el.text.strip() if el is not None and el.text else default

    cfg = {
        'general': {
            'enabled': _parse_bool(text(zt.find('general') if zt.find('general') is not None else ET.Element('x'), 'enabled', '0')),
        },
        'organizations': {},
        'connections': {},
        'split_tunnel_rules': {},
        'dns': {},
        'monitoring': {},
    }

    orgs_node = zt.find('organizations')
    if orgs_node is not None:
        for org in orgs_node.findall('organization'):
            uuid = org.get('uuid', '')
            if not uuid:
                continue
            cfg['organizations'][uuid] = {
                'enabled': _parse_bool(text(org, 'enabled', '1')),
                'name': text(org, 'name'),
                'description': text(org, 'description'),
                'account_id': text(org, 'account_id'),
                'team_name': text(org, 'team_name'),
                'api_token_ref': text(org, 'api_token_ref'),
            }

    conns_node = zt.find('connections')
    if conns_node is not None:
        for conn in conns_node.findall('connection'):
            uuid = conn.get('uuid', '')
            if not uuid:
                continue
            cfg['connections'][uuid] = {
                'enabled': _parse_bool(text(conn, 'enabled', '1')),
                'name': text(conn, 'name'),
                'description': text(conn, 'description'),
                'organization_ref': text(conn, 'organization_ref'),
                'protocol': text(conn, 'protocol', 'warp_masque'),
                'device_id': text(conn, 'device_id'),
                'device_token_ref': text(conn, 'device_token_ref'),
                'device_name': text(conn, 'device_name'),
                'client_ipv4': text(conn, 'client_ipv4'),
                'client_ipv6': text(conn, 'client_ipv6'),
                'endpoint_v4': text(conn, 'endpoint_v4'),
                'endpoint_v6': text(conn, 'endpoint_v6'),
                'endpoint_pubkey_ref': text(conn, 'endpoint_pubkey_ref'),
                'masque_privkey_ref': text(conn, 'masque_privkey_ref'),
                'wg_privkey_ref': text(conn, 'wg_privkey_ref'),
                'wg_pubkey': text(conn, 'wg_pubkey'),
                'wg_peer_pubkey': text(conn, 'wg_peer_pubkey'),
                'wg_peer_port': int(text(conn, 'wg_peer_port', '2408')),
                'tunnel_id': text(conn, 'tunnel_id'),
                'tunnel_token_ref': text(conn, 'tunnel_token_ref'),
                'tunnel_mode': text(conn, 'tunnel_mode', 'split'),
                'use_ipv6': _parse_bool(text(conn, 'use_ipv6', '0')),
                'prefer_ipv6': _parse_bool(text(conn, 'prefer_ipv6', '0')),
                'mtu': int(text(conn, 'mtu', '1280')),
                'bind_interface': text(conn, 'bind_interface'),
                'reconnect_delay': int(text(conn, 'reconnect_delay', '5')),
                'always_reconnect': _parse_bool(text(conn, 'always_reconnect', '1')),
                'http2_fallback': _parse_bool(text(conn, 'http2_fallback', '1')),
                'auto_rotate_keys': _parse_bool(text(conn, 'auto_rotate_keys', '1')),
                'key_rotation_days': int(text(conn, 'key_rotation_days', '30')),
                'last_key_rotation': text(conn, 'last_key_rotation'),
                'registration_status': text(conn, 'registration_status', 'unregistered'),
            }

    rules_node = zt.find('split_tunnel_rules')
    if rules_node is not None:
        for rule in rules_node.findall('rule'):
            uuid = rule.get('uuid', '')
            if not uuid:
                continue
            cfg['split_tunnel_rules'][uuid] = {
                'enabled': _parse_bool(text(rule, 'enabled', '1')),
                'connection_ref': text(rule, 'connection_ref'),
                'action': text(rule, 'action', 'exclude'),
                'type': text(rule, 'type', 'cidr'),
                'value': text(rule, 'value'),
                'description': text(rule, 'description'),
            }

    dns_node = zt.find('dns')
    if dns_node is not None:
        cfg['dns'] = {
            'dns_mode': text(dns_node, 'dns_mode', 'system'),
            'custom_servers': text(dns_node, 'custom_servers'),
            'search_domains': text(dns_node, 'search_domains'),
        }

    mon_node = zt.find('monitoring')
    if mon_node is not None:
        cfg['monitoring'] = {
            'enabled': _parse_bool(text(mon_node, 'enabled', '1')),
            'health_check_interval': int(text(mon_node, 'health_check_interval', '30')),
            'notify_on_failure': _parse_bool(text(mon_node, 'notify_on_failure', '1')),
            'notify_on_recovery': _parse_bool(text(mon_node, 'notify_on_recovery', '1')),
            'log_level': text(mon_node, 'log_level', 'info'),
        }

    return cfg
