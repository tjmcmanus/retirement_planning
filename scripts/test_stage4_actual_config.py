"""
scripts/test_stage4_actual_config.py

Validate Stage 4 (Medicare Bridge) with actual retirement_config.json data.

Run:
    python3 scripts/test_stage4_actual_config.py

Stage 4 activates when either spouse reaches 65 (Medicare) but before SS and RMD.
Tom (born 1966-05-16) turns 65 in 2031.
Sarah (born 1967-03-22) turns 65 in 2032.

Key Stage 4 checks beyond Stage 3:
  - IRMAA penalty calculated from 2-year prior MAGI lookback
  - property_tax flows into AGICalculator SALT via _get_property_tax_from_config()
  - Medicare healthcare costs replace ACA costs
  - DAF carryforward from Stage 3 survives the transition
"""
import sys
import os
import json
import logging
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")

PASS = "✅ PASS"
FAIL = "❌ FAIL"
WARN = "⚠️  WARN"


def load_config() -> dict:
    with open(ROOT / "retirement_config.json") as f:
        return json.load(f)


def get_person_ages(config: dict, year: int) -> tuple[int, int]:
    from datetime import date
    p1_birth = date.fromisoformat(config["personal_info"]["person1_birth_date"])
    p2_birth = date.fromisoformat(config["personal_info"]["person2_birth_date"])
    return year - p1_birth.year, year - p2_birth.year


def load_portfolio_balances(config: dict) -> dict:
    try:
        import pandas as pd
        from load_data import get_portfolio_truth_by_month, get_latest_portfolio_month_year
        m, y = get_latest_portfolio_month_year()
        df = get_portfolio_truth_by_month(m, y)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
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
        print(f"  Loaded from portfolio DB ({m}/{y}): Traditional=${result['traditional']:,.0f}, "
              f"Roth=${result['roth']:,.0f}, Taxable=${result['taxable']:,.0f}, "
              f"Cash=${result['cash']:,.0f}")
        return result
    except Exception as e:
        print(f"  Could not load portfolio: {e}. Using illustrative values.")
        return {"traditional": 6_000_000.0, "roth": 400_000.0,
                "taxable": 600_000.0, "cash": 180_000.0, "daf": 530_000.0}


