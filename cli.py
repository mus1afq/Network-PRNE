"""Interactive CLI to configure a Cisco IOS device over SSH or Telnet.

Covers the PRNE deliverables:
  1. Connect, change hostname, save running config.
  2. Compare the running config against a hardening guide (selected settings).
  3. Configure syslog, an ACL, and a site-to-site IPSec tunnel.

Credentials are read from environment variables, with a prompt fallback:
  DEVICE_USERNAME, DEVICE_PASSWORD, DEVICE_SECRET (optional)

Example:
  python cli.py --ip 10.10.20.48 --transport ssh --syslog-server 10.10.20.5
"""
from __future__ import annotations

import argparse
import datetime as dt
import getpass
import logging
import os
from pathlib import Path

from netmiko import ConnectHandler

import tasks


def get_credentials():
    """Prefer env vars, fall back to an interactive prompt."""
    username = os.getenv("DEVICE_USERNAME") or input("Username: ")
    password = os.getenv("DEVICE_PASSWORD") or getpass.getpass("Password: ")
    secret = os.getenv("DEVICE_SECRET", "")
    return username, password, secret


def setup_logging(log_path):
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[logging.FileHandler(log_path), logging.StreamHandler()],
    )


def collect_acl_entries():
    entries = []
    print("Configure ACL entries (type 'done' to finish):")
    while True:
        entry = input("ACL entry (e.g. 'permit tcp any any eq 80'): ").strip()
        if entry.lower() == "done":
            break
        if entry:
            entries.append(entry)
    return entries


def parse_args():
    parser = argparse.ArgumentParser(description="Configure a Cisco IOS device.")
    parser.add_argument("--ip", help="device management IP")
    parser.add_argument("--transport", choices=["ssh", "telnet"], default="ssh")
    parser.add_argument("--syslog-server", help="syslog collector IP")
    parser.add_argument(
        "--hardening-guide",
        default="hardening-guide.txt",
        help="path to the hardening guide used for the compliance diff",
    )
    parser.add_argument(
        "--out-dir", default="output", help="directory for logs and config dumps"
    )
    return parser.parse_args()


def main():
    args = parse_args()

    ip = args.ip or input("Device IP address: ")
    transport = args.transport
    syslog_server_ip = args.syslog_server or input("Syslog server IP: ")

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    timestamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    stem = f"{transport}_{ip}_{timestamp}"
    setup_logging(out_dir / f"session_{stem}.log")

    username, password, secret = get_credentials()
    device = tasks.build_device_params(ip, username, password, transport, secret)

    try:
        logging.info("Connecting to %s via %s", ip, transport.upper())
        with ConnectHandler(**device) as conn:
            conn.enable()

            logging.info("Setting hostname")
            conn.send_config_set(tasks.hostname_commands(transport))

            running = conn.send_command("show running-config")
            guide = Path(args.hardening_guide)
            if guide.exists():
                diff = tasks.compare_hardening(running, guide)
                diff_path = out_dir / f"hardening_diff_{stem}.txt"
                diff_path.write_text("\n".join(diff))
                if diff:
                    logging.info("Hardening differences found, see %s", diff_path)
                else:
                    logging.info("Checked settings are compliant with the guide")
            else:
                logging.warning("Hardening guide %s not found, skipping diff", guide)

            logging.info("Configuring syslog")
            conn.send_config_set(tasks.syslog_commands(syslog_server_ip))

            acl_name = input("ACL name (e.g. 101): ").strip()
            entries = collect_acl_entries()
            interface = input("Interface for the ACL (e.g. GigabitEthernet1): ").strip()
            direction = input("Direction (in/out): ").strip().lower()
            logging.info("Applying ACL %s", acl_name)
            conn.send_config_set(
                tasks.acl_commands(acl_name, entries, interface, direction)
            )

            psk = getpass.getpass("IPSec pre-shared key: ")
            peer_ip = input("IPSec peer IP: ").strip()
            logging.info("Applying IPSec configuration")
            conn.send_config_set(tasks.ipsec_commands(psk, peer_ip), read_timeout=10)

            running = conn.send_command("show running-config")
            (out_dir / f"running-config_{stem}.txt").write_text(running)
            routing = conn.send_command("show ip route")
            (out_dir / f"routing-table_{stem}.txt").write_text(routing)
            conn.send_command("write memory")
            logging.info("Saved running config and routing table to %s", out_dir)

    except Exception as exc:  # noqa: BLE001 - top-level guard for a CLI tool
        logging.error("An error occurred: %s", exc)


if __name__ == "__main__":
    main()
