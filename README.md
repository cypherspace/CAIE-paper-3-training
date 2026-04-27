# CAIE 9702 Paper 3 Q2 Trainer

A web app to train CAIE A-Level Physics 9702 students on Question 2 of Paper 3 (limitations and improvements).

The deliverable is a single self-contained HTML file (`physics-paper-3-q2-trainer.html`) embeddable in Google Sites.

## Repo layout

- `papers/` — drop your downloaded QP and MS PDFs here (see filename convention below)
- `tools/` — extraction and build scripts (auto-generated, not shipped)
- `data/` — generated `questions.json` with extracted limitations/improvements (auto-generated)

## Filename convention for PDFs

Use the official CAIE pattern:
- `9702_<session><yy>_qp_<variant>.pdf` for question papers
- `9702_<session><yy>_ms_<variant>.pdf` for mark schemes

Where:
- `<session>` = `s` (May/June) or `w` (Oct/Nov)
- `<yy>` = two-digit year (`18` through `24`)
- `<variant>` = `31`, `32`, `33` (and `34`/`35` if available)

Examples:
- `9702_s23_qp_32.pdf` = May/June 2023, variant 32, question paper
- `9702_w19_ms_33.pdf` = Oct/Nov 2019, variant 33, mark scheme

PMT files named `June 2023 (v1) QP.pdf` map to `9702_s23_qp_31.pdf` (v1=31, v2=32, v3=33).

## How to upload PDFs (browser, no command line)

1. Download QPs and MSs from https://www.physicsandmathstutor.com/past-papers/a-level-physics/cie-paper-3/
2. Rename them to the convention above
3. In GitHub web UI: navigate into `papers/`, click **Add file → Upload files**, drag PDFs in, commit directly to this branch
