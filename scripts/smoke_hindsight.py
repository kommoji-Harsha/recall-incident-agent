#!/usr/bin/env python3
"""
scripts/smoke_hindsight.py — Live Hindsight retain/recall and tag-isolation smoke test script.
Run with real HINDSIGHT_API_KEY to verify live connectivity and strict client tag isolation.
"""

import os
import sys
import uuid
from hindsight_client import Hindsight


def main():
    api_key = os.environ.get("HINDSIGHT_API_KEY")
    base_url = os.environ.get("HINDSIGHT_BASE_URL", "https://api.hindsight.vectorize.io")
    bank_id = os.environ.get("HINDSIGHT_BANK_ID", "rapport-client-memory-smoke")

    if not api_key:
        print("Error: HINDSIGHT_API_KEY environment variable is required to run smoke_hindsight.py.")
        sys.exit(1)

    print(f"Connecting to Hindsight at {base_url}...")
    hs = Hindsight(base_url=base_url, api_key=api_key)

    try:
        hs.create_bank(
            bank_id=bank_id,
            name="Smoke Test Bank",
            mission="Verify live tag isolation and recall functionality.",
            enable_observations=True,
        )
    except Exception as e:
        print(f"Note on create_bank: {e}")

    run_id = str(uuid.uuid4())[:8]
    client_a = f"client_smoke_a_{run_id}"
    client_b = f"client_smoke_b_{run_id}"

    doc_a = f"interaction-{client_a}-1"
    doc_b = f"interaction-{client_b}-1"

    print(f"1. Retaining item for {client_a}...")
    hs.retain(
        bank_id=bank_id,
        content="Acme Corp insists on no phone calls before 11:00 AM EST under any circumstances.",
        context="Client communication rule",
        document_id=doc_a,
        metadata={"client_id": client_a, "source_interaction_id": doc_a},
        tags=[f"client:{client_a}"],
        retain_async=False,
    )

    print(f"2. Retaining item for {client_b}...")
    hs.retain(
        bank_id=bank_id,
        content="Vortex Media requires all Friday updates in Slack channel #vortex-project.",
        context="Client communication rule",
        document_id=doc_b,
        metadata={"client_id": client_b, "source_interaction_id": doc_b},
        tags=[f"client:{client_b}"],
        retain_async=False,
    )

    print("3. Recalling for Client A with tags_match='any_strict'...")
    res_a = hs.recall(
        bank_id=bank_id,
        query="What are the meeting timing or channel constraints?",
        tags=[f"client:{client_a}"],
        tags_match="any_strict",
    )

    recalled_a_texts = [r.text for r in res_a]
    print(f"Recalled {len(res_a)} results for {client_a}: {recalled_a_texts}")

    leakage_b_in_a = any(client_b in t or "Vortex Media" in t for t in recalled_a_texts)
    if leakage_b_in_a:
        print("FAIL: Detected cross-client leakage! Client B memory leaked into Client A recall.")
        sys.exit(1)

    print("4. Recalling for Client B with tags_match='any_strict'...")
    res_b = hs.recall(
        bank_id=bank_id,
        query="What are the meeting timing or channel constraints?",
        tags=[f"client:{client_b}"],
        tags_match="any_strict",
    )
    recalled_b_texts = [r.text for r in res_b]
    print(f"Recalled {len(res_b)} results for {client_b}: {recalled_b_texts}")

    leakage_a_in_b = any(client_a in t or "Acme Corp" in t for t in recalled_b_texts)
    if leakage_a_in_b:
        print("FAIL: Detected cross-client leakage! Client A memory leaked into Client B recall.")
        sys.exit(1)

    print("SUCCESS: Live Hindsight retain, recall, and strict tag isolation verified successfully!")


if __name__ == "__main__":
    main()
