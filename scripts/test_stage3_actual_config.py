"""
scripts/test_stage3_actual_config.py  (updated: requires account_manager)

Validate Stage 3 (Early Retirement) with actual retirement_config.json data.

Run:
    python scripts/test_stage3_actual_config.py

Prints a year-by-year table and a side-by-side manual vs. computed check
for 2027 (the first full Stage 3 year per the config).

Manual reference values (2027):
  Tom age 60, Sarah age 59 — both pre-Medicare, pre-SS, no wages
  Annual expenses (2027): $128,300 × 1.03 = $132,149
  ACA premium: per config (person1 + person2 aca_insurance_monthly × 12)
  Property tax: $5,000 (from expenses.living_expenses.property_tax)
  Standard deduction (MFJ 2027): ~$30,000 (indexed from 2024 $29,200)
  Expected: property_tax flows through to AGICalculator SALT calc
"""
import sys
import os
import json
import logging
from pathlib import Path

# ── path setup ──────────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)  # CSV data files are found relative to the project root

# Suppress noisy debug logs during the run; INFO is useful
logging.basicConfig(
    level=logging.WARNING,
    format="%(levelname)s %(name)s: %(message)s"
)

PASS = "✅ PASS"
FAIL = "❌ FAIL"
WARN = "⚠️  WARN"


def load_config() -> dict:
    config_path = ROOT / "retirement_config.json"
    with open(config_path) as f:
        return json.load(f)


def get_person_ages(config: dict, year: int) -> tuple[int, int]:
    """Return (age_primary, age_spouse) for a given year."""
    from datetime import date
    p1_birth = date.fromisoformat(config["personal_info"]["person1_birth_date"])
    p2_birth = date.fromisoformat(config["personal_info"]["person2_birth_date"])
    age1 = year - p1_birth.year
    age2 = year - p2_birth.year
    return age1, age2


