"""Rejoin web app.  Run:  python app.py  then open http://127.0.0.1:5000"""
from __future__ import annotations

import json
import os
from pathlib import Path

from flask import Flask, Response, jsonify, render_template, request

try:
    from dotenv import load_dotenv  # optional
    load_dotenv()
except ImportError:
    pass

from engine import SINCE_OPTIONS, analyze, llm
from engine.ics import build_ics
from engine.voice import read_upload

ROOT = Path(__file__).parent
DEMO = ROOT / "demo"
MAX_UPLOAD_MB = 40

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_MB * 1024 * 1024


def _names(raw: str) -> list[str]:
    return [n.strip() for n in (raw or "").replace(";", ",").split(",") if n.strip()]


@app.get("/")
def index():
    return render_template("index.html", since_options=SINCE_OPTIONS, ai_available=llm.available(), static_site=False)


@app.get("/api/health")
def health():
    return jsonify(ok=True, ai_available=llm.available(), model=llm.MODEL)


@app.post("/api/analyze")
def api_analyze():
    me = _names(request.form.get("me", ""))
    since = request.form.get("since", "last_spoke")
    engine = request.form.get("engine", "auto")
    up = request.files.get("chat")
    if not up or not up.filename:
        return jsonify(error="Choose your exported chat file (.txt or .zip) first."), 400
    try:
        chat_text, audio = read_upload(up.filename, up.read())
        result = analyze(chat_text, me, since, engine, audio=audio)
    except ValueError as exc:
        return jsonify(error=str(exc)), 422
    return jsonify(result)


@app.post("/api/demo")
def api_demo():
    body = request.get_json(silent=True) or {}
    engine = body.get("engine", "auto")
    chat = (DEMO / "aina_fyp_chat.txt").read_text(encoding="utf-8")
    transcripts = json.loads((DEMO / "voice_transcripts.json").read_text(encoding="utf-8"))
    result = analyze(chat, ["Aina", "Ain"], body.get("since", "last_spoke"), engine, demo_transcripts=transcripts)
    result["demo"] = True
    return jsonify(result)


@app.get("/demo/chat.txt")
def demo_file():
    return Response((DEMO / "aina_fyp_chat.txt").read_text(encoding="utf-8"), mimetype="text/plain",
                    headers={"Content-Disposition": "attachment; filename=WhatsApp Chat with FYP Group 7.txt"})


@app.post("/api/ics")
def api_ics():
    body = request.get_json(silent=True) or {}
    deadlines = [d for d in body.get("deadlines", []) if isinstance(d, dict) and d.get("iso") and d.get("what")]
    if not deadlines:
        return jsonify(error="No dates to export."), 400
    return Response(build_ics(deadlines), mimetype="text/calendar",
                    headers={"Content-Disposition": "attachment; filename=rejoin-dates.ics"})


@app.errorhandler(413)
def too_big(_):
    return jsonify(error=f"That file is over {MAX_UPLOAD_MB} MB. Export the chat again without media, or with fewer days."), 413


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="127.0.0.1" if port == 5000 else "0.0.0.0", port=port, debug=False)
