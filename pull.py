"""
S4L Comm Code Report — Google Ads data pull.

Two modes:
    python pull.py --backfill     one-off, 36 months
    python pull.py                daily, last 35 days

Both write to data/daily.csv.gz. The daily run replaces only the dates it
pulled and leaves older history untouched, so the archive keeps data that
has since aged out of Google's 37-month retention window.

Setup:
    pip install google-ads pandas openpyxl
"""

from __future__ import annotations

import argparse
import gzip
import re
import sys
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
from google.ads.googleads.client import GoogleAdsClient

# ---------------------------------------------------------------- config

CUSTOMER_ID = "3119628801"          # Shelters4Less
CONFIG_PATH = "google-ads.yaml"
LOOKUP_PATH = "PBH - Item IDs to Item Group IDs Lookup.xlsx"

DATA_DIR = Path("data")
ARCHIVE = DATA_DIR / "daily.csv.gz"

BACKFILL_MONTHS = 36
DAILY_LOOKBACK_DAYS = 35            # conv window 30 + margin for reporting lag

UNMAPPED = "Unmapped"
SH_SUFFIX = re.compile(r"-sh$", re.IGNORECASE)

QUERY = """
    SELECT
      segments.date,
      segments.product_item_id,
      metrics.impressions,
      metrics.clicks,
      metrics.cost_micros,
      metrics.conversions,
      metrics.conversions_value
    FROM shopping_performance_view
    WHERE segments.date BETWEEN '{start}' AND '{end}'
"""

# ---------------------------------------------------------------- fetch


def month_windows(start: date, end: date):
    """Chunk the range by month so no single response gets unwieldy."""
    cur = start
    while cur <= end:
        nxt = (cur.replace(day=1) + timedelta(days=32)).replace(day=1)
        yield cur, min(nxt - timedelta(days=1), end)
        cur = nxt


def fetch(start: date, end: date) -> pd.DataFrame:
    client = GoogleAdsClient.load_from_storage(CONFIG_PATH)
    service = client.get_service("GoogleAdsService")

    rows = []
    for w_start, w_end in month_windows(start, end):
        print(f"  fetching {w_start} to {w_end} ...", flush=True)
        q = QUERY.format(start=w_start.isoformat(), end=w_end.isoformat())
        stream = service.search_stream(customer_id=CUSTOMER_ID, query=q)
        n = 0
        for batch in stream:
            for r in batch.results:
                rows.append(
                    (
                        r.segments.date,
                        r.segments.product_item_id,
                        r.metrics.impressions,
                        r.metrics.clicks,
                        r.metrics.cost_micros / 1_000_000,
                        r.metrics.conversions,
                        r.metrics.conversions_value,
                    )
                )
                n += 1
        print(f"    {n:,} rows", flush=True)

    return pd.DataFrame(
        rows,
        columns=["date", "item_id", "impressions", "clicks", "cost", "conversions", "conv_value"],
    )


# ---------------------------------------------------------------- transform


def load_lookup(path: str) -> pd.DataFrame:
    p = Path(path)
    if not p.exists():
        sys.exit(f"Lookup not found: {p.resolve()}")
    df = pd.read_excel(p, dtype=str) if p.suffix.lower() in {".xlsx", ".xls"} else pd.read_csv(p, dtype=str)
    df = df.iloc[:, :2]
    df.columns = ["item_id", "item_group_id"]
    df["item_id"] = df["item_id"].astype(str).str.strip().str.lower()
    df["item_group_id"] = df["item_group_id"].astype(str).str.strip()

    # "Uncoded" is folded into the unmapped bucket.
    df.loc[df["item_group_id"].str.lower() == "uncoded", "item_group_id"] = UNMAPPED

    before = len(df)
    df = df.drop_duplicates("item_id", keep="first")
    if len(df) != before:
        print(f"  note: dropped {before - len(df):,} duplicate lookup keys")
    return df


