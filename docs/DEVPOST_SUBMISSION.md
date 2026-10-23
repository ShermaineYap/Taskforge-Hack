# Devpost submission: Rejoin

Copy each section into the matching Devpost field.

---

**Project name:** Rejoin

**Tagline (max 200 chars):** Missed the group chat? Rejoin turns a WhatsApp export into the few things that need you, each linked to the message it came from, with voice notes transcribed and reading-comfort controls built in.

**Built with:** python, flask, javascript, html5, css3, pyodide, groq, llama-3.3, whisper, github-pages, playwright, axe-core, pytest

**Try it out:**
- Live demo: https://shermaineyap.github.io/Taskforge-Hack/
- Code: https://github.com/ShermaineYap/Taskforge-Hack
- Demo video (also in the repo): https://github.com/ShermaineYap/Taskforge-Hack/blob/main/docs/rejoin-demo.mp4

---

## Inspiration

At university, group work runs on WhatsApp. Step away for a few days of exams or work shifts and you come back to hundreds of messages. Somewhere in there you were given a task, someone asked you a question, and the plan changed.

For a lot of people, that wall of unread messages is the real barrier, not the work itself. It's harder with ADHD or anxiety (easy to avoid, hard to start), with dyslexia or when reading in a second language (slow to decode), and if you're deaf or hard of hearing (anything said only in a voice note is gone). WhatsApp has no "what did I miss that involves me?" view, so we built one.

## The user and the barrier

**User:** Aina, a final-year student who muted her six-person project group during a week of exams.
**Barrier:** re-entering a long group chat is a reading and working-memory task that leaves people behind.
**The change:** 317 messages and 7 voice notes (about 5 minutes of reading plus scrolling) become 7 things that need her, readable in about a minute, every one traceable to its source message.

## What it does

You export a chat from WhatsApp (a built-in feature, so no account linking), drop it into Rejoin with your name and nicknames, and get a handoff for the time since you last spoke:

- **Asked of you**: who asked, when, and the due date, with a checkbox to tick it off.
- **Waiting for your answer**: direct questions and "everyone please confirm" requests.
- **Decided while you were away**: topic, format, date and tool changes.
- **Dates**: exportable to your calendar as an .ics file.
- **A message to rejoin with**: a friendly reply ready to paste into the group.

Every item has **Show the message**, which reveals the original text, and **Find it in the full chat**, which jumps to it in context. Voice notes in a "with media" export are transcribed, so a task given only by voice shows up like any other.

Accessibility is built into the core flow: Atkinson Hyperlegible type, larger text, extra spacing, high contrast, dark mode, a plain-language mode, read-aloud with adjustable speed, reduced motion, full keyboard use, and screen-reader announcements.

## How we built it

- **Parser** for real WhatsApp exports: Android and iOS, 12- and 24-hour clocks, day-first or month-first dates (detected from the data), multi-line messages, attachments, and the invisible characters WhatsApp inserts.
- **Redaction** before any reading: phone numbers and e-mails masked, unsaved contacts renamed.
- **Two readers.** An AI reader (Llama 3.3 70B on Groq, strict JSON output) and an offline rule engine (request cues, @mentions, task-split lists, decision cues, some Malay phrasing like *boleh tak*). If there's no key or the API fails, the offline engine takes over, so it never breaks mid-demo.
- **The model doesn't get the last word.** Every AI item must cite message IDs that exist in the window or it's dropped. Dates like "tmr night" or "Monday 2pm" are resolved by our code from the timestamp of the cited message, not by the model. Asks whose source never names you are flagged "Check: not named directly".
- **Runs two ways.** As a Flask app (with the AI reader), and as a static GitHub Pages site where the same Python engine runs in the browser through Pyodide, so a chat is never uploaded.
- **Front end:** one page with vanilla JavaScript. All chat text is inserted with `textContent`, never `innerHTML`, because chat content is untrusted.
- **Verification:** 32 pytest tests; an evaluation script against two hand-labelled chats; an axe-core scan of 17 UI states via Playwright.

## Results

- Offline engine on the demo chat: precision 0.89, recall 1.00, F1 0.94.
- Offline engine on a **held-out** chat (different format, domain and language mix, not used for tuning): F1 0.67. It finds every ask but misses decisions announced without a cue word. That gap is why the AI reader with grounding checks is the default.
- Accessibility: 0 axe-core violations (WCAG 2.0–2.2 A/AA rules) across 17 states, light and dark, desktop and mobile. The keyboard-only path is tested end to end.

## Challenges we ran into

- **Dates.** "Fri 30 Oct" first resolved to the nearest Friday instead of the 30th; "tomorrow" has to mean the day after the message was sent, not after today. We moved date logic out of the model entirely and test it directly.
- **Trusting AI output.** A summary that sounds right but invents a task is worse than no summary. Requiring a source for every item, and checking it in code, was the fix.
- **Being honest about accuracy.** The rules scored 0.94 on the chat we built them with, and 0.67 on one they'd never seen. We report both.

## Accomplishments that we're proud of

- A task given only in a voice note shows up in the handoff with a "From a voice note" tag.
- Every item is traceable to its source, in one click.
- Zero automated accessibility violations across every state we could reach, including high-contrast and large-text modes.

## What we learned

- Accessibility features work best in the main flow, not hidden in settings: the plain-language and read-aloud buttons sit next to the results.
- Evaluate on data you didn't build with. The held-out score changed how we describe the offline engine.
- Pair the model with simple, testable code for anything that has to be exact (IDs, dates).

## Limitations

- WhatsApp exports only (not Telegram, Discord or Slack).
- The offline engine misses decisions without cue words and knows only a few Malay phrases.
- Offline plain-language mode is a light rewrite; the AI mode writes proper plain language.
- Voice-note transcription needs a "with media" export and an API key.
- In AI mode, the masked catch-up text is sent to Groq. Offline mode sends nothing.
- Evaluated on two fictional chats; not yet tested with disabled users.

## What's next for Rejoin

- Test with students who have ADHD, dyslexia, or who are deaf or hard of hearing, and change what they tell us to change.
- Telegram and Discord exports.
- A share-sheet shortcut so "Export chat → Rejoin" is one step on a phone.
- Run the reader on-device so no text has to leave the phone.

## AI assistance and prior work

Built during the Taskforge period (17–24 Oct 2026). Claude (Anthropic) was used for research, most of the code, tests, demo data and writing, with Shermaine directing, reviewing, running and editing. At runtime Rejoin optionally uses Llama 3.3 70B and Whisper via Groq. Open-source libraries: Flask, Requests, pytest, Playwright, axe-core. All demo chats and names are fictional. The demo video's narration is a synthetic voice (Piper TTS). Full disclosure: `AI_ASSISTANCE.md` in the repo.
