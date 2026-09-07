#!/usr/bin/env python3
"""Cleaned re-run report.

Three cleaning steps the raw pipeline lacks, applied symmetrically to both eras:

1. ALIAS DEDUP. The YC directory lists some companies twice under variant names
   ("Legora" / "Legora (formerly Leya)", "Corgi" / "Corgi Insurance",
   "QuickNode" / "Quicknode"), so one company can occupy two top-20 slots. Names
   are normalised and duplicates collapsed to the higher figure at the mark --
   the parser's dominant error is *understatement* (it takes the first number in
   a multi-round string like "$630M (January), $1.3B (May), $4.0B (July)").

2. SYNTHETIC-ESTIMATE FILTER. startuphub.ai and similar publish algorithmic
   "effective valuations" from sector comparables ("19% confidence"). They are
   not reported valuations. Rows sourced to them, or whose notes say the figure
   is estimated from comparable companies, are dropped.

3. MANUAL TOP-20 VERIFICATION. Same step the original author took. Verified
   fabrications are dropped by name+year; see FABRICATED below.
"""

import argparse
import re
import sqlite3
from datetime import date

import cpi
import numpy as np
import pandas as pd
from scipy import stats

from analysis_2026 import format_valuation, lagged_valuation, parse_valuation

# Verified against the web on 2026-09-07. Three different companies were each
# given the identical invented round "$330M Series B at $6.6B, December 2025";
# no such round exists for any of them.
FABRICATED = {
    # Invented round, three companies given the identical story
    # "$330M Series B at $6.6B, December 2025". No such round exists for any.
    ("Rimward", 2025),
    ("Rimward", 2026),
    ("AtlasGrid", 2025),
    ("AtlasGrid", 2026),
    ("Piggy Robotics", 2025),
    ("Piggy Robotics", 2026),
    # Delve's real round ($32M Series A at $300M led by Insight Partners,
    # July 2025) re-used verbatim for two other companies. Clado has raised
    # $2.5M total; the cited clado.ai URL does not exist.
    ("Clado", 2026),
    # continue.dev (YC S23) raised ~$5M and was acqui-hired by Cursor in June
    # 2026 for undisclosed terms; the $65M-at-$500M round belongs to a
    # different "Continue".
    ("Continue", 2024),
    ("Continue", 2025),
    # $470M belongs to Cortex Applications (YC W20 developer portal). This
    # Cortex AI (YC F25, robotics data) has raised $6.5M total.
    ("Cortex AI", 2026),
    # Year misattribution: the row's own notes say the $260M is "from Series B
    # in July 2025, but this reflects valuation at end of 2024 period".
    ("Unify", 2024),
}
# Targets *synthetic* valuations (modelled from sector comparables), not news
# articles that happen to sit on an aggregator's domain -- filtering by domain
# alone wrongly discarded Legora's real Series B row from the baseline.
ESTIMATE_PAT = re.compile(
    r"comparable compan|estimated valuation based on|effective valuation"
    r"|confidence\)|\bconfidence\b.*estimat|estimat.*\bconfidence\b"
    r"|\(estimated\)|estimated range",
    re.IGNORECASE,
)


def norm(name):
    n = str(name).lower()
    n = re.sub(r"\(.*?\)", " ", n)  # "Legora (formerly Leya)" -> "legora"
    n = re.sub(r"\b(insurance|inc|corp|labs?|technologies|ai)\b", " ", n)
    return re.sub(r"[^a-z0-9]", "", n)


def load(db, cutoff, to_date, clean=True, since=None, year_max=None):
    """Load valuation rows.

    `year_max` caps the valuation year independently of the batch cutoff, so a
    chart can include the current batch year (whose only mark is year 0) without
    pulling in a stray future-dated row.

    `since` restricts to rows written on or after that timestamp, which selects
    a single collection vintage: `since="2026-09-06"` keeps only what the Sep-2026
    pass collected and drops every Aug-2025 row still sitting in the database.
    """
    conn = sqlite3.connect(db)
    vintage = f"AND v.created_at >= '{since}'" if since else ""
    df = pd.read_sql_query(
        f"""
        SELECT v.company, v.year, v.valuation, v.source, v.notes,
               c.yc_year, c.batch, c.final_year, c.end_reason
        FROM valuations v JOIN companies c ON v.company = c.company
        WHERE c.status = 'completed' AND c.yc_year < {cutoff}
          AND v.year <= {year_max if year_max else cutoff} {vintage}""",
        conn,
    )
    conn.close()
    dropped = {}
    if clean:
        blob = df.valuation.fillna("") + " " + df.notes.fillna("")
        est = blob.str.contains(ESTIMATE_PAT)
        fab = df.apply(lambda r: (r.company, r.year) in FABRICATED, axis=1)
        dropped = {
            "synthetic estimates": int(est.sum()),
            "verified fabrications": int(fab.sum()),
        }
        df = df[~est & ~fab].copy()
    df["valuation_numeric"] = df.valuation.apply(parse_valuation)
    return df[df.valuation_numeric.notna()].copy(), dropped


