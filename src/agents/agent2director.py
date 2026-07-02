import sys
import io
import json
from pathlib import Path
from loguru import logger
import time
from google import genai

# Force stdout to UTF-8 so Windows cp1252 doesn't choke on Unicode from Gemini
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

sys.path.append(str(Path(__file__).resolve().parents[1]))

PROMPT_PATH = Path(__file__).resolve().parents[2] / "prompts" / "director_agent_prompt.md"

with open(PROMPT_PATH, "r", encoding="utf-8") as f:
    system_prompt = f.read()

from config.geminiAPIsettings import api_key, GEMINI_MODEL
from agent_progress import call_gemini  # live progress + retrying Gemini call

client = genai.Client(api_key=api_key)
logger.info(f"Using Gemini model: {GEMINI_MODEL}")


def run(title, cocktail, idea_text, science='', recipe='', continuity=''):
    continuity_str = json.dumps(continuity, ensure_ascii=False, indent=2) if isinstance(continuity, dict) else str(continuity)
    full_prompt = f"""
{system_prompt}

---

CONCEPT BRIEF
=============
Protocol Title: {title}
Cocktail: {cocktail}

Idea:
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

CONTINUITY DOCUMENT (Universal Environment Block + Props Specification)
=======================================================================
{continuity_str}

---

Produce the complete storyboard brief in the exact format specified above.
"""

    return call_gemini(client, GEMINI_MODEL, full_prompt, "Director Agent")


if __name__ == "__main__":
    raw = sys.stdin.read().strip()
    if not raw:
        logger.error("❌ No idea data received on stdin.")
        sys.exit(1)

    try:
        idea = json.loads(raw)
    except json.JSONDecodeError as e:
        logger.error(f"❌ Failed to parse stdin JSON: {e}")
        sys.exit(1)

    title      = idea.get("title", "Untitled Protocol")
    cocktail   = idea.get("cocktail", "Unknown")
    idea_text  = idea.get("idea_text", "")
    science    = idea.get("science", "")
    recipe     = idea.get("recipe", "")
    continuity = idea.get("continuity", "")

    result = run(title, cocktail, idea_text, science, recipe, continuity)
    print(result)
