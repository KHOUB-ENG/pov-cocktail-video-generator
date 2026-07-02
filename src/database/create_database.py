"""
create_database.py
==================
One-time setup: creates the SQLite database and all tables the app expects.

Run once from the project root before starting the dashboard:
    python src/database/create_database.py

Safe to re-run — every statement uses CREATE TABLE IF NOT EXISTS.
"""

import sqlite3
from pathlib import Path

# Resolve the DB path relative to the project root so this works from anywhere.
DB_PATH = Path(__file__).resolve().parents[2] / "data" / "pov_cocktail.db"
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

# Completed / logged Protocols (one row per published video).
cursor.execute("""
CREATE TABLE IF NOT EXISTS videos (
    protocol_id  INTEGER PRIMARY KEY,
    cocktail     TEXT NOT NULL,
    title        TEXT NOT NULL,
    date_created TEXT,
    notes        TEXT,
    style        TEXT,
    rating       INTEGER
)
""")

# Ideas selected for active development ("Develop Now").
cursor.execute("""
CREATE TABLE IF NOT EXISTS working_ideas (
    id          INTEGER PRIMARY KEY,
    protocol_id INTEGER,
    title       TEXT,
    cocktail    TEXT,
    idea_text   TEXT,
    summary     TEXT,
    created_at  TEXT
)
""")

# Ideas saved for later ("Save for Later").
cursor.execute("""
CREATE TABLE IF NOT EXISTS potential_future_ideas (
    id          INTEGER PRIMARY KEY,
    protocol_id INTEGER,
    title       TEXT,
    cocktail    TEXT,
    idea_text   TEXT,
    summary     TEXT,
    created_at  TEXT
)
""")

conn.commit()
conn.close()

print(f"Database ready at {DB_PATH}")
