import sys
import io
import json
from pathlib import Path
from loguru import logger
import time
from google import genai

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.append(str(Path(__file__).resolve().parents[1]))

PROMPT_PATH = Path(__file__).resolve().parents[2] / "prompts" / "scene_creator_prompt.md"
with open(PROMPT_PATH, "r", encoding="utf-8") as f:
    system_prompt = f.read()

from config.geminiAPIsettings import api_key, GEMINI_MODEL
from agent_progress import call_gemini  # live progress + retrying Gemini call
client = genai.Client(api_key=api_key)
logger.info(f"Scene Creator using model: {GEMINI_MODEL}")


def run(storyboard, continuity):
    continuity_str = json.dumps(continuity, ensure_ascii=False, indent=2) if isinstance(continuity, dict) else str(continuity)
    full_prompt = f"""{system_prompt}

---

INPUTS
======

DIRECTOR STORYBOARD
-------------------
{storyboard}

CONTINUITY DOCUMENT
-------------------
{continuity_str}

---

Produce the complete scene breakdown now in the exact %%DELIMITER%% format specified above.
"""
    return call_gemini(client, GEMINI_MODEL, full_prompt, "Scene Creator")


if __name__ == "__main__":
    raw = sys.stdin.read().strip()
    if not raw:
        logger.error("❌ No input received on stdin.")
        sys.exit(1)
    data = json.loads(raw)
    print(run(data.get("storyboard", ""), data.get("continuity", {})))
