"""Extract Q2 limitations/improvements + procedure text + diagram pages from each
9702 Paper 3 QP/MS pair in papers/, write structured JSON to data/questions.json.

Approach:
  - Find Q2 in the QP via pdftotext output, identify the page range covering the
    procedure (start of Q2 to start of the (h) "limitations" question).
  - Render those pages as PNGs with pdftoppm, optimize with pngquant, base64.
  - Parse Q2(h)(i) and Q2(h)(ii) tables in the MS via pdftotext -layout, splitting
    on the lettered bullets (A, B, C, ...).
  - Pair limitation A with improvement A by letter (the MS uses matching letters
    to indicate which limitation each improvement addresses).
"""

from __future__ import annotations

import base64
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

try:
    import pdfplumber  # for underline detection (graphics-aware)
except ImportError:
    pdfplumber = None

REPO = Path(__file__).resolve().parent.parent
PAPERS = REPO / "papers"
DATA = REPO / "data"
DATA.mkdir(exist_ok=True)

SESSION_LABELS = {"s": "May/June", "w": "Oct/Nov", "m": "Feb/March"}


@dataclass
class Pair:
    letter: str
    limitation: str
    improvement: str = ""
    underlined_in_limitation: list[str] = field(default_factory=list)
    underlined_in_improvement: list[str] = field(default_factory=list)


@dataclass
class Question:
    id: str
    session_code: str  # e.g. "s23"
    session_label: str  # e.g. "May/June 2023"
    variant_pmt: str  # e.g. "v1"
    paper_code: str = ""  # e.g. "9702/31" (read from cover)
    experiment: str = ""  # e.g. "investigate the oscillations of a wooden strip and a pendulum"
    procedure_text: str = ""  # verbatim Q2 procedure (a)..(g), excluding (h) limitations Q
    page_images_b64: list[str] = field(default_factory=list)
    pairs: list[Pair] = field(default_factory=list)
    rejected_limitations: list[str] = field(default_factory=list)  # MS "(not ...)" clauses
    rejected_improvements: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)  # apparatus / topic keywords
    extraction_warnings: list[str] = field(default_factory=list)


def run(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, **kw)


def pdftotext_layout(pdf: Path, first: Optional[int] = None, last: Optional[int] = None) -> str:
    args = ["pdftotext", "-layout"]
    if first is not None:
        args += ["-f", str(first)]
    if last is not None:
        args += ["-l", str(last)]
    args += [str(pdf), "-"]
    r = run(args)
    return r.stdout


def get_page_count(pdf: Path) -> int:
    r = run(["pdfinfo", str(pdf)])
    for line in r.stdout.splitlines():
        if line.startswith("Pages:"):
            return int(line.split(":", 1)[1].strip())
    return 0


def find_q2_page_range(qp: Path) -> tuple[int, int, int]:
    """Return (q2_first_page, q2_last_page, h_page) using a per-page sweep.

    q2_first_page: the page where "2  In this experiment" first appears.
    h_page: the page where Q2(h) (the limitations question) appears.
    q2_last_page: the page just before [Total: 20] / end-of-Q2 marker (inclusive
                  of the page that contains "Describe four sources of uncertainty"
                  - we don't show this page since it's blank lines for answers).
    Procedure pages = q2_first_page .. (h_page - 1).
    """
    pages = get_page_count(qp)
    q2_first = -1
    h_page = -1
    last = -1
    for p in range(1, pages + 1):
        t = pdftotext_layout(qp, p, p)
        if q2_first < 0 and re.search(r"^\s*2\s+In this experiment", t, re.M):
            q2_first = p
        if q2_first > 0 and h_page < 0:
            if re.search(
                r"\(h\)\s*\(i\).*(?:limitation|sources of uncertainty)", t, re.I | re.S
            ):
                h_page = p
        if q2_first > 0 and re.search(r"\[Total:\s*20\]", t):
            last = p
            break
    if last < 0:
        last = pages
    if h_page < 0:
        h_page = last
    return q2_first, last, h_page


