"""
backend/app/db.py — SQLite database helper using stdlib sqlite3.
"""

import sqlite3
import os

DB_PATH = os.environ.get("SQLITE_DB_PATH", "rapport.db")


def get_db_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS clients (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            company TEXT,
            primary_contact TEXT,
            influencers TEXT,
            quirks TEXT,
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS agent_responses (
            id TEXT PRIMARY KEY,
            client_id TEXT NOT NULL,
            incoming_text TEXT NOT NULL,
            memory_enabled INTEGER NOT NULL,
            draft_reply TEXT NOT NULL,
            client_brief TEXT,
            risk_flags TEXT,
            memory_used TEXT,
            warnings TEXT,
            model_used TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (client_id) REFERENCES clients(id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS response_feedback (
            id TEXT PRIMARY KEY,
            response_id TEXT NOT NULL UNIQUE,
            client_id TEXT NOT NULL,
            outcome TEXT NOT NULL,
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (response_id) REFERENCES agent_responses(id)
        )
    """)

    conn.commit()
    conn.close()
