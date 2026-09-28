"""
backend/app/memory/protocol.py — Protocol definition for MemoryBackend.
"""

from typing import Protocol, runtime_checkable
from app.memory.models import MemoryItem, ObservationItem


@runtime_checkable
class MemoryBackend(Protocol):
    """Protocol for memory implementations (FakeMemory and HindsightMemory)."""

    async def retain_interaction(
        self,
        client_id: str,
        content: str,
        context: str,
        interaction_id: str,
        timestamp_iso: str | None = None,
        metadata: dict[str, str] | None = None,
    ) -> str:
        """Retains an interaction for a specific client."""
        ...

    async def retain_feedback(
        self,
        client_id: str,
        interaction_id: str,
        outcome: str,
        notes: str | None = None,
        timestamp_iso: str | None = None,
    ) -> str:
        """Retains user outcome feedback for a specific client synchronously."""
        ...

    async def recall_client(
        self,
        client_id: str,
        query: str,
        max_results: int = 10,
    ) -> list[MemoryItem]:
        """Recalls relevant memories strictly scoped to client_id."""
        ...

    async def list_observations(
        self,
        client_id: str,
    ) -> list[ObservationItem]:
        """Lists consolidated observations/mental models for client_id."""
        ...
