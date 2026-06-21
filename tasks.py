"""Reusable Cisco IOS configuration tasks built on Netmiko.

Shared by the CLI (cli.py) and the Flask web UI (app.py) so the command
definitions live in one place instead of being copy-pasted (and drifting
out of sync, which is how the original IPSec block ended up broken).
"""
from __future__ import annotations

import difflib
from pathlib import Path

# Hardening settings checked during the compliance comparison.
KEY_SETTINGS = [
    "exec-timeout",
    "aaa authentication",
    "service password-encryption",
    "no service",
    "logging host",
    "banner login",
]


def build_device_params(host, username, password, transport="ssh", secret=""):
    """Return a Netmiko connection dict for an IOS device over SSH or Telnet."""
    transport = transport.lower()
    if transport not in ("ssh", "telnet"):
        raise ValueError("transport must be 'ssh' or 'telnet'")
    return {
        "host": host,
        "username": username,
        "password": password,
        "secret": secret,
        "device_type": "cisco_ios_telnet" if transport == "telnet" else "cisco_ios",
        "port": 23 if transport == "telnet" else 22,
    }


def hostname_commands(transport):
    """Set a hostname that records the transport used."""
    return [f"hostname Cisco_{transport.upper()}"]


def syslog_commands(syslog_server_ip):
    """Enable syslog to a remote collector with timestamped, informational logs."""
    return [
        f"logging host {syslog_server_ip}",
        "logging trap informational",
        "service timestamps log datetime msec",
        "logging on",
    ]


def acl_commands(acl_name, entries, interface, direction):
    """Build a numbered/named ACL from entries and apply it to an interface."""
    cmds = [f"access-list {acl_name} {entry}" for entry in entries]
    cmds.append(f"interface {interface}")
    cmds.append(f"ip access-group {acl_name} {direction}")
    return cmds


def ipsec_commands(pre_shared_key, peer_ip, interface="GigabitEthernet0/0"):
    """Site-to-site IPSec tunnel: ISAKMP policy, transform set, crypto map.

    The pre-shared key authenticates the two peers; peer_ip is the remote
    endpoint the tunnel is built to.
    """
    return [
        "crypto isakmp policy 10",
        "encryption aes",
        "hash sha",
        "authentication pre-share",
        "group 2",
        "exit",
        f"crypto isakmp key {pre_shared_key} address {peer_ip}",
        "crypto ipsec transform-set TRANSFORM_SET esp-aes esp-sha-hmac",
        "exit",
        f"access-list 110 permit ip any host {peer_ip}",
        "crypto map CRYPTO_MAP 10 ipsec-isakmp",
        f"set peer {peer_ip}",
        "set transform-set TRANSFORM_SET",
        "match address 110",
        "exit",
        f"interface {interface}",
        "crypto map CRYPTO_MAP",
        "exit",
    ]


def filter_config(lines, keywords=KEY_SETTINGS):
    """Keep only non-comment lines that mention one of the keywords."""
    out = []
    for line in lines:
        line = line.strip()
        if not line or line.startswith("!"):
            continue
        if any(keyword in line for keyword in keywords):
            out.append(line)
    return out


def compare_hardening(running_config, hardening_guide_path):
    """Unified diff between a hardening guide and the running config.

    Returns a list of diff lines, empty if the checked settings are compliant.
    """
    guide_lines = filter_config(Path(hardening_guide_path).read_text().splitlines())
    running_lines = filter_config(running_config.splitlines())
    return list(
        difflib.unified_diff(
            guide_lines,
            running_lines,
            fromfile="Hardening Guide",
            tofile="Running Config",
            lineterm="",
        )
    )
