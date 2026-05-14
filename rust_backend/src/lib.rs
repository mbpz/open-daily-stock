/// Rust acceleration for open-daily-stock backtest engine (P7).
///
/// Provides fast indicator calculations for use via PyO3 FFI.
/// Falls back to pure Python when the Rust extension is not compiled.
use pyo3::prelude::*;

/// Calculate Simple Moving Average over a window.
#[pyfunction]
fn sma_rust(values: Vec<f64>, period: usize) -> PyResult<Vec<Option<f64>>> {
    if period == 0 || values.len() < period {
        return Ok(vec![None; values.len()]);
    }
    let mut result = vec![None; period - 1];
    let mut sum: f64 = values[..period].iter().sum();
    result.push(Some(sum / period as f64));
    for i in period..values.len() {
        sum += values[i] - values[i - period];
        result.push(Some(sum / period as f64));
    }
    Ok(result)
}

/// Calculate Relative Strength Index.
#[pyfunction]
fn rsi_rust(values: Vec<f64>, period: usize) -> PyResult<Vec<Option<f64>>> {
    if values.len() < period + 1 {
        return Ok(vec![None; values.len()]);
    }
    let mut result = vec![None; period];
    let mut gains = 0.0;
    let mut losses = 0.0;
    for i in 1..=period {
        let delta = values[i] - values[i - 1];
        if delta > 0.0 { gains += delta; } else { losses -= delta; }
    }
    let mut avg_gain = gains / period as f64;
    let mut avg_loss = losses / period as f64;
    if avg_loss == 0.0 {
        result.push(Some(100.0));
    } else {
        let rs = avg_gain / avg_loss;
        result.push(Some(100.0 - 100.0 / (1.0 + rs)));
    }
    for i in period + 1..values.len() {
        let delta = values[i] - values[i - 1];
        let gain = if delta > 0.0 { delta } else { 0.0 };
        let loss = if delta < 0.0 { -delta } else { 0.0 };
        avg_gain = (avg_gain * (period - 1) as f64 + gain) / period as f64;
        avg_loss = (avg_loss * (period - 1) as f64 + loss) / period as f64;
        if avg_loss == 0.0 {
            result.push(Some(100.0));
        } else {
            let rs = avg_gain / avg_loss;
            result.push(Some(100.0 - 100.0 / (1.0 + rs)));
        }
    }
    Ok(result)
}

/// Fast backtest loop: iterate days, track position, compute portfolio value.
#[pyfunction]
fn backtest_loop_rust(
    closes: Vec<f64>,
    trades: Vec<(usize, bool, f64)>, // (day_index, is_buy, price)
    initial_capital: f64,
    shares_per_trade: f64,
) -> PyResult<(f64, f64)> {
    // Returns (total_return_pct, max_drawdown_pct)
    let mut cash = initial_capital;
    let mut shares = 0.0;
    let mut trade_idx = 0;
    let mut peak = initial_capital;
    let mut max_dd = 0.0f64;

    for (day, &close) in closes.iter().enumerate() {
        while trade_idx < trades.len() && trades[trade_idx].0 == day {
            let (_day, is_buy, price) = trades[trade_idx];
            if is_buy {
                let cost = price * shares_per_trade;
                if cash >= cost {
                    cash -= cost;
                    shares += shares_per_trade;
                }
            } else {
                cash += price * shares;
                shares = 0.0;
            }
            trade_idx += 1;
        }
        let portfolio = cash + shares * close;
        if portfolio > peak {
            peak = portfolio;
        }
        let dd = (peak - portfolio) / peak * 100.0;
        if dd > max_dd {
            max_dd = dd;
        }
    }
    let total_return = (cash + shares * closes.last().unwrap_or(&0.0) - initial_capital) / initial_capital * 100.0;
    Ok((total_return, -max_dd))
}

/// Module registration.
#[pymodule]
fn ods_accelerate(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(sma_rust, m)?)?;
    m.add_function(wrap_pyfunction!(rsi_rust, m)?)?;
    m.add_function(wrap_pyfunction!(backtest_loop_rust, m)?)?;
    Ok(())
}
