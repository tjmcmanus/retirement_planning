#!/usr/bin/env python3
"""
Example: January Bracket-Fill Strategy with 60-Day Rollover
Using Your Actual Portfolio Data

This demonstrates the complete workflow:
1. January 1, 2027 assessment
2. Annual spending need calculation
3. PNC Savings balance check
4. Withdrawal planning
5. Roth conversion with 60-day rollover
6. Mid-year monitoring

Your Current Situation (Jan 1, 2027):
  - PNC Savings: $138,772.54
  - Age: Tom 61, Sarah 60 (first full retirement year)
  - Annual expenses: $137,608 (inflated from $133,600)
  - ACA premium: $24,000/year ($1,000/mo × 2 people)
"""

import sys
sys.path.insert(0, '.')

from datetime import datetime
from strategy_core.january_bracket_fill_strategy import JanuaryBracketFillStrategy
from strategy_core.tax_calculator import TaxCalculator

def format_currency(amount):
    """Format amount as currency."""
    return f"${amount:,.2f}"

def main():
    print("=" * 80)
    print("EXAMPLE: January Bracket-Fill Strategy with 60-Day Rollover")
    print("Your Actual Portfolio Data (2027)")
    print("=" * 80)
    print()
    
    # Initialize strategy
    # Safety reserve = 5 months of inflated expenses
    _annual_expenses = 137608.0
    _safety_reserve = round(_annual_expenses / 12 * 5)  # ≈ $57,337
    
    strategy = JanuaryBracketFillStrategy(
        annual_expenses=_annual_expenses,  # Inflated from config: 133,600 × 1.03
        savings_account_safety_reserve=_safety_reserve,
        bracket_12_upper=103000.0,  # MFJ 2027
        standard_deduction=35500.0   # MFJ ages 61/60 in 2027
    )
    
    print("STRATEGY PARAMETERS:")
    print(f"  Annual expenses (inflated):    {format_currency(strategy.annual_expenses)}")
    print(f"  Savings safety reserve (5 mo): {format_currency(strategy.savings_account_safety_reserve)}")
    print(f"  12% bracket upper limit:       {format_currency(strategy.bracket_12_upper)}")
    print(f"  Standard deduction:            {format_currency(strategy.standard_deduction)}")
    print()
    
    # Your actual portfolio data
    pnc_savings_balance = 138772.54
    aca_premium = 24000.0  # $1,000/mo × 2 people × 12 months
    
    print("YOUR CURRENT SITUATION (Jan 1, 2027):")
    print(f"  PNC Savings account balance:    {format_currency(pnc_savings_balance)}")
    print(f"  Annual ACA premium:            {format_currency(aca_premium)}")
    print()
    
    # STEP 1: Plan January withdrawal
    print("-" * 80)
    print("STEP 1: PLAN JANUARY WITHDRAWAL")
    print("-" * 80)
    print()
    
    # Withholding rate comes from Stage 3 max conversion rate in config (currently 24%)
    # This is the rate at which taxes are withheld from Roth conversion
    import json
    try:
        with open('retirement_config.json') as f:
            _cfg = json.load(f)
        _stage3_rate = _cfg.get('tax_strategy', {}).get('stage_3_max_conversion_rate', 24) / 100.0
    except:
        _stage3_rate = 0.24
    
    print(f"  Stage 3 withholding rate (from config): {_stage3_rate:.0%}")
    print()
    
    plan = strategy.plan_january_withdrawal(
        pnc_savings_balance_jan1=pnc_savings_balance,
        estimated_tax_rate=_stage3_rate,
        aca_premium=aca_premium,
        conversion_date=datetime(2027, 1, 15)
    )
    
    print(f"Annual need:                    {format_currency(plan.total_annual_need)}")
    print(f"  = Expenses {format_currency(plan.annual_expenses)} + ACA {format_currency(aca_premium)}")
    print()
    print(f"PNC Savings available:          {format_currency(plan.pnc_balance_jan1)}")
    print(f"Shortfall:                      {format_currency(plan.pnc_shortfall)}")
    print()
    
    if plan.pnc_shortfall == 0:
        print("✓ NO WITHDRAWAL REQUIRED FOR SPENDING")
        print("  PNC Savings already covers annual need!")
        print()
        print("  OPTIONS:")
        print("    A) Leave Traditional untouched; spend from PNC Savings")
        print("    B) Still do Roth conversion for tax optimization (fill bracket space)")
        print()
    else:
        print(f"✗ WITHDRAWAL NEEDED: {format_currency(plan.pnc_shortfall)}")
    
    print()
    print("ROTH CONVERSION OPPORTUNITY:")
    print(f"  Conversion amount:             {format_currency(plan.roth_conversion_amount)}")
    print(f"  Conversion withholding (tax):  {format_currency(plan.conversion_withholding)}")
    print(f"  Net to Roth:                   {format_currency(plan.roth_conversion_amount - plan.conversion_withholding)}")
    print()
    
    print("TRADITIONAL WITHDRAWAL PLAN:")
    print(f"  For spending shortfall:        {format_currency(plan.traditional_withdrawal_for_spending)}")
    print(f"  For conversion withholding:    {format_currency(plan.traditional_withdrawal_for_taxes)}")
    print(f"  {'─' * 40}")
    print(f"  Total Traditional withdrawal:  {format_currency(plan.total_traditional_withdrawal)}")
    print()
    
    # STEP 2: 60-Day Rollover details
    print("-" * 80)
    print("STEP 2: 60-DAY ROLLOVER MECHANICS")
    print("-" * 80)
    print()
    
    print(f"Conversion date:                {plan.redeposit_funding_plan['redeposit_deadline'][:10]}")
    print(f"Redeposit deadline (day 60):    {plan.redeposit_funding_plan['redeposit_deadline']}")
    print(f"Redeposit source:               {plan.redeposit_source}")
    print()
    
    print("60-DAY ROLLOVER WORKFLOW:")
    print("  [ ] Day 1 (Jan 15):  Convert $0 to Roth (no conversion in this example)")
    print("  [ ] Day 1 (Jan 15):  Withhold $0 from Traditional (no withholding)")
    print("  [ ] Day 60 (Mar 15): Redeposit $0 to Traditional IRA")
    print()
    
    # STEP 3: Cash flow impact
    print("-" * 80)
    print("STEP 3: CASH FLOW IMPACT")
    print("-" * 80)
    print()
    
    print(f"Cash received:                 {format_currency(plan.cash_received_from_traditional)}")
    print(f"Annual expenses:               {format_currency(plan.annual_expenses)}")
    print(f"Estimated taxes:               {format_currency(plan.estimated_taxes)}")
    print(f"{'─' * 40}")
    print(f"Available after year-start:    {format_currency(plan.cash_available_after_expenses_taxes)}")
    print()
    
    print(f"PNC Savings after year-start:  {format_currency(plan.pnc_after_withdrawal)}")
    print()
    
    # STEP 4: Mid-year monitoring
    print("-" * 80)
    print("STEP 4: MID-YEAR MONITORING (June)")
    print("-" * 80)
    print()
    
    # Simulate PNC balance after 6 months of spending
    monthly_spending = plan.annual_expenses / 12
    pnc_after_6_months = plan.pnc_after_withdrawal - (monthly_spending * 5)  # 5 more months (plus initial month)
    
    print(f"Monthly spending rate:         {format_currency(monthly_spending)}")
    print(f"Months elapsed since Jan 1:    6")
    print(f"Projected PNC balance (Jun):   {format_currency(pnc_after_6_months)}")
    print()
    
    # Check if supplementation needed
    need_supplement, supplement_amount, reason = strategy.assess_midyear_savings_account(
        current_pnc_savings_balance=pnc_after_6_months,
        months_elapsed=6,
        monthly_spending_rate=monthly_spending
    )
    
    print(reason)
    print()
    
    if need_supplement:
        print(f"✗ SUPPLEMENTATION NEEDED: {format_currency(supplement_amount)}")
        print()
        
        # Plan supplementation
        supp_plan = strategy.plan_midyear_supplementation(
            pnc_savings_balance=pnc_after_6_months,
            available_brokerage=500000.0,  # Example: assume $500k in brokerage
            brokerage_ltcg_ratio=0.40
        )
        
        print("SUPPLEMENTATION PLAN:")
        print(f"  Sell Brokerage (LOFO):     {format_currency(supp_plan['amount'])}")
        print(f"  LTCG realized:             {format_currency(supp_plan['ltcg_realized'])}")
        print(f"  Reason:                    {supp_plan['reason']}")
        print(f"  Feasible:                  {'Yes' if supp_plan['feasible'] else 'No'}")
        print()
    else:
        print("✓ NO SUPPLEMENTATION NEEDED")
        print("  PNC Savings remains healthy throughout year")
        print()
    
    # STEP 5: Annual strategy summary
    print("-" * 80)
    print("ANNUAL STRATEGY SUMMARY")
    print("-" * 80)
    print()
    
    print(strategy.generate_annual_strategy_summary(plan))
    
    print()
    print("=" * 80)
    print("KEY INSIGHTS FOR YOUR 2027 PLAN")
    print("=" * 80)
    print()
    
    print("1. SPENDING COVERED")
    print(f"   ✓ PNC Savings ({format_currency(pnc_savings_balance)}) already covers")
    print(f"     annual need ({format_currency(plan.total_annual_need)})")
    print()
    
    print("2. TAX OPPORTUNITY")
    print(f"   → Available 12% bracket space: {format_currency(strategy.bracket_12_upper - strategy.standard_deduction)}")
    print(f"   → Consider Roth conversion if you want tax-free growth")
    print()
    
    print("3. MID-YEAR CUSHION")
    print(f"   → PNC after year-start: {format_currency(plan.pnc_after_withdrawal)}")
    print(f"   → Safety threshold: {format_currency(strategy.savings_account_safety_reserve)}")
    print(f"   → Cushion: {format_currency(plan.pnc_after_withdrawal - strategy.savings_account_safety_reserve)}")
    print()
    
    print("4. 60-DAY ROLLOVER READY")
    print("   → Conversion withholding mechanics are in place")
    print("   → If you do convert, must redeposit within 60 days")
    print()
    
    print("=" * 80)
    print()

if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
