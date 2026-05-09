# ADR-004: DataFetcherManager 策略模式

**Date:** 2026-05-10
**Status:** Accepted

---

## Context

open-daily-stock 依赖多个免费数据源获取 A 股、港股、美股行情数据。可用的数据源包括：

- **AkShare** — 免费 A 股数据（主要来源）
- **efinance** — 免费 A 股数据（替代来源）
- **YFinance** — 港股/美股数据（主要来源）
- **Tushare** — 需注册 Token 的 A 股数据（增强来源）
- **Baostock** — 免费 A 股历史数据
- **PyTDX** — 通达信数据接口

这些免费数据源有两个共性问题：

1. **不稳定** — API 可能随时限流、封 IP、或服务不可用
2. **数据覆盖不同** — AkShare 覆盖 A 股，YFinance 覆盖港美股，单一源无法满足所有市场

需要一种机制：在数据源故障时自动降级到下一个可用源，同时支持按市场类型选择合适的数据源。

## Decision

采用 **策略模式 (Strategy Pattern)**，通过 `DataFetcherManager` 管理优先级排序的 Fetcher 列表，实现自动故障切换：

```
DataFetcherManager
    ├── fetcher_list: List[BaseFetcher]  (按优先级排序)
    ├── fetch(code, market, start, end)
    │       ├── 遍历 fetcher_list
    │       ├── 每个 fetcher fetch() 尝试获取
    │       ├── 成功 → 返回数据 + 写入 SQLite 缓存
    │       └── 失败 → 继续下一个 fetcher
    └── 指数退避重试 (tenacity)
```

### 数据源优先级（未配置 Tushare Token 时）

| 优先级 | Fetcher | 数据覆盖 |
|--------|---------|----------|
| 0 | EfinanceFetcher | A 股 |
| 1 | AkshareFetcher | A 股 |
| 2 | PytdxFetcher | A 股（通达信） |
| 2 | TushareFetcher | 不可用（无 Token） |
| 3 | BaostockFetcher | A 股历史 |
| 4 | YfinanceFetcher | 港股/美股 |

### 选择理由

1. **优雅降级** — 主力数据源不可用时自动切换到备用源，用户无感知
2. **扩展性** — 新增数据源只需实现 `BaseFetcher` 抽象基类，按优先级注册即可
3. **失败隔离** — 单个 Fetcher 崩溃不影响其他数据源
4. **缓存兜底** — 所有 Fetcher 均失败时，返回 SQLite 中缓存的历史数据
5. **标准化接口** — 所有 Fetcher 输出统一列名 (`date/open/high/low/close/volume/amount/pct_chg`)

### 实施

```python
# data_provider/base.py
class BaseFetcher(ABC):
    """数据源抽象基类"""
    @abstractmethod
    def fetch(self, code: str, market: str, start: str, end: str) -> pd.DataFrame:
        ...

class DataFetcherManager:
    """策略管理器 — 按优先级遍历 Fetcher 列表"""
    def __init__(self, fetchers: List[BaseFetcher]):
        self._fetchers = sorted(fetchers, key=lambda f: f.priority)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=30),
        retry=retry_if_exception_type(DataFetchError),
    )
    def fetch(self, code: str, market: str, start=None, end=None):
        for fetcher in self._fetchers:
            try:
                df = fetcher.fetch(code, market, start, end)
                if df is not None and not df.empty:
                    return df
            except DataSourceUnavailableError:
                logger.warning(f"{fetcher.name} unavailable, trying next")
                continue
        # 全部失败 — 回退到 SQLite 缓存
        return self._read_from_cache(code, market)
```

---

## Consequences

**正面：**
- 数据源故障时自动切换，提高可用性
- 新增数据源插件成本低（仅需实现 BaseFetcher）
- 所有 Fetcher 均失败时仍可通过缓存展示历史数据
- 标准化的数据列名简化下游处理

**负面：**
- 多源切换增加延迟（每个 Fetcher 超时后才尝试下一个）
- 不同数据源数据质量可能不一致（同一股票不同源的价格微小差异）
- 缓存数据可能滞后于实时行情（网络中断期间）

**替代方案考虑：**
- 单一数据源 + 重试：简单但单点故障导致无数据
- 并行请求所有数据源：浪费带宽且仍可能全部失败
- 付费数据源（Wind/东方财富）：稳定但不符合免费工具定位
