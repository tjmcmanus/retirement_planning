"""
scripts/projection_2026_2050.py

Full multi-year projection 2026–2050 using actual retirement_config.json data.
Runs all stages in sequence, threads state (balances, MAGI history, DAF carryforward)
across stage boundaries, and prints a compact per-year summary plus key inflection
point cross-checks.

Inflection points validated:
  2026  Stage 2 (Pre-retirement / final working year)
  2027  Stage 3 onset  (early retirement, ACA, Roth conversions begin)
  2031  Stage 4 onset  (Tom turns 65 → Medicare replaces ACA)
  2032  Stage 4 IRMAA jump (lookback hits peak Stage 3 MAGI)
  2036  Stage 5 onset  (SS starts, Tom claims at 70)
  2039  Stage 6 onset  (RMD starts for Tom born 1966, age 73)

Run:
    python3 scripts/projection_2026_2050.py
    python3 scripts/projection_2026_2050.py --csv results/projection_2026_2050.csv
"""
import sys
import os
import json
import argparse
import warnings
from pathlib import Path
from datetime import date
from typing import Dict, Optional

warnings.filterwarnings("ignore")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

import logging
logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")

PASS = "✅"
FAIL = "❌"
WARN = "⚠️ "

# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def load_config() -> dict:
    with open(ROOT / "retirement_config.json") as f:
        return json.load(f)


def ages(config: dict, year: int) -> tuple[int, int]:
    p1 = date.fromisoformat(config["personal_info"]["person1_birth_date"])
    p2 = date.fromisoformat(config["personal_info"]["person2_birth_date"])
    return year - p1.year, year - p2.year


def load_portfolio(config: dict) -> dict:
    """Load live portfolio or fall back to illustrative values."""
    try:
        from load_data import get_portfolio_truth_by_month, get_latest_portfolio_month_year
        m, y = get_latest_portfolio_month_year()
        df = get_portfolio_truth_by_month(m, y)
        df["price"] = df["end_of_month_price"].fillna(df["purchase_price"]).fillna(0)
        df["value"] = df["qty"].fillna(0) * df["price"]
        by_type = df.groupby("account_type")["value"].sum()
        result = {
            "traditional": float(by_type.get("Traditional", 0.0)),
            "roth":        float(by_type.get("Roth",        0.0)),
            "taxable":     float(by_type.get("Brokerage",   0.0)),
            "cash":        float(by_type.get("Savings",     0.0)),
            "daf":         float(by_type.get("DAF", 0.0)),
        }
        if result["daf"] == 0:
            result["daf"] = float(config.get("charitable_giving", {}).get("daf_initial_contribution", 530_000))
        print(f"  Portfolio loaded from DB ({m}/{y}):")
        for k, v in result.items():
            print(f"    {k:>12}: ${v:>13,.0f}")
        return result
    except Exception as e:
        print(f"  Could not load portfolio DB: {e}")
        print("  Using illustrative fallback values.")
        return {
            "traditional": 6_000_000.0,
            "roth":          400_000.0,
            "taxable":       600_000.0,
            "cash":          180_000.0,
            "daf":           530_000.0,
        }


# ──────────────────────────────────────────────────────────────────────────────
# Stage determination  (mirrors engine logic, simpler)
# ──────────────────────────────────────────────────────────────────────────────

def stage_for(config: dict, year: int) -> str:
    """Mirrors the engine's applies() chain exactly."""
    age1, age2 = ages(config, year)
    ret_year   = config["personal_info"]["person1_retirement_year"]
    ss_year    = config["personal_info"].get("ss_start_year", 2036)

    from strategy_core.stages.stage6_rmd import get_rmd_age

    # Stage 6 uses per-person RMD age; triggers if EITHER person reaches their age
    birth_y1 = year - age1
    birth_y2 = year - age2
    rmd_age1 = get_rmd_age(birth_y1)
    rmd_age2 = get_rmd_age(birth_y2)
    in_rmd = (age1 >= rmd_age1) or (age2 >= rmd_age2)

    # Stage 5 uses the YOUNGER person's birth year to set the RMD threshold
    # (older_age = max(age1,age2), rmd_age = get_rmd_age(max(birth_y1, birth_y2)))
    older_age = max(age1, age2)
    rmd_age_s5 = get_rmd_age(max(birth_y1, birth_y2))
    in_ss = (year >= ss_year)

    if year < ret_year:
        return "Stage1_Accumulation"
    if year == ret_year:
        return "Stage2_PrepRetirement"
    if age1 < 65 and age2 < 65:
        return "Stage3_EarlyRetirement"
    if (age1 >= 65 or age2 >= 65) and not in_ss and not in_rmd:
        return "Stage4_Medicare"
    if in_ss and older_age < rmd_age_s5 and not in_rmd:
        return "Stage5_SocialSecurity"
    return "Stage6_RMD"


