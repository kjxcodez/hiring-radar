# Hiring Radar Automation Guide

This guide explains how to configure external scheduling for **Hiring Radar** using standard operating system utilities and CI/CD tools.

The two core commands suitable for automated background execution are:
- `jobs watch --once`: Runs a single iteration of feed discovery, ATS parsing, company enrichment, and alert dispatch.
- `jobs digest --send`: Formats and sends a unified markdown alert summarizing recent discoveries (e.g., to Telegram).

---

## 1. cron (Linux / macOS)

`cron` is a lightweight, time-based job scheduler. Because cron executions run in a minimal shell context, you must explicitly set the working directory and activate the virtual environment.

### Crontab Configuration
Open your user crontab editor:
```bash
crontab -e
```

Add the following entries (replacing `/path/to/hiring-radar` with your actual repository path):

```cron
# Run job watch every 30 minutes, logging output to watch.log
*/30 * * * * cd /path/to/hiring-radar && .venv/bin/python -m app.cli watch --once >> watch.log 2>&1

# Run digest daily at 9:00 AM, logging output to digest.log
0 9 * * * cd /path/to/hiring-radar && .venv/bin/python -m app.cli digest --send >> digest.log 2>&1
```

---

## 2. systemd Timers (Linux)

For Linux systems, `systemd` timers provide robust scheduling, dependency checking, and unified logging via `journalctl`.

To schedule the watch command, create a service file and a timer file in `/etc/systemd/system/`:

### Service File: `/etc/systemd/system/hiring-radar-watch.service`
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

### Timer File: `/etc/systemd/system/hiring-radar-watch.timer`
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

### Enabling the Timer
Enable and start the timer:
```bash
sudo systemctl daemon-reload
sudo systemctl enable --now hiring-radar-watch.timer
```

Verify status and history:
```bash
systemctl list-timers --all
journalctl -u hiring-radar-watch.service
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
