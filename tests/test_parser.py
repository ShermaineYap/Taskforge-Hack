from datetime import datetime

from engine.parser import detect_day_first, parse_chat

ANDROID = """15/10/2026, 9:58 am - Messages and calls are end-to-end encrypted. Learn more.
15/10/2026, 10:00 am - Jun Hao: Hi all
second line of the same message
17/10/2026, 11:42 pm - Aina: going quiet for a few days
20/10/2026, 10:03 pm - Jun Hao: PTT-20261020-WA0001.opus (file attached)
20/10/2026, 10:05 pm - Priya: <Media omitted>
"""

IOS = """[21/10/2026, 9:14:03 PM] ‎Farid: ‎<attached: 00000012-AUDIO-2026-10-21-21-14-03.opus>
[21/10/2026, 9:15:10 PM] Farid: ok can, time: 3pm
[22/10/2026, 12:01:00 AM] Mei Ling: midnight message
"""

US_24H = """10/21/26, 21:14 - Sam: hello
10/22/26, 08:00 - Alex: morning
"""


def test_android_basic_and_multiline():
    msgs = parse_chat(ANDROID)
    assert len(msgs) == 5
    assert msgs[0].is_system and msgs[0].sender is None
    assert msgs[1].sender == "Jun Hao"
    assert msgs[1].text == "Hi all\nsecond line of the same message"
    assert msgs[2].timestamp == datetime(2026, 10, 17, 23, 42)


def test_voice_notes_and_media_android():
    msgs = parse_chat(ANDROID)
    assert msgs[3].is_voice_note and msgs[3].attachment == "PTT-20261020-WA0001.opus"
    assert msgs[4].is_media and not msgs[4].is_voice_note


def test_ios_brackets_seconds_and_invisible_marks():
    msgs = parse_chat(IOS)
    assert [m.sender for m in msgs] == ["Farid", "Farid", "Mei Ling"]
    assert msgs[0].is_voice_note
    assert msgs[0].attachment.endswith(".opus")
    assert msgs[1].text == "ok can, time: 3pm"  # a ':' inside the text stays in the text
    assert msgs[2].timestamp == datetime(2026, 10, 22, 0, 1)  # 12 AM -> 00h


def test_month_first_24h_detected():
    assert detect_day_first(US_24H.splitlines()) is False
    msgs = parse_chat(US_24H)
    assert msgs[0].timestamp == datetime(2026, 10, 21, 21, 14)


def test_ambiguous_dates_default_to_day_first():
    msgs = parse_chat("03/04/2026, 10:00 - A: hi\n")
    assert msgs[0].timestamp.month == 4


def test_not_a_chat_returns_nothing():
    assert parse_chat("just some notes\nno timestamps here") == []
