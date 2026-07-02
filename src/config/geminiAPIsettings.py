import os
import sys
from dotenv import load_dotenv
from google.genai import types

# Load variables from .env
load_dotenv()

api_key = os.getenv("GOOGLE_API_KEY")

#Select Gemini model below
GEMINI_MODEL = "gemini-2.5-flash"
#GEMINI_MODEL = "gemini-3.5-flash"
#GEMINI_MODEL = "gemini-3.1-flash-lite"
#GEMINI_MODEL = "gemini-3.0-flash"

if not api_key:
    print("❌ GOOGLE_API_KEY not found in .env")
    sys.exit(1)


# -----------------------------------------------------------------
# PER-AGENT TEMPERATURE — the single control panel for output variance
# -----------------------------------------------------------------
# Temperature is the "surprise me" ↔ "follow the rules exactly" dial.
#   Low  (~0.3) → repeatable, obedient output. Best for agents that must copy
#                 stamps/prop names verbatim and obey hard rules.
#   High (~0.85)→ more creative/varied. Best for idea + story invention.
#
# This is the ONLY place to tune generation behaviour. The keys are the agent
# `label` strings passed to call_gemini(); no agent file needs editing.
DEFAULT_TEMPERATURE = 0.7

AGENT_TEMPERATURES = {
    "Creative Strategist": 0.85,   # invent concepts — wants creativity
    "Director Agent":      0.85,   # invent the story/pacing — wants creativity
    "Science Developer":   0.5,    # factual + structured
    "Recipe Architect":    0.5,    # factual + structured
    "Continuity Manager":  0.3,    # verbatim stamps, hard rules — max obedience
    "Scene Creator":       0.3,    # verbatim stamps, hard rules — max obedience
    "Upload Packager":     0.5,    # format-driven copy
    "Scene Reviewer":      0.3,    # surgical QA edits — max obedience
}


def config_for(label):
    """Build the GenerateContentConfig for an agent, looked up by its label.
    Falls back to DEFAULT_TEMPERATURE for any label not in the map."""
    temp = AGENT_TEMPERATURES.get(label, DEFAULT_TEMPERATURE)
    return types.GenerateContentConfig(temperature=temp)