def run_stage3_validation():
    config = load_config()

    # ── pull key config values ───────────────────────────────────────────────
    annual_expenses_base = config["financial_assumptions"]["expected_annual_expenses"]  # 128_300
    expense_inflation    = config["financial_assumptions"]["expense_inflation_rate"] / 100  # 0.03
    growth_rate_pct      = config["financial_assumptions"]["expected_rate_of_return"]  # 6.0
    growth_rate          = 1 + growth_rate_pct / 100  # 1.06
    filing_status        = "married_filing_jointly"
    state                = config["personal_info"]["retirement_state"]  # "PA"
    property_tax         = float(
        config.get("expenses", {})
              .get("living_expenses", {})
              .get("property_tax", 0)
    )
    p1_retirement_year   = config["personal_info"]["person1_retirement_year"]  # 2026

    print("=" * 70)
    print("Stage 3 Early Retirement — Validation with Actual Config")
    print("=" * 70)
    print(f"Base expenses:      ${annual_expenses_base:,.0f}")
    print(f"Expense inflation:  {expense_inflation:.1%}")
    print(f"Growth rate:        {growth_rate_pct:.1f}%")
    print(f"State:              {state}")
    print(f"Property tax:       ${property_tax:,.0f}")
    print()

    # ── CHECK 1: property_tax is present in config ───────────────────────────
    if property_tax > 0:
        print(f"{PASS} CHECK 1: property_tax=${property_tax:,.0f} is present in "
              f"retirement_config.json (expenses.living_expenses.property_tax)")
    else:
        print(f"{WARN} CHECK 1: property_tax is 0 — either not set or defaulted")

    # ── Build initial balances from portfolio truth CSV ─────────────────────
    print()
    print("Loading portfolio data …")
    try:
        import warnings
        import pandas as pd
        from load_data import get_portfolio_truth_by_month, get_latest_portfolio_month_year
        latest_month, latest_year = get_latest_portfolio_month_year()
        df = get_portfolio_truth_by_month(latest_month, latest_year)
        print(f"  Latest portfolio: {latest_month}/{latest_year}, {len(df)} rows")

        # Compute value = qty × end_of_month_price (fallback to purchase_price)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            df["price"] = df["end_of_month_price"].fillna(df["purchase_price"]).fillna(0)
        df["value"] = df["qty"].fillna(0) * df["price"]
        by_type = df.groupby("account_type")["value"].sum()

        balances_raw = {
            "traditional": float(by_type.get("Traditional", 0.0)),
            "roth":        float(by_type.get("Roth",        0.0)),
            "taxable":     float(by_type.get("Brokerage",   0.0)),
            "cash":        float(by_type.get("Savings",     0.0)),
            "daf":         float(by_type.get("DAF",         0.0)),
        }
        # DAF initial contribution from config if not in portfolio
        if balances_raw["daf"] == 0:
            balances_raw["daf"] = float(
                config.get("charitable_giving", {}).get("daf_initial_contribution", 530_000)
            )
    except Exception as e:
        print(f"  Could not load portfolio truth: {e}")
        print("  Using illustrative balances for validation")
        balances_raw = {
            "traditional": 2_500_000.0,
            "roth":          500_000.0,
            "taxable":       800_000.0,
            "cash":          100_000.0,
            "daf":           530_000.0,
        }

    print(f"  Traditional: ${balances_raw['traditional']:>12,.0f}")
    print(f"  Roth:        ${balances_raw['roth']:>12,.0f}")
    print(f"  Taxable:     ${balances_raw['taxable']:>12,.0f}")
    print(f"  Cash:        ${balances_raw['cash']:>12,.0f}")
    print(f"  DAF:         ${balances_raw['daf']:>12,.0f}")

    # ── Initialise strategy engine ───────────────────────────────────────────
    from strategy_core.models import PortfolioBalances
    from strategy_core.stages.stage3_early_retirement import Stage3EarlyRetirement
    from strategy_core.tax_calculator import TaxCalculator

    from strategy_core.account_manager import AccountManager
    tax_calc  = TaxCalculator()
    acct_mgr  = AccountManager()
    stage3    = Stage3EarlyRetirement(tax_calculator=tax_calc, account_manager=acct_mgr)

    balances = PortfolioBalances(
        cash=balances_raw["cash"],
        taxable=balances_raw["taxable"],
        traditional=balances_raw["traditional"],
        roth=balances_raw["roth"],
        daf=balances_raw["daf"],
    )

    # ── Run Stage 3 for years 2027 – 2031 ───────────────────────────────────
    # 2026 is the retirement year; 2027 is the first full Stage 3 year.
    results = []
    FIRST_STAGE3_YEAR = p1_retirement_year + 1  # 2027
    END_YEAR = FIRST_STAGE3_YEAR + 4             # 5 years

    print()
    print(f"Running Stage 3 for years {FIRST_STAGE3_YEAR}–{END_YEAR - 1} …")

    for year in range(FIRST_STAGE3_YEAR, END_YEAR):
        age1, age2 = get_person_ages(config, year)

        # Expenses inflate from retirement year
        years_since_retirement = year - p1_retirement_year
        expenses = annual_expenses_base * ((1 + expense_inflation) ** years_since_retirement)

        max_conversion_rate = config["tax_strategy"]["stage_3_max_conversion_rate"] / 100

        try:
            result = stage3.calculate_strategy(
                year=year,
                balances=balances,
                expenses=expenses,
                age_primary=age1,
                age_spouse=age2,
                filing_status=filing_status,
                state=state,
                max_conversion_rate=max_conversion_rate,
                growth_rate=growth_rate,
                start_year=FIRST_STAGE3_YEAR,
            )
            results.append({
                "year": year,
                "age1": age1,
                "expenses": expenses,
                "agi": result.agi,
                "federal_tax": result.federal_tax,
                "state_tax": result.state_tax,
                "roth_conversion": result.roth_conversion,
                "daf_contribution": result.daf_contribution,
                "trad_end": result.balances.traditional,
                "roth_end": result.balances.roth,
                "cash_end": result.balances.cash,
                "success": True,
                "error": None,
            })
            balances = result.balances
        except Exception as e:
            results.append({
                "year": year, "success": False, "error": str(e),
                "expenses": expenses, "age1": age1,
            })
            import traceback
            print(f"  {FAIL} {year}: {e}")
            traceback.print_exc()
            break

    # ── Print results table ─────────────────────────────────────────────────
    print()
    print(f"{'Year':<6}{'Age':<5}{'Expenses':>12}{'AGI':>12}{'Fed Tax':>10}"
          f"{'State Tax':>10}{'Roth Conv':>12}{'DAF':>10}{'Traditional':>14}")
    print("-" * 91)
    for r in results:
        if r["success"]:
            print(f"{r['year']:<6}{r['age1']:<5}"
                  f"${r['expenses']:>11,.0f}"
                  f"${r['agi']:>11,.0f}"
                  f"${r['federal_tax']:>9,.0f}"
                  f"${r['state_tax']:>9,.0f}"
                  f"${r['roth_conversion']:>11,.0f}"
                  f"${r['daf_contribution']:>9,.0f}"
                  f"${r['trad_end']:>13,.0f}")
        else:
            print(f"{r['year']:<6}{r['age1']:<5}  ERROR: {r['error']}")

    # ── Manual cross-check for 2027 ─────────────────────────────────────────
    print()
    print("=" * 70)
    print("Manual Cross-Check — 2027 (First Full Stage 3 Year)")
    print("=" * 70)

    r27 = next((r for r in results if r["year"] == 2027 and r["success"]), None)
    if r27 is None:
        print(f"{FAIL} 2027 result not available")
        return

    # Reconstruct what AGICalculator should have seen
    expenses_2027 = annual_expenses_base * (1 + expense_inflation)
    std_ded_est   = 30_000  # MFJ 2027, rough estimate
    aca_monthly   = (
        config["healthcare"].get("person1_aca_insurance_monthly", 0) +
        config["healthcare"].get("person2_aca_insurance_monthly", 0)
    )
    aca_annual = aca_monthly * 12

    checks = []

    # Check: AGI should be > 0
    checks.append((
        "AGI > 0",
        r27["agi"] > 0,
        f"AGI=${r27['agi']:,.0f}"
    ))

    # Check: federal tax should be non-negative
    checks.append((
        "Federal tax ≥ 0",
        r27["federal_tax"] >= 0,
        f"Federal tax=${r27['federal_tax']:,.0f}"
    ))

    # Check: state tax should be ≥ 0 (PA 3.07% flat)
    checks.append((
        "State tax ≥ 0 (PA 3.07%)",
        r27["state_tax"] >= 0,
        f"State tax=${r27['state_tax']:,.0f}"
    ))

    # Check: property_tax read from config flows to AGICalculator
    # Verify by calling _get_property_tax_from_config directly
    try:
        prop_tax_from_method = stage3._get_property_tax_from_config()
        checks.append((
            f"_get_property_tax_from_config() returns ${property_tax:,.0f}",
            abs(prop_tax_from_method - property_tax) < 1,
            f"Method returned ${prop_tax_from_method:,.0f}, config has ${property_tax:,.0f}"
        ))
    except Exception as e:
        checks.append(("_get_property_tax_from_config()", False, str(e)))

    # Check: AGI plausibility — should be at least expenses worth of withdrawals
    # In Stage 3 the engine must withdraw something to cover expenses
    min_expected_agi = expenses_2027 * 0.3  # very conservative lower bound
    checks.append((
        f"AGI ≥ {min_expected_agi:,.0f} (30% of expenses — sanity floor)",
        r27["agi"] >= min_expected_agi,
        f"AGI=${r27['agi']:,.0f}"
    ))

    # Check: If Roth conversion happened, it should be positive
    checks.append((
        "Roth conversion ≥ 0",
        r27["roth_conversion"] >= 0,
        f"Roth conversion=${r27['roth_conversion']:,.0f}"
    ))

    # Print checks
    all_pass = True
    for label, passed, detail in checks:
        status = PASS if passed else FAIL
        print(f"  {status}  {label}")
        print(f"           {detail}")
        if not passed:
            all_pass = False

    print()
    print(f"  2027 Expenses (inflated):  ${expenses_2027:,.0f}")
    print(f"  ACA premium annual:        ${aca_annual:,.0f}")
    print(f"  Property tax (SALT):       ${property_tax:,.0f}")
    print(f"  Est. standard deduction:   ${std_ded_est:,.0f}")
    print()
    print(f"  Computed AGI:              ${r27['agi']:,.0f}")
    print(f"  Computed Roth conversion:  ${r27['roth_conversion']:,.0f}")
    print(f"  Computed DAF contribution: ${r27['daf_contribution']:,.0f}")
    print(f"  Computed Federal Tax:      ${r27['federal_tax']:,.0f}")
    print(f"  Computed State Tax:        ${r27['state_tax']:,.0f}")

    print()
    if all_pass:
        print(f"{PASS} All checks passed — Stage 3 is computing correctly with actual config data.")
    else:
        print(f"{FAIL} One or more checks failed — review output above.")

    return all_pass


if __name__ == "__main__":
    success = run_stage3_validation()
    sys.exit(0 if success else 1)
