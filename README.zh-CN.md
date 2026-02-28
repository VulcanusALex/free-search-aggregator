<p align="center">
  <img src="assets/hero.jpg?v=6d74a19" alt="Free Search Aggregator" width="100%" />
</p>

<h1 align="center">Free Search Aggregator</h1>

<p align="center">
多源搜索聚合器：自动故障切换、配额感知、任务级多查询检索，
并将结果统一存入 <code>memory/</code>，避免散落在 workspace 根目录。
</p>

## 核心能力

- **自动 failover**：Brave → Tavily → DuckDuckGo → Serper → SearchAPI
- **任务搜索**（`task`）：自动扩展查询、分组结果、去重合并
- **配额管理**：本地追踪 + 提供商真实配额（支持时）
- **并发预设**：
  - 默认：`workers=1`
  - `@dual`：`workers=2`
  - `@deep`：`workers=3` + 更深查询覆盖
- **结果管理**：缓存/索引/报告三层结构化存储

---

## 快速开始

```bash
# 普通搜索
scripts/search "最新开源代理框架" --max-results 5

# 任务搜索
scripts/search task "@dual 对比 Claude 与 GPT-4 在代码生成上的差异" --max-results 5

# 本地配额状态
scripts/status

# 真实配额（支持的提供商）
scripts/remaining --real

# 响应头探测（可选，可能消耗额度）
scripts/remaining --real --probe

# 清理旧缓存（默认建议 14 天）
scripts/gc --cache-days 14
```

---

## CLI 用法

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

payload = search("最新 LLM 评测", max_results=5)
task_payload = task_search(
    "对比 Claude 与 GPT-4 在代码生成上的差异",
    max_results_per_query=5,
    max_queries=6,
)
status = get_quota_status()
real = get_real_quota()
```

---

## 数据组织（统一管理）

所有搜索产物统一写入 `memory/`：

- `memory/search-cache/YYYY-MM-DD/*.json`  
  原始结果缓存（短期复盘/审计）
- `memory/search-index/search-index.jsonl`  
  追加式索引（query/hash/路径/top_urls）
- `memory/search-reports/YYYY-MM-DD/*.md`  
  人类可读报告（标题、链接、摘要）

推荐保留策略：

- cache：**14 天**
- reports：**长期保留**

---

## 真实配额支持情况

- **Tavily**：支持（官方 usage 接口）
- **SearchAPI**：支持（官方 account 接口）
- **Brave**：通过响应头探测（需 `--probe`，会消耗一次请求）
- **Serper**：不支持（无公开配额接口）
- **DuckDuckGo**：无配额概念

---

## 说明

- `@deep` 追求的是“覆盖深度”，不是无脑并发烧额度。
- 当配额占用偏高时，会自动降并发保护额度。
- 生产场景建议默认 `workers=1`，仅在需要时启用 `@dual/@deep`。
