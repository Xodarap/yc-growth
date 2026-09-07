#!/usr/bin/env python3
"""2026 re-run of the yc-growth analysis.

Reproduces analysis.py's pipeline verbatim (same valuation parser, same 1yr/2yr
window rules, same top-20 / base-rate / mean-median comparisons) but
parameterised by database, inflation target and batch-year cutoff, so the
Aug-2025 baseline and the Sep-2026 re-collection can be run through identical
code. Adds significance tests, which the original did not have.
"""
import argparse
import re
import sqlite3
from datetime import date

import cpi
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats


# ---------------------------------------------------------------- original code
def parse_valuation(valuation_str):
    if pd.isna(valuation_str) or not isinstance(valuation_str, str):
        return None
    val_str = valuation_str.lower().strip()
    skip_phrases = ["not found", "not disclosed", "no public", "undisclosed"]
    if any(phrase in val_str for phrase in skip_phrases):
        return None
    match = re.search(r"\$(\d+(,\d+)?(\.\d+)?)(-\d+)?(([kmb])|(\s+[mb]illion))?", val_str, re.IGNORECASE)
    if not match:
        return None
    try:
        number = float(match.group(1).replace(",", ""))
        multiplier = match.group(5)
        if multiplier == "k":
            return number * 1_000
        if multiplier == "m" or multiplier == " million":
            return number * 1_000_000
        if multiplier == "b" or multiplier == " billion":
            return number * 1_000_000_000
        return number
    except Exception:
        return None


def format_valuation(value):
    if pd.isna(value) or value == 0:
        return "$0"
    if value >= 1e9:
        return f"${value/1e9:.1f}B"
    if value >= 1e6:
        return f"${value/1e6:.1f}M"
    if value >= 1e3:
        return f"${value/1e3:.0f}K"
    return f"${value:,.0f}"


SEASON_ORDER = {"winter": 0, "spring": 1, "summer": 2, "fall": 3}


def batch_sort_key(batch):
    parts = str(batch).lower().split()
    if len(parts) != 2 or parts[0] not in SEASON_ORDER:
        raise ValueError(f"Unexpected batch format: {batch}")
    return (int(parts[1]), SEASON_ORDER[parts[0]])


def lagged_valuation(company_data, lag, inflators, strict):
    """analysis.py's get_{one,two}_year_valuation, deduplicated.

    strict=True reproduces the 2-year function's `abs(...) < 1` window (target
    year only); strict=False reproduces the 1-year function's `<= 1` (target
    year +/- 1). The asymmetry is in the original and is kept deliberately.
    """
    company_data = company_data.sort_values("year")
    yc_year = company_data["yc_year"].iloc[0]
    target_year = yc_year + lag
    available_years = company_data["year"].values
    closest_year = min(available_years, key=lambda x: abs(x - target_year))
    within = abs(closest_year - target_year) < 1 if strict else abs(closest_year - target_year) <= 1
    if not within:
        return None
    row = company_data[company_data["year"] == closest_year].iloc[0]
    return {
        "company": row["company"], "yc_year": yc_year, "target_year": target_year,
        "actual_year": closest_year, "valuation": row["valuation_numeric"],
        "valuation_real": row["valuation_numeric"] * inflators[closest_year],
        "batch": row["batch"], "end_reason": row["end_reason"], "source": row["source"],
        "raw": row["valuation"],
    }


# --------------------------------------------------------------------- analysis
def build(db, to_date, cutoff):
    conn = sqlite3.connect(db)
    valuations_df = pd.read_sql_query(f"""
        SELECT v.company, v.year, v.valuation, v.source, v.notes,
               c.yc_year, c.batch, c.final_year, c.end_reason
        FROM valuations v JOIN companies c ON v.company = c.company
        WHERE c.status = 'completed' AND c.yc_year < {cutoff}
        ORDER BY c.yc_year, v.company, v.year""", conn)
    companies_df = pd.read_sql_query(f"""
        SELECT company, batch, yc_year, status FROM companies
        WHERE status = 'completed' AND yc_year < {cutoff}""", conn)
    conn.close()

    valuations_df["valuation_numeric"] = valuations_df["valuation"].apply(parse_valuation)
    numeric = valuations_df[valuations_df["valuation_numeric"].notna()].copy()
    inflators = {y: cpi.inflate(1, date(int(y), 6, 1), to=to_date) for y in numeric["year"].unique()}

    frames = {}
    for lag, strict in ((2, True), (1, False)):
        rows = []
        for company in numeric["company"].unique():
            got = lagged_valuation(numeric[numeric["company"] == company], lag, inflators, strict)
            if got:
                rows.append(got)
        frames[lag] = pd.DataFrame(rows)
    return companies_df, valuations_df, numeric, frames


