#!/usr/bin/env python3
"""Fetch the YC company directory from Algolia.

Unlike the original fetch_yc_companies.py, this pulls a live Algolia search key
off ycombinator.com/companies -- the key hardcoded in the original now 403s.
"""
import csv
import json
import re
import sys
import time

import requests

APP_ID = "45BWZJ1SGC"
URL = "https://45bwzj1sgc-dsn.algolia.net/1/indexes/*/queries"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36")


def live_search_key() -> str:
    html = requests.get("https://www.ycombinator.com/companies",
                        headers={"User-Agent": UA}, timeout=60).text
    # The secured key is a long base64 blob containing restrictIndices=YCCompany_production
    for cand in re.findall(r"[A-Za-z0-9+/=]{150,}", html):
        try:
            decoded = __import__("base64").b64decode(cand + "==").decode("utf-8", "ignore")
        except Exception:
            continue
        if "YCCompany_production" in decoded:
            return cand
    raise RuntimeError("could not find a live Algolia search key on ycombinator.com/companies")


def headers(key: str) -> dict:
    return {
        "content-type": "application/x-www-form-urlencoded",
        "Origin": "https://www.ycombinator.com",
        "Referer": "https://www.ycombinator.com/",
        "User-Agent": UA,
        "x-algolia-agent": "Algolia for JavaScript (3.35.1); Browser; JS Helper (3.16.1)",
        "x-algolia-application-id": APP_ID,
        "x-algolia-api-key": key,
    }


def query(key: str, params: str) -> dict:
    r = requests.post(URL, headers=headers(key),
                      json={"requests": [{"indexName": "YCCompany_production",
                                          "params": params}]}, timeout=60)
    r.raise_for_status()
    return r.json()["results"][0]


def main() -> None:
    key = live_search_key()
    print(f"got live Algolia key ({len(key)} chars)")
    facets = query(key, "analytics=false&facets=batch&hitsPerPage=0&maxValuesPerFacet=1000&page=0&query=")
    batches = facets["facets"]["batch"]
    print(f"{len(batches)} batches, {facets['nbHits']} companies total")

    rows = []
    for i, batch in enumerate(sorted(batches), 1):
        page, got = 0, 0
        while True:
            res = query(key, (f'facetFilters=%5B%5B%22batch%3A{requests.utils.quote(batch)}%22%5D%5D'
                              f"&hitsPerPage=1000&page={page}&query="))
            hits = res["hits"]
            for h in hits:
                rows.append({"name": h.get("name", ""), "batch": h.get("batch", ""),
                             "website": h.get("website", "")})
            got += len(hits)
            page += 1
            if page >= res["nbPages"]:
                break
        print(f"  [{i}/{len(batches)}] {batch}: {got} (expected {batches[batch]})")
        if got != batches[batch]:
            raise RuntimeError(f"batch {batch}: fetched {got} != facet count {batches[batch]}")
        time.sleep(0.1)

    out = sys.argv[1] if len(sys.argv) > 1 else "yc-scrape/yc_companies_2026.csv"
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["name", "batch", "website"])
        w.writeheader()
        w.writerows(rows)
    print(f"wrote {len(rows)} rows to {out}")


if __name__ == "__main__":
    main()
