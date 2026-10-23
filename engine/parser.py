"""Parse WhatsApp "Export chat" text files into structured messages.

Supports the formats WhatsApp actually produces:
  Android 12h : 21/10/2026, 9:14 pm - Jun Hao: message
  Android 24h : 21/10/26, 21:14 - Jun Hao: message
  iOS         : [21/10/2026, 9:14:03 PM] Jun Hao: message
plus US month-first dates, multi-line messages, system lines
("Messages and calls are end-to-end encrypted"), invisible direction
marks and narrow no-break spaces that WhatsApp inserts.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional

# Invisible characters WhatsApp sprinkles into exports.
_INVISIBLES = dict.fromkeys(map(ord, "‎‏‪‫‬‭‮﻿"), None)
_SPACES = {ord(" "): " ", ord(" "): " "}

_HEADER = re.compile(
    r"""^\[?
    (?P<d1>\d{1,2})[/.\-](?P<d2>\d{1,2})[/.\-](?P<y>\d{2,4}),?\s+
    (?P<h>\d{1,2})[:.](?P<mi>\d{2})(?:[:.](?P<s>\d{2}))?
    \s*(?P<ampm>[aApP]\.?\s?[mM]\.?)?
    \]?\s*(?:-\s*)?
    (?P<rest>.*)$""",
    re.VERBOSE,
)

_ATTACHMENT_PATTERNS = [
    re.compile(r"<attached:\s*(?P<f>[^>]+)>", re.I),                 # iOS
    re.compile(r"(?P<f>[\w\-. ]+\.\w{2,5})\s*\(file attached\)", re.I),  # Android
]
_AUDIO_EXT = (".opus", ".ogg", ".m4a", ".mp3", ".aac", ".wav")
_MEDIA_OMITTED = re.compile(r"^<?(media omitted|image omitted|audio omitted|video omitted|sticker omitted|gif omitted|document omitted)>?$", re.I)


@dataclass
class Message:
    id: int
    timestamp: datetime
    sender: Optional[str]          # None for system messages
    text: str
    is_system: bool = False
    attachment: Optional[str] = None
    is_voice_note: bool = False
    is_media: bool = False
    transcript: Optional[str] = None
    transcript_source: Optional[str] = None  # "whisper" | "demo"
    tags: list = field(default_factory=list)

    @property
    def content(self) -> str:
        """Text the engines should read: transcript for voice notes."""
        if self.transcript:
            return self.transcript
        return self.text

    def to_dict(self) -> dict:
        d = asdict(self)
        d["timestamp"] = self.timestamp.isoformat(timespec="minutes")
        d["content"] = self.content
        return d


def _clean(line: str) -> str:
    return line.translate(_INVISIBLES).translate(_SPACES).rstrip("\r\n")


def detect_day_first(lines: list[str]) -> bool:
    """WhatsApp uses the phone's locale. Decide d/m vs m/d from evidence.

    Returns True for day-first. If a first field > 12 appears it must be the
    day; if a second field > 12 appears it must be the day (month-first).
    With no evidence, default to day-first (Malaysia, UK, most of the world).
    """
    first_gt12 = second_gt12 = False
    for raw in lines:
        m = _HEADER.match(_clean(raw))
        if not m:
            continue
        if int(m.group("d1")) > 12:
            first_gt12 = True
        if int(m.group("d2")) > 12:
            second_gt12 = True
    if second_gt12 and not first_gt12:
        return False
    return True


def _to_datetime(m: re.Match, day_first: bool) -> Optional[datetime]:
    d1, d2, y = int(m.group("d1")), int(m.group("d2")), int(m.group("y"))
    day, month = (d1, d2) if day_first else (d2, d1)
    if y < 100:
        y += 2000
    h, mi = int(m.group("h")), int(m.group("mi"))
    s = int(m.group("s") or 0)
    ampm = (m.group("ampm") or "").lower().replace(".", "").replace(" ", "")
    if ampm == "pm" and h != 12:
        h += 12
    elif ampm == "am" and h == 12:
        h = 0
    try:
        return datetime(y, month, day, h, mi, s)
    except ValueError:
        return None


def _split_sender(rest: str) -> tuple[Optional[str], str]:
    # "Name: text". Sender names can contain spaces, emoji, + and digits.
    idx = rest.find(": ")
    if idx == -1:
        if rest.endswith(":"):
            return rest[:-1].strip(), ""
        return None, rest
    sender = rest[:idx].strip()
    # Guard against system lines that merely contain ": " far in.
    if len(sender) > 60 or not sender:
        return None, rest
    return sender, rest[idx + 2:]


def _detect_attachment(text: str) -> tuple[Optional[str], bool, bool]:
    for pat in _ATTACHMENT_PATTERNS:
        m = pat.search(text)
        if m:
            fname = m.group("f").strip()
            is_voice = fname.lower().endswith(_AUDIO_EXT) and (
                "PTT" in fname.upper() or "AUDIO" in fname.upper() or fname.lower().endswith(".opus")
            )
            return fname, is_voice, True
    if _MEDIA_OMITTED.match(text.strip()):
        return None, "audio" in text.lower(), True
    return None, False, False


def parse_chat(raw_text: str) -> list[Message]:
    lines = raw_text.splitlines()
    day_first = detect_day_first(lines)
    messages: list[Message] = []
    for raw in lines:
        line = _clean(raw)
        m = _HEADER.match(line)
        ts = _to_datetime(m, day_first) if m else None
        if m and ts is not None:
            sender, text = _split_sender(m.group("rest"))
            attachment, is_voice, is_media = _detect_attachment(text)
            messages.append(
                Message(
                    id=len(messages),
                    timestamp=ts,
                    sender=sender,
                    text=text.strip(),
                    is_system=sender is None,
                    attachment=attachment,
                    is_voice_note=is_voice,
                    is_media=is_media,
                )
            )
        elif messages and line.strip():
            # Continuation of a multi-line message.
            messages[-1].text += "\n" + line
    return messages


def participants(messages: list[Message]) -> list[str]:
    seen: dict[str, int] = {}
    for msg in messages:
        if msg.sender:
            seen[msg.sender] = seen.get(msg.sender, 0) + 1
    return sorted(seen, key=lambda s: -seen[s])
