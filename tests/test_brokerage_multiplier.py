#!/usr/bin/env python3
"""Test script to verify brokerage multiplier fix"""

from strategy import calculate_cash_buffer_targets
from config import get_config_manager

# Test with example expenses from the screenshot
expenses = 102780

cash_target, brokerage_target = calculate_cash_buffer_targets(expenses)

print(f'Annual Expenses: ${expenses:,.0f}')
print(f'Cash Target: ${cash_target:,.0f}')
print(f'Brokerage Target: ${brokerage_target:,.0f}')
print(f'Expected Brokerage (2x): ${expenses * 2:,.0f}')
print(f'Match: {brokerage_target == expenses * 2}')

# Also test that the config is being read correctly
config_mgr = get_config_manager()
multiplier = config_mgr.get('financial_assumptions', 'brokerage_rebalance_trigger_multiplier', 1.0)
print(f'\nConfig multiplier: {multiplier}')
print(f'Calculated target matches config: {brokerage_target == expenses * multiplier}')

# Made with Bob
