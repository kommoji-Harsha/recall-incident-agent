# Hindsight SDK Verified Signatures & Types

Verified by inspecting installed `hindsight-client` version `0.10.1` package.

## Core Classes & Models

### `RecallResult` Model
- `id`: `str`
- `text`: `str`
- `type`: `str | None` (`"world" | "experience" | "observation"`)
- `entities`: `list[str] | None`
- `context`: `str | None`
- `occurred_start`: `str | None`
- `occurred_end`: `str | None`
- `mentioned_at`: `str | None`
- `document_id`: `str | None`
- `metadata`: `dict[str, str] | None`
- `chunk_id`: `str | None`
- `tags`: `list[str] | None`
- `source_fact_ids`: `list[str] | None`
- `scores`: `RecallScores | None`

### `RecallScores` Model
- `final`: `float`
- `reranker`: `float | None`
- `semantic`: `float | None`
- `keyword`: `float | None`

## Method Signatures

### `Hindsight.__init__`
```python
Hindsight(base_url: str, api_key: str | None = None, timeout: float = 300.0)
```

### `Hindsight.aretain`
```python
await client.aretain(
    bank_id: str,
    content: str,
    timestamp: datetime | None = None,
    context: str | None = None,
    document_id: str | None = None,
    metadata: dict[str, str] | None = None,
    tags: list[str] | None = None,
    retain_async: bool = False,
)
```

### `Hindsight.aretain_batch`
```python
await client.aretain_batch(
    bank_id: str,
    items: list[dict[str, Any]], # Each item dict accepts 'document_id', 'content', 'timestamp', 'context', 'metadata', 'tags'
    document_id: str | None = None, # Fallback batch document_id
    retain_async: bool = False,
)
```

### `Hindsight.arecall`
```python
await client.arecall(
    bank_id: str,
    query: str,
    types: list[str] | None = None,
    budget: str = 'mid',
    max_tokens: int = 4096,
    include_chunks: bool = False,
    include_source_facts: bool = False,
    prefer_observations: bool = False,
) -> RecallResponse
```

### `Hindsight.alist_memories`
```python
await client.alist_memories(
    bank_id: str,
    type: str | None = None,
    limit: int = 100,
) -> ListMemoryUnitsResponse # Contains `.items` list
```
