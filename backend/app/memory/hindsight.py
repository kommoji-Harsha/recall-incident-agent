import logging
from datetime import datetime
from typing import Any

from hindsight_client import Hindsight

from backend.app.memory.protocol import MemoryBackend, Observation, RecalledMemory

logger = logging.getLogger(__name__)


def derive_source_incident_id(document_id: str | None, metadata: dict[str, Any] | None) -> str | None:
    if metadata and metadata.get("incident_id"):
        return str(metadata["incident_id"])
    if metadata and metadata.get("source_incident_id"):
        return str(metadata["source_incident_id"])
    if document_id:
        import re
        match = re.search(r"INC-\d+", str(document_id))
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
        self.bootstrap_error: str | None = None

    async def bootstrap(self) -> None:
        try:
            await self.client.acreate_bank(
                bank_id=self.bank_id,
                name="Recall Incident Memory Bank",
                mission="Recall past incident root causes, troubleshooting steps, and resolution outcomes to assist on-call engineers.",
                disposition={"skepticism": 3, "literalism": 3, "empathy": 1},
            )
            self.bootstrap_error = None
        except Exception as exc:
            err_msg = str(exc)
            # Ignore ONLY if bank already exists
            if "already exists" in err_msg.lower() or "409" in err_msg:
                self.bootstrap_error = None
            else:
                logger.error(f"Hindsight bank creation failed: {exc}")
                self.bootstrap_error = err_msg

    async def ping(self) -> bool:
        try:
            await self.client.arecall(
                bank_id=self.bank_id,
                query="ping",
                budget="low",
                max_tokens=10,
            )
            return True
        except Exception as exc:
            logger.warning(f"Hindsight ping probe failed: {exc}")
            return False

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
            retain_async=False,
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
            memories.append(RecalledMemory.from_sdk(r))

        return memories

    async def list_observations(self, limit: int = 50) -> list[Observation]:
        # Must NOT silently swallow errors: raise on failure
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
                    rec = RecalledMemory.from_sdk(r)
                    obs_list.append(
                        Observation(
                            id=rec.id,
                            text=rec.text,
                            context=rec.context,
                            metadata=rec.metadata,
                            tags=rec.tags,
                            occurred_start=rec.occurred_start,
                        )
                    )
            if obs_list:
                return obs_list[:limit]
        except Exception as exc:
            logger.warning(f"arecall for observations failed, attempting alist_memories fallback: {exc}")

        # Fallback to alist_memories
        mem_res = await self.client.alist_memories(
            bank_id=self.bank_id,
            type="observation",
            limit=limit,
        )
        # Check .items (not .units) as per SDK signature
        mem_items = getattr(mem_res, "items", None)
        if mem_items is None:
            mem_items = getattr(mem_res, "units", []) or []

        obs_list = []
        for u in mem_items:
            u_meta = getattr(u, "metadata", {}) or {}
            meta_clean = {str(k): str(v) for k, v in u_meta.items()}
            obs_list.append(
                Observation(
                    id=str(getattr(u, "id", "")),
                    text=str(getattr(u, "text", "")),
                    context=getattr(u, "context", None),
                    metadata=meta_clean,
                    tags=getattr(u, "tags", []) or [],
                    occurred_start=getattr(u, "occurred_start", None),
                )
            )
        return obs_list

    async def close(self) -> None:
        await self.client.aclose()
