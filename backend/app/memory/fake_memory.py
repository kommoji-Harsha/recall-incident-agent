"""
backend/app/memory/fake_memory.py — Test-only FakeMemory implementation.
Honours tag-filter semantics: any_strict excludes untagged memories.
"""

from typing import Any
from app.memory.models import MemoryItem, ObservationItem


class FakeMemory:
    """FakeMemory implementation for offline testing."""

    def __init__(self) -> None:
        self.memories: list[dict[str, Any]] = []
        self.observations: dict[str, list[ObservationItem]] = {}

    async def retain_interaction(
        self,
        client_id: str,
        content: str,
        context: str,
        interaction_id: str,
        timestamp_iso: str | None = None,
        metadata: dict[str, str] | None = None,
    ) -> str:
        meta = metadata.copy() if metadata else {}
        meta["client_id"] = client_id
        meta["source_interaction_id"] = interaction_id

        doc_id = interaction_id if interaction_id.startswith("interaction-") else f"interaction-{client_id}-{interaction_id}"
        mem_id = f"mem-{interaction_id}"

        self.memories = [m for m in self.memories if m.get("document_id") != doc_id]

        entry = {
            "id": mem_id,
            "text": content,
            "type": "experience",
            "context": context,
            "metadata": meta,
            "tags": [f"client:{client_id}"],
            "document_id": doc_id,
            "occurred_start": timestamp_iso,
            "mentioned_at": timestamp_iso,
            "scores": {"final": 0.95, "semantic": 0.90, "keyword": 0.85},
        }
        self.memories.append(entry)
        return mem_id

    async def retain_feedback(
        self,
        client_id: str,
        interaction_id: str,
        outcome: str,
        notes: str | None = None,
        timestamp_iso: str | None = None,
    ) -> str:
        fb_doc_id = f"feedback-{interaction_id}"
        mem_id = f"mem-{fb_doc_id}"

        content = f"Feedback for interaction {interaction_id}: Outcome={outcome}."
        if notes:
            content += f" Notes: {notes}"

        meta = {
            "client_id": client_id,
            "source_interaction_id": interaction_id,
            "feedback_outcome": outcome,
        }
        if notes:
            meta["feedback_notes"] = notes

        self.memories = [m for m in self.memories if m.get("document_id") != fb_doc_id]

        entry = {
            "id": mem_id,
            "text": content,
            "type": "experience",
            "context": "User interaction feedback",
            "metadata": meta,
            "tags": [f"client:{client_id}"],
            "document_id": fb_doc_id,
            "occurred_start": timestamp_iso,
            "mentioned_at": timestamp_iso,
            "scores": {"final": 0.98, "semantic": 0.95, "keyword": 0.90},
        }
        self.memories.append(entry)
        return mem_id

    async def recall_client(
        self,
        client_id: str,
        query: str,
        max_results: int = 10,
    ) -> list[MemoryItem]:
        target_tag = f"client:{client_id}"
        results: list[MemoryItem] = []

        for m in self.memories:
            tags = m.get("tags", [])
            if target_tag not in tags:
                continue

            meta = m.get("metadata", {})
            src_id = meta.get("source_interaction_id") or m.get("document_id") or m["id"]

            results.append(
                MemoryItem(
                    id=m["id"],
                    text=m["text"],
                    type=m.get("type", "experience"),
                    context=m.get("context"),
                    metadata=m.get("metadata", {}),
                    tags=m.get("tags", []),
                    document_id=m.get("document_id"),
                    source_interaction_id=str(src_id),
                    occurred_start=m.get("occurred_start"),
                    mentioned_at=m.get("mentioned_at"),
                    scores=m.get("scores", {}),
                )
            )

        return results[:max_results]

    async def list_observations(
        self,
        client_id: str,
    ) -> list[ObservationItem]:
        return self.observations.get(client_id, [])
