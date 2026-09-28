"""
backend/app/memory/models.py — Data models for Rapport memory layer.
"""

from typing import Any
from pydantic import BaseModel, Field


class MemoryItem(BaseModel):
    id: str
    text: str
    type: str = Field(description="Type of memory: world, experience, or observation")
    context: str | None = None
    metadata: dict[str, str] = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list)
    document_id: str | None = None
    source_interaction_id: str = Field(
        description="Source interaction ID derived from metadata or document_id"
    )
    occurred_start: str | None = None
    mentioned_at: str | None = None
    scores: dict[str, float] = Field(default_factory=dict)


class ObservationItem(BaseModel):
    id: str | None = None
    name: str | None = None
    description: str | None = None
    content: str | None = None
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
