#!/usr/bin/env python3
"""Quantify collection-vintage bias.

In the re-run, pre-2023 batches keep their Aug-2025 (claude-3-5-haiku) numbers
while 2023+ batches are re-collected with claude-haiku-4-5. If the two vintages
systematically disagree, the headline pre/post comparison is contaminated. This
picks a random pre-2023 sample, re-collects it with the new model, and reports
paired agreement on the 1-year and 2-year marks.

  python vintage_check.py select --n 120      # stage the sample (marks pending)
  <run the collector with --where "and yc_year<2023">
  python vintage_check.py compare
"""
import argparse
import sqlite3
from datetime import date

import cpi
import numpy as np
import pandas as pd

from analysis_2026 import build, format_valuation

OLD, NEW = "yc_valuations.db", "yc_valuations_2026.db"
SAMPLE_TABLE = "vintage_sample"


def select(n, seed):
    conn = sqlite3.connect(NEW)
    cur = conn.cursor()
    cur.execute(f"CREATE TABLE IF NOT EXISTS {SAMPLE_TABLE} (company TEXT PRIMARY KEY)")
    already = {r[0] for r in cur.execute(f"select company from {SAMPLE_TABLE}")}
    if already:
        print(f"sample already staged ({len(already)} companies)")
        return
    rows = [r[0] for r in cur.execute("""
        select distinct c.company from companies c join valuations v on v.company=c.company
        where c.status='completed' and c.yc_year<2023 and c.yc_year>=2015
        order by c.company""")]
    rng = np.random.default_rng(seed)
    pick = list(rng.choice(rows, size=min(n, len(rows)), replace=False))
    cur.executemany(f"insert into {SAMPLE_TABLE} values (?)", [(p,) for p in pick])
    cur.execute(f"""update companies set status='pending' where company in
                    (select company from {SAMPLE_TABLE})""")
    cur.execute(f"""delete from valuations where company in
                    (select company from {SAMPLE_TABLE})""")
    conn.commit()
    print(f"staged {len(pick)} pre-2023 companies for re-collection (cleared their old rows)")
    conn.close()


def marks(db, cutoff, to_date):
    _, _, _, frames = build(db, to_date, cutoff)
    out = {}
    for lag in (1, 2):
        df = frames[lag]
        out[lag] = df.set_index("company")[["valuation", "valuation_real", "raw"]]
    return out


def compare():
    sample = {r[0] for r in sqlite3.connect(NEW).execute(f"select company from {SAMPLE_TABLE}")}
    to_date = date(2026, 6, 1)
    old, new = marks(OLD, 2025, to_date), marks(NEW, 2026, to_date)
    print(f"vintage check on {len(sample)} pre-2023 companies "
          f"(claude-3-5-haiku Aug-2025 vs claude-haiku-4-5 Sep-2026)\n")
    for lag in (2, 1):
        o = old[lag].loc[old[lag].index.intersection(sample)]
        n = new[lag].loc[new[lag].index.intersection(sample)]
        both = o.index.intersection(n.index)
        print(f"--- {lag}-year mark ---")
        print(f"  had a numeric mark then: {len(o)}   now: {len(n)}   both: {len(both)}")
        if len(both) == 0:
            continue
        a, b = o.loc[both, "valuation_real"], n.loc[both, "valuation_real"]
        ratio = b / a
        exact = float((np.isclose(a, b, rtol=0.02)).mean())
        print(f"  identical value (within 2%): {exact*100:.0f}%")
        print(f"  mean:   then {format_valuation(a.mean())}  now {format_valuation(b.mean())} "
              f"({b.mean()/a.mean():.2f}×)")
        print(f"  median: then {format_valuation(a.median())}  now {format_valuation(b.median())} "
              f"({b.median()/a.median():.2f}×)")
        print(f"  median ratio of paired values: {ratio.median():.2f}×   "
              f"geo-mean ratio: {10**np.log10(ratio[ratio>0]).mean():.2f}×")
        big = ratio.sort_values()
        print("  biggest disagreements (then -> now):")
        for comp in list(big.index[:3]) + list(big.index[-3:]):
            print(f"    {comp:<28} {format_valuation(a[comp]):>9} -> {format_valuation(b[comp]):>9}"
                  f"   | now raw: {str(n.loc[comp,'raw'])[:48]}")
        print()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["select", "compare"])
    ap.add_argument("--n", type=int, default=120)
    ap.add_argument("--seed", type=int, default=20260906)
    a = ap.parse_args()
    select(a.n, a.seed) if a.mode == "select" else compare()