def page_text_clean(text: str) -> str:
    """Drop common page furniture (footers like '© UCLES 2023  9702/31/M/J/23')."""
    out = []
    for line in text.splitlines():
        s = line.strip()
        if not s:
            out.append("")
            continue
        if s.startswith("© UCLES"):
            continue
        if s == "PMT":
            continue
        if re.fullmatch(r"\[Turn over\]?", s):
            continue
        if re.fullmatch(r"\d+", s):  # bare page numbers
            continue
        out.append(line)
    # collapse 3+ blank lines to 2
    cleaned = re.sub(r"\n{3,}", "\n\n", "\n".join(out))
    return cleaned.strip()


def extract_paper_code(qp: Path) -> str:
    """Read 9702/3X from cover page."""
    cover = pdftotext_layout(qp, 1, 1)
    m = re.search(r"\b9702\s*/\s*(\d{2})\b", cover)
    return f"9702/{m.group(1)}" if m else ""


def extract_experiment_intro(q2_text: str) -> str:
    """Extract the 'In this experiment, you will investigate ...' sentence."""
    m = re.search(
        r"In this experiment,?\s+you will investigate\s+(.+?)(?:\.|\n\s*\n)",
        q2_text,
        re.S,
    )
    if not m:
        return ""
    return re.sub(r"\s+", " ", m.group(1).strip()).rstrip(".")


def extract_procedure_text(qp: Path, q2_first: int, h_page: int) -> tuple[str, str]:
    """Return (raw_text_pages_concatenated_clean, experiment_intro)."""
    # Procedure lives on q2_first .. (h_page - 1). If h_page == q2_first the (h)
    # is on the same page as Q2 starts; in that case still include that page but
    # truncate at "(h)".
    lo = q2_first
    hi = max(q2_first, h_page - 1)
    raw = pdftotext_layout(qp, lo, hi)
    # If h_page == q2_first, the procedure text is truncated by (h) marker:
    if h_page == q2_first:
        raw_h = pdftotext_layout(qp, q2_first, q2_first)
        cut = re.split(r"\(h\)\s*\(i\)", raw_h, maxsplit=1)
        raw = cut[0]
    cleaned = page_text_clean(raw)
    intro = extract_experiment_intro(cleaned)
    return cleaned, intro


def render_pages_to_b64(qp: Path, first: int, last: int, dpi: int = 110) -> list[str]:
    """Render each page in [first, last] inclusive as a PNG, optimize, base64 it."""
    out: list[str] = []
    with tempfile.TemporaryDirectory() as td:
        prefix = Path(td) / "p"
        run(
            [
                "pdftoppm",
                "-r",
                str(dpi),
                "-png",
                "-f",
                str(first),
                "-l",
                str(last),
                str(qp),
                str(prefix),
            ]
        )
        # pdftoppm produces e.g. p-7.png, p-08.png depending on width
        files = sorted(Path(td).glob("p-*.png"))
        for f in files:
            opt = f.with_suffix(".opt.png")
            r = run(["pngquant", "--quality=55-80", "--speed", "3", "--output", str(opt), str(f)])
            src = opt if opt.exists() else f
            data = src.read_bytes()
            out.append(base64.b64encode(data).decode("ascii"))
    return out


# ---------- Mark scheme parsing ----------

LETTERED = re.compile(r"^(\s+)([A-Z])\s{2,}(.+)$")


def find_ms_table_text(ms: Path) -> str:
    """Return all text from the answers table (everything after 'Generic Marking
    Principles' is the per-question rows)."""
    full = pdftotext_layout(ms)
    # Heuristic: cut everything before the first row that mentions question 1 / 1(a) / Q1.
    m = re.search(r"\n\s*1[\(\s]", full)
    return full[m.start():] if m else full


