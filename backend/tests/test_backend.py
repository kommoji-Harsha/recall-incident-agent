import backend.app.main as main_mod
import pytest
from backend.app.agent.pipeline import IncidentAgentPipeline
from backend.app.db import Database
from backend.app.llm.client import GroqLLMClient, LLMResult
from backend.app.main import app
from backend.app.memory.fake import FakeMemory
from backend.app.memory.protocol import RecalledMemory
from fastapi.testclient import TestClient


@pytest.fixture
def fake_memory() -> FakeMemory:
    mem = FakeMemory(
        initial_memories=[
            RecalledMemory(
                id="mem-101",
                text=(
                    "Incident INC-101: checkout-api DB connection pool exhausted. "
                    "Tried first (FAILED): Restarting pods without pool size increase. "
                    "Resolution: Increased pool size from 100 to 300 in Helm config."
                ),
                type="experience",
                context="past incident INC-101",
                metadata={"incident_id": "INC-101", "service": "checkout-api", "has_failed_step": "true"},
                document_id="incident-INC-101",
                source_incident_id="INC-101",
                scores={"final": 0.95},
            )
        ]
    )
    return mem


@pytest.fixture
def client(fake_memory: FakeMemory, tmp_path) -> TestClient:
    db_file = str(tmp_path / "test_recall.db")
    main_mod.db = Database(db_path=db_file)
    main_mod.memory_backend = fake_memory
    main_mod.llm_client = GroqLLMClient(api_key="")  # No key forces fallback/degraded or offline mode
    return TestClient(app)


def test_health_endpoint(client: TestClient) -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"


def test_analyze_with_and_without_memory(client: TestClient) -> None:
    alert = "checkout-api error: sqlalchemy.exc.TimeoutError QueuePool limit reached"

    # Analyze with Memory ON
    res_on = client.post("/api/analyze", json={"alert_text": alert, "memory_enabled": True})
    assert res_on.status_code == 200
    data_on = res_on.json()
    assert "analysis_id" in data_on
    assert data_on["memory_on"]["likely_root_cause"]["text"] is not None

    # Analyze with Memory OFF
    res_off = client.post("/api/analyze", json={"alert_text": alert, "memory_enabled": False})
    assert res_off.status_code == 200
    data_off = res_off.json()
    assert data_off["memory_on"]["memory_used"] == []
    assert any("[no matching history]" in warning or "Memory is OFF" in warning for warning in data_off["memory_on"]["warnings"])


def test_analyze_compare_mode(client: TestClient) -> None:
    alert = "checkout-api QueuePool limit reached"
    res = client.post("/api/analyze", json={"alert_text": alert, "compare": True})
    assert res.status_code == 200
    data = res.json()
    assert data["memory_on"] is not None
    assert data["memory_off"] is not None
    assert data["memory_off"]["memory_used"] == []


@pytest.mark.asyncio
async def test_citation_grounding_drops_fake_citations(fake_memory: FakeMemory) -> None:
    pipeline = IncidentAgentPipeline(memory=fake_memory, llm_client=GroqLLMClient(api_key=""))

    # Mock LLM returning hallucinatory sources (INC-999 is not in fake_memory)
    class MockLLM:
        async def generate_structured(self, prompt: str, response_model: type) -> LLMResult:
            from backend.app.agent.pipeline import LLMSynthesisSchema
            fake_schema = LLMSynthesisSchema(
                root_cause_summary="DB pool exhausted",
                confidence=0.9,
                root_cause_sources=["INC-101", "INC-999"],  # INC-999 hallucinated
                proposed_fix_steps=[
                    {
                        "step": "Increase pool size to 300",
                        "rationale": "Worked in INC-101",
                        "source_incident_ids": ["INC-101", "INC-888"],  # INC-888 hallucinated
                        "source_memory_ids": ["mem-101", "mem-999"],  # mem-999 hallucinated
                        "prior_outcome": "worked",
                    }
                ],
                suggested_runbooks=["runbook-db.md"],
            )
            return LLMResult(data=fake_schema, model_used="mock-model", warnings=[])

    pipeline.llm_client = MockLLM()  # type: ignore

    res = await pipeline.analyze("checkout-api QueuePool limit reached", memory_enabled=True)
    # Grounding check: INC-999, INC-888, mem-999 should be dropped
    assert "INC-999" not in res.likely_root_cause.sources
    assert "INC-101" in res.likely_root_cause.sources
    assert "INC-888" not in res.fix_steps[0].source_incident_ids
    assert "mem-999" not in res.fix_steps[0].source_memory_ids


