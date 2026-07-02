# this is a python tool. doesn't work with the web interface.

import sqlite3
from pathlib import Path

DB_PATH = Path("data/pov_cocktail.db")

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

while True:

    protocol_id = input("Enter Protocol ID to delete: ")

    try:
        protocol_id = int(protocol_id)
    except ValueError:
        print("Please enter a valid protocol ID.")
        continue

    cursor.execute(
        "SELECT * FROM videos WHERE protocol_id = ?",
        (protocol_id,)
    )

    result = cursor.fetchone()

    if result is None:
        print("Protocol not found. Try again.\n")
        continue

    break

print("\nProtocol Found")
print(f"Protocol ID: {result[0]:03}")
print(f"Cocktail: {result[1]}")
print(f"Title: {result[2]}")
print(f"Date Created: {result[3]}")
print(f"Notes: {result[4]}")

confirm = input(
    "\nAre you sure you want to DELETE this protocol? (y/n): "
)

if confirm.lower() == "y":

    cursor.execute(
        "DELETE FROM videos WHERE protocol_id = ?",
        (protocol_id,)
    )

    conn.commit()

    print("Protocol deleted successfully.")

else:

    print("Deletion cancelled.")

conn.close()