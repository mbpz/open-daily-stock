# P5-10: Factor Analysis Engine Specification

## 1. Overview

**Goal**: Alpha discovery, IC/IR analysis, factor decay monitoring for quantitative finance.

**Module**: `src/factor_engine.py`

**Dependencies**: `src/storage.py` (DatabaseManager), `src/shared/indicators.py`

## 2. Factor Definition

```python
@dataclass
class Factor:
    name: str          # e.g., "pe_ratio", "momentum_5d"
    description: str   # e.g., "Price-to-Earnings ratio (市盈率)"
    formula: str       # e.g., "close / earnings_per_share"
    category: str      # "valuation" | "momentum" | "technical" | "fundamental"
```

### Predefined Factors (7 total)

| Name | Description | Category |
|------|-------------|----------|
| `pe_ratio` | Price-to-Earnings ratio (市盈率) | valuation |
| `pb_ratio` | Price-to-Book ratio (市净率) | valuation |
| `momentum_5d` | 5-day price momentum (%) | momentum |
| `momentum_20d` | 20-day price momentum (%) | momentum |
| `volume_ratio` | Volume / 5-day avg volume | technical |
| `ma_golden_cross` | MA5 > MA20 signal (1.0=golden cross, 0.5=bullish, 0.0=none) | technical |
| `rsi_14` | RSI(14) in range [0, 100] | technical |

## 3. FactorEngine API

### 3.1 `compute_factor(code, factor_name, history_data=None, target_date=None) -> float`

Computes factor value for a single stock.

- Uses `history_data` if provided, otherwise fetches from DB
- Returns `None` if insufficient data or unknown factor

### 3.2 `compute_ic(factor_name, start_date=None, end_date=None, codes=None) -> float`

**IC (Information Coefficient)** = Pearson correlation between factor values[t] and future_returns[t+1].

- Cross-sectional correlation across all stocks at each time point
- Returns `None` if < 10 observations

### 3.3 `compute_ir(factor_name, lookback_days=60, end_date=None, codes=None) -> float`

**IR (Information Ratio)** = mean(IC_series) / std(IC_series)

- Computes rolling IC values over time
- Returns `None` if < 2 IC values

### 3.4 `get_factor_rank(code, factor_name, ranking_date=None) -> int`

Returns rank of a stock among all stocks (1 = highest factor value).

### 3.5 `compute_factor_decay(factor_name, lookback_days=120, window_days=20) -> Dict`

Rolling IC analysis to detect predictive power decay.

Returns:
```python
{
    "dates": ["2025-01-01", ...],    # Oldest first
    "rolling_ic": [0.15, ...],        # Oldest first
    "trend": "positive|negative|stable",
    "latest_ic": 0.12,
    "avg_ic": 0.14,
}
```

Trend determination: linear regression slope on chronological IC series
- slope > 0.005: "positive" (improving)
- slope < -0.005: "negative" (decaying)
- else: "stable"

### 3.6 `get_factor_rankings(factor_name, ranking_date=None, top_n=50) -> List[Dict]`

Returns top N stocks ranked by factor value.

## 4. DataService Actions

Added to `src/data_service.py` action registry:

| Action | Handler | Params |
|--------|---------|--------|
| `get_factor_value` | `_handle_get_factor_value` | `code`, `factor_name` |
| `analyze_factor_ic` | `_handle_analyze_factor_ic` | `factor_name`, `start_date?`, `end_date?` |
| `get_factor_rankings` | `_handle_get_factor_rankings` | `factor_name`, `date?`, `top_n?` |

## 5. Implementation Notes

- **IC calculation**: Pearson correlation on paired (factor_value, future_return) observations
- **IR calculation**: Uses rolling IC with 5-day intervals over lookback period
- **Factor decay**: Rolling IC with configurable window size (default 20 days)
- **Database access**: Uses `DatabaseManager.get_data_range()` for historical OHLCV data
- **Singular value for `get_factor_rankings`**: Each code computed individually; no bulk query

## 6. Testing

Test file: `tests/test_factor_engine.py` (47 tests)

Coverage:
- Factor dataclass creation and immutability
- Predefined factor structure (7 factors)
- Factor computation: momentum, volume_ratio, RSI, MA golden cross, PE, PB
- Pearson correlation: perfect positive/negative, no correlation, edge cases
- Factor rank: highest, lowest, not in codes
- Factor decay: positive/negative/stable trends, insufficient windows
- DataService action methods
- Edge cases: empty history, None values, zero division protection