#!/usr/bin/env python3
"""2026 re-run of the YC valuation collector.

Same prompt and same submit_valuations tool contract as
yc_valuation_analyzer_resume.py; three forced deviations:
  * current_year 2025 -> 2026
  * claude-3-5-haiku-latest is retired -> claude-haiku-4-5 (same tier)
  * higher concurrency + 429 backoff, and per-call usage is logged so the
    run's API cost is auditable instead of guessed.
"""
import argparse
import asyncio
import os
import random
import sqlite3
import sys
import time

from anthropic import Anthropic

MODEL = os.getenv("YC_MODEL", "claude-haiku-4-5-20251001")
CURRENT_YEAR = 2026
# haiku-4.5 list price, USD per token / per search
PRICE_IN, PRICE_OUT, PRICE_SEARCH = 1.0 / 1e6, 5.0 / 1e6, 10.0 / 1000

SUBMIT_TOOL = {
    "name": "submit_valuations",
    "description": "Submit the final valuation data for the company",
    "input_schema": {
        "type": "object",
        "properties": {
            "company": {"type": "string"},
            "final_year": {
                "type": "integer",
                "description": ("The last year this company should be tracked (due to acquisition, "
                                f"bankruptcy, etc.). If still operating, use {CURRENT_YEAR}."),
            },
            "end_reason": {
                "type": "string",
                "description": ("Reason for ending tracking: 'acquired', 'bankrupt', 'shutdown', "
                                "'still_operating', etc."),
            },
            "valuations": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "year": {"type": "integer"},
                        "valuation": {"type": "string"},
                        "source": {"type": "string"},
                        "notes": {"type": "string"},
                    },
                    "required": ["year", "valuation", "source", "notes"],
                },
            },
        },
        "required": ["company", "final_year", "end_reason", "valuations"],
    },
}


NUDGE = """

You MUST finish by calling the submit_valuations tool, even if your searches turn up
nothing. For any year with no publicly available valuation, submit that year with
valuation "Not found". Never end your turn without calling submit_valuations.
"""


def prompt_for(company, years, nudge=False):
    years_str = ", ".join(map(str, years))
    return f"""
Search the internet for the market valuation of "{company['name']}" for each of these years: {years_str}

Company details:
- Name: {company['name']}
- YC Batch: {company['batch']} (YC year: {company['yc_year']})
- Website: {company['website']}

Please search for:
- Funding rounds and valuations
- IPO information if public
- Acquisition details if acquired  
- Market cap data if publicly traded
- Private market valuations
- Exit events (acquisitions, IPOs)
- Company closure, bankruptcy, or shutdown

Search sources like:
- TechCrunch, Bloomberg, Reuters, Wall Street Journal
- SEC filings and regulatory documents
- Company press releases and investor announcements
- Crunchbase, PitchBook, AngelList
- Financial news sites and startup databases

IMPORTANT: If the company was acquired, went bankrupt, shut down, or had any final exit event, indicate the FINAL YEAR of operations/valuation in your response.

When you have gathered the data, use the submit_valuations tool to submit your findings.

For each year, provide:
- The valuation amount (e.g., "$95B", "$50M", "Acquired for $2B"). Be sure that the valuation is a monetary figure, and that it is the company's value (and not, e.g. its revenue). 
- The source URL where you found this information
- Brief notes about the context (funding round, IPO, acquisition, etc.)

Include ALL years from {company['yc_year']} to the final year of operations, or to {CURRENT_YEAR} if still operating.
""" + (NUDGE if nudge else "")


