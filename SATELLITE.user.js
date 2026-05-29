// ==UserScript==
// @name         DXv3 Safari Agent Satellite
// @namespace    https://github.com/DXv-3
// @version      1.0.0
// @description  Captures page context, bridges to local Kernel, executes generated code
// @author       DXv-3
// @match        *://*/*
// @grant        none
// ==/UserScript==

(function () {
  'use strict';

  const KERNEL = 'http://127.0.0.1:8000';
  const POLL_INTERVAL = 3000;
  const SESSION_ID = Date.now().toString(36);

  // ── Repo Card extractor (GitHub only) ──────────────────────────────────────
  function extractRepoCard() {
    if (!location.hostname.includes('github.com')) return null;
    const pathParts = location.pathname.split('/').filter(Boolean);
    if (pathParts.length < 2) return null;
    const fileTree = Array.from(document.querySelectorAll('[aria-label="Files"] a, .js-navigation-item .content a'))
      .map(a => a.textContent.trim()).filter(Boolean).slice(0, 60);
    const readme = document.querySelector('#readme article, .markdown-body')?.innerText?.slice(0, 2000) || '';
    const description = document.querySelector('.f4.my-3, [itemprop="about"]')?.textContent?.trim() || '';
    const stars = document.querySelector('#repo-stars-counter-star, [aria-label*="star"]')?.textContent?.trim() || '';
    const language = document.querySelector('[itemprop="programmingLanguage"], .d-inline .color-fg-default')?.textContent?.trim() || '';
    const lastCommit = document.querySelector('relative-time')?.getAttribute('datetime') || '';
    return {
      owner: pathParts[0],
      repo: pathParts[1],
      description,
      stars,
      language,
      lastCommit,
      fileTree,
      readme
    };
  }

  // ── Page context builder ────────────────────────────────────────────────────
  function buildContext() {
    return {
      sessionId: SESSION_ID,
      url: location.href,
      domain: location.hostname,
      title: document.title,
      bodyText: document.body.innerText.slice(0, 3000),
      forms: Array.from(document.forms).map(f => ({
        action: f.action,
        fields: Array.from(f.elements).map(e => e.name).filter(Boolean)
      })),
      links: Array.from(document.querySelectorAll('a[href]'))
        .map(a => a.href).filter(h => h.startsWith('http')).slice(0, 40),
      repoCard: extractRepoCard(),
      timestamp: new Date().toISOString()
    };
  }

  // ── Sandboxed eval via iframe ───────────────────────────────────────────────
  function safeEval(code) {
    const iframe = document.createElement('iframe');
    iframe.sandbox = 'allow-scripts allow-same-origin';
    iframe.style.display = 'none';
    document.body.appendChild(iframe);
    try {
      const script = iframe.contentDocument.createElement('script');
      script.textContent = code;
      iframe.contentDocument.body.appendChild(script);
    } catch (e) {
      console.error('[Satellite] eval error:', e);
    } finally {
      setTimeout(() => iframe.remove(), 5000);
    }
  }

  // ── Toast notification ──────────────────────────────────────────────────────
  function toast(msg, color = '#1a1a2e') {
    const t = document.createElement('div');
    t.textContent = msg;
    Object.assign(t.style, {
      position: 'fixed', bottom: '24px', right: '24px', zIndex: 999999,
      background: color, color: '#fff', padding: '10px 16px',
      borderRadius: '8px', fontSize: '13px', fontFamily: 'monospace',
      boxShadow: '0 4px 12px rgba(0,0,0,0.3)', maxWidth: '320px'
    });
    document.body.appendChild(t);
    setTimeout(() => t.remove(), 3500);
  }

  // ── POST context to Kernel ──────────────────────────────────────────────────
  async function ingest() {
    const ctx = buildContext();
    try {
      const res = await fetch(`${KERNEL}/ingest`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(ctx)
      });
      if (res.ok) toast(`[DXv3] Ingested: ${ctx.domain}`, '#0f3460');
    } catch (e) {
      toast('[DXv3] Kernel offline', '#7f1d1d');
    }
  }

  // ── Poll Kernel for commands ────────────────────────────────────────────────
  async function poll() {
    try {
      const res = await fetch(`${KERNEL}/command?session=${SESSION_ID}&url=${encodeURIComponent(location.href)}`);
      if (!res.ok) return;
      const cmd = await res.json();
      if (!cmd || cmd.action === 'wait') return;
      if (cmd.action === 'eval_code' && cmd.payload) {
        toast('[DXv3] Executing injected code...', '#064e3b');
        safeEval(cmd.payload);
      }
      if (cmd.action === 'navigate' && cmd.payload) {
        toast(`[DXv3] Navigating to ${cmd.payload}`, '#1e3a5f');
        location.href = cmd.payload;
      }
      if (cmd.action === 'toast' && cmd.payload) {
        toast(cmd.payload, '#374151');
      }
    } catch (_) { /* Kernel offline, silent */ }
  }

  // ── Init ────────────────────────────────────────────────────────────────────
  window.addEventListener('load', () => {
    ingest();
    setInterval(poll, POLL_INTERVAL);
  });

})();
