#!/usr/bin/env python3
"""
Shortcut Builder OS — Kernel Extension
Add these routes to kernel.py (or run as a separate FastAPI mount)
Endpoint: POST /shortcut/build
"""

import json
import os
import uuid
from datetime import datetime
from pathlib import Path

# ── Agent Prompts (import from agent_team.md or inline here) ────────────────

INTENT_PROMPT = """You are the INTENT agent in the iOS Shortcut Builder OS.
Input: raw user idea. Output: intent.md locked scope document.
intent.md must contain:
- CORE_ACTION: one sentence
- TRIGGER: manual|siri|share_sheet|back_tap|automation
- INPUT_TYPE: text|url|clipboard|file|ask_each_time|none
- OUTPUT_TYPE: clipboard|notification|open_url|file|speak|none
- KERNEL_NEEDED: yes|no
- CLARIFICATIONS: max 2 or NONE
Output ONLY the intent.md content. No prose. No fences."""

DESIGN_PROMPT = """You are the DESIGN agent in the iOS Shortcut Builder OS.
Input: intent.md. Output: blueprint.md step-by-step action map.
STEPS: numbered, each has action_name, input, output variable, kernel_call (null or endpoint), bridge (null|pythonista|scriptable|stackblitz).
DATA_FLOW: variable dependency map.
RISKS: iOS version or entitlement requirements.
Output ONLY blueprint.md content. No prose. No fences."""

BUILD_PROMPT = """You are the BUILD agent in the iOS Shortcut Builder OS.
Input: blueprint.md. Optional: fix_request.md.
Output: complete Apple Shortcuts importable JSON (WFWorkflow dict).
WFWorkflowActions array. Real WFActionIdentifier values only. WFVariableReference for all bindings.
HTTP via is.workflow.actions.downloadurl. Conditionals via is.workflow.actions.conditional.
Apply all fixes from fix_request.md if present.
Output ONLY valid JSON. No prose. No fences."""

TEST_PROMPT = """You are the TEST agent in the iOS Shortcut Builder OS.
Input: shortcut.json + blueprint.md. Output: test_report.md.
Must include: HAPPY_PATH, FAILURE_PATH_1 (Kernel offline), FAILURE_PATH_2 (empty input),
VARIABLE_CHECK, HTTP_CHECK, VERSION_FLAGS, VERDICT (PASS|FAIL), FAIL_REASONS.
Output ONLY test_report.md content. No prose. No fences."""

VALIDATE_PROMPT = """You are the VALIDATE agent in the iOS Shortcut Builder OS.
Input: test_report.md + shortcut.json.
Approve if VERDICT=PASS, no unbound variables, no invented WFActionIdentifiers.
Reject: output fix_request.md with ISSUES and INSTRUCTIONS for BUILD agent.
Output ONLY: the word APPROVED or fix_request.md content. No prose. No fences."""

REGISTRY_PROMPT = """You are the REGISTRY agent in the iOS Shortcut Builder OS.
Input: shortcut_final.json + intent.md.
Output: registry_entry JSON + --- divider + install_instructions.md.
registry_entry keys: name, trigger, input_type, output_type, kernel_endpoints_used, created_at, action_count, json_preview.
install_instructions.md: METHOD, ENABLE_EXTENSIONS, SIRI_PHRASE, BACK_TAP.
Output ONLY registry JSON then --- then install_instructions.md. No prose."""

# ── Paste these routes into kernel.py ──────────────────────────────────────────────
# from fastapi import FastAPI, Request  (already in kernel.py)
# from shortcut_builder_os.kernel_extension import shortcut_build_route
# app.include_router(shortcut_build_route)

try:
    from fastapi import APIRouter, Request
    from fastapi.responses import JSONResponse
except ImportError:
    pass

shortcut_build_route = None

