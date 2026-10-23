"""Automated accessibility scan (axe-core) across Rejoin's states.

Needs the app on :5000, Playwright with Chromium, and axe.min.js:
    npm i axe-core   (or pass --axe path/to/axe.min.js)
    python scripts/a11y_check.py --axe node_modules/axe-core/axe.min.js

Scans WCAG 2.0/2.1/2.2 A + AA rules. Automated scans catch roughly a third
of real issues; they do not replace testing with disabled people.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from playwright.sync_api import sync_playwright

URL = "http://127.0.0.1:5000/"
TAGS = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"]


def scan(page, axe_src: str) -> dict:
    page.add_script_tag(content=axe_src)
    return page.evaluate("tags => axe.run(document, {runOnly: {type: 'tag', values: tags}})", TAGS)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--axe", default="node_modules/axe-core/axe.min.js")
    ap.add_argument("--out", default=str(Path(__file__).resolve().parents[1] / "docs" / "a11y-report.json"))
    a = ap.parse_args()
    axe_src = Path(a.axe).read_text(encoding="utf-8")

    states = []
    with sync_playwright() as p:
        b = p.chromium.launch()
        for scheme in ("light", "dark"):
            for width, label in ((1280, "desktop"), (375, "mobile")):
                pg = b.new_page(viewport={"width": width, "height": 900}, color_scheme=scheme)
                pg.goto(URL)
                pg.wait_for_load_state("networkidle")
                states.append((f"{label}/{scheme}/start", scan(pg, axe_src)))
                pg.click(".comfort-toggle")
                states.append((f"{label}/{scheme}/comfort-panel", scan(pg, axe_src)))
                pg.click("#demo")
                pg.wait_for_selector("#results:not([hidden])")
                pg.wait_for_timeout(800)
                pg.locator("#asks .why-btn").first.click()
                pg.evaluate("document.querySelector('#chatlog').open = true; document.querySelector('#how').open = true")
                states.append((f"{label}/{scheme}/results-expanded", scan(pg, axe_src)))
                pg.click("#plain-toggle")
                states.append((f"{label}/{scheme}/plain-language", scan(pg, axe_src)))
                pg.close()
        # High-contrast + large text preferences
        pg = b.new_page(viewport={"width": 1280, "height": 900})
        pg.goto(URL)
        pg.evaluate("localStorage.setItem('rejoin.prefs', JSON.stringify({contrast:true, large:true, readable:true, spacing:true}))")
        pg.reload()
        pg.click("#demo")
        pg.wait_for_selector("#results:not([hidden])")
        pg.wait_for_timeout(800)
        states.append(("desktop/high-contrast-large-readable/results", scan(pg, axe_src)))

        # Keyboard-only path: Tab to the demo button and press Enter.
        kb = b.new_page(viewport={"width": 1280, "height": 900})
        kb.goto(URL)
        reached = False
        for _ in range(40):
            kb.keyboard.press("Tab")
            if kb.evaluate("document.activeElement && document.activeElement.id") == "demo":
                reached = True
                break
        kb.keyboard.press("Enter")
        kb.wait_for_selector("#results:not([hidden])")
        focus_moved = kb.evaluate("document.activeElement.id") == "results"
        live = kb.evaluate("document.getElementById('status').textContent")
        b.close()

    summary = []
    total_serious = 0
    for name, res in states:
        v = res["violations"]
        serious = [x for x in v if x["impact"] in ("serious", "critical")]
        total_serious += len(serious)
        summary.append({"state": name, "passes": len(res["passes"]), "violations": len(v),
                        "serious_or_critical": len(serious),
                        "issues": [{"id": x["id"], "impact": x["impact"], "nodes": len(x["nodes"]), "help": x["help"]} for x in v]})
    report = {
        "axe_version": states[0][1]["testEngine"]["version"],
        "tags": TAGS,
        "states_scanned": len(states),
        "serious_or_critical_total": total_serious,
        "keyboard": {"demo_reachable_by_tab": reached, "focus_moves_to_results": focus_moved, "status_announced": live},
        "states": summary,
    }
    Path(a.out).write_text(json.dumps(report, indent=2))
    print(json.dumps({k: report[k] for k in ("axe_version", "states_scanned", "serious_or_critical_total", "keyboard")}, indent=2))
    for s in summary:
        if s["violations"]:
            print(s["state"], s["issues"])


if __name__ == "__main__":
    main()
