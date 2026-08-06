"""
Example: Using the January Bracket-Fill Strategy

This example demonstrates how to use the new withdrawal orchestrator,
optimizer, and 60-day rollover handler to calculate your complete
annual withdrawal strategy in January.

Run this script to see your calculated withdrawal amounts and 60-day plan.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from strategy_core.withdrawal_orchestrator import JanuaryBracketFillOrchestrator
from strategy_core.roth_conversion_optimizer import RothConversionOptimizer
from strategy_core.sixty_day_rollover import SixtyDayRolloverHandler
from strategy_core.tax_calculator import TaxCalculator

# ============================================================================
# Example: Your 2026 Withdrawal Strategy
# ============================================================================

def example_january_bracket_fill():
    """
    Calculate your January bracket-fill strategy with all optimizations.
    """
    
    print("=" * 70)
    print("2026 JANUARY BRACKET-FILL WITHDRAWAL STRATEGY")
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
    
    # ========================================================================
    # STEP 1: Your Current Situation (January 1, 2026)
    # ========================================================================
    print("\n1. CURRENT SITUATION (January 1, 2026)")
    print("-" * 70)
    
    pnc_balance = 75000.0  # Your actual PNC spendable cash
    age_primary = 60       # Tom's age
    age_spouse = 59        # Sarah's age
    year = 2026
    filing_status = 'married_filing_jointly'
    
    # Account balances (from portfolio snapshot)
    traditional_balance = 1500000.0
    roth_balance = 500000.0
    taxable_balance = 800000.0
    
    print(f"  PNC Cash Balance: ${pnc_balance:,.2f}")
    print(f"  Ages: {age_primary}/{age_spouse}")
    print(f"  Filing Status: {filing_status}")
    print(f"  Traditional Balance: ${traditional_balance:,.2f}")
    print(f"  Roth Balance: ${roth_balance:,.2f}")
    print(f"  Taxable Balance: ${taxable_balance:,.2f}")
    
    # ========================================================================
    # STEP 2: Calculate Annual Spending Need
    # ========================================================================
    print("\n2. ANNUAL SPENDING NEED (Full Year 2026)")
    print("-" * 70)
    
    living_expenses = 145000.0  # 12 months
    healthcare_costs = 12000.0  # ACA premiums (Stage 3)
    one_time_expenses = 0.0     # No big ticket items planned this year
    
    total_expenses = living_expenses + healthcare_costs + one_time_expenses
    print(f"  Living Expenses (12 months): ${living_expenses:,.2f}")
    print(f"  Healthcare (ACA premiums): ${healthcare_costs:,.2f}")
    print(f"  One-Time Items: ${one_time_expenses:,.2f}")
    print(f"  Total Expenses: ${total_expenses:,.2f}")
    
    # ========================================================================
    # STEP 3: Calculate Bracket-Fill Withdrawal
    # ========================================================================
    print("\n3. BRACKET-FILL CALCULATION")
    print("-" * 70)
    
    # Note: ACA is not enabled in this example (set to False)
    # If you had ACA subsidy, set aca_enabled=True and it would constrain conversion
    
    calc = orchestrator.calculate_bracket_fill_withdrawal(
        year=year,
        pnc_balance=pnc_balance,
        annual_expenses=total_expenses,
        filing_status=filing_status,
        age_primary=age_primary,
        age_spouse=age_spouse,
        other_ordinary_income=0.0,  # No dividends/interest yet
        aca_enabled=False,           # ACA not enabled this year
        aca_magi_threshold=None,
        stage="Stage 3 Example"
    )
    
    print(f"  Annual Spending Need: ${calc.annual_spending_need:,.2f}")
    print(f"  PNC Balance: ${calc.pnc_balance:,.2f}")
    print(f"  Shortfall: ${calc.shortfall:,.2f}")
    print()
    print(f"  12% Bracket Available: ${calc.bracket_12_available:,.2f}")
    print()
    print(f"  Traditional Part A (Cover Shortfall): ${calc.traditional_part_a:,.2f}")
    print(f"  Traditional Part B (Roth Conversion): ${calc.traditional_part_b:,.2f}")
    print(f"  Total Traditional Withdrawal: ${calc.traditional_total:,.2f}")
    print()
    print(f"  Estimated Tax on Withdrawal: ${calc.estimated_total_tax:,.2f}")
    
    # ========================================================================
    # STEP 4: Optimize Roth Conversion
    # ========================================================================
    print("\n4. ROTH CONVERSION OPTIMIZATION")
    print("-" * 70)
    
    # Example: You have DAF, so DAF strategy is evaluated first
    optimization = optimizer.optimize_conversion(
        available_bracket_space=calc.traditional_part_b,
        traditional_balance=traditional_balance,
        roth_balance=roth_balance,
        age_primary=age_primary,
        age_spouse=age_spouse,
        year=year,
        has_daf=True,                          # You have a DAF
        daf_annual_contribution=60000.0,       # Annual DAF contribution
        has_pension_or_other_ordinary_income=False,
        life_expectancy_primary=85,
        life_expectancy_spouse=87,
        betr_max_rate=0.24
    )
    
    print(f"  Optimization Strategy: {optimization.optimization_strategy.upper()}")
    print(f"  Recommended Conversion: ${optimization.conversion_amount:,.2f}")
    print(f"  Future RMD Impact: ${optimization.future_rmd_impact:,.2f} reduction")
    print()
    print(f"  Reasoning:\n{optimization.reasoning}")
    
    # ========================================================================
    # STEP 5: Plan 60-Day Rollover (if applicable)
    # ========================================================================
    print("\n5. 60-DAY ROLLOVER PLAN (Optional)")
    print("-" * 70)
    
    available_cash = calc.pnc_balance + calc.traditional_part_a  # Cash after Part A
    available_brokerage = taxable_balance  # Brokerage available
    
    rollover_plan = rollover_handler.plan_conversion_with_withholding(
        conversion_amount=optimization.conversion_amount,
        estimated_tax_rate=0.12,  # 12% federal + 5% state typically ~17%
        conversion_date=None,      # Uses today's date
        available_cash=available_cash,
        available_brokerage=available_brokerage
    )
    
    is_feasible, feasibility_msg = rollover_handler.validate_redeposit_feasibility(
        withholding_amount=rollover_plan.withholding_amount,
        available_cash=available_cash,
        available_brokerage=available_brokerage
    )
    
    print(f"  Conversion Amount: ${rollover_plan.conversion_amount:,.2f}")
    print(f"  Withholding Amount (est): ${rollover_plan.withholding_amount:,.2f}")
    print(f"  Net Roth Deposit: ${rollover_plan.net_conversion_deposit:,.2f}")
    print()
    print(f"  60-Day Redeposit Deadline: {rollover_plan.redeposit_deadline.strftime('%B %d, %Y')}")
    print(f"  Redeposit Source: {rollover_plan.source_for_redeposit}")
    print(f"  Feasible: {'YES ✓' if is_feasible else 'NO ✗'}")
    print()
    print(rollover_plan.reasoning)
    
    # ========================================================================
    # STEP 6: Cost Analysis
    # ========================================================================
    print("\n6. EFFECTIVE COST ANALYSIS")
    print("-" * 70)
    
    cost = rollover_handler.calculate_effective_conversion_cost(
        conversion_amount=optimization.conversion_amount,
        withholding_amount=rollover_plan.withholding_amount,
        capital_gains_if_brokerage_source=0.0  # Assuming LOFO handles this
    )
    
    print(f"  Conversion Amount: ${cost['conversion_amount']:,.2f}")
    print(f"  Withholding Tax: ${cost['withholding_tax']:,.2f}")
    print(f"  Capital Gains Tax: ${cost['capital_gains_tax']:,.2f}")
    print(f"  Total Out-of-Pocket: ${cost['total_out_of_pocket']:,.2f}")
    print(f"  Net to Roth: ${cost['net_to_roth']:,.2f}")
    print(f"  Effective Tax Rate: {cost['effective_tax_rate']*100:.1f}%")
    
    # ========================================================================
    # STEP 7: Execution Checklist
    # ========================================================================
    print("\n7. EXECUTION CHECKLIST")
    print("-" * 70)
    print(rollover_handler.generate_execution_checklist(rollover_plan))
    
    # ========================================================================
    # STEP 8: Mid-Year Monitoring
    # ========================================================================
    print("\n8. MID-YEAR MONITORING")
    print("-" * 70)
    
    safety_threshold = 50000.0  # Your safety threshold
    pnc_month_6 = 42000.0       # Hypothetical balance in June
    
    should_supplement = orchestrator.should_supplement_pnc(pnc_month_6)
    supplement_amount = orchestrator.calculate_brokerage_supplement(
        current_pnc_balance=pnc_month_6,
        target_pnc_balance=safety_threshold
    )
    
    print(f"  Safety Threshold: ${safety_threshold:,.2f}")
    print(f"  PNC Balance (June): ${pnc_month_6:,.2f}")
    print(f"  Should Supplement: {'YES' if should_supplement else 'NO'}")
    if should_supplement:
        print(f"  Supplement Amount: ${supplement_amount:,.2f}")
        print(f"  Action: Withdraw ${supplement_amount:,.2f} from Brokerage (LOFO)")
    
    # ========================================================================
    # SUMMARY
    # ========================================================================
    print("\n" + "=" * 70)
    print("SUMMARY: YOUR 2026 JANUARY WITHDRAWAL PLAN")
    print("=" * 70)
    print(f"""
