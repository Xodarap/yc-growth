#!/usr/bin/env python3
"""Figures for RERUN_2026.md.

One chart per file. Every figure applies the same cleaning and strict-window
rules as clean_and_report.py:

  rerun_count_100m_2yr.png     count of companies >=$100M at the 2-year mark
  rerun_share_100m_2yr.png     the same as a share of the batch year, 2-yr mark
  rerun_share_100m_1yr.png     ... and at the 1-year mark
  rerun_mean_by_year_2yr.png   mean valuation by batch year, 2-year mark
  rerun_mean_by_year_1yr.png   ... and at the 1-year mark
  rerun_only_*.png             the same five, but only the current dataset --
                               one series per batch year, no comparison line
  rerun_single_vintage_2026_count.png  post-ChatGPT batches from rows
  rerun_single_vintage_2026_share.png  physically re-fetched today, as a count
                               and as a share (no pre-2023 baseline exists
                               there)

The two marks (1-year and 2-year) and the count/share pair used to share a
figure each. They are separate files now: each answers its own question, and a
reader comparing two panels inside one image cannot enlarge, caption or quote
either half on its own.

Counts and shares answer different questions and disagree: YC batch sizes grew
~30x over the period, so a count folds cohort growth into the outcome, while a
share does not. Both are plotted, with the denominator on the count chart's
tick labels.
"""

from datetime import date

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from clean_and_report import load, marks

OLD_LABEL, NEW_LABEL = "collected Aug 2025", "re-collected Sep 2026"
OLD_C, NEW_C = "#9aa5b1", "#c44e52"
THRESHOLD = 1e8
# the two post-batch marks the original analysis uses, each its own figure
LAGS = (2, 1)
SV_LAGS = (1, 2)


def hit_table(frames, lag):
    df = frames[lag]
    return (
        df.assign(hit=df.valuation_real >= THRESHOLD)
        .groupby("yc_year")
        .agg(n=("hit", "size"), h=("hit", "sum"))
    )


def count_chart(series, path, lag=2, min_year=2010):
    """Count of companies >=$100M at the `lag`-year mark, by batch year.

    `series` is [(label, marks_dict, colour), ...]. Pass one entry for a single
    line of data, two to compare collections side by side.
    """
    tables = [(label, hit_table(frames, lag), col) for label, frames, col in series]
    years = [
        y
        for y in sorted(set().union(*(t.index for _, t, _ in tables)))
        if y >= min_year
    ]
    # the denominator comes from the last series, which is the newest
    den = [
        next((int(t.n[y]) for _, t, _ in reversed(tables) if y in t.index), 0)
        for y in years
    ]

    fig, ax = plt.subplots(figsize=(13, 6))
    x = np.arange(len(years))
    w = 0.4 if len(tables) > 1 else 0.55
    bars = []
    for i, (label, t, col) in enumerate(tables):
        off = (i - (len(tables) - 1) / 2) * w
        bars += list(
            ax.bar(
                x + off, [int(t.h.get(y, 0)) for y in years], w, label=label, color=col
            )
        )
    for r in bars:
        if r.get_height():
            ax.text(
                r.get_x() + r.get_width() / 2,
                r.get_height() + 0.15,
                str(int(r.get_height())),
                ha="center",
                fontsize=8.5,
            )
    ax.set_xticks(x)
    ax.set_xticklabels([f"{y}\n(n={d})" for y, d in zip(years, den)], fontsize=8.5)
    if 2023 in years:
        ax.axvline(x[years.index(2023)] - 0.5, ls="--", color="black", lw=1.2)
        ax.text(
            x[years.index(2023)] - 0.42,
            ax.get_ylim()[1] * 0.97,
            "ChatGPT launch",
            rotation=90,
            va="top",
            fontsize=9,
        )
    ax.set_xlabel(
        f"YC batch year  (n = companies in that batch year with a {lag}-year valuation)"
    )
    ax.set_ylabel(f"companies valued $\\geq$100M at their {lag}-year mark")
    solo = tables[0][0] if len(tables) == 1 else None
    ax.set_title(
        f"Number of YC companies worth $\\geq$100M {'two' if lag == 2 else 'one'} "
        f"year{'s' if lag == 2 else ''} after their batch"
        + (f"\n{solo} dataset" if solo else "")
    )
    if len(tables) > 1:
        ax.legend()
    ax.grid(axis="y", alpha=0.3)
    ax.set_axisbelow(True)
    fig.tight_layout()
    fig.savefig(path, dpi=140)
    plt.close(fig)
    return years, [[int(t.h.get(y, 0)) for y in years] for _, t, _ in tables], den


