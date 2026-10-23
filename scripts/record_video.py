"""Record the narrated, captioned demo video.

Needs: the app running on :5000, Playwright + Chromium, ffmpeg, and narration
WAVs plus segments.json (made with Piper TTS) in --media.

    python scripts/record_video.py --media path/to/video --out docs/rejoin-demo.mp4
"""
from __future__ import annotations

import argparse
import html
import json
import shutil
import subprocess
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
URL = "http://127.0.0.1:5000/"
W, H = 1280, 720

CAPTION_JS = """
(() => {
  if (document.getElementById('rj-cap')) return;
  const d = document.createElement('div'); d.id = 'rj-cap';
  d.style.cssText = 'position:fixed;left:50%;bottom:22px;transform:translateX(-50%);max-width:1080px;width:max-content;'
    + 'background:rgba(16,24,44,.92);color:#fff;font:600 22px/1.35 "Atkinson Hyperlegible",Verdana,sans-serif;'
    + 'padding:10px 18px;border-radius:8px;z-index:99999;text-align:center;pointer-events:none';
  document.documentElement.append(d);
})();
"""

CARD = """<!doctype html><html><head><meta charset=utf-8>
<link href="https://fonts.googleapis.com/css2?family=Atkinson+Hyperlegible:wght@400;700&family=Caveat:wght@600&display=swap" rel="stylesheet">
<style>
body{{margin:0;height:100vh;background:#E6ECF2;color:#1A2847;font-family:"Atkinson Hyperlegible",Verdana,sans-serif;display:flex;align-items:center;justify-content:center}}
.box{{width:1000px}} h1{{font-size:64px;line-height:1.05;margin:0 0 18px;letter-spacing:-.02em}}
p{{font-size:28px;margin:8px 0;color:#3D4C6B}} .mark{{font-weight:700;font-size:30px;margin-bottom:28px}}
.mark:before{{content:"";display:inline-block;width:28px;height:21px;margin-right:12px;background:#F7D6DC;border:3px solid #1A2847;border-radius:2px;vertical-align:-2px}}
.hand{{font-family:Caveat,cursive;font-size:44px;color:#B4233A}}
ul{{font-size:28px;line-height:1.6;padding-left:28px}}
</style></head><body><div class=box>{body}</div></body></html>"""

WALL = """<!doctype html><html><head><meta charset=utf-8><style>
body{{margin:0;background:#0B141A;font-family:Segoe UI,Helvetica,Arial,sans-serif}}
header{{position:fixed;top:0;left:0;right:0;background:#202C33;color:#E9EDEF;padding:14px 24px;font-size:20px;z-index:2}}
header b{{font-size:22px}} header span{{color:#8696A0;font-size:16px;display:block}}
.badge{{position:fixed;right:28px;top:18px;background:#25D366;color:#0B141A;font-weight:700;border-radius:999px;padding:4px 14px;z-index:3;font-size:20px}}
ol{{list-style:none;margin:0;padding:90px 120px 400px}}
li{{max-width:640px;margin:6px 0;padding:6px 12px 8px;border-radius:8px;background:#202C33;color:#E9EDEF;font-size:17px;line-height:1.35}}
li i{{display:block;font-style:normal;font-size:13px;font-weight:700}} li small{{color:#8696A0;font-size:11px;margin-left:8px}}
</style></head><body><header><b>FYP Group 7 🔥</b><span>Jun Hao, Priya, Farid, Mei Ling, Daniel, You</span></header>
<div class=badge>317 unread</div><ol>{items}</ol></body></html>"""
COLORS = {"Jun Hao": "#53BDEB", "Priya": "#FF72A1", "Farid": "#A5B337", "Mei Ling": "#FFD279", "Daniel": "#7F66FF"}


