"""
Network Monitor with X (Twitter) Alerts
Created for: Raspberry Pi
Written by  Andrew McNeal
Function: Pings multiple hosts, logs results, and alerts via X when thresholds are met.
"""

import csv
import os
import platform
import subprocess
from datetime import datetime, timedelta
import tweepy

# === 1. INITIAL BOOTSTRAP & PATHING ===
# We determine the script's physical location to ensure it finds the config 
# file regardless of where the script is called from (e.g., Cron).
SCRIPT_LOCATION = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE_PATH = os.path.join(SCRIPT_LOCATION, 'config.csv')

def load_csv_to_dict(filename):
    """
    Reads a two-column CSV and converts it into a dictionary for quick lookup.
    Example: row['IP1'] -> '8.8.8.8'
    """
    data = {}
    if not os.path.exists(filename):
        return data
    with open(filename, 'r') as f:
        reader = csv.reader(f)
        try:
            next(reader) # Skip the header row
            for row in reader:
                if len(row) >= 2:
                    data[row[0]] = row[1]
        except StopIteration:
            pass
    return data

def initialize_workspace():
    """
    Sets up the environment on the first run. 
    Creates default config, status files, and the log directory.
    """
    # Create default configuration if none exists
    if not os.path.exists(CONFIG_FILE_PATH):
        defaults = [
            ['Field Name', 'Value'],
            ['BASE_DIR', SCRIPT_LOCATION], # Default to script folder
            ['X_TAG_ACCOUNTS', ''],        # Empty by default to protect privacy
            ['IP1', '8.8.8.8'], ['Hostname1', 'Google'], ['Threshold1', '3'],
            ['IP2', '1.1.1.1'], ['Hostname2', 'Cloudflare'], ['Threshold2', '3'],
            ['IP3', '192.168.1.1'], ['Hostname3', 'Gateway'], ['Threshold3', '1'],
            ['IP4', '9.9.9.9'], ['Hostname4', 'Quad9'], ['Threshold4', '5'],
            ['API_KEY', 'REQUIRED'], ['API_SECRET', 'REQUIRED'],
            ['ACCESS_TOKEN', 'REQUIRED'], ['ACCESS_TOKEN_SECRET', 'REQUIRED'],
            ['BEARER_TOKEN', 'REQUIRED']
        ]
        with open(CONFIG_FILE_PATH, 'w', newline='') as f:
            csv.writer(f).writerows(defaults)

    # Resolve the working directory from the config
    cfg = load_csv_to_dict(CONFIG_FILE_PATH)
    base = cfg.get('BASE_DIR', SCRIPT_LOCATION)
    
    # Ensure the folder for raw text logs exists
    log_dir = os.path.join(base, 'Host-Logs')
    if not os.path.exists(log_dir):
        os.makedirs(log_dir, exist_ok=True)

    # Initialize the status tracker if it's missing
    status_path = os.path.join(base, 'status.csv')
    if not os.path.exists(status_path):
        with open(status_path, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['Field Name', 'Value'])
            for i in range(1, 5):
                writer.writerow([f'Status{i}', 'Up'])
                writer.writerow([f'FailCount{i}', '0'])
                writer.writerow([f'DateTime{i}', datetime.now().strftime("%m%d%Y-%H%M")])

def log_error(message, base_dir):
    """Appends unexpected errors to a yearly log file for debugging."""
    error_log = os.path.join(base_dir, f"Errors-{datetime.now().year}.log")
    with open(error_log, "a") as f:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        f.write(f"{timestamp}: {message}\n")

def get_x_client(cfg):
    """Authenticates with X using credentials provided in config.csv."""
    return tweepy.Client(
        bearer_token=cfg.get('BEARER_TOKEN'),
        consumer_key=cfg.get('API_KEY'),
        consumer_secret=cfg.get('API_SECRET'),
        access_token=cfg.get('ACCESS_TOKEN'),
        access_token_secret=cfg.get('ACCESS_TOKEN_SECRET')
    )

