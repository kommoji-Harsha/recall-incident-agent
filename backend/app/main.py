"""
backend/app/main.py — FastAPI web application for Rapport backend.
"""

import asyncio
import json
import logging
import os
import uuid
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator

from fastapi import FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware

from app.agent import AgentPipeline
from app.db import get_db_connection, init_db
from app.llm.client import LLMClient
from app.memory import FakeMemory, HindsightMemory, MemoryBackend
from app.schemas import (
    ClientCreate,
    ClientResponse,
    FeedbackRequest,
    FeedbackResponse,
    ImportRequest,
    ImportResponse,
    MemoryUsedItem,
    RespondRequest,
    RespondResponse,
    SingleAgentOutput,
)

logger = logging.getLogger(__name__)

memory_backend: MemoryBackend | None = None
llm_client: LLMClient | None = None


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    global memory_backend, llm_client

    init_db()

    hindsight_key = os.environ.get("HINDSIGHT_API_KEY")
    use_fake_memory = os.environ.get("USE_FAKE_MEMORY", "false").lower() in ("true", "1")

    if hindsight_key and not use_fake_memory:
        base_url = os.environ.get("HINDSIGHT_BASE_URL", "https://api.hindsight.vectorize.io")
        bank_id = os.environ.get("HINDSIGHT_BANK_ID", "rapport-client-memory")
        hs_memory = HindsightMemory(base_url=base_url, api_key=hindsight_key, bank_id=bank_id)
        await hs_memory.ensure_bank_exists()
        memory_backend = hs_memory
        logger.info("Initialized HindsightMemory connected to %s", base_url)
    else:
        fake_mem = FakeMemory()
        memory_backend = fake_mem
        logger.info("Initialized FakeMemory for offline/testing operation")

    groq_key = os.environ.get("GROQ_API_KEY", "")
    primary_model = os.environ.get("GROQ_PRIMARY_MODEL", "openai/gpt-oss-120b")
    fallback_model = os.environ.get("GROQ_FALLBACK_MODEL", "qwen/qwen3-32b")
    llm_client = LLMClient(api_key=groq_key, primary_model=primary_model, fallback_model=fallback_model)

    yield


