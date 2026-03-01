import csv
import os
import platform
import subprocess
from datetime import datetime
import tweepy
from concurrent.futures import ThreadPoolExecutor

# ==============================================================================
# 1. PATHS AND CONFIGURATION
# ==============================================================================
# We define paths relative to where the script is located to avoid file-not-found errors.
SCRIPT_LOCATION = os.path.dirname(os.path.abspath(__file__))
GENERAL_CONFIG = os.path.join(SCRIPT_LOCATION, 'config.csv')
TWITTER_CONFIG = os.path.join(SCRIPT_LOCATION, 'twitter-config.csv')
HOSTS_CONFIG = os.path.join(SCRIPT_LOCATION, 'hosts-config.csv')

def load_generic_csv(filename):
    """Utility to turn a 2-column CSV into a Python Dictionary."""
    data = {}
    if not os.path.exists(filename): return data
    with open(filename, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        next(reader, None)  # Skip header
        for row in reader:
            if len(row) >= 2: data[row[0]] = row[1]
    return data

def load_hosts():
    """Utility to load the target hosts to be monitored."""
    if not os.path.exists(HOSTS_CONFIG): return []
    with open(HOSTS_CONFIG, 'r', encoding='utf-8') as f:
        return list(csv.DictReader(f))

# ==============================================================================
# 2. NETWORK & MATH TOOLS
# ==============================================================================

def ping_individual_host(host_data):
    """
    Executes a single ping. 
    Uses -W 5 (5s timeout) to prevent external hosts (Quad9) from 
    timing out prematurely during network jitter.
    """
    name, ip = host_data['Hostname'], host_data['IP']
    param = '-n' if platform.system().lower() == 'windows' else '-c'
    try:
        # Pinging 1 time with a 5-second timeout
        is_up = subprocess.call(['ping', param, '1', '-W', '5', ip], 
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) == 0
    except: 
        is_up = False
    return name, "Up" if is_up else "Down"

def get_duration(start_str, end_dt):
    """
    Calculates minutes between a timestamp string and now.
    Includes a 'Safety Valve' to cap results at 1440m (1 day).
    """
    try:
        start_dt = datetime.strptime(start_str, "%m%d%Y-%H%M")
        diff = end_dt - start_dt
        minutes = int(diff.total_seconds() // 60)
        
        # If the result is impossible (negative or over 1 day), return 1m
        if minutes > 1440 or minutes < 0:
            return 1 
        return minutes
    except: 
        return 0

# ==============================================================================
# 3. MAIN LOGIC
# ==============================================================================

def main():
    # Load all configs
    gen_cfg = load_generic_csv(GENERAL_CONFIG)
    tw_cfg = load_generic_csv(TWITTER_CONFIG)
    hosts = load_hosts()
    
    # Setup directories
    base = os.path.expanduser(gen_cfg.get('BASE_DIR', SCRIPT_LOCATION))
    status_path = os.path.join(base, 'status.csv')
    log_dir = os.path.join(base, 'Host-Logs')
    os.makedirs(log_dir, exist_ok=True)
    
    # Load state from status.csv
    status_vals = load_generic_csv(status_path)
    now = datetime.now()
    today_str = now.strftime("%m%d%Y")
    timestamp = now.strftime("%m%d%Y-%H%M")
    error_file = os.path.join(base, f"Errors-{now.strftime('%Y')}.txt")
    
    # --- PHASE A: MULTI-THREADED PINGING ---
    # We ping everything at once so the script finishes in seconds, not minutes.
    with ThreadPoolExecutor(max_workers=len(hosts) if hosts else 5) as executor:
        current_results = dict(list(executor.map(ping_individual_host, hosts)))

    # --- PHASE B: ISP LEVEL DETECTION ---
    # If all 'Remote' hosts are down but Gateway is Up, the ISP is the problem.
    remote_hosts = [h for h in hosts if h.get('Location') == 'Remote']
    remotes_all_down = all(current_results.get(h['Hostname']) == "Down" for h in remote_hosts) if remote_hosts else False
    gateway_up = current_results.get('Gateway') == "Up"
    
    isp_active = gateway_up and len(remote_hosts) > 0 and remotes_all_down
    was_isp_active = status_vals.get('ISP_Outage_Active', 'False') == 'True'
    
    outage_updates = []
    daily_report_msg = ""

    # --- PHASE C: PROCESS HOST STATUSES ---
    for h in hosts:
        name = h['Hostname']
        res = current_results.get(name, "Up")
        old_status = status_vals.get(f'Status_{name}', 'Up')
        old_time = status_vals.get(f'Time_{name}', timestamp)
        fail_count = int(status_vals.get(f'Fail_{name}', '0'))
        threshold = int(h.get('Threshold', 3))

        # Update the rolling daily text log for this host
        with open(os.path.join(log_dir, f"{name}-{today_str}.txt"), "a") as f:
            f.write(f"{timestamp}: {res}\n")

        if res == "Down":
            fail_count += 1
            # Mark the exact start of the failure
            if fail_count == 1: 
                status_vals[f'Time_{name}'] = timestamp
            # Only mark as 'Down' if we hit the threshold (3 fails)
            if fail_count >= threshold: 
                status_vals[f'Status_{name}'] = "Down"
        else:
            # --- THE TRIPLE RESET LOGIC (The Bug Fix) ---
            # If the host was previously 'Down' and is now 'Up'
            if old_status == "Down":
                duration_mins = get_duration(old_time, now)
                key = f'DailyDowntime_{name}'
                # Add the current outage duration to the daily total
                status_vals[key] = str(int(status_vals.get(key, '0')) + duration_mins)
                
                # Prepare restoration alert (unless ISP outage suppressed it)
                if not was_isp_active or h.get('Location') != 'Remote':
                    outage_updates.append(f"✅ {name} Restored. Down: {duration_mins}m")

            # Forcefully reset Status, Fail Count, and Timestamp every time host is UP
            status_vals[f'Status_{name}'] = "Up"
            status_vals[f'Fail_{name}'] = "0"
            status_vals[f'Time_{name}'] = timestamp

    # Handle ISP Outage state changes
    if was_isp_active and not isp_active and gateway_up:
        isp_dur = get_duration(status_vals.get('ISP_Start_Time', timestamp), now)
        outage_updates.append(f"🚨 ISP Outage Resolved\nDuration: {isp_dur}m")
        status_vals['DailyISPOutages'] = str(int(status_vals.get('DailyISPOutages', '0')) + 1)
        status_vals['ISP_Outage_Active'] = 'False'

    if isp_active and not was_isp_active:
        status_vals['ISP_Outage_Active'] = 'True'
        status_vals['ISP_Start_Time'] = timestamp

    # --- PHASE D: DAILY REPORTING & RESET ---
    # Trigger at midnight (00:00) or configured report time
    report_time_cfg = gen_cfg.get('REPORT_TIME', '00:00')
    if status_vals.get('LastDailyReportDate', '') != today_str and now.strftime("%H:%M") >= report_time_cfg:
        daily_report_msg = f"📊 Daily Network Summary ({now.strftime('%m/%d/%Y')})\n"
        for h in hosts:
            n = h['Hostname']
            m = status_vals.get(f'DailyDowntime_{n}', '0')
            daily_report_msg += f"• {n}: {m}m down\n"
            status_vals[f'DailyDowntime_{n}'] = '0' # Reset counters for new day
        
        isp_cnt = status_vals.get('DailyISPOutages', '0')
        if int(isp_cnt) > 0: daily_report_msg += f"• ISP Outages: {isp_cnt}"
        
        status_vals['LastDailyReportDate'] = today_str
        status_vals['DailyISPOutages'] = '0'

    # --- PHASE E: SEND ALERTS & SAVE STATE ---
    # Send tweets if there is a daily report or an outage update
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
            if daily_report_msg: 
                client.create_tweet(text=f"{daily_report_msg}\n{tags}"[:280])
            for msg in outage_updates: 
                client.create_tweet(text=f"{msg}\n{tags}"[:280])
        except Exception as e:
            with open(error_file, "a") as f: 
                f.write(f"{timestamp}: Twitter Error: {e}\n")

    # FINAL STEP: Save the in-memory state back to the CSV in one go.
    with open(status_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['Field Name', 'Value'])
        for k, v in status_vals.items():
            writer.writerow([k, v])

if __name__ == "__main__":
    main()
