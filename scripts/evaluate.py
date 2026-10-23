"""Score an engine against the labelled demo chat.

    python scripts/evaluate.py            # offline rule engine
    python scripts/evaluate.py --engine ai  # needs GROQ_API_KEY

An extracted item counts as correct when one of its cited source messages
is the labelled message. 'neutral' labels are ignored (neither TP nor FP).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from engine import analyze  # noqa: E402

CATS = ["asked_of_you", "decisions", "open_questions", "deadlines"]


SETS = {
    "demo": (ROOT / "demo", "aina_fyp_chat.txt"),
    "heldout": (ROOT / "demo" / "heldout", "cafe_shift_chat.txt"),
}


def run(engine: str, which: str = "demo") -> dict:
    folder, chat = SETS[which]
    exp = json.loads((folder / "expected.json").read_text(encoding="utf-8"))
    vt = folder / "voice_transcripts.json"
    out = analyze(
        (folder / chat).read_text(encoding="utf-8"),
        exp["me"], exp["since"], engine,
        demo_transcripts=json.loads(vt.read_text(encoding="utf-8")) if vt.exists() else None,
    )
    msgs = {m["id"]: m for m in out["messages"]}

    def ids_for(match: str) -> set[int]:
        return {i for i, m in msgs.items() if match in m["text"] or match == (m.get("attachment") or "")}

    neutral = set().union(*[ids_for(l["match"]) for l in exp["labels"] if l["category"] == "neutral"] or [set()])
    report = {"set": which, "engine": out["engine"], "model": out["model"], "categories": {}}
    tot_tp = tot_fp = tot_fn = 0
    for cat in CATS:
        gold = [ids_for(l["match"]) for l in exp["labels"] if l["category"] == cat]
        items = out["result"][cat]
        tp_gold = sum(1 for g in gold if any(set(it["sources"]) & g for it in items))
        fp = sum(1 for it in items
                 if not any(set(it["sources"]) & g for g in gold) and not set(it["sources"]) <= neutral)
        fn = len(gold) - tp_gold
        tp = len(gold) - fn
        p = tp / (tp + fp) if tp + fp else 1.0
        r = tp / len(gold) if gold else 1.0
        report["categories"][cat] = {"gold": len(gold), "found": tp, "false_positives": fp,
                                     "precision": round(p, 3), "recall": round(r, 3)}
        tot_tp += tp; tot_fp += fp; tot_fn += fn
    P = tot_tp / (tot_tp + tot_fp) if tot_tp + tot_fp else 1.0
    R = tot_tp / (tot_tp + tot_fn) if tot_tp + tot_fn else 1.0
    report["overall"] = {"precision": round(P, 3), "recall": round(R, 3),
                         "f1": round(2 * P * R / (P + R), 3) if P + R else 0.0}
    report["stats"] = out["stats"]
    return report


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--engine", default="rules", choices=["rules", "ai"])
    ap.add_argument("--set", default="demo", choices=list(SETS))
    ap.add_argument("--out", help="write JSON report here")
    a = ap.parse_args()
    rep = run(a.engine, a.set)
    print(json.dumps(rep, indent=2))
    if a.out:
        Path(a.out).write_text(json.dumps(rep, indent=2))