Traditional IRA Withdrawal (January):
  • Part A (to cover shortfall): ${calc.traditional_part_a:,.2f}
  • Part B (Roth conversion): ${calc.traditional_part_b:,.2f}
  • Total: ${calc.traditional_total:,.2f}

Roth Conversion:
  • Amount: ${optimization.conversion_amount:,.2f}
  • Strategy: {optimization.optimization_strategy.upper()}
  • With-holding (60-day redeposit): ${rollover_plan.withholding_amount:,.2f}
  • Deadline: {rollover_plan.redeposit_deadline.strftime('%B %d, %Y')}

PNC Cash Flow:
  • Start: ${pnc_balance:,.2f}
  • + Traditional (Part A): ${calc.traditional_part_a:,.2f}
  • = Available: ${pnc_balance + calc.traditional_part_a:,.2f}
  • - Annual Spending: ${total_expenses:,.2f}
  • = Surplus/Deficit: ${pnc_balance + calc.traditional_part_a - total_expenses:,.2f}

Mid-Year Rule: If PNC drops below ${safety_threshold:,.2f}, 
  withdraw from Brokerage (LOFO: lowest-gain lots first).

Tax Impact:
  • Estimated tax on withdrawal: ${calc.estimated_total_tax:,.2f}
  • Form 8606: Report ${optimization.conversion_amount:,.2f} conversion
  • Keep records: Conversion date, withholding confirmation, redeposit proof
""")


if __name__ == '__main__':
    example_january_bracket_fill()
