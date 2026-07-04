#!/usr/bin/env python3
"""
DXv3 Safari Agent Kernel
FastAPI server — runs in Pythonista 3 on iPad
Endpoints: /ingest /command /generate /reverse /memory

WIRE-01 (2026-07-04):
  safari_brain_publisher is now imported and called at every task completion
  point so iPad agent activity is visible in brain.db via harmony bus:
    /ingest   → publish_agent_result(task_type='ingest')
    /generate → publish_agent_result(task_type='generate_script')
    /reverse  → publish_agent_result(task_type='git_reverse')
                + publish_kg_link for each chain_target discovered
    /health   → publish_agent_ping(status='running')
  Graceful no-op if harmony-engine-protocol is not installed on the device.
"""

import json
import sqlite3
import os
import requests
from datetime import datetime
from pathlib import Path

try:
    from fastapi import FastAPI, Request
    from fastapi.responses import JSONResponse
    import uvicorn
except ImportError:
    import subprocess
    subprocess.run(['pip', 'install', 'fastapi', 'uvicorn', 'requests'], check=True)
    from fastapi import FastAPI, Request
    from fastapi.responses import JSONResponse
    import uvicorn

# ── Brain Bus (graceful — no-op if harmony not installed on this device) ───────
try:
    from safari_brain_publisher import (
        publish_agent_result,
        publish_agent_ping,
        publish_kg_link,
        bus_available,
    )
    _BRAIN_BUS = True
except ImportError:
    _BRAIN_BUS = False
    def publish_agent_result(*a, **kw): return False   # type: ignore[misc]
    def publish_agent_ping(*a, **kw):   return False   # type: ignore[misc]
    def publish_kg_link(*a, **kw):      return False   # type: ignore[misc]
    def bus_available():                return False   # type: ignore[misc]

# ── Config ────────────────────────────────────────────────────────────────────
PORT = 8000
DB_PATH = str(Path.home() / 'Documents' / 'agent_memory.db')
LLM_BASE = 'http://localhost:1234/v1'  # Local LLM Server app default port
LLM_MODEL = 'llama-3.2-3b'
USERSCRIPTS_DIR = '/private/var/mobile/Containers/Shared/AppGroup/'
# Fallback path — update after first Userscripts app launch on your device
FALLBACK_SCRIPTS_DIR = str(Path.home() / 'Documents' / 'GeneratedScripts')

app = FastAPI(title='DXv3 Kernel', version='1.1.0')

