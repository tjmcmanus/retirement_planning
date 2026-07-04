#!/usr/bin/env python3
"""Analyze 2026 tax situation to explain marginal bracket."""

from strategy import PortfolioBalances, build_withdrawal_strategy_display
import pandas as pd

# Get portfolio balances - use values from retirement_config.json
initial_balances = PortfolioBalances(
    cash=55000,  # Approximate from config
    taxable=225000,
    traditional=670000,
    roth=168000,
    daf=200000  # From config: daf_initial_contribution
)

# Calculate strategy for 2026 using config values
strategy_df, balances_df = build_withdrawal_strategy_display(
    start_year=2026,
    end_year=2026,
    initial_balances=initial_balances,
    initial_expenses=102780,  # From config
    person1_name="Gomez",
    person2_name="Morticia",
    growth_rate=1.05,  # 5% from config
    expense_inflation_rate=0.025,  # 2.5% from config
    ss_claiming_age=70,  # From config
    retirement_year=2026,  # Gomez retires in 2026
    has_wages=True  # 2026 is retirement year, still has wages
)

df = strategy_df

# Display 2026 results
if not df.empty:
    # First, let's see what columns we have
    print("\nAvailable columns:", df.columns.tolist())
    
    row = df[df['Year'] == 2026].iloc[0]
    print('\n' + '='*60)
    print('2026 TAX ANALYSIS - HOW YOU REACHED 35% MARGINAL BRACKET')
    print('='*60)
    print(f'\nYear: {int(row["Year"])}')
    print(f'Age (Gomez/Morticia): {row["Age"]}')
    
    print('\n--- INCOME SOURCES ---')
    wages = row.get("Wages", 0)
    trad_dist = row.get("Traditional Withdrawal", 0)
    roth_conv = row.get("Roth Conversion", 0)
    brok_with = row.get("Taxable Withdrawal", 0)
    interest = row.get("Interest Income", 0)
    ltcg = row.get("LTCG Harvested", 0)
    ss_benefits = row.get("SS Benefits", 0)
    
    print(f'Wages: ${wages:,.0f}')
    print(f'Traditional IRA Distributions: ${trad_dist:,.0f}')
    print(f'Roth Conversions: ${roth_conv:,.0f}')
    print(f'Brokerage Withdrawals: ${brok_with:,.0f}')
    print(f'Interest/Dividends: ${interest:,.0f}')
    print(f'Long-term Capital Gains: ${ltcg:,.0f}')
    print(f'Social Security Benefits: ${ss_benefits:,.0f}')
    
    print('\n--- TAX CALCULATION ---')
    daf = row.get("DAF Contribution", 0)
    agi_from_data = row.get("AGI", 0)
    
    # Get standard deduction for 2026 MFJ
    std_deduction = 32200  # 2026 standard deduction for MFJ
    
    # Calculate correct AGI: should include Roth conversions
    # Note: The data may have a bug where AGI doesn't include Roth conversions
    # Correct AGI = Wages (after 401k) + Roth Conversions + Traditional withdrawals + LTCG + SS (taxable)
    correct_agi = wages + roth_conv + trad_dist + ltcg
    if ss_benefits > 0:
        correct_agi += ss_benefits
    
    basis_returned = row.get("Basis Returned", 0)
    
    # Taxable Income = AGI - Standard Deduction (or itemized if DAF year)
    if daf > 0:
        # Simplified: assume DAF + SALT exceeds standard deduction
        calculated_taxable = correct_agi - std_deduction - (daf - std_deduction)
    else:
        calculated_taxable = correct_agi - std_deduction
    
    print(f'AGI Components:')
    print(f'  Wages (after 401k): ${wages:,.0f}')
    if roth_conv > 0:
        print(f'  Roth Conversion: ${roth_conv:,.0f}')
    if trad_dist > 0:
        print(f'  Traditional IRA Distributions: ${trad_dist:,.0f}')
    if ltcg > 0:
        print(f'  Long-Term Capital Gains: ${ltcg:,.0f}')
    if ss_benefits > 0:
        print(f'  Social Security (taxable): ${ss_benefits:,.0f}')
    
    print(f'\nCorrect AGI: ${correct_agi:,.0f}')
    if abs(correct_agi - agi_from_data) > 1:
        print(f'⚠️  Data shows AGI: ${agi_from_data:,.0f} (missing Roth conversion)')
    print(f'Less: Standard Deduction: ${std_deduction:,.0f}')
    if daf > 0:
        print(f'Less: DAF Contribution (itemized): ${daf:,.0f}')
    print(f'= Taxable Income: ${calculated_taxable:,.0f}')
    
    print('\n--- TAX BRACKETS (2026 Married Filing Jointly) ---')
    print('10%: $0 - $24,800')
    print('12%: $24,800 - $100,800')
    print('22%: $100,800 - $211,400')
    print('24%: $211,400 - $403,550')
    print('32%: $403,550 - $512,450')
    print('35%: $512,450 - $768,700')
    print('37%: $768,700+')
    
    fed_tax = row.get("Federal Tax", 0)
    state_tax = row.get("State Tax", 0)
    total_tax = fed_tax + state_tax
    
    # Calculate effective tax rate
    effective_fed = (fed_tax / calculated_taxable * 100) if calculated_taxable > 0 else 0
    effective_total = (total_tax / calculated_taxable * 100) if calculated_taxable > 0 else 0
    
    print(f'\n--- YOUR TAX SITUATION ---')
    print(f'Federal Income Tax: ${fed_tax:,.0f}')
    print(f'State Tax (PA): ${state_tax:,.0f}')
    print(f'Total Tax: ${total_tax:,.0f}')
    print(f'\nEffective Federal Tax Rate: {effective_fed:.2f}%')
    print(f'Effective Total Tax Rate: {effective_total:.2f}%')
    
    print('\n--- MARGINAL TAX BRACKET ANALYSIS ---')
    
    # Determine which bracket based on calculated taxable income
    if calculated_taxable > 768700:
        bracket = "37%"
        bracket_floor = 768700
        marginal_rate = 0.37
    elif calculated_taxable > 512450:
        bracket = "35%"
        bracket_floor = 512450
        marginal_rate = 0.35
    elif calculated_taxable > 403550:
        bracket = "32%"
        bracket_floor = 403550
        marginal_rate = 0.32
    elif calculated_taxable > 211400:
        bracket = "24%"
        bracket_floor = 211400
        marginal_rate = 0.24
    elif calculated_taxable > 100800:
        bracket = "22%"
        bracket_floor = 100800
        marginal_rate = 0.22
    elif calculated_taxable > 24800:
        bracket = "12%"
        bracket_floor = 24800
        marginal_rate = 0.12
    else:
        bracket = "10%"
        bracket_floor = 0
        marginal_rate = 0.10
    
    print(f'Marginal Tax Rate: {bracket}')
    print(f'Your taxable income of ${calculated_taxable:,.0f} places you in the {bracket} bracket.')
    print(f'You are ${calculated_taxable - bracket_floor:,.0f} into this bracket.')
    
    print('\n--- MARGINAL vs EFFECTIVE RATE ---')
    print(f'Marginal Rate: {marginal_rate:.1%} - Rate on your LAST dollar of income')
    print(f'Effective Rate: {effective_fed:.2f}% - AVERAGE rate across all income')
    print(f'Difference: {marginal_rate * 100 - effective_fed:.2f} percentage points')
    
    print('\n--- KEY CONTRIBUTORS TO YOUR TAXABLE INCOME ---')
    if roth_conv > 0:
        print(f'  • Roth Conversions: ${roth_conv:,.0f}')
    if ltcg > 0:
        print(f'  • Long-Term Capital Gains: ${ltcg:,.0f}')
    if wages > 0:
        print(f'  • Wages: ${wages:,.0f}')
    if trad_dist > 0:
        print(f'  • Traditional IRA Distributions: ${trad_dist:,.0f}')
    
    if daf > 0:
        print(f'\n💡 Tax Optimization Note:')
        print(f'Your DAF contribution of ${daf:,.0f} reduced your taxable income.')
        print(f'Without it, your taxable income would be ${calculated_taxable + daf:,.0f}')
        if calculated_taxable + daf > 512450:
            print(f'and you would be in the 35% bracket!')
        elif calculated_taxable + daf > 403550:
            print(f'and you would be in the 32% bracket!')
    
    print('\n' + '='*60)
else:
    print('No data found for 2026')

# Made with Bob