app = FastAPI(
    title="Rapport Client-Memory Agent API",
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


def _get_agent_pipeline() -> AgentPipeline:
    if llm_client is None:
        raise HTTPException(status_code=500, detail="LLM client not initialized")
    return AgentPipeline(memory_backend=memory_backend, llm_client=llm_client)


@app.get("/api/health")
async def health_check() -> dict[str, Any]:
    return {
        "status": "ok",
        "memory_backend": memory_backend.__class__.__name__ if memory_backend else "none",
        "llm_primary_model": llm_client.primary_model if llm_client else "unknown",
        "llm_fallback_model": llm_client.fallback_model if llm_client else "unknown",
    }


@app.get("/api/clients", response_model=list[ClientResponse])
async def list_clients() -> list[ClientResponse]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM clients ORDER BY name ASC")
    rows = cursor.fetchall()
    conn.close()

    result: list[ClientResponse] = []
    for r in rows:
        result.append(
            ClientResponse(
                id=r["id"],
                name=r["name"],
                company=r["company"],
                primary_contact=r["primary_contact"],
                influencers=json.loads(r["influencers"]) if r["influencers"] else [],
                quirks=json.loads(r["quirks"]) if r["quirks"] else [],
                notes=r["notes"],
                created_at=str(r["created_at"]) if r["created_at"] else None,
            )
        )
    return result


@app.post("/api/clients", response_model=ClientResponse, status_code=status.HTTP_201_CREATED)
async def create_client(client_data: ClientCreate) -> ClientResponse:
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT id FROM clients WHERE id = ?", (client_data.id,))
    if cursor.fetchone():
        conn.close()
        raise HTTPException(status_code=400, detail=f"Client with ID '{client_data.id}' already exists.")

    cursor.execute(
        """
        INSERT INTO clients (id, name, company, primary_contact, influencers, quirks, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            client_data.id,
            client_data.name,
            client_data.company,
            client_data.primary_contact,
            json.dumps(client_data.influencers),
            json.dumps(client_data.quirks),
            client_data.notes,
        ),
    )
    conn.commit()
    conn.close()

    return ClientResponse(
        id=client_data.id,
        name=client_data.name,
        company=client_data.company,
        primary_contact=client_data.primary_contact,
        influencers=client_data.influencers,
        quirks=client_data.quirks,
        notes=client_data.notes,
    )


@app.post("/api/respond", response_model=RespondResponse)
async def respond_to_client(req: RespondRequest) -> RespondResponse:
    if not req.incoming_text.strip():
        raise HTTPException(status_code=422, detail="incoming_text cannot be empty.")
    if len(req.incoming_text) > 10000:
        raise HTTPException(status_code=422, detail="incoming_text is oversized (max 10,000 characters).")

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM clients WHERE id = ?", (req.client_id,))
    client_row = cursor.fetchone()
    conn.close()

    client_info = None
    if client_row:
        client_info = {
            "id": client_row["id"],
            "name": client_row["name"],
            "company": client_row["company"],
        }

    pipeline = _get_agent_pipeline()

    if req.compare:
        out_on_task = asyncio.create_task(
            pipeline.run(
                client_id=req.client_id,
                incoming_text=req.incoming_text,
                memory_enabled=True,
                client_info=client_info,
            )
        )
        out_off_task = asyncio.create_task(
            pipeline.run(
                client_id=req.client_id,
                incoming_text=req.incoming_text,
                memory_enabled=False,
                client_info=client_info,
            )
        )
        out_on, out_off = await asyncio.gather(out_on_task, out_off_task)
    elif req.memory_enabled:
        out_on = await pipeline.run(
            client_id=req.client_id,
            incoming_text=req.incoming_text,
            memory_enabled=True,
            client_info=client_info,
        )
        out_off = None
    else:
        out_on = await pipeline.run(
            client_id=req.client_id,
            incoming_text=req.incoming_text,
            memory_enabled=False,
            client_info=client_info,
        )
        out_off = None

    _record_response_db(req.client_id, req.incoming_text, out_on)

    return RespondResponse(memory_on=out_on, memory_off=out_off)


def _record_response_db(client_id: str, incoming_text: str, out: SingleAgentOutput) -> None:
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT OR REPLACE INTO agent_responses (
                id, client_id, incoming_text, memory_enabled, draft_reply,
                client_brief, risk_flags, memory_used, warnings, model_used
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                out.response_id,
                client_id,
                incoming_text,
                1,
                out.draft_reply,
                json.dumps([b.model_dump() for b in out.client_brief]),
                json.dumps([r.model_dump() for r in out.risk_flags]),
                json.dumps([m.model_dump() for m in out.memory_used]),
                json.dumps(out.warnings),
                out.model_used,
            ),
        )
        conn.commit()
        conn.close()
    except Exception as ex:
        logger.warning("Failed to record response in SQLite db: %s", ex)


@app.post("/api/feedback", response_model=FeedbackResponse)
async def record_feedback(req: FeedbackRequest) -> FeedbackResponse:
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT client_id FROM agent_responses WHERE id = ?", (req.response_id,))
    resp_row = cursor.fetchone()
    if not resp_row:
        client_id = "unknown_client"
    else:
        client_id = resp_row["client_id"]

    cursor.execute("SELECT id FROM response_feedback WHERE response_id = ?", (req.response_id,))
    existing_fb = cursor.fetchone()

    if existing_fb:
        feedback_id = existing_fb["id"]
        conn.close()
        return FeedbackResponse(
            status="already_processed",
            message="Feedback for this response_id was already recorded.",
            feedback_id=feedback_id,
            response_id=req.response_id,
            outcome=req.outcome,
        )

    feedback_id = f"fb-{uuid.uuid4().hex[:12]}"

    cursor.execute(
        """
        INSERT INTO response_feedback (id, response_id, client_id, outcome, notes)
        VALUES (?, ?, ?, ?, ?)
        """,
        (feedback_id, req.response_id, client_id, req.outcome, req.notes),
    )
    conn.commit()
    conn.close()

    if memory_backend:
        try:
            await memory_backend.retain_feedback(
                client_id=client_id,
                interaction_id=req.response_id,
                outcome=req.outcome,
                notes=req.notes,
            )
        except Exception as ex:
            logger.warning("Failed to retain feedback in memory backend: %s", ex)

    return FeedbackResponse(
        status="success",
        message="Feedback recorded and retained successfully.",
        feedback_id=feedback_id,
        response_id=req.response_id,
        outcome=req.outcome,
    )


@app.post("/api/import", response_model=ImportResponse)
async def import_client_history(req: ImportRequest) -> ImportResponse:
    if not req.text.strip():
        raise HTTPException(status_code=422, detail="Text cannot be empty.")

    interaction_id = f"import-{uuid.uuid4().hex[:8]}"

    if memory_backend is None:
        raise HTTPException(status_code=500, detail="Memory backend not configured")

    retained_id = await memory_backend.retain_interaction(
        client_id=req.client_id,
        content=req.text,
        context="Imported client history text",
        interaction_id=interaction_id,
    )

    recalled = await memory_backend.recall_client(
        client_id=req.client_id,
        query=req.text[:200],
        max_results=5,
    )

    memory_used_items = [
        MemoryUsedItem(
            id=m.id,
            text=m.text,
            type=m.type,
            source_interaction_id=m.source_interaction_id,
            document_id=m.document_id,
        )
        for m in recalled
    ]

    return ImportResponse(
        status="success",
        client_id=req.client_id,
        retained_doc_id=retained_id,
        recalled_memories=memory_used_items,
    )


@app.get("/api/memory/observations")
async def get_observations(client_id: str = Query(..., description="Client ID")) -> dict[str, Any]:
    if memory_backend is None:
        return {"client_id": client_id, "observations": []}

    obs = await memory_backend.list_observations(client_id=client_id)
    return {
        "client_id": client_id,
        "observations": [o.model_dump() for o in obs],
    }
