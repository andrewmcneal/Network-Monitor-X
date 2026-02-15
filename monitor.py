import csv
import os
import platform
import subprocess
from datetime import datetime, timedelta
import tweepy
from concurrent.futures import ThreadPoolExecutor

# ==========================================
# 1. CORE CONFIGURATION & PATHING
# ==========================================

# Locate the directory where the script is stored
SCRIPT_LOCATION = os.path.dirname(os.path.abspath(__file__))
GENERAL_CONFIG = os.path.join(SCRIPT_LOCATION, 'config.csv')
TWITTER_CONFIG = os.path.join(SCRIPT_LOCATION, 'twitter-config.csv')
HOSTS_CONFIG = os.path.join(SCRIPT_LOCATION, 'hosts-config.csv')

def load_generic_csv(filename):
    """Loads a 2-column CSV into a dictionary for quick lookups."""
    data = {}
    if not os.path.exists(filename): return data
    with open(filename, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        next(reader, None)  # Skip header
        for row in reader:
            if len(row) >= 2: data[row[0]] = row[1]
    return data

def load_hosts():
    """Loads all monitoring targets from the hosts configuration file."""
    if not os.path.exists(HOSTS_CONFIG): return []
    with open(HOSTS_CONFIG, 'r', encoding='utf-8') as f:
        return list(csv.DictReader(f))

# ==========================================
# 2. PING & DURATION UTILITIES
# ==========================================

def ping_individual_host(host_data):
    """Performs a system ping. Returns (Hostname, Status)."""
    name, ip = host_data['Hostname'], host_data['IP']
    # Select correct ping parameter based on Operating System
    param = '-n' if platform.system().lower() == 'windows' else '-c'
    try:
        # Timeout set to 2 seconds (-W 2) with 1 packet count (-c/n 1)
        is_up = subprocess.call(['ping', param, '1', '-W', '2', ip], 
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) == 0
    except: 
        is_up = False
    return name, "Up" if is_up else "Down"

def get_duration(start_str, end_dt):
    """Calculates minutes elapsed between a timestamp string and a datetime object."""
    try:
        start_dt = datetime.strptime(start_str, "%m%d%Y-%H%M")
        diff = end_dt - start_dt
        return int(diff.total_seconds() // 60)
    except: 
        return 0

# ==========================================
# 3. MAIN MONITORING ENGINE
# ==========================================

def main():
    # Load settings and host list
    gen_cfg = load_generic_csv(GENERAL_CONFIG)
    tw_cfg = load_generic_csv(TWITTER_CONFIG)
    hosts = load_hosts()
    
    # Resolve working directories
    base = os.path.expanduser(gen_cfg.get('BASE_DIR', SCRIPT_LOCATION))
    status_path = os.path.join(base, 'status.csv')
    log_dir = os.path.join(base, 'Host-Logs')
    os.makedirs(log_dir, exist_ok=True)
    
    # Load current state and current time
    status_vals = load_generic_csv(status_path)
    now = datetime.now()
    today_str = now.strftime("%m%d%Y")
    timestamp = now.strftime("%m%d%Y-%H%M")
    
    # Error logs live in the root folder as Errors-YYYY.txt
    error_file = os.path.join(base, f"Errors-{now.strftime('%Y')}.txt")
    
    # ------------------------------------------
    # A. DAILY SUMMARY GENERATION
    # ------------------------------------------
    report_time_cfg = gen_cfg.get('REPORT_TIME', '00:00')
    current_time_str = now.strftime("%H:%M")
    last_report_date = status_vals.get('LastDailyReportDate', '')

    daily_report_msg = ""
    # Trigger report if current time is past scheduled time and not sent today
    if last_report_date != today_str and current_time_str >= report_time_cfg:
        daily_report_msg = f"📊 Daily Network Summary ({now.strftime('%m/%d/%Y')})\n"
        isp_count = int(status_vals.get('DailyISPOutages', '0'))
        for h in hosts:
            name = h['Hostname']
            mins = status_vals.get(f'DailyDowntime_{name}', '0')
            daily_report_msg += f"• {name}: {mins}m down\n"
        if isp_count > 0: 
            daily_report_msg += f"• ISP Outages: {isp_count}"
        
        # Reset daily counters in state
        status_vals['LastDailyReportDate'] = today_str
        status_vals['DailyISPOutages'] = '0'
        for h in hosts: 
            status_vals[f'DailyDowntime_{h["Hostname"]}'] = '0'

    # ------------------------------------------
    # B. PARALLEL PING EXECUTION
    # ------------------------------------------
    with ThreadPoolExecutor(max_workers=len(hosts) if hosts else 5) as executor:
        current_results = dict(list(executor.map(ping_individual_host, hosts)))

    # ------------------------------------------
    # C. ISP OUTAGE LOGIC
    # ------------------------------------------
    remote_hosts = [h for h in hosts if h.get('Location') == 'Remote']
    remotes_all_down = all(current_results[h['Hostname']] == "Down" for h in remote_hosts)
    gateway_up = current_results.get('Gateway') == "Up"
    
    # Detect ISP failure: Local Gateway is UP but ALL Remote hosts are DOWN
    isp_active = gateway_up and len(remote_hosts) > 0 and remotes_all_down
    was_isp_active = status_vals.get('ISP_Outage_Active', 'False') == 'True'
    
    outage_updates = []

    # ------------------------------------------
    # D. DATA PROCESSING & LOGGING
    # ------------------------------------------
    for h in hosts:
        name = h['Hostname']
        res = current_results[name]
        old_status = status_vals.get(f'Status_{name}', 'Up')
        old_time = status_vals.get(f'Time_{name}', timestamp)
        fail_count = int(status_vals.get(f'Fail_{name}', '0'))
        threshold = int(h.get('Threshold', 3))

        # Write result to daily host-specific log
        with open(os.path.join(log_dir, f"{name}-{now.strftime('%m%d%Y')}.txt"), "a") as f:
            f.write(f"{timestamp}: {res}\n")

        if res == "Down":
            fail_count += 1
            if fail_count == 1: status_vals[f'Time_{name}'] = timestamp
            # Update state to 'Down' only after threshold is crossed
            if fail_count >= threshold: status_vals[f'Status_{name}'] = "Down"
        else:
            # Check if host just recovered from a 'Down' state
            if old_status == "Down":
                duration_mins = get_duration(old_time, now)
                key = f'DailyDowntime_{name}'
                status_vals[key] = str(int(status_vals.get(key, '0')) + duration_mins)
                
                # Suppress individual tweets during a general ISP outage
                if not was_isp_active or h.get('Location') != 'Remote':
                    outage_updates.append(f"✅ {name} Restored. Down: {duration_mins}m")

            status_vals[f'Status_{name}'] = "Up"
            status_vals[f'Fail_{name}'] = "0"
        
        status_vals[f'Fail_{name}'] = str(fail_count)

    # ISP Event Transitions
    if was_isp_active and not isp_active and gateway_up:
        isp_dur = get_duration(status_vals.get('ISP_Start_Time', timestamp), now)
        outage_updates.append(f"🚨 ISP Outage Resolved\nDuration: {isp_dur}m")
        status_vals['DailyISPOutages'] = str(int(status_vals.get('DailyISPOutages', '0')) + 1)
        status_vals['ISP_Outage_Active'] = 'False'

    if isp_active and not was_isp_active:
        status_vals['ISP_Outage_Active'] = 'True'
        status_vals['ISP_Start_Time'] = timestamp

    # ------------------------------------------
    # E. ALERTS & STATE PERSISTENCE
    # ------------------------------------------
    if daily_report_msg or outage_updates:
        try:
            tags = tw_cfg.get('X_TAG_ACCOUNTS', '')
            client = tweepy.Client(
                bearer_token=tw_cfg.get('BEARER_TOKEN'),
                consumer_key=tw_cfg.get('API_KEY'),
                consumer_secret=tw_cfg.get('API_SECRET'),
                access_token=tw_cfg.get('ACCESS_TOKEN'),
                access_token_secret=tw_cfg.get('ACCESS_TOKEN_SECRET')
            )
            # Post summary or individual alerts
            if daily_report_msg: client.create_tweet(text=f"{daily_report_msg}\n{tags}"[:280])
            for msg in outage_updates: client.create_tweet(text=f"{msg}\n{tags}"[:280])
        except Exception as e:
            # Log failures to root yearly error log
            with open(error_file, "a", encoding='utf-8') as f:
                f.write(f"{now}: Tweet Fail: {e}\n")

    # Finalize state by writing back to status.csv
    with open(status_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['Field Name', 'Value'])
        for k, v in status_vals.items(): writer.writerow([k, v])

if __name__ == "__main__":
    main()
