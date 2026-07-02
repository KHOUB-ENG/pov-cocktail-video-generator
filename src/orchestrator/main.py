"""
POV COCKTAIL VIDEO GENERATOR — main.py
================================
Run this file in your VS Code terminal:
    python main.py

Then open Chrome and go to:
    http://localhost:5000
"""

from flask import Flask, jsonify, request, send_from_directory, Response
import collections
import json
import os
import re
import sqlite3
import subprocess
import sys
import threading
import time
from pathlib import Path

app = Flask(__name__, static_folder=".")

# -----------------------------------------------------------------
# SUBPROCESS JOB TRACKING (for cancellation + live progress)
# -----------------------------------------------------------------
_active_jobs     = {}            # job_id -> Popen (for cancellation)
_jobs_lock       = threading.Lock()
_cancelled_jobs  = set()         # job_ids the user explicitly cancelled
_job_progress    = {}            # job_id -> {"events":[...], "done":bool, "error":dict|None}
_progress_lock   = threading.Lock()
sys.path.append(str(Path(__file__).resolve().parents[1]))  # Add parent to path for imports

from database.add_video import add_video
from database.get_next_protocol_id import get_next_protocol_id
from database.get_all_videos import get_all_videos
from database.update_notes import update_notes
from database.add_to_working_idea_database import (
    add_to_working_idea_database,
    add_to_future_ideas_database,
    get_all_working_ideas
)


# -----------------------------------------------------------------
# AGENT UTILITIES
# -----------------------------------------------------------------

def _find_agent(filename):
    """Locate an agent script from common project layouts."""
    base = Path(__file__).resolve().parent
    candidates = [
        base / "agents" / filename,
        base / filename,
        base.parent / "agents" / filename,
        base.parent / "src" / "agents" / filename,
    ]
    for p in candidates:
        if p.exists():
            return p
    return None


def _find_agent1():
    return _find_agent("agent1creativestrategist.py")


def _extract_idea_fields(text):
    """
    Extract title and cocktail from a single idea block.
    Returns dict with keys: title, cocktail, idea_text.
    """
    lines = [l.strip() for l in text.split('\n') if l.strip()]
    title = ''
    cocktail = ''

    for line in lines:
        clean = re.sub(r'\*{1,2}', '', line).strip()
        lower = clean.lower()

        if not title and re.match(r'^(?:video\s+)?title\s*:', lower):
            title = re.sub(r'^(?:video\s+)?title\s*:\s*', '', clean, flags=re.IGNORECASE).strip()

        elif not cocktail and re.match(r'^cocktail\s*:', lower):
            cocktail = re.sub(r'^cocktail\s*:\s*', '', clean, flags=re.IGNORECASE).strip()

    # Fallback: first non-empty line as title
    if not title and lines:
        title = re.sub(r'\*{1,2}', '', lines[0]).strip()
        title = re.sub(r'^(?:video\s+)?title\s*:\s*', '', title, flags=re.IGNORECASE).strip()

    return {
        'title': title,
        'cocktail': cocktail,
        'idea_text': text.strip()
    }


