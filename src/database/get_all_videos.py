# this works with the web interface. It is used to retrieve all videos from the database and display them on the dashboard.

import sqlite3
from pathlib import Path

DB_PATH = Path("data/pov_cocktail.db")


def get_all_videos():
    conn   = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT protocol_id, cocktail, title, date_created, notes,
               style, rating
        FROM videos
    """)
    rows   = cursor.fetchall()
    conn.close()
    return [
        {
            "id":           row[0],
            "protocol_id":  f"{row[0]:03}",
            "cocktail":     row[1],
            "title":        row[2],
            "date_created": row[3],
            "notes":        row[4],
            "style":        row[5],
            "rating":       row[6],
        }
        for row in rows
    ]