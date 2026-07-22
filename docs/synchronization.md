# Synchronization Engine & Change Detection Reference

This document provides a comprehensive overview of the persistent synchronization engine introduced in Phase 2.1 in the `app/sync/` package.

---

## Synchronization Lifecycle

The synchronization process runs transparently beneath the `DiscoveryCoordinator` or can be executed directly using `hiring-radar sync`. The execution lifecycle proceeds as follows:

```
                  ┌────────────────────────┐
                  │   Load Checkpoint      │
                  └───────────┬────────────┘
                              │
                    [Cooldown Checked?]
                   /                 \
                 Yes                  No
                 /                      \
      ┌─────────────────────┐   ┌─────────────────────┐
      │ Cache Hit (Skip)    │   │ Execute Provider    │
      └─────────────────────┘   └───────────┬─────────┘
                                            │
                                ┌───────────▼─────────┐
                                │ Create Raw Snapshot │
                                └───────────┬─────────┘
                                            │
                                ┌───────────▼─────────┐
                                │ Checksum Match?     │
                                └───────┬─────────────┘
                                       / \
                                     Yes  No
                                     /      \
                          [Cache Hit]      ┌──────────▼─────────┐
                                           │ Run Diff Engine    │
                                           └──────────┬─────────┘
                                                      │
                                           ┌──────────▼─────────┐
                                           │ Reconcile Database │
                                           └──────────┬─────────┘
                                                      │
                                           ┌──────────▼─────────┐
                                           │ Save Snap & Check  │
                                           └────────────────────┘
```

---

## Core Components

### 1. Snapshot Model (`snapshot.py`)
Snapshots represent the raw, unfiltered output of a provider during a synchronization run.
- **Checksumming**: Normalized company and job listings are serialized to a deterministic JSON representation and hashed using SHA-256. If a provider's checksum matches the previous run's checksum, database updates are skipped entirely.

### 2. Fingerprinting Engine (`fingerprint.py`)
Generates deterministic SHA-256 signatures to identify modifications:
- **Company Fingerprint**: Computed from `domain`, `website`, `career_page_url`, and `name`.
- **Job Fingerprint**: Computed from `job_title`, `location`, `remote_type`, and `job_url`.

### 3. Diff Engine (`diff.py`)
Compares snapshots to produce a structured difference `SnapshotDiff`:
- **Added Companies/Jobs**: Entities present in the current snapshot but missing from the previous.
- **Removed Companies/Jobs**: Entities present in the previous snapshot but missing from the current.
- **Updated Companies/Jobs**: Entities present in both whose fingerprint changed.

### 4. Checkpoints (`checkpoint.py`)
Enables resumption and tracking of HTTP metadata:
- **Metadata**: Tracks `last_successful_run`, `last_failed_run`, `duration`, `processed_pages`, `etag`, and `last_modified`.

---

## Soft Deletions and Reconciliation

Soft deletion prevents active crawls from growing indefinitely while preserving data history for recommendations, digests, and audits.
- **Job soft deletion**: When a job is removed, it is purged from the active `jobs` list of the `Company` in `companies.json`. A history note is appended: `"job_removed: {job_title} ({job_url}) at {timestamp}"`.
- **Company soft deletion**: If a company no longer has any active jobs, it is flagged by appending a note: `"company_removed: {timestamp}"`. Active workflows (like Scrape, Enrich, outreach preview) will skip soft-deleted companies.

---

## CLI Sync Command Guide

Hiring Radar exposes the `sync` command group:

- `hiring-radar sync`: Synchronizes all providers concurrently.
- `hiring-radar sync provider <name>`: Syncs a single provider.
- `hiring-radar sync status`: Prints a table showing the checkpoint status for all providers.
- `hiring-radar sync history`: Shows a running execution log of the last 20 syncs.
- `hiring-radar sync reset`: Resets checkpoints, snapshots, and logs.
