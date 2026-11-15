"""Outputs: PNG charts, a markdown summary and a single-file HTML report."""
from __future__ import annotations

import html
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from .score import Dataset, rank  # noqa: E402

BAR, BAR_2 = "#2a78d6", "#eb6834"  # categorical slots 1 and 2
INK, INK_2, GRID = "#0b0b0b", "#52514e", "#e4e3df"
# Sequential blue ramp for scores 1-5 (light = weak, dark = strong)
SCORE_FILL = {1: "#cde2fb", 2: "#9ec5f4", 3: "#5598e7", 4: "#256abf", 5: "#104281"}
SCORE_INK = {1: INK, 2: INK, 3: INK, 4: "#ffffff", 5: "#ffffff"}


def _names(ds: Dataset) -> dict[str, str]:
    return {n.code: n.name for n in ds.countries}


def _barh(ax, labels, values, fmt, title, xlabel, xmax):
    y = range(len(labels))[::-1]
    ax.barh(list(y), values, color=BAR, height=0.6)
    ax.set_yticks(list(y), labels)
    for yi, v in zip(y, values):
        ax.text(v + xmax * 0.01, yi, fmt(v), va="center", color=INK, fontsize=10)
    ax.set_xlim(0, xmax)
    ax.set_title(title, loc="left", fontsize=12, fontweight="bold", color=INK)
    ax.set_xlabel(xlabel, color=INK_2)
    ax.spines[["top", "right"]].set_visible(False)
    ax.spines[["left", "bottom"]].set_color(GRID)
    ax.tick_params(colors=INK_2)
    ax.grid(axis="x", color=GRID)
    ax.set_axisbelow(True)


def _pct_label(v: float) -> str:
    """Percent label that never rounds a near-certainty up to 100% or a rare event down to 0%."""
    if 0 < v < 1:
        return "<1%"
    if 99 < v < 100:
        return ">99%"
    return f"{v:.0f}%"


def rank_labels(ranked: list[tuple[str, float]]) -> dict[str, str]:
    """Competition ranks with ties shown as '4=': equal totals (to 2 decimals) share a rank."""
    labels, shown = {}, [round(v, 2) for _, v in ranked]
    for i, (code, _) in enumerate(ranked):
        first = shown.index(shown[i]) + 1
        tied = shown.count(shown[i]) > 1
        labels[code] = f"{first}=" if tied else str(first)
    return labels


def first_and_top2(shares: dict[str, list[float]]) -> tuple[dict[str, float], dict[str, float]]:
    return {c: r[0] for c, r in shares.items()}, {c: r[0] + r[1] for c, r in shares.items()}


