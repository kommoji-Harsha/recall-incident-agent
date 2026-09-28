from datetime import datetime
from typing import Any, Protocol

from pydantic import BaseModel, Field


class RecalledMemory(BaseModel):
    id: str
    text: str
    type: str  # "world" | "experience" | "observation"
    context: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list)
    entities: list[dict[str, str]] = Field(default_factory=list)
    occurred_start: str | None = None
    mentioned_at: str | None = None
    document_id: str | None = None
    chunk_id: str | None = None
    source_fact_ids: list[str] = Field(default_factory=list)
    scores: dict[str, float] = Field(default_factory=dict)
    source_incident_id: str | None = None


class Observation(BaseModel):
    id: str
    text: str
    context: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list)
    occurred_start: str | None = None


class MemoryBackend(Protocol):
    async def bootstrap(self) -> None:
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
