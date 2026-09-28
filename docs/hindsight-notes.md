# Hindsight SDK Verified Signatures & Notes

Verified against installed `hindsight-client` version `0.10.1`.

## Core Classes & Methods

### Initialization
```python
from hindsight_client import Hindsight

client = Hindsight(
    base_url=os.environ.get("HINDSIGHT_BASE_URL", "https://api.hindsight.vectorize.io"),
    api_key=os.environ.get("HINDSIGHT_API_KEY"),
    timeout=30.0,
)
```

### Bank Creation (`create_bank` / `acreate_bank`)
```python
await client.acreate_bank(
    bank_id="recall-incidents",
    name="Recall Incident Memory",
    mission="Recall past incident root causes, troubleshooting steps, and resolution outcomes to assist on-call engineers.",
    disposition={"skepticism": 3, "literalism": 3, "empathy": 1},
)
```

### Retain Single Item (`retain` / `aretain`)
```python
await client.aretain(
    bank_id="recall-incidents",
    content="Log or text describing incident...",
    timestamp=datetime_obj, # datetime instance
    context="incident_record",
    document_id="incident-INC-001",
    metadata={"service": "checkout-api", "severity": "SEV-1"}, # All values MUST be str
    tags=["incident", "checkout-api"],
    retain_async=False, # Set False for outcome retention so next recall sees it
)
```

### Retain Batch (`retain_batch` / `aretain_batch`)
```python
items = [
    {
        "content": "Log or text content...",
        "timestamp": "2024-01-15T10:30:00Z", # string ISO or datetime
        "context": "incident_record",
        "metadata": {"service": "payments-svc", "severity": "SEV-2"},
        "tags": ["incident", "payments-svc"],
    },
    ...
]

await client.aretain_batch(
    bank_id="recall-incidents",
    items=items,
    document_id="seed-incidents-batch",
    retain_async=False,
)
```

### Recall (`recall` / `arecall`)
```python
response = await client.arecall(
    bank_id="recall-incidents",
    query="Error log text or user alert",
    types=["world", "experience", "observation"],
    budget="mid",
    max_tokens=4096,
    include_chunks=True,
    include_source_facts=True,
    tags=None,
    prefer_observations=True,
)
```

### Response Object Structure (`RecallResponse`)
- `results`: List of `RecallResult` objects
- Each result object attributes:
  - `id`: str
  - `text`: str
  - `type`: str (`world` | `experience` | `observation`)
  - `context`: str | None
  - `metadata`: dict[str, Any] | None
  - `tags`: list[str] | None
  - `entities`: list[dict[str, str]] | None
  - `occurred_start`: str | None
  - `mentioned_at`: str | None
  - `document_id`: str | None
  - `chunk_id`: str | None
  - `source_fact_ids`: list[str] | None
  - `scores`: dict[str, float] (`final`, `reranker`, `semantic`, `keyword`)

### List Memories / Observations (`list_memories` / `alist_memories`)
```python
response = await client.alist_memories(
    bank_id="recall-incidents",
    type="observation",
    limit=100,
)
```
