"""
Example: 2027 January Bracket-Fill Strategy with YOUR ACTUAL DATA

2027 is the first full year in retirement (no wages, no SS yet).
This is where bracket-fill really shines!

Run this to see your optimal withdrawal plan for 2027.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from strategy_core.withdrawal_orchestrator import JanuaryBracketFillOrchestrator
from strategy_core.roth_conversion_optimizer import RothConversionOptimizer
from strategy_core.sixty_day_rollover import SixtyDayRolloverHandler
from strategy_core.tax_calculator import TaxCalculator
from config import get_config_manager

def get_balances_for_2027():
    """
    Estimate 2027 portfolio balances.
    
    These are projections based on:
    - 2026 starting balances from your snapshot
    - 2026 withdrawals and growth
    - Growth rate from config (6% default)
    """
    # Estimate: start with 2026 balances, apply 1 year growth, subtract 2026 net outflows
    # Using conservative estimates
    return {
        'traditional': 1750000,   # Down slightly from 2026 (some 2026 withdrawals)
        'roth': 900000,           # Up from 2026 (2026 Roth conversions + growth)
        'taxable': 1150000,       # Up (2026 gains + DAF funding)
        'cash': 100000,           # Down (spending throughout 2026)
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

def example_2027():
    """
    Calculate your 2027 withdrawal strategy using bracket-fill.
    """
    
    print("=" * 70)
    print("2027 JANUARY BRACKET-FILL WITHDRAWAL STRATEGY")
    print("First Full Year in Retirement (No Wages, No SS)")
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
    # STEP 1: Your 2027 Situation
    # ========================================================================
    print("\n1. YOUR 2027 SITUATION (January 1, 2027)")
    print("-" * 70)
    
    year = 2027
    age_primary = 61  # Tom (born 1966-05-16)
    age_spouse = 60   # Sarah (born 1967-03-22)
    filing_status = 'married_filing_jointly'
    state = config_mgr.get("personal_info", "retirement_state", "PA")
    
    # Get projected balances
    balances = get_balances_for_2027()
    
    print(f"  Names: Tom (age {age_primary}) & Sarah (age {age_spouse})")
    print(f"  Filing Status: {filing_status}, State: {state}")
    print(f"  STATUS: Fully retired (no wages, no SS)")
    print(f"\n  Projected Account Balances (2027):")
    print(f"    Traditional: ${balances['traditional']:,.0f}")
    print(f"    Roth: ${balances['roth']:,.0f}")
    print(f"    Brokerage (Taxable): ${balances['taxable']:,.0f}")
    print(f"    Cash (PNC): ${balances['cash']:,.0f}")
    
    # ========================================================================
    # STEP 2: Your 2027 Annual Spending Need
    # ========================================================================
    print("\n2. YOUR 2027 ANNUAL SPENDING NEED")
    print("-" * 70)
    
    # Get base expenses from config
    base_expenses = config_mgr.get("financial_assumptions", "expected_annual_expenses", 133600)
    # Apply inflation from 2026 to 2027
    # NOTE: Config stores inflation as percentage (3.0 = 3%), need to convert to decimal
    inflation_rate_pct = config_mgr.get("financial_assumptions", "expense_inflation_rate", 3.0)
    inflation_rate = inflation_rate_pct / 100.0  # Convert 3.0 to 0.03
    expenses_2027 = base_expenses * (1 + inflation_rate)
    
    # Calculate ACA costs
    aca_costs = calculate_aca_costs_for_year(config_mgr, year, age_primary, age_spouse)
    
    # DAF contribution (SEPARATE from spending)
    has_daf = config_mgr.get("charitable_giving", "has_daf", False)
    daf_annual = 0
    if has_daf:
        daf_start_age = config_mgr.get("charitable_giving", "daf_contribution_start_age", 61)
        daf_end_age = config_mgr.get("charitable_giving", "daf_contribution_end_age", 75)
        if daf_start_age <= age_primary < daf_end_age:
            daf_annual = config_mgr.get("charitable_giving", "daf_annual_contribution", 0)
    
    # Big-ticket items in 2027
    big_ticket = 0
    big_ticket_items = config_mgr.get("expenses", "big_ticket_items", [])
    for item in big_ticket_items:
        if item.get("start_year") <= year <= item.get("end_year"):
            frequency = item.get("frequency_years", 1)
            years_since_start = year - item.get("start_year", year)
            if years_since_start % frequency == 0:
                big_ticket += item.get("amount", 0)
    
    # SPENDING ONLY (not including DAF)
    total_expenses = expenses_2027 + aca_costs + big_ticket
    
    print(f"  Base Living Expenses (inflated 3%): ${expenses_2027:,.0f}")
    print(f"  ACA Healthcare Costs: ${aca_costs:,.0f}")
    print(f"  Big-Ticket Items (2027): ${big_ticket:,.0f}")
    print(f"  {'─' * 50}")
    print(f"  Total Annual Spending Need: ${total_expenses:,.0f}")
    print()
    print(f"  DAF/Charitable Giving (separate): ${daf_annual:,.0f}")
    
    # ========================================================================
    # STEP 3: Calculate Bracket-Fill Withdrawal for 2027
    # ========================================================================
    print("\n3. BRACKET-FILL CALCULATION")
    print("-" * 70)
    
    # 2027: NO wages, NO SS (both start at age 70)
    # So other_ordinary_income = 0
    other_ordinary_income = 0
    
    print(f"\n  → 2027 Ordinary Income Sources")
    print(f"    Wages: $0 (fully retired)")
    print(f"    Social Security: $0 (both start at age 70)")
    print(f"    Dividends/Interest/Rental: $0 (not configured)")
    print(f"    Total Other Ordinary Income: ${other_ordinary_income:,.0f}")
    
    # Debug: Show bracket calculation
    std_ded = tax_calc.calculate_standard_deduction(filing_status, year, age_primary, age_spouse)
    bracket_12_threshold = 103000  # From income_rates.csv for 2027 MFJ (line 68)
    bracket_available_calc = max(0, bracket_12_threshold - std_ded - other_ordinary_income)
    
    print(f"\n  → DEBUG: 12% Bracket Calculation Details")
    print(f"    Bracket Upper Limit (2027): ${bracket_12_threshold:,.0f}")
    print(f"    Minus: Standard Deduction (age 61/60): ${std_ded:,.0f}")
    print(f"    Minus: Other Ordinary Income: ${other_ordinary_income:,.0f}")
    print(f"    = Available Bracket Space: ${bracket_available_calc:,.0f}")
    
    # ACA is enabled in this scenario (ages 61 and 60)
    aca_enabled = aca_costs > 0
    aca_magi_threshold = None
    if aca_enabled:
        aca_magi_threshold = 74000  # Approximate 400% FPL for 2027
    
    # IMPORTANT: Annual spending for bracket calc is ONLY living expenses (not DAF)
    calc = orchestrator.calculate_bracket_fill_withdrawal(
        year=year,
        pnc_balance=balances['cash'],
        annual_expenses=total_expenses,  # Spending ONLY (not DAF)
        filing_status=filing_status,
        age_primary=age_primary,
        age_spouse=age_spouse,
        other_ordinary_income=other_ordinary_income,
        aca_enabled=aca_enabled,
        aca_magi_threshold=aca_magi_threshold,
        stage="Your 2027 Plan"
    )
    
    # Now add DAF to the Traditional distribution needed
    # DAF is included in the Traditional withdrawal amount but NOT part of the PNC cash shortfall
    total_traditional_with_daf = calc.traditional_total + daf_annual
    
    print(f"\n  PNC Cash On Hand: ${calc.pnc_balance:,.0f}")
    print(f"  Annual Spending Need: ${calc.annual_spending_need:,.0f}")
    print(f"  Shortfall (must withdraw): ${calc.shortfall:,.0f}")
    print()
    print(f"  12% Federal Tax Bracket Available: ${calc.bracket_12_available:,.0f}")
    print()
    print(f"  → Traditional Part A (cover shortfall): ${calc.traditional_part_a:,.0f}")
    print(f"  → Traditional Part B (Roth conversion): ${calc.traditional_part_b:,.0f}")
    print(f"  → Subtotal (Spending only): ${calc.traditional_total:,.0f}")
    print()
    print(f"  → DAF Contribution (separate distribution): ${daf_annual:,.0f}")
    print(f"  → TOTAL Traditional Distribution: ${total_traditional_with_daf:,.0f}")
    print()
    print(f"  Estimated Tax on Spending Withdrawals: ${calc.estimated_total_tax:,.0f}")
    
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
    for line in optimization.reasoning.split('\n')[:6]:
        if line.strip():
            print(f"    {line}")
    
    # ========================================================================
    # STEP 5: PNC Cash Flow Analysis
    # ========================================================================
    print("\n5. PNC CASH FLOW ANALYSIS")
    print("-" * 70)
    
    pnc_after_withdrawal = balances['cash'] + calc.traditional_part_a
    pnc_after_spending = pnc_after_withdrawal - total_expenses  # Spending ONLY (not DAF)
    
    print(f"  PNC Starting Balance: ${balances['cash']:,.0f}")
    print(f"  + Traditional Part A Deposit: ${calc.traditional_part_a:,.0f}")
    print(f"  = Total Available: ${pnc_after_withdrawal:,.0f}")
    print(f"  - Annual Spending: ${total_expenses:,.0f}")
    print(f"  = Year-End Projected (after spending): ${pnc_after_spending:,.0f}")
    print()
    print(f"  NOTE: DAF (${daf_annual:,.0f}) is funded separately from Traditional distribution")
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
    rollover_plan = None
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
    else:
        print("\n6. NO ROTH CONVERSION IN THIS SCENARIO")
        print("-" * 70)
        print(f"  The shortfall (${calc.traditional_part_a:,.0f}) consumes the entire 12% bracket.")
        print(f"  No room remains for Roth conversions in this year.")
    
    # ========================================================================
    # STEP 7: Comparison to 2026
    # ========================================================================
    print("\n7. COMPARISON: 2026 vs 2027")
    print("-" * 70)
    print(f"""
