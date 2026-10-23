"""Build an .ics calendar file from extracted deadlines (RFC 5545)."""
from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone


def _esc(s: str) -> str:
    return s.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def _fold(line: str) -> str:
    out, cur = [], line
    while len(cur.encode()) > 73:
        cut = 73
        while len(cur[:cut].encode()) > 73:
            cut -= 1
        out.append(cur[:cut])
        cur = " " + cur[cut:]
    out.append(cur)
    return "\r\n".join(out)


def build_ics(deadlines: list[dict], chat_name: str = "group chat") -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Rejoin//Catch-up handoff//EN", "CALSCALE:GREGORIAN"]
    for d in deadlines:
        uid = hashlib.sha1((d["iso"] + d["what"]).encode()).hexdigest()[:16] + "@rejoin"
        lines += ["BEGIN:VEVENT", f"UID:{uid}", f"DTSTAMP:{stamp}"]
        if "T" in d["iso"]:
            start = datetime.fromisoformat(d["iso"])
            end = start + timedelta(minutes=30)
            lines += [f"DTSTART:{start:%Y%m%dT%H%M%S}", f"DTEND:{end:%Y%m%dT%H%M%S}"]
        else:
            day = datetime.fromisoformat(d["iso"])
            lines += [f"DTSTART;VALUE=DATE:{day:%Y%m%d}", f"DTEND;VALUE=DATE:{day + timedelta(days=1):%Y%m%d}"]
        lines.append(_fold("SUMMARY:" + _esc(d["what"])))
        lines.append(_fold("DESCRIPTION:" + _esc(f"From your {chat_name} catch-up (Rejoin).")))
        lines += ["BEGIN:VALARM", "TRIGGER:-PT12H", "ACTION:DISPLAY", "DESCRIPTION:Reminder", "END:VALARM", "END:VEVENT"]
    lines.append("END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n"
