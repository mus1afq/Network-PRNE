from flask import Flask, render_template, request, redirect, url_for, flash
import datetime
from netmiko import ConnectHandler

app = Flask(__name__)
app.secret_key = "your_secret_key"

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/configure', methods=['POST'])
def configure():
    try:
        ip = request.form['ip']
        syslog_server_ip = request.form['syslog_server_ip']
        transport = request.form['transport']
        pre_shared_key = request.form['pre_shared_key']
        peer_ip = request.form['peer_ip']
        username = request.form['username']
        password = request.form['password']

        # Log file setup TODO: write to file
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        log_filename = f"session_log_{transport}_{ip}_{timestamp}.txt"

        device_params = {
            'host': ip,
            'username': username,
            'password': password,
            'secret': " ",
            'device_type': 'cisco_ios_telnet' if transport == 'telnet' else 'cisco_ios',
            'port': 23 if transport == 'telnet' else 22,
        }

        net_connect = ConnectHandler(**device_params)
        net_connect.enable()

        new_hostname = f"Cisco_{transport.upper()}"
        config_commands = [f'hostname {new_hostname}']
        net_connect.send_config_set(config_commands)

        syslog_commands = [
            f'logging host {syslog_server_ip}',
            'logging trap informational',
            'service timestamps log datetime msec',
            'logging on'
        ]
        net_connect.send_config_set(syslog_commands)

        ipsec_commands = [
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
            "interface GigabitEthernet0/0",
            "crypto map CRYPTO_MAP",
            "exit"
        ]
        net_connect.send_config_set(ipsec_commands)

        # Save the running configuration
        running_config = net_connect.send_command("show running-config")
        running_config_filename = f"running-config-{transport}-{timestamp}.txt"
        with open(running_config_filename, "w") as file:
            file.write(running_config)

        net_connect.disconnect()

        flash("Configuration applied successfully!", "success")
    except Exception as e:
        flash(f"An error occurred: {e}", "danger")

    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)
