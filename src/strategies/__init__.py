"""Strategy registry and loader for P6-1.

Supports two strategy formats:
  1. YAML DSL — loaded from root strategies/*.yaml (legacy)
  2. Python BaseStrategy subclasses — programmatic, parameterized (new)
"""

from __future__ import annotations

import glob
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from src.strategies.base import BaseStrategy, TradeSignal
from src.strategies.builtin import BUILTIN_STRATEGIES

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# YAML-based Strategy dataclass (legacy)
# ---------------------------------------------------------------------------

class Strategy:
    """A loaded YAML trading strategy with conditions and scoring rules."""

    def __init__(
        self,
        name: str,
        display_name: str,
        description: str,
        category: str,
        required_indicators: List[str],
        conditions: Dict[str, List[Dict]],
        scoring: Dict[str, Any],
        signal_output: Dict[str, str],
        aliases: Optional[List[str]] = None,
        default_active: bool = False,
        default_router: bool = False,
        default_priority: int = 50,
    ):
        self.name = name
        self.display_name = display_name
        self.description = description
        self.category = category
        self.required_indicators = required_indicators
        self.conditions = conditions
        self.scoring = scoring
        self.signal_output = signal_output
        self.aliases = aliases or []
        self.default_active = default_active
        self.default_router = default_router
        self.default_priority = default_priority

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Strategy":
        return cls(
            name=data["name"],
            display_name=data.get("display_name", data["name"]),
            description=data.get("description", ""),
            category=data.get("category", "custom"),
            required_indicators=data.get("required_indicators", []),
            conditions=data.get("conditions", {}),
            scoring=data.get("scoring", {}),
            signal_output=data.get("signal_output", {}),
            aliases=data.get("aliases", []),
            default_active=data.get("default_active", False),
            default_router=data.get("default_router", False),
            default_priority=data.get("default_priority", 50),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "display_name": self.display_name,
            "description": self.description,
            "category": self.category,
            "required_indicators": self.required_indicators,
            "conditions": self.conditions,
            "scoring": self.scoring,
            "signal_output": self.signal_output,
            "aliases": self.aliases,
            "default_active": self.default_active,
            "default_router": self.default_router,
            "default_priority": self.default_priority,
        }


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

_STRATEGIES_DIR = Path(__file__).parent.parent.parent / "strategies"

# Unified registry: name → Strategy | BaseStrategy subclass
_REGISTRY: Optional[Dict[str, Any]] = None
# Python strategy instances (lazy)
_PYTHON_INSTANCES: Optional[Dict[str, BaseStrategy]] = None


def _load_yaml(path: Path) -> Optional[Dict]:
    try:
        with open(path, encoding="utf-8") as f:
            return yaml.safe_load(f)
    except Exception as e:
        logger.warning(f"Failed to load strategy {path}: {e}")
        return None


def _build_registry() -> Dict[str, Any]:
    """Load all YAML strategies and register Python builtins."""
    strategies: Dict[str, Any] = {}

    # Load YAML strategies from root strategies/ directory
    patterns = [
        str(_STRATEGIES_DIR / "*.yaml"),
        str(_STRATEGIES_DIR / "*.yml"),
    ]
    for pattern in patterns:
        for path in glob.glob(pattern):
            fname = Path(path).stem
            if fname.startswith("_") or fname.startswith("."):
                continue
            data = _load_yaml(Path(path))
            if not data or "name" not in data:
                continue
            try:
                strat = Strategy.from_dict(data)
                strategies[strat.name] = strat
                for alias in strat.aliases:
                    strategies[alias] = strat
                logger.debug(f"Loaded YAML strategy: {strat.name}")
            except Exception as e:
                logger.warning(f"Invalid strategy {path}: {e}")

    # Register Python builtins
    for cls in BUILTIN_STRATEGIES:
        instance = cls()
        strategies[instance.name] = instance
        logger.debug(f"Registered Python strategy: {instance.name} ({instance.display_name})")

    return strategies


def get_strategy_registry() -> Dict[str, Any]:
    """Return the unified strategy registry (lazy-loaded singleton)."""
    global _REGISTRY
    if _REGISTRY is None:
        _REGISTRY = _build_registry()
    return _REGISTRY


def get_strategy(name: str) -> Optional[Any]:
    """Look up a strategy by name. Returns Strategy (YAML) or BaseStrategy (Python)."""
    return get_strategy_registry().get(name)


def get_python_strategy(name: str) -> Optional[BaseStrategy]:
    """Get a Python BaseStrategy instance by name. Returns a fresh instance each time."""
    registry = get_strategy_registry()
    entry = registry.get(name)
    if isinstance(entry, BaseStrategy):
        # Return a fresh instance with default params
        return entry.__class__()
    return None


def list_strategies(category: Optional[str] = None) -> List[Any]:
    """List all strategies, optionally filtered by category."""
    seen: set = set()
    results: List[Any] = []
    for strat in get_strategy_registry().values():
        sid = strat.name if hasattr(strat, "name") else id(strat)
        if sid in seen:
            continue
        seen.add(sid)
        cat = strat.category if hasattr(strat, "category") else getattr(strat, "category", "")
        if category is None or cat == category:
            results.append(strat)
    return results


def list_categories() -> List[str]:
    """Return sorted list of unique categories."""
    cats = set()
    for s in get_strategy_registry().values():
        cats.add(s.category if hasattr(s, "category") else getattr(s, "category", "custom"))
    return sorted(cats)
