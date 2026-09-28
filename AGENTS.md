# AGENTS.md - Instructions and Rules for Working on Recall

## Core Rules & Working Agreement
- **Forbidden words:** Never use forbidden competition/event words anywhere in the repository.
- **Secrets:** Never commit secrets or API keys.
- **Offline testing:** All tests must pass completely OFFLINE without network requests or API keys, using a test-only `FakeMemory` implementation behind the `MemoryBackend` Protocol.
- **Strict production behavior:** In running production mode, the backend must use real Hindsight Cloud and real Groq services, and must **never** silently fall back to a fake memory implementation unless `USE_FAKE_MEMORY=true` is explicitly set.
- **Tech stack:** Python 3.11+, FastAPI, Pydantic v2, fully typed (`mypy` clean), `ruff`, `pytest`, official `groq` SDK, official `hindsight-client`.

## Hindsight SDK Rules
- Always use `from hindsight_client import Hindsight`. Never hand-roll HTTP requests or invent unverified API endpoints/parameters.
- The installed `hindsight-client` Python SDK signatures are the single source of truth.
- Client instantiation: `Hindsight(base_url=os.environ.get("HINDSIGHT_BASE_URL", "https://api.hindsight.vectorize.io"), api_key=os.environ["HINDSIGHT_API_KEY"], timeout=...)`.
- Use async variants (`aretain`, `arecall`, `aretain_batch`, `acreate_bank`, `aclose`) in FastAPI endpoints and async agent operations.
- Documented surface:
  - `create_bank(bank_id, name, mission, disposition, ...)`
  - `retain(bank_id, content, timestamp, context, document_id, metadata, tags, retain_async, ...)`
  - `retain_batch(bank_id, items, document_id, document_tags, retain_async, ...)`
  - `recall(bank_id, query, types, budget, max_tokens, include_chunks, include_source_facts, tags, tags_match, prefer_observations, query_timestamp, ...)`
- Recall result fields: `id`, `text`, `type` (`world`|`experience`|`observation`), `context`, `metadata`, `tags`, `entities`, `occurred_start`, `mentioned_at`, `document_id`, `chunk_id`, `source_fact_ids`, `scores` (`final`, `reranker`, `semantic`, `keyword`).
- Scores are **relative** per query: never hard-code a global score cutoff.
- Retain rules:
  - Always set `context` (shapes extraction).
  - Set `timestamp` to the incident's real ISO time.
  - Use stable `document_id`s (`incident-<id>`, `outcome-<analysis_id>`, `postmortem-<id>`) so re-runs are idempotent.
  - All metadata dictionary values MUST be strings.
  - Set `retain_async=False` for outcomes (so subsequent recalls immediately see them).
  - Use `retain_batch` for seed data with per-item `document_id`s.
