# Architecture & Conventions

Detailed architecture notes and conventions for the POV Cocktail Video Generator. Start with
`README.md` for setup and the high-level tour; this document is the deeper reference.

## What This Project Is

POV Cocktail Video Generator is an AI-powered YouTube content pipeline for a cocktail/drinks channel ("POV Cocktail"). It uses Google Gemini to generate complete video production packages ("Protocols") — from concept through to upload-ready copy. A Flask web dashboard (`src/orchestrator/main.py`) serves as the UI and orchestrator for an 8-agent pipeline.

> The output unit is a **Protocol** = one short-form video. The end product of the pipeline is a set of shot-by-shot text prompts (Ideogram stills + Kling image-to-video), voiceover lines, and an upload package. The user pastes those prompts into Ideogram/Kling manually, then assembles the clips in an external editor (CapCut). There is currently **no automated video assembly, VO audio rendering, or generation-API integration** — that handoff is fully manual.

## Running the App

From `pov-cocktail-video-generator/`:

```bash
pip install -r requirements.txt
python src/orchestrator/main.py
```

Then open `http://localhost:5000` in Chrome.

## Environment Setup

Requires a `.env` file in `pov-cocktail-video-generator/` with:

```
GOOGLE_API_KEY=your_key_here
```

The active Gemini model is set in `src/config/geminiAPIsettings.py` (`GEMINI_MODEL` — currently `gemini-2.5-flash`).

**Per-agent generation config:** output variance is tuned centrally via `AGENT_TEMPERATURES` in `geminiAPIsettings.py`. `config_for(label)` builds a `GenerateContentConfig` (temperature) for each agent, and `call_gemini(..., config=None)` in `agents/agent_progress.py` looks it up by the agent's `label` and passes it into the Gemini call. Idea/story agents run hot (~0.85); rule-following agents that must copy prop names/stamps verbatim run cold (~0.3).

## Architecture

**The "Protocol" is the core unit** — one Protocol = one YouTube video. The pipeline takes an idea from concept to upload-ready copy through 8 agents run in sequence by the user.

**Key data flow:**
1. User clicks "Generate Ideas" → orchestrator spawns `agent1creativestrategist.py` as a subprocess
2. Agent calls Gemini with the system prompt + style modifier + previous videos from DB
3. Agent prints raw Gemini text to stdout; orchestrator parses it into up to **9** idea dicts
4. User picks one idea → orchestrator saves it to SQLite and activates the pipeline
5. User runs agents 3–7 in sequence, each building on the previous agent's output
6. All pipeline state is saved to `data/sessions.json` so the browser session can be restored

**Agent subprocess pattern:** all 8 agents are called as subprocesses via `_run_agent()` in `main.py`. They receive a JSON blob on stdin and print their result to stdout. They are never imported. The retrying Gemini call itself lives in `agents/agent_progress.py` (`call_gemini`, 3 attempts w/ backoff, emits `@@PROGRESS@@` events on stderr).

## The 8 Agents

| # | File | Prompt | Purpose |
|---|------|--------|---------|
| 1 | `agent1creativestrategist.py` | `creative_strategist_prompt.md` | Generates up to 9 video concept ideas (TITLE + COCKTAIL only) |
| 2 | `agent2director.py` | `director_agent_prompt.md` | Develops storyboard from chosen idea |
| 3 | `agent3sciencedeveloper.py` | `science_developer_prompt.md` | Writes science/technique brief |
| 4 | `agent4recipearchitect.py` | `recipe_architect_prompt.md` | Writes full recipe |
| 5 | `agent5continuitymanager.py` | `continuity_manager_prompt.md` | 3-part continuity spec (visual blocks, props JSON, vessel state machine) |
| 6 | `agent6scenecreator.py` | `scene_creator_prompt.md` | Shot-by-shot scene breakdown with Ideogram + Kling prompts |
| 7 | `agent7uploadpackager.py` | `upload_packager_prompt.md` | Generates complete YouTube upload package |
| 8 | `agent8scenereviewer.py` | `scene_reviewer_prompt.md` | QA pass over the scene breakdown — fixes cross-clip inconsistencies, removes instrument/admin clutter, adds a `USER CHECK` + `CHANGE` line to every clip |

**Pipeline run order in the UI:** ideas (1) → science (3) → recipe (4) → continuity (5) → storyboard/director (2) → scenes (6) → scene review (8, **auto-runs**) → upload (7). Note the science/recipe/continuity briefs are generated **before** the director storyboard, even though the director is agent #2.

**Agent 8 (Scene Reviewer)** is wired to `POST /api/run-scene-reviewer`. It is **mandatory and auto-chained**: `triggerScenes()` calls `refineScenes(null, true)` automatically as soon as the Scene Creator draft is parsed, so the user always lands on the reviewed breakdown. If the review call fails, `refineScenes` falls back to rendering the unreviewed creator draft (guarded by the `scenesReviewed` flag) so an API blip can't trap the user; `openUploadWarning()` nudges if `scenesReviewed` is still false. The "🔍 Review & Refine (again)" button re-runs it manually (`refineScenes(this)`, `auto=false`). It re-parses through the same `_parse_scenes()` as agent 6 and returns phases in the identical shape, plus per-clip `CHANGE` (edited/added/unchanged) and `USER CHECK` fields.

