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
