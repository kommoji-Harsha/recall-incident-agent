from datetime import datetime
from typing import Any, Protocol, Self

from pydantic import BaseModel, Field


class RecalledMemory(BaseModel):
    id: str
    text: str
    type: str  # "world" | "experience" | "observation"
    context: str | None = None
    metadata: dict[str, str] = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list)
    entities: list[str] = Field(default_factory=list)
    occurred_start: str | None = None
    mentioned_at: str | None = None
    document_id: str | None = None
    chunk_id: str | None = None
    source_fact_ids: list[str] = Field(default_factory=list)
    scores: dict[str, float | None] = Field(default_factory=dict)
    source_incident_id: str | None = None

    @classmethod
    def from_sdk(cls, result: Any) -> Self:
        # If already RecalledMemory instance
        if isinstance(result, cls):
            return result

        # Convert SDK result object to dict
        if hasattr(result, "model_dump"):
            raw_dict = result.model_dump()
        elif hasattr(result, "to_dict"):
            raw_dict = result.to_dict()
        elif isinstance(result, dict):
            raw_dict = result
        else:
            raw_dict = {
                "id": str(getattr(result, "id", "")),
                "text": str(getattr(result, "text", "")),
                "type": str(getattr(result, "type", "world")),
                "context": getattr(result, "context", None),
                "metadata": getattr(result, "metadata", {}) or {},
                "tags": getattr(result, "tags", []) or [],
                "entities": getattr(result, "entities", []) or [],
                "occurred_start": getattr(result, "occurred_start", None),
                "mentioned_at": getattr(result, "mentioned_at", None),
                "document_id": getattr(result, "document_id", None),
                "chunk_id": getattr(result, "chunk_id", None),
                "source_fact_ids": getattr(result, "source_fact_ids", []) or [],
                "scores": getattr(result, "scores", {}) or {},
            }

        scores_raw = raw_dict.get("scores") or {}
        if hasattr(scores_raw, "model_dump"):
            scores_dict = scores_raw.model_dump()
        elif hasattr(scores_raw, "to_dict"):
            scores_dict = scores_raw.to_dict()
        elif isinstance(scores_raw, dict):
            scores_dict = scores_raw
        else:
            scores_dict = {}

        scores_clean: dict[str, float | None] = {
            "final": scores_dict.get("final"),
            "reranker": scores_dict.get("reranker"),
            "semantic": scores_dict.get("semantic"),
            "keyword": scores_dict.get("keyword"),
        }

        metadata_raw = raw_dict.get("metadata") or {}
        metadata_clean = {str(k): str(v) for k, v in metadata_raw.items()}

        entities_raw = raw_dict.get("entities") or []
        entities_clean: list[str] = []
        for e in entities_raw:
            if isinstance(e, str):
                entities_clean.append(e)
            elif isinstance(e, dict):
                entities_clean.append(str(e.get("text", e.get("name", str(e)))))
            else:
                entities_clean.append(str(e))

        doc_id = raw_dict.get("document_id")

        # Derive source incident ID
        src_inc_id = metadata_clean.get("incident_id") or metadata_clean.get("source_incident_id")
        if not src_inc_id and doc_id:
            import re
            match = re.search(r"INC-\d+", str(doc_id))
            if match:
                src_inc_id = match.group(0)

        return cls(
            id=str(raw_dict.get("id", "")),
            text=str(raw_dict.get("text", "")),
            type=str(raw_dict.get("type", "world")),
            context=raw_dict.get("context"),
            metadata=metadata_clean,
            tags=[str(t) for t in (raw_dict.get("tags") or [])],
            entities=entities_clean,
            occurred_start=raw_dict.get("occurred_start"),
            mentioned_at=raw_dict.get("mentioned_at"),
            document_id=doc_id,
            chunk_id=raw_dict.get("chunk_id"),
            source_fact_ids=[str(f) for f in (raw_dict.get("source_fact_ids") or [])],
            scores=scores_clean,
            source_incident_id=src_inc_id,
        )


class Observation(BaseModel):
    id: str
    text: str
    context: str | None = None
    metadata: dict[str, str] = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list)
    occurred_start: str | None = None


class MemoryBackend(Protocol):
    async def bootstrap(self) -> None:
        ...

    async def ping(self) -> bool:
        ...

    async def retain_incident(
        self,
        incident_id: str,
        content: str,
        timestamp: datetime,
        context: str,
        metadata: dict[str, str],
        tags: list[str],
    ) -> str:
        ...

    async def retain_outcome(
        self,
        analysis_id: str,
        content: str,
        timestamp: datetime,
        metadata: dict[str, str],
    ) -> str:
        ...

    async def retain_postmortem(
        self,
        postmortem_id: str,
        content: str,
        timestamp: datetime,
        metadata: dict[str, str],
    ) -> str:
        ...

    async def recall_similar(
        self,
        query: str,
        budget: str = "mid",
        max_tokens: int = 4096,
        prefer_observations: bool = True,
    ) -> list[RecalledMemory]:
        ...

    async def list_observations(self, limit: int = 50) -> list[Observation]:
        ...

    async def close(self) -> None:
        ...
