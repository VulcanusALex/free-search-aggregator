# Free Search Aggregator

Unified web search with automatic multi-provider failover and quota tracking.

## Quick Start
```bash
# Search
scripts/search "latest open source agent frameworks" --max-results 5

# Quota status (tracked)
scripts/status

# Real quota (when supported)
scripts/remaining --real

# Real quota with probe (consumes quota for providers without endpoints, e.g. Brave)
scripts/remaining --real --probe
```

## Python API
```python
from free_search import search, task_search, get_quota_status, get_real_quota

payload = search("latest LLM eval benchmark", max_results=5)
task_payload = task_search("Compare Claude vs GPT-4 for code generation", max_results_per_query=5, max_queries=6)
status = get_quota_status()
real = get_real_quota()
```

## Real Quota Support
- Tavily: supported (official usage endpoint)
- SearchAPI: supported (official account endpoint)
- Brave: supported via header probe (`--probe`, consumes quota)
- Serper: not supported (no public quota endpoint)
- DuckDuckGo: not applicable

## CLI
```bash
python -m free_search "<query>"
python -m free_search task "<task>"
python -m free_search status
python -m free_search remaining --real
```

## Notes
- Real quota depends on provider support. When unsupported, tracked usage is shown only.
- `--probe` is optional and may consume one request to read headers.