def write_charts(ds: Dataset, shares: dict[str, list[float]], iterations: int, outdir: Path) -> list[Path]:
    names = _names(ds)
    ranked = rank(ds)
    mc, top2 = first_and_top2(shares)
    files = []

    fig, ax = plt.subplots(figsize=(8, 3.8))
    _barh(ax, [names[c] for c, _ in ranked], [v for _, v in ranked], lambda v: f"{v:.2f}",
          "Weighted score with base weights (1 = weak, 5 = strong)", "Weighted score", 5)
    files.append(outdir / "ranking.png")
    fig.tight_layout()
    fig.savefig(files[-1], dpi=150)
    plt.close(fig)

    order = [c for c, _ in ranked]
    fig, ax = plt.subplots(figsize=(8, 4.2))
    ys = list(range(len(order)))[::-1]
    h = 0.36
    series = [("Ranks first", mc, BAR, h / 2), ("Ranks first or second", top2, BAR_2, -h / 2)]
    for label, data, color, offset in series:
        vals = [data[c] * 100 for c in order]
        ax.barh([y + offset for y in ys], vals, height=h - 0.04, color=color, label=label)
        for y, v in zip(ys, vals):
            ax.text(v + 1, y + offset, _pct_label(v), va="center", color=INK, fontsize=9)
    ax.set_yticks(ys, [names[c] for c in order])
    ax.set_xlim(0, 110)
    ax.set_title(f"Rank in {iterations:,} random weight sets",
                 loc="left", fontsize=12, fontweight="bold", color=INK)
    ax.set_xlabel("% of weight sets", color=INK_2)
    ax.spines[["top", "right"]].set_visible(False)
    ax.spines[["left", "bottom"]].set_color(GRID)
    ax.tick_params(colors=INK_2)
    ax.grid(axis="x", color=GRID)
    ax.set_axisbelow(True)
    ax.legend(frameon=False, loc="lower right")
    files.append(outdir / "robustness.png")
    fig.tight_layout()
    fig.savefig(files[-1], dpi=150)
    plt.close(fig)

    codes = [c for c, _ in ranked]
    fig, ax = plt.subplots(figsize=(9, 5))
    for i, crit in enumerate(ds.criteria):
        for j, code in enumerate(codes):
            v = ds.score(crit.key, code)
            ax.add_patch(plt.Rectangle((j, i), 0.96, 0.92, color=SCORE_FILL[v]))
            flag = "*" if ds.scores[(crit.key, code)].needs_check else ""
            ax.text(j + 0.48, i + 0.46, f"{v}{flag}", ha="center", va="center", color=SCORE_INK[v], fontsize=10)
    ax.set_xlim(0, len(codes))
    ax.set_ylim(len(ds.criteria), 0)
    ax.set_xticks([j + 0.48 for j in range(len(codes))], [names[c] for c in codes])
    ax.set_yticks([i + 0.46 for i in range(len(ds.criteria))],
                  [f"{c.label} ({c.weight:.0%})" for c in ds.criteria])
    ax.xaxis.tick_top()
    ax.tick_params(length=0, colors=INK_2)
    for s in ax.spines.values():
        s.set_visible(False)
    ax.set_title("Scores by criterion (weight in brackets; * = needs check)", loc="left",
                 fontsize=12, fontweight="bold", color=INK, pad=28)
    files.append(outdir / "scores_heatmap.png")
    fig.tight_layout()
    fig.savefig(files[-1], dpi=150)
    plt.close(fig)
    return files


def headline(ds: Dataset, mc: dict[str, float], thresholds: list[dict], iterations: int,
             score_mc: dict[str, float] | None = None) -> str:
    names = _names(ds)
    leader = rank(ds)[0][0]
    top = thresholds[0]
    text = (f"With base weights, {names[leader]} ranks first; {names[leader]} stays first in "
            f"{mc[leader]:.1%} of {iterations:,} random weight sets")
    if score_mc is not None:
        text += f" and in {score_mc[leader]:.1%} of {iterations:,} draws with every score moved by -1, 0 or +1"
    text += "."
    if top["threshold"] is None:
        return text + " No single weight change overturns the leader."
    return text + (f" The decision is most sensitive to {top['label'].lower()}: moving its weight from "
                   f"{top['base_weight']:.0%} to {top['threshold']:.0%} puts {names[top['new_leader']]} first.")


def write_markdown(ds: Dataset, mc: dict[str, float], top2: dict[str, float], thresholds: list[dict], iterations: int, path: Path,
                   score_mc: dict[str, float] | None = None) -> None:
    names = _names(ds)
    ranked = rank(ds)
    labels = rank_labels(ranked)
    smc = score_mc or {}
    lines = [f"# {ds.title}", "", f"Data as of {ds.as_of}.", "", headline(ds, mc, thresholds, iterations, score_mc), "",
             "## Ranking", "",
             "| Rank | Country | Weighted score | First in random weight sets | First or second | First with scores +/-1 |",
             "|---|---|---|---|---|---|"]
    for code, total in ranked:
        s1 = f"{smc[code]:.1%}" if code in smc else "-"
        lines.append(f"| {labels[code]} | {names[code]} | {total:.2f} | {mc[code]:.1%} | {top2[code]:.1%} | {s1} |")
    lines += ["", "## Weight needed to change the leader", "",
              "| Criterion | Base weight | Leader changes at | New leader |", "|---|---|---|---|"]
    for t in thresholds:
        at = f"{t['threshold']:.0%}" if t["threshold"] is not None else "never"
        who = names[t["new_leader"]] if t["new_leader"] else "-"
        lines.append(f"| {t['label']} | {t['base_weight']:.0%} | {at} | {who} |")
    flagged = [(k, s) for k, s in ds.scores.items() if s.needs_check]
    if flagged:
        lines += ["", "## Scores flagged needs_check", ""]
        lines += [f"- {crit} / {names[code]}" for (crit, code), _ in sorted(flagged)]
    lines += ["", "![Ranking](ranking.png)", "", "![Robustness](robustness.png)", "",
              "![Scores](scores_heatmap.png)", ""]
    path.write_text("\n".join(lines), encoding="utf-8")


