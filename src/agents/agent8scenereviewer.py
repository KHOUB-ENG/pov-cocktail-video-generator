import sys
import io
import json
from pathlib import Path
from loguru import logger
import time
from google import genai

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.append(str(Path(__file__).resolve().parents[1]))

PROMPT_PATH = Path(__file__).resolve().parents[2] / "prompts" / "scene_reviewer_prompt.md"
with open(PROMPT_PATH, "r", encoding="utf-8") as f:
    system_prompt = f.read()

from config.geminiAPIsettings import api_key, GEMINI_MODEL
from agent_progress import call_gemini  # live progress + retrying Gemini call
client = genai.Client(api_key=api_key)
logger.info(f"Scene Reviewer using model: {GEMINI_MODEL}")


def run(recipe, continuity, scenes):
    continuity_str = json.dumps(continuity, ensure_ascii=False, indent=2) if isinstance(continuity, dict) else str(continuity)
    full_prompt = f"""{system_prompt}

---

INPUTS
======

RECIPE BRIEF (ground truth for ingredients, quantities, tools, final drink)
--------------------------------------------------------------------------
{recipe}

CONTINUITY DOCUMENT (exact prop names, hero visual, hands, and the three fixed stamps)
-------------------------------------------------------------------------------------
{continuity_str}

SCENE BREAKDOWN TO REVIEW (from the Scene Creator)
-------------------------------------------------
{scenes}

---

Audit the scene breakdown against the checklist and output the complete corrected breakdown now, in the exact %%DELIMITER%% format specified above, including a %%USER CHECK%% block on every clip.
"""
    return call_gemini(client, GEMINI_MODEL, full_prompt, "Scene Reviewer")


if __name__ == "__main__":
    raw = sys.stdin.read().strip()
    if not raw:
        logger.error("❌ No input received on stdin.")
        sys.exit(1)
    data = json.loads(raw)
    print(run(data.get("recipe", ""), data.get("continuity", {}), data.get("scenes", "")))
