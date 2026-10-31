"""Score jurisdictions, test robustness and write outputs.

Usage:
    python run.py                               # uses data/jurisdictions.yaml, writes to output/
    python run.py --data my.yaml --out results --iterations 10000
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from jurisdiction.report import first_and_top2, headline, write_charts, write_html, write_markdown
from jurisdiction.robustness import rank_shares, weight_thresholds
from jurisdiction.score import load, rank, validate


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare EU jurisdictions for a new banking licence")
    parser.add_argument("--data", default="data/jurisdictions.yaml", help="Path to the jurisdictions YAML")
    parser.add_argument("--out", default="output", help="Output folder")
    parser.add_argument("--iterations", type=int, default=5000, help="Monte Carlo weight sets")
    args = parser.parse_args()

    ds = load(args.data)
    errors = validate(ds)
    if errors:
        sys.exit("Dataset problems:\n  " + "\n  ".join(errors))

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    shares = rank_shares(ds, args.iterations)
    mc, top2 = first_and_top2(shares)
    thresholds = weight_thresholds(ds)

    write_charts(ds, shares, args.iterations, out)
    write_markdown(ds, mc, top2, thresholds, args.iterations, out / "summary.md")
    write_html(ds, mc, top2, thresholds, args.iterations, out / "report.html")

    names = {n.code: n.name for n in ds.countries}
    print(f"{'Rank':<6}{'Country':<14}{'Score':>7}{'First in MC':>13}{'Top two':>10}")
    for i, (code, total) in enumerate(rank(ds), 1):
        print(f"{i:<6}{names[code]:<14}{total:>7.2f}{mc[code]:>13.1%}{top2[code]:>10.1%}")
    print("\n" + headline(ds, mc, thresholds, args.iterations))
    flagged = sum(s.needs_check for s in ds.scores.values())
    print(f"\n{flagged} of {len(ds.scores)} scores flagged needs_check")
    print(f"Outputs written to {out.resolve()}")


if __name__ == "__main__":
    main()
