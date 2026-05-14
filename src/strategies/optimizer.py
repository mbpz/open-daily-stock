"""P7-5: Strategy hyperparameter optimization with Optuna (TPE sampler).

Finds optimal strategy parameters via Bayesian optimization.
Falls back to random search when Optuna is not installed.

Usage:
    from src.strategies.optimizer import HyperOptimizer
    from src.strategies.builtin import MACrossStrategy

    opt = HyperOptimizer()
    result = opt.optimize(MACrossStrategy, history_data, n_trials=50)
    print(f"Best params: {result.best_params}")
    print(f"Best Sharpe: {result.best_sharpe:.2f}")
"""

from __future__ import annotations

import logging
import random
import statistics
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple, Type

from src.strategies.base import BaseStrategy
from src.backtester import backtest, BacktestResult

logger = logging.getLogger(__name__)

DEFAULT_TRIALS = 50
DEFAULT_INITIAL_CAPITAL = 100000.0


@dataclass
class OptimizationResult:
    """Result of a hyperparameter optimization run."""

    strategy_name: str
    best_params: Dict[str, Any] = field(default_factory=dict)
    best_sharpe: float = 0.0
    best_return: float = 0.0
    best_win_rate: float = 0.0
    baseline_sharpe: Optional[float] = None  # Default params result
    trials: int = 0
    duration_seconds: float = 0.0
    trial_history: List[Dict[str, Any]] = field(default_factory=list)  # Top 10 trials

    def to_dict(self) -> Dict[str, Any]:
        return {
            "strategy_name": self.strategy_name,
            "best_params": self.best_params,
            "best_sharpe": round(self.best_sharpe, 4),
            "best_return": round(self.best_return, 2),
            "best_win_rate": round(self.best_win_rate, 2),
            "baseline_sharpe": round(self.baseline_sharpe, 4) if self.baseline_sharpe else None,
            "trials": self.trials,
            "duration_seconds": round(self.duration_seconds, 1),
            "trial_history": self.trial_history,
        }


# ---------------------------------------------------------------------------
# Default parameter spaces for built-in strategies
# ---------------------------------------------------------------------------

DEFAULT_PARAM_SPACES: Dict[str, Dict[str, tuple]] = {
    "ma_cross": {
        "fast": (3, 20, 1),
        "slow": (15, 60, 5),
        "stop_loss_pct": (2.0, 10.0, 1.0),
    },
    "rsi_strategy": {
        "period": (6, 21, 1),
        "oversold": (20.0, 40.0, 5.0),
        "overbought": (60.0, 80.0, 5.0),
        "stop_loss_pct": (2.0, 10.0, 1.0),
    },
    "macd_strategy": {
        "fast": (8, 16, 2),
        "slow": (20, 40, 2),
        "signal": (6, 15, 1),
        "stop_loss_pct": (2.0, 10.0, 1.0),
    },
    "bollinger": {
        "period": (10, 40, 5),
        "std_mult": (1.5, 3.0, 0.5),
        "stop_loss_pct": (2.0, 10.0, 1.0),
    },
    "kdj_strategy": {
        "n": (5, 14, 1),
        "m1": (2, 5, 1),
        "m2": (2, 5, 1),
        "oversold_entry": (20.0, 40.0, 5.0),
        "overbought_exit": (60.0, 80.0, 5.0),
        "stop_loss_pct": (2.0, 10.0, 1.0),
    },
    "volume_break": {
        "vol_period": (3, 15, 2),
        "vol_mult": (1.5, 4.0, 0.5),
        "resistance_lookback": (10, 60, 10),
        "stop_loss_pct": (2.0, 8.0, 1.0),
    },
    "trend_follow": {
        "short": (3, 15, 2),
        "medium": (15, 40, 5),
        "long": (40, 120, 20),
        "bias_limit": (1.0, 10.0, 1.0),
        "stop_loss_pct": (2.0, 10.0, 1.0),
    },
    "mean_revert": {
        "period": (10, 40, 5),
        "deviation_pct": (3.0, 15.0, 2.0),
        "target_pct": (0.5, 5.0, 0.5),
        "stop_loss_pct": (2.0, 10.0, 1.0),
    },
}