def wall_html(messages) -> str:
    items = []
    for m in messages:
        if m["is_system"]:
            continue
        txt = "🎤 Voice note 0:%02d" % (8 + m["id"] % 40) if m["is_voice_note"] else ("📷 Photo" if m["is_media"] else m["text"])
        items.append(f'<li><i style="color:{COLORS.get(m["sender"], "#53BDEB")}">{html.escape(m["sender"] or "")}</i>'
                     f'{html.escape(txt)}<small>{m["timestamp"][11:16]}</small></li>')
    return WALL.format(items="".join(items))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--media", required=True)
    ap.add_argument("--out", default=str(ROOT / "docs" / "rejoin-demo.mp4"))
    a = ap.parse_args()
    media = Path(a.media)
    segs = {s["id"]: s for s in json.loads((media / "segments.json").read_text())}
    rec_dir = media / "rec"
    shutil.rmtree(rec_dir, ignore_errors=True)
    timeline: list[tuple[str, float]] = []

    import requests
    demo = requests.post(URL + "api/demo", json={"engine": "rules"}, timeout=30).json()

    with sync_playwright() as p:
        b = p.chromium.launch()
        ctx = b.new_context(viewport={"width": W, "height": H}, record_video_dir=str(rec_dir),
                            record_video_size={"width": W, "height": H})
        ctx.add_init_script(CAPTION_JS)
        pg = ctx.new_page()
        t0 = time.monotonic()

        def caption(text):
            pg.evaluate(CAPTION_JS)
            pg.evaluate("t => { document.getElementById('rj-cap').textContent = t; }", text)

        def segment(sid, actions):
            start = time.monotonic()
            timeline.append((sid, start - t0))
            caption(segs[sid]["text"])
            actions()
            remaining = segs[sid]["dur"] + 0.5 - (time.monotonic() - start)
            if remaining > 0:
                pg.wait_for_timeout(remaining * 1000)

        def smooth_scroll(to_px, ms):
            pg.evaluate("""([to, ms]) => new Promise(r => { const s = scrollY, t0 = performance.now();
              const f = (t) => { const k = Math.min(1, (t - t0) / ms); scrollTo(0, s + (to - s) * k); k < 1 ? requestAnimationFrame(f) : r(); };
              requestAnimationFrame(f); })""", [to_px, ms])

        def scroll_to(sel, ms=900, offset=90):
            y = pg.evaluate("([s, o]) => document.querySelector(s).getBoundingClientRect().top + scrollY - o", [sel, offset])
            smooth_scroll(y, ms)

        # 1. Title card
        pg.set_content(CARD.format(body='<div class=mark>Rejoin</div><h1>Missed the group chat?<br>Get only the parts that need you.</h1>'
                                        '<p class=hand>Aina was away for 5 days.</p>'))
        pg.wait_for_timeout(600)
        segment("intro", lambda: None)

        # 2. The wall of messages
        pg.set_content(wall_html(demo["messages"]))
        segment("wall", lambda: smooth_scroll(pg.evaluate("document.body.scrollHeight") - H, int(segs["wall"]["dur"] * 1000)))

        # 3. Home page
        pg.goto(URL)
        pg.wait_for_load_state("networkidle")

        def home():
            pg.wait_for_timeout(900)
            pg.click("#me")
            pg.keyboard.type("Aina, Ain", delay=110)
            pg.wait_for_timeout(500)
            scroll_to("#slip", 900, 40)
            pg.wait_for_timeout(700)
            pg.click(".howto summary")
            pg.wait_for_timeout(2200)
            pg.click(".howto summary")
            scroll_to(".slip-actions", 800, 380)
        segment("home", home)

        # 4. Filled slip
        def slip():
            pg.click("#demo")
            pg.wait_for_selector("#results:not([hidden])")
        segment("slip", slip)

        # 5. Asked of you
        def asks():
            scroll_to("#h-asks", 900, 30)
            pg.wait_for_timeout(1800)
            pg.locator("#asks .why > .why-btn").nth(2).click()
            pg.wait_for_timeout(500)
            scroll_to("#asks li:nth-child(3)", 700, 60)
            pg.wait_for_timeout(4200)
            pg.locator("#asks .item-main input").nth(1).check()
        segment("asks", asks)

        # 6. Questions, decisions, dates
        def rest():
            scroll_to("#h-questions", 900, 30)
            pg.wait_for_timeout(2600)
            scroll_to("#h-decisions", 900, 30)
            pg.wait_for_timeout(3600)
            scroll_to("#h-dates", 900, 30)
            pg.wait_for_timeout(1500)
            pg.hover("#ics")
        segment("rest", rest)

        # 7. Plain language and comfort
        def comfort():
            scroll_to("#results .toolbar", 900, 200)
            pg.wait_for_timeout(500)
            pg.click("#plain-toggle")
            pg.wait_for_timeout(300)
            scroll_to("#h-asks", 700, 30)
            pg.wait_for_timeout(2600)
            pg.hover("#read-all")
            smooth_scroll(0, 900)
            pg.wait_for_timeout(600)
            pg.click(".comfort-toggle")
            pg.wait_for_timeout(700)
            pg.check('[data-pref="contrast"]')
            pg.wait_for_timeout(700)
            pg.check('[data-pref="large"]')
            pg.wait_for_timeout(700)
            pg.check('[data-pref="spacing"]')
            pg.wait_for_timeout(500)
            scroll_to("#results", 900, 0)
            pg.wait_for_timeout(2600)
            for k in ("spacing", "large", "contrast"):
                pg.uncheck(f'[data-pref="{k}"]')
            pg.click("#plain-toggle")
            pg.click(".comfort-toggle")
        segment("comfort", comfort)

        # 8. Reply and how it was made
        def reply():
            scroll_to("#h-reply", 900, 30)
            pg.wait_for_timeout(3200)
            pg.click("#how summary")
            scroll_to("#how", 800, 30)
        segment("reply", reply)

        # 9. Outro card
        def outro():
            pg.set_content(CARD.format(body=(
                '<div class=mark>Rejoin</div><h1>Get only the parts that need you.</h1><ul>'
                '<li>32 tests, 0 axe-core violations across 17 screens</li>'
                '<li>Every item linked to its source message</li>'
                '<li>Runs in your browser: your chat is never uploaded</li></ul>'
                '<p>shermaineyap.github.io/Taskforge-Hack</p>')))
            pg.evaluate(CAPTION_JS)
            caption(segs["outro"]["text"])
        segment("outro", outro)
        pg.wait_for_timeout(1200)
        total = time.monotonic() - t0
        video_path = pg.video.path()
        ctx.close()
        b.close()

    # Audio track: each narration WAV placed at its segment start.
    inputs, filters = [], []
    for i, (sid, start) in enumerate(timeline):
        inputs += ["-i", str(media / f"{sid}.wav")]
        ms = int(start * 1000) + 250
        filters.append(f"[{i + 1}:a]adelay={ms}|{ms}[a{i}]")
    mix = "".join(f"[a{i}]" for i in range(len(timeline)))
    filters.append(f"{mix}amix=inputs={len(timeline)}:normalize=0,apad[aout]")
    out = Path(a.out)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(video_path), *inputs,
                    "-filter_complex", ";".join(filters), "-map", "0:v", "-map", "[aout]",
                    "-t", f"{total:.2f}", "-c:v", "libx264", "-preset", "slow", "-crf", "23", "-pix_fmt", "yuv420p",
                    "-r", "30", "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", str(out)], check=True)

    # Captions file (also burned in on screen).
    def ts(x):
        h, r = divmod(x, 3600); m, s = divmod(r, 60)
        return f"{int(h):02d}:{int(m):02d}:{int(s):02d},{int((s % 1) * 1000):03d}"
    srt = []
    for i, (sid, start) in enumerate(timeline, 1):
        srt.append(f"{i}\n{ts(start + .25)} --> {ts(start + .25 + segs[sid]['dur'])}\n{segs[sid]['text']}\n")
    out.with_suffix(".srt").write_text("\n".join(srt), encoding="utf-8")
    print(f"wrote {out} ({total:.1f}s)")


if __name__ == "__main__":
    main()
