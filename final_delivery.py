from netmiko import ConnectHandler
import datetime
import difflib

# Defining the settings to check 
KEY_SETTINGS = [
    "exec-timeout",           
    "aaa authentication",      
    "service password-encryption", 
    "no service",              
    "logging host",            
    "banner login"             
]

def welcome_message():
    message = "WELCOME TO THE ROUTER CONFIG SCRIPT"
    border = "*" * (len(message) + 6)
    print(f"\n{border}")
    print(f"** {message} **")
    print(f"{border}\n")


welcome_message()
#user input
ip = input("Enter the device IP address: ")
syslog_server_ip = input("Enter the Syslog server IP address: ")
transport = input("Choose connection method (telnet/ssh): ").strip().lower()

# Get current timestamp & Create a log
timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
log_filename = f"session_log_{transport}_{ip}_{timestamp}.txt"
log_file = open(log_filename, "w")

# Device config
device_params = {
    'host': ip,
    'username': "cisco",
    'password': "cisco123!",
    'secret': " ",
    'device_type': 'cisco_ios_telnet' if transport == 'telnet' else 'cisco_ios',
    'port': 23 if transport == 'telnet' else 22,
}

def load_and_filter_config(file_path, keywords):
    """Load config file and filter lines containing specified keywords."""
    with open(file_path, 'r') as file:
        lines = file.readlines()

    filtered_lines = []
    for line in lines:
        line = line.strip()
        if not line or line.startswith("!"):
            continue
        if any(keyword in line for keyword in keywords):
            filtered_lines.append(line)
    
    return filtered_lines

hardening_guide_path = 'C:\\Users\\tic\\Desktop\\Hardening-guide.txt' 
hardening_guide_filtered = load_and_filter_config(hardening_guide_path, KEY_SETTINGS)

try:
    # Establish connection and Enter enable mode
    print(f"Connecting to {ip} via {transport.upper()}...")
    log_file.write(f"Connecting to {ip} via {transport.upper()}...\n")
    net_connect = ConnectHandler(**device_params)
    net_connect.enable()
    log_file.write("Entered enable mode.\n")

    # Change hostname
    new_hostname = f"Cisco_{transport.upper()}"
    config_commands = [f'hostname {new_hostname}']
    log_file.write(f"Sending config commands: {config_commands}\n")
    output = net_connect.send_config_set(config_commands)
    log_file.write(f"Output: {output}\n")

    # Print success message
    print(f"{transport.upper()}: Hostname successfully changed to '{new_hostname}'.")

    running_config = net_connect.send_command("show running-config")
    running_config_lines = running_config.splitlines()
    running_config_filtered = [line for line in running_config_lines if any(keyword in line for keyword in KEY_SETTINGS)]
    
    print("Comparing specified hardening settings in running config with hardening guide...")
    diff = list(difflib.unified_diff(
        hardening_guide_filtered,
        running_config_filtered,
        fromfile='Hardening Guide',
        tofile='Running Config',
        lineterm=""
    ))

    differences_filename = f"differences_filtered-{transport}-{timestamp}.txt"
    with open(differences_filename, "w") as diff_file:
        diff_file.write("\n".join(diff))

    with open(differences_filename, "r") as diff_file:
        diff_content = diff_file.read()

    if diff_content:
        print("Differences found! Adjust configurations to match hardening guide...")
        log_file.write("Differences found! Adjust configurations to match hardening guide...:\n")
    else:
        print("No differences found. The specified settings in running configuration are compliant with the hardening guide.")
        log_file.write("No differences found. The specified settings in running configuration are compliant with the hardening guide.\n")
    
    #Enter config mode before commands
    net_connect.config_mode()

    syslog_commands = [
        f'logging host {syslog_server_ip}',
        'logging trap informational',
        'service timestamps log datetime msec',
        'logging on'
    ]
    print("Configuring Syslog for event logging and monitoring...")
    log_file.write("Sending Syslog configuration commands:\n")
    output = net_connect.send_config_set(syslog_commands)
    log_file.write(output + "\n")
    print("Syslog configuration applied.")

    #Enter config mode before commands
    net_connect.config_mode()
    # Configure (ACLs)
    acl_name = input("Enter ACL name (e.g., 101): ")
    acl_commands = []

    print("Configure ACL entries (type 'done' to finish):")
    while True:
        entry = input("Enter ACL entry (e.g., 'permit tcp any any eq 80'): ")
        if entry.lower() == 'done':
            break
        acl_commands.append(f"access-list {acl_name} {entry}")

    interface = input("Enter the interface to apply the ACL (e.g., 'GigabitEthernet1'): ")
    direction = input("Enter direction (in/out): ")

    acl_commands.append(f"interface {interface}")
    acl_commands.append(f"ip access-group {acl_name} {direction}")

    print("Applying ACL configuration...")
    acl_output = net_connect.send_config_set(acl_commands)
    log_file.write(f"ACL configuration:\n{acl_output}\n")
    print("ACL configuration applied.")

#check if in config mode before commands
    if not net_connect.check_config_mode():
        net_connect.config_mode

    # IPSec
    pre_shared_key = input("Enter pre-shared key for IPSec: ") # used to authenticate and establish trust between two IPSec peers
    peer_ip = input("Enter peer IP address for IPSec: ") # This IP identifies the (peer) with which the IPSec tunnel will be established.

# exit command back to config to continue with the commands
    ipsec_commands = [
        "crypto isakmp policy 10",
        "encryption aes",
        "hash sha",
        "authentication pre-share",
        "group 2",
        "exit",
        f"crypto isakmp key {pre_shared_key} address {peer_ip}",
        "crypto ipsec transform-set TRANSFORM_SET esp-aes esp-sha-hmac",
        "exit"
        f"access-list 110 permit ip any host {peer_ip}",
        "crypto map CRYPTO_MAP 10 ipsec-isakmp",
        f"set peer {peer_ip}",
        "set transform-set TRANSFORM_SET",
        "match address 110",
        "exit"
        "interface GigabitEthernet0/0",
        "crypto map CRYPTO_MAP"
        "exit"
    ]

    print("Applying IPSec configuration...")
    ipsec_output = net_connect.send_config_set(ipsec_commands, read_timeout=10)
    log_file.write(f"IPSec configuration:\n{ipsec_output}\n")
    print("IPSec configuration applied.")
    
    # Save running config
    running_config = net_connect.send_command("show running-config")
    running_config_filename = f"running-config-{transport}-{timestamp}.txt"
    with open(running_config_filename, "w") as file:
        file.write(running_config)
    print(f"Running config saved to '{running_config_filename}'.")

    # Retrieve and display the router's routing table and log it
    routing_table = net_connect.send_command("show ip route")
    routing_table_filename = f"routing-table-{transport}-{timestamp}.txt"
    with open(routing_table_filename, "w") as file:
        file.write(routing_table)
    print(f"Routing table saved to '{routing_table_filename}'.")

    # Log the output of the routing table
    log_file.write(f"Routing Table Output:\n{routing_table}\n")

    # Close router connection and log it
    net_connect.disconnect()
    log_file.write(f"Disconnected from {ip}.\n")

except Exception as e:
    print(f"An error occurred: {e}")
    log_file.write(f"An error occurred: {e}\n")

finally:
    # Close the log file
    log_file.close()
    print(f"Session log saved to '{log_filename}'")
