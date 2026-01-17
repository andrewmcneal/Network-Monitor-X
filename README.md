# Pi-Network-Monitor-X

A lightweight, self-initializing network monitoring script for Raspberry Pi that sends alerts and daily health reports via X (Twitter).

## Key Features
* **Smart Thresholds:** Define how many consecutive failures are required before an alert is sent.
* **Daily Stats:** Automatically posts a daily summary of total "Down Minutes" for each host.
* **Self-Bootstrapping:** Automatically creates config files and log directories on first run.
* **Audit Trail:** Maintains high-resolution text logs for every ping attempt.

## Installation
1. Clone this repository to your Raspberry Pi.
2. Install the required Python library:
   `pip install -r requirements.txt`

## Setup
1. Run the script once to generate the default configuration:
   `python monitor.py`
2. Open the newly created `config.csv` and enter your X API Keys, IP Addresses, and Thresholds.

## Automation
To monitor your network 24/7, add the script to your crontab. Run `crontab -e` and add the following line:
`* * * * * /usr/bin/python3 /home/YOUR_USERNAME/Documents/pinger/monitor.py`

## License
This project is licensed under the MIT License.