**Agent 1 style modifiers** (`STYLE_MODIFIERS` dict in `agent1creativestrategist.py`):
- `bar` — classic bar techniques, luxury craft feel
- `science` — real lab techniques with dramatic visual transformation
- `comparison` — head-to-head versus format, always a clear winner
- `mythbusting` — three sub-types: (A) myth bust, (B) historical dive, (C) challenge

**Agent 1 output format:** plain text only — `TITLE:` and `COCKTAIL:` fields per idea, separated by blank lines. No other fields. The prompt deliberately outputs nothing else.

**Agents 3–7 output format:** `%%TAG%%` delimiter blocks, e.g. `%%SCIENCE_BRIEF%%...%%END_SCIENCE_BRIEF%%`. Parsed on the backend or (for agent 7) in the frontend JS via `_parseUploadSection(raw, tag)`.

**Agent 7 upload package sections (%%TAGS%%):**
- `TITLE_OPTIONS` — 4 title variants: A=Recommended, B=Technique Led, C=Outcome Led, D=Provocative
- `DESCRIPTION` — full YouTube description (hook, key numbers, technique, recipe, closing, back-links, hashtags)
- `PINNED_COMMENT` — post immediately after upload
- `SECOND_COMMENT` — post 10 mins after upload
- `CHECKLIST` — 13-item upload settings checklist

## Idea Parsing (`parse_ideas_from_response`)

Located in `main.py` around line 95. Uses 5 fallback strategies in order:
1. `TITLE:` line anchors (primary — matches the current prompt format)
2. `---` horizontal rule splits
3. Numbered section headers (`Idea 1`, `Protocol 2`, etc.) — regex `[1-9]`
4. Bold numbered headers (`**1.**`, `**1:**`) — regex `[1-9]`
5. Even ninths by line count (last resort)

`MAX_IDEAS = 9`. Threshold for triggering a strategy is `>= 2` sections found.

`_extract_idea_fields(text)` — extracts only `title`, `cocktail`, and `idea_text` (the full raw chunk). No `summary` field. No excerpt display on idea cards.

## Session Persistence

Sessions are saved to `data/sessions.json`. Each session stores the chosen idea plus all pipeline outputs.

**`pipeline_fields`** (the fields saved/restored per session):
```
science_output, recipe_output, continuity_output, storyboard_output, scenes_output, upload_output
```

**Pipeline stages** (used in `stage` field of saved sessions):
`idea_selected` → `science_complete` → `recipe_complete` → `continuity_complete` → `storyboard_complete` → `scenes_complete` → `upload_complete`

Session save: `POST /api/session/save`
Session restore: `GET /api/session/<session_id>`

## Database Layer

`src/database/` — thin SQLite wrappers. Agents must never call SQLite directly.

**Tables in `data/pov_cocktail.db`:**
- `videos` — completed/logged Protocol records
- `working_ideas` — ideas selected for active development
- `potential_future_ideas` — ideas saved for later

## Frontend (`pov_cocktail_dashboard.html`)

Single-page app served by Flask. Key JavaScript state variables:

```javascript
let currentIdea = null;        // {title, cocktail, idea_text, ...}
let scienceOutput = null;
let recipeOutput = null;
let continuityOutput = null;
let storyboardOutput = null;
let scenesOutput = null;
let uploadOutput = null;

let scienceHistory = [];       // undo stacks per agent
let recipeHistory = [];
// ... etc
let uploadHistory = [];
```

**`DEEP_VIEWS`** — array of view IDs that show the hero header: `['view-upload']` (and possibly others). Controls hero visibility when switching views.

**`showPipelineState(prefix, state)`** — toggles between `ready`/`generating`/`output` states for each pipeline section. Prefix examples: `'sc'` for scenes, `'up'` for upload.

**`switchView(viewId, title)`** — navigates between dashboard panes.

**Upload warning modal** — shown when clicking "Proceed to Upload →" on the scenes page. Warns that session is already saved, lets user confirm before switching to `view-upload`.

## Key Conventions

- Agent scripts communicate via **stdin JSON in / stdout text out**. Never import agents.
- `_run_agent(filename, stdin_data, label, timeout=180, job_id=None)` — the single helper for all agent calls. Handles cancellation via `job_id`.
- `loguru` is used for logging inside all agent scripts.
- `data/` is the only place for persistent data. `logs/` for runtime logs only.
- Generated Protocol exports (`.md`) go in `protocols/<id>-<name>/`.
- Generated media assets go in `assets/<id>-<name>/`.
- `src/storage/`, `src/generation/`, `src/protocols/` — stubs, not yet implemented.
