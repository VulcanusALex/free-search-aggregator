# Free Search Aggregator

Unified web search with automatic multi-provider failover, quota tracking, and rate pacing.

## Features

- **Unified output** — consistent JSON format across all providers
- **Auto failover** — seamlessly falls back through providers on auth, rate-limit, network, or parse errors
- **Quota tracking** — enforces configurable daily limits per provider
- **Rate pacing** — configurable minimum interval between requests
- **Multiple providers** — Brave, Tavily, DuckDuckGo, Serper, and SearchAPI

## Quick Start

### Install dependencies

```bash
pip install -r requirements.txt
```

### Set API keys

```bash
export BRAVE_API_KEY="..."
export TAVILY_API_KEY="..."
export SERPER_API_KEY="..."
export SEARCHAPI_API_KEY="..."
```

DuckDuckGo does not require an API key.

### Search via CLI

```bash
scripts/search "latest open source agent frameworks" --max-results 5
```

Or using the Python module directly:

```bash
python -m free_search "latest open source agent frameworks" --max-results 5
```

### Check quota status

```bash
scripts/status
```

### Reset quota counters

```bash
scripts/status --reset
```

## Python API

```python
from free_search import search, get_quota_status, reset_quota

results = search("latest LLM eval benchmark", max_results=5)
status  = get_quota_status()
reset   = reset_quota()
```

## Provider Order

Default routing order (configured in `config/providers.yaml`):

| Priority | Provider    | API Key Required |
|----------|-------------|------------------|
| 1        | Brave       | Yes              |
| 2        | Tavily      | Yes              |
| 3        | DuckDuckGo  | No               |
| 4        | Serper      | Yes              |
| 5        | SearchAPI   | Yes              |

Providers can be reordered, enabled, or disabled in `config/providers.yaml`.

## Output Format

```json
{
  "query": "example query",
  "provider": "brave",
  "results": [
    {
      "title": "Example Title",
      "url": "https://example.com",
      "snippet": "A brief description...",
      "source": "brave",
      "rank": 1
    }
  ],
  "meta": {
    "attempted": [],
    "quota": {},
    "timestamp_utc": "2026-01-01T00:00:00+00:00"
  }
}
```

## Running Tests

```bash
PYTHONPATH=src python -m unittest discover tests/ -v
```

## License

See repository for license details.
