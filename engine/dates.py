"""Find and resolve informal date/time phrases relative to when a message was sent.

"by Thu", "tmr night", "Fri 31 Oct 11:59pm", "next Monday 2pm", "30/10" ...
Everything resolves against the message timestamp, not "now", because
"tomorrow" in a message sent on Tuesday means Wednesday.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Optional

WEEKDAYS = {
    "mon": 0, "monday": 0, "tue": 1, "tues": 1, "tuesday": 1, "wed": 2, "wednesday": 2,
    "thu": 3, "thur": 3, "thurs": 3, "thursday": 3, "fri": 4, "friday": 4,
    "sat": 5, "saturday": 5, "sun": 6, "sunday": 6,
}
MONTHS = {
    "jan": 1, "january": 1, "feb": 2, "february": 2, "mar": 3, "march": 3, "apr": 4, "april": 4,
    "may": 5, "jun": 6, "june": 6, "jul": 7, "july": 7, "aug": 8, "august": 8,
    "sep": 9, "sept": 9, "september": 9, "oct": 10, "october": 10, "nov": 11, "november": 11,
    "dec": 12, "december": 12,
}

_WD = r"(?P<wd>mon(?:day)?|tue(?:s(?:day)?)?|wed(?:nesday)?|thu(?:r(?:s(?:day)?)?)?|fri(?:day)?|sat(?:urday)?|sun(?:day)?)"
_MON = r"(?P<mon>jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|july?|aug(?:ust)?|sept?(?:ember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)"
_TIME = r"(?P<time>\d{1,2}(?:[:.]\d{2})?\s?(?:am|pm)|\d{1,2}[:.]\d{2}|noon|midnight)"

PATTERNS = [
    ("dmy", re.compile(r"\b(?P<d>\d{1,2})[/.](?P<m>\d{1,2})(?:[/.](?P<y>\d{2,4}))?\b")),
    ("d_mon", re.compile(r"\b(?P<d>\d{1,2})(?:st|nd|rd|th)?\s+" + _MON + r"\b", re.I)),
    ("mon_d", re.compile(r"\b" + _MON + r"\s+(?P<d>\d{1,2})(?:st|nd|rd|th)?\b", re.I)),
    ("rel", re.compile(r"\b(?P<rel>today|tonight|tmr|tmrw|tomorrow|esok|day after tomorrow|lusa)\b", re.I)),
    ("wd", re.compile(r"\b(?P<next>next\s+|this\s+|coming\s+)?" + _WD + r"\b", re.I)),
]
TIME_RE = re.compile(r"\b" + _TIME + r"\b", re.I)
DEADLINE_CUE = re.compile(
    r"\b(by|before|due|deadline|submit|submission|latest|until|no later than|on|at|meeting|meet|present|presentation)\b",
    re.I,
)


@dataclass
class ResolvedDate:
    text: str
    day: date
    at: Optional[time]

    def iso(self) -> str:
        if self.at:
            return datetime.combine(self.day, self.at).isoformat(timespec="minutes")
        return self.day.isoformat()

    def human(self) -> str:
        s = self.day.strftime("%a %d %b")
        if self.at:
            s += " " + self.at.strftime("%I:%M%p").lstrip("0").lower().replace(":00", "")
        return s


def _parse_time(s: str) -> Optional[time]:
    s = s.lower().strip()
    if s == "noon":
        return time(12, 0)
    if s == "midnight":
        return time(23, 59)
    m = re.match(r"(\d{1,2})(?:[:.](\d{2}))?\s?(am|pm)?", s)
    if not m:
        return None
    h, mi, ap = int(m.group(1)), int(m.group(2) or 0), m.group(3)
    if ap == "pm" and h != 12:
        h += 12
    if ap == "am" and h == 12:
        h = 0
    if not ap and m.group(2) is None:
        return None
    if h > 23 or mi > 59:
        return None
    return time(h, mi)


def find_dates(text: str, sent: datetime) -> list[ResolvedDate]:
    found: list[ResolvedDate] = []
    taken: list[tuple[int, int]] = []
    base = sent.date()
    for kind, pat in PATTERNS:
        for m in pat.finditer(text):
            if any(a <= m.start() < b for a, b in taken):
                continue
            day: Optional[date] = None
            try:
                if kind == "dmy":
                    d, mo = int(m.group("d")), int(m.group("m"))
                    y = m.group("y")
                    yr = int(y) + (2000 if y and len(y) == 2 else 0) if y else base.year
                    if not (1 <= mo <= 12 and 1 <= d <= 31):
                        continue
                    day = date(yr, mo, d)
                    if not y and day < base - timedelta(days=60):
                        day = date(yr + 1, mo, d)
                elif kind in ("d_mon", "mon_d"):
                    mo = MONTHS[m.group("mon").lower()[:3] if m.group("mon").lower()[:4] != "sept" else "sep"]
                    day = date(base.year, mo, int(m.group("d")))
                    if day < base - timedelta(days=60):
                        day = date(base.year + 1, mo, int(m.group("d")))
                elif kind == "rel":
                    r = m.group("rel").lower()
                    offset = {"today": 0, "tonight": 0, "tmr": 1, "tmrw": 1, "tomorrow": 1, "esok": 1,
                              "day after tomorrow": 2, "lusa": 2}[r]
                    day = base + timedelta(days=offset)
                elif kind == "wd":
                    target = WEEKDAYS[m.group("wd").lower()]
                    delta = (target - base.weekday()) % 7
                    nxt = (m.group("next") or "").strip().lower()
                    if delta == 0:
                        delta = 7 if nxt == "next" else 0
                    elif nxt == "next" and delta < 3:
                        # "next Mon" said on a Saturday still means the coming Monday.
                        pass
                    day = base + timedelta(days=delta)
            except (ValueError, KeyError):
                continue
            if day is None:
                continue
            # Look for a time within 14 chars either side.
            window = text[max(0, m.start() - 14): m.end() + 14]
            tm = TIME_RE.search(window)
            at = _parse_time(tm.group("time")) if tm else None
            if at is None and kind == "rel" and (
                m.group("rel").lower() == "tonight" or re.match(r"\s*night", text[m.end():m.end() + 7], re.I)
            ):
                at = time(21, 0)
            found.append(ResolvedDate(text=m.group(0), day=day, at=at))
            found[-1]._kind, found[-1]._pos = kind, m.start()  # type: ignore[attr-defined]
            taken.append((m.start(), m.end()))
    explicit = [f for f in found if f._kind in ("dmy", "d_mon", "mon_d")]  # type: ignore[attr-defined]
    # "Fri 30 Oct": the weekday next to an explicit date is the same date, not a second one.
    found = [
        f for f in found
        if f._kind != "wd" or not any(abs(f._pos - e._pos) <= 10 for e in explicit)  # type: ignore[attr-defined]
    ]
    # Most specific first, then reading order.
    rank = {"dmy": 0, "d_mon": 0, "mon_d": 0, "rel": 1, "wd": 1}
    found.sort(key=lambda r: (rank[r._kind], r._pos))  # type: ignore[attr-defined]
    return found
