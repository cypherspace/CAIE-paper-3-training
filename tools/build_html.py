"""Build the single-file quiz HTML from data/questions.json."""

from __future__ import annotations

import html
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DATA = REPO / "data" / "questions.json"
OUT = REPO / "physics-paper-3-q2-trainer.html"
GAS_DIR = REPO / "google-apps-script"


CODE_GS = """\
/**
 * Web App entry point. Returns the trainer HTML for embedding in Google Sites
 * (or for opening directly via the Web App URL).
 */
function doGet(e) {
  return HtmlService.createTemplateFromFile('index')
    .evaluate()
    .setTitle('CAIE Physics 9702 Paper 3 Q2 Trainer')
    .setXFrameOptionsMode(HtmlService.XFrameOptionsMode.ALLOWALL);
}

/**
 * Used by index.html to inline the contents of styles.html / script.html /
 * data.html. Apps Script's HtmlService can't load multiple HTML files into a
 * single page on its own; this helper is the standard pattern.
 */
function include(filename) {
  return HtmlService.createHtmlOutputFromFile(filename).getContent();
}
"""


APPSSCRIPT_JSON = """\
{
  "timeZone": "Etc/UTC",
  "exceptionLogging": "STACKDRIVER",
  "runtimeVersion": "V8",
  "webapp": {
    "executeAs": "USER_DEPLOYING",
    "access": "ANYONE_ANONYMOUS"
  }
}
"""


GAS_README = """\
# CAIE Physics 9702 Paper 3 Q2 Trainer — Google Apps Script bundle

Drop these files into a new Apps Script project to host the trainer as a Web
App and embed it in a Google Site (the single-file HTML is too large for
Sites' inline embed, but a Web App URL embed works fine).

## Files

| File | Apps Script type | Purpose |
| --- | --- | --- |
| `Code.gs` | Script (`.gs`) | `doGet()` Web App entry point + `include()` helper |
| `appsscript.json` | Manifest | runtime + Web App access settings (`ANYONE_ANONYMOUS`) |
| `index.html` | HTML | Page shell. Inlines the three other HTML files via `<?!= include('...') ?>` |
| `styles.html` | HTML | `<style>` block |
| `script.html` | HTML | `<script>` block (vanilla JS, no frameworks) |
| `data.html` | HTML | Embedded JSON of all 60+ questions, mark-scheme entries, and base64 PNG procedure pages |

## Importing into Apps Script

1. Open https://script.google.com → **New project**.
2. Replace the auto-generated `Code.gs` with the contents of `Code.gs` from
   this folder.
3. In the editor sidebar: **+** next to "Files" → **HTML** → name it `index`
   (no extension). Paste the contents of `index.html`. Save.
4. Repeat for `styles`, `script`, and `data`. (For `data.html` you'll be
   pasting a few MB; the editor handles it but takes a moment.)
5. Click the **Project Settings** gear → tick **Show "appsscript.json"
   manifest file in editor**. Open the `appsscript.json` that now appears
   and replace its contents with the version from this folder.

## Deploying as a Web App

1. **Deploy** → **New deployment** → cog icon → **Web app**.
2. Description: anything (e.g. "Q2 trainer v1").
3. Execute as: **Me**.
4. Who has access: **Anyone** (for embedding in a public Google Site) or
   **Anyone with Google account** for a school workspace.
5. **Deploy**. Copy the **Web app URL**.

## Embedding in Google Sites

1. Open your Google Site → **Insert** → **Embed** → **By URL**.
2. Paste the Web App URL.
3. Resize the embed box to give the trainer enough room (recommended
   minimum 900×700 on desktop).

## Updating after rebuild

When `tools/build_html.py` regenerates this folder (e.g. after you upload
more papers), repaste the four HTML files into your Apps Script project and
**Deploy → Manage deployments → ✏️ Edit → New version → Deploy**. The Web
App URL stays the same so the Google Site embed keeps working.
"""


HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>CAIE Physics 9702 Paper 3 Q2 Trainer</title>
<style>
:root {
  --bg: #f7f7f9;
  --card: #ffffff;
  --border: #d8d8e0;
  --text: #1c1c1f;
  --muted: #6b6b75;
  --primary: #1f4fa3;
  --primary-text: #ffffff;
  --good: #1d6d33;
  --good-bg: #e6f3eb;
  --bad: #a31e1e;
  --bad-bg: #fbeaea;
  --neutral-bg: #f1f1f4;
  --shadow: 0 1px 2px rgba(0,0,0,0.05), 0 4px 12px rgba(0,0,0,0.04);
  --radius: 10px;
  --font: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
}
* { box-sizing: border-box; }
html, body { margin: 0; padding: 0; }
body {
  font-family: var(--font);
  font-size: 16px;
  line-height: 1.5;
  color: var(--text);
  background: var(--bg);
  padding: 16px;
}
#app { max-width: 880px; margin: 0 auto; }
header {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 8px;
}
header h1 {
  font-size: 1.25rem;
  margin: 0;
  font-weight: 600;
}
header .subtitle {
  color: var(--muted);
  font-size: 0.9rem;
}
.toolbar {
  display: flex;
  gap: 8px;
  align-items: center;
  flex-wrap: wrap;
  margin: 8px 0 16px;
  padding: 10px 12px;
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: var(--radius);
}
.toolbar label {
  font-size: 0.875rem;
  color: var(--muted);
  display: flex;
  gap: 6px;
  align-items: center;
}
.toolbar select, .toolbar button {
  font-family: inherit;
  font-size: 0.875rem;
  padding: 6px 10px;
  border: 1px solid var(--border);
  border-radius: 6px;
  background: var(--card);
  color: var(--text);
  cursor: pointer;
}
.toolbar button {
  background: var(--neutral-bg);
}
.toolbar button:hover { background: #e5e5ea; }
.toolbar .progress {
  margin-left: auto;
  font-variant-numeric: tabular-nums;
  color: var(--muted);
  font-size: 0.875rem;
}
.card {
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 16px;
  margin-bottom: 16px;
  box-shadow: var(--shadow);
}
.q-header {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  margin-bottom: 8px;
  gap: 8px;
  flex-wrap: wrap;
}
.q-meta { color: var(--muted); font-size: 0.875rem; }
.q-title { font-weight: 600; font-size: 1.05rem; }
.split {
  display: grid;
  gap: 18px;
  grid-template-columns: 1fr;
  margin-top: 12px;
}
@media (min-width: 940px) {
  #app { max-width: 1240px; }
  .split {
    grid-template-columns: minmax(0, 1.15fr) minmax(0, 1fr);
    gap: 24px;
    align-items: start;
  }
  .split > .diagram-col {
    position: sticky;
    top: 12px;
    max-height: calc(100vh - 24px);
    overflow-y: auto;
  }
}
.diagram-wrap {
  background: #fafafa;
  border: 1px solid var(--border);
  border-radius: 8px;
  overflow: hidden;
}
.diagram-img {
  display: block;
  width: 100%;
  height: auto;
  background: white;
}
.diagram-toolbar {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 10px;
  background: var(--neutral-bg);
  border-top: 1px solid var(--border);
  font-size: 0.85rem;
  color: var(--muted);
}
.diagram-toolbar button {
  font: inherit;
  padding: 2px 8px;
  border: 1px solid var(--border);
  border-radius: 4px;
  background: var(--card);
  cursor: pointer;
}
.prompt {
  font-weight: 600;
  margin: 16px 0 10px;
}
.options { list-style: none; margin: 0; padding: 0; display: grid; gap: 8px; }
.option {
  display: block;
  padding: 12px 14px;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--card);
  cursor: pointer;
  text-align: left;
  font: inherit;
  width: 100%;
  transition: background 0.15s, border-color 0.15s;
}
.option:hover:not(:disabled) {
  background: var(--neutral-bg);
  border-color: #aab;
}
.option:disabled { cursor: default; }
.option.correct {
  background: var(--good-bg);
  border-color: var(--good);
  color: var(--good);
  font-weight: 500;
}
.option.wrong {
  background: var(--bad-bg);
  border-color: var(--bad);
  color: var(--bad);
}
.feedback {
  margin-top: 12px;
  padding: 10px 12px;
  border-radius: 8px;
  font-size: 0.95rem;
}
.feedback.bad { background: var(--bad-bg); color: var(--bad); border: 1px solid #f3c5c5; }
.feedback.good { background: var(--good-bg); color: var(--good); border: 1px solid #b9dcc4; }
.ms-quote {
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px dashed #b9dcc4;
  color: var(--text);
  font-size: 0.9rem;
}
.ms-quote strong { color: var(--good); }
.actions {
  display: flex;
  gap: 8px;
  margin-top: 14px;
  flex-wrap: wrap;
}
.btn {
  font: inherit;
  padding: 8px 14px;
  border: 1px solid var(--border);
  border-radius: 6px;
  background: var(--card);
  color: var(--text);
  cursor: pointer;
}
.btn:hover { background: var(--neutral-bg); }
.btn.primary {
  background: var(--primary);
  color: var(--primary-text);
  border-color: var(--primary);
}
.btn.primary:hover { background: #173d80; }
.start-card { text-align: center; padding: 24px; }
.start-card h2 { margin: 0 0 8px; font-size: 1.4rem; }
.start-card p { color: var(--muted); max-width: 540px; margin: 8px auto; }
.kbd {
  display: inline-block;
  padding: 1px 6px;
  border: 1px solid var(--border);
  border-radius: 4px;
  background: var(--neutral-bg);
  font-family: ui-monospace, "SFMono-Regular", Menlo, monospace;
  font-size: 0.85em;
}
.muted { color: var(--muted); font-size: 0.875rem; }
.tag {
  display: inline-block;
  font-size: 0.75rem;
  padding: 2px 8px;
  border-radius: 999px;
  background: var(--neutral-bg);
  color: var(--muted);
  margin-right: 4px;
}
@media (max-width: 540px) {
  body { padding: 10px; }
  header h1 { font-size: 1.1rem; }
  .card { padding: 12px; }
  .toolbar { padding: 8px; }
  .toolbar .progress { margin-left: 0; width: 100%; }
}
</style>
</head>
<body>
<div id="app">
  <header>
    <div>
      <h1>Paper 3 Q2 Trainer</h1>
      <div class="subtitle">CAIE Physics 9702 — Limitations &amp; Improvements practice</div>
    </div>
  </header>
  <div class="toolbar">
    <label>
      Year:
      <select id="year-filter"><option value="">All</option></select>
    </label>
    <label>
      Session:
      <select id="session-filter">
        <option value="">All</option>
        <option value="May/June">May/June only</option>
        <option value="Oct/Nov">Oct/Nov only</option>
        <option value="Feb/March">Feb/March only</option>
      </select>
    </label>
    <label>
      Order:
      <select id="order">
        <option value="random">Random</option>
        <option value="sequential">Chronological</option>
      </select>
    </label>
    <button id="reset" type="button">Reset progress</button>
    <div class="progress" id="progress-summary"></div>
  </div>
  <main id="main"></main>
  <p class="muted" style="text-align:center;margin-top:24px">
    Past paper diagrams &amp; mark scheme content © UCLES (Cambridge International). Used for educational practice only.
  </p>
</div>
<script type="application/json" id="quiz-data">__DATA__</script>
<script>
"use strict";
(function() {
  const STORE_KEY = "caie-9702-q2-trainer-v1";
  const data = JSON.parse(document.getElementById("quiz-data").textContent);
  const allQuestions = data.questions;

  // Build flat list of all (question, pair) rounds for distractor sampling.
  const allLimitations = [];
  const allImprovements = [];
  allQuestions.forEach(q => {
    q.pairs.forEach(p => {
      allLimitations.push({ qid: q.id, text: p.limitation });
      if (p.improvement) allImprovements.push({ qid: q.id, text: p.improvement });
    });
  });

  // ---- progress (localStorage) ----
  function loadProgress() {
    try {
      const raw = localStorage.getItem(STORE_KEY);
      if (!raw) return { done: {}, attempts: {} };
      const obj = JSON.parse(raw);
      return { done: obj.done || {}, attempts: obj.attempts || {} };
    } catch (e) { return { done: {}, attempts: {} }; }
  }
  function saveProgress(p) {
    try { localStorage.setItem(STORE_KEY, JSON.stringify(p)); } catch (e) {}
  }
  let progress = loadProgress();

  // ---- filtering ----
  const filters = { year: "", session: "", order: "random" };

  function getYears() {
    const ys = new Set();
    allQuestions.forEach(q => {
      const m = q.session_label.match(/\d{4}/);
      if (m) ys.add(m[0]);
    });
    return [...ys].sort();
  }
  function questionMatchesFilter(q) {
    if (filters.year) {
      const m = q.session_label.match(/\d{4}/);
      if (!m || m[0] !== filters.year) return false;
    }
    if (filters.session) {
      if (!q.session_label.startsWith(filters.session)) return false;
    }
    return true;
  }

  // Build the list of all rounds (question + pair) eligible for current filter.
  function buildRounds() {
    const rounds = [];
    allQuestions.forEach(q => {
      if (!questionMatchesFilter(q)) return;
      q.pairs.forEach(p => {
        if (p.improvement) rounds.push({ qid: q.id, letter: p.letter });
      });
    });
    if (filters.order === "random") {
      // Stable shuffle keyed off session so reload doesn't change order mid-session.
      shuffleInPlace(rounds, sessionSeed);
    }
    return rounds;
  }

  // ---- RNG (deterministic per-session seed) ----
  let sessionSeed = Math.floor(Math.random() * 1e9);
  function mulberry32(seed) {
    let t = seed >>> 0;
    return function () {
      t = (t + 0x6D2B79F5) >>> 0;
      let r = Math.imul(t ^ (t >>> 15), 1 | t);
      r = (r + Math.imul(r ^ (r >>> 7), 61 | r)) ^ r;
      return ((r ^ (r >>> 14)) >>> 0) / 4294967296;
    };
  }
  function shuffleInPlace(arr, seed) {
    const rng = mulberry32(seed);
    for (let i = arr.length - 1; i > 0; i--) {
      const j = Math.floor(rng() * (i + 1));
      [arr[i], arr[j]] = [arr[j], arr[i]];
    }
  }
  function pickN(pool, n, exclude) {
    const ex = new Set(exclude || []);
    const filtered = pool.filter(x => !ex.has(x.text));
    const copy = filtered.slice();
    shuffleInPlace(copy, Math.floor(Math.random() * 1e9));
    const seen = new Set();
    const out = [];
    for (const x of copy) {
      const key = x.text.trim();
      if (seen.has(key)) continue;
      seen.add(key);
      out.push(x);
      if (out.length >= n) break;
    }
    return out;
  }

  // ---- distractor strategy ----
  // Normalize text to a short fingerprint so we can detect "the same limitation
  // worded slightly differently" - critical because generic limitations like
  // "Two readings are not enough" appear verbatim in nearly every paper.
  function fingerprint(s) {
    return (s || "")
      .toLowerCase()
      .replace(/[^a-z0-9 ]+/g, " ")
      .split(/\s+/)
      .filter(Boolean)
      .slice(0, 6)
      .join(" ");
  }

  // For "slight variation" distractors we keep a small lookup of words the
  // mark scheme commonly underlines (= required) and tempting alternatives
  // students often substitute. We only apply these when the word is present
  // in THIS pair's underlined_in_* list, so transformations are anchored
  // in the actual MS guidance.
  const KEYWORD_SWAPS = {
    "and": ["or"],
    "or": ["and"],
    "centre": ["edge"],
    "edge": ["centre"],
    "maximum": ["minimum"],
    "minimum": ["maximum"],
    "larger": ["smaller"],
    "smaller": ["larger"],
    "longer": ["shorter"],
    "shorter": ["longer"],
    "more": ["fewer"],
    "fewer": ["more"],
    "increase": ["decrease"],
    "decrease": ["increase"],
    "vertical": ["horizontal"],
    "horizontal": ["vertical"],
    "perpendicular": ["parallel"],
    "parallel": ["perpendicular"],
    "with": ["without"],
    "without": ["with"],
    "compare": ["ignore"],
    "all": ["some"],
    "raw": ["averaged"],
    "percentage": ["absolute"],
    "all readings": ["one reading"],
  };

  function escapeRegex(s) {
    return s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  }

  // Naturalize a raw mark-scheme entry into a student-style answer for display
  // as a quiz option. The original is preserved on the pair object and shown
  // back to the student after they get the answer right, so they see the full
  // canonical version (which may include several alternatives separated by /
  // or parenthetical "(not ...)" rejection clauses they should know about).
  function naturalize(text) {
    if (!text) return text;
    let s = String(text).trim();
    // (Bullet letters were already stripped during extraction; we don't try
    // to strip them again here because some MS texts legitimately start with
    // capital variable names like "H decreases with time".)

    // Drop "(not ...)" rejection clauses entirely - these belong in the
    // post-answer feedback, not the option face.
    s = s.replace(/\s*\(not\s+[^)]*\)\.?/gi, "");
    // Helper to pick first alternative from an "e.g." body, splitting on
    // /, " or ", or comma (mark schemes use these interchangeably as list
    // separators inside e.g. lists).
    const firstAlt = body => body.split(/\s*\/\s*|\s+or\s+|\s*,\s*/i)[0].trim();
    // "with a reason e.g. X/Y/Z" -> ", e.g. X" (just the first example).
    s = s.replace(/\s+with\s+(?:a\s+)?reason,?\s+e\.g\.\s*([^.]+?)(?=\.|$)/i,
      (_m, body) => ", e.g. " + firstAlt(body));
    // Standalone "with a reason" / "with reason" without an e.g. - just drop.
    s = s.replace(/\s+with\s+(?:a\s+)?reason\b\s*\.?/i, "");
    // For other "e.g. ..." trails: pick the first alternative.
    s = s.replace(/\s*e\.g\.\s*([^.]+?)(?=\.|$)/i,
      (_m, body) => ", e.g. " + firstAlt(body));
    // Strip parentheses around short optional words: "(valid) conclusion"
    // -> "valid conclusion".
    s = s.replace(/\(([a-z][a-z\s\-]{0,14})\)/gi, "$1");
    // Truncate slash-separated alternatives that survived ("do X / do Y").
    s = s.replace(/\s*\/[^.]*$/, "");
    // Tidy whitespace + punctuation. Importantly collapse repeated commas
    // (left over by the "with a reason" -> drop transform near an e.g.).
    s = s.replace(/\s{2,}/g, " ")
         .replace(/,\s*,+/g, ",")
         .replace(/\s+([.,;:])/g, "$1")
         .replace(/\.\s*\./g, ".")
         .trim();
    if (s.length > 0) s = s[0].toUpperCase() + s.slice(1);
    if (!/[.?!]$/.test(s)) s += ".";
    return s;
  }

  // Generate "slight variation" distractors from the correct text by either
  // dropping or swapping each underlined keyword. Drops teach the student that
  // the keyword was required; swaps teach that the specific word matters.
  function variantsOf(correctText, underlinedWords) {
    const variants = [];
    // Dedup by literal text (NOT fingerprint - fingerprints truncate to 6
    // words, so a swap further into the text would collide with the original).
    const seen = new Set([correctText]);
    for (const ulw of (underlinedWords || [])) {
      const norm = ulw.toLowerCase().replace(/[^a-z\s'\-/]/g, "").trim();
      if (!norm || norm.length < 2) continue;
      const isWord = /^[a-z]+$/.test(norm);
      const re = isWord
        ? new RegExp("\\b" + escapeRegex(norm) + "\\b", "i")
        : new RegExp(escapeRegex(norm), "i");
      if (!re.test(correctText)) continue;

      const dropped = correctText.replace(re, "")
        .replace(/\s{2,}/g, " ")
        .replace(/\s+([.,;:])/g, "$1")
        .trim();
      if (dropped && !seen.has(dropped) && dropped.length > 8) {
        seen.add(dropped); variants.push(dropped);
      }

      const swaps = KEYWORD_SWAPS[norm] || [];
      for (const sw of swaps) {
        const swapped = correctText.replace(re, sw);
        if (!seen.has(swapped) && swapped !== correctText) {
          seen.add(swapped); variants.push(swapped);
        }
      }
    }
    return variants;
  }

  // Curated pool of plausible-but-uncredited answers students often give. Each
  // entry is gated by apparatus tags - empty `applies_when` = universal (still
  // gated by fingerprint check against this question's accepted answers).
  const MISCONCEPTIONS = [
    // ---- LIMITATIONS commonly written by students but not credited ----
    { kind: "limitation",
      text: "Human reaction time when starting and stopping the stopwatch.",
      applies_when: ["time", "stopwatch", "stop-watch", "oscillation", "oscillations", "swing", "pendulum", "fall", "drop", "ball", "period"] },
    { kind: "limitation",
      text: "Random errors in the measurements.",
      applies_when: [] },
    { kind: "limitation",
      text: "Systematic errors in the apparatus.",
      applies_when: [] },
    { kind: "limitation",
      text: "Air resistance affects the motion of the apparatus.",
      applies_when: ["fall", "ball", "drop", "projectile", "bounce"] },
    { kind: "limitation",
      text: "Friction at the pivot affects the period of oscillation.",
      applies_when: ["pendulum", "pivot", "swing", "oscillation", "oscillations"] },
    { kind: "limitation",
      text: "The temperature of the room could change during the experiment.",
      applies_when: ["resistance", "wire", "current", "voltage", "thermistor"] },
    { kind: "limitation",
      text: "The apparatus is not perfectly accurate.",
      applies_when: [] },
    { kind: "limitation",
      text: "Not enough time was available to complete the experiment.",
      applies_when: [] },
    { kind: "limitation",
      text: "Only one set of readings was taken so the result is unreliable.",
      applies_when: [] },
    { kind: "limitation",
      text: "The measurements depend on the observer's judgement.",
      applies_when: [] },
    { kind: "limitation",
      text: "Light intensity in the room varies.",
      applies_when: ["light", "ldr", "lamp", "intensity"] },
    // ---- IMPROVEMENTS commonly written but not credited (too vague) ----
    { kind: "improvement",
      text: "Repeat the readings to improve accuracy.",
      applies_when: [] },
    { kind: "improvement",
      text: "Use a more accurate piece of apparatus.",
      applies_when: [] },
    { kind: "improvement",
      text: "Eliminate parallax error when reading the scale.",
      applies_when: ["scale", "rule", "ruler", "metre", "millimetre", "mm", "cm"] },
    { kind: "improvement",
      text: "Use digital instruments instead of analogue ones.",
      applies_when: [] },
    { kind: "improvement",
      text: "Take an average of the readings to reduce error.",
      applies_when: [] },
    { kind: "improvement",
      text: "Make sure the apparatus is set up correctly.",
      applies_when: [] },
    { kind: "improvement",
      text: "Wait for the apparatus to reach equilibrium before measuring.",
      applies_when: ["temperature", "thermometer", "heat", "cool"] },
    { kind: "improvement",
      text: "Use a larger sample to reduce uncertainty.",
      applies_when: [] },
    { kind: "improvement",
      text: "Take readings as quickly as possible.",
      applies_when: [] },
    { kind: "improvement",
      text: "Carry out the experiment in a controlled environment.",
      applies_when: [] },
  ];

  function applicableMisconceptions(question, kind) {
    const myTags = new Set(question.tags || []);
    const ownFps = new Set((kind === "limitation"
      ? question.pairs.map(p => fingerprint(p.limitation))
      : question.pairs.map(p => fingerprint(p.improvement))));
    return MISCONCEPTIONS
      .filter(m => m.kind === kind)
      // Universal (empty applies_when) OR has at least one matching tag.
      .filter(m => m.applies_when.length === 0
        || m.applies_when.some(t => myTags.has(t)))
      // Don't show as a "wrong" option if it's actually credited here.
      .filter(m => !ownFps.has(fingerprint(m.text)))
      .map(m => m.text);
  }
  // Build per-qid lookups for tag-overlap scoring.
  const questionsById = Object.fromEntries(allQuestions.map(q => [q.id, q]));
  function tagOverlap(qidA, qidB) {
    const a = questionsById[qidA], b = questionsById[qidB];
    if (!a || !b) return 0;
    const setB = new Set(b.tags || []);
    let n = 0;
    for (const t of (a.tags || [])) if (setB.has(t)) n++;
    return n;
  }
  // Pull from each tier in order until we have n unique items. Each tier is
  // either an array of texts (default: dedup by fingerprint - useful for
  // cross-question candidates that may appear in multiple papers with near-
  // identical wording) OR an object {texts, looseDedup:true} which only dedups
  // by literal text (used for variant distractors, since their fingerprint
  // intentionally matches the correct answer).
  function pickFromTiers(tiers, n, excludeTexts) {
    const seenLit = new Set(excludeTexts || []);
    const seenFp = new Set((excludeTexts || []).map(fingerprint));
    const out = [];
    for (const tier of tiers) {
      if (out.length >= n) break;
      const cfg = Array.isArray(tier)
        ? { texts: tier, looseDedup: false, max: Infinity }
        : { looseDedup: false, max: Infinity, ...tier };
      const shuffled = cfg.texts.slice();
      shuffleInPlace(shuffled, Math.floor(Math.random() * 1e9));
      let takenFromTier = 0;
      for (const text of shuffled) {
        if (out.length >= n || takenFromTier >= cfg.max) break;
        if (seenLit.has(text)) continue;
        if (!cfg.looseDedup) {
          const fp = fingerprint(text);
          if (seenFp.has(fp)) continue;
          seenFp.add(fp);
        }
        seenLit.add(text);
        out.push(text);
        takenFromTier++;
      }
    }
    return out;
  }
  function distractorsForLimitation(question, correctPair) {
    const correctText = correctPair.limitation;
    const ownFps = new Set(question.pairs.map(p => fingerprint(p.limitation)));

    // Tier A: explicit MS "(not ...)" rejections for THIS question.
    const tierA = (question.rejected_limitations || []).filter(t =>
      !ownFps.has(fingerprint(t)));

    // Tier B: slight variations of the correct text - drop or swap an
    // underlined keyword. Anchored in this pair's actually-underlined words.
    const tierB = variantsOf(correctText, correctPair.underlined_in_limitation || []);

    // Tier C: misconceptions filtered by apparatus tag applicability.
    const tierC = applicableMisconceptions(question, "limitation");

    // Tier D / E: cross-question by tag overlap, then anywhere as fallback.
    const myTags = new Set(question.tags || []);
    const tierD = [], tierE = [];
    for (const x of allLimitations) {
      if (x.qid === question.id) continue;
      if (ownFps.has(fingerprint(x.text))) continue;
      const otherQ = questionsById[x.qid];
      const overlap = otherQ && (otherQ.tags || []).some(t => myTags.has(t));
      (overlap ? tierD : tierE).push(x.text);
    }
    // Cap tiers A and C at 1 each so the same MS-rejection / misconception
    // strings don't dominate every single round; ensures students see variety.
    return pickFromTiers(
      [
        { texts: tierA, max: 1 },
        { texts: tierB, looseDedup: true, max: 2 },
        { texts: tierC, max: 1 },
        tierD,
        tierE,
      ],
      3, [correctText]);
  }
  function distractorsForImprovement(question, correctPair) {
    const correctText = correctPair.improvement;
    const ownImpFps = new Set(question.pairs.map(p => fingerprint(p.improvement)));

    // Tier A: same-question OTHER-pair improvements - valid fixes for THIS
    // experiment but address a different limitation. Highly pedagogical.
    const tierA = question.pairs
      .filter(p => p.letter !== correctPair.letter && p.improvement)
      .map(p => p.improvement);

    // Tier B: slight variations of the correct improvement.
    const tierB = variantsOf(correctText, correctPair.underlined_in_improvement || []);

    // Tier C: explicit MS rejections for improvements.
    const tierC = (question.rejected_improvements || [])
      .filter(t => !ownImpFps.has(fingerprint(t)));

    // Tier D: misconceptions filtered by apparatus tag applicability.
    const tierD = applicableMisconceptions(question, "improvement");

    // Tier E / F: cross-question by tag overlap, then anywhere.
    const myTags = new Set(question.tags || []);
    const tierE = [], tierF = [];
    for (const x of allImprovements) {
      if (x.qid === question.id) continue;
      if (ownImpFps.has(fingerprint(x.text))) continue;
      const otherQ = questionsById[x.qid];
      const overlap = otherQ && (otherQ.tags || []).some(t => myTags.has(t));
      (overlap ? tierE : tierF).push(x.text);
    }
    // Same capping rationale as limitations: keep the mix varied.
    return pickFromTiers(
      [
        tierA,                                      // same-Q other pairs (best)
        { texts: tierB, looseDedup: true, max: 2 }, // variants
        { texts: tierC, max: 1 },                   // MS rejected improvements
        { texts: tierD, max: 1 },                   // misconceptions
        tierE,                                      // tag-matched cross-Q
        tierF,                                      // anywhere fallback
      ],
      3, [correctText]);
  }

  // ---- DOM helpers ----
  const main = document.getElementById("main");
  function $(tag, attrs, ...children) {
    const el = document.createElement(tag);
    if (attrs) {
      for (const k in attrs) {
        if (k === "class") el.className = attrs[k];
        else if (k === "html") el.innerHTML = attrs[k];
        else if (k.startsWith("on") && typeof attrs[k] === "function") el.addEventListener(k.slice(2), attrs[k]);
        else el.setAttribute(k, attrs[k]);
      }
    }
    for (const c of children) {
      if (c == null) continue;
      if (typeof c === "string") el.appendChild(document.createTextNode(c));
      else el.appendChild(c);
    }
    return el;
  }

  // ---- screens ----
  function findNextRound() {
    const rounds = buildRounds();
    return rounds.find(r => !(progress.done[r.qid] && progress.done[r.qid][r.letter]));
  }

  function totals() {
    const rounds = buildRounds();
    const done = rounds.filter(r => progress.done[r.qid] && progress.done[r.qid][r.letter]).length;
    return { done, total: rounds.length };
  }

  function updateProgressUI() {
    const t = totals();
    document.getElementById("progress-summary").textContent =
      t.total === 0 ? "No questions match this filter" : `${t.done} / ${t.total} pairs completed`;
  }

  function renderStart() {
    const t = totals();
    const next = findNextRound();
    const card = $("div", { class: "card start-card" },
      $("h2", null, "Practice Q2 limitations & improvements"),
      $("p", null,
        "Each round shows you a real Paper 3 Question 2 stimulus. First, identify a limitation of the experiment from the four options. Once correct, suggest an improvement that addresses that specific limitation."),
      $("p", { class: "muted" },
        "Distractors for limitations come from other experiments (so they don't actually apply here). Distractors for improvements come from the same experiment but address a different limitation — match each improvement to its own limitation."),
      $("p", null, t.total === 0
        ? "No questions in current filter."
        : `${t.done} of ${t.total} pairs completed.`),
      $("div", { class: "actions", style: "justify-content:center" },
        next
          ? $("button", { class: "btn primary", onclick: () => renderRound(next.qid, next.letter) },
              t.done > 0 ? "Continue" : "Start practising")
          : $("span", { class: "muted" }, "Nothing to do — reset or change filter"))
    );
    main.replaceChildren(card);
    updateProgressUI();
  }

  function renderRound(qid, letter) {
    const question = allQuestions.find(q => q.id === qid);
    const pair = question.pairs.find(p => p.letter === letter);
    if (!question || !pair) { renderStart(); return; }

    const card = $("div", { class: "card" });
    const header = $("div", { class: "q-header" },
      $("div", null,
        $("span", { class: "tag" }, question.paper_code || question.id),
        $("span", { class: "q-meta" }, question.session_label)),
      $("div", { class: "q-meta" }, `Limitation ${pair.letter}`));
    card.appendChild(header);
    card.appendChild($("div", { class: "q-title" },
      question.experiment
        ? "In this experiment, you will investigate " + question.experiment + "."
        : "Refer to the procedure and diagrams alongside."));

    // Build split layout: diagram column (left/top) + answer column (right/bottom).
    const split = $("div", { class: "split" });
    const diagramCol = $("div", { class: "diagram-col" });
    const answerCol = $("div", { class: "answer-col" });
    split.appendChild(diagramCol);
    split.appendChild(answerCol);
    card.appendChild(split);

    // Diagrams.
    if (question.page_images_b64 && question.page_images_b64.length) {
      const wrap = $("div", { class: "diagram-wrap" });
      const img = $("img", { class: "diagram-img", alt: "Q2 procedure page" });
      let idx = 0;
      function showPage(i) {
        idx = i;
        img.src = "data:image/png;base64," + question.page_images_b64[i];
        counter.textContent = `Page ${i + 1} of ${question.page_images_b64.length}`;
        prevBtn.disabled = i === 0;
        nextBtn.disabled = i === question.page_images_b64.length - 1;
      }
      const prevBtn = $("button", { type: "button", onclick: () => showPage(Math.max(0, idx - 1)) }, "‹ Prev");
      const nextBtn = $("button", { type: "button", onclick: () => showPage(Math.min(question.page_images_b64.length - 1, idx + 1)) }, "Next ›");
      const counter = $("span", null, "");
      const tb = $("div", { class: "diagram-toolbar" }, prevBtn, counter, nextBtn);
      wrap.appendChild(img);
      wrap.appendChild(tb);
      diagramCol.appendChild(wrap);
      showPage(0);
    } else {
      diagramCol.appendChild($("div", { class: "muted" }, "(No procedure pages captured for this question.)"));
    }

    // Phase 1: limitation MCQ. Build options as {display, raw} pairs so we
    // can show the polished student-style version on the button while
    // remembering the raw mark-scheme entry to reveal in feedback.
    const correctLimNatural = naturalize(pair.limitation);
    const rawLimDistractors = distractorsForLimitation(question, pair);
    const limOptionPairs = [
      { display: correctLimNatural, raw: pair.limitation, isCorrect: true },
      ...rawLimDistractors.map(d => ({ display: naturalize(d), raw: d, isCorrect: false })),
    ];
    // Dedup by display text - naturalization may have collapsed two raw
    // options to the same surface form. Always keep index 0 (the correct
    // option); only drop later entries that duplicate something already kept.
    {
      const seen = new Set([limOptionPairs[0].display]);
      for (let i = limOptionPairs.length - 1; i >= 1; i--) {
        if (seen.has(limOptionPairs[i].display)) limOptionPairs.splice(i, 1);
        else seen.add(limOptionPairs[i].display);
      }
    }
    shuffleInPlace(limOptionPairs, Math.floor(Math.random() * 1e9));

    const promptLim = $("div", { class: "prompt" }, "Identify a limitation of this experiment:");
    answerCol.appendChild(promptLim);
    const limList = $("ul", { class: "options" });
    const limFeedback = $("div", { class: "feedback", style: "display:none" });
    const limButtons = limOptionPairs.map(opt => {
      const btn = $("button", { class: "option", type: "button" }, opt.display);
      btn.addEventListener("click", () => onLimitationChoice(opt, btn));
      const li = $("li", null, btn);
      limList.appendChild(li);
      return btn;
    });
    answerCol.appendChild(limList);
    answerCol.appendChild(limFeedback);

    let limCorrect = false;
    function onLimitationChoice(opt, btn) {
      if (limCorrect) return;
      if (opt.isCorrect) {
        limCorrect = true;
        btn.classList.add("correct");
        limButtons.forEach(b => b.disabled = true);
        limFeedback.style.display = "";
        limFeedback.className = "feedback good";
        limFeedback.replaceChildren(
          $("div", null, "Correct — that's an accepted limitation."),
          $("div", { class: "ms-quote" },
            $("strong", null, "Mark scheme: "),
            pair.limitation));
        showImprovementPhase();
      } else {
        btn.classList.add("wrong");
        btn.disabled = true;
        limFeedback.style.display = "";
        limFeedback.className = "feedback bad";
        limFeedback.textContent = "Not a recognised limitation for this experiment. The mark scheme accepts limitations specific to the apparatus and procedure shown above. Try another option.";
      }
    }

    function showImprovementPhase() {
      const sep = $("hr", { style: "margin:18px 0;border:none;border-top:1px solid var(--border)" });
      answerCol.appendChild(sep);

      const limRecap = $("div", { class: "muted", style: "margin-bottom:6px" },
        $("strong", null, "Limitation: "), pair.limitation);
      answerCol.appendChild(limRecap);

      const promptImp = $("div", { class: "prompt" },
        "Suggest an improvement that addresses this specific limitation:");
      answerCol.appendChild(promptImp);

      const correctImpNatural = naturalize(pair.improvement);
      const rawImpDistractors = distractorsForImprovement(question, pair);
      const impOptionPairs = [
        { display: correctImpNatural, raw: pair.improvement, isCorrect: true,
          matchesLetter: pair.letter },
        ...rawImpDistractors.map(d => {
          const matching = question.pairs.find(p => p.improvement === d);
          return {
            display: naturalize(d),
            raw: d,
            isCorrect: false,
            matchesLetter: matching ? matching.letter : null,
            matchingLimitation: matching ? matching.limitation : null,
          };
        }),
      ];
      // Dedup, always keeping the correct option at index 0.
      {
        const seen = new Set([impOptionPairs[0].display]);
        for (let i = impOptionPairs.length - 1; i >= 1; i--) {
          if (seen.has(impOptionPairs[i].display)) impOptionPairs.splice(i, 1);
          else seen.add(impOptionPairs[i].display);
        }
      }
      shuffleInPlace(impOptionPairs, Math.floor(Math.random() * 1e9));
      const impList = $("ul", { class: "options" });
      const impFeedback = $("div", { class: "feedback", style: "display:none" });
      const impButtons = impOptionPairs.map(opt => {
        const btn = $("button", { class: "option", type: "button" }, opt.display);
        btn.addEventListener("click", () => onImprovementChoice(opt, btn));
        const li = $("li", null, btn);
        impList.appendChild(li);
        return btn;
      });
      answerCol.appendChild(impList);
      answerCol.appendChild(impFeedback);

      let impCorrect = false;
      function onImprovementChoice(opt, btn) {
        if (impCorrect) return;
        if (opt.isCorrect) {
          impCorrect = true;
          btn.classList.add("correct");
          impButtons.forEach(b => b.disabled = true);
          impFeedback.style.display = "";
          impFeedback.className = "feedback good";
          impFeedback.replaceChildren(
            $("div", null, "Correct! That's the mark-scheme improvement for this limitation."),
            $("div", { class: "ms-quote" },
              $("strong", null, "Mark scheme: "),
              pair.improvement));
          markDone(qid, letter);
          showNextActions();
        } else {
          btn.classList.add("wrong");
          btn.disabled = true;
          impFeedback.style.display = "";
          impFeedback.className = "feedback bad";
          if (opt.matchesLetter && opt.matchesLetter !== pair.letter) {
            impFeedback.textContent =
              `That improvement addresses a different limitation (limitation ${opt.matchesLetter}: "${truncate(opt.matchingLimitation, 110)}"). Pick the one that fixes the limitation you just identified.`;
          } else {
            impFeedback.textContent = "That improvement isn't credited for the limitation you identified — either it's too vague, doesn't apply to this experiment, or it's missing a key word the mark scheme requires. Try another option.";
          }
        }
      }

      function showNextActions() {
        const next = findNextRound();
        const actions = $("div", { class: "actions" },
          next
            ? $("button", { class: "btn primary", onclick: () => renderRound(next.qid, next.letter) }, "Next round")
            : $("button", { class: "btn primary", onclick: () => renderStart() }, "All done — back to start"),
          $("button", { class: "btn", onclick: () => renderRound(qid, letter) }, "Repeat this one"));
        answerCol.appendChild(actions);
      }
    }

    main.replaceChildren(card);
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  function truncate(s, n) { return s.length > n ? s.slice(0, n - 1) + "…" : s; }

  function markDone(qid, letter) {
    progress.done[qid] = progress.done[qid] || {};
    progress.done[qid][letter] = true;
    saveProgress(progress);
    updateProgressUI();
  }

  // ---- toolbar wiring ----
  const yearSel = document.getElementById("year-filter");
  getYears().forEach(y => {
    const opt = document.createElement("option");
    opt.value = y;
    opt.textContent = y;
    yearSel.appendChild(opt);
  });
  yearSel.addEventListener("change", () => { filters.year = yearSel.value; renderStart(); });
  document.getElementById("session-filter").addEventListener("change", e => {
    filters.session = e.target.value; renderStart();
  });
  document.getElementById("order").addEventListener("change", e => {
    filters.order = e.target.value;
    sessionSeed = Math.floor(Math.random() * 1e9);
    renderStart();
  });
  document.getElementById("reset").addEventListener("click", () => {
    if (confirm("Reset all progress?")) {
      progress = { done: {}, attempts: {} };
      saveProgress(progress);
      renderStart();
    }
  });

  renderStart();
})();
</script>
</body>
</html>
"""


def split_for_gas(single_file_html: str) -> dict[str, str]:
    """Split the assembled single-file HTML into the GAS file layout.

    Returns a dict {filename: content}. The split works by extracting the
    three inline blocks (`<style>`, `<script type="application/json">`,
    `<script>`) into separate HTML files and replacing them in `index.html`
    with `<?!= include('...') ?>` directives that Apps Script's HtmlService
    template engine evaluates server-side.
    """
    style_re = re.compile(r"<style>([\s\S]*?)</style>", re.S)
    data_re = re.compile(
        r'<script type="application/json" id="quiz-data">([\s\S]*?)</script>',
        re.S,
    )
    main_script_re = re.compile(
        r'<script>(\s*"use strict";[\s\S]*?)</script>',
        re.S,
    )

    sm = style_re.search(single_file_html)
    dm = data_re.search(single_file_html)
    smain = main_script_re.search(single_file_html)
    if not (sm and dm and smain):
        raise RuntimeError(
            "could not locate one of <style>, <script id=quiz-data>, or main "
            "<script> blocks - HTML structure may have drifted"
        )

    styles_html = "<style>" + sm.group(1) + "</style>\n"
    data_html = (
        '<script type="application/json" id="quiz-data">'
        + dm.group(1)
        + "</script>\n"
    )
    script_html = "<script>" + smain.group(1) + "</script>\n"

    # Build index.html by replacing the three blocks with include directives.
    # Replace in descending position order so earlier replacements don't shift
    # later match offsets.
    spans = sorted(
        [
            (sm.start(), sm.end(), "<?!= include('styles'); ?>"),
            (dm.start(), dm.end(), "<?!= include('data'); ?>"),
            (smain.start(), smain.end(), "<?!= include('script'); ?>"),
        ],
        key=lambda t: t[0],
        reverse=True,
    )
    index = single_file_html
    for start, end, repl in spans:
        index = index[:start] + repl + index[end:]

    return {
        "Code.gs": CODE_GS,
        "appsscript.json": APPSSCRIPT_JSON,
        "index.html": index,
        "styles.html": styles_html,
        "script.html": script_html,
        "data.html": data_html,
        "README.md": GAS_README,
    }


def main():
    raw = json.loads(DATA.read_text())
    minimal = {
        "questions": [
            {
                "id": q["id"],
                "session_label": q["session_label"],
                "paper_code": q["paper_code"],
                "experiment": q["experiment"],
                "page_images_b64": q.get("page_images_b64", []),
                "tags": q.get("tags", []),
                "rejected_limitations": q.get("rejected_limitations", []),
                "rejected_improvements": q.get("rejected_improvements", []),
                "pairs": [
                    {
                        "letter": p["letter"],
                        "limitation": p["limitation"],
                        "improvement": p["improvement"],
                        "underlined_in_limitation": p.get("underlined_in_limitation", []),
                        "underlined_in_improvement": p.get("underlined_in_improvement", []),
                    }
                    for p in q["pairs"]
                    if p["limitation"] and p["improvement"]  # skip any orphans
                ],
            }
            for q in raw["questions"]
        ]
    }
    blob = json.dumps(minimal, ensure_ascii=False)
    # Make safe to embed inside <script type="application/json">.
    safe = blob.replace("</", "<\\/")
    out = HTML_TEMPLATE.replace("__DATA__", safe)
    OUT.write_text(out, encoding="utf-8")
    n_q = len(minimal["questions"])
    n_p = sum(len(q["pairs"]) for q in minimal["questions"])
    n_img = sum(len(q["page_images_b64"]) for q in minimal["questions"])
    size_kb = OUT.stat().st_size // 1024
    print(
        f"wrote {OUT}: {n_q} questions, {n_p} answerable pairs, {n_img} diagram pages, {size_kb} KB",
        file=sys.stderr,
    )

    # Emit the Google Apps Script bundle.
    GAS_DIR.mkdir(exist_ok=True)
    files = split_for_gas(out)
    for fname, content in files.items():
        (GAS_DIR / fname).write_text(content, encoding="utf-8")
    print(
        f"wrote {GAS_DIR}/ with {len(files)} files "
        f"({', '.join(sorted(files))})",
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
