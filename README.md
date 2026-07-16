# 📡 Hiring Radar

Hiring Radar is a local-first CLI that discovers companies actively hiring and turns that into structured, actionable outreach data.

[![Python Version](https://img.shields.io/badge/python-%3E%3D3.13-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](#contributing)

---

## What it does

Hiring Radar searches public ATS platforms (such as Greenhouse, Lever, Ashby, Bamboohr, and Workable) and job feeds (such as RemoteOK and WeWorkRemotely) to identify companies currently listing active job postings. It downloads company details and processes job specifications locally to surface match fits. Using OpenRouter models, it runs deep corporate analysis, ranks attractiveness, parses candidate resumes, and crafts tailored cold-outreach emails. Discovered companies and status histories are persisted inside a unified local JSON datastore, allowing the platform to generate daily activity digests, update a dark-mode browser dashboard, and host an interactive tool-calling AI agent.

### Why local-first?
Everything runs on your own machine. There are no external database servers to configure, no Docker containers to launch, and no SaaS subscriptions to manage. Your job applications, contacts, notes, and parsed resumes remain strictly private in local JSON files. Network requests are only made to fetch public job board listings, scrape target company webpages, dispatch SMTP emails, send Telegram alerts, or communicate with OpenRouter using your own API key. Nothing phones home.

---

## Feature Overview

| Capability | Command | Description |
|---|---|---|
| **Discover Hiring Companies** | `discover` | Query public ATS APIs/job boards for hiring companies. |
| **Scrape Metadata & Contacts** | `scrape` | Crawl company websites to extract metadata and contact details. |
| **Summarize Company Profiles** | `enrich` | Perform initial AI summarization on crawled company data. |
| **Deep Corporate Research** | `research <company>` | Crawl GitHub and query AI to extract products, target customers, and signals. |
| **Score Employer Quality** | `score-company <company>` | Rate companies on growth, culture, remote compatibility, and open source. |
| **Resume Matching Score** | `score` | Evaluate candidate resume compatibility against company job postings. |
| **Tailor Resume Content** | `tailor <company>` | Get non-destructive resume tailoring and objective summary recommendations. |
| **Track Applications** | `apply <company>` | Update and record job application stages with history logs. |
| **Record Application Notes** | `note <company>` | Add or list timestamped progress logs and updates. |
| **Pending Follow-up Alerts** | `followups` | Surface applications in active states that have gone uncontacted. |
| **Rank Recommendations** | `recommend` | Sort and rank uncontacted companies based on desirability and resume overlap. |
| **Preview Outreach Email** | `preview <company>` | Generate and preview personalized cold outreach emails using templates. |
| **Send Cold Outreach** | `send` | Dispatch emails securely using configured SMTP settings. |
| **Automated Loop Daemon** | `watch` | Continuous discovery, enrichment, and Telegram notification daemon. |
| **Hiring Summary Digest** | `digest` | Generate a recent hiring summary report and optionally send to Telegram. |
| **Daily Morning Digest** | `morning-brief` | Send the pre-configured daily summary digest to Telegram. |
| **Daily Activity Report** | `report` | Generate an end-of-day summary of local activities and applications. |
| **Visual UI Dashboard** | `dashboard` | Compile a local, build-less dark-mode HTML interface. |
| **Model Context Protocol** | `mcp-serve` | Run the FastMCP server over stdio or HTTP-SSE transport. |
| **Interactive AI Agent** | `agent` | Launch the local tool-calling CLI agent. |
| **Data Summary Diagnostics** | `status` | Display statistics of local databases and configurations. |

---

## Quickstart

Follow these steps to set up and run Hiring Radar on your machine:

1. **Clone the repository**:
   ```bash
   git clone https://github.com/kjxcodez/hiring-radar.git
   cd hiring-radar
   ```

2. **Create and activate a virtual environment**:
   ```bash
   python -m venv .venv
   # On Windows (PowerShell):
   .venv\Scripts\Activate.ps1
   # On macOS/Linux:
   source .venv/bin/activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   # Optionally install in editable mode to expose the 'hiring-radar' script:
   pip install -e .
   ```

4. **Initialize configurations**:
   ```bash
   cp .env.example .env
   cp config.example.yaml config.yaml
   ```
   *Edit `.env` to add your `OPENROUTER_API_KEY` and other credentials.*

5. **Run your first discovery query**:
   ```bash
   python -m app.cli discover --sources greenhouse,lever --limit 20
   ```

6. **Check data status**:
   ```bash
   python -m app.cli status
   ```

7. **Generate and open the dashboard**:
   ```bash
   python -m app.cli dashboard --open
   ```

---

## Configuration Reference

### `.env` Environment Variables

| Variable | Purpose | Required? | Default |
|---|---|---|---|
| `OPENROUTER_API_KEY` | API key to perform AI summary, research, scoring, and tailoring. | Yes (for AI) | None |
| `OUTPUT_DIR` | Directory where databases and generated files are saved. | No | `output` |
| `REQUEST_DELAY_SECONDS` | Rate-limiting pause between scraper page requests. | No | `1.5` |
| `LOG_LEVEL` | Logging verbosity (DEBUG, INFO, WARNING, ERROR). | No | `INFO` |
| `SMTP_HOST` | SMTP server host address for sending outreach emails. | No | `smtp.gmail.com` |
| `SMTP_PORT` | SMTP port number (typically 587 for STARTTLS). | No | `587` |
| `SMTP_USERNAME` | SMTP account email address. | No | None |
| `SMTP_APP_PASSWORD` | App-specific SMTP password or credentials. | No | None |
| `TELEGRAM_BOT_TOKEN` | API token for your Telegram Bot alerts. | No | None |
| `RESUME_PATH` | Path to default candidate resume file (`.pdf` or `.txt`). | No | None |

### `config.yaml` Configurations

| Key | Purpose | Default |
|---|---|---|
| `default_profile` | Stem name of the search profile YAML to apply (from `profiles/`). | `frontend` |
| `telegram.enabled` | Enable sending alerts and summaries to Telegram. | `false` |
| `telegram.chat_id` | Chat ID where the Telegram Bot sends notification alerts. | `""` |
| `email.from_name` | Sender display name in sent email headers. | `"Kapil Kumar Jangid"` |
| `email.from_address` | Sender email address in sent email headers. | `""` |
| `export.default_format` | Default export file type format (`csv` or `json`). | `csv` |

---

## Screenshots

### Static HTML Dashboard
<!-- TODO: screenshot -->

### Interactive AI Agent REPL Session
<!-- TODO: screenshot -->

---

## Project Structure

```
.
├── .env.example              # Template for local environment secrets
├── LICENSE                   # License information (MIT)
├── README.md                 # Project documentation
├── alerts.example.yaml       # Example alert matching rules
├── config.example.yaml       # Default user configurations
├── pyproject.toml            # Package definition and script entrypoint
├── requirements.txt          # Python virtual environment dependencies
├── app/                      # Main application logic
│   ├── agent/                # Standalone AI agent planner, memory, and tools
│   ├── dashboard/            # Local dashboard builder
│   ├── discover/             # Crawlers querying greenhouse, lever, ashby, remoteok, etc.
│   ├── enrich/               # OpenRouter corporate profiles and scoring APIs
│   ├── exporters/            # CSV/JSON file exporter formats
│   ├── notify/               # Telegram alert notifications
│   ├── outreach/             # Cold email templates, subjects, and mailers
│   └── resume/               # Resume parsing, versioning, and tailoring engines
├── docs/                     # Guides for timers, systemd, and client setups
│   ├── automation.md         # Linux cron, timers, and GitHub Actions recipes
│   └── mcp.md                # MCP client setup configurations
├── mcp_server/               # Model Context Protocol server entrypoints
│   └── server.py             # Tools, resources, and prompts registrations
├── output/                   # Generated databases and dashboards (local only)
├── profiles/                 # YAML filters constraining discovery runs
├── resumes/                  # PDF/TXT resumes matched against postings
├── scripts/                  # Command-line diagnostics and setups
└── templates/                # Markdown outreach email drafts
```

---

## CLI Reference

To view the complete list of options and commands, run:
```bash
python -m app.cli --help
```

For help on a specific subcommand, append `--help`:
```bash
python -m app.cli recommend --help
python -m app.cli agent --help
```

### Concrete Examples

- **Continuous Scraping Loop (Daemon mode)**:
  ```bash
  python -m app.cli watch --interval 3600
  ```
- **Attractiveness AI Evaluation**:
  ```bash
  python -m app.cli score-company "Example Corp"
  ```
- **Heuristic Recommendations**:
  ```bash
  python -m app.cli recommend --top 5 --resume backend
  ```

---

## MCP & Agent Subsystems

Hiring Radar supports deep external LLM client integrations:
- **Model Context Protocol (MCP)**: Exposes search tools, resources, and prompts to client applications like Claude Desktop or Cursor. For configurations and connections details, see [docs/mcp.md](docs/mcp.md) and [mcp_server/README.md](mcp_server/README.md).
- **In-process AI Agent**: A standalone CLI planner executing tool-calling completions loops to resolve hiring pipelines autonomously. Execute using `python -m app.cli agent`.

---

## Automation

You can schedule automated discovery checks, daily digests, and notifications using standard OS-level utilities (such as `cron` or `systemd` timers) and GitHub Actions. For tested setup templates, see [docs/automation.md](docs/automation.md).

---

## Roadmap

### What's Built
- [x] Multi-source ATS crawlers (Greenhouse, Lever, Ashby, Workable, BambooHR, RemoteOK, WWR).
- [x] Local-first JSON databases (`companies.json` and `applications.json`).
- [x] OpenAI / OpenRouter resume matching and corporate research scorers.
- [x] Build-less static HTML interactive browser dashboard with charts.
- [x] Cold email outreaches (SMTP support) and Telegram alert notifications.
- [x] Model Context Protocol server exposing tools, resources, and prompt templates.
- [x] Standalone autonomous AI Agent REPL with mechanical confirmation gates.
- [x] CLI diagnostic tools and automation recipes.

### What's Next
- [ ] Direct web browser extensions to capture LinkedIn profile detail cards.
- [ ] Integration with local LLM models (e.g. via Ollama) to support completely offline AI scoring.
- [ ] Weekly/monthly rollups and statistics.

---

## Contributing

Contributors are welcome! Please read [CONTRIBUTING.md](CONTRIBUTING.md) for details on our code of conduct, development setups, and pull request workflows.

---

## License

Hiring Radar is open source software licensed under the [MIT License](LICENSE).