def marks(numeric, to_date, dedup=True, strict_one_year=False, lags=None):
    inflators = {
        y: cpi.inflate(1, date(int(y), 6, 1), to=to_date) for y in numeric.year.unique()
    }
    out = {}
    plan = ([(l, True) for l in lags] if lags
            else [(2, True), (1, True if strict_one_year else False)])
    for lag, strict in plan:
        rows = [
            g
            for company in numeric.company.unique()
            if (
                g := lagged_valuation(
                    numeric[numeric.company == company], lag, inflators, strict
                )
            )
        ]
        df = pd.DataFrame(rows)
        if dedup and len(df):
            df["key"] = df.company.map(norm)
            df = (
                df.sort_values("valuation_real", ascending=False)
                .drop_duplicates("key", keep="first")
                .reset_index(drop=True)
            )
        out[lag] = df
    return out


def compare(label_a, frames_a, label_b, frames_b, era=2023):
    lines = []
    for lag in (2, 1):
        lines += [f"\n{'=' * 96}\n{lag}-YEAR POST-YC VALUATION\n{'=' * 96}"]
        rowsets = []
        for label, frames in ((label_a, frames_a), (label_b, frames_b)):
            df = frames[lag]
            top = df.sort_values("valuation_real", ascending=False).head(20)
            recent, older = df[df.yc_year >= era], df[df.yc_year < era]
            base = len(recent) / len(df) * 100
            hits = int((top.yc_year >= era).sum())
            geo = lambda s: 10 ** np.log10(s[s > 0]).mean()
            _, p = stats.mannwhitneyu(
                recent.valuation_real, older.valuation_real, alternative="two-sided"
            )
            _, pl = stats.ttest_ind(
                np.log10(recent.valuation_real[recent.valuation_real > 0]),
                np.log10(older.valuation_real[older.valuation_real > 0]),
                equal_var=False,
            )
            rowsets.append(
                {
                    "run": label,
                    "n": len(df),
                    f"{era}+ in top 20": f"{hits}/20",
                    "base rate": f"{base:.1f}%",
                    "lift": f"{(hits / 20 * 100) / base:.2f}x",
                    f"mean pre-{era}": format_valuation(older.valuation_real.mean()),
                    f"mean {era}+": format_valuation(recent.valuation_real.mean()),
                    "mean ratio": f"{recent.valuation_real.mean() / older.valuation_real.mean():.2f}x",
                    f"median pre-{era}": format_valuation(
                        older.valuation_real.median()
                    ),
                    f"median {era}+": format_valuation(recent.valuation_real.median()),
                    f"geomean pre-{era}": format_valuation(geo(older.valuation_real)),
                    f"geomean {era}+": format_valuation(geo(recent.valuation_real)),
                    f">=$1B pre-{era}": f"{(older.valuation_real >= 1e9).mean() * 100:.2f}%",
                    f">=$1B {era}+": f"{(recent.valuation_real >= 1e9).mean() * 100:.2f}%",
                    "MWU p": f"{p:.3g}",
                    "log-t p": f"{pl:.3g}",
                }
            )
        lines.append(pd.DataFrame(rowsets).set_index("run").T.to_string())
        for label, frames in ((label_a, frames_a), (label_b, frames_b)):
            df = frames[lag]
            top = df.sort_values("valuation_real", ascending=False).head(25)
            lines.append(f"\n-- {label}: top 25 ({lag}-yr) --")
            for i, (_, r) in enumerate(top.iterrows(), 1):
                star = "*" if r.yc_year >= era else " "
                lines.append(
                    f"  {i:>2}{star} {r.company:<26} {r.batch:<13} "
                    f"{format_valuation(r.valuation_real):>8}   {str(r.raw)[:44]}"
                )
    return "\n".join(lines)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--raw",
        action="store_true",
        help="skip cleaning (reproduce the naive pipeline)",
    )
    a = ap.parse_args()
    clean = not a.raw
    old_num, _ = load("yc_valuations.db", 2025, date(2025, 6, 1), clean=clean)
    new_num, dropped = load(
        "yc_valuations_2026.db", 2026, date(2026, 6, 1), clean=clean
    )
    print(f"cleaning={'ON' if clean else 'OFF'}  rows dropped from re-run: {dropped}")
    for strict in (False, True):
        print(
            f"\n\n{'#' * 96}\n# 1-YEAR WINDOW: "
            f"{'STRICT (target year only, consistent with the 2-year rule)' if strict else 'ORIGINAL (target year +/- 1)'}"
            f"\n{'#' * 96}"
        )
        print(
            compare(
                "baseline Aug-2025",
                marks(old_num, date(2025, 6, 1), clean, strict),
                "re-run Sep-2026",
                marks(new_num, date(2026, 6, 1), clean, strict),
            )
        )
