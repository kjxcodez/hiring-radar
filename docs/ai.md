# Hiring Radar — AI Gateway & Prompt Management Architecture

This document describes the unified AI/LLM infrastructure layer of Hiring Radar.

---

## 1. AI Architecture

To decouple the service layer from provider SDKs, raw HTTP call structures, model naming conventions, and retry policies, we introduced a centralized `app/ai/` package:

```
 [ Research / Resume / Outreach / Agent Services ]
                      │
                      ▼
                 [ AI Gateway ] (orchestrates routing, retries, and caching)
                      │
         ┌────────────┴────────────┐
         ▼                         ▼
    [ AI Cache ]            [ OpenRouterClient ]
 (handles transparent      (performs raw HTTP calls,
  local file cache)         headers, auth tokens)
```

1. **AI Registry (`prompts.py`)**: Stores version-controlled system prompt templates with metadata.
2. **AI Cache (`cache.py`)**: Maintains a persistent local cache in `output/ai_cache.json` using atomic writes to prevent duplicate network calls.
3. **Retry Manager (`retry.py`)**: Centralizes exponential backoff policies for transient network and API rate-limiting errors.
4. **Client (`client.py`)**: Wraps OpenRouter connection details, authorization, timeouts, and headers.
5. **Gateway (`gateway.py`)**: Serves as the primary entry point, resolving abstract model aliases and formatting system messages.

---

## 2. Request Lifecycle

The pathway of a completion request:

```
1. Service invokes complete() or complete_json()
      │
      ▼
2. Gateway resolves abstract model (e.g. "fast" -> "openrouter/free")
      │
      ▼
3. Prompt is resolved from Prompt Registry (e.g. "resume_match.v1")
      │
      ▼
4. Gateway checks AI Cache (if enabled) using a SHA-256 parameter hash
      ├── [Hit]  Return cached text immediately
      └── [Miss] Proceed to step 5
            │
            ▼
5. Gateway executes client call wrapped inside Retry Policy
      ├── [Transient Error] Backoff and retry (max 3 attempts)
      └── [Success] Retrieve response content
            │
            ▼
6. Gateway stores response in AI Cache
      │
      ▼
7. Gateway validates and parses output (validating Pydantic schemas if complete_json was called)
      │
      ▼
8. Parsed result is returned to Service
```

---

## 3. Prompt Registry

All system prompts reside in [app/ai/prompts.py](file:///c:/Users/91637/Desktop/Business%20Project/hiring-radar/app/ai/prompts.py). Each registered prompt must define:
* **Identifier**: Unique name representing the domain (e.g. `resume_match`).
* **Version**: Numeric suffix representing the template version (e.g. `v1`).
* **Description**: Human-readable purpose.
* **System Prompt Template**: The raw instruction text.

### Available Prompts
* `enrichment.v1`
* `company_score.v1`
* `research.v1`
* `resume_match.v1`
* `resume_suggestions.v1`
* `outreach_email.v1`
* `outreach_subject.v1`
* `agent.v1`

---

## 4. Future Providers

The AI Gateway has been architected to make the additions of alternative LLM engines (like OpenAI SDK, Anthropic Claude SDK, local Ollama endpoints, or Google Gemini API) straightforward:

1. **Implement client**: Create a new client class under `app/ai/client.py` (e.g. `OllamaClient`).
2. **Update resolution**: Map provider configurations in `app/ai/models.py`.
3. **Configure Gateway**: Instantiate the correct client inside `AiGateway._get_client()` based on a provider configuration value (e.g. `settings.ai_provider`).
4. **No Service changes**: Because services only invoke `ai_gateway.complete()`, they remain entirely unaffected by changes to underlying SDKs and providers.