2026 (Partial Retirement Year):
  • Wages: $278,333
  • 12% Bracket Available: $0 (exhausted by wages)
  • Roth Conversion Opportunity: NONE
  • Traditional Withdrawal: $6,828 (only shortfall)

2027 (First Full Retirement Year):
  • Wages: $0 (fully retired)
  • 12% Bracket Available: ${calc.bracket_12_available:,.0f}
  • Roth Conversion Opportunity: ${optimization.conversion_amount:,.0f}
  • Traditional Withdrawal: ${calc.traditional_total:,.0f}
  
KEY INSIGHT:
  By retiring in October 2026, you unlock ~${calc.bracket_12_available:,.0f} of 
  12% bracket space in 2027 that can be used for Roth conversions. This is where
  the bracket-fill strategy creates significant tax efficiency!
""")
    
    # ========================================================================
    # SUMMARY
    # ========================================================================
    withholding_amt = rollover_plan.withholding_amount if rollover_plan else 0
    
    print("\n" + "=" * 70)
    print("YOUR 2027 JANUARY WITHDRAWAL PLAN - SUMMARY")
    print("=" * 70)
    print(f"""
WITHDRAWAL PLAN (January 2027):
  Part A (Cover Spending Shortfall): ${calc.traditional_part_a:,.0f} → PNC
  Part B (Roth Conversion Space): ${calc.traditional_part_b:,.0f}
  Subtotal (Spending-based): ${calc.traditional_total:,.0f}
  
  + DAF Contribution: ${daf_annual:,.0f}
  = TOTAL Traditional Distribution: ${total_traditional_with_daf:,.0f}

