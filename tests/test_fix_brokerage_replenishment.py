#!/usr/bin/env python3
"""Test the fix for brokerage buffer replenishment issue"""

from strategy import (
    calculate_cash_buffer_targets,
    rebalance_accounts,
    PortfolioBalances,
)

# Test scenario: Brokerage is already below target (like year 2032 in screenshot)
expenses = 102780
age_primary = 66
year = 2032
stage = "Stage5SocialSecurity"

# Starting balances where brokerage is BELOW target
# These are BEFORE expenses are deducted (like beginning of year)
balances_before = PortfolioBalances(
    cash=244200.89,  # Before expenses
    taxable=138244.77,  # BELOW target of $205,560
    traditional=5470413.63,
    roth=162425.75,
    daf=500000
)

print("=" * 100)
print("TEST: Brokerage Buffer Replenishment Fix")
print("=" * 100)
print(f"\nScenario: Brokerage starts BELOW target and needs replenishment")
print(f"Year: {year}, Age: {age_primary}, Stage: {stage}")
print(f"Annual Expenses: ${expenses:,.0f}")

cash_target, brokerage_target = calculate_cash_buffer_targets(expenses)
print(f"\nBuffer Targets:")
print(f"  Cash Target: ${cash_target:,.0f}")
print(f"  Brokerage Target: ${brokerage_target:,.0f}")

print(f"\nStarting Balances (before expenses deducted):")
print(f"  Cash: ${balances_before.cash:,.2f}")
print(f"  Taxable: ${balances_before.taxable:,.2f} (deficit: ${max(0, brokerage_target - balances_before.taxable):,.0f})")
print(f"  Traditional: ${balances_before.traditional:,.2f}")
print(f"  Roth: ${balances_before.roth:,.2f}")

# Calculate what the routing decision should be AFTER expenses are deducted
cash_after_expenses = balances_before.cash - expenses
cash_deficit = max(0, cash_target - cash_after_expenses)
brokerage_after_cash = balances_before.taxable - cash_deficit
brokerage_deficit_after_cash = max(0, brokerage_target - brokerage_after_cash)

print(f"\nRouting Analysis (after ${expenses:,.0f} expenses deducted):")
print(f"  Cash after expenses: ${cash_after_expenses:,.0f}")
print(f"  Cash deficit: ${cash_deficit:,.0f}")
print(f"  Brokerage after covering cash: ${brokerage_after_cash:,.0f}")
print(f"  Brokerage deficit after cash: ${brokerage_deficit_after_cash:,.0f}")

if cash_deficit > 0 and brokerage_deficit_after_cash > 100:
    print(f"  → Optimized routing will be used")
else:
    print(f"  → Normal routing will be used")

# Run rebalance
print(f"\n" + "=" * 100)
print("RUNNING rebalance_accounts() WITH FIX")
print("=" * 100)

new_balances, transactions, decision_log = rebalance_accounts(
    balances=balances_before,
    expenses=expenses,  # Will be deducted inside rebalance_accounts
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
print(f"  Taxable: ${new_balances.taxable:,.2f}")
print(f"  Traditional: ${new_balances.traditional:,.2f}")
print(f"  Roth: ${new_balances.roth:,.2f}")

print(f"\nBalance Changes:")
print(f"  Cash: ${new_balances.cash - balances_before.cash:+,.2f}")
print(f"  Brokerage: ${new_balances.taxable - balances_before.taxable:+,.2f}")
print(f"  Traditional: ${new_balances.traditional - balances_before.traditional:+,.2f}")

print(f"\n" + "=" * 100)
print("VERIFICATION")
print("=" * 100)

cash_shortfall = max(0, cash_target - new_balances.cash)
brokerage_shortfall = max(0, brokerage_target - new_balances.taxable)

print(f"\nTarget Achievement:")
print(f"  Cash: ${new_balances.cash:,.2f} vs ${cash_target:,.0f} target")
if cash_shortfall < 100:
    print(f"    ✓ Cash buffer at target")
else:
    print(f"    ❌ Cash still short by ${cash_shortfall:,.0f}")

print(f"  Brokerage: ${new_balances.taxable:,.2f} vs ${brokerage_target:,.0f} target")
if brokerage_shortfall < 100:
    print(f"    ✓ Brokerage buffer at target (FIX WORKING!)")
else:
    print(f"    ❌ Brokerage still short by ${brokerage_shortfall:,.0f} (FIX NOT WORKING)")

print(f"\n" + "=" * 100)
if cash_shortfall < 100 and brokerage_shortfall < 100:
    print("✓✓✓ SUCCESS! Both buffers replenished to target")
elif brokerage_shortfall < 100:
    print("✓ PARTIAL SUCCESS: Brokerage replenished (cash may need more sources)")
else:
    print("❌ FAILURE: Brokerage buffer not replenished")
print("=" * 100)

# Made with Bob