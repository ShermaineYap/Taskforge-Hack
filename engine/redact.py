"""Remove personal identifiers before any text leaves the machine.

Senders shown as raw phone numbers (unsaved contacts) become
"Unsaved contact 1", "Unsaved contact 2"... consistently across the chat.
Phone numbers and e-mail addresses inside message bodies are masked.
"""
from __future__ import annotations

import re

PHONE = re.compile(r"(?<![\w/])\+?\d[\d\s\-().]{7,}\d(?![\w/])")
EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
# Sender field that is only a phone number.
PHONE_SENDER = re.compile(r"^\+?[\d\s\-().]{8,}$")
# Dates like 30/10/2026 must survive the phone regex.
_DATEISH = re.compile(r"^\d{1,2}[/.\-]\d{1,2}([/.\-]\d{2,4})?$")


def _mask_phone(m: re.Match) -> str:
    s = m.group(0)
    if _DATEISH.match(s.strip()):
        return s
    digits = re.sub(r"\D", "", s)
    if len(digits) < 9:
        return s
    return "[phone]"


def redact_text(text: str) -> str:
    text = EMAIL.sub("[email]", text)
    text = PHONE.sub(_mask_phone, text)
    return text


class SenderAliaser:
    def __init__(self) -> None:
        self.map: dict[str, str] = {}

    def __call__(self, sender: str | None) -> str | None:
        if sender is None:
            return None
        if PHONE_SENDER.match(sender.strip()):
            if sender not in self.map:
                self.map[sender] = f"Unsaved contact {len(self.map) + 1}"
            return self.map[sender]
        return sender


def redact_messages(messages) -> dict:
    """Mutates messages in place. Returns a small report for the UI."""
    aliaser = SenderAliaser()
    masked = 0
    for msg in messages:
        msg.sender = aliaser(msg.sender)
        for attr in ("text", "transcript"):
            val = getattr(msg, attr)
            if val:
                new = redact_text(val)
                if new != val:
                    masked += new.count("[phone]") + new.count("[email]") - (
                        val.count("[phone]") + val.count("[email]")
                    )
                setattr(msg, attr, new)
    return {"masked_identifiers": masked, "aliased_senders": len(aliaser.map)}
