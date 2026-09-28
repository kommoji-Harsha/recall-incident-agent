# AGENTS.md — Rules & Guidelines for Rapport Backend

## Working Agreement
- Work in small commits on one branch; open ONE PR at the end.
- Never commit secrets. Keep `.env` gitignored and provide `.env.example`.
- All tests pass **OFFLINE** using a test-only `FakeMemory` behind a `MemoryBackend` Protocol.
- `FakeMemory` MUST honour tag-filter semantics: `any_strict` excludes untagged memories.
- The running production app must use the real Hindsight Cloud and never silently fall back to a fake.
- Do NOT use the word "hackathon" anywhere in the repository.
- Tech Stack: Python 3.11+, FastAPI, Pydantic v2, fully typed (`mypy` clean), `ruff`, `pytest`, official `groq` SDK, official `hindsight-client` SDK.

## Hindsight Rules
- Use `from hindsight_client import Hindsight`. Never hand-roll HTTP calls or invent endpoints/parameters.
- Standard client instantiation:
  ```python
  Hindsight(
      base_url=os.environ.get("HINDSIGHT_BASE_URL", "https://api.hindsight.vectorize.io"),
      api_key=os.environ["HINDSIGHT_API_KEY"],
      timeout=10.0,
  )
  ```
- Use async variants (`aretain`, `arecall`, `aclose`, `aretain_batch`, `alist_mental_models`, `acreate_bank`) in FastAPI async routes and pipeline calls.
- Verified surface:
  - `create_bank(bank_id, name, mission, disposition...)`
  - `retain(bank_id, content, context, timestamp, document_id, metadata, tags, retain_async)`
  - `retain_batch(bank_id, items, ...)`
  - `recall(bank_id, query, types, budget, max_tokens, include_chunks, include_source_facts, tags, tags_match, prefer_observations, query_timestamp)`
  - `list_mental_models(bank_id, tags, tags_match, ...)`
- Recall results: `id`, `text`, `type` (`world`|`experience`|`observation`), `context`, `metadata`, `tags`, `entities`, `occurred_start`, `mentioned_at`, `document_id`, `chunk_id`, `source_fact_ids`, `scores{final,reranker,semantic,keyword}`.
- Scores are RELATIVE per query: never hard-code a global score cutoff.
- `retain`:
  - Always set `context`.
  - Set `timestamp` to interaction's real time.
  - Stable `document_id`s (`interaction-<client>-<n>`) for idempotency.
  - Metadata values are strings.
  - Format text standard: `"Name (ISO timestamp): text"`.
  - Use `retain_async=False` for feedback so the next recall immediately sees it.
  - Use `retain_batch` for seed loading.
- Client Isolation (Critical):
  - Tag every retained item `client:<client_id>`.
  - Recall for a client with `tags=["client:<client_id>"]` and `tags_match="any_strict"` (default `"any"` also returns untagged memories).
