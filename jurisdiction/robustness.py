"""How robust is the ranking to the choice of weights?

Three views:
- Monte Carlo on weights: draw random weight sets from a Dirichlet distribution centred on the base
  weights and count how often each country ranks first.
- Monte Carlo on scores: keep the base weights, move every score by a random -1, 0 or +1
  (clipped to 1-5) and count how often each country ranks first.
- Weight thresholds: move one criterion's weight (others scaled to keep the sum at 1) and find
  the nearest weight at which the base-case leader loses first place.
"""
from __future__ import annotations

import numpy as np

from .score import Dataset, rank, totals


def rank_shares(ds: Dataset, iterations: int = 5000, concentration: float = 50.0, seed: int = 42) -> dict[str, list[float]]:
    """For each country, the share of random weight sets in which it lands at rank 1, 2, ... n.

    concentration controls how far weights wander from the base: alpha = base_weight x concentration.
    50 means a 15% weight typically lands between ~10% and ~20%.
    """
    rng = np.random.default_rng(seed)
    keys = [c.key for c in ds.criteria]
    alpha = np.array([max(c.weight, 1e-6) for c in ds.criteria]) * concentration
    counts = {n.code: [0] * len(ds.countries) for n in ds.countries}
    for w in rng.dirichlet(alpha, size=iterations):
        for position, (code, _) in enumerate(rank(ds, dict(zip(keys, w)))):
            counts[code][position] += 1
    return {code: [x / iterations for x in row] for code, row in counts.items()}


def monte_carlo(ds: Dataset, iterations: int = 5000, concentration: float = 50.0, seed: int = 42) -> dict[str, float]:
    """Share of random weight sets in which each country ranks first."""
    return {code: row[0] for code, row in rank_shares(ds, iterations, concentration, seed).items()}


def score_uncertainty(ds: Dataset, iterations: int = 5000, seed: int = 42) -> dict[str, float]:
    """Share of draws in which each country ranks first when every score is uncertain by one point.

    Each draw adds an independent random integer from {-1, 0, +1} to every score, clips the result
    to 1-5 and ranks with the base weights. This tests the scores, not the weights.
    """
    rng = np.random.default_rng(seed)
    codes = [n.code for n in ds.countries]
    keys = [c.key for c in ds.criteria]
    base = np.array([[ds.score(k, code) for k in keys] for code in codes], dtype=float)
    w = np.array([c.weight for c in ds.criteria])
    w = w / w.sum()
    wins = np.zeros(len(codes))
    for _ in range(iterations):
        noisy = np.clip(base + rng.integers(-1, 2, size=base.shape), 1, 5)
        t = np.round(noisy @ w, 12)
        # Ties are broken by country code, as in rank()
        best = min(range(len(codes)), key=lambda i: (-t[i], codes[i]))
        wins[best] += 1
    return {code: wins[i] / iterations for i, code in enumerate(codes)}


def _reweight(ds: Dataset, key: str, new_weight: float) -> dict[str, float]:
    base = ds.weights
    rest = 1 - base[key]
    scale = (1 - new_weight) / rest if rest > 0 else 0
    return {k: (new_weight if k == key else v * scale) for k, v in base.items()}


def weight_thresholds(ds: Dataset, steps: int = 1000) -> list[dict]:
    """For each criterion, the nearest weight (0-100%) at which the base leader is overtaken.

    Overtaken means another country scores strictly higher; a tie does not count.
    Rows are sorted most sensitive first: the smallest weight change that flips the leader.
    Criteria that never flip the leader have threshold None and sort last.
    """
    leader = rank(ds)[0][0]
    rows = []
    for c in ds.criteria:
        best = None
        for i in range(steps + 1):
            w = i / steps
            t = totals(ds, _reweight(ds, c.key, w))
            rival = max((code for code in t if code != leader), key=lambda code: (t[code], code))
            overtaken = t[rival] > t[leader] + 1e-9
            if overtaken and (best is None or abs(w - c.weight) < abs(best[0] - c.weight)):
                best = (w, rival)
        rows.append({
            "criterion": c.key,
            "label": c.label,
            "base_weight": c.weight,
            "threshold": best[0] if best else None,
            "new_leader": best[1] if best else None,
            "change": abs(best[0] - c.weight) if best else None,
        })
    return sorted(rows, key=lambda r: (r["change"] is None, r["change"] or 0, r["criterion"]))
