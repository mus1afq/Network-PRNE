"""Flask web UI for the PRNE network configuration tasks.

Pulls the device details from a form and applies hostname, syslog and IPSec
configuration via Netmiko. The command definitions live in tasks.py so the
CLI and the web UI stay in sync.
"""
from __future__ import annotations

import datetime as dt
import os
from pathlib import Path

from flask import Flask, flash, redirect, render_template, request, url_for
from netmiko import ConnectHandler

import tasks

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "dev-only-change-me")

OUTPUT_DIR = Path("output")


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/configure", methods=["POST"])
def configure():
    form = request.form
    transport = form.get("transport", "ssh")
    ip = form["ip"]

    device = tasks.build_device_params(
        host=ip,
        username=form["username"],
        password=form["password"],
        transport=transport,
        secret=form.get("secret", ""),
    )

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    stem = f"{transport}_{ip}_{timestamp}"

    try:
        with ConnectHandler(**device) as conn:
            conn.enable()
            conn.send_config_set(tasks.hostname_commands(transport))
            conn.send_config_set(tasks.syslog_commands(form["syslog_server_ip"]))
            conn.send_config_set(
                tasks.ipsec_commands(form["pre_shared_key"], form["peer_ip"])
            )
            running = conn.send_command("show running-config")
            (OUTPUT_DIR / f"running-config_{stem}.txt").write_text(running)
            conn.send_command("write memory")

        flash("Configuration applied successfully.", "success")
    except Exception as exc:  # noqa: BLE001
        flash(f"An error occurred: {exc}", "danger")

    return redirect(url_for("index"))


if __name__ == "__main__":
    # Debug stays off unless explicitly enabled: FLASK_DEBUG=1 python app.py
    app.run(debug=os.getenv("FLASK_DEBUG") == "1")
