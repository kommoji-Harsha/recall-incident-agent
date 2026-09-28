#!/usr/bin/env python3
"""
scripts/seed.py — Idempotent seed script for Rapport client history in Hindsight Cloud using retain_batch.
Reads data/clients.json and data/interactions.json and populates the configured Hindsight bank.
"""

import datetime
import json
import os
import sys
from pathlib import Path

from hindsight_client import Hindsight


def load_data():
    base_dir = Path(__file__).parent.parent / "data"
    clients_file = base_dir / "clients.json"
    interactions_file = base_dir / "interactions.json"

    with open(clients_file, "r", encoding="utf-8") as f:
        clients = json.load(f)

    with open(interactions_file, "r", encoding="utf-8") as f:
        interactions = json.load(f)

    return clients, interactions


def main():
    api_key = os.environ.get("HINDSIGHT_API_KEY")
    base_url = os.environ.get("HINDSIGHT_BASE_URL", "https://api.hindsight.vectorize.io")
    bank_id = os.environ.get("HINDSIGHT_BANK_ID", "rapport-client-memory")

    if not api_key:
        print("Error: HINDSIGHT_API_KEY environment variable is required to run seed.py.")
        sys.exit(1)

    print(f"Connecting to Hindsight Cloud at {base_url} (bank_id: {bank_id})...")
    client = Hindsight(base_url=base_url, api_key=api_key, timeout=30.0)

    try:
        client.create_bank(
            bank_id=bank_id,
            name="Rapport Client History Bank",
            mission=(
                "Maintain detailed long-term memory of client communications, preferences, payment habits, "
                "scope changes, channel switches, and explicit constraints for freelancers and consultants."
            ),
            enable_observations=True,
        )
        print(f"Bank '{bank_id}' created or verified.")
    except Exception as e:
        print(f"Bank creation check info: {e}")

    clients, interactions = load_data()
    print(f"Loaded {len(clients)} clients and {len(interactions)} interactions.")

    client_batches: dict[str, list[dict]] = {}
    for item in interactions:
        cid = item["client_id"]
        if cid not in client_batches:
            client_batches[cid] = []

        ts_str = item["timestamp"]
        dt = datetime.datetime.fromisoformat(ts_str.replace("Z", "+00:00"))

        meta = item.get("metadata", {})
        meta_str = {k: str(v) for k, v in meta.items()}
        meta_str["client_id"] = cid
        meta_str["source_interaction_id"] = item["id"]

        client_batches[cid].append({
            "content": item["content"],
            "context": item.get("context", f"Interaction for client {cid}"),
            "timestamp": dt,
            "document_id": item["id"],
            "metadata": meta_str,
            "tags": [f"client:{cid}"],
        })

    total_retained = 0
    for cid, batch in client_batches.items():
        print(f"Seeding batch of {len(batch)} interactions for client {cid} using retain_batch...")
        try:
            client.retain_batch(
                bank_id=bank_id,
                items=batch,
                retain_async=False,
            )
            total_retained += len(batch)
        except Exception as ex:
            print(f"  Warning during retain_batch for client {cid}: {ex}")

    print(f"Seeding complete! Successfully processed {total_retained} interactions into bank '{bank_id}'.")


if __name__ == "__main__":
    main()
