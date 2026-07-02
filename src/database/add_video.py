# this is a web interface tool. works with the main.py flask server.

import sqlite3
from pathlib import Path

DB_PATH = Path("data/pov_cocktail.db")


def add_video(
    protocol_id,
    cocktail,
    title,
    date_created,
    notes,
    style=None,
):
    conn   = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO videos (protocol_id, cocktail, title, date_created, notes, style)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (protocol_id, cocktail, title, date_created, notes, style))
    conn.commit()
    conn.close()