def share_chart(series, path, lag=2, min_n=20):
    """Top-tail outcome rate by batch year, at one mark.

    One mark per figure: `lag` selects it, and the caller writes the 1-year and
    2-year views to separate files.
    """
    fig, ax = plt.subplots(figsize=(8.5, 5.5))
    for label, frames, col in series:
        t = hit_table(frames, lag)
        t = t[t.n >= min_n]
        ax.plot(t.index, t.h / t.n * 100, marker="o", label=label, color=col, lw=2)
    ax.axvline(2022.5, ls="--", color="black", lw=1.2)
    ax.text(
        2022.6,
        ax.get_ylim()[1] * 0.95,
        "ChatGPT launch",
        rotation=90,
        va="top",
        fontsize=9,
    )
    ax.set_xlabel("YC batch year")
    ax.set_ylabel("% of companies with a valuation $\\geq$100M")
    if len(series) > 1:
        ax.legend()
    ax.grid(alpha=0.3)
    solo = series[0][0] if len(series) == 1 else None
    ax.set_title(
        f"Share of a YC batch worth $\\geq$100M at its {lag}-year mark\n"
        f"batch-years with n$\\geq${min_n}; cleaned, strict window"
        + (f"; {solo} dataset" if solo else ""),
        fontsize=11,
    )
    fig.tight_layout()
    fig.savefig(path, dpi=140)
    plt.close(fig)


def mean_chart(series, path, lag=2, min_n=20):
    """Mean post-YC valuation by batch year, at one mark.

    One mark per figure, as in share_chart.
    """
    fig, ax = plt.subplots(figsize=(8.5, 5.5))
    for label, frames, col in series:
        t = frames[lag].groupby("yc_year")["valuation_real"].agg(["mean", "size"])
        t = t[t["size"] >= min_n]
        ax.plot(t.index, t["mean"], marker="o", label=label, color=col, lw=2)
    ax.set_yscale("log")
    ax.axvline(2022.5, ls="--", color="black", lw=1.2)
    ax.text(
        2022.6,
        ax.get_ylim()[1] * 0.6,
        "ChatGPT launch",
        rotation=90,
        va="top",
        fontsize=9,
    )
    solo = series[0][0] if len(series) == 1 else None
    ax.set_title(
        f"Mean {lag}-year post-YC valuation by batch year"
        + (f"\n{solo} dataset" if solo else ""),
        fontsize=11,
    )
    ax.set_xlabel("YC batch year")
    ax.set_ylabel("mean valuation (log scale)")
    if len(series) > 1:
        ax.legend()
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(path, dpi=140)
    plt.close(fig)


def single_vintage_tables(min_year=2023, max_year=2025):
    """Load only the rows the Sep-2026 pass physically collected.

    The charts above mix vintages: pre-2023 batches carry their Aug-2025
    numbers, 2023+ batches were re-collected. This drops every pre-existing
    row, so one model on one day produced every number that follows.

    Two things the result therefore cannot show. There is no pre-ChatGPT
    baseline: only 46 pre-2023 companies were re-collected (1-12 per batch
    year, and they are precisely the ones the first pass failed on), so no
    pre-2023 series is drawn. And the 2026 batches are excluded even though
    they have a year-zero figure, because that figure is not trustworthy -- 8
    of the 10 companies it puts above $100M are the fabrication pattern
    documented in FABRICATED, e.g. a "$1.5B Series C" for a Winter 2026
    company that has actually raised a $500K pre-seed. What remains is the
    post-ChatGPT era measured against itself, at the two marks the original
    analysis uses.
    """
    fresh, _ = load(
        "yc_valuations_2026.db",
        2027,
        date(2026, 6, 1),
        since="2026-09-06",
        year_max=2026,
    )
    m = marks(fresh, date(2026, 6, 1), True, True)
    tables = {lag: hit_table(m, lag) for lag in SV_LAGS}
    return tables, list(range(min_year, max_year + 1))