def parse_ideas_from_response(text):
    """
    Parse Gemini response text into a list of up to 9 idea dicts.
    Tries 5 strategies in order, falling back gracefully.
    """
    ideas = []
    MAX_IDEAS = 9

    # Strategy 0: TITLE: line anchors — primary format
    title_markers = list(re.finditer(r'(?:^|\n)\s*(?:\*{1,2})?TITLE\s*:', text, re.IGNORECASE))
    if len(title_markers) >= 2:
        markers = title_markers[:MAX_IDEAS]
        positions = [m.start() for m in markers] + [len(text)]
        parts = [text[positions[i]:positions[i + 1]].strip() for i in range(len(markers))]
        for part in parts:
            ideas.append(_extract_idea_fields(part))
        return ideas

    # Strategy 1: Split on --- horizontal rules
    if text.count('---') >= 2:
        parts = [p.strip() for p in re.split(r'\n\s*---+\s*\n', text) if p.strip()]
        if len(parts) >= 2:
            for part in parts[:MAX_IDEAS]:
                ideas.append(_extract_idea_fields(part))
            return ideas

    # Strategy 2: Numbered idea/protocol sections
    split_pattern = r'(?:^|\n)(?:#{1,3}\s*)?(?:\*{1,2})?(?:Idea|IDEA|Protocol|PROTOCOL|Option|OPTION)\s*[1-9#]?[.:)\s]\s*(?:\*{1,2})?'
    sections = [s.strip() for s in re.split(split_pattern, text, flags=re.IGNORECASE) if s.strip()]
    if len(sections) >= 2:
        for part in sections[:MAX_IDEAS]:
            ideas.append(_extract_idea_fields(part))
        return ideas

    # Strategy 3: Bold numbered headers (**1.** / **1:** up to 9)
    sections2 = [s.strip() for s in re.split(r'\*{2}\s*[1-9]\s*[.:]\s*\*{2}', text) if s.strip()]
    if len(sections2) >= 2:
        for part in sections2[:MAX_IDEAS]:
            ideas.append(_extract_idea_fields(part))
        return ideas

    # Strategy 4: Even fifths by line count
    lines = [l for l in text.split('\n') if l.strip()]
    chunk = max(1, len(lines) // MAX_IDEAS)
    for i in range(MAX_IDEAS):
        part = '\n'.join(lines[i * chunk: (i + 1) * chunk])
        if part.strip():
            ideas.append(_extract_idea_fields(part))

    return ideas


# -----------------------------------------------------------------
# SERVE WEB APP INTERFACE & STATIC ASSETS
# -----------------------------------------------------------------

@app.route("/")
def home():
    print("\n[WEB INTERFACE] Serving dashboard homepage...")
    resp = send_from_directory(".", "pov_cocktail_dashboard.html")
    # Never cache the dashboard during development — otherwise browsers keep
    # serving a stale copy after edits.
    resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    resp.headers["Pragma"] = "no-cache"
    resp.headers["Expires"] = "0"
    return resp


@app.route("/logo.jpg")
def serve_logo():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    logo_path = os.path.join(base_dir, "logo.jpg")
    if os.path.exists(logo_path):
        return send_from_directory(base_dir, "logo.jpg")
    print(f"[ERROR] Logo missing! Looked inside: {base_dir}")
    return jsonify({"error": "File not found"}), 404


# -----------------------------------------------------------------
# API DATA EXCHANGE ENDPOINTS
# -----------------------------------------------------------------

@app.route("/api/videos", methods=["POST"])
def add_video_route():
    data = request.get_json()
    add_video(
        protocol_id=int(data["protocol_id"]),
        cocktail=data["cocktail"],
        title=data["title"],
        date_created=data["date_created"],
        notes=data["notes"],
        style=data.get("style"),
    )
    return jsonify({"success": True, "message": "Video saved successfully."})


@app.route("/api/next_protocol_id")
def next_protocol_id():
    return jsonify({"protocol_id": get_next_protocol_id()})


@app.route("/api/videos", methods=["GET"])
def get_videos_route():
    return jsonify(get_all_videos())


@app.route("/api/update_notes", methods=["POST"])
def update_notes_route():
    data = request.get_json()
    success = update_notes(
        protocol_id=int(data["protocol_id"]),
        new_notes=data["notes"],
        append=data.get("append", False)
    )
    if not success:
        return jsonify({"success": False, "message": "Protocol not found."}), 404
    return jsonify({"success": True, "message": "Notes updated successfully."})


@app.route("/api/ideas", methods=["GET"])
def get_existing_ideas():
    print("[DB INTERACTION] Streaming working ideas from database...")
    rows = get_all_working_ideas()
    return jsonify([
        {
            "id":       r["id"],
            "title":    r["title"],
            "cocktail": r["cocktail"],
            "idea_text": r["idea_text"],
            "desc":     r["summary"] or r["cocktail"] or ""
        }
        for r in rows
    ])


@app.route("/api/unfinished", methods=["GET"])
def get_unfinished_protocols():
    print("[DB INTERACTION] Unfinished protocols table not yet implemented.")
    return jsonify([])


@app.route("/api/run-creative-strategist", methods=["POST"])
def run_creative_strategist():
    """
    Runs agent1creativestrategist.py as a subprocess, captures its stdout,
    parses the Gemini response into 3 structured idea dicts, and returns them.
    """
    print("\n[ORCHESTRATOR ALERT] Creative Strategist engine trigger signal fired.")

    agent_path = _find_agent1()
    if not agent_path:
        print("[ERROR] agent1creativestrategist.py not found in expected locations.")
        return jsonify({
            "success": False,
            "error": "Agent script not found. Ensure agent1creativestrategist.py is in your agents/ directory.",
            "ideas": []
        }), 404

    body    = request.get_json() or {}
    style   = body.get("style", "bar")
    job_id  = body.get("job_id")
    # Ideas already shown to the user this brainstorm session — the agent avoids
    # repeating them. Frontend sends only the last few batches; cleared on Develop.
    avoid   = body.get("avoid", []) or []
    print(f"[AGENT] Launching creative strategist (style={style}, job={job_id}, avoid={len(avoid)})")

    raw, err = _run_agent(
        "agent1creativestrategist.py",
        {"style": style, "avoid": avoid},
        "Creative Strategist",
        timeout=180,
        job_id=job_id,
    )
    if err:
        return _agent_error_response(err, ideas=[])

    ideas = parse_ideas_from_response(raw)
    print(f"[AGENT] Parsed {len(ideas)} ideas.")
    if not ideas:
        return jsonify({"success": False,
                        "error": "No ideas could be extracted from the Gemini response. Try regenerating.",
                        "error_code": "parse_failed",
                        "error_detail": (raw or "")[:1200],
                        "ideas": [], "raw": raw}), 502
    return jsonify({"success": True, "ideas": ideas, "raw": raw})


@app.route("/api/save-working-idea", methods=["POST"])
def save_working_idea():
    """Save a selected idea to the working_ideas table for active development."""
    data = request.get_json()
    try:
        protocol_id = get_next_protocol_id()
        idea_id = add_to_working_idea_database(
            protocol_id=protocol_id,
            title=data.get('title', ''),
            cocktail=data.get('cocktail', ''),
            idea_text=data.get('idea_text', ''),
            summary=data.get('summary', '')
        )
        print(f"[DB] Working idea saved — ID: {idea_id}, Protocol: {protocol_id}")
        return jsonify({"success": True, "id": idea_id, "protocol_id": protocol_id})
    except Exception as e:
        print(f"[ERROR] Failed to save working idea: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/delete-working-idea/<int:idea_id>", methods=["DELETE"])
def delete_working_idea(idea_id):
    from database.add_to_working_idea_database import DB_PATH
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.execute("DELETE FROM working_ideas WHERE id = ?", (idea_id,))
        conn.commit()
        conn.close()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/delete-video/<int:protocol_id>", methods=["DELETE"])
def delete_video(protocol_id):
    db_path = Path(__file__).resolve().parents[2] / "data" / "pov_cocktail.db"
    try:
        conn = sqlite3.connect(db_path)
        conn.execute("DELETE FROM videos WHERE protocol_id = ?", (protocol_id,))
        conn.commit()
        conn.close()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/clear-working-ideas", methods=["POST"])
def clear_working_ideas():
    """Delete all rows from the working_ideas table."""
    from database.add_to_working_idea_database import DB_PATH
    import sqlite3
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.execute("DELETE FROM working_ideas")
        conn.commit()
        conn.close()
        print("[DB] working_ideas table cleared.")
        return jsonify({"success": True})
    except Exception as e:
        print(f"[ERROR] Failed to clear working ideas: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/save-future-idea", methods=["POST"])
def save_future_idea():
    """Save a selected idea to the potential_future_ideas table for later."""
    data = request.get_json()
    try:
        protocol_id = get_next_protocol_id()
        idea_id = add_to_future_ideas_database(
            protocol_id=protocol_id,
            title=data.get('title', ''),
            cocktail=data.get('cocktail', ''),
            idea_text=data.get('idea_text', ''),
            summary=data.get('summary', '')
        )
        print(f"[DB] Future idea saved — ID: {idea_id}, Protocol: {protocol_id}")
        return jsonify({"success": True, "id": idea_id, "protocol_id": protocol_id})
    except Exception as e:
        print(f"[ERROR] Failed to save future idea: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


# -----------------------------------------------------------------
# DIRECTOR AGENT
# -----------------------------------------------------------------

def _set_progress(job_id, event):
    """Append one live progress event (a dict) for a running job."""
    if not job_id:
        return
    with _progress_lock:
        st = _job_progress.setdefault(job_id, {"events": [], "done": False, "error": None})
        st["events"].append(event)


def _finish_progress(job_id, err):
    """Mark a job done. `err` is None on success or an error dict on failure."""
    if not job_id:
        return
    with _progress_lock:
        st = _job_progress.setdefault(job_id, {"events": [], "done": False, "error": None})
        st["done"]  = True
        st["error"] = err


def _agent_error_response(err, **extra):
    """Turn an error dict from _run_agent into a categorised JSON response.

    `error` stays a plain string (backward compatible); `error_code` and
    `error_detail` let the frontend show the failure *type* and the raw stderr.
    """
    status = 499 if err.get("code") == "cancelled" else err.get("http", 500)
    body = {
        "success":      False,
        "error":        err.get("message", "Agent error."),
        "error_code":   err.get("code", "error"),
        "error_detail": err.get("detail", ""),
    }
    body.update(extra)
    return jsonify(body), status


def _run_agent(agent_filename, stdin_data, label, timeout=180, job_id=None):
    """Run an agent subprocess, streaming @@PROGRESS@@ markers from its stderr
    into _job_progress (polled by /api/job-status), and returning
    (raw_stdout, error_dict_or_None). The error dict carries a `code` so the
    UI can distinguish timeout / crash / empty-output / cancellation."""
    agent_path = _find_agent(agent_filename)
    if not agent_path:
        return None, {"code": "not_found", "http": 404,
                      "message": f"{agent_filename} not found."}

    print(f"\n[ORCHESTRATOR] {label} trigger fired.")
    if job_id:
        with _progress_lock:
            # Light prune so long-lived servers don't accumulate stale jobs.
            if len(_job_progress) > 60:
                for k in list(_job_progress.keys())[:30]:
                    _job_progress.pop(k, None)
            _job_progress[job_id] = {"events": [], "done": False, "error": None}

    try:
        proc = subprocess.Popen(
            [sys.executable, str(agent_path)],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        if job_id:
            with _jobs_lock:
                _active_jobs[job_id] = proc

        # Feed stdin on a thread so a large payload can't deadlock on a full pipe.
        def _feed_stdin():
            try:
                proc.stdin.write(json.dumps(stdin_data).encode("utf-8"))
                proc.stdin.close()
            except Exception:
                pass
        threading.Thread(target=_feed_stdin, daemon=True).start()

        # Drain stdout (the real agent result) on a thread.
        stdout_chunks = []
        def _drain_stdout():
            try:
                for chunk in iter(lambda: proc.stdout.read(4096), b""):
                    stdout_chunks.append(chunk)
            except Exception:
                pass
        t_out = threading.Thread(target=_drain_stdout, daemon=True)
        t_out.start()

        # Watchdog enforces the timeout — the stderr readline loop would
        # otherwise block forever on a hung agent.
        timed_out = {"v": False}
        def _watchdog():
            end = time.time() + timeout
            while time.time() < end:
                if proc.poll() is not None:
                    return
                time.sleep(0.4)
            if proc.poll() is None:
                timed_out["v"] = True
                try:
                    proc.kill()
                except Exception:
                    pass
        threading.Thread(target=_watchdog, daemon=True).start()

        # Read stderr line-by-line; surface @@PROGRESS@@ markers as they arrive.
        stderr_tail = collections.deque(maxlen=40)
        for raw_line in iter(proc.stderr.readline, b""):
            line = raw_line.decode("utf-8", errors="replace").rstrip("\r\n")
            if not line:
                continue
            _, sep, rest = line.partition("@@PROGRESS@@ ")
            if sep:
                try:
                    evt = json.loads(rest)
                except Exception:
                    evt = {"stage": "log", "status": "active", "note": rest}
                _set_progress(job_id, evt)
            else:
                stderr_tail.append(line)

        proc.wait()
        t_out.join(timeout=5)
        if job_id:
            with _jobs_lock:
                _active_jobs.pop(job_id, None)

        stdout_b   = b"".join(stdout_chunks)
        stderr_txt = ("\n".join(stderr_tail))[-1200:]
        rc         = proc.returncode

        was_cancelled = False
        if job_id:
            with _jobs_lock:
                was_cancelled = job_id in _cancelled_jobs
                _cancelled_jobs.discard(job_id)

        if was_cancelled:
            err = {"code": "cancelled", "http": 499, "message": "Cancelled by user."}
            _finish_progress(job_id, err)
            return None, err
        if timed_out["v"]:
            err = {"code": "timeout", "http": 504,
                   "message": f"{label} timed out after {timeout}s — Gemini never responded.",
                   "detail": stderr_txt}
            print(f"[ERROR] {label} timed out after {timeout}s.")
            _finish_progress(job_id, err)
            return None, err
        if rc != 0:
            err = {"code": "agent_failed", "http": 500,
                   "message": f"{label} crashed (exit code {rc}).",
                   "detail": stderr_txt or "No stderr captured."}
            print(f"[ERROR] {label} exit {rc}:\n{stderr_txt}")
            _finish_progress(job_id, err)
            return None, err

        raw = stdout_b.decode("utf-8", errors="replace").strip()
        if not raw or len(raw) < 30:
            err = {"code": "empty_output", "http": 502,
                   "message": f"{label} returned no usable output.",
                   "detail": stderr_txt or "No stderr captured."}
            _finish_progress(job_id, err)
            return None, err

        _finish_progress(job_id, None)
        return raw, None

    except Exception as e:
        err = {"code": "exception", "http": 500, "message": str(e)}
        _finish_progress(job_id, err)
        return None, err


@app.route("/api/run-science-developer", methods=["POST"])
def run_science_developer():
    data   = request.get_json()
    job_id = data.get('job_id')
    raw, err = _run_agent(
        "agent3sciencedeveloper.py",
        {'title': data.get('title',''), 'cocktail': data.get('cocktail',''), 'idea_text': data.get('idea_text','')},
        "Science Developer", job_id=job_id
    )
    if err:
        return _agent_error_response(err)
    return jsonify({"success": True, "raw": raw})


@app.route("/api/run-recipe-architect", methods=["POST"])
def run_recipe_architect():
    data   = request.get_json()
    job_id = data.get('job_id')
    raw, err = _run_agent(
        "agent4recipearchitect.py",
        {'title': data.get('title',''), 'cocktail': data.get('cocktail',''),
         'idea_text': data.get('idea_text',''), 'science': data.get('science','')},
        "Recipe Architect", job_id=job_id
    )
    if err:
        return _agent_error_response(err)
    return jsonify({"success": True, "raw": raw})


@app.route("/api/run-continuity-manager", methods=["POST"])
def run_continuity_manager():
    data   = request.get_json()
    job_id = data.get('job_id')
    raw, err = _run_agent(
        "agent5continuitymanager.py",
        {
            'title':     data.get('title',''),
            'cocktail':  data.get('cocktail',''),
            'idea_text': data.get('idea_text',''),
            'science':   data.get('science',''),
            'recipe':    data.get('recipe',''),
        },
        "Continuity Manager", job_id=job_id
    )
    if err:
        return _agent_error_response(err)

    # `raw` (the full 3-part document) is what gets passed downstream — see
    # pov_cocktail_dashboard.html's triggerContinuity(). `continuity_obj` and `warnings`
    # below are best-effort extras for callers that want the structured props
    # spec or a heads-up that the model didn't follow the tagged format.
    warnings = []
    continuity_obj = None

    json_tagged = re.search(
        r'%%CONTINUITY_PROPS_JSON%%([\s\S]*?)%%END_CONTINUITY_PROPS_JSON%%', raw
    )
    if json_tagged:
        fenced = re.sub(r'^```(?:json)?\s*|```\s*$', '', json_tagged.group(1).strip(), flags=re.MULTILINE)
        try:
            continuity_obj = json.loads(fenced)
        except Exception:
            warnings.append("PROPS_JSON tag found but contents are not valid JSON")
    else:
        warnings.append("Missing %%CONTINUITY_PROPS_JSON%% tag — model did not follow the tagged output format")
        # Fall back to brace-matching for older/malformed responses.
        json_match = re.search(r'\{[\s\S]+\}', raw, re.DOTALL)
        if json_match:
            try:
                continuity_obj = json.loads(json_match.group(0))
            except Exception:
                pass

    if '%%CONTINUITY_VISUAL_BLOCKS%%' not in raw:
        warnings.append("Missing %%CONTINUITY_VISUAL_BLOCKS%% tag — Part 1 (environment/hand/camera blocks) may be absent")
    if '%%CONTINUITY_VESSEL_STATE_MACHINE%%' not in raw:
        warnings.append("Missing %%CONTINUITY_VESSEL_STATE_MACHINE%% tag — Part 3 (vessel state machine) may be absent")

    return jsonify({"success": True, "continuity": continuity_obj, "raw": raw, "warnings": warnings})


@app.route("/api/run-director-agent", methods=["POST"])
def run_director_agent():
    data      = request.get_json()
    title     = data.get('title', '')
    cocktail  = data.get('cocktail', '')
    idea_text = data.get('idea_text', '')
    science   = data.get('science', '')
    recipe    = data.get('recipe', '')
    continuity = data.get('continuity', {})
    job_id    = data.get('job_id')

    if not title or not idea_text:
        return jsonify({"success": False, "error": "Missing title or idea_text."}), 400

    raw, err = _run_agent(
        "agent2director.py",
        {'title': title, 'cocktail': cocktail, 'idea_text': idea_text,
         'science': science, 'recipe': recipe, 'continuity': continuity},
        "Director Agent", job_id=job_id
    )
    if err:
        return _agent_error_response(err)
    return jsonify({"success": True, "raw": raw})


def _parse_scenes(raw):
    """Parse scene creator %%DELIMITER%% output into structured data."""
    phases = []
    phase_blocks = re.split(r'%%PHASE\s+(\d+)%%', raw)
    # phase_blocks[0] = pre-content, then alternating: phase_num, phase_body
    i = 1
    while i < len(phase_blocks) - 1:
        phase_num  = phase_blocks[i].strip()
        phase_body = phase_blocks[i + 1]
        i += 2

        def get_field(text, key):
            m = re.search(rf'^{key}\s*:\s*(.+)', text, re.MULTILINE | re.IGNORECASE)
            return m.group(1).strip() if m else ''

        phase = {
            'number':   phase_num,
            'name':     get_field(phase_body, 'NAME'),
            'timecode': get_field(phase_body, 'TIMECODE'),
            'clips_count': get_field(phase_body, 'TOTAL CLIPS') or get_field(phase_body, 'CLIPS'),
            'duration': get_field(phase_body, 'TOTAL DURATION') or get_field(phase_body, 'DURATION'),
            'clips': []
        }

        clip_blocks = re.split(r'%%CLIP\s+([\d.]+)%%', phase_body)
        j = 1
        while j < len(clip_blocks) - 1:
            clip_num  = clip_blocks[j].strip()
            clip_body = clip_blocks[j + 1]
            j += 2

            def get_section(text, tag):
                m = re.search(rf'%%{tag}%%\s*(.*?)(?=%%|\Z)', text, re.DOTALL | re.IGNORECASE)
                return m.group(1).strip() if m else ''

            vo_block = get_section(clip_body, 'VOICEOVER')
            vo_line  = re.search(r'LINE\s*:\s*(.+)',      vo_block, re.IGNORECASE)
            vo_speed = re.search(r'SPEED\s*:\s*(.+)',     vo_block, re.IGNORECASE)
            vo_stab  = re.search(r'STABILITY\s*:\s*(.+)', vo_block, re.IGNORECASE)
            vo_text  = re.search(r'TEXT\s*:\s*"(.*)"',   vo_block, re.IGNORECASE | re.DOTALL)

            def strip_shot_type(block):
                m = re.match(r'Shot\s+type\s*:\s*(.+)\n?', block, re.IGNORECASE)
                shot_type = m.group(1).strip() if m else ''
                clean = re.sub(r'^Shot\s+type\s*:.+\n?', '', block, flags=re.IGNORECASE).strip()
                return shot_type, clean

            ideogram_raw = get_section(clip_body, 'IDEOGRAM')
            kling_raw    = get_section(clip_body, 'KLING')
            shot_type, ideogram_clean = strip_shot_type(ideogram_raw)
            _,         kling_clean    = strip_shot_type(kling_raw)

            # CONTINUE clips inherit their start frame from the previous clip's
            # final video frame and carry no Ideogram still — the model writes
            # "NONE, continues from Clip X.Y final frame." Normalise that to empty
            # so the UI shows no Ideogram block for those clips.
            if re.match(r'\s*NONE\b', ideogram_clean, re.IGNORECASE):
                ideogram_clean = ''

            ref_mode = (get_field(clip_body, 'REFERENCE MODE') or '').upper()
            ref_mode = 'CONTINUE' if 'CONTINUE' in ref_mode else ('RE-ESTABLISH' if 'ESTABLISH' in ref_mode else '')

            phase['clips'].append({
                'number':    clip_num,
                'title':     get_field(clip_body, 'TITLE'),
                'duration':  get_field(clip_body, 'DURATION'),
                'shot_type': shot_type,
                'reference_mode': ref_mode,
                'start_frame':    get_field(clip_body, 'START FRAME'),
                'change':         (get_field(clip_body, 'CHANGE') or '').strip().lower(),
                'foreground': get_section(clip_body, 'FOREGROUND'),
                'ideogram':  ideogram_clean,
                'kling':     kling_clean,
                'user_check': get_section(clip_body, 'USER CHECK'),
                'note':      get_section(clip_body, 'NOTE'),
                'voiceover': {
                    'line':      vo_line.group(1).strip()  if vo_line  else clip_num,
                    'speed':     vo_speed.group(1).strip() if vo_speed else '1.0',
                    'stability': vo_stab.group(1).strip()  if vo_stab  else '72',
                    'text':      (vo_text.group(1).strip() or 'SILENCE') if vo_text else vo_block,
                }
            })

        phases.append(phase)
    return phases


@app.route("/api/run-scene-creator", methods=["POST"])
def run_scene_creator():
    data   = request.get_json()
    job_id = data.get('job_id')
    raw, err = _run_agent(
        "agent6scenecreator.py",
        {'storyboard': data.get('storyboard', ''), 'continuity': data.get('continuity', {})},
        "Scene Creator",
        timeout=240, job_id=job_id
    )
    if err:
        return _agent_error_response(err)
    phases = _parse_scenes(raw)
    print(f"[SCENE CREATOR] Parsed {len(phases)} phases, {sum(len(p['clips']) for p in phases)} clips.")
    return jsonify({"success": True, "phases": phases, "raw": raw})


@app.route("/api/run-scene-reviewer", methods=["POST"])
def run_scene_reviewer():
    """Second pass over the Scene Creator output: a global audit that fixes
    cross-clip inconsistencies, removes admin/instrument clutter, adds missing
    process shots, and stamps a USER CHECK line onto every clip. Returns the
    corrected breakdown in the same shape as run_scene_creator."""
    data   = request.get_json()
    job_id = data.get('job_id')
    scenes = data.get('scenes', '')
    if not scenes.strip():
        return jsonify({"success": False, "error": "No scene breakdown supplied to review."}), 400
    raw, err = _run_agent(
        "agent8scenereviewer.py",
        {'recipe': data.get('recipe', ''), 'continuity': data.get('continuity', {}), 'scenes': scenes},
        "Scene Reviewer",
        timeout=300, job_id=job_id
    )
    if err:
        return _agent_error_response(err)
    phases = _parse_scenes(raw)
    print(f"[SCENE REVIEWER] Parsed {len(phases)} phases, {sum(len(p['clips']) for p in phases)} clips.")
    return jsonify({"success": True, "phases": phases, "raw": raw})


@app.route("/api/cancel-job/<job_id>", methods=["POST"])
def cancel_job(job_id):
    with _jobs_lock:
        proc = _active_jobs.pop(job_id, None)
        _cancelled_jobs.add(job_id)   # so _run_agent reports "cancelled", not "crashed"
    if proc:
        try:
            proc.kill()
        except Exception:
            pass
        return jsonify({"cancelled": True})
    return jsonify({"cancelled": False})


@app.route("/api/job-status/<job_id>", methods=["GET"])
def job_status(job_id):
    """Live progress for a running agent, polled by the dashboard timeline.
    Returns the ordered list of @@PROGRESS@@ events plus done/error state."""
    with _progress_lock:
        st = _job_progress.get(job_id)
        if st is None:
            return jsonify({"found": False, "events": [], "done": False, "error": None})
        return jsonify({
            "found":  True,
            "events": list(st["events"]),
            "done":   st["done"],
            "error":  st["error"],
        })


# -----------------------------------------------------------------
# VIDEO RATINGS & STYLE TRACKING
# -----------------------------------------------------------------

def _ensure_video_columns():
    """Add style and rating columns to videos table if they don't exist."""
    db_path = Path(__file__).resolve().parents[2] / "data" / "pov_cocktail.db"
    with sqlite3.connect(str(db_path)) as conn:
        for col, col_type in [("style", "TEXT"), ("rating", "INTEGER")]:
            try:
                conn.execute(f"ALTER TABLE videos ADD COLUMN {col} {col_type}")
                conn.commit()
            except sqlite3.OperationalError:
                pass  # Column already exists


@app.route("/api/rate-video/<int:protocol_id>", methods=["POST"])
def rate_video(protocol_id):
    data   = request.get_json() or {}
    rating = data.get("rating")
    if rating is None:
        return jsonify({"success": False, "error": "rating required"}), 400
    rating = int(rating)
    if not 1 <= rating <= 10:
        return jsonify({"success": False, "error": "rating must be 1-10"}), 400
    db_path = Path(__file__).resolve().parents[2] / "data" / "pov_cocktail.db"
    with sqlite3.connect(str(db_path)) as conn:
        conn.execute("UPDATE videos SET rating = ? WHERE protocol_id = ?", (rating, protocol_id))
        conn.commit()
    return jsonify({"success": True})


@app.route("/api/video-stats", methods=["GET"])
def video_stats():
    db_path = Path(__file__).resolve().parents[2] / "data" / "pov_cocktail.db"
    with sqlite3.connect(str(db_path)) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT style, AVG(rating) as avg_rating, COUNT(*) as cnt
            FROM videos
            WHERE style IS NOT NULL AND rating IS NOT NULL
            GROUP BY style
        """)
        rows = cursor.fetchall()
    return jsonify({r[0]: {"avg": round(r[1], 1), "count": r[2]} for r in rows})


# -----------------------------------------------------------------
# PROTOCOL EXPORT
# -----------------------------------------------------------------

def _build_protocol_md(session):
    """Build the protocol .md content and a filesystem-safe title for a session."""
    idea  = session.get("idea", {})
    title = idea.get("title", "Untitled Protocol")

    lines = [
        f"# {title}",
        f"**Cocktail:** {idea.get('cocktail', 'N/A')}",
        f"**Style:** {session.get('style', 'N/A')}",
        f"**Generated:** {session.get('created_at', 'Unknown')}",
        "",
        "---",
        "",
        "## Concept",
        idea.get("idea_text", idea.get("summary", "")),
        "",
    ]

    if session.get("science_output"):
        lines += ["---", "", "## Science Brief", session["science_output"], ""]

    if session.get("recipe_output"):
        lines += ["---", "", "## Recipe Brief", session["recipe_output"], ""]

    if session.get("continuity_output"):
        cont = session["continuity_output"]
        cont_str = json.dumps(cont, indent=2, ensure_ascii=False) if isinstance(cont, dict) else str(cont)
        lines += ["---", "", "## Continuity Brief", "```json", cont_str, "```", ""]

    if session.get("storyboard_output"):
        lines += ["---", "", "## Director Storyboard", session["storyboard_output"], ""]

    if session.get("upload_output"):
        lines += ["---", "", "## Upload Pack", session["upload_output"], ""]

    if session.get("scenes_output"):
        lines += ["---", "", "## Scene Breakdown"]
        for phase in session["scenes_output"]:
            lines.append(f"\n### Phase {phase.get('number')} — {phase.get('name','')}")
            meta = " · ".join(filter(None, [phase.get("timecode"), phase.get("clips_count","") + " clips", phase.get("duration","") + "s"]))
            if meta:
                lines.append(f"*{meta}*")
            for clip in phase.get("clips", []):
                lines.append(f"\n**Clip {clip.get('number')} — {clip.get('title','')}**")
                mode = clip.get("reference_mode")
                start = clip.get("start_frame")
                if mode or start:
                    label = " · ".join(filter(None, [mode, start]))
                    lines.append(f"\n▶ Start frame: {label}")
                if clip.get("user_check"):
                    lines.append(f"\n✅ Should look like: {clip['user_check']}")
                if clip.get("ideogram"):
                    lines.append(f"\n*IDEOGRAM:*\n> {clip['ideogram']}")
                if clip.get("kling"):
                    lines.append(f"\n*KLING:*\n> {clip['kling']}")
                vo = clip.get("voiceover", {})
                if vo.get("text"):
                    spd  = vo.get("speed", "1.0")
                    stab = vo.get("stability", "72")
                    lines.append(f"\n*VOICEOVER [speed {spd} · stability {stab}]:*\n> \"{vo['text']}\"")

    content = "\n".join(lines)
    safe_title = re.sub(r'[^\w\s-]', '', title).strip().replace(' ', '_')[:40]
    return content, safe_title


def _save_protocol_md(session, session_id):
    """Write the protocol .md into protocols/<id>-<title>/protocol.md. Returns (content, safe_title, out_dir)."""
    content, safe_title = _build_protocol_md(session)
    protocols_dir = Path(__file__).resolve().parents[2] / "protocols"
    protocols_dir.mkdir(exist_ok=True)
    out_dir = protocols_dir / f"{session_id}-{safe_title}"
    out_dir.mkdir(exist_ok=True)
    (out_dir / "protocol.md").write_text(content, encoding='utf-8')
    return content, safe_title, out_dir


@app.route("/api/export-protocol", methods=["POST"])
def export_protocol():
    data       = request.get_json() or {}
    session_id = data.get("session_id")
    session = next((s for s in _load_sessions() if s["id"] == session_id), None)
    if not session:
        return jsonify({"success": False, "error": "Session not found"}), 404

    content, safe_title, _ = _save_protocol_md(session, session_id)
    return Response(
        content,
        mimetype="text/markdown",
        headers={"Content-Disposition": f'attachment; filename="{safe_title}_protocol.md"'},
    )


@app.route("/api/save-protocol", methods=["POST"])
def save_protocol():
    """Save the protocol .md to the protocols folder without downloading, then
    remove the session from the unfinished list so it stops showing under
    'Continue Existing Unfinished Protocol'. The saved .md is the permanent archive."""
    data       = request.get_json() or {}
    session_id = data.get("session_id")
    sessions = _load_sessions()
    session = next((s for s in sessions if s["id"] == session_id), None)
    if not session:
        return jsonify({"success": False, "error": "Session not found"}), 404

    content, safe_title, out_dir = _save_protocol_md(session, session_id)

    # Also log it to the videos archive so it shows up in View Database, using the
    # data already in the session — no manual form entry needed. Notes and rating
    # are left blank: they are post-publish performance fields, added later via the
    # ADD NOTES button and the star rating in View Database.
    idea  = session.get("idea", {})
    title = idea.get("title", "Untitled Protocol")
    logged_id = None
    try:
        already = any((v.get("title") or "").strip() == title.strip() for v in (get_all_videos() or []))
        if not already:
            logged_id = int(get_next_protocol_id())
            created = (session.get("created_at") or "")[:10] or time.strftime("%Y-%m-%d")
            add_video(
                protocol_id  = logged_id,
                cocktail     = idea.get("cocktail", ""),
                title        = title,
                date_created = created,
                notes        = "",
                style        = session.get("style"),
            )
    except Exception as e:
        # The .md is already saved; surface the logging failure but don't lose the file.
        return jsonify({"success": False, "error": f"Saved the .md but could not log to the database: {e}"}), 500

    # Remove from the unfinished sessions list (it is now archived as a .md).
    remaining = [s for s in sessions if s["id"] != session_id]
    _write_sessions(remaining)

    return jsonify({
        "success": True,
        "folder": f"{session_id}-{safe_title}",
        "title": title,
        "protocol_id": logged_id,
    })


@app.route("/api/protocol-md", methods=["GET"])
def protocol_md():
    """Return the saved protocol .md for an archived idea, matched by title.
    Used by the View Database archive viewer. Returns {found, content}."""
    title = (request.args.get("title") or "").strip()
    if not title:
        return jsonify({"found": False})
    safe_title = re.sub(r'[^\w\s-]', '', title).strip().replace(' ', '_')[:40]
    protocols_dir = Path(__file__).resolve().parents[2] / "protocols"
    if not protocols_dir.exists():
        return jsonify({"found": False})
    # Folder names are "<session_id>-<safe_title>"; match the safe_title suffix.
    for d in sorted(protocols_dir.iterdir(), reverse=True):
        if d.is_dir() and d.name.endswith(f"-{safe_title}"):
            md = d / "protocol.md"
            if md.exists():
                return jsonify({"found": True, "content": md.read_text(encoding='utf-8')})
    return jsonify({"found": False})


# -----------------------------------------------------------------
# SESSION STATE (multi-session)
# -----------------------------------------------------------------

SESSIONS_PATH = Path(__file__).resolve().parents[2] / "data" / "sessions.json"


def _load_sessions():
    if not SESSIONS_PATH.exists():
        return []
    try:
        return json.loads(SESSIONS_PATH.read_text(encoding='utf-8'))
    except Exception:
        return []


def _write_sessions(sessions):
    SESSIONS_PATH.write_text(json.dumps(sessions, ensure_ascii=False, indent=2), encoding='utf-8')


@app.route("/api/sessions", methods=["GET"])
def list_sessions():
    sessions = _load_sessions()
    # Return summary only (no heavy director_output blob)
    summary = [
        {
            "id":         s["id"],
            "title":      s.get("idea", {}).get("title", "Untitled"),
            "cocktail":   s.get("idea", {}).get("cocktail", ""),
            "stage":      s.get("stage", ""),
            "updated_at": s.get("updated_at", ""),
        }
        for s in sessions
    ]
    return jsonify(summary)


@app.route("/api/session/save", methods=["POST"])
def save_session():
    import time as _time
    data = request.get_json()
    session_id = data.get("session_id")
    sessions = _load_sessions()

    now = _time.strftime("%Y-%m-%dT%H:%M:%S")

    pipeline_fields = ["science_output", "recipe_output", "continuity_output", "storyboard_output", "scenes_output", "upload_output"]

    if session_id:
        for s in sessions:
            if s["id"] == session_id:
                s["stage"]    = data.get("stage", s["stage"])
                s["idea"]     = data.get("idea", s["idea"])
                if data.get("style"):
                    s["style"] = data["style"]
                for f in pipeline_fields:
                    if data.get(f) is not None:
                        s[f] = data[f]
                s["updated_at"] = now
                _write_sessions(sessions)
                return jsonify({"success": True, "session_id": session_id})

    # New session
    new_id = str(int(_time.time() * 1000))
    new_session = {
        "id":         new_id,
        "stage":      data.get("stage", "idea_selected"),
        "idea":       data.get("idea", {}),
        "style":      data.get("style"),
        "created_at": now,
        "updated_at": now,
    }
    for f in pipeline_fields:
        new_session[f] = data.get(f)
    sessions.append(new_session)
    _write_sessions(sessions)
    return jsonify({"success": True, "session_id": new_id})


@app.route("/api/session/<session_id>", methods=["GET"])
def load_session(session_id):
    for s in _load_sessions():
        if s["id"] == session_id:
            return jsonify({"exists": True, **s})
    return jsonify({"exists": False}), 404


@app.route("/api/session/<session_id>", methods=["DELETE"])
def delete_session(session_id):
    sessions = _load_sessions()
    sessions = [s for s in sessions if s["id"] != session_id]
    _write_sessions(sessions)
    return jsonify({"success": True})


@app.route("/api/run-upload-packager", methods=["POST"])
def run_upload_packager():
    data    = request.get_json()
    job_id  = data.get('job_id')
    previous_videos = get_all_videos()
    raw, err = _run_agent(
        "agent7uploadpackager.py",
        {
            'title':           data.get('title', ''),
            'cocktail':        data.get('cocktail', ''),
            'idea_text':       data.get('idea_text', ''),
            'science':         data.get('science', ''),
            'recipe':          data.get('recipe', ''),
            'storyboard':      data.get('storyboard', ''),
            'previous_videos': previous_videos,
        },
        "Upload Packager", timeout=180, job_id=job_id
    )
    if err:
        return _agent_error_response(err)
    return jsonify({"success": True, "raw": raw})


# -----------------------------------------------------------------
# EXECUTION INIT
# -----------------------------------------------------------------

if __name__ == "__main__":
    _ensure_video_columns()
    print("\n========================================")
    print("  POV Cocktail Video Generator — Content Dashboard v0.5")
    print("  Server active at http://localhost:5000")
    print("  Press Ctrl+C to terminate runtime session")
    print("========================================\n")
    # threaded=True lets /api/job-status be polled *while* an agent request is
    # still in flight (the dev server is single-threaded by default).
    app.run(debug=True, port=5000, threaded=True)