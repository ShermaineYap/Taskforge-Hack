"""AI handoff extractor (Groq, OpenAI-compatible API).

The model only proposes items. Rejoin then checks every item:
  * each item must cite message ids that exist inside the catch-up window,
  * dates are re-resolved deterministically from the cited message's timestamp
    (models are unreliable at "what date is next Thursday"),
  * asks that cite a message not mentioning you are flagged "inferred".
Anything that fails validation is dropped, never shown.
"""
from __future__ import annotations

import json
import os
import re


from .dates import find_dates
from .parser import Message
from .plain import plainify

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
MODEL = os.environ.get("REJOIN_MODEL", "llama-3.3-70b-versatile")
MAX_WINDOW = 600

SYSTEM = """You help a person who missed part of a busy group chat get back in.
You receive the chat as numbered lines: [id] (time) Sender: text.
Lines marked CONTEXT happened before the person left; use them only to understand, never report them.
Return ONLY JSON with this shape:
{
 "asked_of_you": [{"text": str, "plain": str, "from": str, "when_text": str|null, "sources": [int]}],
 "decisions": [{"text": str, "plain": str, "from": str, "sources": [int]}],
 "open_questions": [{"text": str, "plain": str, "from": str, "sources": [int]}],
 "deadlines": [{"what": str, "when_text": str, "sources": [int]}],
 "draft_reply": str
}
Rules:
- "asked_of_you": things someone asked or assigned to THE PERSON (by name, nickname, @mention, or a task list naming them, or a reply clearly aimed at them). Not tasks for other people.
- "decisions": what the group settled or changed that affects the person's work (formats, dates, scope, roles, venues). Skip trivia.
- "open_questions": questions the person still needs to answer, including group-wide "everyone confirm" requests.
- "deadlines": every concrete date/time that matters; copy the date words exactly as written in the chat into when_text.
- "text": one short instruction-style sentence, max 18 words, in English, addressed to the person ("Write the literature review section...").
- "plain": the same meaning in very plain language: max 12 words, common words, no idioms, no abbreviations.
- "sources": ids of the lines that support the item. Every item needs at least one.
- "draft_reply": a short, friendly message (max 60 words) the person could send to rejoin the chat, acknowledging their tasks. Match the chat's language and tone.
- If nothing fits a list, return an empty list. Never invent facts that are not in the lines.
"""


def available() -> bool:
    return bool(os.environ.get("GROQ_API_KEY"))


def _format_lines(window: list[Message], context: list[Message]) -> str:
    out = []
    for m in context:
        if m.is_system:
            continue
        out.append(f"CONTEXT [{m.id}] ({m.timestamp:%a %d %b %H:%M}) {m.sender}: {_line(m)}")
    for m in window:
        if m.is_system:
            continue
        out.append(f"[{m.id}] ({m.timestamp:%a %d %b %H:%M}) {m.sender}: {_line(m)}")
    return "\n".join(out)


def _line(m: Message) -> str:
    if m.is_voice_note and m.transcript:
        return f"(voice note) {m.transcript}"
    if m.is_voice_note:
        return "(voice note, not transcribed)"
    if m.is_media and not m.text.strip("<> "):
        return "(media)"
    return m.content.replace("\n", " / ")


def call_groq(window: list[Message], context: list[Message], me: list[str], timeout: int = 45) -> dict:
    key = os.environ["GROQ_API_KEY"]
    user = (
        f"The person is called: {', '.join(me)}.\n"
        f"Today in the chat is {window[-1].timestamp:%A %d %B %Y}.\n\n"
        + _format_lines(window[-MAX_WINDOW:], context)
    )
    import requests  # imported lazily so the engine also runs in the browser (Pyodide)

    resp = requests.post(
        GROQ_URL,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        json={
            "model": MODEL,
            "temperature": 0.1,
            "response_format": {"type": "json_object"},
            "messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}],
        },
        timeout=timeout,
    )
    resp.raise_for_status()
    content = resp.json()["choices"][0]["message"]["content"]
    return json.loads(content)


def validate(raw: dict, window: list[Message], me: list[str]) -> tuple[dict, dict]:
    """Keep only grounded items. Returns (clean_result, report)."""
    by_id = {m.id: m for m in window}
    me_re = re.compile(r"(?<![\w])@?(" + "|".join(re.escape(n) for n in me if n) + r")(?![\w])", re.I)
    dropped = 0

    def good_sources(item) -> list[int]:
        ids = []
        for s in item.get("sources") or []:
            try:
                s = int(s)
            except (TypeError, ValueError):
                continue
            if s in by_id and s not in ids:
                ids.append(s)
        return ids

    def clean_list(key, fields):
        nonlocal dropped
        out = []
        items = raw.get(key)
        for item in items if isinstance(items, list) else []:
            if not isinstance(item, dict):
                dropped += 1
                continue
            srcs = good_sources(item)
            text = str(item.get(fields[0]) or "").strip()
            if not srcs or not text:
                dropped += 1
                continue
            clean = {f: (str(item.get(f)).strip() if item.get(f) is not None else None) for f in fields}
            clean["sources"] = srcs
            out.append(clean)
        return out

    asks = clean_list("asked_of_you", ["text", "plain", "from", "when_text"])
    for a in asks:
        src = by_id[a["sources"][0]]
        a["inferred"] = not any(me_re.search(by_id[s].content or "") for s in a["sources"])
        a["deadline"] = _resolve(a.pop("when_text"), src)
        a["plain"] = a["plain"] or plainify(a["text"])
    decisions = clean_list("decisions", ["text", "plain", "from"])
    questions = clean_list("open_questions", ["text", "plain", "from"])
    for lst in (decisions, questions):
        for it in lst:
            it["plain"] = it["plain"] or plainify(it["text"])

    deadlines = []
    for d in clean_list("deadlines", ["what", "when_text"]):
        r = _resolve(d["when_text"], by_id[d["sources"][0]])
        if not r:
            dropped += 1
            continue
        deadlines.append({"what": d["what"], "when_human": r["human"], "iso": r["iso"], "sources": d["sources"]})
    deadlines.sort(key=lambda x: x["iso"])

    result = {
        "asked_of_you": asks,
        "decisions": decisions,
        "open_questions": questions,
        "deadlines": deadlines,
        "draft_reply": str(raw.get("draft_reply") or "").strip(),
    }
    return result, {"dropped_ungrounded": dropped}


def _resolve(when_text, msg: Message):
    if not when_text:
        return None
    found = find_dates(str(when_text), msg.timestamp)
    if not found:
        # Fall back to the dates written in the source message itself.
        found = find_dates(msg.content, msg.timestamp)
    if not found:
        return None
    f = found[0]
    return {"text": str(when_text), "iso": f.iso(), "human": f.human()}


def extract(window: list[Message], me: list[str], context: list[Message]) -> tuple[dict, dict]:
    raw = call_groq(window, context, me)
    return validate(raw, window, me)