# ── Database ──────────────────────────────────────────────────────────────────
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS memory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT,
            url TEXT,
            domain TEXT,
            raw_context TEXT,
            repo_card TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS commands (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT,
            action TEXT,
            payload TEXT,
            executed INTEGER DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS generated_scripts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task TEXT,
            script TEXT,
            filename TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
    """)
    conn.commit()
    conn.close()

init_db()

# ── LLM Client ────────────────────────────────────────────────────────────────
def llm(system_prompt: str, user_message: str, temperature: float = 0.2) -> str:
    try:
        res = requests.post(
            f'{LLM_BASE}/chat/completions',
            json={
                'model': LLM_MODEL,
                'messages': [
                    {'role': 'system', 'content': system_prompt},
                    {'role': 'user', 'content': user_message}
                ],
                'temperature': temperature
            },
            timeout=60
        )
        return res.json()['choices'][0]['message']['content']
    except Exception as e:
        return f'LLM_ERROR: {str(e)}'

# ── Prompts ───────────────────────────────────────────────────────────────────
DECOMPOSER_PROMPT = """
You are a GitHub Repository Decomposer. Given a repo card (JSON), extract:
1. atoms: list of reusable functions/patterns with name, purpose, inputs, outputs
2. interfaces: key APIs, endpoints, event hooks
3. dependencies: critical external packages
4. build_prompt: a 5-sentence LLM prompt to rebuild this tool from scratch
5. chain_targets: 3 other GitHub repos this would pair well with
Output ONLY valid JSON. No prose. No markdown fences.
"""

SCRIPT_GENERATOR_PROMPT = """
You are a Safari iPadOS Userscript Generator for Vinny Gilberti (DXv-3).
Rules:
- Output ONLY a complete .user.js file. No explanation. No markdown fences.
- Use native fetch() only. No GM_* APIs.
- Eval any dynamic code inside a sandboxed iframe.
- Target: Safari on iPadOS via Userscripts app.
- Scripts must be self-contained and run on page load.
- Include proper ==UserScript== metadata header.
"""

COMMAND_PROMPT = """
You are a browser automation orchestrator for iPad Safari.
Given the current page context (JSON), decide the next action.
Output ONLY valid JSON with keys: action (eval_code|navigate|toast|wait), payload (string or null).
For eval_code: payload is complete JS to inject. For navigate: payload is the URL. For toast: payload is the message.
If nothing useful to do: {"action": "wait", "payload": null}
"""

# ── Endpoints ─────────────────────────────────────────────────────────────────
@app.post('/ingest')
async def ingest(request: Request):
    data = await request.json()
    conn = get_db()
    conn.execute(
        'INSERT INTO memory (session_id, url, domain, raw_context, repo_card) VALUES (?,?,?,?,?)',
        (
            data.get('sessionId'),
            data.get('url'),
            data.get('domain'),
            json.dumps(data),
            json.dumps(data.get('repoCard')) if data.get('repoCard') else None
        )
    )
    conn.commit()
    conn.close()

    # ── WIRE-01: publish ingest event so brain tracks every page Safari visits ──
    publish_agent_result(
        task_id   = data.get('sessionId', 'ingest'),
        task_type = 'ingest',
        outcome   = 'pass',
        detail    = f"domain={data.get('domain', '')}",
        model     = '',
        url       = data.get('url', ''),
    )

    return {'status': 'ok', 'domain': data.get('domain')}


@app.get('/command')
async def command(session: str = '', url: str = ''):
    conn = get_db()
    # Check for pending queued command first
    row = conn.execute(
        'SELECT * FROM commands WHERE session_id=? AND executed=0 ORDER BY id LIMIT 1',
        (session,)
    ).fetchone()
    if row:
        conn.execute('UPDATE commands SET executed=1 WHERE id=?', (row['id'],))
        conn.commit()
        conn.close()
        return {'action': row['action'], 'payload': row['payload']}
    # Otherwise ask LLM based on last ingest
    last = conn.execute(
        'SELECT raw_context FROM memory WHERE session_id=? ORDER BY id DESC LIMIT 1',
        (session,)
    ).fetchone()
    conn.close()
    if not last:
        return {'action': 'wait', 'payload': None}
    response = llm(COMMAND_PROMPT, last['raw_context'])
    try:
        return json.loads(response)
    except Exception:
        return {'action': 'wait', 'payload': None}


@app.post('/generate')
async def generate(request: Request):
    data = await request.json()
    task = data.get('task', '')
    context = data.get('context', '')
    prompt = f'TASK: {task}\n\nCONTEXT:\n{context}'
    script = llm(SCRIPT_GENERATOR_PROMPT, prompt, temperature=0.3)

    # Save to DB
    filename = f'generated_{datetime.now().strftime("%Y%m%d_%H%M%S")}.user.js'
    conn = get_db()
    conn.execute(
        'INSERT INTO generated_scripts (task, script, filename) VALUES (?,?,?)',
        (task, script, filename)
    )
    conn.commit()
    conn.close()

    # Write to filesystem
    _write_script(filename, script)

    # ── WIRE-01: publish script generation — outcome tracks LLM errors ──────────
    outcome = 'fail' if script.startswith('LLM_ERROR') else 'pass'
    publish_agent_result(
        task_id   = filename,
        task_type = 'generate_script',
        outcome   = outcome,
        detail    = f"task={task[:120]}",
        model     = LLM_MODEL,
        url       = '',
    )

    return {'status': 'ok', 'filename': filename, 'script': script}


@app.post('/reverse')
async def reverse(request: Request):
    data = await request.json()
    repo_url = data.get('url', '')

    # Fetch via gitingest
    try:
        ingest_url = repo_url.replace('github.com', 'gitingest.com')
        raw = requests.get(ingest_url, timeout=30).text[:8000]
    except Exception as e:
        raw = f'FETCH_ERROR: {e}'

    result = llm(DECOMPOSER_PROMPT, raw)
    try:
        parsed = json.loads(result)
    except Exception:
        parsed = {'raw': result}

    # ── WIRE-01: publish reverse event + KG edges for every chain_target ────────
    outcome = 'fail' if ('FETCH_ERROR' in raw or 'LLM_ERROR' in raw) else 'pass'
    publish_agent_result(
        task_id   = repo_url,
        task_type = 'git_reverse',
        outcome   = outcome,
        detail    = f"url={repo_url[:150]}",
        model     = LLM_MODEL,
        url       = repo_url,
    )
    if outcome == 'pass':
        # Register KG edges: safari-agent-stack CHAIN_TARGET → discovered repos
        for target in parsed.get('chain_targets', []):
            if isinstance(target, str) and target.strip():
                publish_kg_link(
                    target_repo = target.strip(),
                    relation    = 'CHAIN_TARGET',
                    weight      = 1.0,
                )

    return {'url': repo_url, 'decomposed': parsed}


@app.get('/memory')
async def memory(domain: str = '', limit: int = 20):
    conn = get_db()
    if domain:
        rows = conn.execute(
            'SELECT url, domain, timestamp, repo_card FROM memory WHERE domain LIKE ? ORDER BY id DESC LIMIT ?',
            (f'%{domain}%', limit)
        ).fetchall()
    else:
        rows = conn.execute(
            'SELECT url, domain, timestamp, repo_card FROM memory ORDER BY id DESC LIMIT ?',
            (limit,)
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


@app.post('/queue')
async def queue_command(request: Request):
    """Manually queue a command for a session (for iOS Shortcut integration)"""
    data = await request.json()
    conn = get_db()
    conn.execute(
        'INSERT INTO commands (session_id, action, payload) VALUES (?,?,?)',
        (data.get('session_id', '*'), data.get('action'), data.get('payload'))
    )
    conn.commit()
    conn.close()
    return {'status': 'queued'}


@app.get('/health')
async def health():
    # ── WIRE-01: subsystem heartbeat so the-brain dashboard shows safari online ──
    publish_agent_ping(status='running')
    return {
        'status':     'online',
        'model':      LLM_MODEL,
        'db':         DB_PATH,
        'brain_bus':  _BRAIN_BUS,
    }


# ── File Writer ───────────────────────────────────────────────────────────────
def _write_script(filename: str, content: str):
    """Write generated script to Documents/GeneratedScripts for manual install"""
    out_dir = Path(FALLBACK_SCRIPTS_DIR)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / filename).write_text(content)
    print(f'[Kernel] Script written: {out_dir / filename}')


# ── Run ───────────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    print(f'[DXv3 Kernel] Starting on http://127.0.0.1:{PORT}')
    print(f'[DXv3 Kernel] DB: {DB_PATH}')
    print(f'[DXv3 Kernel] LLM: {LLM_BASE} ({LLM_MODEL})')
    print(f'[DXv3 Kernel] Brain bus: {"connected" if _BRAIN_BUS else "offline (harmony not installed)"}')
    uvicorn.run(app, host='127.0.0.1', port=PORT, log_level='info')
