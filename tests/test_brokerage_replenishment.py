#!/usr/bin/env python3
"""Test script to debug brokerage replenishment"""

from strategy import (
    calculate_cash_buffer_targets,
    replenish_brokerage_buffer,
    PortfolioBalances,
    BrokerageAccount
)
from config import get_config_manager

# Test with example from screenshot
expenses = 102780
age_primary = 66  # Year 2032, you're 66
year = 2032

# Starting balances from screenshot (2032)
balances = PortfolioBalances(
    cash=250305.91,
    taxable=138244.77,  # This is what we see in the new screenshot
    traditional=5370524.16,
    roth=162097.63,
    daf=500000
)

print("=" * 80)
print("BROKERAGE REPLENISHMENT TEST")
print("=" * 80)
print(f"\nYear: {year}")
print(f"Age: {age_primary}")
print(f"Annual Expenses: ${expenses:,.0f}")
print(f"\nStarting Balances:")
print(f"  Cash: ${balances.cash:,.2f}")
print(f"  Taxable (Brokerage): ${balances.taxable:,.2f}")
print(f"  Traditional: ${balances.traditional:,.2f}")
print(f"  Roth: ${balances.roth:,.2f}")

# Get targets
cash_target, brokerage_target = calculate_cash_buffer_targets(expenses)
print(f"\nBuffer Targets:")
print(f"  Cash Target: ${cash_target:,.0f}")
print(f"  Brokerage Target: ${brokerage_target:,.0f}")

# Calculate deficits
cash_deficit = max(0, cash_target - balances.cash)
brokerage_deficit = max(0, brokerage_target - balances.taxable)
print(f"\nDeficits:")
print(f"  Cash Deficit: ${cash_deficit:,.0f}")
print(f"  Brokerage Deficit: ${brokerage_deficit:,.0f}")

# Test replenishment
print(f"\n" + "=" * 80)
print("CALLING replenish_brokerage_buffer()")
print("=" * 80)

new_balances, transactions, decision_log = replenish_brokerage_buffer(
    balances=balances,
    expenses=expenses,
    age_primary=age_primary,
    year=year,
    brokerage_account=None
)

print(f"\nTransactions:")
print(f"  Traditional → Brokerage: ${transactions['traditional_to_brokerage']:,.2f}")
print(f"  Total Brokerage Replenishment: ${transactions['brokerage_replenishment']:,.2f}")

print(f"\nNew Balances:")
print(f"  Cash: ${new_balances.cash:,.2f}")
print(f"  Taxable (Brokerage): ${new_balances.taxable:,.2f}")
print(f"  Traditional: ${new_balances.traditional:,.2f}")
print(f"  Roth: ${new_balances.roth:,.2f}")

print(f"\nBrokerage Change: ${new_balances.taxable - balances.taxable:,.2f}")
print(f"Expected to reach target: ${brokerage_target:,.0f}")
print(f"Actual after replenishment: ${new_balances.taxable:,.2f}")
print(f"Still short by: ${max(0, brokerage_target - new_balances.taxable):,.2f}")

print(f"\n" + "=" * 80)
print("DECISION LOG")
print("=" * 80)
for decision in decision_log.all_decisions():
    print(f"\n[{decision['category']}] {decision['title']}")
    print(f"  Action: {decision['action']}")
    print(f"  Reason: {decision['reason']}")
    if decision.get('details'):
        for key, value in decision['details'].items():
            print(f"    {key}: {value}")

# Made with Bob
