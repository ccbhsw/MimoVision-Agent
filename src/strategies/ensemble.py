"""
集成策略融合
多个策略加权投票，生成综合交易信号
"""
import logging
from typing import Optional

from src.strategies.trend_following import TrendFollowingStrategy
from src.strategies.mean_reversion import MeanReversionStrategy
from src.strategies.breakout import BreakoutStrategy

logger = logging.getLogger(__name__)


class EnsembleStrategy:
    """集成策略融合 - 加权投票+冲突解决"""

    DEFAULT_WEIGHTS = {
        "trend_following": 0.45,
        "breakout": 0.35,
        "mean_reversion": 0.20,
    }

    def __init__(self, strategies: Optional[list] = None, weights: Optional[dict] = None):
        self.strategies = strategies or [
            TrendFollowingStrategy(),
            MeanReversionStrategy(),
            BreakoutStrategy(),
        ]
        self.weights = weights or self.DEFAULT_WEIGHTS
        self._history = []

    def generate_signal(self, indicators: dict) -> dict:
        signals = []
        for strategy in self.strategies:
            try:
                sig = strategy.generate_signal(indicators)
                sig["weight"] = self.weights.get(sig["strategy"], 0.15)
                signals.append(sig)
            except Exception as e:
                logger.warning(f"Strategy {type(strategy).__name__} failed: {e}")

        if not signals:
            return {"signal": "wait", "strength": 0, "confidence": 0.0,
                    "agreement": 0.0, "contributing_strategies": [], "reasons": ["无信号"]}

        vote_result = self._weighted_vote(signals)
        consistency = self._check_consistency(signals)

        if vote_result["signal"] == "wait" and consistency > 0.5:
            resolved = self._resolve_conflict(signals)
            vote_result = resolved

        all_reasons = []
        for sig in signals:
            if sig["signal"] == vote_result["signal"]:
                for r in sig.get("reasons", []):
                    all_reasons.append(f"[{sig['strategy']}] {r}")

        result = {
            "signal": vote_result["signal"],
            "strength": vote_result["strength"],
            "confidence": consistency,
            "agreement": round(consistency * 100, 1),
            "contributing_strategies": [s["strategy"] for s in signals if s["signal"] == vote_result["signal"]],
            "reasons": all_reasons[:10],
            "individual_signals": signals,
        }
        self._history.append(result)
        return result

    def _weighted_vote(self, signals: list[dict]) -> dict:
        votes = {"long": 0.0, "short": 0.0, "wait": 0.0}
        strength_sum = {"long": 0.0, "short": 0.0, "wait": 0.0}
        count = {"long": 0, "short": 0, "wait": 0}

        for sig in signals:
            w = sig.get("weight", 0.15)
            s = sig.get("strength", 50) / 100.0
            d = sig.get("signal", "wait")
            votes[d] += w * s
            strength_sum[d] += sig.get("strength", 0)
            count[d] += 1

        best = max(votes, key=votes.get)
        avg_s = strength_sum[best] / count[best] if count[best] > 0 else 0
        return {"signal": best, "strength": round(avg_s, 1)}

    def _check_consistency(self, signals: list[dict]) -> float:
        active = [s for s in signals if s["signal"] != "wait"]
        if not active:
            return 0.0
        dirs = [s["signal"] for s in active]
        most = max(set(dirs), key=dirs.count)
        return dirs.count(most) / len(active)

    def _resolve_conflict(self, signals: list[dict]) -> dict:
        active = [s for s in signals if s["signal"] != "wait"]
        if not active:
            return {"signal": "wait", "strength": 0}
        best = max(active, key=lambda s: s.get("weight", 0) * s.get("strength", 0))
        return {"signal": best["signal"], "strength": best["strength"]}

    def get_strategy_performance(self) -> dict:
        if not self._history:
            return {}
        total = len(self._history)
        counts = {"long": 0, "short": 0, "wait": 0}
        for r in self._history:
            counts[r.get("signal", "wait")] += 1
        return {
            "total_signals": total,
            "signal_distribution": counts,
            "avg_strength": sum(r.get("strength", 0) for r in self._history) / total,
            "avg_confidence": sum(r.get("confidence", 0) for r in self._history) / total,
        }
