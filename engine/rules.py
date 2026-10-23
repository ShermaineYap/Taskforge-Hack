"""Deterministic, offline handoff extractor.

Works with no API key and no network. It is deliberately conservative:
every item it emits points at the exact message(s) it came from.
"""
from __future__ import annotations

import re
from typing import Iterable

from .dates import find_dates
from .parser import Message
from .plain import plainify, strip_noise

REQUEST = re.compile(
    r"\b(can you|could you|can u|could u|would you|will you|pls|please|plz|tolong|boleh tak|"
    r"need you|needs? (?:you|u) to|you (?:do|handle|take|settle|book|send|write|check|update|cover|prepare|bring|finish)|"
    r"(?:your|ur) (?:part|section|job|task)|assign(?:ed)? to|in charge of|help (?:me|us) (?:with)?|"
    r"don'?t forget|remember to|make sure)\b",
    re.I,
)
GROUP_CONFIRM = re.compile(
    r"\b(everyone|everybody|all of you|guys|ppl|people|korang|semua|team)\b.*"
    r"\b(confirm|reply|vote|let me know|lmk|react|thumbs|👍|can make it|available|free|ok with)\b",
    re.I,
)
DECISION = re.compile(
    r"\b(decided|decision|final(?:ly|ised|ized)?\b|confirmed|agreed|settled|"
    r"we(?:'ll|'re| will| are| r)? (?:go(?:ing)? with|use|using|switch(?:ing)? (?:to|from))|switch(?:ing|ed)? (?:from|to)|let'?s go with|going with|"
    r"changed? to|moved? to|postponed|resched\w*|instead of|no longer|not \w+ anymore|"
    r"(?:supervisor|lecturer|dr\.? ?\w+|prof\.? ?\w+|sir|miss|madam) (?:said|says|confirmed|wants|replied))\b",
    re.I,
)
TASK_LINE = re.compile(r"^\s*[-•*\d.)]*\s*(?P<who>[A-Za-z][\w ]{0,20}?)\s*(?:-|–|:|→|=>|=)\s*(?P<task>.{3,})$")
NOISE = re.compile(r"^(ok+|okay|k+|noted|lol+|haha\w*|hehe\w*|thanks?|tq|ty|sure|yes|ya+|yup|nice|👍+|🙏+|😂+)[.!\s]*$", re.I)


def _names_regex(names: Iterable[str]) -> re.Pattern:
    alts = sorted({n.strip() for n in names if n and n.strip()}, key=len, reverse=True)
    return re.compile(r"(?<![\w])@?(" + "|".join(re.escape(a) for a in alts) + r")(?![\w])", re.I)


def _deadline_for(msg: Message):
    ds = find_dates(msg.content, msg.timestamp)
    return ds[0] if ds else None


def _snippet(text: str, limit: int = 140) -> str:
    t = strip_noise(text).replace("\n", " ")
    return t if len(t) <= limit else t[: limit - 1].rsplit(" ", 1)[0] + "…"


def _focus(text: str, me_re: re.Pattern) -> str:
    """Keep the sentence(s) that carry the request; drop greetings and fillers."""
    sentences = re.split(r"(?<=[.?!])\s+", strip_noise(text).replace("\n", " "))
    keep = [s for s in sentences if me_re.search(s) or REQUEST.search(s)]
    out = " ".join(keep) if keep else " ".join(sentences)
    out = re.sub(r"^@?\w+[,:]?\s+(?=(?:can|could|would|will|pls|please|also|are|do)\b)", "", out, flags=re.I)
    out = re.sub(r"^@\S+\s*", "", out)
    out = out.strip()
    return out[:1].upper() + out[1:] if out else out


def _deadline_dict(d):
    if not d:
        return None
    return {"text": d.text, "iso": d.iso(), "human": d.human()}