def extract_letters_block(ms_text: str, marker: str) -> list[tuple[str, str]]:
    """Find the section of the MS table starting at e.g. '2(h)(i)' and return
    list of (letter, body_text) pairs. Stops at the next question marker
    or '1 mark for each point' line."""
    # Locate the marker. The marker appears at the start of a question's row,
    # followed by the body text (which contains the lettered bullets in a column).
    pat = re.compile(r"^\s*" + re.escape(marker) + r"(?!\w)", re.M)
    m = pat.search(ms_text)
    if not m:
        return []
    rest = ms_text[m.start():]
    # Stop at the next question id like 2(h)(ii) or 3(a) or end-of-page footer.
    # We look for the next "<digit>(<letter>)" line at column ~4. Conservative:
    # split at "1 mark for each point" or next marker line.
    # Build candidate end markers.
    end_markers = [
        re.compile(r"^\s*1\s*mark\s+for\s+each\s+point", re.M),
        re.compile(r"^\s*\d+\(\w+\)(?:\(\w+\))?(?!\w)", re.M),
    ]
    skip_chars = len(re.match(r"\s*" + re.escape(marker), rest.lstrip()).group(0)) + (
        len(rest) - len(rest.lstrip())
    )
    earliest = len(rest)
    for em in end_markers:
        mm = em.search(rest, skip_chars)
        if mm and mm.start() < earliest:
            earliest = mm.start()
    block = rest[:earliest]

    # Now parse lettered bullets within block.
    # Each lettered bullet starts with a single uppercase letter A-Z preceded by
    # significant whitespace, then 2+ spaces, then text. Continuation lines may
    # follow with more indentation.
    lines = block.splitlines()
    pairs: list[tuple[str, str]] = []
    cur_letter: Optional[str] = None
    cur_lines: list[str] = []
    for ln in lines:
        m = LETTERED.match(ln)
        # Heuristic: the letter must be at the typical bullet column (somewhere
        # past the marker column). The first line containing the marker also
        # contains "A   ...". Capture that.
        if m:
            letter = m.group(2)
            # ensure it's a single char A..Z used as bullet (not a stray)
            if cur_letter is not None:
                pairs.append((cur_letter, " ".join(s.strip() for s in cur_lines).strip()))
            cur_letter = letter
            cur_lines = [m.group(3).rstrip()]
        else:
            if cur_letter is None:
                # might be the line that has marker + first letter on same line:
                # e.g. "2(h)(i)     A   text..."
                m2 = re.match(r"^\s*\d+\([a-z]+\)(?:\([ivx]+\))?\s+([A-Z])\s{2,}(.+)$", ln)
                if m2:
                    cur_letter = m2.group(1)
                    cur_lines = [m2.group(2).rstrip()]
                continue
            # continuation line
            stripped = ln.rstrip()
            if not stripped:
                continue
            # Drop trailing column with a "Marks" number (e.g. integer at right)
            stripped = re.sub(r"\s{4,}\d+\s*$", "", stripped)
            cur_lines.append(stripped.strip())
    if cur_letter is not None:
        pairs.append((cur_letter, " ".join(s.strip() for s in cur_lines).strip()))
    # Strip trailing "Marks" tail values that may have leaked into first text.
    cleaned: list[tuple[str, str]] = []
    for letter, text in pairs:
        text = re.sub(r"\s{2,}\d+\s*$", "", text).strip()
        cleaned.append((letter, text))
    return cleaned


SUBQ_FIRST_LETTER = re.compile(
    r"^\s*2\((?P<sub>[a-z]+)\)\(i\)\s+A\s{2,}", re.M
)
SUBQ_LIM_KEYWORD = re.compile(
    r"^\s*2\((?P<sub>[a-z]+)\)\(i\)\s+.+(?:not enough|valid conclusion|difficult to|sources of uncertainty)",
    re.M | re.I,
)


