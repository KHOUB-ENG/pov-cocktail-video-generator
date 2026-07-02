import sys
import io
import json
from pathlib import Path
from loguru import logger
import time
from google import genai
from agent_progress import emit, call_gemini  # live progress + retrying Gemini call

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Sort out paths and load system prompt
sys.path.append(str(Path(__file__).resolve().parents[1])) # Add src/config to path for imports
PROMPT_PATH = Path(__file__).resolve().parents[2] / "prompts" / "creative_strategist_prompt.md" # Add path to prompt file

with open(PROMPT_PATH, "r", encoding="utf-8") as file:
    system_prompt = file.read()

# import other tools and settings
from config.geminiAPIsettings import api_key, GEMINI_MODEL
from database.get_all_videos import get_all_videos

# Initialize Gemini client and logger
STYLE_MODIFIERS = {
    "bar": """STYLE DIRECTIVE: Bar & Classic
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ON TOP OF THE GENERIC PROMPT, YOU HAVE BEEN GIVEN THE FOLLOWING ADDITIONAL INSTRUCTIONS FOR A BAR AND CLASSIC THEME.

Every idea must be rooted in a specific traditional bar technique.
Each idea should give the viewer something immediately applicable: they finish the video and can do this differently tonight.
Focus on real, recognised classic cocktails
or genuine bartending techniques used in real high-end bars. Bring that element of luxury. 
The "wow" factor should come from applying POV Cocktail's clinical precision treatment
 to something the viewer already knows and trusts, not from inventing a fictional or impossible drink.

Equipment must be bar equipment a skilled home bartender would own. 

REQUIREMENTS FOR THIS:
- The cocktail or technique must be real and verifiable — no invented drinks, no fictional chemistry.
- Lean into recognisable names, iconic glassware, and classic ratios as a source of credibility and SEO value (these titles are searched constantly).
- Equipment must be bar equipment a skilled home bartender would own. 
- Genuine bartending techniques used in real high-end bars.  
- The "wow" comes from precision, ritual, and craft — not spectacle. Think slow-motion, perfect geometry, exact control — the things real bartenders obsess over, exaggerated.
- Titles should reference the classic drink by name where possible, since search volume on classic cocktail names is consistently high.
- Avoid anything that feels gimmicky or sci-fi — this modifier is about reverence for craft, executed at an impossible level of precision.

""",

    "science": """STYLE DIRECTIVE: Science & Lab
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ON TOP OF THE GENERIC PROMPT, YOU HAVE BEEN GIVEN THE FOLLOWING ADDITIONAL INSTRUCTIONS FOR A SCIENCE AND LAB THEME.

Every idea must feature a laboratory technique or scientific instrument - The science must be real and the equipment must produce a measurably different cocktail outcome that could not be achieved without it.

Requirements for this modifier:
- The technique must be real and explainable — viewers should walk away having genuinely learned something, even if delivered in a deadpan or exaggerated way.
- Favour techniques with a dramatic visual transformation moment (liquid becoming solid, cloudy becoming clear, one colour becoming another) as the central "wow."
- It's acceptable and encouraged for this modifier to include brief, real explanation of the underlying chemistry or physics — this is the one modifier where POV Cocktail is allowed to sound slightly more like a teacher, while still maintaining the deadpan clinical tone.
- Use real scientific or technical vocabulary (compounds, reactions, dilution, emulsification, etc.) as part of the appeal — precision language is part of the entertainment here.
- These ideas can be the most ambitious/technically difficult to film and generate — that's expected and fine for this category.

WHAT YOU MUST NOT PRODUCE:
- Ideas that use standard bar techniques with "precision" labels instead of actual lab equipment
- Lab equipment used for decoration only — it must change the outcome
- Concepts where the science is invisible to the camera
- Concepts that are purely theoretical or speculative — the science must be real and demonstrable
- Concepts that are too complex - you shouldn't need a chemistry PhD to follow.
""",

    "comparison": """STYLE DIRECTIVE: Head-to-Head Comparison
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ON TOP OF THE GENERIC PROMPT, YOU HAVE BEEN GIVEN THE FOLLOWING ADDITIONAL INSTRUCTIONS FOR A SHEAD-TO-HEAD COMPARISON

Every single idea MUST be a direct comparison between two named, distinct options. 
The video format is: introduce both sides — run identical tests side by side — reveal which produces the better result. There is always a clear winner. The viewer watches because they do not know who wins before the reaveal.
-the comparison must be something people already have opinions about — this is what drives engagement.

WHAT YOU MUST NOT PRODUCE:
- A concept about a single cocktail with no comparison element
- A concept where the verdict is "it depends" or "both are valid"
- A concept where the two options are not clearly named at the concept stage
- Three independent cocktail ideas with a comparison theme but no actual versus structure

""",

    "mythbusting": """STYLE DIRECTIVE: Myth-Busting
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ON TOP OF THE GENERIC PROMPT, YOU HAVE BEEN GIVEN THE FOLLOWING ADDITIONAL INSTRUCTIONS FOR A MYTH-BUSTING THEME.

Every idea is a short, fact-based test of a specific, falsifiable claim about a cocktail or technique.
Focus on testing a commonly held belief, bartending "rule," or popular claim.

REQUIREMENTS FOR THIS:
- Pick myths or claims people actually believe or argue about — the viewer must already have an opinion before the video starts.
- The video must reach a definitive conclusion — confirmed, debunked, or "more complicated than you think" — stated with full clinical confidence regardless of which outcome.
- The claim must be testable and demonstrable on camera. Avoid myths that are purely subjective taste opinions with no measurable answer.
- The myth should feel slightly confrontational to the bartending orthodoxy — POV Cocktail does not hedge.

WHAT YOU MUST NOT PRODUCE:
- Myths with no testable answer (purely preference-based)
- Ideas where the conclusion is "it depends" or "personal choice"
- Ideas that are comparisons in disguise — this format is about a single claim, not two equal sides

""",

    "historical": """STYLE DIRECTIVE: Historical Dive
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ON TOP OF THE GENERIC PROMPT, YOU HAVE BEEN GIVEN THE FOLLOWING ADDITIONAL INSTRUCTIONS FOR A HISTORICAL DIVE THEME.

Every idea explores where a cocktail or technique actually came from — the real story, not the popular version.

REQUIREMENTS FOR THIS:
- The history must be genuinely accurate — do not fabricate dates, names, or origin stories for dramatic effect.
- Find an angle that surprises people: a popular origin story that is actually false, a real inventor nobody remembers, or a technique that disappeared and came back under a different name.
- The hook is the gap between what people think they know and what actually happened.
- POV Cocktail delivers historical fact the same way he delivers a measured temperature: with complete clinical certainty. History is not discussed — it is confirmed.

WHAT YOU MUST NOT PRODUCE:
- Ideas with fabricated or unverifiable history — if the record is genuinely uncertain, find a different angle
- Ideas where the history is well-known and contains no surprising element
- Ideas that are essentially a recipe for a classic drink with a brief history footnote

""",

    "challenge": """STYLE DIRECTIVE: Challenge
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ON TOP OF THE GENERIC PROMPT, YOU HAVE BEEN GIVEN THE FOLLOWING ADDITIONAL INSTRUCTIONS FOR A CHALLENGE THEME.

Every idea is built around a specific constraint or rule that POV Cocktail commits to completely and without acknowledgement.

REQUIREMENTS FOR THIS:
- The constraint itself is the hook — it must be immediately understood and feel slightly absurd or provocative when stated.
- POV Cocktail's deadpan total commitment to following the rule exactly is the comedic engine — he never breaks character, never acknowledges the absurdity, never winks at the camera.
- These ideas should be slightly more comment-bait than other styles — the constraint should invite disagreement or debate by design.
- The constraint must still produce a real cocktail with a real verdict. It is not a stunt — it is an experiment.
- Constraint types to draw from: limited tools, limited time, limited ingredients, forbidden techniques, material substitutions.

WHAT YOU MUST NOT PRODUCE:
- Challenges where the constraint produces no interesting result on camera
- Ideas that are comparisons in disguise — there is one attempt under the rule, not two sides
- Constraints so extreme they produce an undrinkable result — the final product must still be a real cocktail

""",
}

