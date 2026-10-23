"""Build the static GitHub Pages site into ./site.

The page is the same template and front end as the Flask app. Instead of
calling the API, it runs the offline engine in the visitor's browser with
Pyodide, so chats are never uploaded anywhere.

    python scripts/build_site.py [--pyodide URL]
"""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from flask import render_template  # noqa: E402

from app import app  # noqa: E402
from engine import SINCE_OPTIONS  # noqa: E402

PYODIDE = "https://cdn.jsdelivr.net/pyodide/v0.27.2/full/"


def build(out: Path, pyodide: str) -> None:
    if out.exists():
        shutil.rmtree(out)
    (out / "engine").mkdir(parents=True)
    (out / "demo").mkdir()
    with app.test_request_context("/"):
        html = render_template("index.html", since_options=SINCE_OPTIONS, ai_available=False,
                               static_site=True, pyodide_url=pyodide)
    html = html.replace('"/static/', '"static/')
    (out / "index.html").write_text(html, encoding="utf-8")
    shutil.copytree(ROOT / "static", out / "static")
    for f in (ROOT / "engine").glob("*.py"):
        shutil.copy(f, out / "engine" / f.name)
    for f in ("aina_fyp_chat.txt", "voice_transcripts.json"):
        shutil.copy(ROOT / "demo" / f, out / "demo" / f)
    (out / ".nojekyll").write_text("")
    print(f"built {out}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "site"))
    ap.add_argument("--pyodide", default=PYODIDE)
    a = ap.parse_args()
    build(Path(a.out), a.pyodide)
