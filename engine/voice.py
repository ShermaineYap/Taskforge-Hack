"""Voice-note transcription and export-archive handling.

WhatsApp "Export chat > Attach media" produces a .zip containing the chat
.txt and the audio files (.opus). Voice notes are transcribed with Whisper
on Groq so people who are deaf or hard of hearing, or who simply can't
play audio right now, get the content as text.
"""
from __future__ import annotations

import io
import os
import zipfile


WHISPER_URL = "https://api.groq.com/openai/v1/audio/transcriptions"
WHISPER_MODEL = os.environ.get("REJOIN_WHISPER_MODEL", "whisper-large-v3-turbo")
MAX_AUDIO_BYTES = 20 * 1024 * 1024
AUDIO_EXT = (".opus", ".ogg", ".m4a", ".mp3", ".aac", ".wav")


def read_upload(filename: str, data: bytes) -> tuple[str, dict[str, bytes]]:
    """Return (chat_text, audio_files). Accepts .txt or WhatsApp .zip export."""
    if filename.lower().endswith(".zip") or data[:2] == b"PK":
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            names = zf.namelist()
            txts = [n for n in names if n.lower().endswith(".txt")]
            if not txts:
                raise ValueError("That .zip has no chat .txt file inside. Export the chat again from WhatsApp.")
            chat_name = next((n for n in txts if "chat" in n.lower()), txts[0])
            chat = zf.read(chat_name).decode("utf-8", errors="replace")
            audio = {}
            for n in names:
                if n.lower().endswith(AUDIO_EXT):
                    info = zf.getinfo(n)
                    if info.file_size <= MAX_AUDIO_BYTES:
                        audio[os.path.basename(n)] = zf.read(n)
            return chat, audio
    return data.decode("utf-8", errors="replace"), {}


def transcribe(name: str, data: bytes, timeout: int = 60) -> str:
    key = os.environ["GROQ_API_KEY"]
    upload_name = name[:-5] + ".ogg" if name.lower().endswith(".opus") else name  # opus is ogg-contained
    import requests  # imported lazily so the engine also runs in the browser (Pyodide)

    resp = requests.post(
        WHISPER_URL,
        headers={"Authorization": f"Bearer {key}"},
        files={"file": (upload_name, data)},
        data={"model": WHISPER_MODEL, "response_format": "json"},
        timeout=timeout,
    )
    resp.raise_for_status()
    return resp.json().get("text", "").strip()


def attach_transcripts(messages, audio: dict[str, bytes], demo_transcripts: dict[str, str] | None = None) -> dict:
    """Fill msg.transcript for voice notes. Returns a report for the UI."""
    report = {"voice_notes": 0, "transcribed": 0, "failed": 0, "demo": 0}
    can_whisper = bool(os.environ.get("GROQ_API_KEY"))
    for msg in messages:
        if not msg.is_voice_note:
            continue
        report["voice_notes"] += 1
        name = msg.attachment or ""
        if demo_transcripts and name in demo_transcripts:
            msg.transcript, msg.transcript_source = demo_transcripts[name], "demo"
            report["demo"] += 1
        elif name in audio and can_whisper:
            try:
                msg.transcript, msg.transcript_source = transcribe(name, audio[name]), "whisper"
                report["transcribed"] += 1
            except Exception:  # network, quota, bad audio: keep going
                report["failed"] += 1
    return report
