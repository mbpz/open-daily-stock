# Strategies - Community Strategy Platform

## Overview

The strategy platform lets you save, share, and run backtest strategies as structured JSON files. Strategies define entry/exit rules, parameters, and indicators for the backtesting engine.

## Strategy JSON Format

```json
{
  "name": "MA Cross Strategy",
  "version": "1.0",
  "description": "Golden cross strategy using MA5/MA20",
  "author": "username",
  "params": {
    "fast_ma": 5,
    "slow_ma": 20,
    "initial_capital": 100000,
    "stop_loss_pct": -5.0
  },
  "code": "python",
  "indicators": ["ma5", "ma20"],
  "entry_rule": "MA5 crosses above MA20",
  "exit_rule": "MA5 crosses below MA20"
}
```

### Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | Yes | Unique strategy name |
| `version` | string | No | Semantic version (default: "1.0") |
| `description` | string | No | Human-readable description |
| `author` | string | No | Author/username for attribution |
| `params` | object | Yes | Strategy parameters (see below) |
| `code` | string | No | Strategy code language (default: "python") |
| `indicators` | string[] | No | List of indicator names used |
| `entry_rule` | string | No | Description of entry condition |
| `exit_rule` | string | No | Description of exit condition |

### Params Object

The `params` object contains tunable parameters for the strategy:

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `fast_ma` | int | 5 | Fast moving average period |
| `slow_ma` | int | 20 | Slow moving average period |
| `initial_capital` | float | 100000 | Starting capital for backtest |
| `stop_loss_pct` | float | -5.0 | Stop loss percentage (negative) |
| `code` | string | "000001" | Stock code for backtest |
| `days` | int | 60 | Lookback days for history data |

## How to Write a Strategy

1. Define your entry and exit rules clearly
2. Choose indicator parameters (MA periods, RSI thresholds, etc.)
3. Create a JSON file following the format above
4. Import it via the GUI (Import Strategy button) or TUI (press `i`)
5. Run backtest to validate performance

## Example Strategies

### MA Cross (Golden Cross)

```json
{
  "name": "MA Cross Strategy",
  "version": "1.0",
  "description": "Golden cross strategy using MA5/MA20",
  "author": "demo",
  "params": {
    "fast_ma": 5,
    "slow_ma": 20,
    "initial_capital": 100000,
    "stop_loss_pct": -5.0
  },
  "indicators": ["ma5", "ma20"],
  "entry_rule": "MA5 crosses above MA20",
  "exit_rule": "MA5 crosses below MA20"
}
```

### RSI + Bollinger Bands Combo

```json
{
  "name": "RSI + Bollinger Combo",
  "version": "1.0",
  "description": "Buy when RSI < 30 and price touches lower Bollinger band; sell when RSI > 70",
  "author": "demo",
  "params": {
    "rsi_period": 14,
    "rsi_oversold": 30,
    "rsi_overbought": 70,
    "bb_period": 20,
    "bb_std": 2,
    "initial_capital": 100000,
    "stop_loss_pct": -8.0
  },
  "indicators": ["rsi", "bollinger_upper", "bollinger_lower", "bollinger_mid"],
  "entry_rule": "RSI < 30 AND price <= Bollinger lower band",
  "exit_rule": "RSI > 70 OR price >= Bollinger upper band"
}
```

### MACD Divergence

```json
{
  "name": "MACD Divergence",
  "version": "1.0",
  "description": "MACD histogram divergence strategy",
  "author": "demo",
  "params": {
    "macd_fast": 12,
    "macd_slow": 26,
    "macd_signal": 9,
    "initial_capital": 100000,
    "stop_loss_pct": -5.0
  },
  "indicators": ["macd", "macd_signal", "macd_histogram"],
  "entry_rule": "MACD histogram turns positive after divergence",
  "exit_rule": "MACD histogram turns negative"
}
```

## How to Share Strategies

1. Export your strategy as a JSON file (GUI: Export button; TUI: the strategy files are in `strategies/` directory)
2. Share the `.json` file with the community
3. Consider contributing to the [open-daily-stock-strategies](https://github.com/mbpz/open-daily-stock-strategies) repository

## Storage

Strategies are stored as `.json` files in the `strategies/` directory at the project root. Each strategy gets its own file named after the strategy (sanitized for filesystem safety).

## CLI / API Access

The DataService exposes these actions:

```python
# List all saved strategies
client._send_request("list_strategies")

# Export (save) a strategy
client._send_request("export_strategy", {
    "name": "My Strategy",
    "params": {"fast_ma": 5, "slow_ma": 20, "initial_capital": 100000},
    "entry_rule": "MA5 crosses above MA20",
    "exit_rule": "MA5 crosses below MA20"
})

# Import a strategy from JSON
client._send_request("import_strategy", {"data": json_string})

# Delete a strategy
client._send_request("delete_strategy", {"name": "My Strategy"})
```