try:
    from fastapi import APIRouter, Request
    shortcut_build_route = APIRouter()

    @shortcut_build_route.post('/shortcut/build')
    async def shortcut_build(request: Request):
        import requests as req
        data = await request.json()
        idea = data.get('idea', '')
        run_id = data.get('run_id') or uuid.uuid4().hex[:8]

        # Output dir
        run_dir = Path.home() / 'Documents' / 'ShortcutBuilderOS' / run_id
        run_dir.mkdir(parents=True, exist_ok=True)

        def call_llm(system, user):
            """Reuse kernel.py llm() — inline here for standalone use"""
            try:
                r = req.post(
                    'http://localhost:1234/v1/chat/completions',
                    json={
                        'model': 'llama-3.2-3b',
                        'messages': [
                            {'role': 'system', 'content': system},
                            {'role': 'user', 'content': user}
                        ],
                        'temperature': 0.2
                    },
                    timeout=90
                )
                return r.json()['choices'][0]['message']['content']
            except Exception as e:
                return f'LLM_ERROR: {e}'

        def save(filename, content):
            (run_dir / filename).write_text(content)
            return content

        # ── AGENT 1: INTENT ───────────────────────────────────────────────
        intent_md = save('intent.md', call_llm(INTENT_PROMPT, idea))

        # ── AGENT 2: DESIGN ──────────────────────────────────────────────
        blueprint_md = save('blueprint.md', call_llm(DESIGN_PROMPT, intent_md))

        # ── AGENT 3+5: BUILD → VALIDATE loop (max 2 iterations) ───────────────
        fix_request = ''
        shortcut_json = ''
        shortcut_final = ''
        MAX_LOOPS = 2

        for loop in range(MAX_LOOPS):
            build_input = blueprint_md
            if fix_request:
                build_input = f'{blueprint_md}\n\nFIX_REQUEST:\n{fix_request}'

            # AGENT 3: BUILD
            shortcut_json = save(f'shortcut_v{loop+1}.json', call_llm(BUILD_PROMPT, build_input))

            # AGENT 4: TEST
            test_input = f'SHORTCUT_JSON:\n{shortcut_json}\n\nBLUEPRINT:\n{blueprint_md}'
            test_report = save('test_report.md', call_llm(TEST_PROMPT, test_input))

            # AGENT 5: VALIDATE
            validate_input = f'TEST_REPORT:\n{test_report}\n\nSHORTCUT_JSON:\n{shortcut_json}'
            validation = call_llm(VALIDATE_PROMPT, validate_input)

            if validation.strip().upper().startswith('APPROVED'):
                shortcut_final = save('shortcut_final.json', shortcut_json)
                fix_request = ''
                break
            else:
                fix_request = save('fix_request.md', validation)

        if not shortcut_final:
            shortcut_final = save('shortcut_final.json', shortcut_json)  # best effort

        # ── AGENT 6: REGISTRY ─────────────────────────────────────────────
        registry_input = f'SHORTCUT_FINAL:\n{shortcut_final}\n\nINTENT:\n{intent_md}'
        registry_output = call_llm(REGISTRY_PROMPT, registry_input)

        parts = registry_output.split('---', 1)
        registry_entry_raw = parts[0].strip()
        install_instructions = parts[1].strip() if len(parts) > 1 else ''

        save('install_instructions.md', install_instructions)

        # Write to shortcuts_registry.json
        registry_file = Path.home() / 'Documents' / 'shortcuts_registry.json'
        registry = []
        if registry_file.exists():
            try:
                registry = json.loads(registry_file.read_text())
            except Exception:
                pass
        try:
            entry = json.loads(registry_entry_raw)
            entry['run_id'] = run_id
            entry['run_dir'] = str(run_dir)
            registry.append(entry)
            registry_file.write_text(json.dumps(registry, indent=2))
        except Exception:
            pass

        return {
            'run_id': run_id,
            'run_dir': str(run_dir),
            'intent': intent_md,
            'blueprint': blueprint_md,
            'shortcut_final': shortcut_final,
            'install_instructions': install_instructions,
            'registry_entry': registry_entry_raw,
            'loops': loop + 1
        }

except Exception as e:
    print(f'[ShortcutBuilderOS] Extension load error: {e}')
