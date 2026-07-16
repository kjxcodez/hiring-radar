# Hiring Radar Automation Guide

This guide explains how to configure external scheduling for **Hiring Radar** using standard operating system utilities and CI/CD tools.

The core commands suitable for automated background execution are:
- `jobs watch --once`: Runs a single iteration of feed discovery, ATS parsing, company enrichment, and alert dispatch.
- `jobs digest --send` / `jobs morning-brief`: Formats and sends a daily summary of recent discoveries (e.g., to Telegram). The `jobs morning-brief` command is a dedicated alias for `jobs digest --send` with clean configuration guards (exiting with code 0 instead of crashing if Telegram is unconfigured).

---

## 1. cron (Linux / macOS)

`cron` is a lightweight, time-based job scheduler. Because cron executions run in a minimal shell context, you must explicitly set the working directory and activate the virtual environment.

### Timezone Warning
`cron` evaluates schedules against the **system timezone**, not the user shell or application configurations. Ensure your system timezone is correct:
```bash
# Check current system timezone
timedatectl

# Set system timezone (e.g. to Europe/London or Asia/Kolkata)
sudo timedatectl set-timezone Asia/Kolkata
```

### Crontab Configuration
Open your user crontab editor:
```bash
crontab -e
```

Add the following entries (replacing `/path/to/hiring-radar` with your actual repository path):

```cron
# Run job watch every 30 minutes, logging output to watch.log
*/30 * * * * cd /path/to/hiring-radar && .venv/bin/python -m app.cli watch --once >> watch.log 2>&1

# Run the morning brief daily at 8:00 AM local time, logging output to morning_brief.log
0 8 * * * cd /path/to/hiring-radar && .venv/bin/python -m app.cli morning-brief >> morning_brief.log 2>&1
```

---

## 2. systemd Timers (Linux)

For Linux systems, `systemd` timers provide robust scheduling, dependency checking, and unified logging via `journalctl`.

### A. Discovery Job (`watch --once` every 30 minutes)

Create a service file and a timer file in `/etc/systemd/system/`:

#### Service File: `/etc/systemd/system/hiring-radar-watch.service`
```ini
[Unit]
Description=Hiring Radar Job Feed Watch
After=network.target

[Service]
Type=oneshot
WorkingDirectory=/path/to/hiring-radar
ExecStart=/path/to/hiring-radar/.venv/bin/python -m app.cli watch --once
User=yourusername
Group=yourusername
```

#### Timer File: `/etc/systemd/system/hiring-radar-watch.timer`
```ini
[Unit]
Description=Run Hiring Radar Watch every 30 minutes

[Timer]
OnBootSec=5min
OnUnitActiveSec=30min
Unit=hiring-radar-watch.service

[Install]
WantedBy=timers.target
```

### B. Daily Morning Brief (`morning-brief` at 8:00 AM daily)

Create these units:

#### Service File: `/etc/systemd/system/hiring-radar-brief.service`
```ini
[Unit]
Description=Hiring Radar Daily Morning Brief
After=network.target

[Service]
Type=oneshot
WorkingDirectory=/path/to/hiring-radar
ExecStart=/path/to/hiring-radar/.venv/bin/python -m app.cli morning-brief
User=yourusername
Group=yourusername
```

#### Timer File: `/etc/systemd/system/hiring-radar-brief.timer`
```ini
[Unit]
Description=Run Hiring Radar Morning Brief daily at 8:00 AM

[Timer]
OnCalendar=*-*-* 08:00:00
Persistent=true
Unit=hiring-radar-brief.service

[Install]
WantedBy=timers.target
```

### Enabling and Starting Timers
Enable and start the timers:
```bash
sudo systemctl daemon-reload
sudo systemctl enable --now hiring-radar-watch.timer
sudo systemctl enable --now hiring-radar-brief.timer
```

Verify status and history:
```bash
systemctl list-timers --all
journalctl -u hiring-radar-watch.service
journalctl -u hiring-radar-brief.service
```

---

## 3. GitHub Actions Workflows

If you host your repository on GitHub, you can use GitHub Actions to automate runs on hosted runners. 

### Option A: Private Repository (Committing Database State)
This workflow checks out the repository, executes the watch script, and commits changes back to `companies.json`.

Create `.github/workflows/watch.yml`:
```yaml
name: Scheduled Watch (Private Repo)

on:
  schedule:
    # Run every 30 minutes
    - cron: '*/30 * * * *'
  workflow_dispatch:

jobs:
  watch:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout repository
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.10'
          cache: 'pip'

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt

      - name: Run Watch Once
        env:
          OPENROUTER_API_KEY: ${{ secrets.OPENROUTER_API_KEY }}
          TELEGRAM_BOT_TOKEN: ${{ secrets.TELEGRAM_BOT_TOKEN }}
        run: python -m app.cli watch --once

      - name: Commit updated database
        run: |
          git config --global user.name 'github-actions[bot]'
          git config --global user.email 'github-actions[bot]@users.noreply.github.com'
          git add output/companies.json
          git diff-index --quiet HEAD || git commit -m "auto: update discovered companies database"
          git push
```

### Option B: Public Repository (Zero-Commit Notification Only)
If your repository is public or you gitignore `companies.json`, this workflow runs discovery and sends notifications (such as Telegram) without checking in any data changes.

Create `.github/workflows/watch-public.yml`:
```yaml
name: Scheduled Watch (Notification Only)

on:
  schedule:
    # Run every 30 minutes
    - cron: '*/30 * * * *'
  workflow_dispatch:

jobs:
  watch:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout repository
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.10'
          cache: 'pip'

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt

      - name: Run Watch Once
        env:
          OPENROUTER_API_KEY: ${{ secrets.OPENROUTER_API_KEY }}
          TELEGRAM_BOT_TOKEN: ${{ secrets.TELEGRAM_BOT_TOKEN }}
        run: python -m app.cli watch --once
```
