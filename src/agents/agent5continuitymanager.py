import sys
import io
import json
from pathlib import Path
from loguru import logger
import time
from google import genai

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.append(str(Path(__file__).resolve().parents[1]))

PROMPT_PATH = Path(__file__).resolve().parents[2] / "prompts" / "continuity_manager_prompt.md"
with open(PROMPT_PATH, "r", encoding="utf-8") as f:
    system_prompt = f.read()

from config.geminiAPIsettings import api_key, GEMINI_MODEL
from agent_progress import call_gemini  # live progress + retrying Gemini call
client = genai.Client(api_key=api_key)
logger.info(f"Continuity Manager using model: {GEMINI_MODEL}")


def run(title, cocktail, idea_text, science, recipe):
    full_prompt = f"""{system_prompt}

---

INPUTS
======

CONCEPT
-------
Protocol Title: {title}
Cocktail: {cocktail}

Idea:
{idea_text}

SCIENCE BRIEF
-------------
{science}

RECIPE BRIEF
------------
{recipe}

---

Produce the continuity document now in the exact three-part format specified above, each part wrapped in its required %%TAG%% pair, in order: PART 1 (%%CONTINUITY_VISUAL_BLOCKS%% — environment, hand, and camera blocks), PART 2 (%%CONTINUITY_PROPS_JSON%% — JSON in ```json fences), PART 3 (%%CONTINUITY_VESSEL_STATE_MACHINE%% — vessel state machine). Run the FINAL SELF-CHECK silently before answering. No other text before, after, or between the tagged parts.
"""
    return call_gemini(client, GEMINI_MODEL, full_prompt, "Continuity Manager")


if __name__ == "__main__":
    raw = sys.stdin.read().strip()
    if not raw:
        logger.error("❌ No input received on stdin.")
        sys.exit(1)
    data = json.loads(raw)
    print(run(
        data.get("title", ""),
        data.get("cocktail", ""),
        data.get("idea_text", ""),
        data.get("science", ""),
        data.get("recipe", ""),
    ))
