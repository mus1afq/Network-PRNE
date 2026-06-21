# Network-PRNE

Automating Cisco IOS device configuration with Python and Netmiko, over SSH or
Telnet. Built for the Programming for Network Engineers module and tidied up for
portfolio use.

## What it does

- Connects to an IOS device, sets the hostname, and saves the running config.
- Compares the running config against a hardening guide and writes a diff of the
  settings that drift from the baseline.
- Configures syslog, an ACL, and a site-to-site IPSec tunnel.
- Available as an interactive CLI and a small Flask web UI.

## Layout

| File | Purpose |
| --- | --- |
| `tasks.py` | Shared command builders and the hardening diff. One source of truth for both front ends. |
| `cli.py` | Interactive command-line tool. |
| `app.py` | Flask web UI. |
| `templates/index.html` | Form for the web UI. |
| `hardening-guide.txt` | Sample baseline for the compliance diff. |

## Setup

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env             # then fill in credentials
```

Credentials are read from environment variables, never hardcoded:
`DEVICE_USERNAME`, `DEVICE_PASSWORD`, `DEVICE_SECRET` (optional).

## Usage

CLI:

```bash
export DEVICE_USERNAME=admin
export DEVICE_PASSWORD=...        # or let the script prompt
python cli.py --ip 10.10.20.48 --transport ssh --syslog-server 10.10.20.5
```

Anything not passed as a flag is prompted for. Logs and config dumps are written
to `output/` (gitignored).

Web UI:

```bash
export FLASK_SECRET_KEY=$(python -c "import secrets; print(secrets.token_hex())")
python app.py                    # http://127.0.0.1:5000
```

`debug` stays off unless you set `FLASK_DEBUG=1`.

## Testing without hardware

No lab required. Cisco's DevNet Always-On Sandbox gives a real IOS XE device
reachable over the internet, no reservation or VPN:

- Host: `sandbox-iosxe-latest-1.cisco.com`
- Username: `admin`, password: `C1sco12345`
- `device_type`: `cisco_xe`

It is shared, so keep changes small and non-disruptive: edit interface
descriptions, do not shut interfaces, change IPs, or touch the management
interface or AAA. For destructive testing, reserve the "IOS XE on Cat 8K" lab
for an isolated box.

To lab locally on Apple Silicon, run GNS3 inside an OrbStack x86 Linux machine
and use IOSv or IOL images (ASAv, Catalyst 8000V and Nexus 9000v do not run on
Apple Silicon).

## Roadmap

- Natural-language front end: a network engineer types intent in plain English,
  reviews generated Cisco commands, then approves deployment.
- Add dry-run previews for the CLI and web UI before sending changes.
- Add unit tests around command builders and hardening comparisons.

