"""Generate the synthetic demo chat for persona Aina + ground-truth labels.

Everything here is fictional and written for this project; no real chat
was used. Run:  python demo/build_demo.py
Outputs: demo/aina_fyp_chat.txt, demo/voice_transcripts.json, demo/expected.json
"""
from __future__ import annotations

import json
import random
from datetime import datetime, timedelta
from pathlib import Path

HERE = Path(__file__).parent
rng = random.Random(2026)
NNBSP = " "  # WhatsApp Android puts a narrow no-break space before am/pm

MEMBERS = ["Jun Hao", "Priya", "Farid", "Mei Ling", "Daniel"]

NOISE = {
    "Jun Hao": ["ok noted", "haha", "who's coming to class tmr", "bro the wifi in block B is dead again",
                "anyone eating? I'm starving", "lol", "nice one", "ok can", "wait I check", "brb",
                "omg this lecture is so long", "😂😂", "same", "later we discuss", "ya ya"],
    "Priya": ["lolll", "same tbh", "I'm at mamak now", "who wants bubble tea", "the quiz was so hard 😭",
              "ok wait", "hahaha", "true", "sending the meme", "omg", "can", "noted 👍", "slayyy",
              "I need sleep", "lunch anyone?"],
    "Farid": ["ok bro", "haha", "noted", "boleh", "wait I'm driving", "yes", "lol", "I'm stuck in jam on LDP",
              "steady", "ok ok", "who has the parking coupon", "😂", "nvm", "ya can", "alamak"],
    "Mei Ling": ["ok!", "noted", "haha same", "who took my charger 😭", "ok thanks", "yes", "wait what",
                 "lol", "the library is full again", "anyone at campus?", "hehe", "okie", "good night all",
                 "morning!", "true"],
    "Daniel": ["haha", "ok", "yes bro", "lol", "noted", "anyone playing valo tonight", "I'm sleeping already",
               "same", "nice", "lmao", "ok can", "who's free saturday", "sian", "true true", "ok"],
}
MEDIA = "<Media omitted>"
TOPIC_CHATTER = [
    ("Priya", "did anyone see the new canteen menu"),
    ("Daniel", "the nasi lemak there is not bad actually"),
    ("Farid", "too oily la"),
    ("Mei Ling", "anyone got the week 5 slides?"),
    ("Jun Hao", "check moodle, under week 5 folder"),
    ("Mei Ling", "found it thanks"),
    ("Daniel", "lol Aina posted her cat on IG, so cute"),
    ("Priya", "her cat is famous already haha"),
    ("Farid", "who is going to the career fair on wed"),
    ("Jun Hao", "me, need internship 😭"),
    ("Daniel", "Farid can you fix the login bug before Monday"),
    ("Farid", "ok I'll try tonight"),
    ("Priya", "is the parking at APU still full in the morning"),
    ("Mei Ling", "always lol"),
]
LONG_CHATTER = [
    ("Priya", "honestly this sem is killing me, 3 assignments due the same week and the FYP on top of that"),
    ("Daniel", "my manager asked me to cover extra shifts this weekend so I might be slow to reply"),
    ("Farid", "anyone know if the career fair needs us to bring printed resumes or just the QR thing"),
    ("Mei Ling", "I booked the small discussion room for my other group but they cancelled on me again haiz"),
    ("Jun Hao", "reminder that the library closes at 10pm on weekends now, don't get locked in like last time"),
    ("Priya", "the data mining quiz was so unfair, half the questions were not even from the slides"),
    ("Daniel", "I found a youtube channel that explains face recognition really well, will share later"),
    ("Farid", "my laptop fan sounds like a helicopter every time I open android studio, send help"),
    ("Mei Ling", "does anyone have a good gantt chart template? the one from last sem looks so ugly"),
    ("Jun Hao", "I'll be in the lab until 6 if anyone wants to sit together and work on the proposal"),
    ("Priya", "grab food is so expensive now, I'm going to start bringing lunch from home"),
    ("Daniel", "did you guys get the email about the timetable change for next week? some classes moved to friday"),
    ("Farid", "ok who ate my kuih in the lab fridge, I labelled it with my name"),
    ("Mei Ling", "I'm so behind on my readings, going to spend the whole weekend at the library"),
    ("Jun Hao", "if anyone needs the github repo access just send me your username"),
    ("Priya", "my sister's wedding is next month so I'll be busy a few weekends, just letting you know early"),
]


