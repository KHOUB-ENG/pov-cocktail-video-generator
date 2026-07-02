import sys
import io
import json
from pathlib import Path
from loguru import logger
import time
from google import genai

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.append(str(Path(__file__).resolve().parents[1]))

PROMPT_PATH = Path(__file__).resolve().parents[2] / "prompts" / "upload_packager_prompt.md"
with open(PROMPT_PATH, "r", encoding="utf-8") as f:
    system_prompt = f.read()

from config.geminiAPIsettings import api_key, GEMINI_MODEL
from agent_progress import call_gemini  # live progress + retrying Gemini call
client = genai.Client(api_key=api_key)
logger.info(f"Upload Packager using model: {GEMINI_MODEL}")


def run(title, cocktail, idea_text, science='', recipe='', storyboard='', previous_videos=None):
    prev_str = ''
    if previous_videos:
        valid = [v for v in (previous_videos if isinstance(previous_videos, list) else [])
                 if v.get('protocol_id') and v.get('title')]
        prev_str = '\n'.join(
            f"· Protocol {v['protocol_id']} — {v['title']}"
            for v in valid
        )

    full_prompt = f"""{system_prompt}

---

CONCEPT BRIEF
=============
Protocol Title: {title}
Cocktail: {cocktail}

Concept:
{idea_text}

---

SCIENCE BRIEF
=============
{science}

---

RECIPE BRIEF
============
{recipe}

---

DIRECTOR STORYBOARD
===================
{storyboard}

---

PREVIOUSLY PUBLISHED PROTOCOLS (for back-linking)
==================================================
{prev_str if prev_str else 'No previous protocols recorded yet.'}

---

Produce the complete upload package in the exact format specified above. End after the checklist.
"""
    return call_gemini(client, GEMINI_MODEL, full_prompt, "Upload Packager")


if __name__ == "__main__":
    raw = sys.stdin.read().strip()
    data = json.loads(raw) if raw else {}
    result = run(
        title           = data.get("title", "Untitled Protocol"),
        cocktail        = data.get("cocktail", "Unknown"),
        idea_text       = data.get("idea_text", ""),
        science         = data.get("science", ""),
        recipe          = data.get("recipe", ""),
        storyboard      = data.get("storyboard", ""),
        previous_videos = data.get("previous_videos", []),
    )
    print(result)
