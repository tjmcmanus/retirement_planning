#!/usr/bin/env python3
"""Analyze the screenshot data to identify the buffer replenishment issue"""

from strategy import calculate_cash_buffer_targets

# Data from screenshot - Account Balances Over Time
years_data = [
    {"year": 2031, "cash": 244200.89, "taxable": 238244.77, "traditional": 5470413.63, "roth": 162425.75, "daf": 400000},
    {"year": 2032, "cash": 250305.91, "taxable": 138244.77, "traditional": 5334199.65, "roth": 162425.75, "daf": 500000},
    {"year": 2033, "cash": 256563.56, "taxable": 138244.77, "traditional": 5194704.22, "roth": 162425.75, "daf": 500000},
    {"year": 2034, "cash": 262977.64, "taxable": 38244.77, "traditional": 5051845.31, "roth": 162425.75, "daf": 600000},
    {"year": 2035, "cash": 269552.09, "taxable": 38244.77, "traditional": 4905538.83, "roth": 162425.75, "daf": 600000},
    {"year": 2036, "cash": 276290.89, "taxable": 38244.77, "traditional": 4818536.82, "roth": 162425.75, "daf": 600000},
    {"year": 2037, "cash": 271015.23, "taxable": 38244.77, "traditional": 4810933.45, "roth": 162425.75, "daf": 600000},
    {"year": 2038, "cash": 276455.35, "taxable": 38244.77, "traditional": 4791781.62, "roth": 162425.75, "daf": 600000},
    {"year": 2039, "cash": 283366.73, "taxable": 219066.71, "traditional": 4509249.49, "roth": 183638.66, "daf": 600000},
    {"year": 2040, "cash": 290450.90, "taxable": 395900.03, "traditional": 4223032.76, "roth": 210223.39, "daf": 600000},
]

# Assume expenses around $102,780 (from earlier test)
expenses = 102780

print("=" * 100)
print("SCREENSHOT DATA ANALYSIS - Buffer Replenishment Issue")
print("=" * 100)

cash_target, brokerage_target = calculate_cash_buffer_targets(expenses)
print(f"\nBuffer Targets (assuming ${expenses:,.0f} expenses):")
print(f"  Cash Target: ${cash_target:,.0f}")
print(f"  Brokerage Target: ${brokerage_target:,.0f}")

print(f"\n{'Year':<6} {'Cash':<15} {'Taxable':<15} {'Cash vs Target':<20} {'Taxable vs Target':<20} {'Issue?':<10}")
print("-" * 100)

for data in years_data:
    year = data['year']
    cash = data['cash']
    taxable = data['taxable']
    
    cash_diff = cash - cash_target
    taxable_diff = taxable - brokerage_target
    
    # Check if there's an issue
    issue = ""
    if taxable < brokerage_target - 100:
        issue = "❌ LOW"
    elif cash < cash_target - 100:
        issue = "⚠️ CASH"
    else:
        issue = "✓"
    
    print(f"{year:<6} ${cash:<14,.0f} ${taxable:<14,.0f} ${cash_diff:<19,.0f} ${taxable_diff:<19,.0f} {issue:<10}")

print("\n" + "=" * 100)
print("KEY FINDINGS")
print("=" * 100)

# Identify problematic years
print("\nYears with Brokerage Buffer Issues:")
for data in years_data:
    if data['taxable'] < brokerage_target - 100:
        shortfall = brokerage_target - data['taxable']
        print(f"  {data['year']}: Brokerage ${data['taxable']:,.0f} (${shortfall:,.0f} below target)")

print("\nPattern Analysis:")
print("  2031: Brokerage = $238,245 (above target) ✓")
print("  2032: Brokerage = $138,245 (dropped by $100,000) ❌")
print("  2033: Brokerage = $138,245 (stayed low) ❌")
print("  2034: Brokerage = $38,245 (dropped another $100,000) ❌")
print("  2035-2038: Brokerage = $38,245 (stayed very low) ❌")
print("  2039: Brokerage = $219,067 (jumped up) ✓")
print("  2040: Brokerage = $395,900 (jumped up more) ✓")

print("\n" + "=" * 100)
print("HYPOTHESIS")
print("=" * 100)
print("The brokerage buffer is NOT being replenished in years 2032-2038.")
print("This suggests the replenishment logic is being bypassed or not triggered.")
print("\nPossible causes:")
print("1. The optimized routing is preventing brokerage replenishment")
print("2. The brokerage buffer check is not running in normal flow")
print("3. There's a condition preventing Traditional→Brokerage transfers")
print("4. The buffer target calculation is incorrect")

# Made with Bob