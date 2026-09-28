"""
backend/app/memory/hindsight_memory.py — Production Hindsight Cloud Memory implementation.
"""

import datetime
import logging
from hindsight_client import Hindsight
from app.memory.models import MemoryItem, ObservationItem

logger = logging.getLogger(__name__)


class HindsightMemory:
    """Production memory implementation connecting directly to Hindsight Cloud.

    NEVER silently falls back to FakeMemory in production.
    """

    def __init__(
        self,
        base_url: str,
        api_key: str,
        bank_id: str = "rapport-client-memory",
        timeout: float = 10.0,
    ) -> None:
        self.base_url = base_url
        self.api_key = api_key
        self.bank_id = bank_id
        self.timeout = timeout
        self.client = Hindsight(
            base_url=base_url,
            api_key=api_key,
            timeout=timeout,
        )

    async def ensure_bank_exists(self) -> None:
        """Ensures the Hindsight bank exists with appropriate client memory mission."""
        try:
            await self.client.acreate_bank(
                bank_id=self.bank_id,
                name="Rapport Client Memory Bank",
                mission=(
                    "Maintain detailed long-term memory of client communications, preferences, payment habits, "
                    "scope changes, channel switches, and explicit constraints for freelancers."
                ),
                enable_observations=True,
            )
        except Exception as ex:
            logger.info("Hindsight bank existence check notice: %s", ex)

    async def retain_interaction(
        self,
        client_id: str,
        content: str,
        context: str,
        interaction_id: str,
        timestamp_iso: str | None = None,
        metadata: dict[str, str] | None = None,
    ) -> str:
        doc_id = interaction_id if interaction_id.startswith("interaction-") else f"interaction-{client_id}-{interaction_id}"
        meta = metadata.copy() if metadata else {}
        meta["client_id"] = client_id
        meta["source_interaction_id"] = interaction_id

        dt = None
        if timestamp_iso:
            try:
                dt = datetime.datetime.fromisoformat(timestamp_iso.replace("Z", "+00:00"))
            except ValueError:
                dt = None

        res = await self.client.aretain(
            bank_id=self.bank_id,
            content=content,
            context=context,
            timestamp=dt,
            document_id=doc_id,
            metadata=meta,
            tags=[f"client:{client_id}"],
            retain_async=False,
        )
        return str(getattr(res, "id", doc_id))

    async def retain_feedback(
        self,
        client_id: str,
        interaction_id: str,
        outcome: str,
        notes: str | None = None,
        timestamp_iso: str | None = None,
    ) -> str:
        fb_doc_id = f"feedback-{interaction_id}"
        content = f"Client Feedback for interaction {interaction_id}: Outcome={outcome}."
        if notes:
            content += f" Notes: {notes}"

        meta = {
            "client_id": client_id,
            "source_interaction_id": interaction_id,
            "feedback_outcome": outcome,
        }
        if notes:
            meta["feedback_notes"] = notes

        dt = None
        if timestamp_iso:
            try:
                dt = datetime.datetime.fromisoformat(timestamp_iso.replace("Z", "+00:00"))
            except ValueError:
                dt = None

        res = await self.client.aretain(
            bank_id=self.bank_id,
            content=content,
            context="User outcome feedback for client interaction",
            timestamp=dt,
            document_id=fb_doc_id,
            metadata=meta,
            tags=[f"client:{client_id}"],
            retain_async=False,
        )
        return str(getattr(res, "id", fb_doc_id))

    async def recall_client(
        self,
        client_id: str,
        query: str,
        max_results: int = 10,
    ) -> list[MemoryItem]:
        response = await self.client.arecall(
            bank_id=self.bank_id,
            query=query,
            tags=[f"client:{client_id}"],
            tags_match="any_strict",
            prefer_observations=True,
        )

        items: list[MemoryItem] = []
        for raw in response:
            meta = getattr(raw, "metadata", {}) or {}
            doc_id = getattr(raw, "document_id", None)
            raw_id = getattr(raw, "id", "")

            src_id = meta.get("source_interaction_id") or doc_id or raw_id

            scores_raw = getattr(raw, "scores", {}) or {}
            scores_dict = {k: float(v) for k, v in scores_raw.items()} if isinstance(scores_raw, dict) else {}

            items.append(
                MemoryItem(
                    id=str(raw_id),
                    text=getattr(raw, "text", ""),
                    type=getattr(raw, "type", "experience"),
                    context=getattr(raw, "context", None),
                    metadata={str(k): str(v) for k, v in meta.items()},
                    tags=list(getattr(raw, "tags", []) or []),
                    document_id=doc_id,
                    source_interaction_id=str(src_id),
                    occurred_start=getattr(raw, "occurred_start", None),
                    mentioned_at=getattr(raw, "mentioned_at", None),
                    scores=scores_dict,
                )
            )

        return items[:max_results]

    async def list_observations(
        self,
        client_id: str,
    ) -> list[ObservationItem]:
        try:
            raw_models = await self.client.alist_mental_models(
                bank_id=self.bank_id,
                tags=[f"client:{client_id}"],
                tags_match="exact",
            )
            obs_list: list[ObservationItem] = []
            if isinstance(raw_models, list):
                for rm in raw_models:
                    obs_list.append(
                        ObservationItem(
                            id=getattr(rm, "id", None),
                            name=getattr(rm, "name", None),
                            description=getattr(rm, "description", None),
                            content=getattr(rm, "content", None),
                            tags=list(getattr(rm, "tags", []) or []),
                            metadata=dict(getattr(rm, "metadata", {}) or {}),
                        )
                    )
            return obs_list
        except Exception as ex:
            logger.warning("Error listing mental models for client %s: %s", client_id, ex)
            return []
