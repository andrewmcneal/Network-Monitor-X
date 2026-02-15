import csv
import os
from datetime import datetime, timedelta

STATUS_FILE = 'status.csv'

def simulate_outage():
    # 1. Load the current status
    rows = []
    with open(STATUS_FILE, 'r') as f:
        reader = csv.reader(f)
        header = next(reader)
        for row in reader:
            rows.append(row)

    # 2. Manually set IP3 (Google) to 'Down' and set the time to 2 hours ago
    # This simulates a long-running outage
    two_hours_ago = (datetime.now() - timedelta(hours=2)).strftime("%m%d%Y-%H%M")
    
    # In status.csv: 
    # Row 6 is IP3, Row 7 is Status3, Row 8 is DateTime3
    rows[7][1] = "Down"
    rows[8][1] = two_hours_ago
    
    with open(STATUS_FILE, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(header)
        writer.writerows(rows)
    
    print(f"Simulation active: Google (IP3) marked as DOWN starting at {two_hours_ago}")
    print("Now wait for the next minute cycle, or run 'python3 monitor.py' manually.")

if __name__ == "__main__":
    simulate_outage()
