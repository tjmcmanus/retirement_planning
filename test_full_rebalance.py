#!/usr/bin/env python3
"""Test script to debug full rebalance flow including brokerage replenishment"""

from strategy import (
    calculate_cash_buffer_targets,
    rebalance_accounts,
    PortfolioBalances,
    BrokerageAccount
)
from config import get_config_manager

# Test with example from screenshot - Year 2032
expenses = 102780
age_primary = 66
year = 2032
stage = "Stage5SocialSecurity"

# Starting balances BEFORE rebalance (2031 ending balances)
balances_before = PortfolioBalances(
    cash=244200.89,
    taxable=238244.77,  # This should drop to 138244.77 after cash replenishment
    traditional=5470413.63,
    roth=162425.75,
    daf=400000
)

print("=" * 80)
print("FULL REBALANCE TEST - Year 2032")
print("=" * 80)
print(f"\nYear: {year}")
print(f"Age: {age_primary}")
print(f"Stage: {stage}")
print(f"Annual Expenses: ${expenses:,.0f}")

print(f"\nStarting Balances (before rebalance):")
print(f"  Cash: ${balances_before.cash:,.2f}")
print(f"  Taxable (Brokerage): ${balances_before.taxable:,.2f}")
print(f"  Traditional: ${balances_before.traditional:,.2f}")
print(f"  Roth: ${balances_before.roth:,.2f}")

# Get targets
cash_target, brokerage_target = calculate_cash_buffer_targets(expenses)
print(f"\nBuffer Targets:")
print(f"  Cash Target: ${cash_target:,.0f}")
print(f"  Brokerage Target: ${brokerage_target:,.0f}")

# Simulate what happens in rebalance_accounts
print(f"\n" + "=" * 80)
print("STEP 1: Deduct expenses from cash")
print("=" * 80)
total_cash_outflow = expenses  # Simplified - no taxes for this test
balances_after_expenses = PortfolioBalances(
    cash=balances_before.cash - total_cash_outflow,
    taxable=balances_before.taxable,
    traditional=balances_before.traditional,
    roth=balances_before.roth,
    daf=balances_before.daf
)
print(f"Cash after expenses: ${balances_after_expenses.cash:,.2f}")

# Calculate deficits
cash_deficit = max(0, cash_target - balances_after_expenses.cash)
print(f"Cash deficit: ${cash_deficit:,.0f}")

# Calculate what brokerage would have after covering cash deficit
brokerage_after_cash = balances_after_expenses.taxable - cash_deficit
brokerage_deficit_after_cash = max(0, brokerage_target - brokerage_after_cash)

print(f"\n" + "=" * 80)
print("STEP 2: Check routing decision")
print("=" * 80)
print(f"Brokerage balance: ${balances_after_expenses.taxable:,.0f}")
print(f"Brokerage after covering cash deficit: ${brokerage_after_cash:,.0f}")
print(f"Brokerage target: ${brokerage_target:,.0f}")
print(f"Brokerage deficit after cash: ${brokerage_deficit_after_cash:,.0f}")

_BUFFER_REPLENISHMENT_MIN_DEFICIT = 100.0
if cash_deficit > 0 and brokerage_deficit_after_cash > _BUFFER_REPLENISHMENT_MIN_DEFICIT:
    print(f"\n✓ OPTIMIZED ROUTING TRIGGERED")
    print(f"  Brokerage cannot cover both cash and maintain buffer")
    print(f"  Will route Traditional directly to Cash")
else:
    print(f"\n✓ NORMAL ROUTING")
    print(f"  Brokerage can cover cash and maintain buffer")
    print(f"  Will use: Brokerage→Cash, then Traditional→Brokerage")

# Now run the actual rebalance
print(f"\n" + "=" * 80)
print("CALLING rebalance_accounts()")
print("=" * 80)

new_balances, transactions, decision_log = rebalance_accounts(
    balances=balances_before,
    expenses=expenses,
    roth_conversion=0.0,
    year=year,
    age_primary=age_primary,
    stage=stage,
    federal_tax=0.0,
    irmaa_penalty=0.0,
    aca_premium=0.0,
    medical_costs=0.0,
    cash_target_override=None,
    brokerage_account=None
)

print(f"\nTransactions:")
print(f"  Brokerage → Cash: ${transactions['brokerage_to_cash']:,.2f}")
print(f"  Traditional → Cash: ${transactions['traditional_to_cash']:,.2f}")
print(f"  Traditional → Brokerage: ${transactions['traditional_to_brokerage']:,.2f}")
print(f"  Roth → Cash: ${transactions['roth_to_cash']:,.2f}")
print(f"  Cash Replenishment: ${transactions['cash_replenishment']:,.2f}")
print(f"  Brokerage Replenishment: ${transactions['brokerage_replenishment']:,.2f}")

print(f"\nFinal Balances:")
print(f"  Cash: ${new_balances.cash:,.2f}")
print(f"  Taxable (Brokerage): ${new_balances.taxable:,.2f}")
print(f"  Traditional: ${new_balances.traditional:,.2f}")
print(f"  Roth: ${new_balances.roth:,.2f}")

print(f"\nBalance Changes:")
print(f"  Cash: ${new_balances.cash - balances_before.cash:,.2f}")
print(f"  Brokerage: ${new_balances.taxable - balances_before.taxable:,.2f}")
print(f"  Traditional: ${new_balances.traditional - balances_before.traditional:,.2f}")

print(f"\nTarget Analysis:")
print(f"  Cash target: ${cash_target:,.0f}, Actual: ${new_balances.cash:,.2f}, Short by: ${max(0, cash_target - new_balances.cash):,.2f}")
print(f"  Brokerage target: ${brokerage_target:,.0f}, Actual: ${new_balances.taxable:,.2f}, Short by: ${max(0, brokerage_target - new_balances.taxable):,.2f}")

print(f"\n" + "=" * 80)
print("ISSUE ANALYSIS")
print("=" * 80)
if new_balances.taxable < brokerage_target - 100:
    print(f"❌ ISSUE CONFIRMED: Brokerage buffer not replenished!")
    print(f"   Expected: ${brokerage_target:,.0f}")
    print(f"   Actual: ${new_balances.taxable:,.2f}")
    print(f"   Shortfall: ${brokerage_target - new_balances.taxable:,.2f}")
else:
    print(f"✓ Brokerage buffer properly maintained")

# Made with Bob