import re
from datetime import datetime
from typing import Any

from hindsight_client import Hindsight

from backend.app.memory.protocol import MemoryBackend, Observation, RecalledMemory


def derive_source_incident_id(document_id: str | None, metadata: dict[str, Any] | None) -> str | None:
    if metadata and metadata.get("incident_id"):
        return str(metadata["incident_id"])
    if metadata and metadata.get("source_incident_id"):
        return str(metadata["source_incident_id"])
    if document_id:
        match = re.search(r"INC-\d+", document_id)
        if match:
            return match.group(0)
    return None


class HindsightMemory(MemoryBackend):
    def __init__(
        self,
        base_url: str = "https://api.hindsight.vectorize.io",
        api_key: str = "",
        bank_id: str = "recall-incidents",
        timeout: float = 15.0,
    ) -> None:
        self.base_url = base_url
        self.api_key = api_key
        self.bank_id = bank_id
        self.timeout = timeout
        self.client = Hindsight(
            base_url=self.base_url,
            api_key=self.api_key,
            timeout=self.timeout,
        )

    async def bootstrap(self) -> None:
        try:
            await self.client.acreate_bank(
                bank_id=self.bank_id,
                name="Recall Incident Memory Bank",
                mission="Recall past incident root causes, troubleshooting steps, and resolution outcomes to assist on-call engineers.",
                disposition={"skepticism": 3, "literalism": 3, "empathy": 1},
            )
        except Exception:
            # Bank already exists or API warning; proceed safely
            pass

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

        res = await self.client.aretain(
            bank_id=self.bank_id,
            content=content,
            timestamp=timestamp,
            context=context,
            document_id=doc_id,
            metadata=meta,
            tags=tags,
            retain_async=False,
        )
        return str(res.id if hasattr(res, "id") and res.id else doc_id)

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

        res = await self.client.aretain(
            bank_id=self.bank_id,
            content=content,
            timestamp=timestamp,
            context=f"incident outcome record for analysis {analysis_id}",
            document_id=doc_id,
            metadata=meta,
            tags=["outcome", meta.get("result", "")],
            retain_async=False,  # Outcome retain must be synchronous so next recall sees it immediately
        )
        return str(res.id if hasattr(res, "id") and res.id else doc_id)

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

        res = await self.client.aretain(
            bank_id=self.bank_id,
            content=content,
            timestamp=timestamp,
            context=f"postmortem record {postmortem_id}",
            document_id=doc_id,
            metadata=meta,
            tags=["postmortem"],
            retain_async=False,
        )
        return str(res.id if hasattr(res, "id") and res.id else doc_id)

    async def recall_similar(
        self,
        query: str,
        budget: str = "mid",
        max_tokens: int = 4096,
        prefer_observations: bool = True,
    ) -> list[RecalledMemory]:
        res = await self.client.arecall(
            bank_id=self.bank_id,
            query=query,
            types=["world", "experience", "observation"],
            budget=budget,
            max_tokens=max_tokens,
            include_chunks=True,
            include_source_facts=True,
            prefer_observations=prefer_observations,
        )

        memories: list[RecalledMemory] = []
        raw_results = getattr(res, "results", []) or []
        for r in raw_results:
            doc_id = getattr(r, "document_id", None)
            meta = getattr(r, "metadata", {}) or {}
            source_inc_id = derive_source_incident_id(doc_id, meta)

            memories.append(
                RecalledMemory(
                    id=str(getattr(r, "id", "")),
                    text=str(getattr(r, "text", "")),
                    type=str(getattr(r, "type", "world")),
                    context=getattr(r, "context", None),
                    metadata=meta,
                    tags=getattr(r, "tags", []) or [],
                    entities=getattr(r, "entities", []) or [],
                    occurred_start=getattr(r, "occurred_start", None),
                    mentioned_at=getattr(r, "mentioned_at", None),
                    document_id=doc_id,
                    chunk_id=getattr(r, "chunk_id", None),
                    source_fact_ids=getattr(r, "source_fact_ids", []) or [],
                    scores=getattr(r, "scores", {}) or {},
                    source_incident_id=source_inc_id,
                )
            )

        return memories

    async def list_observations(self, limit: int = 50) -> list[Observation]:
        # Fetch observations via recall(types=["observation"], include_source_facts=True)
        # or alist_memories
        try:
            res = await self.client.arecall(
                bank_id=self.bank_id,
                query="system observations performance incidents issues patterns",
                types=["observation"],
                budget="mid",
                max_tokens=4096,
                include_source_facts=True,
                prefer_observations=True,
            )
            raw_results = getattr(res, "results", []) or []
            obs_list: list[Observation] = []
            for r in raw_results:
                if getattr(r, "type", "") == "observation":
                    obs_list.append(
                        Observation(
                            id=str(getattr(r, "id", "")),
                            text=str(getattr(r, "text", "")),
                            context=getattr(r, "context", None),
                            metadata=getattr(r, "metadata", {}) or {},
                            tags=getattr(r, "tags", []) or [],
                            occurred_start=getattr(r, "occurred_start", None),
                        )
                    )
            if obs_list:
                return obs_list[:limit]
        except Exception:
            pass

        # Fallback to alist_memories if available
        try:
            mem_res = await self.client.alist_memories(
                bank_id=self.bank_id,
                type="observation",
                limit=limit,
            )
            mem_units = getattr(mem_res, "units", []) or []
            obs_list = []
            for u in mem_units:
                obs_list.append(
                    Observation(
                        id=str(getattr(u, "id", "")),
                        text=str(getattr(u, "text", "")),
                        context=getattr(u, "context", None),
                        metadata=getattr(u, "metadata", {}) or {},
                        tags=getattr(u, "tags", []) or [],
                        occurred_start=getattr(u, "occurred_start", None),
                    )
                )
            return obs_list
        except Exception:
            return []

    async def close(self) -> None:
        await self.client.aclose()
