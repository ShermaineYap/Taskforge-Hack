/* Rejoin front end. All chat content is untrusted: it is only ever set with
   textContent, never innerHTML. */
(() => {
  "use strict";
  const $ = (s, r = document) => r.querySelector(s);
  const el = (tag, attrs = {}, ...kids) => {
    const n = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs)) {
      if (v === null || v === undefined || v === false) continue;
      if (k === "class") n.className = v;
      else if (k === "text") n.textContent = v;
      else if (k.startsWith("on")) n.addEventListener(k.slice(2), v);
      else n.setAttribute(k, v === true ? "" : v);
    }
    for (const kid of kids) if (kid) n.append(kid);
    return n;
  };
  const root = document.documentElement;
  const status = $("#status");
  const errBox = $("#error");
  let data = null;
  let plain = false;

  /* ---------- Preferences (kept on this device) ---------- */
  const PREF_KEY = "rejoin.prefs";
  const loadPrefs = () => { try { return JSON.parse(localStorage.getItem(PREF_KEY)) || {}; } catch { return {}; } };
  const savePrefs = (p) => { try { localStorage.setItem(PREF_KEY, JSON.stringify(p)); } catch { /* private mode */ } };
  const prefs = loadPrefs();
  const applyPrefs = () => {
    for (const box of document.querySelectorAll("[data-pref]")) {
      const key = box.dataset.pref;
      box.checked = !!prefs[key];
      if (key === "plain") continue;
      root.classList.toggle("pref-" + key, !!prefs[key]);
    }
    setPlain(!!prefs.plain, false);
    if (prefs.rate) { $("#rate").value = prefs.rate; }
    $("#rate-out").textContent = Number($("#rate").value).toFixed(1) + "×";
  };
  document.querySelectorAll("[data-pref]").forEach((box) => box.addEventListener("change", () => {
    prefs[box.dataset.pref] = box.checked; savePrefs(prefs); applyPrefs();
  }));
  $("#rate").addEventListener("input", (e) => { prefs.rate = e.target.value; savePrefs(prefs); applyPrefs(); });

  const comfortBtn = $(".comfort-toggle");
  comfortBtn.addEventListener("click", () => {
    const open = comfortBtn.getAttribute("aria-expanded") === "true";
    comfortBtn.setAttribute("aria-expanded", String(!open));
    $("#comfort").hidden = open;
    if (!open) $("#comfort input").focus();
  });
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && !$("#comfort").hidden) { comfortBtn.click(); comfortBtn.focus(); }
  });

  function setPlain(on, rerender = true) {
    plain = on;
    $("#plain-toggle").setAttribute("aria-pressed", String(on));
    const box = document.querySelector('[data-pref="plain"]');
    if (box) box.checked = on;
    if (rerender && data) renderLists();
  }
  $("#plain-toggle").addEventListener("click", () => {
    prefs.plain = !plain; savePrefs(prefs); setPlain(prefs.plain);
    say(plain ? "Plain language on." : "Plain language off.");
  });

  /* ---------- Helpers ---------- */
  const say = (msg) => { status.textContent = ""; requestAnimationFrame(() => { status.textContent = msg; }); };
  const showError = (msg) => { errBox.hidden = !msg; errBox.textContent = msg || ""; };
  const fmtTime = (iso) => new Date(iso).toLocaleString(undefined, { weekday: "short", day: "numeric", month: "short", hour: "numeric", minute: "2-digit" });
  const cap = (t) => (t ? t[0].toUpperCase() + t.slice(1) : t);
  const minutes = (s) => s < 60 ? `${Math.max(s, 5)} sec` : `${Math.round(s / 60)} min`;
  const msgById = (id) => data.messages.find((m) => m.id === id);
  const doneKey = () => "rejoin.done." + (data ? data.chat_end + data.me.join() : "");
  const loadDone = () => { try { return new Set(JSON.parse(localStorage.getItem(doneKey())) || []); } catch { return new Set(); } };
  const saveDone = (set) => { try { localStorage.setItem(doneKey(), JSON.stringify([...set])); } catch {} };

  /* ---------- Back ends ----------
     Server mode: the Flask API. Static mode (GitHub Pages): the same Python
     engine runs in the browser with Pyodide, so nothing is uploaded. */
  const STATIC = window.REJOIN_STATIC || null;
  const jsonOrThrow = async (res) => {
    const body = await res.json().catch(() => ({ error: "The server sent back something unreadable. Try again." }));
    if (!res.ok || body.error) throw new Error(body.error || `Request failed (${res.status}).`);
    return body;
  };
  const serverBackend = {
    analyze: async ({ me, file, since, engine }) => {
      const fd = new FormData();
      fd.append("me", me); fd.append("chat", file); fd.append("since", since); fd.append("engine", engine);
      return jsonOrThrow(await fetch("/api/analyze", { method: "POST", body: fd }));
    },
    demo: async ({ since, engine }) => jsonOrThrow(await fetch("/api/demo", {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ engine, since }),
    })),
    ics: async (deadlines) => {
      const res = await fetch("/api/ics", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ deadlines }) });
      if (!res.ok) throw new Error("Couldn't make the calendar file.");
      return res.blob();
    },
  };

  const PY_HELPERS = `
import sys, json
sys.path.insert(0, "/rejoin")
from engine import analyze
from engine.voice import read_upload
from engine.ics import build_ics

def rejoin_run(name, data, me, since, transcripts):
    try:
        raw = data.to_bytes() if hasattr(data, "to_bytes") else bytes(data)
        chat, audio = read_upload(name, raw)
        tr = json.loads(transcripts) if transcripts else None
        out = analyze(chat, me.split(","), since, "rules", audio=audio, demo_transcripts=tr)
        out["warnings"] = [w for w in out["warnings"] if "GROQ" not in w]
        return json.dumps(out)
    except ValueError as exc:
        return json.dumps({"error": str(exc)})

def rejoin_ics(deadlines_json):
    return build_ics(json.loads(deadlines_json))
`;
  const ENGINE_FILES = ["__init__.py", "parser.py", "dates.py", "redact.py", "plain.py", "rules.py", "llm.py", "voice.py", "ics.py", "handoff.py"];
  let pyPromise = null;
  const loadScript = (src) => new Promise((ok, fail) => {
    const s = document.createElement("script"); s.src = src; s.onload = ok;
    s.onerror = () => fail(new Error("Couldn't load the in-browser reader. Check your connection and try again."));
    document.head.append(s);
  });
  function python() {
    if (!pyPromise) {
      pyPromise = (async () => {
        say("Loading the in-browser reader (first time only, about 10 seconds)…");
        await loadScript(STATIC.pyodide + "pyodide.js");
        const py = await window.loadPyodide({ indexURL: STATIC.pyodide });
        py.FS.mkdirTree("/rejoin/engine");
        await Promise.all(ENGINE_FILES.map(async (f) => {
          const res = await fetch("engine/" + f);
          if (!res.ok) throw new Error("Couldn't load part of the reader (" + f + ").");
          py.FS.writeFile("/rejoin/engine/" + f, await res.text());
        }));
        py.runPython(PY_HELPERS);
        return py;
      })().catch((e) => { pyPromise = null; throw e; });
    }
    return pyPromise;
  }
  const callPy = async (fn, ...args) => {
    const py = await python();
    const f = py.globals.get(fn);
    try { return f(...args); } finally { f.destroy(); }
  };
  const staticBackend = {
    analyze: async ({ me, file, since }) => {
      const bytes = new Uint8Array(await file.arrayBuffer());
      const body = JSON.parse(await callPy("rejoin_run", file.name, bytes, me, since, ""));
      if (body.error) throw new Error(body.error);
      return body;
    },
    demo: async ({ since }) => {
      const [chat, tr] = await Promise.all([fetch("demo/aina_fyp_chat.txt"), fetch("demo/voice_transcripts.json")]);
      const bytes = new Uint8Array(await chat.arrayBuffer());
      const body = JSON.parse(await callPy("rejoin_run", "chat.txt", bytes, "Aina,Ain", since, await tr.text()));
      if (body.error) throw new Error(body.error);
      body.demo = true;
      return body;
    },
    ics: async (deadlines) => new Blob([await callPy("rejoin_ics", JSON.stringify(deadlines))], { type: "text/calendar" }),
  };
  const backend = STATIC ? staticBackend : serverBackend;

  /* ---------- Submit ---------- */
  async function run(task, label) {
    showError("");
    const btns = document.querySelectorAll("#slip button");
    btns.forEach((b) => (b.disabled = true));
    say(label);
    try {
      data = await task();
      render();
    } catch (e) {
      showError(e.message);
      say("");
    } finally {
      btns.forEach((b) => (b.disabled = false));
    }
  }
  const choice = (name) => (document.querySelector(`input[name="${name}"]:checked`) || {}).value;

  $("#slip").addEventListener("submit", (e) => {
    e.preventDefault();
    const me = $("#me").value.trim();
    const file = $("#chat").files[0];
    if (!me) { showError("Add your name as it appears in the chat."); $("#me").focus(); return; }
    if (!file) { showError("Choose your exported chat file first."); $("#chat").focus(); return; }
    run(() => backend.analyze({ me, file, since: choice("since"), engine: choice("engine") }), "Reading your chat…");
  });
  $("#demo").addEventListener("click", () => {
    $("#me").value = "Aina, Ain";
    run(() => backend.demo({ since: choice("since"), engine: choice("engine") }), "Reading Aina's chat…");
  });

  /* ---------- Render ---------- */
  function render() {
    const s = data.stats;
    const r = data.result;
    $("#results").hidden = false;
    $("#since-label").textContent = data.cutoff ? "Since " + fmtTime(data.cutoff) : data.since_label;
    $("#t-msgs").textContent = s.messages;
    $("#t-voice").textContent = s.voice_notes;
    $("#t-people").textContent = s.senders;
    $("#t-in").textContent = "~" + minutes(s.read_seconds_in);
    $("#t-out").textContent = "~" + minutes(s.read_seconds_out);
    const need = r.asked_of_you.length + r.open_questions.length;
    $("#stamp").textContent = need === 0 ? "Nothing needs you" : need === 1 ? "1 thing needs you" : `${need} things need you`;
    $("#filled-summary").textContent =
      `${s.messages} messages and ${s.voice_notes} voice notes from ${s.senders} people while you were out. ` +
      `${r.asked_of_you.length} asked of you, ${r.open_questions.length} waiting for your answer, ` +
      `${r.decisions.length} decisions, ${r.deadlines.length} dates.`;

    const w = $("#warnings");
    w.replaceChildren(...data.warnings.map((t) => el("p", { text: t })));
    w.hidden = !data.warnings.length;

    renderLists();
    renderDates();
    $("#reply").value = r.draft_reply;
    renderHow();
    renderChat();

    say(`Done. ${need} ${need === 1 ? "thing needs" : "things need"} you.`);
    const results = $("#results");
    results.scrollIntoView({ behavior: root.classList.contains("pref-calm") ? "auto" : "smooth", block: "start" });
    results.focus({ preventScroll: true });
  }

  function sourceBlock(ids) {
    const box = el("div", { class: "source" });
    for (const id of ids) {
      const m = msgById(id);
      if (!m) continue;
      const head = el("p", {}, el("span", { class: "who", text: m.sender || "WhatsApp" }), document.createTextNode(", " + fmtTime(m.timestamp)));
      box.append(head);
      if (m.is_voice_note) box.append(el("p", { class: "vn", text: m.transcript_source === "demo" ? "Voice note (demo transcript)" : m.transcript ? "Voice note, transcribed" : "Voice note, not transcribed" }));
      box.append(el("p", { text: m.content }));
      box.append(el("button", { type: "button", class: "why-btn", text: "Find it in the full chat", onclick: () => jumpTo(id) }));
    }
    return box;
  }

  function itemNode(item, kind, idx, done) {
    const key = `${kind}:${item.sources.join("-")}`;
    const textId = `t-${kind}-${idx}`;
    const srcId = `s-${kind}-${idx}`;
    const isDone = done.has(key);
    const li = el("li", { class: "item" + (isDone ? " is-done" : "") });
    const text = el("p", { class: "item-text", id: textId, text: cap(plain && item.plain ? item.plain : item.text) });
    const metaBits = [];
    if (item.from) metaBits.push("From " + item.from);
    const first = msgById(item.sources[0]);
    if (first) metaBits.push(fmtTime(first.timestamp));
    const meta = el("p", { class: "meta", text: metaBits.join(", ") });
    if (item.deadline) meta.append(document.createTextNode(". "), el("span", { class: "due", text: "Due " + item.deadline.human }));
    if (item.inferred) meta.append(el("span", { class: "flag", title: "The source message doesn't name you. Check it.", text: "Check: not named directly" }));
    if (first && first.is_voice_note) meta.append(el("span", { class: "flag", text: "From a voice note" }));

    const body = el("div", {}, text, meta);
    const main = el("div", { class: "item-main" });
    if (kind === "asks" || kind === "questions") {
      const box = el("input", { type: "checkbox", "aria-labelledby": textId, checked: isDone });
      box.addEventListener("change", () => {
        const set = loadDone();
        box.checked ? set.add(key) : set.delete(key);
        saveDone(set);
        li.classList.toggle("is-done", box.checked);
        updateDone();
        say(box.checked ? "Marked done." : "Marked not done.");
      });
      main.append(box);
    }
    main.append(body);
    li.append(main);

    const src = sourceBlock(item.sources);
    src.id = srcId; src.hidden = true;
    const why = el("button", { type: "button", class: "why-btn", "aria-expanded": "false", "aria-controls": srcId, text: "Show the message" });
    why.addEventListener("click", () => {
      const open = why.getAttribute("aria-expanded") === "true";
      why.setAttribute("aria-expanded", String(!open));
      why.textContent = open ? "Show the message" : "Hide the message";
      src.hidden = open;
    });
    li.append(el("div", { class: "why" }, why, src));
    return li;
  }

  function fill(listSel, items, kind, emptyText) {
    const done = loadDone();
    const ul = $(listSel);
    ul.replaceChildren(...(items.length ? items.map((it, i) => itemNode(it, kind, i, done)) : [el("li", { class: "empty", text: emptyText })]));
  }
  function renderLists() {
    const r = data.result;
    fill("#asks", r.asked_of_you, "asks", "Nobody asked you for anything. Nice.");
    fill("#questions", r.open_questions, "questions", "No questions waiting for you.");
    fill("#decisions", r.decisions, "decisions", "No decisions that affect you.");
    updateDone();
  }
  function updateDone() {
    const total = data.result.asked_of_you.length + data.result.open_questions.length;
    const n = document.querySelectorAll("#asks .is-done, #questions .is-done").length;
    $("#t-done").textContent = `${n} of ${total}`;
  }

  function renderDates() {
    const ds = data.result.deadlines;
    const ol = $("#dates");
    if (!ds.length) { ol.replaceChildren(el("li", { class: "empty", text: "No dates mentioned." })); $("#ics").hidden = true; return; }
    $("#ics").hidden = false;
    ol.replaceChildren(...ds.map((d) => {
      const mine = d.what.startsWith("You:");
      return el("li", { class: mine ? "mine" : "" },
        el("time", { datetime: d.iso, text: d.when_human }),
        el("span", {}, mine ? el("strong", { class: "due", text: "For you: " }) : null,
          document.createTextNode(cap(mine ? d.what.slice(4).trim() : d.what))));
    }));
  }

  function renderHow() {
    const lines = [];
    lines.push(data.engine === "ai"
      ? `Read by ${data.model}. Every item had to point at a real message in the chat; ${data.validation.dropped_ungrounded || 0} item(s) that didn't were thrown away. Dates were worked out from when each message was sent, not by the AI.`
      : STATIC ? "Read by Rejoin's offline rules, running inside your browser. Nothing was uploaded."
      : "Read by Rejoin's offline rules. Nothing left this computer.");
    lines.push(`${data.privacy.masked_identifiers} phone number(s) or e-mail(s) masked, ${data.privacy.aliased_senders} unsaved contact(s) renamed, before anything was read.`);
    if (data.voice.voice_notes) {
      const v = data.voice;
      lines.push(v.demo ? `${v.demo} voice note(s) use demo transcripts written for this fictional chat.`
        : `${v.transcribed} of ${v.voice_notes} voice note(s) transcribed with Whisper${v.failed ? `, ${v.failed} failed` : ""}.`);
    }
    lines.push(`Looked at ${data.stats.messages} messages ${data.cutoff ? "since " + fmtTime(data.cutoff) : ""} in ${data.elapsed_ms} ms. Nothing was stored${STATIC ? "" : " on the server"}.`);
    $("#how-list").replaceChildren(...lines.map((t) => el("li", { text: t })));
  }

  function renderChat() {
    const hits = new Set();
    for (const k of ["asked_of_you", "decisions", "open_questions"]) data.result[k].forEach((it) => it.sources.forEach((s) => hits.add(s)));
    $("#chatlog-summary").textContent = `The full chat (${data.stats.messages} messages)`;
    $("#chat-list").replaceChildren(...data.messages.filter((m) => !m.is_system).map((m) =>
      el("li", { id: "m-" + m.id, tabindex: "-1", class: hits.has(m.id) ? "hit" : "" },
        el("time", { datetime: m.timestamp, text: fmtTime(m.timestamp) }),
        el("span", { class: "who", text: (m.sender || "") + ": " }),
        document.createTextNode(m.is_voice_note ? `🎤 ${m.transcript || "voice note"}` : m.content))));
  }
  function jumpTo(id) {
    $("#chatlog").open = true;
    const li = document.getElementById("m-" + id);
    if (li) { li.scrollIntoView({ block: "center" }); li.focus(); }
  }
  $("#show-chat").addEventListener("click", () => {
    const d = $("#chatlog"); d.open = true; d.scrollIntoView({ block: "start" }); $("#chatlog-summary").focus();
  });

  /* ---------- Calendar, copy ---------- */
  $("#ics").addEventListener("click", async () => {
    let blob;
    try { blob = await backend.ics(data.result.deadlines); } catch (e) { showError(e.message); return; }
    const url = URL.createObjectURL(blob);
    const a = el("a", { href: url, download: "rejoin-dates.ics" });
    document.body.append(a); a.click(); a.remove(); URL.revokeObjectURL(url);
    say("Calendar file downloaded. Open it to add the dates.");
  });
  $("#copy-reply").addEventListener("click", async () => {
    try { await navigator.clipboard.writeText($("#reply").value); say("Message copied. Paste it into the group."); }
    catch { $("#reply").select(); say("Select the text and copy it with your keyboard."); }
  });

  /* ---------- Read aloud ---------- */
  const synth = window.speechSynthesis;
  let reading = false;
  const readBtn = $("#read-all");
  if (!synth) readBtn.hidden = true;
  readBtn.addEventListener("click", () => {
    if (reading) { synth.cancel(); return; }
    const r = data.result;
    const pick = (it) => (plain && it.plain ? it.plain : it.text);
    const parts = [];
    const add = (title, items, fmt) => { if (items.length) { parts.push({ t: title }); items.forEach((it) => parts.push({ t: fmt(it) })); } };
    add("Asked of you.", r.asked_of_you, (it) => `${pick(it)}${it.from ? ". From " + it.from : ""}${it.deadline ? ". Due " + it.deadline.human : ""}.`);
    add("Waiting for your answer.", r.open_questions, (it) => `${pick(it)}${it.from ? ". From " + it.from : ""}.`);
    add("Decided while you were away.", r.decisions, (it) => pick(it) + ".");
    add("Dates.", r.deadlines, (d) => `${d.when_human}: ${d.what}.`);
    reading = true; readBtn.textContent = "Stop reading";
    parts.forEach((p, i) => {
      const u = new SpeechSynthesisUtterance(p.t);
      u.rate = Number($("#rate").value);
      if (i === parts.length - 1) u.onend = u.onerror = () => { reading = false; readBtn.textContent = "Read it to me"; };
      synth.speak(u);
    });
    // cancel() fires onerror on the queued utterance; make sure the button resets
    const iv = setInterval(() => { if (!synth.speaking && !synth.pending) { reading = false; readBtn.textContent = "Read it to me"; clearInterval(iv); } }, 500);
  });

  applyPrefs();
})();
