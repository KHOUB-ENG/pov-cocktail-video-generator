import sys
import io
import json
from pathlib import Path
from loguru import logger
import time
from google import genai

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.append(str(Path(__file__).resolve().parents[1]))

PROMPT_PATH = Path(__file__).resolve().parents[2] / "prompts" / "recipe_architect_prompt.md"
with open(PROMPT_PATH, "r", encoding="utf-8") as f:
    system_prompt = f.read()

from config.geminiAPIsettings import api_key, GEMINI_MODEL
from agent_progress import call_gemini  # live progress + retrying Gemini call
client = genai.Client(api_key=api_key)
logger.info(f"Recipe Architect using model: {GEMINI_MODEL}")


def run(title, cocktail, idea_text, science=""):
    science_block = f"""
SCIENCE BRIEF (already produced for this concept — your recipe must execute and stay consistent with it)
=============
{science}
""" if science.strip() else ""

    full_prompt = f"""{system_prompt}

---

CONCEPT INPUT
=============
Protocol Title: {title}
Cocktail: {cocktail}

Concept:
{idea_text}
{science_block}
---

Produce the complete Recipe Brief in the exact format specified above.
"""
    return call_gemini(client, GEMINI_MODEL, full_prompt, "Recipe Architect")


if __name__ == "__main__":
    raw = sys.stdin.read().strip()
    if not raw:
        logger.error("❌ No input received on stdin.")
        sys.exit(1)
    data = json.loads(raw)
    print(run(data.get("title", ""), data.get("cocktail", ""), data.get("idea_text", ""), data.get("science", "")))
