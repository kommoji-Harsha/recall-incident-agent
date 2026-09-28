#!/usr/bin/env python3
import asyncio
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# Add backend directory to path if needed
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from hindsight_client import Hindsight

BANK_ID = os.environ.get("HINDSIGHT_BANK_ID", "recall-incidents")
BASE_URL = os.environ.get("HINDSIGHT_BASE_URL", "https://api.hindsight.vectorize.io")
API_KEY = os.environ.get("HINDSIGHT_API_KEY", "")

async def smoke_test():
    if not API_KEY:
        print("ERROR: HINDSIGHT_API_KEY environment variable is missing.", file=sys.stderr)
        sys.exit(1)

    print(f"Connecting to Hindsight Cloud at {BASE_URL}...")
    client = Hindsight(base_url=BASE_URL, api_key=API_KEY)

    try:
        # 1. Create bank
        print(f"Creating/verifying bank '{BANK_ID}'...")
        await client.acreate_bank(
            bank_id=BANK_ID,
            name="Recall Incident Memory Bank",
            mission="Recall past incident root causes, troubleshooting steps, and resolution outcomes to assist on-call engineers.",
            disposition={"skepticism": 3, "literalism": 3, "empathy": 1},
        )
        print("Bank created/verified.")

        # 2. Retain test incident
        test_doc_id = "smoke-test-doc-1"
        test_content = (
            "Smoke test incident INC-999: PostgreSQL connection pool exhausted on auth-gateway. "
            "Error: QueuePool limit reached. Resolution: Raised pool size from 50 to 200."
        )
        print(f"Retaining test memory with document_id '{test_doc_id}'...")
        await client.aretain(
            bank_id=BANK_ID,
            content=test_content,
            timestamp=datetime.now(timezone.utc),
            context="smoke test incident record",
            document_id=test_doc_id,
            metadata={"service": "auth-gateway", "severity": "SEV-1", "type": "incident"},
            tags=["smoke-test", "auth-gateway"],
            retain_async=False,
        )
        print("Retain succeeded.")

        # 3. Recall similar memory
        query = "auth-gateway QueuePool limit reached connection pool exhausted"
        print(f"Recalling memories for query: '{query}'...")
        recall_res = await client.arecall(
            bank_id=BANK_ID,
            query=query,
            types=["world", "experience", "observation"],
            budget="mid",
            include_chunks=True,
            include_source_facts=True,
        )

        print(f"Recall returned {len(recall_res.results)} results:")
        for idx, res in enumerate(recall_res.results):
            print(f"  [{idx+1}] ID: {res.id} | Type: {res.type} | Scores: {res.scores}")
            print(f"      Text: {res.text[:120]}...")
            if res.metadata:
                print(f"      Metadata: {res.metadata}")

        print("\nSmoke test passed successfully!")

    finally:
        await client.aclose()

if __name__ == "__main__":
    asyncio.run(smoke_test())
