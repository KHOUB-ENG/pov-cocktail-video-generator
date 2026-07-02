"""Tiny progress emitter for agent subprocesses.

Agents print `@@PROGRESS@@ <json>` lines to **stderr**; the orchestrator's
`_run_agent` parses them live and exposes them via `/api/job-status/<job_id>`,
so the dashboard timeline can show *real* progress (DB load, each Gemini retry,
rate-limit waits, success) instead of fake timers.

stdout is reserved for the agent's actual result — never write progress there.
"""
import sys
import json
import time


def emit(stage, status="active", note="", **extra):
    """Emit one progress event.

    stage  — short machine key the UI maps to a timeline step
             (e.g. "context", "prompt", "gemini", "parsing").
    status — "active" | "done" | "retry" | "error".
    note   — human-readable line shown under the step.
    extra  — any extra fields (e.g. attempt=2, max=3, wait=15).
    """
    payload = {"stage": stage, "status": status, "note": note, "t": round(time.time(), 3)}
    if extra:
        payload.update(extra)
    try:
        sys.stderr.write("@@PROGRESS@@ " + json.dumps(payload) + "\n")
        sys.stderr.flush()
    except Exception:
        # Progress reporting must never break the agent itself.
        pass


def call_gemini(client, model, prompt, label, stage="gemini", config=None):
    """Run a Gemini text generation with up to 3 retries, emitting a live
    progress event for every attempt / retry / success.

    Same backoff as the agents' original loops (10s, 15s, 20s). Returns
    response.text, or raises (so the orchestrator reports a real failure type).

    If no `config` is supplied, the per-agent temperature is looked up from
    config.geminiAPIsettings.AGENT_TEMPERATURES using `label` — so generation
    behaviour is tuned entirely from that one config file.
    """
    if config is None:
        from config.geminiAPIsettings import config_for
        config = config_for(label)

    last_err = None
    for attempt in range(3):
        try:
            emit(stage, "active",
                 f"Contacting Gemini ({model}) — attempt {attempt + 1} of 3…",
                 attempt=attempt + 1, max=3)
            if config is not None:
                response = client.models.generate_content(
                    model=model, contents=prompt, config=config)
            else:
                response = client.models.generate_content(model=model, contents=prompt)
            emit(stage, "done", f"{label}: Gemini responded on attempt {attempt + 1}.")
            return response.text
        except Exception as e:
            last_err = e
            es = str(e)
            if "429" in es or "RESOURCE_EXHAUSTED" in es:
                wait = 10 + attempt * 5
                emit(stage, "retry",
                     f"Rate limited (429). Waiting {wait}s then retrying…",
                     attempt=attempt + 1, max=3, wait=wait, reason="rate_limit")
                time.sleep(wait)
            elif "503" in es or "UNAVAILABLE" in es:
                wait = 10 + attempt * 5
                emit(stage, "retry",
                     f"Gemini overloaded (503). Waiting {wait}s then retrying…",
                     attempt=attempt + 1, max=3, wait=wait, reason="overloaded")
                time.sleep(wait)
            else:
                emit(stage, "error", f"Unexpected Gemini error: {e}", reason="unexpected")
                raise
    emit(stage, "error", f"{label}: Gemini did not respond after 3 attempts.",
         reason="exhausted")
    raise RuntimeError(f"{label}: Gemini API unreachable after 3 attempts. "
                       f"Last error: {last_err}")
