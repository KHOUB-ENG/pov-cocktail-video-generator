import sqlite3
from pathlib import Path

DB_PATH = Path("data/pov_cocktail.db")


def get_next_protocol_id():

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT MAX(protocol_id)
        FROM videos
    """)

    result = cursor.fetchone()

    conn.close()

    if result[0] is None:
        return 1

    return result[0] + 1