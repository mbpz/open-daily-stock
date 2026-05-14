"""Built-in Python strategy implementations (P6-1)."""
from src.strategies.builtin.ma_cross import MACrossStrategy
from src.strategies.builtin.rsi_strategy import RSIStrategy
from src.strategies.builtin.macd_strategy import MACDStrategy
from src.strategies.builtin.bollinger import BollingerStrategy
from src.strategies.builtin.kdj_strategy import KDJStrategy
from src.strategies.builtin.volume_break import VolumeBreakStrategy
from src.strategies.builtin.trend_follow import TrendFollowStrategy
from src.strategies.builtin.mean_revert import MeanRevertStrategy

BUILTIN_STRATEGIES = [
    MACrossStrategy,
    RSIStrategy,
    MACDStrategy,
    BollingerStrategy,
    KDJStrategy,
    VolumeBreakStrategy,
    TrendFollowStrategy,
    MeanRevertStrategy,
]

__all__ = [
    "MACrossStrategy",
    "RSIStrategy",
    "MACDStrategy",
    "BollingerStrategy",
    "KDJStrategy",
    "VolumeBreakStrategy",
    "TrendFollowStrategy",
    "MeanRevertStrategy",
    "BUILTIN_STRATEGIES",
]