client = genai.Client(api_key=api_key)
logger.info(f"Using Gemini model: {GEMINI_MODEL}")


def _format_avoid_block(avoid_ideas):
    """Build the 'already proposed this session' block from the recent batches
    the frontend sent. Returns '' when there is nothing to avoid (first
    generation of a session), so the prompt is unchanged in that case."""
    if not avoid_ideas:
        return ""

    lines = []
    for idea in avoid_ideas:
        title    = (idea.get("title") or "").strip()
        cocktail = (idea.get("cocktail") or "").strip()
        if not title and not cocktail:
            continue
        if cocktail:
            lines.append(f"- {title}  (cocktail: {cocktail})")
        else:
            lines.append(f"- {title}")

    if not lines:
        return ""

    listed = "\n".join(lines)
    return f"""
    ------------------
    ALREADY PROPOSED THIS SESSION — DO NOT REPEAT
    ------------------
    The ideas below were already shown to the user in this brainstorming session and were NOT chosen.
    Do not repeat them. Avoid the same cocktails, the same hooks, and the same angles, including close
    variations or rewordings of them. Generate 9 genuinely different ideas: prefer different cocktails,
    and where a cocktail must reappear, the angle must be clearly distinct from any listed below.

    {listed}
    """


# How many of the most recent videos' cocktails are off-limits for new ideas.
# A cocktail used this recently can't be suggested again; one used longer ago can.
RECENT_COCKTAIL_BAN_COUNT = 5