def post_daily_stats(cfg, base_dir, log_dir):
    """
    Summarizes the previous day's uptime/downtime.
    Uses a marker file to ensure it only posts once per day.
    """
    yesterday = (datetime.now() - timedelta(days=1))
    date_str = yesterday.strftime("%m%d%Y")
    marker_file = os.path.join(base_dir, f".stats_sent_{date_str}")
    
    # Exit if we already sent today's report
    if os.path.exists(marker_file):
        return

    tags = cfg.get('X_TAG_ACCOUNTS', '')
    stats_msg = f"Daily Network Report {tags}\nDate: {yesterday.strftime('%m/%d/%Y')}\n"
    
    for i in range(1, 5):
        host = cfg.get(f'Hostname{i}', f'Host{i}')
        log_file = os.path.join(log_dir, f"{host}-{date_str}.txt")
        down_minutes = 0
        if os.path.exists(log_file):
            with open(log_file, 'r') as f:
                # Count lines containing ": Down" as one minute of downtime
                down_minutes = sum(1 for line in f if ": Down" in line)
        stats_msg += f"• {host}: {down_minutes}m down\n"

    try:
        get_x_client(cfg).create_tweet(text=stats_msg[:280])
        with open(marker_file, "w") as f:
            f.write(f"Sent at {datetime.now()}")
    except Exception as e:
        log_error(f"Daily Report Tweet Failed: {e}", base_dir)

def main():
    # Setup environment
    initialize_workspace()

    # Load validated settings and paths
    config = load_csv_to_dict(CONFIG_FILE_PATH)
    base = config.get('BASE_DIR', SCRIPT_LOCATION)
    status_path = os.path.join(base, 'status.csv')
    log_dir = os.path.join(base, 'Host-Logs')

    try:
        status_vals = load_csv_to_dict(status_path)
        now = datetime.now()
        date_str = now.strftime("%m%d%Y")
        timestamp = f"{date_str}-{now.strftime('%H%M')}"
        
        # Attempt to post daily summary (Midnight Logic)
        post_daily_stats(config, base, log_dir)

        outage_updates = []
        tags = config.get('X_TAG_ACCOUNTS', '')

        # Loop through the 4 host slots
        for i in range(1, 5):
            ip = config.get(f'IP{i}')
            host = config.get(f'Hostname{i}')
            threshold = int(config.get(f'Threshold{i}', 2))
            if not ip: continue

            # Previous known state
            old_status = status_vals.get(f'Status{i}', 'Up')
            old_time = status_vals.get(f'DateTime{i}', '0')
            fail_count = int(status_vals.get(f'FailCount{i}', '0'))

            # Execute system ping command (-c 1 for Linux, -n 1 for Windows)
            param = '-n' if platform.system().lower() == 'windows' else '-c'
            is_up = subprocess.call(['ping', param, '1', '-W', '1', ip], 
                                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) == 0
            
            result = "Up" if is_up else "Down"

            # Always log the raw result to the Host-Logs folder
            log_path = os.path.join(log_dir, f"{host}-{date_str}.txt")
            with open(log_path, "a") as hf:
                hf.write(f"{timestamp}: {ip}: {result}\n")

            # Logic for host failing
            if result == "Down":
                fail_count += 1
                if fail_count == 1:
                    status_vals[f'DateTime{i}'] = timestamp # Mark original fail time
                
                # Check if threshold is reached to trigger an alert
                if fail_count == threshold and old_status == "Up":
                    status_vals[f'Status{i}'] = "Down"
                    outage_updates.append(f"Alert: {host} DOWN at {status_vals[f'DateTime{i}']}")
            
            # Logic for host returning to service
            else:
                if old_status == "Down":
                    outage_updates.append(f"Recovery: {host} UP. Outage: {old_time} to {timestamp}")
                
                status_vals[f'Status{i}'] = "Up"
                status_vals[f'FailCount{i}'] = "0"
                status_vals[f'DateTime{i}'] = timestamp # Use as heartbeat

            status_vals[f'FailCount{i}'] = str(fail_count)

        # Send any collected alerts or recoveries to X
        if outage_updates:
            msg = f"Network Update {tags}:\n" + "\n".join(outage_updates)
            try:
                get_x_client(config).create_tweet(text=msg[:280])
            except Exception as e:
                log_error(f"Alert Tweet Failed: {e}", base)

        # Persist the current state to status.csv for the next run
        with open(status_path, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['Field Name', 'Value'])
            for key, val in status_vals.items():
                writer.writerow([key, val])

    except Exception as e:
        log_error(f"Global Script Error: {e}", base)

if __name__ == "__main__":
    main()
