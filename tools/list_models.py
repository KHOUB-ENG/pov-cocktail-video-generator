"""
List the Gemini models available to your API key that support content generation.

Usage (from the project root, with GOOGLE_API_KEY set in .env):
    python tools/list_models.py
"""

import os
from dotenv import load_dotenv
from google import genai

load_dotenv()
client = genai.Client()

print("--- Models that support generateContent ---")
for m in client.models.list():
    if "generateContent" in m.supported_actions:
        print(f"-> {m.name} ({m.display_name})")
