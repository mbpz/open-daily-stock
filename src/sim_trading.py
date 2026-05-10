"""Simulated trading with virtual 1,000,000 CNY account."""
import threading
from dataclasses import dataclass, field
from datetime import datetime, date
from typing import Dict, List, Optional
import json
import logging

logger = logging.getLogger(__name__)

INITIAL_CAPITAL = 1_000_000.0  # ¥


@dataclass
class SimPosition:
    code: str
    name: str
    shares: int
    buy_price: float
    buy_date: str
    current_price: float = 0.0

    @property
    def cost(self) -> float:
        return self.shares * self.buy_price

    @property
    def market_value(self) -> float:
        return self.shares * self.current_price

    @property
    def pnl(self) -> float:
        return self.market_value - self.cost

    @property
    def pnl_pct(self) -> float:
        return (self.pnl / self.cost) * 100 if self.cost > 0 else 0

    def to_dict(self) -> Dict:
        return {
            "code": self.code,
            "name": self.name,
            "shares": self.shares,
            "buy_price": self.buy_price,
            "buy_date": self.buy_date,
            "current_price": self.current_price,
            "cost": self.cost,
            "market_value": self.market_value,
            "pnl": self.pnl,
            "pnl_pct": round(self.pnl_pct, 2),
        }

    @classmethod
    def from_dict(cls, d: Dict) -> "SimPosition":
        return cls(
            code=d["code"],
            name=d["name"],
            shares=d["shares"],
            buy_price=d["buy_price"],
            buy_date=d["buy_date"],
            current_price=d.get("current_price", 0.0),
        )


@dataclass
class SimAccount:
    cash: float = INITIAL_CAPITAL
    positions: Dict[str, SimPosition] = field(default_factory=dict)
    trade_history: List[Dict] = field(default_factory=list)
    total_commission: float = 0.0
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    @property
    def total_assets(self) -> float:
        return self.cash + sum(p.market_value for p in self.positions.values())

    @property
    def total_pnl(self) -> float:
        return self.total_assets - INITIAL_CAPITAL

    @property
    def total_pnl_pct(self) -> float:
        return (self.total_pnl / INITIAL_CAPITAL) * 100

    def buy(self, code: str, name: str, price: float, shares: int = 100) -> Dict:
        """Buy stock. Returns result dict."""
        with self._lock:
            cost = price * shares
            commission = max(cost * 0.00025, 5.0)  # min commission ¥5
            total_cost = cost + commission

            if total_cost > self.cash:
                return {"status": "error", "message": f"资金不足，需要 ¥{total_cost:.2f}，可用 ¥{self.cash:.2f}"}

            self.cash -= total_cost
            self.total_commission += commission

            if code in self.positions:
                # Average up/down
                pos = self.positions[code]
                total_shares = pos.shares + shares
                pos.buy_price = (pos.cost + cost) / total_shares
                pos.shares = total_shares
            else:
                self.positions[code] = SimPosition(
                    code=code, name=name, shares=shares,
                    buy_price=price, buy_date=date.today().isoformat(),
                    current_price=price
                )

            trade = {"action": "buy", "code": code, "name": name, "price": price,
                     "shares": shares, "cost": total_cost, "time": datetime.now().isoformat()}
            self.trade_history.append(trade)
            return {"status": "ok", "message": f"买入 {name} {shares}股 @{price:.2f}", "trade": trade}

    def sell(self, code: str, price: float, shares: Optional[int] = None) -> Dict:
        """Sell stock. If shares is None, sell all."""
        with self._lock:
            if code not in self.positions:
                return {"status": "error", "message": f"未持有 {code}"}

            pos = self.positions[code]
            sell_shares = shares or pos.shares

            if sell_shares > pos.shares:
                return {"status": "error", "message": f"持仓不足，持有 {pos.shares}股"}

            revenue = price * sell_shares
            commission = max(revenue * 0.00025, 5.0)
            stamp_tax = revenue * 0.001  # 印花税
            net_revenue = revenue - commission - stamp_tax

            self.cash += net_revenue
            self.total_commission += commission

            trade = {"action": "sell", "code": code, "name": pos.name, "price": price,
                     "shares": sell_shares, "revenue": net_revenue, "pnl": (price - pos.buy_price) * sell_shares,
                     "time": datetime.now().isoformat()}
            self.trade_history.append(trade)

            if sell_shares == pos.shares:
                del self.positions[code]
            else:
                pos.shares -= sell_shares

            return {"status": "ok", "message": f"卖出 {trade['name']} {sell_shares}股 @{price:.2f}", "trade": trade}

    def update_prices(self, prices: Dict[str, float]):
        """Update current prices for all positions."""
        with self._lock:
            for code, price in prices.items():
                if code in self.positions:
                    self.positions[code].current_price = price

    def get_summary(self) -> Dict:
        return {
            "cash": round(self.cash, 2),
            "total_assets": round(self.total_assets, 2),
            "total_pnl": round(self.total_pnl, 2),
            "total_pnl_pct": round(self.total_pnl_pct, 2),
            "position_count": len(self.positions),
            "positions": [p.to_dict() for p in self.positions.values()],
            "total_commission": round(self.total_commission, 2),
            "trade_count": len(self.trade_history),
        }

    def to_dict(self) -> Dict:
        """Serialize entire account state for persistence."""
        return {
            "cash": self.cash,
            "positions": {code: pos.to_dict() for code, pos in self.positions.items()},
            "trade_history": self.trade_history,
            "total_commission": self.total_commission,
        }

    @classmethod
    def from_dict(cls, d: Dict) -> "SimAccount":
        """Deserialize account state from persistence."""
        account = cls(
            cash=d.get("cash", INITIAL_CAPITAL),
            total_commission=d.get("total_commission", 0.0),
        )
        for code, pos_data in d.get("positions", {}).items():
            account.positions[code] = SimPosition.from_dict(pos_data)
        account.trade_history = d.get("trade_history", [])
        return account