def find_lim_imp_markers(ms_text: str) -> tuple[Optional[str], Optional[str]]:
    """Autodetect the limitations and improvements sub-question markers.

    Strategy 1: lettered format - row like '2(<x>)(i) A   <text>'.
    Strategy 2: paragraph format - row like '2(<x>)(i) <prose limitation>',
                identified by characteristic phrases ('not enough', 'valid
                conclusion', 'difficult to', 'sources of uncertainty').
    """
    m = SUBQ_FIRST_LETTER.search(ms_text)
    if m:
        sub = m.group("sub")
        return f"2({sub})(i)", f"2({sub})(ii)"
    m = SUBQ_LIM_KEYWORD.search(ms_text)
    if m:
        sub = m.group("sub")
        return f"2({sub})(i)", f"2({sub})(ii)"
    return None, None


def extract_paragraph_block(ms_text: str, marker: str) -> list[str]:
    """For papers without lettered bullets - extract paragraph items from a row.

    Each non-empty 'paragraph' (run of lines separated by blank lines) inside
    the row body becomes one item.
    """
    pat = re.compile(r"^\s*" + re.escape(marker) + r"(?!\w)", re.M)
    m = pat.search(ms_text)
    if not m:
        return []
    rest = ms_text[m.start():]
    end_markers = [
        re.compile(r"^\s*\d+\(\w+\)(?:\(\w+\))?(?!\w)", re.M),
        re.compile(r"^\s*©\s*UCLES", re.M),
    ]
    # Skip past the marker line itself when looking for end markers (else we'd
    # match our own marker as 'end').
    skip_chars = len(re.match(r"\s*" + re.escape(marker), rest.lstrip()).group(0)) + (
        len(rest) - len(rest.lstrip())
    )
    earliest = len(rest)
    for em in end_markers:
        mm = em.search(rest, skip_chars)
        if mm and mm.start() < earliest:
            earliest = mm.start()
    block = rest[:earliest]
    # Strip leading whitespace and the marker prefix from the first line.
    block = re.sub(r"^\s*" + re.escape(marker) + r"\s*", "", block.lstrip())
    lines = block.splitlines()
    cleaned = []
    for ln in lines:
        s = ln.rstrip()
        s = re.sub(r"\s{2,}\d+\s*(?:max)?\s*$", "", s)
        cleaned.append(s.strip())
    paragraphs: list[str] = []
    cur: list[str] = []
    for s in cleaned:
        if s:
            cur.append(s)
        else:
            if cur:
                paragraphs.append(" ".join(cur).strip())
                cur = []
    if cur:
        paragraphs.append(" ".join(cur).strip())
    # filter empty/short
    paragraphs = [p for p in paragraphs if len(p) > 5]
    return paragraphs


# ---------- Rejection clauses & tags ----------

REJECT_CLAUSE = re.compile(r"\(not\s+([^)]+)\)", re.I)


def parse_rejections(section_text: str) -> list[str]:
    """From a MS section (e.g. the 2(h)(i) block), pull explicitly rejected
    answers from "(not ...)" clauses. Splits on commas, strips smart quotes.
    Filters out residue like "on its own" qualifiers when they leave nothing."""
    # Drop bare-number lines (the right-aligned marks column wraps into the
    # body when the rejection clause spans multiple visual lines).
    section_text = re.sub(r"\n\s+\d+\s*\n", "\n", section_text)
    out: list[str] = []
    for m in REJECT_CLAUSE.finditer(section_text):
        body = m.group(1)
        # Split on commas BUT only ones outside quotes - mark schemes use
        # "X", "Y" with curly quotes. Easier: replace curly quotes, split on ",
        # then strip surrounding straight quotes and single quotes.
        normalised = (
            body.replace("“", '"')
            .replace("”", '"')
            .replace("‘", "'")
            .replace("’", "'")
        )
        # Split on "," but respect quote groupings: extract quoted phrases first.
        quoted = re.findall(r'"([^"]+)"|\'([^\']+)\'', normalised)
        if quoted:
            for q in quoted:
                phrase = (q[0] or q[1]).strip()
                # Strip stray marks-column digits that wrapped into the phrase.
                phrase = re.sub(r"\s+\d+\s+", " ", phrase)
                phrase = re.sub(r"\s+", " ", phrase).strip()
                if phrase and len(phrase) > 2:
                    out.append(phrase)
        else:
            # No quotes - split on comma.
            for piece in normalised.split(","):
                p = piece.strip().strip("'\"")
                # Skip qualifiers / fragments that aren't standalone answers.
                if not p:
                    continue
                if p.lower() in {"on its own", "alone", "by itself"}:
                    continue
                if len(p) < 4:
                    continue
                out.append(p)
    # Dedup, preserve order.
    seen = set()
    uniq: list[str] = []
    for s in out:
        k = re.sub(r"\s+", " ", s).strip().lower()
        if k in seen:
            continue
        seen.add(k)
        uniq.append(re.sub(r"\s+", " ", s).strip())
    return uniq


