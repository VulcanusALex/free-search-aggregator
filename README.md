<p align="center">
  <img src="assets/hero.jpg?v=6d74a19" alt="Free Search Aggregator" width="100%" />
</p>

<h1 align="center">Free Search Aggregator</h1>

<p align="center">
Unified web search with provider failover, quota awareness, task-level multi-query search,
and managed storage under <code>memory/</code>.
</p>

## Highlights

- **Auto failover** across providers (Brave → Tavily → DuckDuckGo → Serper → SearchAPI)
- **Task search** (`task`) with query expansion + deduped merged results
- **Quota controls**: tracked quota + real quota (when providers support it)
- **Preset modes**:
  - default: `workers=1`
  - `@dual`: `workers=2`
  - `@deep`: `workers=3` + deeper query coverage
- **Managed storage** (cache/index/report) so results do not scatter in workspace root

---

## Quick Start

```bash
# Normal search
scripts/search "latest open source agent frameworks" --max-results 5

# Task-level search
scripts/search task "@dual Compare Claude vs GPT-4 for code generation" --max-results 5

# Tracked quota status
scripts/status

# Real quota (supported providers)
scripts/remaining --real

# Optional probe for header-only providers (may consume quota)
scripts/remaining --real --probe

# Cleanup old cache files (default: 14 days)
scripts/gc --cache-days 14
```

---

## CLI

```bash
python -m free_search "<query>"
python -m free_search task "<task>" [--workers 1|2|3] [--max-queries N]
python -m free_search status
python -m free_search remaining --real [--probe]
python -m free_search gc --cache-days 14 [--report-days 90]
```

---

## Python API

```python
from free_search import search, task_search, get_quota_status, get_real_quota

payload = search("latest LLM eval benchmark", max_results=5)
task_payload = task_search(
    "Compare Claude vs GPT-4 for code generation",
    max_results_per_query=5,
    max_queries=6,
)
status = get_quota_status()
real = get_real_quota()
```

---

## Data Organization (Managed)

All search artifacts are persisted under `memory/`:

- `memory/search-cache/YYYY-MM-DD/*.json`  
  Raw payload cache (short-term replay/audit)
- `memory/search-index/search-index.jsonl`  
  Append-only searchable index (query/hash/paths/top_urls)
- `memory/search-reports/YYYY-MM-DD/*.md`  
  Human-readable report with top links/snippets

Recommended retention:

- cache: **14 days**
- reports: **long-term**

---

## Real Quota Support

- **Tavily**: supported (official usage endpoint)
- **SearchAPI**: supported (official account endpoint)
- **Brave**: supported via header probe (`--probe`, consumes request)
- **Serper**: not supported (no public quota endpoint)
- **DuckDuckGo**: not applicable

---

## Notes

- `@deep` prioritizes **coverage depth**, not brute-force API burn.
- When quota usage is high, concurrency may be auto-downgraded for safety.
- For production workflows, keep `workers=1` as default and enable `@dual/@deep` only when needed.
