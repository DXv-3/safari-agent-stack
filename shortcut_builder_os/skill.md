# SKILL: iOS Shortcut Builder OS

**Version:** 2.0 — safari-agent-stack integration
**Operator:** Vinny Gilberti · DXv-3
**Runtime:** 6-agent team dispatched by Kernel at `http://127.0.0.1:8000/shortcut/build`

---

## PURPOSE

Takes any idea, vague or specific, and produces a complete, executable iOS Shortcut — as valid JSON/plist — using a 6-agent pipeline. Each agent has a single responsibility and hands off a structured artifact to the next. The Kernel orchestrates all 6. Vinhub shortcuts are the human trigger layer.

---

## AGENTS

### AGENT 1 — INTENT
- **Input:** Raw idea string (any format, any length)
- **Output:** `intent.md` — locked scope document
- **Does:**
  - Extracts the single core action the shortcut must perform
  - Identifies trigger type: manual / Siri / Share Sheet / back-tap / automation
  - Identifies input type: text / URL / clipboard / file / Ask Each Time
  - Identifies output type: clipboard / notification / open URL / file / speak
  - Asks ≤2 clarifying questions IF scope is genuinely ambiguous — otherwise locks immediately
- **Handoff:** `intent.md` → DESIGN

### AGENT 2 — DESIGN
- **Input:** `intent.md`
- **Output:** `blueprint.md` — action-by-action flow map
- **Does:**
  - Maps intent to real iOS Shortcuts actions (exact action names from Shortcuts app)
  - Identifies where native actions are insufficient → flags for Scriptable / Pythonista / Kernel bridge
  - Specifies data flow between every action step
  - Flags any Vinhub Kernel calls needed (which endpoint, what payload)
  - Flags any StackBlitz/WebContainer steps if Node.js runtime needed
- **Handoff:** `blueprint.md` → BUILD

### AGENT 3 — BUILD
- **Input:** `blueprint.md`
- **Output:** `shortcut.json` — complete importable Shortcut JSON
- **Does:**
  - Generates valid Apple Shortcuts JSON (WFWorkflowActions array)
  - Every action uses real WFActionIdentifier values
  - Includes all parameters, variable bindings, and conditionals
  - Embeds Vinhub Kernel HTTP calls where blueprint flagged them
  - Adds error handling: If Kernel offline → fallback behavior
- **Handoff:** `shortcut.json` + `blueprint.md` → TEST

### AGENT 4 — TEST
- **Input:** `shortcut.json` + `blueprint.md`
- **Output:** `test_report.md`
- **Does:**
  - Traces every action path (happy path + 2 failure paths)
  - Verifies all variable bindings are valid
  - Checks all HTTP calls have correct method/headers/body
  - Flags any actions that require specific iOS version or entitlement
  - Flags any Kernel endpoint that must exist before shortcut runs
- **Handoff:** `test_report.md` + `shortcut.json` → VALIDATE

### AGENT 5 — VALIDATE
- **Input:** `test_report.md` + `shortcut.json`
- **Output:** `shortcut_final.json` (approved) OR `fix_request.md` (back to BUILD)
- **Does:**
  - Accepts if: all paths traced, no unbound variables, all HTTP calls valid
  - Rejects if: any critical failure path unhandled, any made-up action identifiers
  - On reject: writes precise `fix_request.md` → sends back to BUILD (max 2 loops)
  - On accept: signs off, passes to REGISTRY
- **Handoff:** `shortcut_final.json` → REGISTRY

### AGENT 6 — REGISTRY
- **Input:** `shortcut_final.json` + `intent.md`
- **Output:** Registry entry written to `agent_memory.db` + install instructions
- **Does:**
  - Extracts reusable snippets (HTTP call patterns, variable patterns, conditionals) → saves as atoms
  - Writes entry to Kernel memory DB: name, trigger, endpoints_used, created_at, json_hash
  - Checks Kernel /memory for duplicate workflows before saving
  - Outputs final install instructions: import URL or manual step list
  - Updates `shortcuts_registry.json` in Documents
- **Handoff:** Done. Notify user via Vinhub toast.

---

## ARTIFACTS PER RUN

```
Documents/ShortcutBuilderOS/[run_id]/
  intent.md
  blueprint.md
  shortcut.json
  test_report.md
  shortcut_final.json
  install_instructions.md
```

---

## CONSTRAINTS

- Only use real WFActionIdentifier values — never invent action names
- Every HTTP call to Kernel must include Content-Type: application/json
- Shortcuts targeting Kernel assume it's at http://127.0.0.1:8000
- If a step requires Pythonista, use URL scheme: `pythonista3://run?script=X`
- If a step requires StackBlitz, use URL: `https://node.new`
- Max 2 BUILD→VALIDATE loops before escalating to user
