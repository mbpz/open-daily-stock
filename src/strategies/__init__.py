"""Strategy registry and loader for P6-1 YAML strategy DSL."""
from __future__ import annotations
import os
import glob
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any

import yaml

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Strategy dataclass
# ---------------------------------------------------------------------------

class Strategy:
    """A loaded trading strategy with conditions and scoring rules."""

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
        self.conditions = conditions  # "entry" / "exit" lists of condition dicts
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
_REGISTRY: Optional[Dict[str, Strategy]] = None


def _load_yaml(path: Path) -> Optional[Dict]:
    try:
        with open(path, encoding="utf-8") as f:
            return yaml.safe_load(f)
    except Exception as e:
        logger.warning(f"Failed to load strategy {path}: {e}")
        return None


def _build_registry() -> Dict[str, Strategy]:
    """Load all YAML strategy files and build the registry."""
    strategies: Dict[str, Strategy] = {}

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
                # Also index by aliases
                for alias in strat.aliases:
                    strategies[alias] = strat
                logger.debug(f"Loaded strategy: {strat.name}")
            except Exception as e:
                logger.warning(f"Invalid strategy {path}: {e}")

    return strategies


def get_strategy_registry() -> Dict[str, Strategy]:
    """Return the strategy registry (lazy-loaded singleton)."""
    global _REGISTRY
    if _REGISTRY is None:
        _REGISTRY = _build_registry()
    return _REGISTRY


def get_strategy(name: str) -> Optional[Strategy]:
    """Look up a strategy by name or alias."""
    return get_strategy_registry().get(name)


def list_strategies(category: Optional[str] = None) -> List[Strategy]:
    """List all strategies, optionally filtered by category.

    Returns only the canonical name-strategy entries (not aliases).
    """
    seen: set = set()
    results: List[Strategy] = []
    for strat in get_strategy_registry().values():
        if strat.name in seen:
            continue
        seen.add(strat.name)
        if category is None or strat.category == category:
            results.append(strat)
    return sorted(results, key=lambda s: s.default_priority)


def list_categories() -> List[str]:
    """Return sorted list of unique categories."""
    cats = {s.category for s in get_strategy_registry().values()}
    return sorted(cats)