def extract_block_text(ms_text: str, marker: str) -> str:
    """Return the raw text of the MS section starting at the marker."""
    pat = re.compile(r"^\s*" + re.escape(marker) + r"(?!\w)", re.M)
    m = pat.search(ms_text)
    if not m:
        return ""
    rest = ms_text[m.start():]
    # Stop at next sub-question marker or footer.
    for em in (
        re.compile(r"^\s*\d+\(\w+\)(?:\(\w+\))?(?!\w)", re.M),
        re.compile(r"^\s*©\s*UCLES", re.M),
    ):
        skip = len(re.match(r"\s*" + re.escape(marker), rest.lstrip()).group(0)) + (
            len(rest) - len(rest.lstrip())
        )
        mm = em.search(rest, skip)
        if mm:
            rest = rest[: mm.start()]
            break
    return rest


STOPWORDS = {
    # Articles, prepositions, conjunctions, pronouns
    "a", "an", "the", "of", "in", "on", "at", "to", "and", "or", "but",
    "with", "between", "for", "from", "by", "into", "as", "this", "that",
    "is", "was", "were", "be", "are", "you", "will", "your", "their",
    "its", "it", "some", "any", "have", "has", "had", "been", "being",
    # Generic experiment vocabulary that adds no apparatus signal
    "investigate", "experiment", "experiments", "use", "using", "uses",
    "different", "various", "varied", "varying", "value", "values",
    "amount", "amounts", "many", "several", "first", "second", "third",
    "two", "three", "four", "five",
    # Common procedure boilerplate appearing in nearly every Q2
    "need", "needed", "materials", "provided", "apparatus", "shown",
    "place", "placed", "set", "setup", "set-up", "stand", "boss",
    "clamp", "table", "above", "below", "before", "after", "when",
    "while", "should", "could", "may", "might", "approximately",
    "about", "make", "made", "carefully", "ensure", "record",
    "recorded", "measure", "measured", "measurement", "measurements",
    "calculate", "calculated", "shown", "show", "showing", "follow",
    "following", "step", "steps", "diagram", "fig", "figure",
}


def filter_corpus_specific_tags(questions: list[Question], threshold: float = 0.4) -> None:
    """Mutate questions in-place: drop tags that appear in more than `threshold`
    fraction of all questions (they're not discriminative for distractor
    clustering)."""
    if not questions:
        return
    counts: dict[str, int] = {}
    for q in questions:
        for t in set(q.tags):
            counts[t] = counts.get(t, 0) + 1
    total = len(questions)
    too_common = {t for t, c in counts.items() if c / total > threshold}
    for q in questions:
        q.tags = [t for t in q.tags if t not in too_common][:8]


def compute_tags(experiment_intro: str, procedure_text: str) -> list[str]:
    """Tokenize intro + first ~200 chars of procedure into lowercase keywords
    used for distractor clustering. Keep words >=4 chars, drop stopwords."""
    text = (experiment_intro or "") + " " + (procedure_text or "")[:400]
    text = text.lower()
    words = re.findall(r"[a-z][a-z\-]{3,}", text)
    out: list[str] = []
    seen = set()
    for w in words:
        if w in STOPWORDS:
            continue
        if w in seen:
            continue
        seen.add(w)
        out.append(w)
    return out[:12]  # cap