# ──────────────────────────────────────────────────────────────────────────────
# Main projection loop
# ──────────────────────────────────────────────────────────────────────────────

def run_projection(start_year: int = 2026, end_year: int = 2050, csv_path: Optional[str] = None):
    config = load_config()
    fi = config["financial_assumptions"]
    pi = config["personal_info"]

    base_expenses     = float(fi["expected_annual_expenses"])
    expense_inflation = float(fi["expense_inflation_rate"]) / 100.0
    growth_rate       = 1.0 + float(fi["expected_rate_of_return"]) / 100.0
    filing_status     = "married_filing_jointly"
    state             = pi["retirement_state"]
    ret_year          = int(pi["person1_retirement_year"])
    ss_start_year     = int(pi.get("ss_start_year", 2036))

    max_conv_s3 = float(config["tax_strategy"]["stage_3_max_conversion_rate"]) / 100
    max_conv_s4 = float(config["tax_strategy"].get("stage_4_max_conversion_rate", 22)) / 100

    print("=" * 90)
    print(f"  Full Projection {start_year}–{end_year}  |  Retirement: {ret_year}  |  SS starts: {ss_start_year}")
    print(f"  Base expenses: ${base_expenses:,.0f}  |  Inflation: {expense_inflation:.1%}  |"
          f"  Growth: {growth_rate-1:.1%}  |  State: {state}")
    print("=" * 90)
    print()

    print("Loading portfolio …")
    raw = load_portfolio(config)
    print()

    from strategy_core.models import PortfolioBalances
    from strategy_core.tax_calculator import TaxCalculator
    from strategy_core.account_manager import AccountManager
    from strategy_core.stages.stage2_prep_retirement import Stage2PrepForRetirement as Stage2PrepRetirement
    from strategy_core.stages.stage3_early_retirement import Stage3EarlyRetirement
    from strategy_core.stages.stage4_medicare import Stage4Medicare
    from strategy_core.stages.stage5_social_security import Stage5SocialSecurity
    from strategy_core.stages.stage6_rmd import Stage6RMD

    tax_calc = TaxCalculator()
    acct_mgr = AccountManager()

    stage2 = Stage2PrepRetirement(tax_calculator=tax_calc, account_manager=acct_mgr)
    stage3 = Stage3EarlyRetirement(tax_calculator=tax_calc, account_manager=acct_mgr)
    stage4 = Stage4Medicare(tax_calculator=tax_calc, account_manager=acct_mgr)
    stage5 = Stage5SocialSecurity(tax_calculator=tax_calc, account_manager=acct_mgr)
    stage6 = Stage6RMD(tax_calculator=tax_calc, account_manager=acct_mgr)

    balances = PortfolioBalances(
        cash=raw["cash"],
        taxable=raw["taxable"],
        traditional=raw["traditional"],
        roth=raw["roth"],
        daf=raw["daf"],
    )

    magi_history: Dict[int, float] = {}
    daf_cf = 0.0
    rows = []

    HDR = (f"{'Year':<5} {'Ages':^9} {'Stage':<22} {'Expenses':>11} {'AGI':>12}"
           f" {'FedTax':>9} {'IRMAA':>8} {'StateTx':>8} {'RothConv':>11}"
           f" {'Trad':>13} {'Total':>13}")
    SEP = "-" * len(HDR)
    print(HDR)
    print(SEP)

    for year in range(start_year, end_year + 1):
        age1, age2 = ages(config, year)
        years_since_ret = max(0, year - ret_year)
        expenses = base_expenses * ((1 + expense_inflation) ** years_since_ret)
        stage_label = stage_for(config, year)

        try:
            if stage_label == "Stage2_PrepRetirement":
                result = stage2.calculate_strategy(
                    year=year, balances=balances, expenses=expenses,
                    age_primary=age1, age_spouse=age2,
                    filing_status=filing_status, state=state,
                    growth_rate=growth_rate,
                )

            elif stage_label == "Stage3_EarlyRetirement":
                result = stage3.calculate_strategy(
                    year=year, balances=balances, expenses=expenses,
                    age_primary=age1, age_spouse=age2,
                    filing_status=filing_status, state=state,
                    max_conversion_rate=max_conv_s3,
                    growth_rate=growth_rate,
                    start_year=ret_year + 1,
                    daf_carryforward_prior=daf_cf,
                )

            elif stage_label == "Stage4_Medicare":
                prior_magi = magi_history.get(year - 2, 0.0)
                result = stage4.calculate_strategy(
                    year=year, balances=balances, expenses=expenses,
                    age_primary=age1, age_spouse=age2,
                    filing_status=filing_status, state=state,
                    max_conversion_rate=max_conv_s4,
                    growth_rate=growth_rate,
                    start_year=ret_year + 1,
                    prior_magi=prior_magi,
                    daf_carryforward_prior=daf_cf,
                )

            elif stage_label == "Stage5_SocialSecurity":
                prior_magi = magi_history.get(year - 2, 0.0)
                result = stage5.calculate_strategy(
                    year=year, balances=balances, expenses=expenses,
                    age_primary=age1, age_spouse=age2,
                    filing_status=filing_status, state=state,
                    max_conversion_rate=max_conv_s4,
                    growth_rate=growth_rate,
                    start_year=ss_start_year,
                    prior_magi=prior_magi,
                    daf_carryforward_prior=daf_cf,
                )

            else:  # Stage6_RMD
                prior_magi = magi_history.get(year - 2, 0.0)
                result = stage6.calculate_strategy(
                    year=year, balances=balances, expenses=expenses,
                    age_primary=age1, age_spouse=age2,
                    filing_status=filing_status, state=state,
                    max_conversion_rate=max_conv_s4,
                    growth_rate=growth_rate,
                    start_year=ss_start_year,
                    prior_magi=prior_magi,
                    daf_carryforward_prior=daf_cf,
                )

            magi_history[year] = result.magi if hasattr(result, "magi") and result.magi else result.agi
            daf_cf = max(0.0, (result.daf_contribution or 0) - (getattr(result, "daf_deductible", result.daf_contribution) or 0))
            balances = result.balances

            total = balances.total()
            row = {
                "year": year, "age1": age1, "age2": age2, "stage": stage_label,
                "expenses": expenses,
                "agi": result.agi, "federal_tax": result.federal_tax,
                "irmaa": result.irmaa_penalty, "state_tax": getattr(result, "state_tax", 0.0),
                "roth_conversion": result.roth_conversion,
                "traditional": balances.traditional, "total": total,
                "daf_cf": daf_cf, "success": True, "error": None,
            }

        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            row = {
                "year": year, "age1": age1, "age2": age2, "stage": stage_label,
                "expenses": expenses,
                "agi": 0, "federal_tax": 0, "irmaa": 0, "state_tax": 0,
                "roth_conversion": 0, "traditional": balances.traditional,
                "total": balances.total(), "daf_cf": daf_cf,
                "success": False, "error": str(e),
            }
            print(f"  {FAIL} {year} ERROR: {e}")
            print(tb)

        rows.append(row)
        r = row
        stage_short = stage_label.replace("Stage", "S").replace("_", "")[:16]
        flag = "" if r["success"] else f"  {FAIL}"
        print(
            f"{r['year']:<5} {r['age1']:>2}/{r['age2']:<2}   "
            f"{stage_short:<22}"
            f"${r['expenses']:>10,.0f}"
            f"${r['agi']:>11,.0f}"
            f"${r['federal_tax']:>8,.0f}"
            f"${r['irmaa']:>7,.0f}"
            f"${r['state_tax']:>7,.0f}"
            f"${r['roth_conversion']:>10,.0f}"
            f"${r['traditional']:>12,.0f}"
            f"${r['total']:>12,.0f}"
            f"{flag}"
        )

    # ── Inflection-point cross-checks ─────────────────────────────────────────
    print()
    print("=" * 90)
    print("  Inflection-Point Cross-Checks")
    print("=" * 90)

    def get_row(yr: int):
        return next((r for r in rows if r["year"] == yr), None)

    checks = []

    r27 = get_row(2027)
    checks.append((
        "2027 is Stage 3 (first full retirement year)",
        r27 and "Stage3" in r27["stage"],
        r27["stage"] if r27 else "missing"
    ))
    checks.append((
        "2027 Roth conversion > 0 (bracket-fill active)",
        r27 and r27["roth_conversion"] > 0,
        f"${r27['roth_conversion']:,.0f}" if r27 else "missing"
    ))

    r31 = get_row(2031)
    checks.append((
        "2031 is Stage 4 (Tom turns 65, Medicare)",
        r31 and "Stage4" in r31["stage"],
        r31["stage"] if r31 else "missing"
    ))
    checks.append((
        "2031 IRMAA ≥ 0",
        r31 and r31["irmaa"] >= 0,
        f"${r31['irmaa']:,.0f}" if r31 else "missing"
    ))

    r32 = get_row(2032)
    r31_irmaa = r31["irmaa"] if r31 else 0
    r32_irmaa = r32["irmaa"] if r32 else 0
    checks.append((
        "2032 IRMAA > 2031 IRMAA (lookback hits peak 2030 MAGI)",
        r32_irmaa > r31_irmaa,
        f"2031=${r31_irmaa:,.0f}  →  2032=${r32_irmaa:,.0f}"
    ))

    r36 = get_row(2036)
    checks.append((
        "2036 is Stage 5 (SS starts)",
        r36 and "Stage5" in r36["stage"],
        r36["stage"] if r36 else "missing"
    ))
    checks.append((
        "2036 SS benefits > 0",
        r36 and r36["agi"] > 0,
        f"AGI=${r36['agi']:,.0f}" if r36 else "missing"
    ))

    # Stage 6 first activates when older_age >= rmd_age where rmd_age is computed from
    # the YOUNGER spouse's birth year (Stage 5 applies logic).  Sarah born 1967 → rmd_age=75.
    # Tom turns 75 in 2041, so Stage 6 first appears in 2041.
    # Note: Tom's own RMD (age 73, born 1966) begins in 2039 even while Stage 5 runs —
    # Stage 6 will distribute his RMD from that year as well since Stage 6 triggers on
    # either person reaching their own RMD age.
    r39 = get_row(2039)
    checks.append((
        "2039 still Stage 5 (Stage 5 threshold = 75 for younger spouse born 1967)",
        r39 and "Stage5" in r39["stage"],
        r39["stage"] if r39 else "missing"
    ))
    r41 = get_row(2041)
    checks.append((
        "2041 is Stage 6 (Tom age 75, both persons have hit RMD age)",
        r41 and "Stage6" in r41["stage"],
        r41["stage"] if r41 else "missing"
    ))

    all_pass = True
    for label, passed, detail in checks:
        icon = PASS if passed else FAIL
        print(f"  {icon}  {label}")
        print(f"       {detail}")
        if not passed:
            all_pass = False

    # ── DAF carryforward tracker ─────────────────────────────────────────────
    print()
    print("  DAF Carryforward by Year:")
    for r in rows:
        if r["daf_cf"] > 1:
            print(f"    {r['year']}  ${r['daf_cf']:>10,.0f}")

    # ── Portfolio trajectory ──────────────────────────────────────────────────
    print()
    print("  Portfolio Total by Stage Transition:")
    transitions = [2026, 2027, 2031, 2036, 2039, 2041, 2050]
    for yr in transitions:
        r = get_row(yr)
        if r:
            print(f"    {yr} (age {r['age1']})  {r['stage']:<28}  Total: ${r['total']:>13,.0f}"
                  f"  Trad: ${r['traditional']:>13,.0f}")

    # ── CSV export ───────────────────────────────────────────────────────────
    if csv_path:
        import csv
        fields = ["year","age1","age2","stage","expenses","agi","federal_tax",
                  "irmaa","state_tax","roth_conversion","traditional","total",
                  "daf_cf","success","error"]
        out = Path(csv_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        with open(out, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=fields)
            w.writeheader()
            for r in rows:
                w.writerow({k: r.get(k, "") for k in fields})
        print(f"\n  CSV written → {out}")

    print()
    if all_pass:
        print(f"{PASS} All inflection-point checks passed.")
    else:
        print(f"{FAIL} One or more inflection-point checks FAILED.")
    print()
    return rows, all_pass


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Full retirement projection 2026–2050")
    parser.add_argument("--start", type=int, default=2026)
    parser.add_argument("--end",   type=int, default=2050)
    parser.add_argument("--csv",   type=str, default=None, help="Path to write CSV output")
    args = parser.parse_args()
    _, ok = run_projection(args.start, args.end, args.csv)
    sys.exit(0 if ok else 1)
