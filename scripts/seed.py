#!/usr/bin/env python3
import asyncio
import json
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

async def seed():
    if not API_KEY:
        print("ERROR: HINDSIGHT_API_KEY environment variable is missing.", file=sys.stderr)
        sys.exit(1)

    print(f"Connecting to Hindsight at {BASE_URL} (Bank: {BANK_ID})...")
    client = Hindsight(base_url=BASE_URL, api_key=API_KEY)

    try:
        # 1. Ensure Bank exists
        print(f"Ensuring memory bank '{BANK_ID}' exists...")
        try:
            await client.acreate_bank(
                bank_id=BANK_ID,
                name="Recall Incident Memory Bank",
                mission="Recall past incident root causes, troubleshooting steps, and resolution outcomes to assist on-call engineers.",
                disposition={"skepticism": 3, "literalism": 3, "empathy": 1},
            )
            print("Bank created successfully.")
        except Exception as e:
            print(f"Bank check/creation note: {e} (continuing)")

        # 2. Load Incidents
        incidents_path = Path(__file__).resolve().parent.parent / "data" / "incidents.json"
        with open(incidents_path, "r", encoding="utf-8") as f:
            incidents = json.load(f)

        print(f"Loaded {len(incidents)} incidents from {incidents_path}")

        # Seed incidents in batches with per-item document_id
        items = []
        for inc in incidents:
            content_text = (
                f"Incident ID: {inc['id']}\n"
                f"Title: {inc['title']}\n"
                f"Service: {inc['service']}\n"
                f"Severity: {inc['severity']}\n"
                f"Root Cause: {inc['root_cause']}\n"
            )
            if inc.get("failed_first_step"):
                content_text += f"Tried First (FAILED): {inc['failed_first_step']}\n"

            content_text += "Resolution Steps:\n"
            for step in inc.get("resolution_steps", []):
                content_text += f"- {step}\n"

            content_text += "\nLogs:\n" + "\n".join(inc.get("logs", []))

            metadata = {
                "incident_id": str(inc["id"]),
                "service": str(inc["service"]),
                "severity": str(inc["severity"]),
                "runbook_used": str(inc.get("runbook_used", "")),
                "time_to_resolve": str(inc.get("time_to_resolve", "")),
                "type": "incident",
            }
            if inc.get("failed_first_step"):
                metadata["has_failed_step"] = "true"

            items.append({
                "content": content_text,
                "timestamp": inc["timestamp"],
                "context": f"past incident {inc['id']} for {inc['service']}",
                "document_id": f"incident-{inc['id']}",  # Per-item unique stable document_id
                "metadata": metadata,
                "tags": ["incident", inc["service"], inc["severity"].lower()],
            })

        print(f"Retaining batch of {len(items)} incidents with per-item document_ids...")
        await client.aretain_batch(
            bank_id=BANK_ID,
            items=items,
            retain_async=False,
        )
        print("Batch incident retain complete.")

        # 3. Load Post-Mortems
        postmortems_dir = Path(__file__).resolve().parent.parent / "data" / "postmortems"
        if postmortems_dir.exists():
            pm_files = sorted(postmortems_dir.glob("*.md"))
            print(f"Found {len(pm_files)} post-mortem files in {postmortems_dir}")
            for pm_file in pm_files:
                pm_text = pm_file.read_text(encoding="utf-8")
                doc_id = f"postmortem-{pm_file.stem}"
                print(f"Retaining post-mortem {doc_id}...")
                await client.aretain(
                    bank_id=BANK_ID,
                    content=pm_text,
                    timestamp=datetime.now(timezone.utc),
                    context=f"post-mortem record {pm_file.stem}",
                    document_id=doc_id,
                    metadata={"type": "postmortem", "source_file": pm_file.name},
                    tags=["postmortem"],
                    retain_async=False,
                )
                print(f"Retained {doc_id}")

        print("Seeding finished successfully.")

    finally:
        await client.aclose()

if __name__ == "__main__":
    asyncio.run(seed())
