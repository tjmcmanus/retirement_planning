"""
Example: Using January Bracket-Fill Strategy with YOUR ACTUAL DATA

This script reads your retirement_config.json and calculates your actual
2026 withdrawal plan using the bracket-fill strategy.

Run this to see YOUR numbers, not generic examples.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from strategy_core.withdrawal_orchestrator import JanuaryBracketFillOrchestrator
from strategy_core.roth_conversion_optimizer import RothConversionOptimizer
from strategy_core.sixty_day_rollover import SixtyDayRolloverHandler
from strategy_core.tax_calculator import TaxCalculator
from config import get_config_manager

# ============================================================================
# Load your actual configuration
# ============================================================================

def get_actual_balances_for_year(year):
    """
    Get actual portfolio balances for the year from your portfolio database.
    This is a PLACEHOLDER - you'll need to connect to your actual portfolio_db.py
    
    For now, returning 2026 estimated balances based on your 2026 snapshot.
    """
    # From your Year-to-Year Details screenshot for 2026:
    # These are approximations - please verify against your actual portfolio
    return {
        'traditional': 1800000,  # Total Traditional across all accounts
        'roth': 850000,          # Total Roth across all accounts
        'taxable': 1100000,      # Total Brokerage/Taxable
        'cash': 138772,          # From your screenshot "Cash Start" for 2026
    }

def calculate_aca_costs_for_year(config_mgr, year, age_primary, age_spouse):
    """Calculate ACA premium costs for the year."""
    aca_total = 0
    
    # Person 1 (Tom)
    person1_monthly = config_mgr.get("healthcare", "person1_aca_insurance_monthly", 0)
    person1_aca_start = config_mgr.get("healthcare", "person1_aca_start_age", 62)
    person1_aca_end = config_mgr.get("healthcare", "person1_aca_end_age", 65)
    
    if person1_aca_start <= age_primary < person1_aca_end:
        aca_total += person1_monthly * 12
    
    # Person 2 (Sarah)
    person2_monthly = config_mgr.get("healthcare", "person2_aca_insurance_monthly", 0)
    person2_aca_start = config_mgr.get("healthcare", "person2_aca_start_age", 62)
    person2_aca_end = config_mgr.get("healthcare", "person2_aca_end_age", 65)
    
    if person2_aca_start <= age_spouse < person2_aca_end:
        aca_total += person2_monthly * 12
    
    return aca_total

def example_with_actual_data():
    """
    Calculate your 2026 withdrawal strategy using actual config data.
    """
    
    print("=" * 70)
    print("2026 JANUARY BRACKET-FILL WITHDRAWAL STRATEGY")
    print("Using YOUR ACTUAL Configuration Data")
    print("=" * 70)
    print()
    
    # Initialize components
    tax_calc = TaxCalculator()
    orchestrator = JanuaryBracketFillOrchestrator(
        tax_calculator=tax_calc,
        account_manager=None
    )
    optimizer = RothConversionOptimizer()
    rollover_handler = SixtyDayRolloverHandler()
    config_mgr = get_config_manager()
    
    # ========================================================================
    # STEP 1: Your Actual Situation
    # ========================================================================
    print("\n1. YOUR SITUATION (January 1, 2026)")
    print("-" * 70)
    
    year = 2026
    age_primary = 60  # Tom (born 1966-05-16)
    age_spouse = 59   # Sarah (born 1967-03-22)
    filing_status = 'married_filing_jointly'
    state = config_mgr.get("personal_info", "retirement_state", "PA")
    
    # Get balances from your portfolio
    balances = get_actual_balances_for_year(year)
    
    print(f"  Names: Tom (age {age_primary}) & Sarah (age {age_spouse})")
    print(f"  Filing Status: {filing_status}, State: {state}")
    print(f"\n  Account Balances (2026 estimate):")
    print(f"    Traditional: ${balances['traditional']:,.0f}")
    print(f"    Roth: ${balances['roth']:,.0f}")
    print(f"    Brokerage (Taxable): ${balances['taxable']:,.0f}")
    print(f"    Cash (PNC): ${balances['cash']:,.0f}")
    
    # ========================================================================
    # STEP 2: Your Actual Annual Spending Need
    # ========================================================================
    print("\n2. YOUR ANNUAL SPENDING NEED (2026)")
    print("-" * 70)
    
    # Get base expenses from config
    base_expenses = config_mgr.get("financial_assumptions", "expected_annual_expenses", 133600)
    
    # Calculate ACA costs
    aca_costs = calculate_aca_costs_for_year(config_mgr, year, age_primary, age_spouse)
    
    # Get charitable giving (if applicable in 2026)
    has_daf = config_mgr.get("charitable_giving", "has_daf", False)
    daf_annual = 0
    if has_daf:
        daf_start_age = config_mgr.get("charitable_giving", "daf_contribution_start_age", 61)
        daf_end_age = config_mgr.get("charitable_giving", "daf_contribution_end_age", 75)
        if daf_start_age <= age_primary < daf_end_age:
            daf_annual = config_mgr.get("charitable_giving", "daf_annual_contribution", 0)
    
    # Check for big-ticket items in 2026
    big_ticket = 0
    big_ticket_items = config_mgr.get("expenses", "big_ticket_items", [])
    for item in big_ticket_items:
        if item.get("start_year") <= year <= item.get("end_year"):
            frequency = item.get("frequency_years", 1)
            years_since_start = year - item.get("start_year", year)
            if years_since_start % frequency == 0:
                big_ticket += item.get("amount", 0)
    
    total_expenses = base_expenses + aca_costs + big_ticket
    
    print(f"  Base Living Expenses: ${base_expenses:,.0f}")
    print(f"  ACA Healthcare Costs: ${aca_costs:,.0f}")
    print(f"  Big-Ticket Items (2026): ${big_ticket:,.0f}")
    print(f"  DAF/Charitable Giving: ${daf_annual:,.0f}")
    print(f"  {'─' * 50}")
    print(f"  Total Annual Need (excluding tax): ${total_expenses + daf_annual:,.0f}")
    
    # ========================================================================
    # STEP 3: Calculate Bracket-Fill Withdrawal
    # ========================================================================
    print("\n3. BRACKET-FILL CALCULATION")
    print("-" * 70)
    
    # Note: ACA subsidy optimization only applies if in ACA coverage years
    aca_enabled = aca_costs > 0  # Enable if you have ACA costs
    aca_magi_threshold = None
    if aca_enabled:
        aca_magi_threshold = 74000  # Approximate 400% FPL for 2026
    
    # Calculate 2026 wages (retirement happens mid-year for both)
    # Tom retires Oct 2 → works ~9 months
    # Sarah retires July 15 → works ~6.5 months
    tom_retirement_date = "2026-10-02"
    sarah_retirement_date = "2026-07-15"
    
    tom_months_worked = 9.2  # Oct 2 = early Oct = ~9.2 months
    sarah_months_worked = 6.5  # July 15 = mid-July = ~6.5 months
    
    tom_annual_wages = config_mgr.get("income", "person1_annual_wages", 250000)
    sarah_annual_wages = config_mgr.get("income", "person2_annual_wages", 160000)
    
    tom_2026_wages = tom_annual_wages * (tom_months_worked / 12)
    sarah_2026_wages = sarah_annual_wages * (sarah_months_worked / 12)
    total_2026_wages = tom_2026_wages + sarah_2026_wages
    
    print(f"\n  → IMPORTANT: Wage Income in 2026 (Partial Retirement Year)")
    print(f"    Tom: $250,000/year × {tom_months_worked/12:.1%} = ${tom_2026_wages:,.0f}")
    print(f"    Sarah: $160,000/year × {sarah_months_worked/12:.1%} = ${sarah_2026_wages:,.0f}")
    print(f"    Total 2026 Wages: ${total_2026_wages:,.0f}")
    
    # SSI: Both start at age 70, so no SSI in 2026
    ssi_2026 = 0
    print(f"    Social Security (2026): ${ssi_2026:,.0f} (both start at age 70)")
    
    # Total ordinary income (wages + SSI + dividends/interest, etc.)
    other_ordinary_income = total_2026_wages + ssi_2026
    
    # Debug: Show bracket calculation
    std_ded = tax_calc.calculate_standard_deduction(filing_status, year, age_primary, age_spouse)
    bracket_12_threshold = 100800  # From income_rates.csv for 2026 MFJ
    bracket_available_calc = max(0, bracket_12_threshold - std_ded - other_ordinary_income)
    
    print(f"\n  → DEBUG: 12% Bracket Calculation Details")
    print(f"    Bracket Upper Limit: ${bracket_12_threshold:,.0f}")
    print(f"    Minus: Standard Deduction: ${std_ded:,.0f}")
    print(f"    Minus: Wage Income: ${other_ordinary_income:,.0f}")
    print(f"    = Available Bracket Space: ${bracket_available_calc:,.0f}")
    
    calc = orchestrator.calculate_bracket_fill_withdrawal(
        year=year,
        pnc_balance=balances['cash'],
        annual_expenses=total_expenses + daf_annual,
        filing_status=filing_status,
        age_primary=age_primary,
        age_spouse=age_spouse,
        other_ordinary_income=other_ordinary_income,
        aca_enabled=aca_enabled,
        aca_magi_threshold=aca_magi_threshold,
        stage="Your 2026 Plan"
    )
    
    print(f"\n  PNC Cash On Hand: ${calc.pnc_balance:,.0f}")
    print(f"  Total Annual Spending Need: ${calc.annual_spending_need:,.0f}")
    print(f"  Shortfall (must withdraw): ${calc.shortfall:,.0f}")
    print()
    print(f"  12% Federal Tax Bracket Available: ${calc.bracket_12_available:,.0f}")
    print()
    print(f"  → Traditional Part A (cover shortfall): ${calc.traditional_part_a:,.0f}")
    print(f"  → Traditional Part B (Roth conversion): ${calc.traditional_part_b:,.0f}")
    print(f"  → Total Traditional Withdrawal: ${calc.traditional_total:,.0f}")
    print()
    print(f"  Estimated Tax on Withdrawals: ${calc.estimated_total_tax:,.0f}")
    
    # ========================================================================
    # STEP 4: Optimize Roth Conversion
    # ========================================================================
    print("\n4. ROTH CONVERSION OPTIMIZATION")
    print("-" * 70)
    
    optimization = optimizer.optimize_conversion(
        available_bracket_space=calc.traditional_part_b,
        traditional_balance=balances['traditional'],
        roth_balance=balances['roth'],
        age_primary=age_primary,
        age_spouse=age_spouse,
        year=year,
        has_daf=has_daf,
        daf_annual_contribution=daf_annual if has_daf else 0,
        has_pension_or_other_ordinary_income=False,
        life_expectancy_primary=85,
        life_expectancy_spouse=87,
        betr_max_rate=0.24
    )
    
    print(f"  Optimization Strategy: {optimization.optimization_strategy.upper()}")
    print(f"  Recommended Conversion: ${optimization.conversion_amount:,.0f}")
    print(f"  Future RMD Impact Reduction: ${optimization.future_rmd_impact:,.0f}")
    print()
    print(f"  Strategy Notes:")
    for line in optimization.reasoning.split('\n')[:5]:
        if line.strip():
            print(f"    {line}")
    
    # ========================================================================
    # STEP 5: PNC Cash Flow Analysis
    # ========================================================================
    print("\n5. PNC CASH FLOW ANALYSIS")
    print("-" * 70)
    
    pnc_after_withdrawal = balances['cash'] + calc.traditional_part_a
    pnc_after_spending = pnc_after_withdrawal - (total_expenses + daf_annual)
    
    print(f"  PNC Starting Balance: ${balances['cash']:,.0f}")
    print(f"  + Traditional Part A Deposit: ${calc.traditional_part_a:,.0f}")
    print(f"  = Total Available: ${pnc_after_withdrawal:,.0f}")
    print(f"  - Annual Spending & DAF: ${total_expenses + daf_annual:,.0f}")
    print(f"  = Year-End Projected: ${pnc_after_spending:,.0f}")
    print()
    
    safety_threshold = 50000
    if pnc_after_spending < safety_threshold:
        supplement_needed = safety_threshold - pnc_after_spending
        print(f"  ⚠ WARNING: Projected PNC falls below safety threshold (${safety_threshold:,.0f})")
        print(f"  Mid-year supplementation needed: ${supplement_needed:,.0f} from Brokerage")
    else:
        print(f"  ✓ PNC remains above safety threshold (${safety_threshold:,.0f})")
    
    # ========================================================================
    # STEP 6: 60-Day Rollover (if applicable)
    # ========================================================================
    if optimization.conversion_amount > 0:
        print("\n6. 60-DAY ROLLOVER PLAN")
        print("-" * 70)
        
        rollover_plan = rollover_handler.plan_conversion_with_withholding(
            conversion_amount=optimization.conversion_amount,
            estimated_tax_rate=0.17,
            available_cash=pnc_after_withdrawal,
            available_brokerage=balances['taxable']
        )
        
        is_feasible, msg = rollover_handler.validate_redeposit_feasibility(
            withholding_amount=rollover_plan.withholding_amount,
            available_cash=pnc_after_withdrawal,
            available_brokerage=balances['taxable']
        )
        
        print(f"  Conversion Amount: ${rollover_plan.conversion_amount:,.0f}")
        print(f"  Estimated Withholding (17%): ${rollover_plan.withholding_amount:,.0f}")
        print(f"  Net Roth Deposit: ${rollover_plan.net_conversion_deposit:,.0f}")
        print(f"  Redeposit Deadline: {rollover_plan.redeposit_deadline.strftime('%B %d, %Y')}")
        print(f"  Feasible: {'✓ YES' if is_feasible else '✗ NO'}")
    
    # ========================================================================
    # SUMMARY
    # ========================================================================
    print("\n" + "=" * 70)
    print("YOUR 2026 JANUARY WITHDRAWAL PLAN - SUMMARY")
    print("=" * 70)
    print(f"""