CSS = """
.viz-root{color-scheme:light;--surface:#fcfcfb;--ink:#0b0b0b;--ink2:#52514e;--grid:#e4e3df;--bar:#2a78d6;--card:#ffffff}
@media (prefers-color-scheme:dark){.viz-root{color-scheme:dark;--surface:#1a1a19;--ink:#f0efec;--ink2:#c3c2b7;--grid:#383835;--bar:#3987e5;--card:#232322}}
body{margin:0;font:15px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif}
.viz-root{background:var(--surface);color:var(--ink);padding:32px;max-width:1100px;margin:auto}
h1{font-size:26px;margin:0 0 4px}h2{font-size:18px;margin:32px 0 12px}
.muted{color:var(--ink2)}.lead{font-size:17px;max-width:820px}
table{border-collapse:collapse;width:100%;font-variant-numeric:tabular-nums}
th,td{text-align:left;padding:6px 10px;border-bottom:1px solid var(--grid);vertical-align:top}
th{color:var(--ink2);font-weight:600}
td.cell{text-align:center;font-weight:600;cursor:default}
.bars .row{display:grid;grid-template-columns:140px 1fr 60px;align-items:center;gap:10px;margin:6px 0}
.bars .track{height:18px}.bars .fill{height:18px;background:var(--bar);border-radius:0 4px 4px 0}
.bars .row:hover .fill{filter:brightness(1.15)}
.cards{display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:16px}
.card{background:var(--card);border:1px solid var(--grid);border-radius:8px;padding:16px}
.card h3{margin:0 0 4px;font-size:17px}.card ul{padding-left:18px;margin:6px 0}
.card li{margin:6px 0}.flag{color:#b06d00;font-weight:600}
a{color:var(--bar)}
"""


def _bars(rows: list[tuple[str, float, str, str]], xmax: float) -> str:
    out = ['<div class="bars">']
    for label, value, shown, tip in rows:
        pct = max(value / xmax * 100, 0.5)
        out.append(f'<div class="row" title="{html.escape(tip)}"><span>{html.escape(label)}</span>'
                   f'<div class="track"><div class="fill" style="width:{pct:.1f}%"></div></div><span>{shown}</span></div>')
    out.append("</div>")
    return "".join(out)


