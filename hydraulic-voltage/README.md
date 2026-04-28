# Hydraulic Voltage

An interactive browser simulation teaching the hydraulic analogy of electric circuits:

| Hydraulic | Electrical |
|-----------|------------|
| Pump | Battery / EMF source |
| Water pressure (height difference) | Voltage |
| Flow rate | Current |
| Permeable barrier | Resistor |
| Wide-chamber standpipe | Capacitor |
| One-way valve | Diode |

## Features

- Axonometric side view with real water-height physics
- Barriers whose hatch density encodes resistance (more lines = more resistance)
- Parallel channels (same elevation — gravity-symmetric)
- Capacitor slot: large-area chamber shows RC charging curve
- Diode slot: one-way valve with forward/reverse toggle
- Drag the pump slider to power up; watch flow and pressures respond
- Add ΔP (voltage) probes between any two nodes
- Add flow (current) probes on any pipe segment
- Toggle schematic mode to overlay a standard circuit diagram at the same scale
- Readouts in both natural units (Pa, L/s) and electrical-equivalent units (V, A)

## Project structure

```
Code.gs          — Apps Script server: doGet() + include() helper
index.html       — Main HTML, pulls in all partials via <?!= include('…') ?>
style.html       — CSS (one <style> block)
js-config.html   — All constants (CONFIG tree)
js-math.html     — solveLinear, MNA stamp helpers, clamp/lerp
js-project.html  — project(x,y,z), axonometric helpers
js-model.html    — HNode, HEdge, Slot, Probe classes + STATE
js-layout.html   — layoutFromSlots(): slot list → 3D nodes/edges/geometry
js-solver.html   — MNA solver, diode iteration, tank height integration
js-render.html   — Canvas drawing (world, water, barriers, particles, schematic)
js-ui.html       — Slot carousel, param panel, probes, controls
js-main.html     — init, RAF loop, particle advection
appsscript.json  — GAS manifest (V8 runtime, anonymous web-app access)
```

## Deploying to Google Apps Script

### First-time setup

1. Go to [script.google.com](https://script.google.com) → **New project** → rename it **Hydraulic Voltage**.
2. Delete the default `Code.gs` that Google creates.
3. Copy each file from this repo into the GAS editor:
   - **`.gs` files** → File → New → **Script** → enter the filename without `.gs` → paste contents.
   - **`.html` files** → File → New → **HTML** → enter the filename without `.html` → paste contents.
4. Open the manifest: **Project Settings** → tick **"Show `appsscript.json`"** → paste the contents of `appsscript.json` from this repo.
5. Save all files (Ctrl+S or ⌘+S).

### Deploy as a web app

1. **Deploy** → **New deployment** → type **Web app**.
2. Set:
   - **Execute as**: Me
   - **Who has access**: Anyone (including anonymous)
3. Click **Deploy** → copy the `/exec` URL.

### Embed in Google Sites

1. In the Sites editor → **Insert** → **Embed** → **By URL**.
2. Paste the `/exec` URL → place on the page.
3. Resize the embed to at least **1200 × 760 px** for best results.

> **Why it works without sign-in:** `Code.gs` calls `setXFrameOptionsMode(ALLOWALL)` and `appsscript.json` sets `"access": "ANYONE_ANONYMOUS"`.

### Updating after code changes

1. Edit files locally, commit to git.
2. Re-paste changed files into the GAS editor.
3. **Deploy** → **Manage deployments** → edit the existing deployment → **Version: New version** → **Deploy**.
4. The `/exec` URL stays the same; the updated code is served immediately.

> **Tip:** Treat the GAS editor as a deploy target only — always edit here in git and paste across. This keeps git as the source of truth and prevents drift.

## Physics notes

The solver uses **Modified Nodal Analysis (MNA)** each animation frame:

- All inter-barrier chambers are treated as *Dirichlet* nodes (pressure = water height h).
- Only the two pump junction nodes are solved each frame (matrix is at most 3×3).
- Barrier flow: Q = k · (h_upstream − h_downstream) — directly analogous to Ohm's law.
- Tank heights integrate with semi-implicit Euler: Δh = dt · Q_net / A_tank.
- Diodes iterate up to 6 times per frame: start assuming forward conduction, flip if Q < 0, re-solve.
- The pump is modelled as an ideal voltage source (enforces pressure difference = dP).