WITHDRAWAL PLAN (January):
  Part A (Cover Spending Shortfall): ${calc.traditional_part_a:,.0f} → PNC
  Part B (Roth Conversion Space): ${calc.traditional_part_b:,.0f}
  Total Traditional Withdrawal: ${calc.traditional_total:,.0f}

ANNUAL CASH FLOW:
  PNC Starting: ${balances['cash']:,.0f}
  Total Available (after withdrawal): ${pnc_after_withdrawal:,.0f}
  Less: Annual Spending & DAF: ${total_expenses + daf_annual:,.0f}
  Projected Year-End: ${pnc_after_spending:,.0f}

SAFETY RULE:
  If PNC drops below ${safety_threshold:,.0f}, withdraw from Brokerage

TAX SUMMARY:
  Estimated Federal + State Tax: ${calc.estimated_total_tax:,.0f}
  Roth Conversion Amount: ${optimization.conversion_amount:,.0f}
  Strategy: {optimization.optimization_strategy.upper()}

COMPARISON TO CURRENT (BETR) STRATEGY:
  From your Year-to-Year Details for 2026:
  - Current shows Trad→Cash: $107,160
  - Bracket-fill calculates: ${calc.traditional_part_a:,.0f}
  - Difference: ${abs(calc.traditional_part_a - 107160):,.0f}
""")


if __name__ == '__main__':
    example_with_actual_data()