class Collector:
    statuses = "('pending','error')"

    def __init__(self, db_path, concurrency, nudge=False):
        self.nudge = nudge
        self.db_path = db_path
        self.client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"], max_retries=5)
        self.sem = asyncio.Semaphore(concurrency)
        self.lock = asyncio.Lock()
        self.done = self.failed = 0
        self.cost = 0.0
        self.t0 = time.time()
        self._init_usage_table()

    def _conn(self):
        c = sqlite3.connect(self.db_path, timeout=60)
        c.execute("PRAGMA busy_timeout=60000")
        return c

    def _init_usage_table(self):
        c = self._conn()
        c.execute("""CREATE TABLE IF NOT EXISTS api_usage (
            id INTEGER PRIMARY KEY AUTOINCREMENT, company TEXT, model TEXT,
            input_tokens INTEGER, output_tokens INTEGER, searches INTEGER,
            cost_usd REAL, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
        c.commit()
        c.close()

    def pending(self, where=""):
        c = self._conn()
        rows = c.execute("""SELECT company, batch, yc_year, website FROM companies
                             WHERE status IN {statuses} {where} ORDER BY random()""".format(
                                 statuses=self.statuses, where=where)).fetchall()
        c.close()
        return [{"name": r[0], "batch": r[1], "yc_year": r[2], "website": r[3] or ""} for r in rows]

    def _save(self, company, valuations, final_year, end_reason, usage):
        c = self._conn()
        cur = c.cursor()
        for v in valuations:
            try:
                year = int(v["year"])
            except (TypeError, ValueError, KeyError):
                continue
            cur.execute("""INSERT OR REPLACE INTO valuations (company, year, valuation, source, notes)
                           VALUES (?,?,?,?,?)""",
                        (company, year, str(v.get("valuation", "")), str(v.get("source", "")),
                         str(v.get("notes", ""))))
        cur.execute("""UPDATE companies SET status='completed', final_year=?, end_reason=?,
                       processed_at=CURRENT_TIMESTAMP WHERE company=?""",
                    (final_year, end_reason, company))
        cur.execute("""INSERT INTO api_usage (company, model, input_tokens, output_tokens, searches, cost_usd)
                       VALUES (?,?,?,?,?,?)""",
                    (company, MODEL, usage[0], usage[1], usage[2], usage[3]))
        c.commit()
        c.close()

    def _mark(self, company, status, usage=None):
        c = self._conn()
        cur = c.cursor()
        cur.execute("UPDATE companies SET status=?, processed_at=CURRENT_TIMESTAMP WHERE company=?",
                    (status, company))
        if usage:
            cur.execute("""INSERT INTO api_usage (company, model, input_tokens, output_tokens, searches, cost_usd)
                           VALUES (?,?,?,?,?,?)""", (company, MODEL, *usage))
        c.commit()
        c.close()

    async def run_one(self, company):
        years = list(range(company["yc_year"], CURRENT_YEAR + 1))
        async with self.sem:
            usage = (0, 0, 0, 0.0)
            try:
                msg = await asyncio.to_thread(
                    self.client.messages.create,
                    model=MODEL, max_tokens=6000,
                    messages=[{"role": "user", "content": prompt_for(company, years, self.nudge)}],
                    tools=[{"type": "web_search_20250305", "name": "web_search", "max_uses": 10},
                           SUBMIT_TOOL],
                )
                u = msg.usage
                searches = getattr(getattr(u, "server_tool_use", None), "web_search_requests", 0) or 0
                cost = (u.input_tokens * PRICE_IN + u.output_tokens * PRICE_OUT
                        + searches * PRICE_SEARCH)
                usage = (u.input_tokens, u.output_tokens, searches, cost)
                submitted = next((b.input for b in msg.content
                                  if getattr(b, "name", None) == "submit_valuations"), None)
                if submitted and isinstance(submitted, dict) and submitted.get("valuations"):
                    await asyncio.to_thread(
                        self._save, company["name"], submitted["valuations"],
                        submitted.get("final_year", CURRENT_YEAR),
                        submitted.get("end_reason", "still_operating"), usage)
                    ok = True
                else:
                    await asyncio.to_thread(self._mark, company["name"], "failed", usage)
                    ok = False
            except Exception as e:  # network/API failures: mark 'error' so a later pass retries
                await asyncio.to_thread(self._mark, company["name"], "error", usage)
                print(f"   !! {company['name']}: {type(e).__name__}: {e}", flush=True)
                ok = False
            async with self.lock:
                self.done += 1
                self.failed += 0 if ok else 1
                self.cost += usage[3]
                if self.done % 25 == 0:
                    rate = self.done / (time.time() - self.t0) * 3600
                    print(f"   [{self.done}] failed={self.failed} ${self.cost:.2f} "
                          f"({rate:.0f}/h, ${self.cost/self.done:.3f}/co)", flush=True)


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="yc_valuations_2026.db")
    ap.add_argument("--concurrency", type=int, default=20)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--where", default="", help="extra SQL predicate, e.g. \"and yc_year>=2023\"")
    ap.add_argument("--retry-failed", action="store_true",
                    help="re-attempt companies the model refused to submit for, with an explicit "
                         "instruction to always call submit_valuations")
    args = ap.parse_args()

    col = Collector(args.db, args.concurrency, nudge=args.retry_failed)
    col.statuses = "('failed')" if args.retry_failed else "('pending','error')"
    todo = col.pending(args.where)
    if args.limit:
        todo = todo[:args.limit]
    print(f"model={MODEL} concurrency={args.concurrency} pending={len(todo)}", flush=True)
    await asyncio.gather(*(col.run_one(c) for c in todo))
    print(f"\ndone: {col.done} processed, {col.failed} failed, ${col.cost:.2f} spent, "
          f"{(time.time()-col.t0)/60:.1f} min", flush=True)


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