# ---------- Underline detection (pdfplumber) ----------

def detect_underlined_runs(page) -> list[tuple[str, float]]:
    """For one pdfplumber page, return list of (word_text, y_top) for underlined
    word runs. Underlines are detected as thin horizontal rects (h<2pt, w>=5pt)
    sitting just below a row of characters."""
    if page is None:
        return []
    out: list[tuple[str, float]] = []
    page_h = page.height
    for r in page.rects:
        h = abs(r["y1"] - r["y0"])
        w = abs(r["x1"] - r["x0"])
        if not (h < 2 and 5 < w < 250):
            continue
        rect_top_td = page_h - r["y1"]  # top-down y of the rect's top edge
        chars_above = [
            c for c in page.chars
            if c["x1"] >= r["x0"] and c["x0"] <= r["x1"]
            and abs(c["bottom"] - rect_top_td) < 3
        ]
        if not chars_above:
            continue
        text = "".join(ch["text"] for ch in sorted(chars_above, key=lambda c: c["x0"])).strip()
        if not text or text.isdigit() or len(text) < 2:
            continue
        # The text might be a phrase like "with a reason," - keep the whole run
        # but also split into word tokens for matching.
        out.append((text, rect_top_td))
    return out


def find_letter_y_positions(page, marker_subq: str) -> list[tuple[str, float, float]]:
    """For a Q2(h)(i) / 2(h)(ii) page, return list of (letter, y_top, x0)
    triples - one per A-J bullet found at the bullet column. We may see the
    same letter twice (once for limitations, once for improvements) if both
    sections are on the same page; both occurrences are returned."""
    if page is None:
        return []
    # Find the bullet column: the x0 most commonly occupied by isolated A-J
    # uppercase chars surrounded by whitespace.
    rows: dict[int, list] = {}
    for c in page.chars:
        key = round(c["top"] / 1.5)
        rows.setdefault(key, []).append(c)
    candidates: list[tuple[str, float, float]] = []
    from collections import Counter
    x_counter: Counter[int] = Counter()
    raw: list[tuple[str, float, float]] = []
    for _, chs in sorted(rows.items()):
        chs = sorted(chs, key=lambda c: c["x0"])
        for i, c in enumerate(chs):
            if c["text"] not in "ABCDEFGHIJ":
                continue
            prev_t = chs[i - 1]["text"] if i > 0 else " "
            next_t = chs[i + 1]["text"] if i + 1 < len(chs) else " "
            if prev_t == " " and next_t == " ":
                raw.append((c["text"], c["top"], c["x0"]))
                x_counter[round(c["x0"])] += 1
    if not raw:
        return []
    # The bullet column is the most-frequent x0 value among raw candidates.
    bullet_x, bullet_count = x_counter.most_common(1)[0]
    # Require at least 3 distinct lettered bullets at the same column - else
    # the "letters" we found are likely incidental (e.g. variable names like
    # "B" in "measure B"), not real bullet markers. Without this guard,
    # paragraph-format MSs (e.g. m19) produce nonsense underline attributions.
    if bullet_count < 3:
        return []
    for L, y, x in raw:
        if abs(x - bullet_x) <= 1:
            candidates.append((L, y, x))
    # Also need at least 3 distinct letters to be confident this is a bullet
    # column, not an inline variable.
    distinct_letters = {L for L, _, _ in candidates}
    if len(distinct_letters) < 3:
        return []
    candidates.sort(key=lambda t: t[1])
    return candidates