def stamp(dt: datetime) -> str:
    h12 = dt.strftime("%I").lstrip("0")
    ampm = dt.strftime("%p").lower()
    return f"{dt:%d/%m/%Y}, {h12}:{dt:%M}{NNBSP}{ampm}"


lines: list[tuple[datetime, str, str]] = []
labels: list[dict] = []
voice: dict[str, str] = {}
vn_counter = [0]


def add(dt, sender, text, label=None, match=None):
    lines.append((dt, sender, text))
    if label:
        for cat in label if isinstance(label, list) else [label]:
            labels.append({"category": cat, "match": match or text[:60], "sender": sender})


def voice_note(dt, sender, transcript, label=None):
    vn_counter[0] += 1
    fname = f"PTT-{dt:%Y%m%d}-WA{vn_counter[0]:04d}.opus"
    voice[fname] = transcript
    lines.append((dt, sender, f"{fname} (file attached)"))
    for cat in (label if isinstance(label, list) else [label] if label else []):
        labels.append({"category": cat, "match": fname, "sender": sender})


def chatter(start: datetime, end: datetime, n: int):
    span = (end - start).total_seconds()
    for _ in range(n):
        dt = start + timedelta(seconds=rng.random() * span)
        # people chat 9am-1am
        if 2 <= dt.hour < 9:
            dt = dt.replace(hour=rng.randint(9, 23))
        s = rng.choice(MEMBERS)
        r = rng.random()
        if r < 0.08:
            add(dt, s, MEDIA)
        else:
            add(dt, s, rng.choice(NOISE[s]))


# ---------- CONTEXT: before Aina goes quiet (Thu 15 - Sat 17 Oct) ----------
d = datetime(2026, 10, 15, 10, 0)
add(d, "Jun Hao", "Hi all, welcome to FYP group 7 🎉 supervisor is Dr Wong")
add(d + timedelta(minutes=3), "Aina", "hi everyone! excited to work with you all")
add(d + timedelta(minutes=5), "Priya", "hiii")
add(d + timedelta(hours=2), "Jun Hao", "two topic options: (A) canteen pre-order app, (B) lecturer attendance app with face recognition. think about it")
add(d + timedelta(hours=3), "Aina", "I like B, more AI stuff. I can help with research side")
chatter(datetime(2026, 10, 15, 14, 0), datetime(2026, 10, 17, 22, 0), 40)
add(datetime(2026, 10, 17, 23, 42), "Aina",
    "guys I'm going quiet for a few days, 2 exams + work shifts 😵 ping me if urgent, will catch up after")
add(datetime(2026, 10, 17, 23, 50), "Mei Ling", "good luck Aina!!")

# ---------- WINDOW: Aina is away (Sun 18 - Thu 22 Oct) ----------
chatter(datetime(2026, 10, 18, 9, 0), datetime(2026, 10, 22, 23, 30), 268)

for i, (s, t) in enumerate(LONG_CHATTER):
    add(datetime(2026, 10, 18, 10, 0) + timedelta(hours=6 * i, minutes=rng.randint(0, 50)), s, t)

for i, (s, t) in enumerate(TOPIC_CHATTER):
    add(datetime(2026, 10, 18, 12, 0) + timedelta(hours=7 * i, minutes=rng.randint(0, 50)), s, t)

add(datetime(2026, 10, 18, 20, 15), "Jun Hao",
    "ok so we decided: final topic is B, the lecturer attendance app. not the canteen one", "decisions")

add(datetime(2026, 10, 19, 21, 4), "Jun Hao",
    "Ok task split for the proposal draft:\nJun Hao - intro + problem statement\nPriya - system design + Figma\n"
    "Farid - methodology\nMei Ling - project plan / gantt\nDaniel - feasibility\n"
    "Aina - literature review (min 15 refs)", "asked_of_you", match="Ok task split for the proposal draft")
