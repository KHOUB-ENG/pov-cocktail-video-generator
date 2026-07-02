# This script allows you to add or update notes for a specific protocol in the database.
# Only works in python for now, not on the web. 

import sqlite3
from pathlib import Path

DB_PATH = Path("data/pov_cocktail.db")

conn = sqlite3.connect(DB_PATH)

cursor = conn.cursor()
adding_notes = True
while adding_notes:
    protocol_id = input("Enter Protocol ID: ")

    protocol_id = int(protocol_id)

    cursor.execute(
        "SELECT * FROM videos WHERE protocol_id = ?",
        (protocol_id,)
    )

    result = cursor.fetchone()

    if result is None:
        print("Protocol not found.")
        choice = 3
    else:

        print(f"\nProtocol ID: {result[0]:03}")
        print(f"Cocktail: {result[1]}")
        print(f"Title: {result[2]}")
        print(f"Date Created: {result[3]}")
        print(f"Current Notes: {result[4]}")

        print("\nOptions:")
        print("1 - Append Notes")
        print("2 - Replace Notes")
        print("3 - Cancel")

        choice = input("\nChoose option: ")

    if choice == "1":

        additional_notes = input("\nEnter additional notes: ")

        if result[4]:
            updated_notes = result[4] + "\n\n" + additional_notes
        else:
            updated_notes = additional_notes

        print("\nUpdated Notes:")
        print(updated_notes)

        confirm = input("\nSave changes? (y/n): ")

        if confirm.lower() == "y":

            cursor.execute(
                """
                UPDATE videos
                SET notes = ?
                WHERE protocol_id = ?
                """,
                (updated_notes, protocol_id)
            )

            conn.commit()

            print("Notes updated successfully.")

        else:

            print("Changes discarded.")

    elif choice == "2":

        updated_notes = input("\nEnter new notes: ")

        print("\nUpdated Notes:")
        print(updated_notes)

        confirm = input("\nSave changes? (y/n): ")

        if confirm.lower() == "y":

            cursor.execute(
                """
                UPDATE videos
                SET notes = ?
                WHERE protocol_id = ?
                """,
                (updated_notes, protocol_id)
            )

            conn.commit()

            print("Notes updated successfully.")

        else:

            print("Changes discarded.")
            
    elif choice == "3":

        print("Cancelled.")

    else:

        print("Invalid option.")

    continue_adding = input("\nAdd notes to another protocol? (y/n): ")
    if continue_adding.lower() != "y":
        adding_notes = False