class HyperOptimizer:
    """Optimize strategy parameters using Optuna TPE or random search.

    Requires Optuna for Bayesian optimization. Falls back to random
    search when Optuna is not installed.
    """

    def __init__(self, initial_capital: float = DEFAULT_INITIAL_CAPITAL):
        self._initial_capital = initial_capital
        self._optuna_available = self._check_optuna()

    @staticmethod
    def _check_optuna() -> bool:
        try:
            import optuna  # noqa: F401
            return True
        except ImportError:
            return False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def optimize(
        self,
        strategy_cls: Type[BaseStrategy],
        history_data: List[Dict],
        n_trials: int = DEFAULT_TRIALS,
        param_space: Optional[Dict[str, tuple]] = None,
        objective: str = "sharpe",
    ) -> OptimizationResult:
        """Run hyperparameter optimization for a strategy.

        Args:
            strategy_cls: BaseStrategy subclass (e.g. MACrossStrategy).
            history_data: OHLCV data list for backtesting.
            n_trials: Number of optimization trials (default 50).
            param_space: Dict of param_name → (low, high, step).
                         If None, uses DEFAULT_PARAM_SPACES.
            objective: "sharpe" | "return" | "win_rate" — what to maximize.

        Returns:
            OptimizationResult with best parameters and metrics.
        """
        start_time = time.time()

        instance = strategy_cls()
        strategy_name = instance.name

        if param_space is None:
            param_space = DEFAULT_PARAM_SPACES.get(strategy_name, {})

        if not param_space:
            logger.warning(f"No parameter space defined for {strategy_name}")
            return OptimizationResult(strategy_name=strategy_name, trials=0)

        # Baseline: default params
        baseline = self._evaluate(strategy_cls, {}, history_data)
        baseline_sharpe = baseline.sharpe_ratio

        # Run optimization
        if self._optuna_available:
            best_params, best_metric, history = self._optimize_optuna(
                strategy_cls, history_data, param_space, n_trials, objective
            )
        else:
            logger.info("Optuna not available, using random search")
            best_params, best_metric, history = self._optimize_random(
                strategy_cls, history_data, param_space, n_trials, objective
            )

        # Final evaluation with best params
        final = self._evaluate(strategy_cls, best_params, history_data)
        duration = time.time() - start_time

        result = OptimizationResult(
            strategy_name=strategy_name,
            best_params=best_params,
            best_sharpe=final.sharpe_ratio,
            best_return=final.total_return,
            best_win_rate=final.win_rate,
            baseline_sharpe=baseline_sharpe,
            trials=n_trials,
            duration_seconds=duration,
            trial_history=history[:10],  # Top 10
        )

        improvement = (
            f"{(result.best_sharpe - baseline_sharpe):+.3f}"
            if baseline_sharpe is not None
            else "N/A"
        )
        logger.info(
            f"Optimization complete for {strategy_name}: "
            f"sharpe {baseline_sharpe:.3f}→{result.best_sharpe:.3f} "
            f"({improvement}), {n_trials} trials in {duration:.1f}s"
        )

        return result

    # ------------------------------------------------------------------
    # Optuna optimization
    # ------------------------------------------------------------------

    def _optimize_optuna(
        self,
        strategy_cls: Type[BaseStrategy],
        history_data: List[Dict],
        param_space: Dict[str, tuple],
        n_trials: int,
        objective: str,
    ) -> Tuple[Dict[str, Any], float, List[Dict]]:
        import optuna

        optuna.logging.set_verbosity(optuna.logging.WARNING)

        history: List[Dict] = []

        def objective_fn(trial: optuna.Trial) -> float:
            params = {}
            for name, spec in param_space.items():
                if len(spec) == 3:
                    low, high, step = spec
                    if isinstance(low, int) and isinstance(high, int):
                        params[name] = trial.suggest_int(name, low, high, step=max(1, step))
                    else:
                        params[name] = trial.suggest_float(name, low, high, step=step)
                elif len(spec) == 2 and isinstance(spec[0], list):
                    # Categorical
                    params[name] = trial.suggest_categorical(name, spec[0])

            metric = self._evaluate_metric(strategy_cls, params, history_data, objective)

            # Record trial
            if len(history) < 50:
                result = self._evaluate(strategy_cls, params, history_data)
                history.append({
                    "params": dict(params),
                    "sharpe": round(result.sharpe_ratio, 4),
                    "return": round(result.total_return, 2),
                })

            return metric

        sampler = optuna.samplers.TPESampler(seed=42)
        study = optuna.create_study(
            direction="maximize",
            sampler=sampler,
            study_name=f"ods_{strategy_cls.name}",
        )
        study.optimize(objective_fn, n_trials=n_trials, show_progress_bar=False)

        # Sort history by sharpe descending
        history.sort(key=lambda x: x["sharpe"], reverse=True)

        return dict(study.best_params), study.best_value, history

    # ------------------------------------------------------------------
    # Random search fallback
    # ------------------------------------------------------------------

    def _optimize_random(
        self,
        strategy_cls: Type[BaseStrategy],
        history_data: List[Dict],
        param_space: Dict[str, tuple],
        n_trials: int,
        objective: str,
    ) -> Tuple[Dict[str, Any], float, List[Dict]]:
        best_params = {}
        best_metric = float("-inf")
        history: List[Dict] = []

        for i in range(n_trials):
            params = {}
            for name, spec in param_space.items():
                if len(spec) == 3:
                    low, high, step = spec
                    if isinstance(low, int) and isinstance(high, int):
                        params[name] = random.randint(low, high)
                    else:
                        params[name] = round(random.uniform(low, high) / step) * step
                        params[name] = max(low, min(high, params[name]))
                elif len(spec) == 2:
                    params[name] = random.choice(spec[0])

            result = self._evaluate(strategy_cls, params, history_data)
            metric = self._extract_metric(result, objective)

            history.append({
                "params": dict(params),
                "sharpe": round(result.sharpe_ratio, 4),
                "return": round(result.total_return, 2),
            })

            if metric > best_metric:
                best_metric = metric
                best_params = dict(params)

        history.sort(key=lambda x: x["sharpe"], reverse=True)
        return best_params, best_metric, history

    # ------------------------------------------------------------------
    # Evaluation helpers
    # ------------------------------------------------------------------

    def _evaluate_metric(
        self,
        strategy_cls: Type[BaseStrategy],
        params: Dict[str, Any],
        history_data: List[Dict],
        objective: str,
    ) -> float:
        result = self._evaluate(strategy_cls, params, history_data)
        return self._extract_metric(result, objective)

    def _evaluate(
        self,
        strategy_cls: Type[BaseStrategy],
        params: Dict[str, Any],
        history_data: List[Dict],
    ) -> BacktestResult:
        instance = strategy_cls(**params)
        return backtest(history_data, self._initial_capital, instance)

    @staticmethod
    def _extract_metric(result: BacktestResult, objective: str) -> float:
        if objective == "sharpe":
            return result.sharpe_ratio if result.sharpe_ratio is not None else float("-inf")
        elif objective == "return":
            return result.total_return
        elif objective == "win_rate":
            return result.win_rate
        return result.sharpe_ratio

    # ------------------------------------------------------------------
    # Convenience
    # ------------------------------------------------------------------

    def get_param_space(self, strategy_name: str) -> Optional[Dict[str, tuple]]:
        """Return the default parameter space for a strategy."""
        return DEFAULT_PARAM_SPACES.get(strategy_name)

    def list_optimizable_strategies(self) -> List[str]:
        """Return names of all strategies with defined param spaces."""
        return list(DEFAULT_PARAM_SPACES.keys())
