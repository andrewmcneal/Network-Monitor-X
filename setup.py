import csv
import os

# Define the location of the script to ensure paths stay relative
SCRIPT_LOCATION = os.path.dirname(os.path.abspath(__file__))

def create_csv_if_missing(filename, headers, default_rows=None):
    """Checks if a CSV exists; if not, creates it with headers and optional defaults."""
    if not os.path.exists(filename):
        with open(filename, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(headers)
            if default_rows:
                for row in default_rows:
                    writer.writerow(row)
        print(f"[Created] {os.path.basename(filename)}")

def setup_wizard():
    print("--- Raspberry Pi Network Monitor Setup Wizard ---")
    
    # 1. Initialize File Paths
    gen_cfg = os.path.join(SCRIPT_LOCATION, 'config.csv')
    tw_cfg = os.path.join(SCRIPT_LOCATION, 'twitter-config.csv')
    hosts_cfg = os.path.join(SCRIPT_LOCATION, 'hosts-config.csv')

    # 2. Ensure Files Exist with Correct Headers
    create_csv_if_missing(gen_cfg, ['Setting', 'Value'], [
        ['BASE_DIR', SCRIPT_LOCATION],
        ['REPORT_TIME', '08:00']
    ])
    
    create_csv_if_missing(tw_cfg, ['Key', 'Value'], [
        ['API_KEY', 'your_key_here'],
        ['API_SECRET', 'your_secret_here'],
        ['ACCESS_TOKEN', 'your_token_here'],
        ['ACCESS_TOKEN_SECRET', 'your_token_secret_here'],
        ['BEARER_TOKEN', 'your_bearer_here'],
        ['X_TAG_ACCOUNTS', '@YourHandle']
    ])
    
    # Defaults include a local Gateway and a Remote host for ISP logic to work
    create_csv_if_missing(hosts_cfg, ['Hostname', 'IP', 'Location', 'Threshold'], [
        ['Gateway', '192.168.1.1', 'Local', '2'],
        ['Google-DNS', '8.8.8.8', 'Remote', '3']
    ])

    print("\nFile structure verified. Moving to configuration...\n")

    # 3. Interactive Configuration for General Settings
    base_dir = input(f"Enter base directory for logs (Default: {SCRIPT_LOCATION}): ") or SCRIPT_LOCATION
    report_time = input("Enter daily report time (24hr format HH:MM, Default: 08:00): ") or "08:00"

    with open(gen_cfg, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['Setting', 'Value'])
        writer.writerow(['BASE_DIR', base_dir])
        writer.writerow(['REPORT_TIME', report_time])

    # 4. Interactive Configuration for X (Twitter) Credentials
    print("\n--- X (Twitter) API Configuration ---")
    print("Leave blank to keep existing values.")
    
    # Read existing values to allow skipping
    current_tw = {}
    with open(tw_cfg, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        next(reader)
        current_tw = {row[0]: row[1] for row in reader}

    tw_keys = ['API_KEY', 'API_SECRET', 'ACCESS_TOKEN', 'ACCESS_TOKEN_SECRET', 'BEARER_TOKEN', 'X_TAG_ACCOUNTS']
    new_tw_vals = []
    for key in tw_keys:
        val = input(f"Enter {key}: ")
        new_tw_vals.append([key, val if val else current_tw.get(key, '')])

    with open(tw_cfg, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['Key', 'Value'])
        writer.writerows(new_tw_vals)

    # 5. Host Management
    print("\n--- Host Management ---")
    add_host = input("Would you like to add a new host to monitor? (y/n): ").lower()
    if add_host == 'y':
        h_name = input("Enter Hostname: ")
        h_ip = input("Enter IP: ")
        h_loc = input("Location (Local/Remote): ")
        h_thresh = input("Failure Threshold (Default 3): ") or "3"
        
        with open(hosts_cfg, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([h_name, h_ip, h_loc, h_thresh])

    print("\nSetup Complete! You can now run 'python3 monitor.py'.")

if __name__ == "__main__":
    setup_wizard()
