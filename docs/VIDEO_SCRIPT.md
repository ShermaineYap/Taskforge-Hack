# Demo video script (2 min 30 s)

Record the screen at 1080p with the browser zoomed to 125%. Speak slowly; captions matter for this project, so upload an .srt or use YouTube auto-captions and correct them. Turn on **Reading comfort → No motion** only if the stamp animation distracts.

Before recording: use the live demo (https://shermaineyap.github.io/Taskforge-Hack/) or `python app.py` with `GROQ_API_KEY` set if you have one (the AI wording reads more naturally), a WhatsApp chat open on your phone or in WhatsApp Web scrolled to an unread badge (any harmless chat, or skip that shot), and the page reset (reload, clear checkboxes).

| Time | On screen | Say |
| --- | --- | --- |
| 0:00–0:15 | WhatsApp with a big unread badge (or `demo/aina_fyp_chat.txt` open in a text editor, scrolled fast). | "This is Aina. She muted her final-year project group for one week of exams. She came back to 317 messages and 7 voice notes. Somewhere in there, she was given work." |
| 0:15–0:30 | Keep scrolling the raw chat. | "For people with ADHD, dyslexia, or anxiety, that wall is the barrier, not the work. And if you're deaf or hard of hearing, anything said in a voice note is just gone." |
| 0:30–0:45 | Rejoin home page. Type "Aina, Ain". Show the "How do I export" disclosure briefly. Click **Try it with Aina's chat**. | "Rejoin reads a WhatsApp export. You add your name and nicknames, and it catches you up on everything since you last spoke." |
| 0:45–1:00 | The filled slip and stamp. | "317 messages, about five minutes of reading plus scrolling, become seven things that need her, readable in about a minute." |
| 1:00–1:25 | Asked of you. Open **Show the message** on the room booking, point at "From a voice note". Tick the Figma item. | "Here's what was asked of her. This one was only ever said in a voice note. Rejoin transcribed it. Every item shows the exact message it came from, so she can trust it." |
| 1:25–1:40 | Scroll to Waiting for your answer, Decided, Dates. Click **Add these dates to my calendar**. | "Questions waiting for her, decisions made while she was away, like the switch to IEEE referencing, and dates she can add to her calendar in one click." |
| 1:40–2:00 | Click **Plain language**, then **Read it to me** (let it read one item). Open **Reading comfort**, switch on high contrast and larger text. | "Plain language rewrites each item in short, simple words. It can read everything aloud. And the reading-comfort settings change the type, spacing and contrast." |
| 2:00–2:15 | Copy the draft reply. Open **How this was made**. | "There's a reply to rejoin the group with. And under the hood: phone numbers are masked first, and the AI only proposes items. If an item doesn't point at a real message, Rejoin throws it away, and dates are worked out by code, not the model." |
| 2:15–2:30 | README evaluation table or terminal running `pytest` and `evaluate.py --set heldout`. | "32 tests, zero automated accessibility violations across 17 screens, and an honest evaluation on a chat we never tuned on. Rejoin: get only the parts that need you." |

Tips
- Keep it under 3 minutes. Judges skim.
- Don't show a real group chat with other people's messages unless they agree.
- If the AI call is slow on camera, record with the offline engine; it's instant.
- The counts in the script (317 messages, 7 things) are what the offline engine shows. The AI engine may group items differently; say what your screen shows.
