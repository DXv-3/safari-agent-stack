# Vinhub iOS Shortcuts — safari-agent-stack Integration

> One-tap triggers for every Kernel endpoint. No paid APIs. No Mac required.

---

## Prerequisites

- Kernel running in Pythonista: `pythonista3://run?script=kernel`
- Local LLM Server app open + model loaded
- SATELLITE.user.js enabled in Safari Extensions

---

## Shortcut 1 — Vinhub: Reverse Any Repo

**Trigger:** Share Sheet from Safari (GitHub URL) or manual paste
**Does:** Takes a GitHub URL → hits Kernel /reverse → returns PromptParts JSON → copies to clipboard

```
Name: Vinhub Reverse
Icon: arrow.triangle.2.circlepath (blue)

Actions:
1. Receive input from Share Sheet (or Ask Each Time)
   → Input type: URL

2. Text
   → {"url": "[Shortcut Input]"}
   → Save as: request_body

3. Get Contents of URL
   → URL: http://127.0.0.1:8000/reverse
   → Method: POST
   → Headers: Content-Type: application/json
   → Request Body: JSON (request_body)
   → Save as: kernel_response

4. Get Dictionary from Input
   → Input: kernel_response

5. Get Value for Key in Dictionary
   → Key: decomposed
   → Save as: decomposed

6. Copy to Clipboard
   → decomposed

7. Show Notification
   → Title: Vinhub ✅
   → Body: Repo reversed. PromptParts copied to clipboard.
```

---

## Shortcut 2 — Vinhub: Generate Script

**Trigger:** Manual or Siri ("Hey Siri, Vinhub generate")
**Does:** Ask for task description → Kernel /generate → new .user.js written to device

```
Name: Vinhub Generate
Icon: wand.and.stars (purple)

Actions:
1. Ask for Input
   → Question: What should the script do? (site + behavior)
   → Input type: Text
   → Save as: task_description

2. Get Clipboard
   → Save as: context (optional: paste a RepoCard or page snippet)

3. Text
   → {"task": "[task_description]", "context": "[Clipboard]"}
   → Save as: gen_body

4. Get Contents of URL
   → URL: http://127.0.0.1:8000/generate
   → Method: POST
   → Headers: Content-Type: application/json
   → Request Body: JSON (gen_body)
   → Save as: gen_response

5. Get Dictionary from Input → gen_response

6. Get Value for Key: filename
   → Save as: script_filename

7. Show Notification
   → Title: Vinhub ✅
   → Body: Script generated: [script_filename]. Enable in Safari → Extensions.
```

---

## Shortcut 3 — Vinhub: Memory Browser

**Trigger:** Manual
**Does:** Fetches last 20 memory entries from Kernel → shows as list → tap to copy URL

```
Name: Vinhub Memory
Icon: brain (green)

Actions:
1. Ask for Input
   → Question: Filter by domain? (leave blank for all)
   → Input type: Text
   → Allow empty input: Yes
   → Save as: domain_filter

2. Get Contents of URL
   → URL: http://127.0.0.1:8000/memory?domain=[domain_filter]&limit=20
   → Method: GET
   → Save as: memory_list

3. Choose from List
   → Input: memory_list
   → Prompt: Select a memory entry

4. Get Value for Key: url
   → Save as: selected_url

5. Copy to Clipboard → selected_url

6. Show Notification
   → Title: Vinhub 🧠
   → Body: URL copied: [selected_url]
```

---

## Shortcut 4 — Vinhub: Queue Command

**Trigger:** Manual or back-tap
**Does:** Injects a command into the Kernel command queue → Satellite picks it up next poll

```
Name: Vinhub Queue
Icon: terminal (orange)

Actions:
1. Choose from Menu
   → Prompt: Choose action type
   → Options: eval_code | navigate | toast
   → Save as: action_type

2. Ask for Input
   → Question: Payload (JS code / URL / message)
   → Input type: Text
   → Save as: action_payload

3. Ask for Input
   → Question: Session ID (leave blank for wildcard *)
   → Input type: Text
   → Allow empty input: Yes
   → Save as: session_id

4. Text
   → {"session_id": "[session_id OR *]", "action": "[action_type]", "payload": "[action_payload]"}
   → Save as: queue_body

5. Get Contents of URL
   → URL: http://127.0.0.1:8000/queue
   → Method: POST
   → Headers: Content-Type: application/json
   → Request Body: JSON (queue_body)

6. Show Notification
   → Title: Vinhub ⚡
   → Body: Command queued. Satellite picks it up within 3 seconds.
```

---

## Shortcut 5 — Vinhub: Start Kernel

**Trigger:** Morning routine / back-tap / Siri
**Does:** Launches Pythonista and runs kernel.py

```
Name: Vinhub Start
Icon: power (red → green)

Actions:
1. Open URL
   → URL: pythonista3://run?script=kernel

2. Wait 3 seconds

3. Get Contents of URL
   → URL: http://127.0.0.1:8000/health
   → Method: GET
   → Save as: health

4. If health contains "online"
   → Show Notification
      → Title: Vinhub 🟢 Online
      → Body: Kernel live. LLM ready.
   Otherwise
   → Show Notification
      → Title: Vinhub 🔴 Offline
      → Body: Kernel not responding. Check Pythonista.
```

---

## Power User: Siri Phrases

| Say | Shortcut | What Happens |
|-----|----------|--------------|
| "Hey Siri, reverse this repo" | Vinhub Reverse | Clipboard URL → PromptParts |
| "Hey Siri, generate a script" | Vinhub Generate | Prompted task → .user.js |
| "Hey Siri, show my memory" | Vinhub Memory | Last 20 pages browsed |
| "Hey Siri, start the kernel" | Vinhub Start | Pythonista launches, health checked |

---

## Back-Tap Setup (iPhone / iPad)

Settings → Accessibility → Touch → Back Tap:
- Double tap → Vinhub Queue (instant command injection)
- Triple tap → Vinhub Start (restart kernel anytime)

---

## iOS Shortcut Builder OS Integration

The 6-agent Shortcut Builder OS (INTENT → DESIGN → BUILD → TEST → VALIDATE → REGISTRY)
can call Vinhub shortcuts as sub-agents:

```
BUILD agent calls:
  → Vinhub Reverse (on any GitHub repo the BUILD agent identifies)
  → Vinhub Generate (with the build_prompt from decomposed RepoCard)
  → Vinhub Queue (to inject test code into Safari immediately)

REGISTRY agent calls:
  → Vinhub Memory (to check if similar workflow already captured)
```

## StackBlitz / WebContainer Bridge

For shortcuts that need a Node.js runtime on iPad:
1. Vinhub Reverse → copies PromptParts to clipboard
2. Open URL: https://node.new
3. Vinhub Queue → injects clipboard content into active Safari tab as eval_code
4. WebContainer runs the code, Satellite captures output, POSTs back to /ingest