def extract(window: list[Message], me: list[str], context: list[Message] | None = None) -> dict:
    me_re = _names_regex(me)
    me_lower = {n.lower() for n in me}

    asks, decisions, questions, deadlines = [], [], [], []
    used_for_ask: set[int] = set()

    def is_me(sender: str | None) -> bool:
        if not sender:
            return False
        s = sender.lower()
        return s in me_lower or s.split()[0] in me_lower

    for msg in window:
        if msg.is_system or is_me(msg.sender):
            continue
        content = msg.content
        if not content or NOISE.match(content.strip()):
            continue
        addressed = bool(me_re.search(content))

        # 1. Task-allocation lists: "Aina - lit review"
        if "\n" in content or content.count(" - ") >= 2:
            for line in re.split(r"\n|;\s*", content):
                tm = TASK_LINE.match(line)
                if tm and me_re.fullmatch(tm.group("who").strip()):
                    d = find_dates(line, msg.timestamp) or find_dates(content, msg.timestamp)
                    task = tm.group("task").strip()
                    asks.append({
                        "text": _snippet(task),
                        "plain": plainify(task),
                        "from": msg.sender,
                        "deadline": _deadline_dict(d[0] if d else None),
                        "sources": [msg.id],
                    })
                    used_for_ask.add(msg.id)

        if msg.id in used_for_ask:
            continue

        # 2. Direct requests to me
        if addressed and REQUEST.search(content):
            d = _deadline_for(msg)
            focused = _focus(content, me_re)
            asks.append({
                "text": _snippet(focused),
                "plain": plainify(focused),
                "from": msg.sender,
                "deadline": _deadline_dict(d),
                "sources": [msg.id],
            })
            used_for_ask.add(msg.id)
            continue

        # 3. Questions to me, or group-wide "everyone confirm"
        if (addressed and "?" in content) or GROUP_CONFIRM.search(content):
            questions.append({
                "text": _snippet(_focus(content, me_re) if addressed else content),
                "plain": plainify(content),
                "from": msg.sender,
                "sources": [msg.id],
            })
            if not DECISION.search(content):
                continue

        # 4. Decisions made while I was away
        if DECISION.search(content) and len(content.split()) >= 4:
            decisions.append({
                "text": _snippet(content),
                "plain": plainify(content),
                "from": msg.sender,
                "sources": [msg.id],
            })
            d = _deadline_for(msg)
            if d and re.search(r"\b(due|deadline|submit|meeting|meet|present|presentation|moved|resched)", content, re.I):
                deadlines.append({"what": _snippet(content, 80), "when_human": d.human(), "iso": d.iso(), "sources": [msg.id]})
            continue

        # 5. Group deadlines that are not decisions
        if re.search(r"\b(due|deadline|submission)\b", content, re.I):
            d = _deadline_for(msg)
            if d:
                deadlines.append({"what": _snippet(content, 80), "when_human": d.human(), "iso": d.iso(), "sources": [msg.id]})

    for a in asks:
        if a["deadline"]:
            deadlines.append({
                "what": "You: " + _snippet(a["text"], 70),
                "when_human": a["deadline"]["human"],
                "iso": a["deadline"]["iso"],
                "sources": a["sources"],
            })

    # De-duplicate deadlines by (iso, source)
    seen = set()
    uniq = []
    for d in sorted(deadlines, key=lambda x: x["iso"]):
        key = (d["iso"], tuple(d["sources"]))
        if key not in seen:
            seen.add(key)
            uniq.append(d)

    return {
        "asked_of_you": asks,
        "decisions": decisions,
        "open_questions": questions,
        "deadlines": uniq,
        "draft_reply": draft_reply(asks, questions, uniq),
    }


def draft_reply(asks: list, questions: list, deadlines: list) -> str:
    parts = ["Hi all, sorry for going quiet, I've caught up now!"]
    n = len(asks)
    if n:
        parts.append(f"I saw the {n} thing{'s' if n != 1 else ''} you need from me and I'm on {'them' if n != 1 else 'it'}.")
    if questions:
        parts.append("Replying to the questions for me below.")
    group = [d for d in deadlines if not d["what"].startswith("You:")
             and re.search(r"\b(due|deadline|submit|submission)\b", d["what"], re.I)]
    if group:
        parts.append(f"Noted the {group[0]['when_human']} deadline.")
    return " ".join(parts)
