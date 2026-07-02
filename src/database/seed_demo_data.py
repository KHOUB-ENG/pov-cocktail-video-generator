"""
seed_demo_data.py
=================
Populate the database with a small set of illustrative demo records so the
dashboard has content on first run — a library of "previously published"
Protocols (used by the Creative Strategist to avoid repeats and by the Upload
Packager for back-linking), plus a few in-progress and saved ideas.

All content below is fictional demo data for the "POV Cocktail" example channel.

Run once after creating the database:
    python src/database/create_database.py
    python src/database/seed_demo_data.py

Safe to run repeatedly: it does nothing if the videos table already has rows,
so it will never overwrite real data.
"""

import sqlite3
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).resolve().parents[2] / "data" / "pov_cocktail.db"

# --- Previously published Protocols (one row per video) -------------------
# (protocol_id, cocktail, title, date_created, notes, style, rating)
VIDEOS = [
    (1, "Martini",
     "I stirred a Martini for exactly 37 seconds. The data is clear.",
     "2026-05-02", "Dilution plateaus at 37s; colder was not better.", "science", 5),
    (2, "Daiquiri",
     "The '2:1:0.75' Daiquiri ratio is mathematically wrong.",
     "2026-05-15", "Brix-balanced at 1.9:1 outperformed the classic.", "mythbusting", 4),
    (3, "Negroni",
     "Equal parts is a myth. The Negroni, re-measured.",
     "2026-05-29", "1:1:0.75 tested higher for bitterness balance.", "comparison", 5),
    (4, "Old Fashioned",
     "One sugar cube vs. simple syrup: the dilution data.",
     "2026-06-10", "Syrup held Brix steady; cube variance was +/-0.4.", "comparison", 4),
    (5, "Whiskey Sour",
     "Your Whiskey Sour foam collapses in 90 seconds. Fix it.",
     "2026-06-20", "Aquafaba out-stabilised egg white past 3 minutes.", "science", 5),
    (6, "Butterfly Pea Flower Gin Sour",
     "I made a cocktail CHANGE color on command.",
     "2026-06-27",
     "pH-driven anthocyanin shift; blue to purple in <10s. "
     "(Full sample export in protocols/sample-color-changing-cocktail/.)",
     "science", 5),
]

# --- Ideas currently in active development --------------------------------
# (protocol_id, title, cocktail, idea_text, summary)
WORKING_IDEAS = [
    (7, "Clarified Milk Punch, but I measured the haze.",
     "Milk Punch",
     "TITLE: Clarified Milk Punch, but I measured the haze.\nCOCKTAIL: Milk Punch",
     "Turbidity (NTU) before vs after milk clarification."),
    (7, "The Espresso Martini crema is 80% technique, 20% beans.",
     "Espresso Martini",
     "TITLE: The Espresso Martini crema is 80% technique, 20% beans.\nCOCKTAIL: Espresso Martini",
     "Crema thickness vs shake force, extraction, and bean freshness."),
]

# --- Ideas saved for later -----------------------------------------------
POTENTIAL_FUTURE_IDEAS = [
    (7, "Ice geometry changes your drink's temperature curve.",
     "Highball",
     "TITLE: Ice geometry changes your drink's temperature curve.\nCOCKTAIL: Highball",
     "Sphere vs cube vs spear: surface area and melt rate."),
    (7, "Fat-washing bourbon: how much fat actually binds?",
     "Fat-washed Old Fashioned",
     "TITLE: Fat-washing bourbon: how much fat actually binds?\nCOCKTAIL: Fat-washed Old Fashioned",
     "Mass of fat recovered vs infused across three ratios."),
]


def seed():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    existing = cur.execute("SELECT COUNT(*) FROM videos").fetchone()[0]
    if existing:
        print(f"videos table already has {existing} row(s) — skipping seed to avoid overwriting data.")
        conn.close()
        return

    now = datetime.now().isoformat()

    cur.executemany(
        "INSERT INTO videos (protocol_id, cocktail, title, date_created, notes, style, rating) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)", VIDEOS)

    cur.executemany(
        "INSERT INTO working_ideas (protocol_id, title, cocktail, idea_text, summary, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        [(pid, title, cocktail, idea, summ, now) for (pid, title, cocktail, idea, summ) in WORKING_IDEAS])

    cur.executemany(
        "INSERT INTO potential_future_ideas (protocol_id, title, cocktail, idea_text, summary, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        [(pid, title, cocktail, idea, summ, now) for (pid, title, cocktail, idea, summ) in POTENTIAL_FUTURE_IDEAS])

    conn.commit()
    print(f"Seeded {len(VIDEOS)} videos, {len(WORKING_IDEAS)} working ideas, "
          f"{len(POTENTIAL_FUTURE_IDEAS)} future ideas into {DB_PATH}")
    conn.close()


if __name__ == "__main__":
    seed()