@pytest.mark.asyncio
async def test_failed_fix_demotion(fake_memory: FakeMemory) -> None:
    pipeline = IncidentAgentPipeline(memory=fake_memory, llm_client=GroqLLMClient(api_key=""))

    class MockLLM:
        async def generate_structured(self, prompt: str, response_model: type) -> LLMResult:
            from backend.app.agent.pipeline import LLMSynthesisSchema
            fake_schema = LLMSynthesisSchema(
                root_cause_summary="DB pool exhausted",
                confidence=0.9,
                root_cause_sources=["INC-101"],
                proposed_fix_steps=[
                    {
                        "step": "Restart pods without pool increase",
                        "rationale": "Quick reboot attempt",
                        "source_incident_ids": ["INC-101"],
                        "source_memory_ids": ["mem-101"],
                        "prior_outcome": "failed",
                    },
                    {
                        "step": "Increase pool size from 100 to 300",
                        "rationale": "Permanent fix",
                        "source_incident_ids": ["INC-101"],
                        "source_memory_ids": ["mem-101"],
                        "prior_outcome": "worked",
                    },
                ],
                suggested_runbooks=[],
            )
            return LLMResult(data=fake_schema, model_used="mock-model", warnings=[])

    pipeline.llm_client = MockLLM()  # type: ignore

    res = await pipeline.analyze("checkout-api QueuePool limit reached", memory_enabled=True)
    # The failed step ("Restart pods") should be demoted below the working step ("Increase pool size")
    assert res.fix_steps[0].step == "Increase pool size from 100 to 300"
    assert res.fix_steps[1].step == "Restart pods without pool increase"
    assert res.fix_steps[1].prior_outcome == "failed"
    assert any("Demoted step" in w for w in res.warnings)


@pytest.mark.asyncio
async def test_no_similar_incident_path() -> None:
    empty_mem = FakeMemory(initial_memories=[])
    pipeline = IncidentAgentPipeline(memory=empty_mem, llm_client=GroqLLMClient(api_key=""))

    res = await pipeline.analyze("unusual_unknown_exotic_error_xyz_123", memory_enabled=True)
    assert res.likely_root_cause.sources == []
    assert any("no matching history" in warning or "No matching historical" in warning for warning in res.warnings)


@pytest.mark.asyncio
async def test_hindsight_timeout_yielding_degraded_response() -> None:
    class FailingMemory(FakeMemory):
        async def recall_similar(self, query: str, **kwargs) -> list[RecalledMemory]:
            raise TimeoutError("Hindsight API request timed out")

    failing_mem = FailingMemory()
    pipeline = IncidentAgentPipeline(memory=failing_mem, llm_client=GroqLLMClient(api_key=""))

    # Should not crash, returns degraded generic response safely
    res = await pipeline.analyze("checkout-api QueuePool limit reached", memory_enabled=True)
    assert res.fix_steps is not None
    assert res.likely_root_cause is not None


@pytest.mark.asyncio
async def test_llm_retry_and_fallback_to_degraded() -> None:
    mem = FakeMemory(
        initial_memories=[
            RecalledMemory(
                id="mem-1",
                text="Resolution: Increase pool size to 300.",
                type="experience",
                metadata={"incident_id": "INC-101"},
                document_id="incident-INC-101",
                source_incident_id="INC-101",
            )
        ]
    )

    class AlwaysFailingLLM(GroqLLMClient):
        async def generate_structured(self, prompt: str, response_model: type, **kwargs) -> LLMResult:
            raise RuntimeError("LLM rate limit / tool call 400 failure")

    pipeline = IncidentAgentPipeline(memory=mem, llm_client=AlwaysFailingLLM(api_key="test"))

    res = await pipeline.analyze("checkout-api error", memory_enabled=True)
    assert res.model_used == "memory-degraded"
    assert any("LLM synthesis failed" in w for w in res.warnings)


def test_outcome_idempotency(client: TestClient) -> None:
    # First analyze
    res_an = client.post("/api/analyze", json={"alert_text": "checkout-api pool error"})
    an_id = res_an.json()["analysis_id"]

    # Submit outcome 1st time
    out1 = client.post(
        "/api/outcome",
        json={"analysis_id": an_id, "result": "fixed", "notes": "Worked after pool increase"},
    )
    assert out1.status_code == 200
    assert out1.json()["idempotent_duplicate"] is False

    # Repeat submit outcome 2nd time
    out2 = client.post(
        "/api/outcome",
        json={"analysis_id": an_id, "result": "fixed", "notes": "Worked after pool increase"},
    )
    assert out2.status_code == 200
    assert out2.json()["idempotent_duplicate"] is True


def test_empty_and_oversized_input(client: TestClient) -> None:
    # Empty alert text
    res_empty = client.post("/api/analyze", json={"alert_text": "   "})
    assert res_empty.status_code == 200
    assert "No alert or log text was provided" in res_empty.json()["memory_on"]["likely_root_cause"]["text"]

    # Oversized alert text
    huge_text = "a" * 100001
    res_huge = client.post("/api/analyze", json={"alert_text": huge_text})
    assert res_huge.status_code == 400
    assert "exceeds max length limit" in res_huge.json()["detail"]


def test_postmortem_endpoint(client: TestClient) -> None:
    res = client.post(
        "/api/postmortem",
        json={"title": "INC-101 Postmortem", "text": "Postmortem text content detailing root cause."},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "retained"
    assert data["postmortem_id"].startswith("pm-")


def test_get_observations_endpoint(client: TestClient) -> None:
    res = client.get("/api/memory/observations")
    assert res.status_code == 200
    data = res.json()
    assert "observations" in data
    assert isinstance(data["observations"], list)
