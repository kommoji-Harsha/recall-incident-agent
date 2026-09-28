from datetime import datetime
from typing import Any

from backend.app.memory.hindsight import derive_source_incident_id
from backend.app.memory.protocol import MemoryBackend, Observation, RecalledMemory


class FakeMemory(MemoryBackend):
    """
    Offline fake memory backend for testing without network/API keys.
    """

    def __init__(self, initial_memories: list[RecalledMemory] | None = None) -> None:
        self.memories: list[RecalledMemory] = initial_memories or []
        self.outcomes: list[dict[str, Any]] = []
        self.postmortems: list[dict[str, Any]] = []
        self.observations: list[Observation] = []
        self.bootstrapped = False
        self.ping_success = True
        self.bootstrap_error: str | None = None

    async def bootstrap(self) -> None:
        self.bootstrapped = True

    async def ping(self) -> bool:
        return self.ping_success

    async def retain_incident(
        self,
        incident_id: str,
        content: str,
        timestamp: datetime,
        context: str,
        metadata: dict[str, str],
        tags: list[str],
    ) -> str:
        doc_id = f"incident-{incident_id}"
        meta = {k: str(v) for k, v in metadata.items()}
        meta["incident_id"] = incident_id
        meta["type"] = "incident"

        rec = RecalledMemory(
            id=f"mem-{len(self.memories) + 1}",
            text=content,
            type="experience",
            context=context,
            metadata=meta,
            tags=tags,
            occurred_start=timestamp.isoformat(),
            document_id=doc_id,
            source_incident_id=incident_id,
            scores={"final": 0.9, "reranker": 0.9, "semantic": 0.9, "keyword": None},
        )
        self.memories.append(rec)
        return doc_id

    async def retain_outcome(
        self,
        analysis_id: str,
        content: str,
        timestamp: datetime,
        metadata: dict[str, str],
    ) -> str:
        doc_id = f"outcome-{analysis_id}"
        meta = {k: str(v) for k, v in metadata.items()}
        meta["analysis_id"] = analysis_id
        meta["type"] = "outcome"

        src_inc = meta.get("source_incident_id")
        rec = RecalledMemory(
            id=f"mem-outcome-{len(self.outcomes) + 1}",
            text=content,
            type="experience",
            context=f"incident outcome record for analysis {analysis_id}",
            metadata=meta,
            tags=["outcome", meta.get("result", "")],
            occurred_start=timestamp.isoformat(),
            document_id=doc_id,
            source_incident_id=src_inc,
            scores={"final": 0.95, "reranker": 0.95, "semantic": 0.95, "keyword": None},
        )
        self.memories.append(rec)
        self.outcomes.append({"analysis_id": analysis_id, "doc_id": doc_id, "metadata": meta})
        return doc_id

    async def retain_postmortem(
        self,
        postmortem_id: str,
        content: str,
        timestamp: datetime,
        metadata: dict[str, str],
    ) -> str:
        doc_id = f"postmortem-{postmortem_id}"
        meta = {k: str(v) for k, v in metadata.items()}
        meta["postmortem_id"] = postmortem_id
        meta["type"] = "postmortem"

        rec = RecalledMemory(
            id=f"mem-pm-{len(self.postmortems) + 1}",
            text=content,
            type="world",
            context=f"postmortem record {postmortem_id}",
            metadata=meta,
            tags=["postmortem"],
            occurred_start=timestamp.isoformat(),
            document_id=doc_id,
            source_incident_id=derive_source_incident_id(doc_id, meta),
            scores={"final": 0.85, "reranker": 0.85, "semantic": 0.85, "keyword": None},
        )
        self.memories.append(rec)
        self.postmortems.append({"postmortem_id": postmortem_id, "content": content})
        return doc_id

    async def recall_similar(
        self,
        query: str,
        budget: str = "mid",
        max_tokens: int = 4096,
        prefer_observations: bool = True,
    ) -> list[RecalledMemory]:
        query_words = set(query.lower().split())
        matched: list[RecalledMemory] = []
        for m in self.memories:
            text_words = set(m.text.lower().split())
            if query_words.intersection(text_words):
                matched.append(m)

        return matched if matched else self.memories

    async def list_observations(self, limit: int = 50) -> list[Observation]:
        obs = [
            Observation(
                id=m.id,
                text=m.text,
                context=m.context,
                metadata=m.metadata,
                tags=m.tags,
                occurred_start=m.occurred_start,
            )
            for m in self.memories
            if m.type == "observation"
        ]
        if not obs:
            obs = [
                Observation(
                    id="obs-1",
                    text="Database connection pool exhaustion typically occurs during traffic surges without pool scaling.",
                    tags=["database", "connection-pool"],
                ),
                Observation(
                    id="obs-2",
                    text="Redis eviction storms follow cache memory exhaustion without proper key TTLs.",
                    tags=["redis", "cache"],
                ),
            ]
        return obs[:limit]

    async def close(self) -> None:
        pass
