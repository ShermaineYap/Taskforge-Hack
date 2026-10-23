# Evaluation

## What is measured

For each labelled chat, Rejoin runs over the catch-up window ("since my last message") and every extracted item is compared with hand-written labels.

- An item is **correct** when one of the messages it cites is the labelled message for that category.
- **Precision** = correct items / all items emitted in that category.
- **Recall** = labelled messages found / all labelled messages.
- Messages labelled `neutral` (for example "Aina are u alive, pls reply") are not scored either way.

Scoring code: [`scripts/evaluate.py`](../scripts/evaluate.py). Raw reports: `eval-rules-demo.json`, `eval-rules-heldout.json`.

## Labelling guide

| Category | Label it when… |
| --- | --- |
| `asked_of_you` | Someone asks or assigns the person a task (by name, nickname, @mention, a task list, or a voice note). |
| `open_questions` | A question the person still needs to answer, including group "everyone confirm" requests. |
| `decisions` | The group settled or changed something that affects the person's work (topic, format, dates, venue, tools, rules). |
| `deadlines` | A concrete date or time attached to a task, meeting or submission that matters to the person. |

## Results (offline rule engine)

| Chat | Messages in window | Precision | Recall | F1 |
| --- | --- | --- | --- | --- |
| Aina's FYP group (`demo/`) | 317 | 0.889 | 1.000 | 0.941 |
| Kumar's café team (`demo/heldout/`) | 35 | 0.875 | 0.538 | 0.667 |

Per category, held-out chat:

| Category | Labelled | Found | False positives |
| --- | --- | --- | --- |
| Asked of you | 2 | 2 | 1 |
| Waiting for answer | 2 | 1 | 0 |
| Decisions | 4 | 1 | 0 |
| Dates | 5 | 3 | 0 |

## Honest notes

- **The demo chat was used while writing the rules.** Its score shows the rules work on that chat, not that they generalise. The held-out chat was written after the rules were frozen, in a different format (iOS), domain (café shifts) and with Malay phrasing (*boleh tak*). The rules were not changed after seeing its score.
- **One label correction.** After the first scoring run of the held-out chat, two `deadlines` labels were added (the Sunday shift and the Saturday restock), because the labelling guide above says dated tasks for the person count and they had been missed. Before the correction the held-out F1 was 0.526.
- **Where rules fail:** decisions announced without a cue word ("FYI the espresso machine is getting serviced Thursday", "New rule from HQ…"). This is the main reason the AI reader is the default when a key is set.
- **The disputed item:** "Kumar did you finish the allergen training module? HQ says due 18 Oct" is labelled as a question; the rules call it an ask. Either reading is defensible; it is scored as one false positive and one miss.
- Both chats are fictional and written by the author. This is a sanity check, not a benchmark.

## AI engine

Run with a Groq key to score the AI reader on the same labels:

```bash
export GROQ_API_KEY=...
python scripts/evaluate.py --set demo --engine ai --out docs/eval-ai-demo.json
python scripts/evaluate.py --set heldout --engine ai --out docs/eval-ai-heldout.json
```

AI results: _run the commands above and paste the overall precision / recall / F1 here._