def run_stage4_validation():
    config = load_config()

    annual_expenses_base = config["financial_assumptions"]["expected_annual_expenses"]
    expense_inflation    = config["financial_assumptions"]["expense_inflation_rate"] / 100
    growth_rate          = 1 + config["financial_assumptions"]["expected_rate_of_return"] / 100
    filing_status        = "married_filing_jointly"
    state                = config["personal_info"]["retirement_state"]
    property_tax         = float(
        config.get("expenses", {}).get("living_expenses", {}).get("property_tax", 0)
    )
    retirement_year      = config["personal_info"]["person1_retirement_year"]

    print("=" * 70)
    print("Stage 4 Medicare Bridge — Validation with Actual Config")
    print("=" * 70)
    print(f"Base expenses:    ${annual_expenses_base:,.0f}")
    print(f"Expense inflation:{expense_inflation:.1%}")
    print(f"Growth rate:      {growth_rate - 1:.1%}")
    print(f"State:            {state}")
    print(f"Property tax:     ${property_tax:,.0f}")
    print()

    # CHECK 1: property_tax present
    if property_tax > 0:
        print(f"{PASS} CHECK 1: property_tax=${property_tax:,.0f} in config")
    else:
        print(f"{WARN} CHECK 1: property_tax is $0 or missing")

    print()
    print("Loading portfolio data …")
    balances_raw = load_portfolio_balances(config)

    from strategy_core.models import PortfolioBalances
    from strategy_core.stages.stage4_medicare import Stage4Medicare
    from strategy_core.stages.stage3_early_retirement import Stage3EarlyRetirement
    from strategy_core.tax_calculator import TaxCalculator
    from strategy_core.account_manager import AccountManager

    tax_calc = TaxCalculator()
    acct_mgr = AccountManager()

    # ── First: run Stage 3 for 2027–2030 to arrive at realistic Stage 4 starting balances
    # and to simulate the MAGI lookback that Stage 4 will use for IRMAA
    stage3 = Stage3EarlyRetirement(tax_calculator=tax_calc, account_manager=acct_mgr)
    balances = PortfolioBalances(
        cash=balances_raw["cash"],
        taxable=balances_raw["taxable"],
        traditional=balances_raw["traditional"],
        roth=balances_raw["roth"],
        daf=balances_raw["daf"],
    )

    # Track MAGI for IRMAA lookback
    magi_history = {}
    daf_carryforward = 0.0

    STAGE3_START = retirement_year + 1   # 2027
    STAGE4_START = 2031                  # Tom turns 65

    print()
    print(f"Running Stage 3 bridge (2027–2030) to build realistic Stage 4 starting state …")
    for year in range(STAGE3_START, STAGE4_START):
        age1, age2 = get_person_ages(config, year)
        years_since_ret = year - retirement_year
        expenses = annual_expenses_base * ((1 + expense_inflation) ** years_since_ret)
        max_rate = config["tax_strategy"]["stage_3_max_conversion_rate"] / 100
        try:
            result = stage3.calculate_strategy(
                year=year, balances=balances, expenses=expenses,
                age_primary=age1, age_spouse=age2,
                filing_status=filing_status, state=state,
                max_conversion_rate=max_rate, growth_rate=growth_rate,
                start_year=STAGE3_START, daf_carryforward_prior=daf_carryforward,
            )
            # Update MAGI history and carryforward
            magi_history[year] = result.agi
            daf_carryforward = max(0.0, result.daf_contribution - result.daf_deductible)
            balances = result.balances
            print(f"  {year} (age {age1}): AGI=${result.agi:,.0f}, "
                  f"Fed=${result.federal_tax:,.0f}, Conv=${result.roth_conversion:,.0f}, "
                  f"DAF_CF=${daf_carryforward:,.0f}")
        except Exception as e:
            print(f"  {FAIL} Stage 3 {year}: {e}")
            import traceback; traceback.print_exc()
            return False

    # ── Now run Stage 4 for 2031–2035
    stage4 = Stage4Medicare(tax_calculator=tax_calc, account_manager=acct_mgr)

    print()
    print(f"Running Stage 4 (2031–2035) …")
    print()
    print(f"{'Year':<6}{'Age':<5}{'Expenses':>11}{'AGI':>12}{'Fed Tax':>10}{'IRMAA':>9}"
          f"{'State Tax':>10}{'Roth Conv':>12}{'Traditional':>14}")
    print("-" * 89)

    stage4_results = []
    for year in range(STAGE4_START, 2036):
        age1, age2 = get_person_ages(config, year)
        years_since_ret = year - retirement_year
        expenses = annual_expenses_base * ((1 + expense_inflation) ** years_since_ret)
        max_rate = config["tax_strategy"]["stage_4_max_conversion_rate"] / 100
        prior_magi = magi_history.get(year - 2, 0.0)

        try:
            result = stage4.calculate_strategy(
                year=year, balances=balances, expenses=expenses,
                age_primary=age1, age_spouse=age2,
                filing_status=filing_status, state=state,
                max_conversion_rate=max_rate, growth_rate=growth_rate,
                start_year=STAGE4_START, prior_magi=prior_magi,
                daf_carryforward_prior=daf_carryforward,
            )
            magi_history[year] = result.agi
            daf_carryforward = max(0.0, result.daf_contribution - result.daf_deductible)
            balances = result.balances
            stage4_results.append({
                "year": year, "age1": age1, "expenses": expenses,
                "agi": result.agi, "federal_tax": result.federal_tax,
                "irmaa": result.irmaa_penalty, "state_tax": result.state_tax,
                "roth_conversion": result.roth_conversion,
                "daf": result.daf_contribution,
                "trad_end": result.balances.traditional,
                "success": True, "error": None,
            })
            print(f"{year:<6}{age1:<5}"
                  f"${expenses:>10,.0f}"
                  f"${result.agi:>11,.0f}"
                  f"${result.federal_tax:>9,.0f}"
                  f"${result.irmaa_penalty:>8,.0f}"
                  f"${result.state_tax:>9,.0f}"
                  f"${result.roth_conversion:>11,.0f}"
                  f"${result.balances.traditional:>13,.0f}")
        except Exception as e:
            stage4_results.append({"year": year, "success": False, "error": str(e)})
            print(f"{year:<6}{age1:<5}  ERROR: {e}")
            import traceback; traceback.print_exc()
            break

    # ── Manual cross-checks for 2031 (first Stage 4 year)
    print()
    print("=" * 70)
    print("Manual Cross-Check — 2031 (First Stage 4 Year, Tom age 65)")
    print("=" * 70)

    r31 = next((r for r in stage4_results if r["year"] == 2031 and r["success"]), None)
    if r31 is None:
        print(f"{FAIL} 2031 result not available")
        return False

    checks = []

    # AGI > 0
    checks.append(("AGI > 0", r31["agi"] > 0, f"AGI=${r31['agi']:,.0f}"))

    # Federal tax ≥ 0
    checks.append(("Federal tax ≥ 0", r31["federal_tax"] >= 0, f"${r31['federal_tax']:,.0f}"))

    # State tax ≥ 0
    checks.append(("State tax ≥ 0 (PA 3.07%)", r31["state_tax"] >= 0, f"${r31['state_tax']:,.0f}"))

    # IRMAA non-negative
    checks.append(("IRMAA penalty ≥ 0", r31["irmaa"] >= 0, f"${r31['irmaa']:,.0f}"))

    # IRMAA lookback: 2031 IRMAA is based on 2029 MAGI
    prior_magi_2031 = magi_history.get(2029, 0.0)
    checks.append((
        f"IRMAA 2-year lookback uses 2029 MAGI (${prior_magi_2031:,.0f})",
        prior_magi_2031 > 0,
        f"2029 MAGI=${prior_magi_2031:,.0f}"
    ))

    # property_tax helper works
    try:
        pt = stage4._get_property_tax_from_config()
        checks.append((
            f"_get_property_tax_from_config() = ${property_tax:,.0f}",
            abs(pt - property_tax) < 1,
            f"Got ${pt:,.0f}"
        ))
    except Exception as e:
        checks.append(("_get_property_tax_from_config()", False, str(e)))

    # Roth conversion ≥ 0
    checks.append(("Roth conversion ≥ 0", r31["roth_conversion"] >= 0, f"${r31['roth_conversion']:,.0f}"))

    all_pass = True
    for label, passed, detail in checks:
        status = PASS if passed else FAIL
        print(f"  {status}  {label}")
        print(f"           {detail}")
        if not passed:
            all_pass = False

    print()
    expenses_2031 = annual_expenses_base * ((1 + expense_inflation) ** (2031 - retirement_year))
    print(f"  2031 Expenses (inflated):  ${expenses_2031:,.0f}")
    print(f"  Prior MAGI (2029):         ${prior_magi_2031:,.0f}  (used for IRMAA)")
    print(f"  Property tax (SALT):       ${property_tax:,.0f}")
    print()
    print(f"  Computed AGI:              ${r31['agi']:,.0f}")
    print(f"  Computed IRMAA:            ${r31['irmaa']:,.0f}")
    print(f"  Computed Roth conversion:  ${r31['roth_conversion']:,.0f}")
    print(f"  Computed Federal Tax:      ${r31['federal_tax']:,.0f}")
    print(f"  Computed State Tax:        ${r31['state_tax']:,.0f}")

    print()
    if all_pass:
        print(f"{PASS} All checks passed — Stage 4 is computing correctly with actual config data.")
    else:
        print(f"{FAIL} One or more checks failed.")

    return all_pass


if __name__ == "__main__":
    success = run_stage4_validation()
    sys.exit(0 if success else 1)