def transform(raw: pd.DataFrame, lookup: pd.DataFrame) -> pd.DataFrame:
    df = raw.copy()
    df["item_id"] = df["item_id"].astype(str).str.strip().str.lower()

    # Anchored to the end only. A global replace would corrupt IDs like
    # ekdrg5-shelf, cc-sheet and bespoke-shs02.
    #
    # Validated against the Aug-25 to Aug-26 product report: 3,499 of 7,024
    # S4L item IDs carry the suffix and no lookup key ends in -sh, so the
    # strip is required, not optional. Raw join reaches 83.4% of spend;
    # with the strip it reaches 97.7%. Colour suffixes (-blu, -grn, -blk,
    # -sil, -ut ...) are keyed that way in the lookup and must be left alone.
    stripped = df["item_id"].str.replace(SH_SUFFIX, "", regex=True)
    print(f"  -sh suffix stripped from {(stripped != df['item_id']).sum():,} rows")
    df["item_id"] = stripped

    df = df.merge(lookup, on="item_id", how="left", validate="many_to_one")
    n_unmapped = df["item_group_id"].isna().sum()
    df["item_group_id"] = df["item_group_id"].fillna(UNMAPPED)

    out = (
        df.groupby(["date", "item_group_id"], as_index=False)[
            ["impressions", "clicks", "cost", "conversions", "conv_value"]
        ]
        .sum()
    )

    # Reconciliation: aggregation must not lose or invent anything.
    for col in ["impressions", "clicks", "cost", "conversions", "conv_value"]:
        a, b = raw[col].sum(), out[col].sum()
        if abs(a - b) > 0.01:
            sys.exit(f"RECONCILIATION FAILED — {col}: {a:,.4f} in, {b:,.4f} out")

    unmapped_cost = out.loc[out["item_group_id"] == UNMAPPED, "cost"].sum()
    total_cost = out["cost"].sum()
    pct = unmapped_cost / total_cost * 100 if total_cost else 0
    print(f"  {n_unmapped:,} rows unmapped ({pct:.1f}% of spend)")
    print(f"  {out['item_group_id'].nunique():,} comm codes, {out['date'].nunique():,} days")
    return out


# ---------------------------------------------------------------- archive


def merge_archive(new: pd.DataFrame) -> pd.DataFrame:
    DATA_DIR.mkdir(exist_ok=True)
    if ARCHIVE.exists():
        old = pd.read_csv(ARCHIVE)
        pulled = set(new["date"])
        kept = old[~old["date"].isin(pulled)]
        print(f"  archive: kept {len(kept):,} older rows, replaced {len(old) - len(kept):,}")
        combined = pd.concat([kept, new], ignore_index=True)
    else:
        combined = new
    combined = combined.sort_values(["date", "item_group_id"]).reset_index(drop=True)
    combined.to_csv(ARCHIVE, index=False, compression="gzip")
    print(f"  wrote {ARCHIVE} — {len(combined):,} rows, {ARCHIVE.stat().st_size / 1e6:.1f} MB")
    return combined


# ---------------------------------------------------------------- main


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--backfill", action="store_true", help="pull 36 months instead of 35 days")
    args = ap.parse_args()

    end = date.today() - timedelta(days=1)
    if args.backfill:
        start = end - timedelta(days=int(BACKFILL_MONTHS * 30.44))
        print(f"BACKFILL: {start} to {end}")
    else:
        start = end - timedelta(days=DAILY_LOOKBACK_DAYS - 1)
        print(f"DAILY: {start} to {end}")

    print("Loading lookup ...")
    lookup = load_lookup(LOOKUP_PATH)

    print("Fetching from Google Ads ...")
    raw = fetch(start, end)
    if raw.empty:
        sys.exit("No rows returned. Check the customer ID and date range.")
    print(f"  {len(raw):,} raw rows")

    print("Transforming ...")
    out = transform(raw, lookup)

    print("Updating archive ...")
    merge_archive(out)
    print("Done.")


if __name__ == "__main__":
    main()
