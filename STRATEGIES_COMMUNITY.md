# Strategy Community Guide

open-daily-stock supports community-contributed trading strategies. Share your strategies, discover others', and backtest them all locally.

## Quick Start

### Export a Strategy (GUI)
1. Open **策略管理** page
2. Select a strategy → click **导出**
3. A `.json` file is saved to `strategies/`

### Import a Strategy (GUI)
1. Open **策略管理** page
2. Click **导入**
3. Select a `.json` strategy file
4. The strategy appears in your list — ready for backtest

### CLI / API
```python
# List all strategies
client._send_request("list_strategies")

# Export a strategy
client._send_request("export_strategy", {
    "name": "My MA Cross",
    "params": {"fast": 5, "slow": 20, "stop_loss_pct": 5.0},
    "entry_rule": "MA5 crosses above MA20",
    "exit_rule": "MA5 crosses below MA20 or stop loss",
})

# Import a strategy
client._send_request("import_strategy", {"data": json_string})

# Run backtest with imported strategy
client._send_request("run_backtest", {
    "code": "600519",
    "initial_capital": 100000,
    "strategy": "ma_cross",
    "strategy_params": {"fast": 8, "slow": 30},
})
```

## Strategy JSON Format

```json
{
  "name": "My Strategy",
  "version": "1.0",
  "description": "Description of the strategy logic",
  "author": "your-github-username",
  "params": {
    "fast_ma": 5,
    "slow_ma": 20,
    "initial_capital": 100000,
    "stop_loss_pct": -5.0
  },
  "code": "python",
  "indicators": ["ma5", "ma20"],
  "entry_rule": "MA5 crosses above MA20",
  "exit_rule": "MA5 crosses below MA20 or stop loss"
}
```

### Fields

| Field | Type | Required | Description |
|-------|------|:---:|------|
| `name` | string | ✅ | Unique strategy name |
| `version` | string | | Semantic version (default: "1.0") |
| `description` | string | | What the strategy does |
| `author` | string | | GitHub username for attribution |
| `params` | object | ✅ | Tunable parameters |
| `code` | string | | Strategy language (default: "python") |
| `indicators` | string[] | | Technical indicators used |
| `entry_rule` | string | | Entry condition description |
| `exit_rule` | string | | Exit condition description |

## Writing Python Strategies (Advanced)

For programmatic strategies with custom logic, extend `BaseStrategy`:

```python
from src.strategies.base import BaseStrategy
from typing import Dict, List, Tuple

class MyStrategy(BaseStrategy):
    name = "my_strategy"
    display_name = "My Custom Strategy"
    description = "RSI + Volume breakout combo"
    category = "momentum"
    params = {"rsi_period": 14, "vol_mult": 1.5, "stop_loss_pct": 5.0}

    def entry_signal(self, data: List[Dict], idx: int) -> Tuple[bool, str]:
        # Your entry logic here
        ...

    def exit_signal(self, data: List[Dict], idx: int, entry_idx: int, entry_price: float) -> Tuple[bool, str]:
        # Your exit logic here
        ...
```

Place your strategy in `strategies/` as `my_strategy.py` and it will be auto-discovered.

## Sharing Strategies

1. Export your strategy as JSON from the GUI
2. Fork [open-daily-stock-strategies](https://github.com/mbpz/open-daily-stock-strategies)
3. Add your `.json` file to the `strategies/` directory
4. Submit a Pull Request

## Community Repository

- **Template:** [open-daily-stock-strategies](https://github.com/mbpz/open-daily-stock-strategies)
- **Format:** One `.json` file per strategy in `strategies/`
- **Review:** Strategies are reviewed for correctness before merging
- **Attribution:** Authors are credited in the strategy metadata

## Built-in Strategies

open-daily-stock ships with 8 built-in Python strategies:

| Strategy | Category | Description |
|----------|----------|-------------|
| `ma_cross` | trend | MA golden cross / death cross |
| `rsi_strategy` | mean_reversion | RSI oversold/overbought |
| `macd_strategy` | trend | MACD golden cross |
| `bollinger` | mean_reversion | Bollinger Bands touch |
| `kdj_strategy` | mean_reversion | KDJ golden cross |
| `volume_break` | volume | Volume breakout above resistance |
| `trend_follow` | trend | MA alignment pullback |
| `mean_revert` | mean_reversion | Mean reversion from deviation |

Use these as starting points for your own strategies.
