# safari-agent-stack

> Self-coding iPad Safari userscript agent. Zero cloud APIs. Zero paid keys.

**Operator:** Vinny Gilberti · DXv-3 · May 2026

## Stack

| Layer | File | Runs In |
|-------|------|---------|
| Satellite | `SATELLITE.user.js` | Safari (Userscripts app) |
| Kernel | `kernel.py` | Pythonista 3 on iPad |
| Persistence | `persistence_hook.py` | Pythonista 3 on iPad |
| LLM | Local LLM Server app | On-device (M-series / A17 Pro) |

## Setup

1. Install [Userscripts](https://apps.apple.com/us/app/userscripts/id1463298887) from App Store
2. Install [Pythonista 3](https://apps.apple.com/us/app/pythonista-3/id1085978097) from App Store
3. Install [Local LLM Server](https://apps.apple.com/us/app/local-llm-server/id6757007308) from App Store — download `llama-3.2-3b`
4. Copy `kernel.py` + `persistence_hook.py` into Pythonista Documents
5. Run `kernel.py` in Pythonista — server starts at `http://127.0.0.1:8000`
6. Drop `SATELLITE.user.js` into `On My iPad/Userscripts/`
7. Safari → Settings → Extensions → Userscripts → Allow
8. Navigate to any site — agent is live

## iOS Shortcut Trigger

To restart Kernel manually:
```
pythonista3://run?script=kernel
```

## Constraints
- No `GM_*` APIs — native `fetch()` only (iOS Tampermonkey GM support is patchy)
- New `.user.js` files require one manual Enable tap in Safari → Extensions
- True Playwright cannot run on iPadOS — `MutationObserver` + DOM IS the automation
- All LLM calls stay on-device — zero recurring API cost

## Pipeline
```
iPad Safari
  → Satellite captures DOM / GitHub page
  → POST /ingest to Kernel
  → Kernel builds RepoCard (if GitHub)
  → GitReverse Decomposer runs via Local LLM
  → LLM generates new .user.js
  → persistence_hook.py writes to On My iPad/Userscripts/
  → Vinhub iOS Shortcut triggers repeat run
```
