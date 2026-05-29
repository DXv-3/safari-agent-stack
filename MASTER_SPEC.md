# DXv-3 Safari Agent Stack — Master Specification

**Owner:** Vinny Gilberti · [@DXv-3](https://github.com/DXv-3)  
**Repos:** [`safari-agent-stack`](https://github.com/DXv-3/safari-agent-stack) · [`gitreverse-hub`](https://github.com/DXv-3/gitreverse-hub)  
**Runtime:** iPad Pro · Pythonista 3 · Local LLM Server · Safari · Userscripts

---

## What This Is

A fully self-contained, on-device AI agent stack that runs entirely on iPad. No cloud APIs required. No Mac bridge required. A local LLM generates code, a FastAPI Kernel orchestrates everything, a Safari userscript captures and executes in-browser, and six Vinhub iOS Shortcuts are the human trigger layer. The Shortcut Builder OS sits on top, turning any idea into an importable iOS Shortcut via a 6-agent LLM pipeline. gitreverse-hub feeds it a corpus of 408 starred repos as persistent memory.

The system is self-coding. Browse a GitHub repo → it generates a script for that site. That script improves the browsing experience → which surfaces more repos → which generate more scripts.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  HUMAN LAYER                                                │
│  6 Vinhub iOS Shortcuts  ·  Siri  ·  Back-Tap              │
└───────────────────────┬─────────────────────────────────────┘
                        │ HTTP POST/GET
┌───────────────────────▼─────────────────────────────────────┐
│  KERNEL  (kernel.py · FastAPI · http://127.0.0.1:8000)      │
│  /ingest  /reverse  /generate  /memory  /queue  /health     │
│  /shortcut/build  (Shortcut Builder OS extension)           │
│  SQLite memory  ·  on-device LLM via Local LLM Server       │
└──────┬───────────────────────────┬───────────────────────────┘
       │ polls /queue              │ writes scripts
┌──────▼──────────┐   ┌───────────▼──────────────────────────┐
│  SATELLITE      │   │  PERSISTENCE HOOK  (persistence_hook.py)│
│  SATELLITE.user.js│  │  Watches output dir · installs .user.js│
│  Safari userscript│  │  into Userscripts app container       │
│  DOM capture    │   └──────────────────────────────────────┘
│  RepoCard extract│
│  sandboxed eval │
│  toast notify   │
└──────┬──────────┘
       │
┌──────▼──────────────────────────────────────────────────────┐
│  GITREVERSE-HUB  (TypeScript · Node.js)                     │
│  src/safari-bridge  ·  src/repo-scorer  ·  src/hermes       │
│  src/wrapper-gen   ·  src/aal  ·  src/ability-registry      │
│  src/seed  ·  src/dashboard                                 │
│  Feeds 408 starred repos into Kernel memory                 │
└─────────────────────────────────────────────────────────────┘
```

---

## Components

### 1. Kernel — `kernel.py`

The single Python process that runs in Pythonista. Everything routes through it.

| Endpoint | Method | Does |
|----------|--------|------|
| `/health` | GET | Returns `{status, model, uptime}` |
| `/ingest` | POST | Stores page visit / RepoCard to SQLite memory |
| `/reverse` | POST | Fetches repo via gitingest → LLM → returns PromptParts JSON |
| `/generate` | POST | task + context → LLM → writes `.user.js` to device |
| `/memory` | GET | Query SQLite memory with domain/keyword filter |
| `/queue` | POST | Enqueue command for active Satellite session |
| `/command` | GET | Satellite polls this — returns next queued action |
| `/shortcut/build` | POST | Runs full 6-agent Shortcut Builder OS pipeline |

**Data model (SQLite):**
```sql
CREATE TABLE memory (
  id INTEGER PRIMARY KEY,
  session_id TEXT,
  url TEXT,
  domain TEXT,
  title TEXT,
  body_text TEXT,
  repo_card JSON,
  created_at TIMESTAMP
);
CREATE TABLE queue (
  id INTEGER PRIMARY KEY,
  session_id TEXT,
  action TEXT,  -- eval_code | navigate | toast
  payload TEXT,
  delivered INTEGER DEFAULT 0,
  created_at TIMESTAMP
);
```

---

### 2. Satellite — `SATELLITE.user.js`

The Safari-side agent. Runs on every page load via Userscripts extension.

**Per-page actions:**
1. Capture DOM snapshot (title, URL, visible text, meta)
2. If `github.com/*/*` — extract RepoCard (owner, repo, description, stars, language, file tree from DOM)
3. POST RepoCard + page data to Kernel `/ingest`
4. Poll Kernel `/command` every 3 seconds
5. Execute queued actions in sandboxed iframe: `eval_code` / `navigate` / `toast`
6. Inject **⚡ GitReverse** button on GitHub repo pages → opens `gitreverse.com/owner/repo`
7. On `gitreverse.com` — extract generated prompt → clipboard → POST to `/ingest`

---

### 3. Persistence Hook — `persistence_hook.py`

File watcher running in background. Watches the Kernel script output directory. On new `.user.js` file → copies into Userscripts app container at `On My iPad/Userscripts/`. Logs every install to SQLite.

---

### 4. Vinhub Shortcuts — 6 Triggers

All shortcuts call `http://127.0.0.1:8000`. All use `Get Contents of URL` with `Content-Type: application/json`.

| # | Name | Trigger | Kernel Endpoint | Output |
|---|------|---------|----------------|--------|
| 1 | **Vinhub Start** | Back-tap triple / Siri / morning | `GET /health` | Green notification if online |
| 2 | **Vinhub Reverse** | Safari Share Sheet | `POST /reverse` | PromptParts JSON → clipboard |
| 3 | **Vinhub Generate** | Siri / manual | `POST /generate` | `.user.js` written to device |
| 4 | **Vinhub Memory** | Manual | `GET /memory` | Choose from list → copy URL |
| 5 | **Vinhub Queue** | Back-tap double | `POST /queue` | Command injected → Satellite picks up in ≤3s |
| 6 | **Vinhub Build** | Siri / manual | `POST /shortcut/build` | Full iOS Shortcut JSON + install instructions |

**Back-tap config:** Settings → Accessibility → Touch → Back Tap
- Double tap → Vinhub Queue
- Triple tap → Vinhub Start

**Siri phrases:** "reverse this repo" · "generate a script" · "start the kernel" · "Vinhub Build"

---

### 5. Shortcut Builder OS — 6-Agent Pipeline

Activated by `POST /shortcut/build {"idea": "..."}`. Runs entirely on-device via local LLM.

```
IDEA (any format)
  → INTENT   → intent.md        scope lock: trigger, I/O types, Kernel needed y/n
  → DESIGN   → blueprint.md     real iOS action names, kernel_calls flagged, bridges flagged
  → BUILD    → shortcut.json    valid WFWorkflow JSON, real WFActionIdentifiers only
  → TEST     → test_report.md   happy path + 2 failure paths + variable check + HTTP check
  → VALIDATE → APPROVED         or fix_request.md back to BUILD (max 2 loops)
  → REGISTRY → registry entry + install_instructions.md
                 written to Documents/ShortcutBuilderOS/[run_id]/
                 appended to Documents/shortcuts_registry.json
```

**Artifacts per run** (saved to `Documents/ShortcutBuilderOS/[run_id]/`):
- `intent.md` · `blueprint.md` · `shortcut.json` · `test_report.md` · `shortcut_final.json` · `install_instructions.md`

**Rules enforced by every agent:**
- Real `WFActionIdentifier` values only — never invented
- All HTTP calls include `Content-Type: application/json`
- Kernel assumed at `http://127.0.0.1:8000`
- Pythonista bridge via `pythonista3://run?script=X`
- StackBlitz/WebContainer bridge via `https://node.new`
- Max 2 BUILD↔VALIDATE loops before escalating to user

---

### 6. gitreverse-hub Bridge — `src/safari-bridge/`

TypeScript module wiring gitreverse-hub's existing pipeline into the Kernel.

**Module map:**

| gitreverse-hub module | Bridge call | Kernel endpoint |
|----------------------|-------------|----------------|
| `src/repo-scorer` | `pushRepoCard()` | `POST /ingest` |
| `src/hermes` | `decomposeRepo()` | `POST /reverse` |
| `src/wrapper-gen` | `pullGeneratedScript()` | `POST /generate` |
| `src/aal` | `triggerShortcutBuild()` | `POST /shortcut/build` |
| `src/ability-registry` | `queueSatelliteCommand()` | `POST /queue` |
| `src/seed` | `pushRepoCard()` loop | `POST /ingest` ×408 |
| `src/dashboard` | All of the above | All endpoints |

**Power calls:**
```typescript
// Repo → .user.js + Safari toast in one call
const result = await reverseAndGenerate('https://github.com/owner/repo');

// Repo → iOS Shortcut JSON in one call
const payload = await Vinhub.reverseAndBuild('https://github.com/owner/repo');
const shortcut = await fetch(`${KERNEL}/shortcut/build`, { method:'POST', body: JSON.stringify(payload) });
```

---

### 7. Bulk Seed — 408 Starred Repos

Two seeders, same logic, different runtimes:

| File | Runtime | Batch | Delay |
|------|---------|-------|-------|
| `src/seed/seed-kernel.ts` | Node.js | 10 concurrent | 1.5s |
| `src/seed/seed-kernel-python.py` | Pythonista 3 (iPad) | 5 sequential | 2.0s |

**Per repo:**
1. GitHub API fetch (public, no token needed; `GITHUB_TOKEN` env var unlocks higher rate limits)
2. `POST /ingest` → SQLite row written
3. `POST /reverse` → PromptParts decomposed → atoms stored
4. Entry written to `Documents/seed_kernel_log.json`

**Resume-safe:** re-run anytime. Already-seeded repos skipped via log.
**Completion signal:** Satellite receives toast on active Safari tab.

**Fast mode** (ingest only, skip LLM decomposition):
```
npx ts-node src/seed/seed-kernel.ts --decompose=false
# ~5 min for 408 repos vs ~60 min with decompose
```

---

## Full Self-Coding Loop

```
1. Safari opens github.com/owner/repo
2. Satellite extracts RepoCard → POST /ingest → memory stored
3. gitreverse-hub hermes calls decomposeRepo() → PromptParts produced
4. wrapper-gen calls pullGeneratedScript(build_prompt) → .user.js written
5. persistence_hook.py detects new file → installs to Userscripts
6. Safari Extensions → new script active on target site
7. Script runs → captures more data → POST /ingest → memory grows
8. Repeat
```

The loop is fully automatic after step 1. No human action required between steps 2–7.

---

## Setup — 8 Steps

1. Install **Pythonista 3** + **Local LLM Server** + **Userscripts** from App Store
2. Load a model in Local LLM Server (Llama 3.2 3B recommended for speed)
3. Copy `kernel.py` into Pythonista → Run → Kernel live at `127.0.0.1:8000`
4. Run `persistence_hook.py` in a second Pythonista tab
5. Drop `SATELLITE.user.js` into `On My iPad/Userscripts/`
6. Safari → Settings → Extensions → Userscripts → Allow for all sites
7. Build all 6 Vinhub shortcuts in Shortcuts app (specs in `shortcuts/VINHUB_SHORTCUTS.md`)
8. (Optional) Run seed: `pythonista3://run?script=seed-kernel-python` — loads 408 repos into memory

---

## Environment Variables

| Var | Required | Default | Notes |
|-----|----------|---------|-------|
| `SAFARI_KERNEL_URL` | No | `http://127.0.0.1:8000` | Override for LAN access from Mac |
| `GITHUB_TOKEN` | No | — | Raises API rate limit from 60 to 5000 req/hr |
| `LLM_BASE_URL` | No | `http://localhost:1234/v1` | Local LLM Server default port |
| `LLM_MODEL` | No | `llama-3.2-3b` | Match model loaded in Local LLM Server |

---

## File Index

### `DXv-3/safari-agent-stack`
```
SATELLITE.user.js                     Safari userscript agent
kernel.py                             FastAPI Kernel — all endpoints
persistence_hook.py                   File watcher → auto-installs scripts
brainstorm_prompt.md                  LLM activation prompt with stack context
gitreverse_integration.md            RepoCard schema + chain wiring guide
README.md                             8-step setup
shortcuts/
  VINHUB_SHORTCUTS.md                 All 6 Vinhub shortcut specs
shortcut_builder_os/
  skill.md                            6-agent team spec (drop into any LLM)
  agent_team.md                       All 6 agent system prompts verbatim
  kernel_extension.py                 POST /shortcut/build route + agent dispatcher
  orchestrator_prompt.md              Manual activation prompt + Vinhub Build shortcut
MASTER_SPEC.md                        ← this file
```

### `DXv-3/gitreverse-hub`
```
src/safari-bridge/
  index.ts                            6 exported Kernel bridge functions
  vinhub.ts                           Vinhub payload builders + reverseAndBuild()
src/seed/
  seed-registry.ts                    Existing ability registry seeder
  seed-kernel.ts                      New: bulk seed 408 repos → Kernel (Node.js)
  seed-kernel-python.py               New: bulk seed 408 repos → Kernel (Pythonista)
SAFARI_AGENT_INTEGRATION.md          Module map + flow examples + env var docs
[existing modules unchanged]
  src/aal  src/ability-registry  src/dashboard
  src/hermes  src/repo-scorer  src/server  src/wrapper-gen
```

---

## Constraints

- All scripts must run without a Mac. iPad-only.
- No paid cloud APIs in the critical path. Local LLM only.
- Kernel is always `http://127.0.0.1:8000`. No hostname changes.
- Userscripts app is the only Safari extension needed besides the Satellite itself.
- `WFActionIdentifier` values in generated shortcuts must be real. No invented identifiers.
- Seed log is the source of truth for what's in memory. Never truncate it.
- All generated `.user.js` files are installed automatically. No manual drag-and-drop after initial setup.
- BUILD↔VALIDATE loops cap at 2. Escalate to user if unresolved after 2 passes.