def write_html(ds: Dataset, mc: dict[str, float], top2: dict[str, float], thresholds: list[dict], iterations: int, path: Path,
               score_mc: dict[str, float] | None = None) -> None:
    names = _names(ds)
    ranked = rank(ds)
    e = html.escape
    parts = [f"<!DOCTYPE html><html lang='en'><head><meta charset='utf-8'><title>{e(ds.title)}</title>",
             f"<meta name='viewport' content='width=device-width,initial-scale=1'><style>{CSS}</style></head>",
             "<body><main class='viz-root'>",
             f"<h1>{e(ds.title)}</h1><p class='muted'>Data as of {e(ds.as_of)}. Scores 1 (weak) to 5 (strong).</p>",
             f"<p class='lead'>{e(headline(ds, mc, thresholds, iterations, score_mc))}</p>"]

    parts.append("<h2>Weighted score, base weights</h2>")
    parts.append(_bars([(names[c], v, f"{v:.2f}", f"{names[c]}: {v:.2f} of 5") for c, v in ranked], 5))

    parts.append(f"<h2>Ranks first in {iterations:,} random weight sets</h2>")
    parts.append(_bars([(names[c], mc[c], f"{mc[c]:.1%}", f"{names[c]} first in {mc[c]:.1%} of weight sets")
                        for c, _ in ranked], 1))
    parts.append(f"<h2>Ranks first or second in {iterations:,} random weight sets</h2>")
    parts.append(_bars([(names[c], top2[c], f"{top2[c]:.1%}", f"{names[c]} in the top two in {top2[c]:.1%} of weight sets")
                        for c, _ in ranked], 1))
    if score_mc is not None:
        parts.append(f"<h2>Ranks first in {iterations:,} draws with every score moved by -1, 0 or +1</h2>")
        parts.append(_bars([(names[c], score_mc[c], f"{score_mc[c]:.1%}",
                             f"{names[c]} first in {score_mc[c]:.1%} of score draws") for c, _ in ranked], 1))

    parts.append("<h2>Scores by criterion</h2><p class='muted'>Hover a cell for the rationale. "
                 "<span class='flag'>*</span> = needs check.</p><table><tr><th>Criterion</th><th>Weight</th>")
    parts += [f"<th>{e(names[c])}</th>" for c, _ in ranked]
    parts.append("</tr>")
    for crit in ds.criteria:
        parts.append(f"<tr><td title='{e(crit.description)}'>{e(crit.label)}</td><td>{crit.weight:.0%}</td>")
        for code, _ in ranked:
            s = ds.scores[(crit.key, code)]
            flag = "<span class='flag'>*</span>" if s.needs_check else ""
            parts.append(f"<td class='cell' style='background:{SCORE_FILL[s.value]};color:{SCORE_INK[s.value]}' "
                         f"title='{e(s.rationale)}'>{s.value}{flag}</td>")
        parts.append("</tr>")
    parts.append("<tr><th>Weighted total</th><th>100%</th>")
    parts += [f"<th>{v:.2f}</th>" for _, v in ranked]
    parts.append("</tr></table>")

    parts.append("<h2>Weight needed to change the leader</h2><table>"
                 "<tr><th>Criterion</th><th>Base weight</th><th>Leader changes at</th><th>New leader</th></tr>")
    for t in thresholds:
        at = f"{t['threshold']:.0%}" if t["threshold"] is not None else "never"
        who = names[t["new_leader"]] if t["new_leader"] else "-"
        parts.append(f"<tr><td>{e(t['label'])}</td><td>{t['base_weight']:.0%}</td><td>{at}</td><td>{e(who)}</td></tr>")
    parts.append("</table>")

    if ds.baseline:
        parts.append("<h2>Common to all five</h2><ul>")
        parts += [f"<li>{e(b['fact'])} <a href='{e(b['source'])}' target='_blank' rel='noopener'>Source</a></li>"
                  for b in ds.baseline]
        parts.append("</ul>")

    parts.append("<h2>Country cards</h2><div class='cards'>")
    for code, total in ranked:
        n = next(x for x in ds.countries if x.code == code)
        parts.append(f"<div class='card'><h3>{e(n.name)} <span class='muted'>{total:.2f}</span></h3>"
                     f"<div class='muted'>Supervisor: {e(n.supervisor)}</div><p>{e(n.summary)}</p><ul>")
        for crit in ds.criteria:
            s = ds.scores[(crit.key, code)]
            links = ", ".join(f"<a href='{e(x.url)}' target='_blank' rel='noopener'>{e(x.title)}</a>" for x in s.sources)
            flag = " <span class='flag'>needs check</span>" if s.needs_check else ""
            parts.append(f"<li><b>{e(crit.label)}: {s.value}</b>{flag}. {e(s.rationale)}"
                         f"{' <span class=muted>Sources: </span>' + links if links else ''}</li>")
        parts.append("</ul></div>")
    parts.append("</div></main></body></html>")
    path.write_text("".join(parts), encoding="utf-8")
