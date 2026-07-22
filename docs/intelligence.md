# Company Intelligence Engine & Knowledge Graph

This document details the architecture, design choices, and mechanisms of the **Company Intelligence Engine** and **Knowledge Graph** index implemented in Phase 2.2.

---

## Architecture Overview

The Company Intelligence subsystem enriches discovered organizations with business signals, technology stacks, open-source presence, hiring trends, and AI-generated copy.

```
                  ┌──────────────────────┐
                  │   Discovery Engine   │
                  └──────────┬───────────┘
                             │
                  [WorkflowCompletedEvent]
                             │
                             ▼
               ┌──────────────────────────┐
               │    Background Runtime    │
               └─────────────┬────────────┘
                             │
                  [Trigger: "intelligence"]
                             │
                             ▼
               ┌──────────────────────────┐
               │    Intelligence Engine   │
               └─────────────┬────────────┘
                             │
        ┌────────────────────┼────────────────────┐
        ▼                    ▼                    ▼
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│ Website Crawl│     │ GitHub Crawl │     │ AI Summaries │
└───────┬──────┘     └───────┬──────┘     └───────┬──────┘
        │                    │                    │
        └────────────────────┼────────────────────┘
                             │
                             ▼
                ┌─────────────────────────┐
                │   Knowledge Graph       │
                │ (knowledge_graph.json)  │
                └─────────────────────────┘
```

---

## 1. Sub-Profile Schemas

All enrichment variables are grouped inside the `CompanyIntelligence` profile in `app/models.py`:

* **`BusinessProfile`**: firmographics, headquarters, remote policy, and founded year.
* **`EngineeringProfile`**: languages, frameworks, databases, cloud, infrastructure, CI/CD, and AI stack.
* **`HiringProfile`**: velocity, roles count, departments distribution, seniority ratios, and locations.
* **`GitHubProfile`**: repository names, star count, contributor estimations, and activity level.
* **`SignalsProfile`**: funding stage, startup maturity, culture tags, and AI adoption indexes.

---

## 2. Technology Detector & Parsers

* **`TechnologyDetector`**: Uses optimized regular expressions to scan text files, code listings, and descriptions, normalizing keywords (e.g. `k8s` -> `Kubernetes`, `py` -> `Python`).
* **`WebsiteAnalyzer`**: Extracts remote policies ("remote", "hybrid", "onsite") and maps mission or products statements.
* **`GitHubAnalyzer`**: Parses HTML profiles to extract top repositories, star counts, languages, and activity ratings.
* **`HiringAnalyzer`**: Calculates seniority proportions and department segments by filtering text tags on active job postings.
* **`SignalDetector`**: Infers corporate funding milestones (e.g., "Series A", "Seed") and growth flags.

---

## 3. Self-Invalidating Composite Cache

To minimize rate limits and OpenRouter completion charges, the engine implements a zero-dependency, self-invalidating check:

1. A stable cache hash is computed from the company's identity fingerprint (domain, name) and the combined hashes of all its active job listings.
2. If `company.intelligence` exists and `intelligence.cache_key` matches this calculated key, the pipeline immediately returns the cached profile, avoiding any network crawl or AI API requests.
3. If any job title changes, a role is added/removed, or the company is renamed, the cache invalidates automatically.

---

## 4. Knowledge Graph Index

The Knowledge Graph builds a semantic map of the corporate space (`output/knowledge_graph.json`):

* **Vertices (Nodes)**: Represents entities (`company`, `technology`, `location`, `department`, `github_org`).
* **Edges (Links)**: Maps relations between nodes (`uses_framework`, `hires_in`, `hires_for`, `has_github`).

---

## 5. CLI Interface

The CLI offers high-density Rich visualization tools:

```bash
# Run pipeline manually (wipe caches with --force)
hiring-radar intelligence [--force]

# Show detailed profile groups for a company
hiring-radar intelligence company stripe

# Show AI summaries and cold outreach briefing
hiring-radar intelligence summary stripe

# View aggregated technology frequencies
hiring-radar intelligence technologies

# View Knowledge Graph node and edge counts
hiring-radar intelligence graph
```
