import json
from pathlib import Path

import pytest

from engine import analyze, llm
from engine.ics import build_ics
from engine.parser import parse_chat

ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "demo"


@pytest.fixture(scope="module")
def demo():
    return analyze(
        (DEMO / "aina_fyp_chat.txt").read_text(encoding="utf-8"), ["Aina", "Ain"], "last_spoke", "rules",
        demo_transcripts=json.loads((DEMO / "voice_transcripts.json").read_text(encoding="utf-8")),
    )


def test_window_starts_after_my_last_message(demo):
    assert demo["cutoff"].startswith("2026-10-17T23:42")
    assert all(m["sender"] != "Aina" for m in demo["messages"])
    assert demo["stats"]["messages"] > 300


def test_finds_every_ask_including_voice_note_and_task_list(demo):
    asks = demo["result"]["asked_of_you"]
    texts = " ".join(a["text"].lower() for a in asks)
    assert "literature review" in texts
    assert "figma" in texts
    assert "discussion room" in texts  # only said in a voice note
    assert "3 papers" in texts


def test_does_not_assign_other_peoples_tasks(demo):
    texts = " ".join(a["text"].lower() for a in demo["result"]["asked_of_you"])
    assert "login bug" not in texts  # asked of Farid
    assert "cat" not in texts       # mentions Aina, asks nothing


def test_every_item_cites_a_message_in_the_window(demo):
    ids = {m["id"] for m in demo["messages"]}
    for key in ("asked_of_you", "decisions", "open_questions", "deadlines"):
        for item in demo["result"][key]:
            assert item["sources"] and set(item["sources"]) <= ids


def test_deadlines_resolved_relative_to_message(demo):
    isos = {d["iso"] for d in demo["result"]["deadlines"]}
    assert "2026-10-30T23:59" in isos   # Fri 30 Oct 11.59pm
    assert "2026-10-26T14:00" in isos   # Monday 2pm


def test_output_much_shorter_than_input(demo):
    s = demo["stats"]
    assert s["words_out"] < s["words_in"] * 0.4


def test_since_options():
    raw = (DEMO / "aina_fyp_chat.txt").read_text(encoding="utf-8")
    day = analyze(raw, ["Aina"], "24h", "rules")
    week = analyze(raw, ["Aina"], "7d", "rules")
    assert day["stats"]["messages"] < week["stats"]["messages"]


def test_errors_are_helpful():
    with pytest.raises(ValueError, match="name"):
        analyze("x", [], "all", "rules")
    with pytest.raises(ValueError, match="Export chat"):
        analyze("not a chat", ["Aina"], "all", "rules")


def test_ai_requested_without_key_falls_back(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    raw = (DEMO / "aina_fyp_chat.txt").read_text(encoding="utf-8")
    out = analyze(raw, ["Aina"], "last_spoke", "ai")
    assert out["engine"] == "rules" and out["warnings"]


def test_llm_validation_drops_ungrounded_items():
    msgs = parse_chat(
        "20/10/2026, 1:00 pm - Priya: Aina can you send the Figma link by tmr\n"
        "20/10/2026, 1:05 pm - Farid: ok\n"
    )
    raw = {
        "asked_of_you": [
            {"text": "Send Priya the Figma link", "plain": "Send the Figma link", "from": "Priya",
             "when_text": "tmr", "sources": [0]},
            {"text": "Invented task", "plain": "", "from": "X", "when_text": None, "sources": [99]},
            {"text": "No source", "plain": "", "from": "X", "when_text": None, "sources": []},
            {"text": "Says ok", "plain": "", "from": "Farid", "when_text": None, "sources": ["1"]},
        ],
        "decisions": "not a list",
        "open_questions": [],
        "deadlines": [{"what": "Figma link", "when_text": "tmr", "sources": [0]},
                      {"what": "ghost", "when_text": "no date here", "sources": [1]}],
        "draft_reply": "On it!",
    }
    clean, report = llm.validate(raw, msgs, ["Aina"])
    assert [a["text"] for a in clean["asked_of_you"]] == ["Send Priya the Figma link", "Says ok"]
    assert clean["asked_of_you"][0]["deadline"]["iso"] == "2026-10-21"   # resolved by code, not the model
    assert clean["asked_of_you"][0]["inferred"] is False
    assert clean["asked_of_you"][1]["inferred"] is True   # cited message never names Aina
    assert [d["what"] for d in clean["deadlines"]] == ["Figma link"]
    assert report["dropped_ungrounded"] == 3


def test_ics_is_valid_calendar():
    ics = build_ics([{"what": "Draft due, Moodle; IEEE", "iso": "2026-10-30T23:59", "when_human": "x", "sources": [1]},
                     {"what": "All-day thing", "iso": "2026-10-31", "when_human": "x", "sources": [2]}])
    assert ics.startswith("BEGIN:VCALENDAR") and ics.rstrip().endswith("END:VCALENDAR")
    assert ics.count("BEGIN:VEVENT") == 2
    assert "DTSTART:20261030T235900" in ics and "DTSTART;VALUE=DATE:20261031" in ics
    assert "Draft due\\, Moodle\\; IEEE" in ics
    assert all(len(line.encode()) <= 75 for line in ics.split("\r\n"))