def report(label, db, to_date, cutoff, out_prefix, era=2023):
    companies_df, valuations_df, numeric, frames = build(db, to_date, cutoff)
    L = [f"# {label}", "",
         f"- database: `{db}`  ·  inflated to {to_date:%B %Y} dollars  ·  batches with yc_year < {cutoff}",
         f"- companies with completed collection: **{len(companies_df)}**",
         f"- valuation rows: **{len(valuations_df)}**, of which numerically parseable: **{len(numeric)}**",
         ""]

    for lag in (2, 1):
        df = frames[lag]
        top = df.sort_values("valuation_real", ascending=False).head(20).copy()
        top["fmt"] = top["valuation_real"].apply(format_valuation)
        recent, older = df[df.yc_year >= era], df[df.yc_year < era]
        base = len(recent) / len(df) * 100
        top_recent = int((top.yc_year >= era).sum())

        L += [f"## {lag}-year post-YC valuation", "",
              f"companies with a {lag}-year figure: **{len(df)}** "
              f"(batch years {int(df.yc_year.min())}–{int(df.yc_year.max())})", "",
              f"### Top 20", "",
              "| # | company | batch | valuation ({}$) | source |".format(f"{to_date:%b %Y} "),
              "|---|---|---|---|---|"]
        for i, (_, r) in enumerate(top.iterrows(), 1):
            mark = " ⭐" if r.yc_year >= era else ""
            L.append(f"| {i} | {r.company}{mark} | {r.batch} | {r.fmt} | {str(r.source)[:60]} |")
        L += ["", f"**{era}+ batches in the top 20: {top_recent}/20 ({top_recent/20*100:.0f}%)** "
                  f"vs a base rate of {len(recent)}/{len(df)} ({base:.1f}%) "
                  f"→ {(top_recent/20*100)/base if base else float('nan'):.2f}× the base rate", ""]

        a, b = older["valuation_real"], recent["valuation_real"]
        u, p_u = stats.mannwhitneyu(b, a, alternative="two-sided") if len(b) > 1 else (np.nan, np.nan)
        loga, logb = np.log10(a[a > 0]), np.log10(b[b > 0])
        t, p_t = stats.ttest_ind(logb, loga, equal_var=False) if len(logb) > 1 else (np.nan, np.nan)
        L += [f"### Pre-{era} vs {era}+", "",
              "| | n | mean | median | geo-mean | ≥$100M | ≥$1B |", "|---|---|---|---|---|---|---|"]
        for name, s in ((f"pre-{era}", a), (f"{era}+", b)):
            geo = 10 ** np.log10(s[s > 0]).mean() if (s > 0).any() else float("nan")
            L.append(f"| {name} | {len(s)} | {format_valuation(s.mean())} | {format_valuation(s.median())} "
                     f"| {format_valuation(geo)} | {(s>=1e8).mean()*100:.1f}% | {(s>=1e9).mean()*100:.1f}% |")
        L += ["",
              f"- mean ratio ({era}+ / pre-{era}): **{b.mean()/a.mean():.2f}×**, "
              f"median ratio: **{b.median()/a.median():.2f}×**",
              f"- Mann-Whitney U two-sided p = **{p_u:.3g}**; Welch t on log10 valuation p = **{p_t:.3g}**",
              ""]

        by_batch = df.groupby("batch")["valuation_real"].agg(["count", "mean", "median"])
        by_batch = by_batch.loc[sorted(by_batch.index, key=batch_sort_key)]
        L += [f"### By batch", "", "| batch | n | mean | median |", "|---|---|---|---|"]
        for bname, r in by_batch.iterrows():
            L.append(f"| {bname} | {int(r['count'])} | {format_valuation(r['mean'])} | {format_valuation(r['median'])} |")
        L.append("")

        fig, ax = plt.subplots(figsize=(13, 6))
        ax.bar(range(len(by_batch)), by_batch["mean"].values,
               color=["#c44e52" if batch_sort_key(b)[0] >= era else "#4c72b0" for b in by_batch.index])
        ax.set_yscale("log")
        ax.set_xticks(range(len(by_batch)))
        ax.set_xticklabels(by_batch.index, rotation=45, ha="right")
        first_recent = next((i for i, b in enumerate(by_batch.index) if batch_sort_key(b)[0] >= era), None)
        if first_recent is not None:
            ax.axvline(first_recent - 0.5, color="black", ls="--", lw=1.5)
            ax.text(first_recent - 0.4, ax.get_ylim()[1] * 0.5, "ChatGPT launch", rotation=90,
                    va="top", fontsize=10)
        ax.set_ylabel(f"mean {lag}-year valuation ({to_date:%b %Y} $)")
        ax.set_xlabel("YC batch")
        ax.set_title(f"{label} — mean {lag}-year post-YC valuation by batch")
        fig.tight_layout()
        path = f"{out_prefix}_{lag}yr.png"
        fig.savefig(path, dpi=130)
        plt.close(fig)
        L += [f"![chart]({path})", ""]

    return "\n".join(L), frames


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--to-year", type=int, required=True)
    ap.add_argument("--cutoff", type=int, required=True)
    ap.add_argument("--label", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    md, _ = report(a.label, a.db, date(a.to_year, 6, 1), a.cutoff, a.out)
    open(a.out + ".md", "w", encoding="utf-8").write(md)
    print(md)
