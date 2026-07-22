# Discovery Engine — Architecture Reference

Phase 2.0 introduced a dedicated async discovery engine in `app/discovery/` that coordinates all ATS and job-board providers concurrently. This document covers the architecture, key design decisions, and a guide for adding new providers.

---

## Architecture Overview

```
CLI / DiscoveryService
        │
        ▼
DiscoverStep (app/workflows/step.py)
        │
        ├── [registry mock detected] ──► Legacy SOURCE_REGISTRY path (sync)
        │
        └── [production providers] ────► DiscoveryCoordinator (async bridge)
                                                │
                                    asyncio.gather(
                                        _run_provider("greenhouse", ...),
                                        _run_provider("lever", ...),
                                        _run_provider("remoteok", ...),
                                        ...
                                    )
                                                │
                                    Each provider runs in executor:
                                    loop.run_in_executor(None, sync_discover_fn, slugs)
                                                │
                                    ┌─────────────────────┐
                                    │  AsyncRateLimiter   │
                                    │  (per-provider)     │
                                    └─────────────────────┘
                                                │
                                    ┌─────────────────────┐
                                    │   Deduplicator      │
                                    │  (cross-provider)   │
                                    └─────────────────────┘
                                                │
                                    ┌─────────────────────┐
                                    │   DiscoveryFilter   │
                                    │  (delegate to       │
                                    │  app.filters)       │
                                    └─────────────────────┘
                                                │
                                    list[Company]
```

---

## Package Layout

```
app/discovery/
├── __init__.py           # Public API re-exports
├── provider.py           # DiscoveryProvider ABC
├── registry.py           # ProviderRegistry (class-level dict + decorator)
├── coordinator.py        # DiscoveryCoordinator (sync bridge + async engine)
├── rate_limit.py         # AsyncRateLimiter + per-provider defaults
├── pagination.py         # PaginationState dataclass
├── normalization.py      # CompanyNormalizer + infer_remote_type()
├── deduplication.py      # Deduplicator (priority-keyed merge)
├── filters.py            # DiscoveryFilter (delegates to app.filters)
├── errors.py             # Exception hierarchy
└── providers/
    ├── __init__.py       # Triggers all self-registrations
    ├── greenhouse.py     # GreenhouseProvider
    ├── lever.py          # LeverProvider
    ├── ashby.py          # AshbyProvider
    ├── workable.py       # WorkableProvider
    ├── bamboohr.py       # BambooHRProvider
    ├── remoteok.py       # RemoteOKProvider (feed-based)
    └── wwr.py            # WWRProvider (feed-based)
```

---

## Async Execution Model

The coordinator exposes a **synchronous** `discover()` entry point that internally bridges to `asyncio` via `asyncio.run()`. This means:

- **All callers above it (CLI, DiscoverStep, DiscoveryService) remain fully synchronous** — no `async/await` propagation required.
- Inside `_discover_async()`, `asyncio.gather(return_exceptions=True)` runs all providers concurrently.
- Each provider runs the existing synchronous `app.discover.*` module in a **thread-pool executor** via `loop.run_in_executor(None, sync_fn, slugs)`. No provider rewrite is needed.

### Provider failure isolation

`asyncio.gather(return_exceptions=True)` ensures that a single provider's network failure, HTTP error, or unexpected exception **never aborts the other providers**. Failed providers log a `WARNING` and return `[]`.

### Global concurrency cap

A `asyncio.Semaphore(max_concurrency)` wraps each `_run_provider()` call to prevent more than N providers from executing simultaneously. Default: 7 (all providers concurrently).

---

## Rate Limiting

Each provider has an `AsyncRateLimiter` built from defaults in `PROVIDER_RATE_LIMITS`:

| Provider   | Max Concurrent | RPS  |
|------------|---------------|------|
| greenhouse | 10            | 3.0  |
| lever      | 8             | 3.0  |
| ashby      | 8             | 2.0  |
| workable   | 5             | 2.0  |
| bamboohr   | 5             | 2.0  |
| remoteok   | 1             | 0.5  |
| wwr        | 1             | 0.5  |

The `AsyncRateLimiter` combines:
1. An `asyncio.Semaphore` for max-concurrency enforcement.
2. A minimum inter-request delay (`1.0 / rps` seconds) via `asyncio.sleep`.

---

## Deduplication Algorithm

`Deduplicator.merge()` uses a **priority-ordered key strategy** to identify the same company across providers:

1. **`ats_platform::ats_slug`** — Most specific. Used when the same ATS record is fetched from the same platform. Prevents incorrect merges of different companies with the same name.
2. **`domain`** — Authoritative identity. Used for cross-provider merging of the same company (e.g., Greenhouse + Lever both return "Stripe").
3. **`website` hostname** — Normalised to strip `www.` prefix. Used as fallback when domain isn't set.
4. **`name.lower().strip()`** — Final fallback. Less reliable (spelling variations) but better than no deduplication at all.

When a duplicate is found, **new job URLs are merged into the existing record** and `last_updated` is refreshed. Other fields are preserved as-is.

---

## Pagination Support

`PaginationState` is a dataclass that carries per-provider cursor state through multi-page fetches. Current providers (Greenhouse, Lever, etc.) are single-request, so `has_more=False` is the default.

Future providers implementing pagination should:

```python
async def discover(self, slugs, limit, **kwargs):
    state = PaginationState()
    results = []
    while state.has_more or state.page == 1:
        page_data, state = await self._fetch_page(state)
        results.extend(page_data)
        if len(results) >= limit:
            break
    return results[:limit]
```

---

## Normalization

`CompanyNormalizer` provides two factory methods:

- `from_slug(slug, jobs, provider_name)` — For slug-based providers (Greenhouse, Lever, Ashby, Workable, BambooHR). Converts `acme-corp` → `"Acme Corp"`, sets `ats_platform` and `ats_slug`.
- `from_name(company_name, jobs, provider_name)` — For feed-based providers (RemoteOK, WWR). Company name comes directly from the feed; `ats_platform` and `ats_slug` are `None`.

`infer_remote_type()` centralises the `remote_type` resolution logic (previously duplicated in every provider):

```
is_remote_flag (bool)     → "remote" / falls through
explicit_type (str)       → from EXPLICIT_REMOTE_MAP
location string           → heuristic "remote" substring check
fallback                  → "unknown"
```

> **Note:** Existing provider modules (`app/discover/*.py`) have not been migrated to use `CompanyNormalizer` yet. They continue to construct `Company` objects directly. `CompanyNormalizer` is available for future providers and incremental migration.

---

## Adding a New Provider

Follow these 3 steps to add a new ATS integration.

### Step 1 — Implement the sync discover function

Create `app/discover/myats.py` following the pattern of `greenhouse.py`. Implement a synchronous `discover(slugs: list[str]) -> list[Company]` function.

### Step 2 — Create the async adapter

Create `app/discovery/providers/myats.py`:

```python
from __future__ import annotations

import asyncio
from app.discovery.provider import DiscoveryProvider
from app.discovery.registry import ProviderRegistry
from app.models import Company


@ProviderRegistry.register("myats")
class MyATSProvider(DiscoveryProvider):
    name = "myats"
    default_concurrency = 5
    default_rate_limit_rps = 2.0

    async def discover(self, slugs, limit, **kwargs) -> list[Company]:
        if not slugs:
            return []
        from app.discover.myats import discover as _sync_discover
        loop = asyncio.get_event_loop()
        try:
            return await loop.run_in_executor(None, _sync_discover, slugs)
        except Exception as exc:
            from loguru import logger
            logger.warning("myats: async discover failed — {exc}", exc=exc)
            return []
```

### Step 3 — Register it

Import your provider in `app/discovery/providers/__init__.py`:

```python
from app.discovery.providers import myats  # triggers @register decorator
```

And add it to `app/discover/__init__.py`'s `SOURCE_REGISTRY` for backward compatibility:

```python
from app.discover import myats
SOURCE_REGISTRY["myats"] = myats.discover
```

That's it. The coordinator will now run `myats` concurrently alongside all other providers.

---

## Error Hierarchy

```
DiscoveryError          # Base exception
├── ProviderError       # Provider encountered unrecoverable error
├── ProviderNotFoundError  # Registry lookup miss
├── RateLimitExceeded   # Rate limit timeout
└── PaginationError     # Pagination inconsistency
```

All exceptions import from `app.discovery.errors`.

---

## Backward Compatibility

The `app/discover/` package and `SOURCE_REGISTRY` are **unchanged**. `DiscoverStep` checks:

1. If `local_registry` is a **mock object** (test scenario) → all sources use the legacy synchronous path via `SOURCE_REGISTRY`.
2. Otherwise, sources registered in `ProviderRegistry` use the async coordinator; sources not in `ProviderRegistry` fall back to `SOURCE_REGISTRY` (synchronous).

This means existing CLI tests that mock `app.cli.SOURCE_REGISTRY` continue to work without modification.