ROTH CONVERSION:
  Amount: ${optimization.conversion_amount:,.0f}
  Strategy: {optimization.optimization_strategy.upper()}
  Withholding (60-day redeposit): ${withholding_amt:,.0f}

ANNUAL CASH FLOW:
  PNC Starting: ${balances['cash']:,.0f}
  + Traditional withdrawal (Part A): ${calc.traditional_part_a:,.0f}
  = Available for spending: ${pnc_after_withdrawal:,.0f}
  - Annual spending: ${total_expenses:,.0f}
  = Year-end PNC: ${pnc_after_spending:,.0f}

TAX EFFICIENCY:
  The bracket-fill strategy analysis (spending only):
  • Available 12% bracket space: ${calc.bracket_12_available:,.0f}
  • Used for spending/taxes: ${calc.traditional_total:,.0f}
  • Remaining bracket for conversion: ${max(0, calc.bracket_12_available - calc.traditional_total):,.0f}
  
  DAF Contribution:
  • Amounts to ${daf_annual:,.0f}, funded from Traditional distribution
  • Can be optimized with Roth conversions in future years

BUDGET SUMMARY:
  PNC Cash Flow: Spending covered by ${calc.traditional_part_a:,.0f} Traditional + PNC
  Traditional Distribution: ${total_traditional_with_daf:,.0f} (spending + DAF)
  Safety buffer: Maintain PNC above ${safety_threshold:,.0f}
""")


if __name__ == '__main__':
    example_2027()
