"""Plain-language helpers used by the offline engine and for word counts.

The AI engine writes its own plain-language versions; this module is the
deterministic fallback so plain mode still works with no network.
"""
from __future__ import annotations

import re

SLANG = {
    r"\bpls\b|\bplz\b|\bplis\b": "please",
    r"\btmr\b|\btmrw\b|\besok\b": "tomorrow",
    r"\bu\b": "you",
    r"\bur\b": "your",
    r"\br\b": "are",
    r"\bppl\b": "people",
    r"\bmsg\b": "message",
    r"\bthx\b|\btq\b|\bty\b": "thanks",
    r"\bidk\b": "I don't know",
    r"\blmk\b": "let me know",
    r"\basap\b": "as soon as possible",
    r"\bbtw\b": "by the way",
    r"\bfyi\b": "for your information",
    r"\bw/\b": "with",
    r"\bbcs\b|\bbcoz\b|\bcuz\b": "because",
    r"\bdun\b": "don't",
    r"\bcan or not\b": "is that OK",
    r"\bboleh tak\b": "can you",
    r"\btolong\b": "please",
    r"\bkorang\b": "everyone",
    r"\bsupervisor\b": "supervisor",
    r"\blit review\b": "literature review",
    r"\brefs\b": "references",
    r"\bdiscussion rm\b": "discussion room",
    r"\bpresentation\b": "presentation",
}
PARTICLES = re.compile(r"\s*\b(lah|lor|leh|meh|mah|ah|hor|kan|wei|bro|sis|guys)\b[,!.]*", re.I)
EMOJI = re.compile(
    "[\U0001F300-\U0001FAFF\U00002600-\U000027BF\U0001F000-\U0001F2FF⭐✅❌️]+"
)
MENTION = re.compile(r"@\S+\s*")


def strip_noise(text: str) -> str:
    text = EMOJI.sub("", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip(" ,")


def plainify(text: str, max_words: int = 22) -> str:
    t = strip_noise(text)
    t = MENTION.sub("", t)
    for pat, rep in SLANG.items():
        t = re.sub(pat, rep, t, flags=re.I)
    t = PARTICLES.sub("", t)
    t = re.sub(r"([!?.])\1+", r"\1", t)
    t = re.sub(r"\s+", " ", t).strip(" ,.-")
    words = t.split()
    if len(words) > max_words:
        t = " ".join(words[:max_words]).rstrip(",;") + "…"
    if t:
        t = t[0].upper() + t[1:]
    return t


def word_count(text: str) -> int:
    return len(re.findall(r"[\w'’]+", text or ""))


READING_WPM = 238  # Brysbaert (2019) average silent reading rate, adults, English non-fiction


def reading_seconds(words: int) -> int:
    return round(words / READING_WPM * 60)
