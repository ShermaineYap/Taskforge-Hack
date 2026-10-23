"""Turn an exported chat into a personal handoff."""
from __future__ import annotations

import time as _time
from datetime import datetime, timedelta

from . import llm, rules
from .parser import Message, parse_chat, participants
from .plain import reading_seconds, word_count
from .redact import redact_messages
from .voice import attach_transcripts

SINCE_OPTIONS = {
    "last_spoke": "Since I last sent a message",
    "24h": "Last 24 hours",
    "3d": "Last 3 days",
    "7d": "Last 7 days",
    "all": "The whole chat",
}
CONTEXT_SIZE = 40


def _is_me(sender: str | None, me: list[str]) -> bool:
    if not sender:
        return False
    s = sender.lower().strip()
    lows = {n.lower() for n in me}
    return s in lows or s.split()[0] in lows


def select_window(messages: list[Message], me: list[str], since: str):
    if not messages:
        return [], [], None
    end = messages[-1].timestamp
    start_idx = 0
    cutoff_label = None
    if since == "last_spoke":
        mine = [i for i, m in enumerate(messages) if _is_me(m.sender, me)]
        if mine:
            start_idx = mine[-1] + 1
            cutoff_label = messages[mine[-1]].timestamp
        else:
            since = "3d"
    if since in ("24h", "3d", "7d"):
        delta = {"24h": timedelta(hours=24), "3d": timedelta(days=3), "7d": timedelta(days=7)}[since]
        cutoff = end - delta
        start_idx = next((i for i, m in enumerate(messages) if m.timestamp > cutoff), len(messages))
        cutoff_label = cutoff
    window = messages[start_idx:]
    context = messages[max(0, start_idx - CONTEXT_SIZE):start_idx]
    return window, context, cutoff_label


def _stats(window: list[Message], result: dict) -> dict:
    content_msgs = [m for m in window if not m.is_system]
    in_words = sum(word_count(m.content) for m in content_msgs)
    out_text = []
    for key in ("asked_of_you", "decisions", "open_questions"):
        for it in result[key]:
            out_text.append(it["text"])
    out_text += [d["what"] + " " + d["when_human"] for d in result["deadlines"]]
    out_words = sum(word_count(t) for t in out_text)
    items = sum(len(result[k]) for k in ("asked_of_you", "decisions", "open_questions"))
    return {
        "messages": len(content_msgs),
        "voice_notes": sum(1 for m in content_msgs if m.is_voice_note),
        "media": sum(1 for m in content_msgs if m.is_media and not m.is_voice_note),
        "senders": len({m.sender for m in content_msgs}),
        "words_in": in_words,
        "read_seconds_in": reading_seconds(in_words),
        "items_out": items,
        "for_you": len(result["asked_of_you"]) + len(result["open_questions"]),
        "words_out": out_words,
        "read_seconds_out": reading_seconds(out_words),
        "reduction_pct": round(100 * (1 - out_words / in_words)) if in_words else 0,
    }


def analyze(
    raw_text: str,
    me: list[str],
    since: str = "last_spoke",
    engine: str = "auto",
    audio: dict | None = None,
    demo_transcripts: dict | None = None,
) -> dict:
    t0 = _time.perf_counter()
    me = [n.strip() for n in me if n and n.strip()]
    if not me:
        raise ValueError("Tell Rejoin your name as it appears in the chat.")
    messages = parse_chat(raw_text)
    if not messages:
        raise ValueError("That doesn't look like a WhatsApp chat export. In WhatsApp: open the group, tap ⋮ / the group name, then Export chat.")

    voice_report = attach_transcripts(messages, audio or {}, demo_transcripts)
    privacy = redact_messages(messages)
    window, context, cutoff = select_window(messages, me, since)
    if not window:
        raise ValueError("Nothing new since your last message. You're already caught up.")

    warnings: list[str] = []
    engine_used = "rules"
    llm_report = {}
    want_ai = engine in ("auto", "ai")
    if want_ai and llm.available():
        try:
            result, llm_report = llm.extract(window, me, context)
            engine_used = "ai"
        except Exception as exc:  # network, quota, malformed JSON
            warnings.append(f"AI engine unavailable ({type(exc).__name__}); used the offline engine instead.")
            result = rules.extract(window, me, context)
    else:
        if engine == "ai":
            warnings.append("No GROQ_API_KEY set; used the offline engine.")
        result = rules.extract(window, me, context)
    for a in result["asked_of_you"]:
        a.setdefault("inferred", False)

    names_seen = participants(messages)
    if not any(_is_me(n, me) for n in names_seen):
        warnings.append(
            "Your name doesn't appear as a sender in this chat. Check the spelling exactly as WhatsApp shows it."
        )

    return {
        "me": me,
        "since": since,
        "since_label": SINCE_OPTIONS.get(since, since),
        "cutoff": cutoff.isoformat(timespec="minutes") if cutoff else None,
        "chat_end": messages[-1].timestamp.isoformat(timespec="minutes"),
        "engine": engine_used,
        "model": llm.MODEL if engine_used == "ai" else "Rejoin rules v1",
        "warnings": warnings,
        "result": result,
        "stats": _stats(window, result),
        "privacy": privacy,
        "voice": voice_report,
        "validation": llm_report,
        "participants": names_seen,
        "messages": [m.to_dict() for m in window],
        "elapsed_ms": round((_time.perf_counter() - t0) * 1000),
    }
