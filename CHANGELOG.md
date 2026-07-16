# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

---

## [0.1.0] - 2026-07-16

This is the initial public release of Hiring Radar, a local-first hiring intelligence platform and CLI tool designed to query ATS feeds, scrape contacts, evaluate job opportunities with AI, send cold outreach, and host interactive agents.

### Added

- **Multi-Source Job Discovery**: Integrated public API job search adapters querying Greenhouse, Lever, Ashby, BambooHR, and Workable ATS platforms, alongside RemoteOK and WeWorkRemotely feeds.
- **Dynamic Scraper & Parser**: Built HTML scraper extracting operational contacts, emails, and corporate description details.
- **AI-Based Profile Summarization**: Added OpenRouter LLM enrichment summarizing company features, hook points, and tech stack details.
- **Deeper AI Corporate Research**: Implemented static GitHub profile crawlers and deep AI corporate research notes.
- **Employer Quality Attractiveness Rating**: Built multi-axis scoring evaluating growth, culture, remote compatibility, open source presence, and overall desirability.
- **AI Career Intelligence & Tailoring**: Added plain text/PDF resume parsing (using `pypdf`) and resume tailoring suggestions to generate targeted job objective adjustments without fabricating experience.
- **Outreach Campaign Engine**: Configured local SMTP cold email draft previewers and dispatchers using markdown templates.
- **Workflow Application Tracker**: Implemented local `applications.json` status lifecycle state transitions (`discovered`, `researched`, `applied`, `interviewing`, `rejected`, `offer`) with dated notes and history logs.
- **Visual Dark Mode Dashboard**: Generated build-less, self-contained interactive `dashboard.html` plotting metrics, date timelines, and breakdown charts.
- **Model Context Protocol Server**: Exposed local tools, JSON-RPC resources, and prompts over stdio or HTTP-SSE transport modes.
- **Interactive AI Agent REPL**: Launched tool-calling CLI assistant (`jobs agent`) with mechanical confirmation guards for side-effecting operations (like status changes or email sends).
- **System Health Checks**: Built command-line diagnostics validating secrets configurations and file access.
- **Scheduling Automation**: Documented systemd services, timers, and cron configurations for routine runs.