def _recent_cocktails(videos, n=RECENT_COCKTAIL_BAN_COUNT):
    """Return the distinct cocktails from the n most recent videos.

    Recency is by protocol_id, which is assigned MAX+1 on every save, so the
    highest ids are always the latest videos (more reliable than string-sorting
    a free-form date_created). Blanks are skipped; order is most-recent-first
    with duplicates removed."""
    ordered = sorted(videos, key=lambda v: (v.get("id") or 0), reverse=True)
    seen, cocktails = set(), []
    for v in ordered[:n]:
        name = (v.get("cocktail") or "").strip()
        key  = name.lower()
        if name and key not in seen:
            seen.add(key)
            cocktails.append(name)
    return cocktails


def _format_banned_cocktails_block(cocktails):
    """Hard rule: do not propose any cocktail used in the last few videos.
    Returns '' when there are none (e.g. an empty channel), leaving the
    prompt unchanged."""
    if not cocktails:
        return ""
    listed = "\n".join(f"- {c}" for c in cocktails)
    return f"""
    ------------------
    RECENTLY USED COCKTAILS — HARD RULE, DO NOT USE
    ------------------
    These cocktails were the subject of the last {RECENT_COCKTAIL_BAN_COUNT} videos. To avoid
    short-term repetition, NONE of your 9 ideas may use any of these cocktails, in any form or
    angle. This is an absolute constraint, not a preference. A cocktail used earlier than these
    is fine to revisit with a fresh angle; only the ones listed below are off-limits.

    {listed}
    """


def run(style="bar", avoid_ideas=None):
    style_block = STYLE_MODIFIERS.get(style, STYLE_MODIFIERS["bar"])

    # Load previous videos from database for context
    emit("context", "active", "Loading historical video context…")
    videos = get_all_videos()
    logger.info(f"Loaded {len(videos)} previous videos from database (style={style})")
    emit("context", "done", f"Loaded {len(videos)} previous videos.")
    video_context = str(videos)

    banned_cocktails = _recent_cocktails(videos)
    banned_block = _format_banned_cocktails_block(banned_cocktails)
    if banned_block:
        logger.info(f"Banning cocktails from the last {RECENT_COCKTAIL_BAN_COUNT} videos: {banned_cocktails}")
        emit("context", "done", f"Excluding {len(banned_cocktails)} recently-used cocktails.")

    avoid_block = _format_avoid_block(avoid_ideas)
    if avoid_block:
        logger.info(f"Avoiding {len(avoid_ideas)} ideas already shown this session.")
        emit("context", "done", f"Avoiding {len(avoid_ideas)} ideas from earlier this session.")

    full_prompt = f"""
    {system_prompt}

    ------------------
    {style_block}
    ------------------

    ------------------
    PREVIOUS VIDEOS
    ------------------
    Take inspiration from the format and titles of the channel's previous videos. Each entry
    includes a rating where available — lean towards the angles, formats, and styles of the
    highest-rated videos, and away from low-rated ones. (The 'cocktail' field is the drink each
    video was about; see the HARD RULE below for which of these are temporarily off-limits.)
    {video_context}
    {banned_block}
    {avoid_block}
    ------------------
    TASK
    ------------------

    Generate 9 new potential protocol ideas for POV Cocktail in the previously outlined format, strictly following the STYLE DIRECTIVE above.
    """

    emit("prompt", "done", "Strategy prompt assembled for Gemini.")

    # Live-progress Gemini call with retry/backoff (see agent_progress.call_gemini).
    return call_gemini(client, GEMINI_MODEL, full_prompt, "Creative Strategist")
    

if __name__ == "__main__":
    raw = sys.stdin.read().strip()
    data = json.loads(raw) if raw else {}
    result = run(data.get("style", "bar"), data.get("avoid"))
    print(result)