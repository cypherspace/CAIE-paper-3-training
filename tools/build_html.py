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
.diagram-wrap {
  margin: 12px 0;
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
  function distractorsForLimitation(question, correctText) {
    // Pool: limitations from OTHER questions whose fingerprint doesn't match
    // any of the current question's accepted limitations (else the "wrong"
    // option would actually be credited here too).
    const ownFps = new Set(question.pairs.map(p => fingerprint(p.limitation)));
    const pool = allLimitations.filter(x =>
      x.qid !== question.id && !ownFps.has(fingerprint(x.text)));
    return pickN(pool, 3, [correctText]).map(x => x.text);
  }
  function distractorsForImprovement(question, correctPair) {
    // Prefer improvements from same question's OTHER pairs (most pedagogical -
    // they're "valid improvements for this experiment, but for a different
    // limitation").
    const sameQ = question.pairs
      .filter(p => p.letter !== correctPair.letter && p.improvement)
      .map(p => ({ qid: question.id, text: p.improvement }));
    let pool = sameQ.slice();
    if (pool.length < 3) {
      const ownFps = new Set(question.pairs.map(p => fingerprint(p.improvement)));
      const others = allImprovements.filter(x =>
        x.qid !== question.id && !ownFps.has(fingerprint(x.text)));
      pool = pool.concat(others);
    }
    return pickN(pool, 3, [correctPair.improvement]).map(x => x.text);
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
        : "Refer to the procedure and diagrams below."));

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
      card.appendChild(wrap);
      showPage(0);
    }

    // Phase 1: limitation MCQ.
    const limitationOptions = [pair.limitation, ...distractorsForLimitation(question, pair.limitation)];
    shuffleInPlace(limitationOptions, Math.floor(Math.random() * 1e9));

    const promptLim = $("div", { class: "prompt" }, "Identify a limitation of this experiment:");
    card.appendChild(promptLim);
    const limList = $("ul", { class: "options" });
    const limFeedback = $("div", { class: "feedback", style: "display:none" });
    const limButtons = limitationOptions.map(text => {
      const btn = $("button", { class: "option", type: "button" }, text);
      btn.addEventListener("click", () => onLimitationChoice(text, btn));
      const li = $("li", null, btn);
      limList.appendChild(li);
      return btn;
    });
    card.appendChild(limList);
    card.appendChild(limFeedback);

    let limCorrect = false;
    function onLimitationChoice(text, btn) {
      if (limCorrect) return;
      if (text === pair.limitation) {
        limCorrect = true;
        btn.classList.add("correct");
        limButtons.forEach(b => b.disabled = true);
        limFeedback.style.display = "";
        limFeedback.className = "feedback good";
        limFeedback.textContent = "Correct — that's an accepted limitation. Now match an improvement to it.";
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
      card.appendChild(sep);

      const limRecap = $("div", { class: "muted", style: "margin-bottom:6px" },
        $("strong", null, "Limitation: "), pair.limitation);
      card.appendChild(limRecap);

      const promptImp = $("div", { class: "prompt" },
        "Suggest an improvement that addresses this specific limitation:");
      card.appendChild(promptImp);

      const improvementOptions = [pair.improvement, ...distractorsForImprovement(question, pair)];
      shuffleInPlace(improvementOptions, Math.floor(Math.random() * 1e9));
      const impList = $("ul", { class: "options" });
      const impFeedback = $("div", { class: "feedback", style: "display:none" });
      const impButtons = improvementOptions.map(text => {
        const btn = $("button", { class: "option", type: "button" }, text);
        btn.addEventListener("click", () => onImprovementChoice(text, btn));
        const li = $("li", null, btn);
        impList.appendChild(li);
        return btn;
      });
      card.appendChild(impList);
      card.appendChild(impFeedback);

      let impCorrect = false;
      function onImprovementChoice(text, btn) {
        if (impCorrect) return;
        if (text === pair.improvement) {
          impCorrect = true;
          btn.classList.add("correct");
          impButtons.forEach(b => b.disabled = true);
          impFeedback.style.display = "";
          impFeedback.className = "feedback good";
          impFeedback.textContent = "Correct! That's the mark-scheme improvement for this limitation.";
          markDone(qid, letter);
          showNextActions();
        } else {
          btn.classList.add("wrong");
          btn.disabled = true;
          // Find which limitation this improvement actually pairs with, if any.
          const matchingPair = question.pairs.find(p => p.improvement === text);
          impFeedback.style.display = "";
          impFeedback.className = "feedback bad";
          impFeedback.textContent = matchingPair
            ? `That improvement addresses a different limitation (limitation ${matchingPair.letter}: "${truncate(matchingPair.limitation, 110)}"). Pick the one that fixes the limitation you just identified.`
            : "That improvement isn't credited for the limitation you identified. Try another option.";
        }
      }

      function showNextActions() {
        const next = findNextRound();
        const actions = $("div", { class: "actions" },
          next
            ? $("button", { class: "btn primary", onclick: () => renderRound(next.qid, next.letter) }, "Next round")
            : $("button", { class: "btn primary", onclick: () => renderStart() }, "All done — back to start"),
          $("button", { class: "btn", onclick: () => renderRound(qid, letter) }, "Repeat this one"));
        card.appendChild(actions);
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
                "pairs": [
                    {
                        "letter": p["letter"],
                        "limitation": p["limitation"],
                        "improvement": p["improvement"],
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


if __name__ == "__main__":
    main()
