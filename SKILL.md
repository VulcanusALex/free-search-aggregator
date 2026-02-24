---
name: free-search-aggregator
description: Unified web search skill with automatic multi-provider failover. Use this when OpenClaw needs reliable web search via script or Python API, with quota/rate-limit awareness and fallback across Brave, Tavily, DuckDuckGo, Serper, and SearchAPI.
---

# Free Search Aggregator

## What This Skill Does
This skill provides one stable search interface for OpenClaw with:
- Unified output JSON format across providers
- Automatic provider failover on auth/rate/network/parse/upstream failures
- Quota tracking and simple rate pacing
- Script entrypoints for direct OpenClaw invocation

## Entry Scripts (OpenClaw)
Use scripts in `scripts/` first:

1. Search
```bash
scripts/search "latest open source agent frameworks" --max-results 5
```

2. Quota status
```bash
scripts/status
```

3. Reset quota counters and show status
```bash
scripts/status --reset
```

All scripts auto-set `PYTHONPATH` and run from this skill root.

## Python API
```python
from free_search import search, get_quota_status, reset_quota

payload = search("latest LLM eval benchmark", max_results=5)
status = get_quota_status()
reset = reset_quota()
```

## Provider List
Default routing order in `config/providers.yaml`:
1. Brave (`brave`)
2. Tavily (`tavily`)
3. DuckDuckGo HTML (`duckduckgo`)
4. Serper (`serper`)
5. SearchAPI (`searchapi`)

Notes:
- You can reorder providers via `router.provider_order`.
- A provider can be disabled with `enabled: false`.
- Additional providers may exist in code, but only configured providers in order are used.

## Auto Failover Behavior
For each request:
1. Iterate providers in configured order.
2. Skip disabled providers or providers with exhausted `daily_quota`.
3. If a provider raises recoverable errors (`AuthError`, `RateLimitError`, `NetworkError`, `ParseError`, `UpstreamError`), record failure and continue.
4. Return immediately on first provider that yields non-empty results.
5. If all providers fail, raise `SearchRouterError`.

Returned payload includes attempt history:
- `meta.attempted`: per-provider status/reason/latency
- `meta.quota`: snapshot of current quota usage

## Configuration
Main config file: `config/providers.yaml`

Key fields:
- `router.provider_order`: failover order
- `router.quota_state_file`: persisted usage state file
- `providers.<name>.enabled`: on/off
- `providers.<name>.api_key`: provider credential
- `providers.<name>.daily_quota`: request cap per UTC day
- `providers.<name>.min_interval_seconds`: pacing between calls
- `providers.<name>.timeout_seconds`: request timeout

Recommended credential setup:
```bash
export BRAVE_API_KEY="..."
export TAVILY_API_KEY="..."
export SERPER_API_KEY="..."
export SEARCHAPI_API_KEY="..."
```

## CLI Compatibility
The module CLI supports:
- `python -m free_search "<query>"`
- `python -m free_search status`
- legacy compat: `python -m free_search brave search "<query>"`

## Output Contract
Search returns JSON-compatible dict:
- `query`
- `provider`
- `results`: list of `{title, url, snippet, source, rank}`
- `meta`: attempted providers, quota snapshot, UTC timestamp

Quota status returns:
- `date`
- `providers[]`: `provider`, `used_today`, `remaining`, `daily_quota`, `percentage_used`
