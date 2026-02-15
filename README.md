# Raspberry Pi Network & ISP Monitor

A robust, multi-threaded network monitoring suite designed for Raspberry Pi. This tool tracks the health of local and remote nodes, detects ISP outages, and provides intelligent alerting via X (Twitter).

## Key Features

- Parallel Monitoring: Uses Python's ThreadPoolExecutor to ping all hosts simultaneously, ensuring high-speed execution.
- ISP Outage Detection: Logic that distinguishes between a single host failure and a total ISP blackout (Gateway UP + all Remote nodes DOWN).
- Daily Summary Reports: Posts a daily network health summary to X at a user-defined time.
- Threshold Protection: Requires a configurable number of consecutive failures before marking a host as "Down" to prevent false alerts.
- Setup Wizard: Interactive setup.py to manage API credentials and host configurations securely.

## Getting Started

### 1. Prerequisites
Ensure you have Python 3.x installed on your Raspberry Pi.

### 2. Installation
Clone the repository to your local machine:
git clone https://github.com/YOUR_USERNAME/network-monitor.git
cd network-monitor

### 3. Install Dependencies
pip install -r requirements.txt

### 4. Configuration
Run the interactive Setup Wizard to configure your directories, Twitter API keys, and monitoring targets:
python3 setup.py
Note: This will create your config.csv, twitter-config.csv, and hosts-config.csv files locally.

## Usage

### Manual Run
To test the monitor immediately:
python3 monitor.py

### Automation (Crontab)
To run the monitor every minute, add it to your crontab:
crontab -e

Add the following line (adjusting the path to your script location):
* * * * * /usr/bin/python3 /home/your-user/pinger/monitor.py

## Directory Structure
- monitor.py: The core monitoring engine.
- setup.py: Configuration and host management utility.
- status.csv: The local state engine (tracks failure counts and daily timers).
- Errors-YYYY.txt: Yearly log file for system and API errors (located in root).
- Host-Logs/: Subfolder containing detailed daily ping history for every host.

## License
Distributed under the MIT License.
