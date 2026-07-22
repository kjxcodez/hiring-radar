# Execution Runtime & Job Queue Architecture

This document describes the design, execution lifecycle, triggers, locking, and asynchronous background worker processing inside the **Hiring Radar Execution Runtime**.

---

## 1. Design Overview

To support execution schedules, background jobs, retries, and rate-limiting across multiple presentation adapters (CLI, MCP, Telegram, Dashboard), Hiring Radar uses a unified **Execution Runtime**.

The Runtime sits between the presentation trigger layer and the Workflow Engine:

```
            CLI / Dashboard / Telegram / Webhook
                             │
                             ▼
                     Execution Runtime
                             │
         ┌───────────────────┴───────────────────┐
         │                                       │
         ▼                                       ▼
     Job Queue                               Scheduler
  (output/queue.json)                  (output/schedules.json)
         │                                       │
         └───────────────────┬───────────────────┘
                             ▼
                       Worker Thread
                             │
                             ▼
                      Workflow Engine
```

---

## 2. Core Modules

The runtime is structured inside `app/runtime/` as follows:

* **[state.py](file:///c:/Users/91637/Desktop/Business%20Project/hiring-radar/app/runtime/state.py)**: Defines states (`queued`, `running`, `waiting`, `completed`, `cancelled`, `retrying`, `failed`).
* **[triggers.py](file:///c:/Users/91637/Desktop/Business%20Project/hiring-radar/app/runtime/triggers.py)**: Defines trigger sources (`manual`, `cli`, `cron`, `telegram`, `webhook`, `dashboard`).
* **[execution.py](file:///c:/Users/91637/Desktop/Business%20Project/hiring-radar/app/runtime/execution.py)**: Contains the `Execution` Pydantic model representing a single task run metadata, status, result and duration.
* **[locks.py](file:///c:/Users/91637/Desktop/Business%20Project/hiring-radar/app/runtime/locks.py)**: File-based exclusive locking on workflow aliases (e.g. `wf_discover`) to prevent concurrent workspace writes.
* **[history.py](file:///c:/Users/91637/Desktop/Business%20Project/hiring-radar/app/runtime/history.py)**: Atomic history serialization in `output/executions.json`.
* **[queue.py](file:///c:/Users/91637/Desktop/Business%20Project/hiring-radar/app/runtime/queue.py)**: Local JSON-backed FIFO queue supporting priorities and delayed jobs.
* **[scheduler.py](file:///c:/Users/91637/Desktop/Business%20Project/hiring-radar/app/runtime/scheduler.py)**: Evaluates cron and interval schedules to trigger recurring discovery and analysis jobs.
* **[worker.py](file:///c:/Users/91637/Desktop/Business%20Project/hiring-radar/app/runtime/worker.py)**: Daemon execution loop polling queue and scheduling ticks.
* **[runtime.py](file:///c:/Users/91637/Desktop/Business%20Project/hiring-radar/app/runtime/runtime.py)**: Orchestrates submit, execute, cancel, status, and Worker triggers.

---

## 3. Usage & CLI Interface

The runtime provides the `jobs` command group to monitor background tasks:

### List running and queued tasks
```bash
hiring-radar jobs list
```

### View job history logs
```bash
hiring-radar jobs history --limit 20
```

### Cancel a queued or active task
```bash
hiring-radar jobs cancel <job-uuid-or-prefix>
```

### Retry a failed task
```bash
hiring-radar jobs retry <job-uuid-or-prefix>
```

---

## 4. Concurrency & Locking

To prevent race conditions on databases (`companies.json`, `applications.json`), the runtime enforces exclusive file-based locks:
* A lock `wf_discover.lock` is acquired during discovery/scraping.
* If a background job attempts to run while another is active, it is automatically re-enqueued with a 10s delay.
* Lock safety is validated in `tests/test_locks.py`.
