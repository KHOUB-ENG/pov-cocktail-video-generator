# this is a python tool. doesn't work with the web interface.

import sqlite3
from pathlib import Path

DB_PATH = Path("data/pov_cocktail.db")
Adding = True

while Adding:
    conn = sqlite3.connect(DB_PATH)

    cursor = conn.cursor()

    cursor.execute("""
    SELECT MAX(protocol_id)
    FROM videos
    """)

    result = cursor.fetchone()

    if result[0] is None:
        print("No protocols found in the database.")
        next_protocol_id = 1
    else:
        next_protocol_id = result[0] + 1

    formatted_protocol_id = f"{next_protocol_id:03}"

    print(f"Protocol ID: {formatted_protocol_id}")

    cocktail = input("Enter cocktail: ")

    title = input("Enter title: ")

    date_created = input("Enter date created (YYYY-MM-DD): ")

    notes = input("Enter notes: ")

    print(f"\nProtocol ID: {formatted_protocol_id}")
    print(f"Cocktail: {cocktail}")
    print(f"Title: {title}")
    print(f"Date Created: {date_created}")
    print(f"Notes: {notes}")

    confirm = input("\nSave to database? (y/n): ")

    if confirm.lower() == "y":

        cursor.execute("""
        INSERT INTO videos (
            protocol_id,
            cocktail,
            title,
            date_created,
            notes
        )
        VALUES (?, ?, ?, ?, ?)
        """, (
            next_protocol_id,
            cocktail,
            title,
            date_created,
            notes
        ))

        conn.commit()

        print("Saved successfully.")

    else:
        print("Cancelled.")
        
    conn.close()
    add_another = input("\nWould you like to add another protocol? (y/n): ")
    if add_another.lower() != "y":
        Adding = False

print("Exiting program.")