def collect_underlines_for_pairs(ms_pdf: Path, pairs: list[Pair],
                                  lim_marker: Optional[str],
                                  imp_marker: Optional[str]) -> None:
    """Mutate `pairs` in place, populating each pair's underlined_in_*
    fields by correlating underline rects with the bullet they sit under."""
    if pdfplumber is None:
        return
    try:
        with pdfplumber.open(ms_pdf) as pdf:
            # Find pages relevant to lim/imp markers.
            for page in pdf.pages:
                txt = page.extract_text() or ""
                has_lim = lim_marker and lim_marker in txt
                has_imp = imp_marker and imp_marker in txt
                if not (has_lim or has_imp):
                    continue
                underlines = detect_underlined_runs(page)
                if not underlines:
                    continue
                bullets = find_letter_y_positions(page, lim_marker or imp_marker or "")
                if not bullets:
                    continue
                # Locate the y of the (ii) marker line so we can split bullets
                # into limitation vs improvement sections.
                imp_y = None
                if has_imp and imp_marker:
                    rows: dict[int, list] = {}
                    for c in page.chars:
                        key = round(c["top"] / 1.5)
                        rows.setdefault(key, []).append(c)
                    for _, chs in sorted(rows.items()):
                        line = "".join(c["text"] for c in sorted(chs, key=lambda c: c["x0"]))
                        if imp_marker in line:
                            imp_y = chs[0]["top"]
                            break

                # For each underline, find the LATEST bullet whose y <= underline.y.
                # That's the bullet the underline belongs to.
                for text, y_top in underlines:
                    chosen = None
                    for L, ly, _ in bullets:
                        if ly <= y_top + 1:
                            chosen = (L, ly)
                        else:
                            break
                    if not chosen:
                        continue
                    L, ly = chosen
                    in_imp = imp_y is not None and ly >= imp_y - 0.5
                    target = next((p for p in pairs if p.letter == L), None)
                    if not target:
                        continue
                    bucket = target.underlined_in_improvement if in_imp else target.underlined_in_limitation
                    norm = re.sub(r"\s+", " ", text).strip().rstrip(",.;:")
                    if norm and norm.lower() not in {x.lower() for x in bucket}:
                        bucket.append(norm)
    except Exception as e:
        # Underline detection is best-effort; don't fail extraction on errors.
        print(f"  underline detection failed on {ms_pdf.name}: {e}", file=sys.stderr)


def extract_pairs(ms: Path) -> tuple[list[Pair], list[str]]:
    warns: list[str] = []
    full = pdftotext_layout(ms)
    lim_marker, imp_marker = find_lim_imp_markers(full)
    if not lim_marker:
        warns.append("could not autodetect limitations sub-question marker")
        return [], warns
    lims = extract_letters_block(full, lim_marker)
    imps = extract_letters_block(full, imp_marker) if imp_marker else []
    if not lims:
        # Fallback: paragraph format (no lettered bullets), pair positionally.
        lim_paras = extract_paragraph_block(full, lim_marker)
        imp_paras = extract_paragraph_block(full, imp_marker) if imp_marker else []
        if not lim_paras:
            warns.append(f"no limitations parsed at {lim_marker} (lettered or paragraph)")
            return [], warns
        warns.append(f"used paragraph fallback parser at {lim_marker}")
        n = max(len(lim_paras), len(imp_paras))
        out: list[Pair] = []
        for i in range(n):
            letter = chr(ord("A") + i)
            lim = lim_paras[i] if i < len(lim_paras) else ""
            imp = imp_paras[i] if i < len(imp_paras) else ""
            if lim and not imp:
                warns.append(f"paragraph {letter} (limitation) has no matching improvement")
            out.append(Pair(letter=letter, limitation=lim, improvement=imp))
        return out, warns
    if not imps:
        warns.append(f"no improvements parsed at {imp_marker}")
    by_letter_imp = dict(imps)
    pairs: list[Pair] = []
    for letter, lim_text in lims:
        imp_text = by_letter_imp.pop(letter, "")
        if not imp_text:
            warns.append(f"limitation {letter} has no matching improvement")
        pairs.append(Pair(letter=letter, limitation=lim_text, improvement=imp_text))
    for letter, imp_text in by_letter_imp.items():
        warns.append(f"improvement {letter} has no matching limitation; appended as orphan")
        pairs.append(Pair(letter=letter, limitation="", improvement=imp_text))
    return pairs, warns


