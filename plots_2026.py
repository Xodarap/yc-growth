#!/usr/bin/env python3
"""Figures for RERUN_2026.md.

Every figure compares the two collections through the same cleaning and
strict-window rules as clean_and_report.py:

  rerun_count_100m_2yr.png  count of companies >=$100M at the 2-year mark
  rerun_share_100m.png      the same as a share of the batch year, both marks
  rerun_mean_by_year.png    mean valuation by batch year, both marks

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


def hit_table(frames, lag):
    df = frames[lag]
    return (
        df.assign(hit=df.valuation_real >= THRESHOLD)
        .groupby("yc_year")
        .agg(n=("hit", "size"), h=("hit", "sum"))
    )


def count_chart(mo, mn, path, lag=2, min_year=2010):
    a, b = hit_table(mo, lag), hit_table(mn, lag)
    years = [y for y in sorted(set(a.index) | set(b.index)) if y >= min_year]
    av = [int(a.h.get(y, 0)) for y in years]
    bv = [int(b.h.get(y, 0)) for y in years]
    den = [int(b.n.get(y, a.n.get(y, 0))) for y in years]

    fig, ax = plt.subplots(figsize=(13, 6))
    x, w = np.arange(len(years)), 0.4
    bars = list(ax.bar(x - w / 2, av, w, label=OLD_LABEL, color=OLD_C))
    bars += list(ax.bar(x + w / 2, bv, w, label=NEW_LABEL, color=NEW_C))
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
    ax.set_title(
        f"Number of YC companies worth $\\geq$100M {'two' if lag == 2 else 'one'} "
        f"year{'s' if lag == 2 else ''} after their batch"
    )
    ax.legend()
    ax.grid(axis="y", alpha=0.3)
    ax.set_axisbelow(True)
    fig.tight_layout()
    fig.savefig(path, dpi=140)
    plt.close(fig)
    return years, av, bv, den


def share_chart(mo, mn, path, min_n=20):
    fig, axes = plt.subplots(1, 2, figsize=(15, 5.5))
    for ax, lag in zip(axes, (2, 1)):
        for label, frames, col in ((OLD_LABEL, mo, OLD_C), (NEW_LABEL, mn, NEW_C)):
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
        ax.set_title(f"Share of a YC batch worth $\\geq$100M at its {lag}-year mark")
        ax.set_xlabel("YC batch year")
        ax.set_ylabel("% of companies with a valuation $\\geq$100M")
        ax.legend()
        ax.grid(alpha=0.3)
    fig.suptitle(
        f"Top-tail outcome rate by batch year "
        f"(batch-years with n$\\geq${min_n}; cleaned, strict window)",
        y=1.0,
    )
    fig.tight_layout()
    fig.savefig(path, dpi=140)
    plt.close(fig)


def mean_chart(mo, mn, path, min_n=20):
    fig, axes = plt.subplots(1, 2, figsize=(15, 5.5))
    for ax, lag in zip(axes, (2, 1)):
        for label, frames, col in (
            (f"{OLD_LABEL} (June-2025 $)", mo, OLD_C),
            (f"{NEW_LABEL} (June-2026 $)", mn, NEW_C),
        ):
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
        ax.set_title(f"Mean {lag}-year post-YC valuation by batch year")
        ax.set_xlabel("YC batch year")
        ax.set_ylabel("mean valuation (log scale)")
        ax.legend()
        ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(path, dpi=140)
    plt.close(fig)


if __name__ == "__main__":
    to25, to26 = date(2025, 6, 1), date(2026, 6, 1)
    old, _ = load("yc_valuations.db", 2025, to25)
    new, _ = load("yc_valuations_2026.db", 2026, to26)
    mo, mn = marks(old, to25, True, True), marks(new, to26, True, True)

    years, av, bv, den = count_chart(mo, mn, "rerun_count_100m_2yr.png")
    share_chart(mo, mn, "rerun_share_100m.png")
    mean_chart(mo, mn, "rerun_mean_by_year.png")

    print(f"{'year':<6}{'n':>5}{'Aug-2025':>10}{'Sep-2026':>10}")
    for y, d, p, q in zip(years, den, av, bv):
        print(f"{y:<6}{d:>5}{p:>10}{q:>10}")
    print(
        f"\ntotal >=$100M at the 2-year mark: pre-2023 {sum(q for y, q in zip(years, bv) if y < 2023)}, "
        f"2023+ {sum(q for y, q in zip(years, bv) if y >= 2023)}"
    )
    print("wrote rerun_count_100m_2yr.png rerun_share_100m.png rerun_mean_by_year.png")
