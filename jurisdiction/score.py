"""Load the jurisdiction dataset, validate it, and rank countries by weighted score."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

MIN_SCORE, MAX_SCORE = 1, 5


@dataclass(frozen=True)
class Source:
    title: str
    url: str


@dataclass(frozen=True)
class Score:
    value: int
    rationale: str
    sources: tuple[Source, ...]
    last_checked: str
    needs_check: bool


@dataclass(frozen=True)
class Criterion:
    key: str
    label: str
    weight: float
    description: str


@dataclass(frozen=True)
class Country:
    code: str
    name: str
    supervisor: str
    summary: str


@dataclass
class Dataset:
    title: str
    as_of: str
    countries: list[Country]
    criteria: list[Criterion]
    scores: dict[tuple[str, str], Score] = field(default_factory=dict)  # (criterion, country) -> Score
    baseline: list[dict] = field(default_factory=list)  # facts common to all countries

    @property
    def weights(self) -> dict[str, float]:
        return {c.key: c.weight for c in self.criteria}

    def score(self, criterion: str, country: str) -> int:
        return self.scores[(criterion, country)].value


def load(path: str | Path) -> Dataset:
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    countries = [Country(code, c["name"], c["supervisor"], c.get("summary", "")) for code, c in raw["countries"].items()]
    criteria = [Criterion(key, c["label"], float(c["weight"]), c["description"]) for key, c in raw["criteria"].items()]
    scores = {}
    for crit_key, by_country in raw["scores"].items():
        for code, s in by_country.items():
            sources = tuple(Source(x["title"], x["url"]) for x in s.get("sources") or [])
            scores[(crit_key, code)] = Score(
                value=s["score"],
                rationale=s["rationale"],
                sources=sources,
                last_checked=str(s.get("last_checked", "")),
                needs_check=bool(s.get("needs_check", False)),
            )
    return Dataset(raw["title"], str(raw["as_of"]), countries, criteria, scores, raw.get("baseline") or [])


def validate(ds: Dataset) -> list[str]:
    """Return a list of problems; empty means the dataset is usable."""
    errors = []
    total = sum(c.weight for c in ds.criteria)
    if abs(total - 1) > 1e-9:
        errors.append(f"weights sum to {total:.4f}, not 1")
    for crit in ds.criteria:
        if crit.weight < 0:
            errors.append(f"{crit.key}: negative weight")
        for country in ds.countries:
            s = ds.scores.get((crit.key, country.code))
            where = f"{crit.key}/{country.code}"
            if s is None:
                errors.append(f"{where}: missing score")
                continue
            if not isinstance(s.value, int) or not MIN_SCORE <= s.value <= MAX_SCORE:
                errors.append(f"{where}: score {s.value!r} not an integer {MIN_SCORE}-{MAX_SCORE}")
            if not s.sources and not s.needs_check:
                errors.append(f"{where}: no source and not flagged needs_check")
    unknown = {k for k in ds.scores} - {(c.key, n.code) for c in ds.criteria for n in ds.countries}
    errors += [f"{c}/{n}: score for unknown criterion or country" for c, n in sorted(unknown)]
    return errors


def totals(ds: Dataset, weights: dict[str, float] | None = None) -> dict[str, float]:
    """Weighted score per country on the 1-5 scale. Weights are normalised to sum to 1."""
    w = weights or ds.weights
    norm = sum(w.values())
    return {
        n.code: sum(w[c.key] * ds.score(c.key, n.code) for c in ds.criteria) / norm
        for n in ds.countries
    }


def rank(ds: Dataset, weights: dict[str, float] | None = None) -> list[tuple[str, float]]:
    """Countries sorted best first. Ties are broken by country code so the order is deterministic."""
    t = totals(ds, weights)
    return sorted(t.items(), key=lambda kv: (-round(kv[1], 12), kv[0]))


def contributions(ds: Dataset) -> dict[str, dict[str, float]]:
    """Points each criterion adds to each country's total: weight x score."""
    return {n.code: {c.key: c.weight * ds.score(c.key, n.code) for c in ds.criteria} for n in ds.countries}
