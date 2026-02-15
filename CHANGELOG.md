# Changelog

All notable changes to the **Raspberry Pi Network Monitor** project will be documented in this file.

## [1.1.0] - 2026-02-15

### Added
- **Configuration Wizard (`setup.py`):** A new command-line interface to safely generate and manage `config.csv`, `twitter-config.csv`, and `hosts-config.csv`.
- **Parallel Processing:** Integrated `ThreadPoolExecutor` in `monitor.py` to ping all hosts simultaneously, significantly reducing script runtime.
- **Dynamic Path Resolution:** Added `BASE_DIR` support in `config.csv` allowing the script to be installed in any directory (e.g., `/home/a-mcneal/Documents/pinger`).
- **ISP Outage Logic:** New intelligence to detect if the local gateway is Up while all remote nodes are Down, grouping them into a single "ISP Outage" event.
- **Daily Summary Reports:** Automatic 24-hour network health summary posted to X (Twitter) at a user-defined time (24-hour format).
- **Threshold Protection:** Added a configurable `Threshold` per host to prevent alerts on single dropped packets or minor blips.
- **Comprehensive Documentation:** Full inline comments added to the codebase for easier maintenance and GitHub collaboration.

### Changed
- **Error Logging:** Reverted to the yearly naming convention (`Errors-YYYY.txt`) located in the project root folder for better visibility.
- **State Management:** Upgraded `status.csv` to track cumulative daily downtime and ISP event counts.
- **Cross-Platform Compatibility:** Improved ping logic to automatically detect and adjust for Linux and Windows environments.
- **Output Encoding:** Standardized all file I/O to `UTF-8` to prevent character rendering errors across different systems.

### Fixed
- **Permission Errors:** Resolved `PermissionError` by ensuring the script strictly follows the user-defined `BASE_DIR` instead of hardcoded `/home/pi` paths.
- **Alert Fatigue:** Fixed logic that previously sent individual "Up" tweets for every host during a mass recovery; now grouped into a single ISP restoration tweet.

### Removed
- **Hardcoded Credentials:** Removed all API keys and personal paths from the source code, moving them to secure, git-ignored CSV files.
