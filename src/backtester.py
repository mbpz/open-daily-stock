"""Simple backtester engine for stock strategy testing"""
from dataclasses import dataclass
from typing import List, Dict, Callable, Optional, Tuple
from datetime import datetime


@dataclass
class BacktestResult:
    """回测结果 dataclass"""
    total_return: float        # 总收益率 (%)
    max_drawdown: float       # 最大回撤 (%)
    sharpe_ratio: float       # 夏普比率
    num_trades: int          # 交易次数
    win_rate: float          # 胜率 (%)


def ma_crossover_strategy(data: List[Dict]) -> List[Dict]:
    """MA5/MA20 crossover strategy, returns list of trades

    Buy when MA5 crosses above MA20
    Sell when MA5 crosses below MA20

    Args:
        data: List of daily OHLCV data with fields: date, open, high, low, close, volume, pct_chg

    Returns:
        List of trade dicts: [{"date": str, "action": "buy"|"sell", "price": float, "shares": int}]
    """
    if len(data) < 20:
        return []

    trades = []
    position = None  # None = no position, "long" = holding

    # Calculate MA5 and MA20 for each day
    ma_values = []
    for i in range(len(data)):
        if i < 19:
            ma_values.append({"ma5": None, "ma20": None})
        else:
            # Calculate MA5 (average of last 5 closes)
            ma5 = sum(data[j]["close"] for j in range(i - 4, i + 1)) / 5
            # Calculate MA20 (average of last 20 closes)
            ma20 = sum(data[j]["close"] for j in range(i - 19, i + 1)) / 20
            ma_values.append({"ma5": ma5, "ma20": ma20})

    # Detect crossover signals
    for i in range(1, len(ma_values)):
        prev = ma_values[i - 1]
        curr = ma_values[i]

        if prev["ma5"] is None or prev["ma20"] is None:
            continue
        if curr["ma5"] is None or curr["ma20"] is None:
            continue

        # Buy signal: MA5 crosses above MA20
        if prev["ma5"] <= prev["ma20"] and curr["ma5"] > curr["ma20"]:
            if position is None:  # Only buy if not already holding
                trades.append({
                    "date": data[i]["date"],
                    "action": "buy",
                    "price": data[i]["close"],
                    "shares": 100  # Default: 100 shares per trade
                })
                position = "long"

        # Sell signal: MA5 crosses below MA20
        elif prev["ma5"] >= prev["ma20"] and curr["ma5"] < curr["ma20"]:
            if position == "long":  # Only sell if holding
                trades.append({
                    "date": data[i]["date"],
                    "action": "sell",
                    "price": data[i]["close"],
                    "shares": 100
                })
                position = None

    return trades


def _calculate_returns(data: List[Dict], trades: List[Dict], initial_capital: float) -> Tuple[List[float], List[float]]:
    """Calculate portfolio value over time and returns

    Returns:
        Tuple of (portfolio_values, daily_returns)
    """
    if not trades:
        # No trades, portfolio stays at initial capital
        return [initial_capital], []

    # Build trade ledger
    cash = initial_capital
    shares = 0
    position_entry_price = 0

    portfolio_values = []
    trade_index = 0

    for i, day in enumerate(data):
        current_date = day["date"]

        # Process any trades on this date
        while trade_index < len(trades) and trades[trade_index]["date"] == current_date:
            trade = trades[trade_index]
            if trade["action"] == "buy":
                # Buy shares
                cost = trade["price"] * trade["shares"]
                if cash >= cost:
                    cash -= cost
                    shares += trade["shares"]
                    position_entry_price = trade["price"]
                    trade_index += 1
                else:
                    # Not enough cash to buy
                    break
            elif trade["action"] == "sell":
                # Sell shares
                proceeds = trade["price"] * trade["shares"]
                cash += proceeds
                shares = 0
                position_entry_price = 0
                trade_index += 1

        # Calculate portfolio value
        portfolio_value = cash + shares * day["close"]
        portfolio_values.append(portfolio_value)

    # Calculate daily returns
    daily_returns = []
    for i in range(1, len(portfolio_values)):
        if portfolio_values[i - 1] > 0:
            ret = (portfolio_values[i] - portfolio_values[i - 1]) / portfolio_values[i - 1] * 100
            daily_returns.append(ret)

    return portfolio_values, daily_returns


def _calculate_max_drawdown(portfolio_values: List[float]) -> float:
    """Calculate maximum drawdown (%)
    """
    if len(portfolio_values) < 2:
        return 0.0

    peak = portfolio_values[0]
    max_dd = 0.0

    for value in portfolio_values:
        if value > peak:
            peak = value
        drawdown = (peak - value) / peak * 100
        if drawdown > max_dd:
            max_dd = drawdown

    return -max_dd  # Negative for convention


def _calculate_sharpe_ratio(daily_returns: List[float], risk_free_rate: float = 0.0) -> float:
    """Calculate Sharpe ratio

    Sharpe = (mean_return - risk_free_rate) / stddev_return
    Assuming daily returns, annualized by * sqrt(252)
    """
    if len(daily_returns) < 2:
        return 0.0

    import statistics

    mean_ret = statistics.mean(daily_returns)
    std_ret = statistics.stdev(daily_returns)

    if std_ret == 0:
        return 0.0

    # Annualize the Sharpe ratio (daily * sqrt(252))
    excess_return = mean_ret - risk_free_rate / 252
    sharpe = (excess_return / std_ret) * (252 ** 0.5)

    return sharpe


def backtest(history_data: List[Dict], initial_capital: float, strategy_fn: Callable) -> BacktestResult:
    """Run backtest on historical data

    Args:
        history_data: List of daily OHLCV data
        initial_capital: Starting capital
        strategy_fn: Strategy function that takes data and returns trades

    Returns:
        BacktestResult with metrics
    """
    if not history_data or initial_capital <= 0:
        return BacktestResult(
            total_return=0.0,
            max_drawdown=0.0,
            sharpe_ratio=0.0,
            num_trades=0,
            win_rate=0.0
        )

    # Run strategy to get trades
    trades = strategy_fn(history_data)

    # Calculate portfolio values
    portfolio_values, daily_returns = _calculate_returns(history_data, trades, initial_capital)

    # Calculate metrics
    final_value = portfolio_values[-1]
    total_return = (final_value - initial_capital) / initial_capital * 100

    max_drawdown = _calculate_max_drawdown(portfolio_values)

    sharpe_ratio = _calculate_sharpe_ratio(daily_returns)

    # Count trades and wins
    num_trades = len(trades)
    winning_trades = 0

    # Track positions to calculate P&L
    cash = initial_capital
    shares = 0
    position_entry_price = 0

    for trade in trades:
        if trade["action"] == "buy":
            cost = trade["price"] * trade["shares"]
            if cash >= cost:
                cash -= cost
                shares += trade["shares"]
                position_entry_price = trade["price"]
        elif trade["action"] == "sell":
            if shares > 0:
                proceeds = trade["price"] * trade["shares"]
                pnl = proceeds - (position_entry_price * shares)
                if pnl > 0:
                    winning_trades += 1
                cash += proceeds
                shares = 0
                position_entry_price = 0

    win_rate = (winning_trades / num_trades * 100) if num_trades > 0 else 0.0

    return BacktestResult(
        total_return=round(total_return, 2),
        max_drawdown=round(max_drawdown, 2),
        sharpe_ratio=round(sharpe_ratio, 2),
        num_trades=num_trades,
        win_rate=round(win_rate, 2)
    )
