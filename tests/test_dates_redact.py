from datetime import date, datetime, time

from engine.dates import find_dates
from engine.parser import parse_chat
from engine.redact import redact_messages, redact_text

TUE = datetime(2026, 10, 20, 13, 12)  # Tuesday


def first(text, sent=TUE):
    found = find_dates(text, sent)
    return found[0] if found else None


def test_tomorrow_night():
    d = first("send it before tmr night pls")
    assert d.day == date(2026, 10, 21) and d.at == time(21, 0)


def test_weekday_with_time():
    d = first("book the room for Monday 2pm")
    assert d.day == date(2026, 10, 26) and d.at == time(14, 0)


def test_explicit_date_beats_weekday_word():
    d = first("draft due Fri 30 Oct 11.59pm")
    assert d.day == date(2026, 10, 30) and d.at == time(23, 59)


def test_numeric_date():
    assert first("submit on 31/10").day == date(2026, 10, 31)


def test_same_weekday_means_today_unless_next():
    assert first("tuesday").day == date(2026, 10, 20)
    assert first("next tuesday").day == date(2026, 10, 27)


def test_time_alone_is_not_a_date():
    assert first("at 9.30pm") is None


def test_redact_phone_and_email_but_not_dates():
    out = redact_text("call me 012-345 6789 or +60 12 345 6789, mail a.b@uni.edu.my, due 30/10/2026")
    assert "345" not in out and "@" not in out
    assert out.count("[phone]") == 2 and "[email]" in out
    assert "30/10/2026" in out


def test_unsaved_contact_senders_are_aliased():
    msgs = parse_chat("20/10/2026, 10:00 am - +60 12-345 6789: hi\n20/10/2026, 10:01 am - +60 12-345 6789: again\n")
    report = redact_messages(msgs)
    assert msgs[0].sender == msgs[1].sender == "Unsaved contact 1"
    assert report["aliased_senders"] == 1
