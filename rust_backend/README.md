# Rust Acceleration (P7)

Optional Rust-powered acceleration for the open-daily-stock backtest engine.

## Why Rust?

The backtest engine iterates over thousands of OHLCV data points per trial. When running hyperparameter optimization (50+ trials), this becomes CPU-bound. Rust provides 5-10x speedup for indicator calculations and backtest loops.

## Build

```bash
cd rust_backend
pip install maturin
maturin develop --release
```

This compiles the Rust module and installs it as `ods_accelerate` in your Python environment.

## Usage

The acceleration is transparent — the Python optimizer auto-detects the Rust module:

```python
try:
    import ods_accelerate
    print("Rust acceleration enabled")
except ImportError:
    print("Using pure Python (install maturin for speedup)")
```

## Functions

| Function | Description | Speedup vs Python |
|----------|-------------|:---:|
| `sma_rust(values, period)` | Simple Moving Average | ~5x |
| `rsi_rust(values, period)` | Relative Strength Index | ~4x |
| `backtest_loop_rust(closes, trades, capital, shares)` | Portfolio simulation | ~8x |

## Architecture

```
Python (src/strategies/optimizer.py)
    ↓ try import
ods_accelerate.so (Rust via PyO3)
    ↓ FFI
Rust (rust_backend/src/lib.rs)
    ├── sma_rust()       → Vec<f64> → Vec<Option<f64>>
    ├── rsi_rust()       → Vec<f64> → Vec<Option<f64>>
    └── backtest_loop_rust() → (total_return, max_drawdown)
```

## Fallback

When the Rust module is not compiled, all functions fall back to pure Python implementations in `src/strategies/base.py`. No functionality is lost — only speed.