# ---------- Top-level driver ----------


def process_pair(qp: Path, ms: Path, render_diagrams: bool = True) -> Question:
    stem = qp.stem  # e.g. 9702_s23_qp_v1
    parts = stem.split("_")
    # parts = ['9702', 's23', 'qp', 'v1']
    sess_code = parts[1]
    sess_letter = sess_code[0]
    yy = sess_code[1:]
    label = f"{SESSION_LABELS.get(sess_letter, '?')} 20{yy}"
    qid = f"{parts[0]}_{sess_code}_{parts[3]}"

    q = Question(
        id=qid,
        session_code=sess_code,
        session_label=label,
        variant_pmt=parts[3],
    )
    q.paper_code = extract_paper_code(qp)

    try:
        first, last, h_page = find_q2_page_range(qp)
    except Exception as e:
        q.extraction_warnings.append(f"Q2 page range: {e}")
        return q

    if first < 0:
        q.extraction_warnings.append("could not locate Q2 in QP")
    else:
        proc_text, intro = extract_procedure_text(qp, first, h_page)
        q.procedure_text = proc_text
        q.experiment = intro
        if render_diagrams:
            try:
                q.page_images_b64 = render_pages_to_b64(qp, first, max(first, h_page - 1))
            except Exception as e:
                q.extraction_warnings.append(f"page render: {e}")

    pairs, warns = extract_pairs(ms)
    q.pairs = pairs
    q.extraction_warnings.extend(warns)

    # Rejection clauses (Tier 1 distractors).
    full_ms = pdftotext_layout(ms)
    lim_marker, imp_marker = find_lim_imp_markers(full_ms)
    if lim_marker:
        q.rejected_limitations = parse_rejections(extract_block_text(full_ms, lim_marker))
    if imp_marker:
        q.rejected_improvements = parse_rejections(extract_block_text(full_ms, imp_marker))

    # Underlined keywords per pair (mark scheme uses underline to indicate
    # required words - perfect for "slight variation" distractor generation).
    collect_underlines_for_pairs(ms, q.pairs, lim_marker, imp_marker)

    # Apparatus tags.
    q.tags = compute_tags(q.experiment, q.procedure_text)
    return q


def find_pairs() -> list[tuple[Path, Path]]:
    out = []
    for qp in sorted(PAPERS.glob("9702_*_qp_*.pdf")):
        ms = qp.parent / qp.name.replace("_qp_", "_ms_")
        if ms.exists():
            out.append((qp, ms))
    return out


def main():
    only = set(sys.argv[1:])  # optionally filter by stem
    questions: list[Question] = []
    pairs = find_pairs()
    if only:
        pairs = [(qp, ms) for qp, ms in pairs if qp.stem in only]
    print(f"processing {len(pairs)} QP/MS pairs", file=sys.stderr)
    for i, (qp, ms) in enumerate(pairs, 1):
        print(f"[{i}/{len(pairs)}] {qp.name}", file=sys.stderr)
        q = process_pair(qp, ms, render_diagrams=True)
        questions.append(q)
        if q.extraction_warnings:
            for w in q.extraction_warnings:
                print(f"  WARN: {w}", file=sys.stderr)
    filter_corpus_specific_tags(questions)
    out = {
        "schema_version": 1,
        "questions": [
            {**asdict(q), "pairs": [asdict(p) for p in q.pairs]} for q in questions
        ],
    }
    out_path = DATA / "questions.json"
    out_path.write_text(json.dumps(out, indent=2, ensure_ascii=False))
    total_imgs = sum(len(q.page_images_b64) for q in questions)
    total_pairs = sum(len(q.pairs) for q in questions)
    print(
        f"wrote {out_path} - {len(questions)} questions, {total_pairs} lim/imp pairs, "
        f"{total_imgs} diagram pages, {out_path.stat().st_size//1024} KB",
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