def single_vintage_chart(tables, years, path, mode="count", min_n=50):
    """One panel of the single-vintage view: `mode` is "count" or "share".

    The count and the share are separate files. They are the same hits over
    the same denominators, but a count folds ~30x cohort growth into the
    outcome and a share does not, so they are two claims, not two halves of
    one.
    """
    colours = {1: "#dfa06b", 2: "#c44e52"}
    fig, ax = plt.subplots(figsize=(8.5, 5.6))
    w = 0.32
    for i, lag in enumerate(SV_LAGS):
        t = tables[lag]
        xs, vals, labels = [], [], []
        for j, y in enumerate(years):
            if y not in t.index or t.n.get(y, 0) < min_n:
                # A batch year that cannot have reached this mark yet must
                # not be drawn as a zero.
                ax.bar(
                    [j + (i - 0.5) * w],
                    [0],
                    w,
                    color="none",
                    edgecolor="#bbb",
                    hatch="///",
                    lw=0.8,
                )
                ax.annotate(
                    f"{lag}-year mark\nnot yet observable",
                    xy=(j + (i - 0.5) * w, 0),
                    xytext=(0, 14),
                    textcoords="offset points",
                    ha="center",
                    fontsize=7.5,
                    color="#888",
                )
                continue
            xs.append(j + (i - 0.5) * w)
            n, h = int(t.n[y]), int(t.h[y])
            vals.append(h if mode == "count" else h / n * 100)
            labels.append(f"{h}" if mode == "count" else f"{h / n * 100:.1f}%")
        bars = ax.bar(
            xs,
            vals,
            w,
            color=colours[lag],
            label=f"{lag} year{'s' if lag > 1 else ''} after the batch",
        )
        for r, lab in zip(bars, labels):
            ax.text(
                r.get_x() + r.get_width() / 2,
                r.get_height() + max(vals) * 0.02,
                lab,
                ha="center",
                fontsize=8,
            )
    ax.set_xticks(range(len(years)))
    ax.set_xticklabels(
        [
            f"{y}\n(n={int(tables[1].n.get(y, 0))} at 1yr"
            f"{f', {int(tables[2].n[y])} at 2yr' if y in tables[2].index else ''})"
            for y in years
        ]
    )
    ax.set_xlabel("YC batch year")
    ax.set_ylabel(
        "companies valued $\\geq$100M"
        if mode == "count"
        else "% of the batch year valued $\\geq$100M"
    )
    ax.set_title(
        f"{'Number' if mode == 'count' else 'Share'} of post-ChatGPT YC "
        f"companies worth $\\geq$100M,\nby years since the batch"
        " -- single collection vintage, every number\ncollected on "
        "2026-09-06/07, so there is no pre-ChatGPT comparison group",
        fontsize=10,
    )
    ax.legend(fontsize=8.5)
    ax.grid(axis="y", alpha=0.3)
    ax.set_axisbelow(True)
    fig.tight_layout()
    fig.savefig(path, dpi=140)
    plt.close(fig)


if __name__ == "__main__":
    to25, to26 = date(2025, 6, 1), date(2026, 6, 1)
    old, _ = load("yc_valuations.db", 2025, to25)
    new, _ = load("yc_valuations_2026.db", 2026, to26)
    mo, mn = marks(old, to25, True, True), marks(new, to26, True, True)

    both = [(OLD_LABEL, mo, OLD_C), (NEW_LABEL, mn, NEW_C)]
    just_new = [(NEW_LABEL, mn, NEW_C)]

    written = []

    # two-series charts: the two collections side by side
    years, (av, bv), den = count_chart(both, "rerun_count_100m_2yr.png")
    written.append("rerun_count_100m_2yr.png")
    # one mark per file: the 1-year and 2-year views used to share a figure
    for lag in LAGS:
        for stem, series in (("rerun", both), ("rerun_only", just_new)):
            for kind, fn in (("share_100m", share_chart), ("mean_by_year", mean_chart)):
                path = f"{stem}_{kind}_{lag}yr.png"
                fn(series, path, lag=lag)
                written.append(path)

    # one-series count chart: the current dataset only, no Aug-2025 comparison
    count_chart(just_new, "rerun_only_count_100m_2yr.png")
    written.append("rerun_only_count_100m_2yr.png")

    print(f"{'year':<6}{'n':>5}{'Aug-2025':>10}{'Sep-2026':>10}")
    for y, d, p, q in zip(years, den, av, bv):
        print(f"{y:<6}{d:>5}{p:>10}{q:>10}")
    print(
        f"\ntotal >=$100M at the 2-year mark: pre-2023 {sum(q for y, q in zip(years, bv) if y < 2023)}, "
        f"2023+ {sum(q for y, q in zip(years, bv) if y >= 2023)}"
    )
    tables, sv_years = single_vintage_tables()
    for mode in ("count", "share"):
        path = f"rerun_single_vintage_2026_{mode}.png"
        single_vintage_chart(tables, sv_years, path, mode=mode)
        written.append(path)
    print("\nsingle collection vintage (rows collected 2026-09-06/07 only):")
    print(f"{'batch':<7}" + "".join(f"{f'{l}-yr mark':>22}" for l in (1, 2)))
    for y in sv_years:
        cells = []
        for l in (1, 2):
            t = tables[l]
            if y in t.index and t.n[y] >= 50:
                cells.append(
                    f"{int(t.h[y])}/{int(t.n[y])} ({t.h[y] / t.n[y] * 100:.1f}%)".rjust(
                        22
                    )
                )
            else:
                cells.append("not yet observable".rjust(22))
        print(f"{y:<7}" + "".join(cells))

    print(f"\nwrote {len(written)} figures, one chart each:")
    for path in sorted(written):
        print(f"  {path}")
