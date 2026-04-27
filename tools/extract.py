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
