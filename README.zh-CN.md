# Free Search Aggregator

多源搜索聚合器，提供自动故障切换和配额追踪。

## 快速开始
```bash
# 搜索
scripts/search "最新开源代理框架" --max-results 5

# 配额状态（本地追踪）
scripts/status

# 真实配额（支持的提供商）
scripts/remaining --real

# 真实配额 + 探测（会消耗额度，比如 Brave）
scripts/remaining --real --probe
```

## Python API
```python
from free_search import search, task_search, get_quota_status, get_real_quota

payload = search("最新 LLM 评测", max_results=5)
task_payload = task_search("对比 Claude 与 GPT-4 在代码生成上的差异", max_results_per_query=5, max_queries=6)
status = get_quota_status()
real = get_real_quota()
```

## 真实配额支持情况
- Tavily：支持（官方用量接口）
- SearchAPI：支持（官方账户接口）
- Brave：通过响应头探测（需要 `--probe`，会消耗一次额度）
- Serper：不支持（无公开用量接口）
- DuckDuckGo：无配额概念

## CLI
```bash
python -m free_search "<query>"
python -m free_search task "<task>"
python -m free_search status
python -m free_search remaining --real
```

## 说明
- 真实配额仅在支持的提供商可用，否则只显示本地追踪。
- `--probe` 会发起一次请求获取响应头，可能消耗额度。