add(datetime(2026, 10, 19, 21, 30), "Mei Ling",
    "Supervisor said draft due Fri 30 Oct 11.59pm, submit thru moodle", ["decisions", "deadlines"])

add(datetime(2026, 10, 20, 13, 12), "Priya",
    "@Aina can you send me your Figma link for the user flow you did last sem? before tmr night pls 🙏",
    ["asked_of_you", "deadlines"])
add(datetime(2026, 10, 20, 16, 40), "Daniel",
    "Dr Wong replied, presentation is 10 min max now, not 15. and he wants a live demo", "decisions")
voice_note(datetime(2026, 10, 20, 22, 3), "Jun Hao",
           "Hi guys, ah, quick one. Ain, can you also book the discussion room in the library for Monday 2pm? "
           "Need the big one on level 4. Thanks ah.", ["asked_of_you", "deadlines"])

add(datetime(2026, 10, 21, 10, 25), "Jun Hao",
    "Final: we use IEEE referencing, NOT APA. Aina take note ya since you doing lit review", "decisions")
add(datetime(2026, 10, 21, 15, 2), "Farid",
    "we're switching from MySQL to Firebase, easier for the demo", "decisions")
add(datetime(2026, 10, 21, 19, 48), "Mei Ling",
    "Aina are you ok to take the Q&A part during the presentation?", "open_questions")

add(datetime(2026, 10, 22, 11, 5), "Jun Hao",
    "Meeting moved to Monday 26 Oct 2pm, L4 discussion room. Everyone pls confirm can come or not",
    ["decisions", "open_questions", "deadlines"])
add(datetime(2026, 10, 22, 16, 33), "Priya",
    "Aina also pls add the 3 papers I put in the drive into your lit review, the ones on face recognition attendance",
    "asked_of_you")
add(datetime(2026, 10, 22, 22, 47), "Jun Hao", "Aina are u alive 😂 pls reply when u see this", "neutral")

# Mundane voice notes
voice_note(datetime(2026, 10, 18, 13, 20), "Priya", "Lol I'm at the mamak now, anyone want teh tarik? I'm buying.")
voice_note(datetime(2026, 10, 19, 9, 41), "Farid", "Jam on the LDP again, I'll be late for class, someone sign for me can?")
voice_note(datetime(2026, 10, 20, 18, 2), "Daniel", "Bro the valorant match last night was crazy, I tell you tomorrow.")
voice_note(datetime(2026, 10, 21, 12, 30), "Mei Ling", "Okay I'm at the library, level 2 is full, I'm going up.")
voice_note(datetime(2026, 10, 22, 8, 55), "Priya", "Morning guys, I overslept, see you all at the lecture.")
voice_note(datetime(2026, 10, 22, 20, 10), "Farid", "Okay login bug fixed, I pushed to GitHub already.")

lines.sort(key=lambda x: x[0])
out = [f"{stamp(datetime(2026, 10, 15, 9, 58))} - Messages and calls are end-to-end encrypted. "
       "Only people in this chat can read, listen to, or share them. Learn more.",
       f"{stamp(datetime(2026, 10, 15, 9, 59))} - Jun Hao created group \"FYP Group 7 🔥\""]
for dt, sender, text in lines:
    out.append(f"{stamp(dt)} - {sender}: {text}")

(HERE / "aina_fyp_chat.txt").write_text("\n".join(out) + "\n", encoding="utf-8")
(HERE / "voice_transcripts.json").write_text(json.dumps(voice, indent=2, ensure_ascii=False), encoding="utf-8")
(HERE / "expected.json").write_text(json.dumps({
    "persona": "Aina",
    "me": ["Aina", "Ain"],
    "since": "last_spoke",
    "note": "Ground truth for the synthetic demo chat. 'match' is a substring of the source message text "
            "(or the voice note filename). 'neutral' items are not scored either way.",
    "labels": labels,
}, indent=2, ensure_ascii=False), encoding="utf-8")
print(f"{len(out)} lines, {len(voice)} voice notes, {len(labels)} labels")
