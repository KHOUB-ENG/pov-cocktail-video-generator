# the web equivalent of the add_notes.py file. This is used to update the notes for a specific video

import sqlite3
from pathlib import Path

DB_PATH = Path("data/pov_cocktail.db")


def update_notes(protocol_id, new_notes, append=False):

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT notes
        FROM videos
        WHERE protocol_id = ?
        """,
        (protocol_id,)
    )

    result = cursor.fetchone()

    if result is None:
        conn.close()
        return False

    current_notes = result[0]

    if append:

        if current_notes:
            updated_notes = current_notes + "\n\n" + new_notes
        else:
            updated_notes = new_notes

    else:

        updated_notes = new_notes

    cursor.execute(
        """
        UPDATE videos
        SET notes = ?
        WHERE protocol_id = ?
        """,
        (updated_notes, protocol_id)
    )

    conn.commit()
    conn.close()

    return True