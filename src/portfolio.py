"""Portfolio management - position tracking and P&L calculations"""
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Optional


@dataclass
class Position:
    """
    持仓数据结构

    Attributes:
        code: 股票代码
        name: 股票名称
        shares: 持股数量
        buy_price: 买入价格
        buy_date: 买入日期
        current_price: 当前价格（可选，默认等于买入价格）
        id: 持仓记录ID（数据库主键）
    """
    code: str
    name: str
    shares: float
    buy_price: float
    buy_date: date
    current_price: Optional[float] = None
    id: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    def __post_init__(self):
        """初始化后设置默认值"""
        if self.current_price is None:
            self.current_price = self.buy_price
        if self.created_at is None:
            self.created_at = datetime.now()
        if self.updated_at is None:
            self.updated_at = datetime.now()

    @property
    def cost_basis(self) -> float:
        """持仓成本 = 持股数量 × 买入价格"""
        return self.shares * self.buy_price

    @property
    def current_value(self) -> float:
        """当前市值 = 持股数量 × 当前价格"""
        return self.shares * (self.current_price or self.buy_price)

    @property
    def unrealized_pnl(self) -> float:
        """未实现盈亏 = 当前市值 - 成本"""
        return self.current_value - self.cost_basis

    @property
    def return_pct(self) -> float:
        """收益率(%) = (当前价格 - 买入价格) / 买入价格 × 100"""
        if self.buy_price == 0:
            return 0.0
        return ((self.current_price or self.buy_price) - self.buy_price) / self.buy_price * 100

    def to_dict(self) -> dict:
        """转换为字典（用于JSON序列化）"""
        return {
            "id": self.id,
            "code": self.code,
            "name": self.name,
            "shares": self.shares,
            "buy_price": self.buy_price,
            "buy_date": self.buy_date.isoformat() if isinstance(self.buy_date, date) else self.buy_date,
            "current_price": self.current_price,
            "cost_basis": self.cost_basis,
            "current_value": self.current_value,
            "unrealized_pnl": self.unrealized_pnl,
            "return_pct": self.return_pct,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Position":
        """从字典创建Position对象"""
        buy_date = data.get("buy_date")
        if isinstance(buy_date, str):
            buy_date = date.fromisoformat(buy_date)

        created_at = data.get("created_at")
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at)

        updated_at = data.get("updated_at")
        if isinstance(updated_at, str):
            updated_at = datetime.fromisoformat(updated_at)

        return cls(
            id=data.get("id"),
            code=data.get("code", ""),
            name=data.get("name", ""),
            shares=data.get("shares", 0),
            buy_price=data.get("buy_price", 0.0),
            buy_date=buy_date,
            current_price=data.get("current_price"),
            created_at=created_at,
            updated_at=updated_at,
        )