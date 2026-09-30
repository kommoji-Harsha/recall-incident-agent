import asyncio
import os
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any, AsyncGenerator

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware

from backend.app.agent.models import (
    AnalyzeRequest,
    AnalyzeResponse,
    OutcomeRequest,
    PostmortemRequest,
    PostmortemResponse,
)
from backend.app.agent.pipeline import IncidentAgentPipeline
from backend.app.db import Database
from backend.app.llm.client import LLMProvider, get_llm_provider
from backend.app.memory.fake import FakeMemory
from backend.app.memory.hindsight import HindsightMemory
from backend.app.memory.protocol import MemoryBackend

# Global instances
memory_backend: MemoryBackend | None = None
llm_provider: LLMProvider | None = None
db: Database | None = None


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    global memory_backend, llm_provider, db

    db = Database()

    api_key = os.environ.get("HINDSIGHT_API_KEY", "").strip()
    use_fake = os.environ.get("USE_FAKE_MEMORY", "false").lower() == "true"

    if use_fake:
        memory_backend = FakeMemory()
    elif not api_key:
        raise RuntimeError("HINDSIGHT_API_KEY environment variable is required unless USE_FAKE_MEMORY=true is explicitly set.")
    else:
        memory_backend = HindsightMemory(
            base_url=os.environ.get("HINDSIGHT_BASE_URL", "https://api.hindsight.vectorize.io"),
            api_key=api_key,
            bank_id=os.environ.get("HINDSIGHT_BANK_ID", "recall-incidents"),
            timeout=float(os.environ.get("HINDSIGHT_TIMEOUT_SECONDS", "15.0")),
        )

    await memory_backend.bootstrap()

    llm_provider = get_llm_provider()

    yield

    if memory_backend:
        await memory_backend.close()


app = FastAPI(
    title="Recall Backend",
    description="Recall incident-response agent backend API",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
async def health_check() -> dict[str, Any]:
    hindsight_reachable = False
    bootstrap_error = getattr(memory_backend, "bootstrap_error", None)

    if memory_backend and bootstrap_error is None:
        try:
            hindsight_reachable = await memory_backend.ping()
        except Exception:
            hindsight_reachable = False

    llm_configured = bool(llm_provider and llm_provider.api_key)

    return {
        "status": "ok" if (hindsight_reachable or isinstance(memory_backend, FakeMemory)) else "degraded",
        "hindsight_reachable": hindsight_reachable,
        "bootstrap_error": bootstrap_error,
        "groq_configured": llm_configured,
        "llm_provider": os.environ.get("LLM_PROVIDER", "groq"),
        "primary_model": llm_provider.primary_model if llm_provider else None,
        "fallback_model": llm_provider.fallback_model if llm_provider else None,
    }


@app.post("/api/analyze", response_model=AnalyzeResponse)
async def analyze_alert(req: AnalyzeRequest) -> AnalyzeResponse:
    if not memory_backend or not llm_provider or not db:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Backend services not initialized",
        )

    if len(req.alert_text) > 100000:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Alert text exceeds max length limit of 100,000 characters",
        )

    pipeline = IncidentAgentPipeline(memory=memory_backend, llm_client=llm_provider)
    analysis_id = f"analysis-{uuid.uuid4().hex[:8]}"

    if req.compare:
        mem_on_task = asyncio.create_task(
            pipeline.analyze(alert_text=req.alert_text, memory_enabled=True)
        )
        mem_off_task = asyncio.create_task(
            pipeline.analyze(alert_text=req.alert_text, memory_enabled=False)
        )
        mem_on_res, mem_off_res = await asyncio.gather(mem_on_task, mem_off_task)
    else:
        mem_on_res = await pipeline.analyze(
            alert_text=req.alert_text, memory_enabled=req.memory_enabled
        )
        mem_off_res = None

    db.save_analysis(
        analysis_id=analysis_id,
        alert_text=req.alert_text,
        memory_enabled=req.memory_enabled,
        result_data=mem_on_res.model_dump(),
    )

    return AnalyzeResponse(
        analysis_id=analysis_id,
        memory_on=mem_on_res,
        memory_off=mem_off_res,
    )


@app.post("/api/outcome")
async def record_outcome(req: OutcomeRequest) -> dict[str, Any]:
    if not memory_backend or not db:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Backend services not initialized",
        )

    analysis_record = db.get_analysis(req.analysis_id)
    if not analysis_record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Analysis with ID {req.analysis_id} not found",
        )

    result_data = analysis_record.get("result_data", {})
    sources = result_data.get("likely_root_cause", {}).get("sources", [])
    src_inc_id = sources[0] if sources else "unknown"

    content = (
        f"OUTCOME FEEDBACK for Analysis {req.analysis_id}:\n"
        f"Original Alert: {analysis_record.get('alert_text', '')[:300]}...\n"
        f"Result: {req.result.upper()}\n"
        f"User Notes: {req.notes}\n"
    )

    doc_id = f"outcome-{req.analysis_id}"
    is_new = db.save_outcome(
        analysis_id=req.analysis_id,
        result=req.result,
        notes=req.notes,
        retained_doc_id=doc_id,
    )

    if is_new:
        try:
            await memory_backend.retain_outcome(
                analysis_id=req.analysis_id,
                content=content,
                timestamp=datetime.now(timezone.utc),
                metadata={
                    "result": req.result,
                    "notes": req.notes,
                    "source_incident_id": src_inc_id,
                },
            )
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to retain outcome in memory: {exc}",
            )

    return {
        "status": "recorded",
        "analysis_id": req.analysis_id,
        "result": req.result,
        "retained_doc_id": doc_id,
        "idempotent_duplicate": not is_new,
    }


@app.post("/api/postmortem", response_model=PostmortemResponse)
async def submit_postmortem(req: PostmortemRequest) -> PostmortemResponse:
    if not memory_backend:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Backend services not initialized",
        )

    if not req.text.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Postmortem text cannot be empty",
        )

    pm_id = f"pm-{uuid.uuid4().hex[:8]}"
    content = f"Title: {req.title or 'Postmortem'}\n\n{req.text}"

    await memory_backend.retain_postmortem(
        postmortem_id=pm_id,
        content=content,
        timestamp=datetime.now(timezone.utc),
        metadata={"title": req.title or "Postmortem"},
    )

    sample_recalled = await memory_backend.recall_similar(
        query=req.title or req.text[:100],
        budget="low",
        max_tokens=1024,
    )

    recalled_sample = [
        {
            "id": m.id,
            "text": m.text[:150],
            "document_id": m.document_id,
            "type": m.type,
        }
        for m in sample_recalled[:3]
    ]

    return PostmortemResponse(
        postmortem_id=pm_id,
        status="retained",
        recalled_sample=recalled_sample,
    )


@app.get("/api/memory/observations")
async def list_memory_observations(limit: int = 50) -> dict[str, Any]:
    if not memory_backend:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Backend services not initialized",
        )

    obs = await memory_backend.list_observations(limit=limit)
    return {
        "count": len(obs),
        "observations": [o.model_dump() for o in obs],
    }
