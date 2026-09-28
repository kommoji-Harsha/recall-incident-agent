# Hindsight SDK Verification & Notes

This document records the verified Python SDK signatures and API observations for `hindsight-client` (v0.10.1).

## Installed Package Version
- `hindsight-client == 0.10.1`

## Client Initialization
```python
from hindsight_client import Hindsight

client = Hindsight(
    base_url=os.environ.get("HINDSIGHT_BASE_URL", "https://api.hindsight.vectorize.io"),
    api_key=os.environ.get("HINDSIGHT_API_KEY"),
    timeout=10.0
)
```

## Verified Method Signatures

### 1. Bank Creation / Bootstrap (`create_bank` / `acreate_bank`)
```python
client.create_bank(
    bank_id: str,
    name: str | None = None,
    mission: str | None = None,
    disposition_skepticism: int | None = None,
    disposition_literalism: int | None = None,
    disposition_empathy: int | None = None,
    disposition: dict[str, float] | None = None,
    enable_observations: bool | None = None,
    ...
)
```

### 2. Retain (`retain` / `aretain`)
```python
client.retain(
    bank_id: str,
    content: str | list[dict[str, Any]],
    timestamp: datetime.datetime | None = None,
    context: str | None = None,
    document_id: str | None = None,
    metadata: dict[str, str] | None = None,
    entities: list[dict[str, str]] | None = None,
    resolve_entities: bool | None = None,
    tags: list[str] | None = None,
    update_mode: str | None = None,
    retain_async: bool = False,
    operation_id: str | None = None
)
```

### 3. Retain Batch (`retain_batch` / `aretain_batch`)
```python
client.retain_batch(
    bank_id: str,
    items: list[dict[str, Any]],
    document_id: str | None = None,
    document_tags: list[str] | None = None,
    retain_async: bool = False,
    operation_id: str | None = None
)
```

### 4. Recall (`recall` / `arecall`)
```python
client.recall(
    bank_id: str,
    query: str,
    types: list[str] | None = None,
    max_tokens: int = 4096,
    budget: str = 'mid',
    trace: bool = False,
    query_timestamp: str | None = None,
    include_entities: bool = False,
    max_entity_tokens: int = 500,
    include_chunks: bool = False,
    max_chunk_tokens: int = 8192,
    include_source_facts: bool = False,
    max_source_facts_tokens: int = 4096,
    tags: list[str] | None = None,
    tags_match: Literal['any', 'all', 'any_strict', 'all_strict', 'exact'] = 'any',
    tag_groups: list[dict[str, Any]] | None = None,
    prefer_observations: bool = False,
    min_scores: dict[str, float] | None = None,
    temporal_window: dict[str, Any] | None = None
)
```

### 5. Observations / Mental Models (`list_mental_models` / `alist_mental_models`)
```python
client.list_mental_models(
    bank_id: str,
    tags: list[str] | None = None,
    tags_match: Literal['any', 'all', 'exact'] | None = None,
    detail: Literal['metadata', 'content', 'full'] | None = None,
    limit: int | None = None,
    offset: int | None = None
)
```
