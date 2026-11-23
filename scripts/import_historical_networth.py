"""
scripts/import_historical_networth.py
======================================
One-time import of historical monthly net worth snapshots into portfolio.db.

Each month is represented as one synthetic CASH holding per account type,
where qty = total value and price = $1.00, so market_value = the total.

The UNIQUE key in portfolio.db is (month, year, account_name, symbol).
Using a stable account_name per account type (e.g. "Historical-Savings")
means this script is safe to re-run — it will REPLACE existing rows.

Usage
-----
    python scripts/import_historical_networth.py [--dry-run]

Add --dry-run to print the rows that would be inserted without writing.

Edit HISTORICAL_DATA below to add more months.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Make sure project root is on the path so portfolio_db imports cleanly
# ---------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pandas as pd
from portfolio_db import db_upsert, HOLDINGS_COLUMNS

# ---------------------------------------------------------------------------
# Historical data
# ---------------------------------------------------------------------------
# Each entry is (month, year, account_type, account_name, total_value).
#
# account_type must be one of the values the app recognises:
#   Savings | Brokerage | Traditional | Roth | Real Estate
#
# account_name is used as the display label in the Net Worth Statement and
# is also part of the UNIQUE key, so keep it stable across months.
#
# Real Estate is intentionally excluded here — it is managed via config
# (retirement_config.json → real_estate.properties) and added on top of
# the DB values at render time, so inserting it here would double-count it.
# ---------------------------------------------------------------------------
HISTORICAL_DATA: list[tuple[int, int, str, str, float]] = [
    # (month, year, account_type,   account_name,         total_value)

    # ── October 2025 ────────────────────────────────────────────────
    (10, 2025, "Savings",     "PNC",                       130_602.20),
    (10, 2025, "Brokerage",   "Charles Schwab",          1_158_448.06),
    (10, 2025, "Brokerage",   "IBM Stock",                 507_799.84),
    (10, 2025, "Traditional", "CGEY 401K",                 529_025.15),
    (10, 2025, "Traditional", "Highmark 401K",           1_224_673.00),
    (10, 2025, "Traditional", "IBM 401K",                3_922_279.86),
    (10, 2025, "Traditional", "HM Pension",                 79_000.00),
    (10, 2025, "Traditional", "IBM Pension (new)",          26_188.47),
    (10, 2025, "Traditional", "IBM Pension",                78_295.98),

    # ── November 2025 ───────────────────────────────────────────────
    (11, 2025, "Savings",     "PNC",                       124_768.81),
    (11, 2025, "Brokerage",   "Charles Schwab",          1_051_615.32),
    (11, 2025, "Brokerage",   "IBM Stock",                 547_084.65),
    (11, 2025, "Traditional", "CGEY 401K",                 527_592.39),
    (11, 2025, "Traditional", "Highmark 401K",           1_230_919.04),
    (11, 2025, "Traditional", "IBM 401K",                3_839_531.80),
    (11, 2025, "Traditional", "HM Pension",                 79_000.00),
    (11, 2025, "Traditional", "IBM Pension (new)",          27_585.20),
    (11, 2025, "Traditional", "IBM Pension",                78_627.41),

    # ── December 2025 ───────────────────────────────────────────────
    # Note: Roth accounts (Sarah Roth IRA, Tom Roth IRA, IBM 401k Roth)
    # and Sarah IRA first appear this month.
    (12, 2025, "Savings",     "PNC",                       120_948.27),
    (12, 2025, "Brokerage",   "Charles Schwab",            688_868.36),
    (12, 2025, "Brokerage",   "IBM Stock",                 527_172.58),
    (12, 2025, "Roth",        "Sarah Roth IRA",            136_712.79),
    (12, 2025, "Roth",        "Tom Roth IRA",               61_773.16),
    (12, 2025, "Roth",        "IBM 401k Roth",             422_436.81),
    (12, 2025, "Traditional", "Sarah IRA",                 163_898.42),
    (12, 2025, "Traditional", "CGEY 401K",                 533_843.09),
    (12, 2025, "Traditional", "Highmark 401K",           1_230_843.74),
    (12, 2025, "Traditional", "CVS 401k",                   14_322.99),
    (12, 2025, "Traditional", "IBM 401K",                3_454_980.00),
    (12, 2025, "Traditional", "HM Pension",                 79_302.97),
    (12, 2025, "Traditional", "IBM Pension (new)",          28_677.91),
    (12, 2025, "Traditional", "IBM Pension",                78_928.95),

    # ── January 2026 ────────────────────────────────────────────────
    # Sarah IRA shows $0 this month — omitted (zero rows add no value).
    ( 1, 2026, "Savings",     "PNC",                       111_952.22),
    ( 1, 2026, "Brokerage",   "Charles Schwab",            668_084.14),
    ( 1, 2026, "Brokerage",   "IBM Stock",                 547_152.70),
    ( 1, 2026, "Roth",        "Sarah Roth IRA",            268_782.39),
    ( 1, 2026, "Roth",        "Tom Roth IRA",               60_574.93),
    ( 1, 2026, "Roth",        "IBM 401k Roth",             443_756.89),
    ( 1, 2026, "Traditional", "CGEY 401K",                 552_665.29),
    ( 1, 2026, "Traditional", "Highmark 401K",           1_264_894.50),
    ( 1, 2026, "Traditional", "CVS 401k",                   14_322.99),
    ( 1, 2026, "Traditional", "IBM 401K",                3_585_634.67),
    ( 1, 2026, "Traditional", "HM Pension",                 59_030.21),
    ( 1, 2026, "Traditional", "IBM Pension (new)",          29_725.09),
    ( 1, 2026, "Traditional", "IBM Pension",                79_231.64),

    # ── February 2026 ───────────────────────────────────────────────
    # Sarah IRA shows $0 — omitted.
    ( 2, 2026, "Savings",     "PNC",                       119_584.43),
    ( 2, 2026, "Brokerage",   "Charles Schwab",            631_777.19),
    ( 2, 2026, "Brokerage",   "IBM Stock",                 430_856.36),
    ( 2, 2026, "Roth",        "Sarah Roth IRA",            261_639.51),
    ( 2, 2026, "Roth",        "Tom Roth IRA",               52_656.93),
    ( 2, 2026, "Roth",        "IBM 401k Roth",             457_923.30),
    ( 2, 2026, "Traditional", "CGEY 401K",                 553_486.64),
    ( 2, 2026, "Traditional", "Highmark 401K",           1_264_894.50),
    ( 2, 2026, "Traditional", "CVS 401k",                   14_322.99),
    ( 2, 2026, "Traditional", "IBM 401K",                3_674_172.11),
    ( 2, 2026, "Traditional", "HM Pension",                 59_030.21),
    ( 2, 2026, "Traditional", "IBM Pension (new)",          31_057.71),
    ( 2, 2026, "Traditional", "IBM Pension",                79_535.49),

    # ── March 2026 ──────────────────────────────────────────────────
    # Sarah IRA shows $0 — omitted.
    ( 3, 2026, "Savings",     "PNC",                       120_707.57),
    ( 3, 2026, "Brokerage",   "Charles Schwab",            617_679.97),
    ( 3, 2026, "Brokerage",   "IBM Stock",                 452_455.68),
    ( 3, 2026, "Roth",        "Sarah Roth IRA",            259_360.24),
    ( 3, 2026, "Roth",        "Tom Roth IRA",               47_835.21),
    ( 3, 2026, "Roth",        "IBM 401k Roth",             430_146.16),
    ( 3, 2026, "Traditional", "CGEY 401K",                 555_834.11),
    ( 3, 2026, "Traditional", "Highmark 401K",           1_163_438.23),
    ( 3, 2026, "Traditional", "CVS 401k",                   14_322.99),
    ( 3, 2026, "Traditional", "IBM 401K",                3_451_300.80),
    ( 3, 2026, "Traditional", "HM Pension",                 59_030.21),
    ( 3, 2026, "Traditional", "IBM Pension (new)",          32_384.60),
    ( 3, 2026, "Traditional", "IBM Pension",                79_840.51),

    # ── April 2026 ──────────────────────────────────────────────────
    # Sarah IRA shows $0 — omitted.
    ( 4, 2026, "Savings",     "PNC",                       119_630.98),
    ( 4, 2026, "Brokerage",   "Charles Schwab",            697_438.32),
    ( 4, 2026, "Brokerage",   "IBM Stock",                 426_247.00),
    ( 4, 2026, "Roth",        "Sarah Roth IRA",            275_090.64),
    ( 4, 2026, "Roth",        "Tom Roth IRA",               50_551.12),
    ( 4, 2026, "Roth",        "IBM 401k Roth",             464_920.23),
    ( 4, 2026, "Traditional", "CGEY 401K",                 557_172.07),
    ( 4, 2026, "Traditional", "Highmark 401K",           1_163_438.23),
    ( 4, 2026, "Traditional", "CVS 401k",                   14_322.99),
    ( 4, 2026, "Traditional", "IBM 401K",                3_730_312.40),
    ( 4, 2026, "Traditional", "HM Pension",                 59_030.21),
    ( 4, 2026, "Traditional", "IBM Pension (new)",          33_493.64),
    ( 4, 2026, "Traditional", "IBM Pension",                80_146.70),

    # ── May 2026 ────────────────────────────────────────────────────
    # Sarah IRA shows $0 — omitted.
    ( 5, 2026, "Savings",     "PNC",                       128_913.74),
    ( 5, 2026, "Brokerage",   "Charles Schwab",            709_888.35),
    ( 5, 2026, "Brokerage",   "IBM Stock",                 546_566.39),
    ( 5, 2026, "Roth",        "Sarah Roth IRA",            261_026.36),
    ( 5, 2026, "Roth",        "Tom Roth IRA",               56_155.32),
    ( 5, 2026, "Roth",        "IBM 401k Roth",             489_754.28),
    ( 5, 2026, "Traditional", "CGEY 401K",                 558_726.18),
    ( 5, 2026, "Traditional", "Highmark 401K",           1_452_244.48),
    ( 5, 2026, "Traditional", "CVS 401k",                   19_307.00),
    ( 5, 2026, "Traditional", "IBM 401K",                3_918_820.04),
    ( 5, 2026, "Traditional", "HM Pension",                 82_494.27),
    ( 5, 2026, "Traditional", "IBM Pension (new)",          34_684.62),
    ( 5, 2026, "Traditional", "IBM Pension",                80_454.06),

    # ── June 2026 ───────────────────────────────────────────────────
    # Sarah IRA shows $0 — omitted.
    ( 6, 2026, "Savings",     "PNC",                       118_806.46),
    ( 6, 2026, "Brokerage",   "Charles Schwab",            652_894.73),
    ( 6, 2026, "Brokerage",   "IBM Stock",                 522_238.15),
    ( 6, 2026, "Roth",        "Sarah Roth IRA",            288_757.55),
    ( 6, 2026, "Roth",        "Tom Roth IRA",               65_057.86),
    ( 6, 2026, "Roth",        "IBM 401k Roth",             502_376.80),
    ( 6, 2026, "Traditional", "CGEY 401K",                 564_535.90),
    ( 6, 2026, "Traditional", "Highmark 401K",           1_443_143.04),
    ( 6, 2026, "Traditional", "CVS 401k",                   19_307.00),
    ( 6, 2026, "Traditional", "IBM 401K",                4_001_667.15),
    ( 6, 2026, "Traditional", "HM Pension",                 82_494.27),
    ( 6, 2026, "Traditional", "IBM Pension (new)",          36_109.02),
    ( 6, 2026, "Traditional", "IBM Pension",                80_762.60),

    # ── July 2026 ───────────────────────────────────────────────────
    # Sarah IRA shows $0 — omitted.
    ( 7, 2026, "Savings",     "PNC",                       138_772.54),
    ( 7, 2026, "Brokerage",   "Charles Schwab",            728_723.36),
    ( 7, 2026, "Brokerage",   "IBM Stock",                 404_274.18),
    ( 7, 2026, "Roth",        "Sarah Roth IRA",            257_830.98),
    ( 7, 2026, "Roth",        "Tom Roth IRA",               53_225.15),
    ( 7, 2026, "Roth",        "IBM 401k Roth",             467_134.83),
    ( 7, 2026, "Traditional", "CGEY 401K",                 547_283.36),
    ( 7, 2026, "Traditional", "Highmark 401K",           1_443_143.04),
    ( 7, 2026, "Traditional", "CVS 401k",                   19_307.00),
    ( 7, 2026, "Traditional", "IBM 401K",                3_707_518.20),
    ( 7, 2026, "Traditional", "HM Pension",                 82_494.27),
    ( 7, 2026, "Traditional", "IBM Pension (new)",          37_247.80),
    ( 7, 2026, "Traditional", "IBM Pension",                81_072.32),

    # ── August 2026 ─────────────────────────────────────────────────
    # Sarah IRA now shows $1,979,139.58 — CGEY/Highmark/CVS rolled in.
    ( 8, 2026, "Savings",     "PNC",                       138_706.58),
    ( 8, 2026, "Brokerage",   "Charles Schwab",            751_524.68),
    ( 8, 2026, "Brokerage",   "IBM Stock",                 423_569.56),
    ( 8, 2026, "Roth",        "Sarah Roth IRA",            255_785.16),
    ( 8, 2026, "Roth",        "Tom Roth IRA",               54_195.00),
    ( 8, 2026, "Roth",        "IBM 401k Roth",             488_505.39),
    ( 8, 2026, "Traditional", "Sarah IRA",               1_979_139.58),
    ( 8, 2026, "Traditional", "IBM 401K",                3_876_363.05),
    ( 8, 2026, "Traditional", "HM Pension",                107_000.00),
    ( 8, 2026, "Traditional", "IBM Pension (new)",          38_238.82),
    ( 8, 2026, "Traditional", "IBM Pension",                81_383.23),

    # ── September 2026 ──────────────────────────────────────────────
    ( 9, 2026, "Savings",     "PNC",                       172_009.46),
    ( 9, 2026, "Brokerage",   "Charles Schwab",            820_423.65),
    ( 9, 2026, "Brokerage",   "IBM Stock",                 326_309.51),
    ( 9, 2026, "Roth",        "Sarah Roth IRA",            245_311.00),
    ( 9, 2026, "Roth",        "Tom Roth IRA",               54_289.69),
    ( 9, 2026, "Roth",        "IBM 401k Roth",             493_328.78),
    ( 9, 2026, "Traditional", "Sarah IRA",               1_982_471.77),
    ( 9, 2026, "Traditional", "IBM 401K",                3_882_381.28),
    ( 9, 2026, "Traditional", "HM Pension",                107_000.00),
    ( 9, 2026, "Traditional", "IBM Pension (new)",          40_229.56),
    ( 9, 2026, "Traditional", "IBM Pension",                81_695.33),

    # ── October 2026 ────────────────────────────────────────────────
    (10, 2026, "Savings",     "PNC",                       127_238.20),
    (10, 2026, "Brokerage",   "Charles Schwab",            847_222.59),
    (10, 2026, "Brokerage",   "IBM Stock",                 371_918.47),
    (10, 2026, "Roth",        "Sarah Roth IRA",            237_866.20),
    (10, 2026, "Roth",        "Tom Roth IRA",               56_066.98),
    (10, 2026, "Roth",        "IBM 401k Roth",             487_033.10),
    (10, 2026, "Traditional", "Sarah IRA",               1_981_578.80),
    (10, 2026, "Traditional", "IBM 401K",                3_815_017.52),
    (10, 2026, "Traditional", "HM Pension",                107_000.00),
    (10, 2026, "Traditional", "IBM Pension (new)",          41_471.05),
    (10, 2026, "Traditional", "IBM Pension",                82_008.63),
]


def build_rows(data: list[tuple]) -> pd.DataFrame:
    """Convert the flat tuples into a portfolio.db-compatible DataFrame."""
    records = []
    for month, year, account_type, account_name, total_value in data:
        records.append({
            "month":              month,
            "year":               year,
            "account_name":       account_name,
            "account_type":       account_type,
            "owner":              "",
            # Symbol encodes the account type so each row has a unique symbol
            # within its account_name, and CASH-priced rows don't go to Yahoo.
            "symbol":             "CASH",
            "name":               f"Historical snapshot — {account_type}",
            "sector":             "MF:Cash",
            "qty":                float(total_value),
            "purchase_price":     1.0,
            "end_of_month_price": 1.0,   # stored price = $1 → market_value = qty
            "purchase_date":      f"{year}-{month:02d}-01",
        })
    return pd.DataFrame(records, columns=HOLDINGS_COLUMNS)


def main() -> None:
    parser = argparse.ArgumentParser(description="Import historical net worth snapshots.")
    parser.add_argument("--dry-run", action="store_true", help="Print rows without writing.")
    args = parser.parse_args()

    df = build_rows(HISTORICAL_DATA)

    if df.empty:
        print("No data to import — HISTORICAL_DATA is empty.")
        return

    # Summary by month
    summary = (
        df.groupby(["year", "month"])["qty"]
        .sum()
        .reset_index()
        .rename(columns={"qty": "total_net_worth"})
        .sort_values(["year", "month"])
    )

    print("\nMonths to import:")
    print("-" * 45)
    for _, row in summary.iterrows():
        import calendar
        month_name = calendar.month_name[int(row["month"])]
        print(f"  {month_name} {int(row['year'])}: ${row['total_net_worth']:>14,.2f}")
    print("-" * 45)
    print(f"  Total rows : {len(df)}")

    if args.dry_run:
        print("\n[DRY RUN] No data written. Remove --dry-run to commit.")
        print("\nRow preview:")
        print(df[["month", "year", "account_type", "account_name", "qty"]].to_string(index=False))
        return

    n = db_upsert(df)
    print(f"\n✅  Inserted/replaced {n} rows into portfolio.db")
    print("   Run the dashboard and refresh to see the updated net worth trend.")


if __name__ == "__main__":
    main()
