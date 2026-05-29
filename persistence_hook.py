#!/usr/bin/env python3
"""
DXv3 Persistence Hook
Runs in Pythonista 3 on iPad.
Monitors Documents/GeneratedScripts/ and copies new .user.js files
to the Userscripts app shared container.
Also exposes a one-shot CLI: python persistence_hook.py <script_path>
"""

import os
import sys
import shutil
import time
import sqlite3
from pathlib import Path

# ── Paths ─────────────────────────────────────────────────────────────────────
SOURCE_DIR = Path.home() / 'Documents' / 'GeneratedScripts'

# Userscripts app group container — update after first app launch
# Find real path: Files app → On My iPad → Userscripts
# Or use Pythonista's `os.listdir('/private/var/mobile/Containers/Shared/AppGroup/')` to discover
USERSCRIPTS_CANDIDATES = [
    Path('/private/var/mobile/Containers/Shared/AppGroup/'),
    Path.home() / 'Documents',  # fallback: copy here, drag manually
]

DB_PATH = Path.home() / 'Documents' / 'agent_memory.db'

# ── Discover Userscripts container ────────────────────────────────────────────
def find_userscripts_dir():
    for base in USERSCRIPTS_CANDIDATES:
        if not base.exists():
            continue
        for child in base.iterdir():
            marker = child / 'Library' / 'userscripts'
            if marker.exists():
                return marker
    # Final fallback
    fallback = Path.home() / 'Documents' / 'Userscripts'
    fallback.mkdir(parents=True, exist_ok=True)
    return fallback

USERSCRIPTS_DIR = find_userscripts_dir()
print(f'[Persistence] Userscripts dir: {USERSCRIPTS_DIR}')

# ── Copy script ───────────────────────────────────────────────────────────────
def install_script(src: Path):
    dest = USERSCRIPTS_DIR / src.name
    shutil.copy2(src, dest)
    print(f'[Persistence] Installed: {src.name} → {dest}')
    # Log to DB
    try:
        conn = sqlite3.connect(str(DB_PATH))
        conn.execute(
            'CREATE TABLE IF NOT EXISTS installs (id INTEGER PRIMARY KEY, filename TEXT, installed_at DATETIME DEFAULT CURRENT_TIMESTAMP)'
        )
        conn.execute('INSERT INTO installs (filename) VALUES (?)', (src.name,))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f'[Persistence] DB log error: {e}')

# ── Watch mode ────────────────────────────────────────────────────────────────
def watch():
    SOURCE_DIR.mkdir(parents=True, exist_ok=True)
    seen = set(SOURCE_DIR.glob('*.user.js'))
    print(f'[Persistence] Watching {SOURCE_DIR} ...')
    print('[Persistence] Drop .user.js files here to auto-install')
    while True:
        current = set(SOURCE_DIR.glob('*.user.js'))
        new_files = current - seen
        for f in new_files:
            install_script(f)
        seen = current
        time.sleep(2)

# ── iOS Shortcut URL: pythonista3://run?script=persistence_hook ───────────────
if __name__ == '__main__':
    if len(sys.argv) > 1:
        # CLI mode: python persistence_hook.py path/to/script.user.js
        target = Path(sys.argv[1])
        if target.exists() and target.suffix in ('.js',):
            install_script(target)
        else:
            print(f'[Persistence] File not found or not a .js: {target}')
    else:
        # Watch mode
        watch()
