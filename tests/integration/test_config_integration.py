"""
Integration tests for cfzt_config.py — parses real XML structures.
No OPNsense required; creates temp config.xml files.
"""

import os
import sys
import tempfile
import textwrap
import pytest

SCRIPTS_DIR = os.path.join(os.path.dirname(__file__),
    '../../net/cloudflare-zt/src/opnsense/scripts/CloudflareZT')
sys.path.insert(0, SCRIPTS_DIR)


def _write_config(xml_content: str) -> str:
    """Write XML to a temp file, return path."""
    f = tempfile.NamedTemporaryFile(mode='w', suffix='.xml', delete=False)
    f.write(xml_content)
    f.close()
    return f.name


def _get_config_from_xml(xml_content: str) -> dict:
    import cfzt_config as mod
    path = _write_config(xml_content)
    try:
        old = mod.CONFIG_FILE
        mod.CONFIG_FILE = path
        return mod.get_config()
    finally:
        mod.CONFIG_FILE = old
        os.unlink(path)


FULL_CONFIG = textwrap.dedent("""\
    <?xml version="1.0"?>
    <opnsense>
      <OPNsense>
        <CloudflareZT>
          <general>
            <enabled>1</enabled>
          </general>
          <organizations>
            <organization uuid="org-1111">
              <enabled>1</enabled>
              <name>Acme Corp</name>
              <account_id>abc123</account_id>
              <team_name>acme</team_name>
              <api_token_ref>org_apitoken_org-1111</api_token_ref>
            </organization>
          </organizations>
          <connections>
            <connection uuid="conn-2222">
              <enabled>1</enabled>
              <name>Main WARP</name>
              <organization_ref>org-1111</organization_ref>
              <protocol>warp_masque</protocol>
              <device_id>dev-abc</device_id>
              <client_ipv4>100.96.0.1</client_ipv4>
              <client_ipv6>fd01::1</client_ipv6>
              <endpoint_v4>162.159.198.1</endpoint_v4>
              <mtu>1280</mtu>
              <tunnel_mode>split</tunnel_mode>
              <reconnect_delay>5</reconnect_delay>
              <always_reconnect>1</always_reconnect>
              <registration_status>enrolled</registration_status>
              <key_rotation_days>30</key_rotation_days>
            </connection>
          </connections>
          <split_tunnel_rules>
            <rule uuid="rule-3333">
              <enabled>1</enabled>
              <connection_ref>conn-2222</connection_ref>
              <action>exclude</action>
              <type>cidr</type>
              <value>192.168.0.0/16</value>
            </rule>
          </split_tunnel_rules>
          <dns>
            <override_dns>1</override_dns>
            <gateway_dns>0</gateway_dns>
            <custom_servers>1.1.1.1,1.0.0.1</custom_servers>
            <search_domains>example.com</search_domains>
          </dns>
          <monitoring>
            <enabled>1</enabled>
            <health_check_interval>30</health_check_interval>
            <notify_on_failure>1</notify_on_failure>
          </monitoring>
        </CloudflareZT>
      </OPNsense>
    </opnsense>
""")


def test_parse_general_enabled():
    cfg = _get_config_from_xml(FULL_CONFIG)
    assert cfg['general']['enabled'] is True


def test_parse_organization():
    cfg = _get_config_from_xml(FULL_CONFIG)
    assert 'org-1111' in cfg['organizations']
    org = cfg['organizations']['org-1111']
    assert org['name'] == 'Acme Corp'
    assert org['account_id'] == 'abc123'
    assert org['team_name'] == 'acme'


def test_parse_connection():
    cfg = _get_config_from_xml(FULL_CONFIG)
    assert 'conn-2222' in cfg['connections']
    conn = cfg['connections']['conn-2222']
    assert conn['protocol'] == 'warp_masque'
    assert conn['client_ipv4'] == '100.96.0.1'
    assert conn['mtu'] == 1280
    assert conn['registration_status'] == 'enrolled'
    assert conn['always_reconnect'] is True


def test_parse_split_tunnel_rule():
    cfg = _get_config_from_xml(FULL_CONFIG)
    assert 'rule-3333' in cfg['split_tunnel_rules']
    rule = cfg['split_tunnel_rules']['rule-3333']
    assert rule['action'] == 'exclude'
    assert rule['value'] == '192.168.0.0/16'
    assert rule['connection_ref'] == 'conn-2222'


def test_parse_dns():
    cfg = _get_config_from_xml(FULL_CONFIG)
    assert cfg['dns']['override_dns'] is True
    assert cfg['dns']['custom_servers'] == '1.1.1.1,1.0.0.1'
    assert cfg['dns']['search_domains'] == 'example.com'


def test_parse_monitoring():
    cfg = _get_config_from_xml(FULL_CONFIG)
    assert cfg['monitoring']['enabled'] is True
    assert cfg['monitoring']['health_check_interval'] == 30


def test_missing_cloudflarezt_section():
    xml = '<?xml version="1.0"?><opnsense><OPNsense></OPNsense></opnsense>'
    cfg = _get_config_from_xml(xml)
    assert cfg['general']['enabled'] is False
    assert cfg['connections'] == {}
    assert cfg['organizations'] == {}


def test_disabled_plugin():
    xml = textwrap.dedent("""\
        <?xml version="1.0"?>
        <opnsense><OPNsense><CloudflareZT>
          <general><enabled>0</enabled></general>
        </CloudflareZT></OPNsense></opnsense>
    """)
    cfg = _get_config_from_xml(xml)
    assert cfg['general']['enabled'] is False


def test_multiple_connections():
    xml = textwrap.dedent("""\
        <?xml version="1.0"?>
        <opnsense><OPNsense><CloudflareZT>
          <general><enabled>1</enabled></general>
          <connections>
            <connection uuid="c1"><enabled>1</enabled><name>A</name>
              <protocol>warp_masque</protocol><mtu>1280</mtu>
              <reconnect_delay>5</reconnect_delay><key_rotation_days>30</key_rotation_days>
              <wg_peer_port>2408</wg_peer_port>
            </connection>
            <connection uuid="c2"><enabled>0</enabled><name>B</name>
              <protocol>cloudflared</protocol><mtu>1280</mtu>
              <reconnect_delay>5</reconnect_delay><key_rotation_days>30</key_rotation_days>
              <wg_peer_port>2408</wg_peer_port>
            </connection>
          </connections>
        </CloudflareZT></OPNsense></opnsense>
    """)
    cfg = _get_config_from_xml(xml)
    assert len(cfg['connections']) == 2
    assert cfg['connections']['c1']['enabled'] is True
    assert cfg['connections']['c2']['enabled'] is False
    assert cfg['connections']['c2']['protocol'] == 'cloudflared'


def test_defaults_applied():
    """Connections with missing optional fields get correct defaults."""
    xml = textwrap.dedent("""\
        <?xml version="1.0"?>
        <opnsense><OPNsense><CloudflareZT>
          <general><enabled>1</enabled></general>
          <connections>
            <connection uuid="c1"><name>Test</name><protocol>warp_wireguard</protocol></connection>
          </connections>
        </CloudflareZT></OPNsense></opnsense>
    """)
    cfg = _get_config_from_xml(xml)
    conn = cfg['connections']['c1']
    assert conn['mtu'] == 1280
    assert conn['reconnect_delay'] == 5
    assert conn['always_reconnect'] is True
    assert conn['registration_status'] == 'unregistered'
    assert conn['wg_peer_port'] == 2408


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
