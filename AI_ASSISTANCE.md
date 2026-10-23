# AI assistance and prior work

Taskforge asks entrants to identify AI assistance and pre-existing work. Here is all of it.

## AI assistance

- **Claude (Anthropic)** was used during the hackathon period to research the hackathon brief and existing tools, choose the project direction, and write most of the code, tests, the demo chats and the documentation, with Shermaine directing, reviewing, running and editing the work.
- **At runtime**, Rejoin optionally calls **Llama 3.3 70B** (via Groq) to read the chat, and **Whisper** (via Groq) to transcribe voice notes. The model output is checked by Rejoin's own code before it's shown (see README, "Why the model doesn't get the last word").

## Pre-existing work

- None of Rejoin's code existed before 17 October 2026.
- Open-source libraries: Flask, Requests, Pyodide, python-dotenv, pytest, Playwright, axe-core. Fonts: Atkinson Hyperlegible and Caveat (SIL Open Font License).
- Similar products exist (general WhatsApp chat summarisers such as CatchMeUp and ThreadRecap). Rejoin differs in focus: it extracts only what involves one named person, links every item to its source message, verifies AI output against the chat, and is designed around accessibility needs.

## Data

All chats, names and voice-note transcripts in `demo/` are fictional and were written for this project. No real person's messages were used.
