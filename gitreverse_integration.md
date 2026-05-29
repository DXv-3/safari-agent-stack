# GitReverse Integration Guide

How `safari-agent-stack` connects to `DXv-3/gitreverse-hub`.

## Flow

```
github.com/owner/repo
  → SATELLITE.user.js extracts RepoCard JSON
  → POST /ingest (Kernel stores to memory DB)
  → POST /reverse (Kernel fetches via gitingest.com mirror)
  → Decomposer LLM prompt → PromptParts JSON
      {
        atoms: [...],
        interfaces: [...],
        dependencies: [...],
        build_prompt: "...",
        chain_targets: [...]
      }
  → POST /generate with build_prompt as task
  → New .user.js generated for that repo's site
  → persistence_hook.py installs it
```

## RepoCard Schema

```json
{
  "owner": "string",
  "repo": "string",
  "description": "string",
  "stars": "string",
  "language": "string",
  "lastCommit": "ISO8601",
  "fileTree": ["string"],
  "readme": "string (2000 char max)"
}
```

## Chaining Repo Cards

To build a multi-tool pipeline:

```python
# In Pythonista / Kernel extension
urls = [
    'https://github.com/filiksyos/gitreverse',
    'https://github.com/quoid/userscripts',
    'https://github.com/simonw/llm'
]
cards = [requests.post('http://127.0.0.1:8000/reverse', json={'url': u}).json() for u in urls]
chained_context = '\n\n'.join([json.dumps(c['decomposed']) for c in cards])
# Feed chained_context to /generate as context
```

## Gitingest Mirror

`github.com` → `gitingest.com` (drop-in URL swap)
Returns full repo as single flat text — optimal for one-shot LLM context.

## iOS Shortcut Trigger

```
pythonista3://run?script=kernel
```

Build a Shortcut with:
1. Get clipboard (GitHub URL)
2. URL: `http://127.0.0.1:8000/reverse`
3. Method: POST, body: `{"url": [Clipboard]}`
4. Show result
```
