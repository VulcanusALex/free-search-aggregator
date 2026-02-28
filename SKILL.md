---
name: free-search-aggregator
description: Quota-aware multi-provider web search for OpenClaw. Includes automatic failover, task-level deep search (@dual/@deep), real quota checks, and managed result storage under memory/.
---

# Free Search Aggregator

Reliable web search for OpenClaw with **high uptime + low operator overhead**.

## Why use this skill

- One unified search interface across providers
- Automatic fallback when a provider fails (auth / rate limit / network / upstream)
- Quota-aware behavior to reduce API burn
- Task search mode for research-style queries
- Built-in storage lifecycle (cache / index / report), no workspace clutter

## Credential model (important)

- **No mandatory API key for basic install** (DuckDuckGo-only works out of the box).
- API-key providers are **optional** and disabled by default in `config/providers.yaml`:
  - `BRAVE_API_KEY`
  - `TAVILY_API_KEY`
  - `SERPER_API_KEY`
  - `SEARCHAPI_API_KEY`
- Enable each provider explicitly only after setting its key.

## Core capabilities

1) **Search failover**
- Provider order (default): Brave → Tavily → DuckDuckGo → Serper → SearchAPI
- First successful non-empty result returns immediately

2) **Task-level multi-query search**
- Expands one task into multiple targeted queries
- Aggregates + deduplicates results
- Prefix presets in task text:
  - default: `workers=1`
  - `@dual ...` → `workers=2`
  - `@deep ...` → `workers=3` and deeper query coverage

3) **Quota intelligence**
- Tracked quota status
- Real quota retrieval where provider supports it
- Optional probe mode (may consume quota)

4) **Managed persistence**
- `memory/search-cache/YYYY-MM-DD/*.json`
- `memory/search-index/search-index.jsonl`
- `memory/search-reports/YYYY-MM-DD/*.md`
- Optional override: `FREE_SEARCH_MEMORY_DIR` (guarded)
  - By default it must stay under `workspace/memory/`
  - To allow any path, set `FREE_SEARCH_ALLOW_ANY_MEMORY_DIR=1`

## Quick commands

```bash
# Normal search
scripts/search "latest open source agent frameworks" --max-results 5

# Task search
scripts/search task "@dual Compare Claude vs GPT-4 for code generation" --max-results 5 --max-queries 6

# Quota
scripts/status
scripts/remaining --real

# Cleanup cache (recommended daily/weekly)
python3 -m free_search gc --cache-days 14
```

## Post-install self-check (recommended)

```bash
# 1) Confirm config + provider enablement
scripts/status --compact

# 2) Run a safe smoke search (DuckDuckGo-only baseline)
scripts/search "openclaw" --max-results 3 --compact

# 3) Verify managed storage paths are being written
#    (cache/index/report under workspace/memory)
ls -la /home/openclaw/.openclaw/workspace/memory/search-cache/ | tail -n 5
ls -la /home/openclaw/.openclaw/workspace/memory/search-index/
ls -la /home/openclaw/.openclaw/workspace/memory/search-reports/ | tail -n 5

# 4) Optional: test real quota endpoint behavior
scripts/remaining --real --compact
```

## Output contract (stable)

- Search:
  - `query`, `provider`, `results[]`, `meta.attempted`, `meta.quota`
- Task search:
  - `task`, `queries[]`, `grouped_results[]`, `merged_results[]`, `meta`
- Quota:
  - `date`, `providers[]`, `totals`
  - with `--real`: `real_quota.providers[]`

## Operator notes

- Default mode is intentionally conservative (`workers=1`) for cost control
- Use `@dual` / `@deep` only when better coverage is worth extra quota
- Configure provider keys via environment variables (`BRAVE_API_KEY`, `TAVILY_API_KEY`, etc.)
