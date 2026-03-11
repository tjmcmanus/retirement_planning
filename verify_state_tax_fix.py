#!/usr/bin/env python3
"""
Verify that state tax is being calculated correctly in Stage 5 and Stage 6
by running a mini simulation.
"""

import sys
from strategy import (
    Stage5SocialSecurity, Stage6RMD, PortfolioBalances,
    get_config_manager
)

def verify_stage5_state_tax():
    """Verify Stage 5 calculates state tax correctly"""
    print("=" * 80)
    print("Verifying Stage 5 (Social Security) State Tax Calculation")
    print("=" * 80)
    
    # Set up test scenario similar to 2034
    stage5 = Stage5SocialSecurity()
    
    balances = PortfolioBalances(
        cash=256563,
        taxable=100015,
        traditional=500000,
        roth=300000,
        daf=0
    )
    
    # Simulate Stage 5 calculation
    result = stage5.calculate_strategy(
        year=2034,
        balances=balances,
        expenses=131488,
        ss_benefits=50676,
        target_conversion=0,
        prior_magi=169559,
        age_primary=68,
        age_spouse=67,
        start_year=2026,
        growth_rate=1.07,
        max_conversion_rate=0.24
    )
    
    print(f"\nYear: {result.year}")
    print(f"Stage: {result.stage}")
    print(f"SS Benefits: ${result.ss_benefits:,.0f}")
    print(f"Traditional Withdrawal: ${result.traditional_withdrawal:,.0f}")
    print(f"Brokerage Withdrawal: ${result.taxable_withdrawal:,.0f}")
    print(f"Roth Conversion: ${result.roth_conversion:,.0f}")
    print(f"LTCG Harvested: ${result.ltcg_harvested:,.0f}")
    print(f"AGI: ${result.agi:,.0f}")
    print(f"Federal Tax: ${result.federal_tax:,.0f}")
    print(f"State Tax: ${result.state_tax:,.0f}")
    
    if result.state_tax > 0:
        print(f"\n✓ SUCCESS: State tax is being calculated (${result.state_tax:,.0f})")
    else:
        print(f"\n❌ ISSUE: State tax is $0")
        print("This could mean:")
        print("1. You're in a no-tax state (check config)")
        print("2. All income is exempt in your state")
        print("3. The app needs to be restarted to pick up code changes")
    
    return result

def verify_stage6_state_tax():
    """Verify Stage 6 calculates state tax correctly"""
    print("\n" + "=" * 80)
    print("Verifying Stage 6 (RMD) State Tax Calculation")
    print("=" * 80)
    
    # Set up test scenario similar to 2039
    stage6 = Stage6RMD()
    
    balances = PortfolioBalances(
        cash=276455,
        taxable=110368,
        traditional=400000,
        roth=500000,
        daf=0
    )
    
    # Simulate Stage 6 calculation
    result = stage6.calculate_strategy(
        year=2039,
        balances=balances,
        expenses=141683,
        ss_benefits=122634,
        prior_magi=502240,
        age_primary=73,
        age_spouse=72,
        start_year=2026,
        growth_rate=1.07,
        max_conversion_rate=0.24
    )
    
    print(f"\nYear: {result.year}")
    print(f"Stage: {result.stage}")
    print(f"SS Benefits: ${result.ss_benefits:,.0f}")
    print(f"RMD Amount: ${result.rmd_amount:,.0f}")
    print(f"Traditional Withdrawal: ${result.traditional_withdrawal:,.0f}")
    print(f"Brokerage Withdrawal: ${result.taxable_withdrawal:,.0f}")
    print(f"AGI: ${result.agi:,.0f}")
    print(f"Federal Tax: ${result.federal_tax:,.0f}")
    print(f"State Tax: ${result.state_tax:,.0f}")
    
    if result.state_tax > 0:
        print(f"\n✓ SUCCESS: State tax is being calculated (${result.state_tax:,.0f})")
    else:
        print(f"\n❌ ISSUE: State tax is $0")
    
    return result

if __name__ == '__main__':
    print("\nChecking configuration...")
    try:
        config_mgr = get_config_manager()
        state = config_mgr.get('personal_info', 'retirement_state', 'FL')
        print(f"Retirement state: {state}")
        
        if state in ['FL', 'TX', 'WA', 'NV', 'SD', 'WY', 'AK', 'TN', 'NH']:
            print(f"⚠ WARNING: {state} is a no-tax state. State tax will always be $0.")
            print("If you want to see state taxes, change retirement_state to a state")
            print("with income tax (e.g., CA, NY, PA, etc.) in the Configuration page.\n")
    except Exception as e:
        print(f"Could not load config: {e}\n")
    
    result5 = verify_stage5_state_tax()
    result6 = verify_stage6_state_tax()
    
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Stage 5 State Tax: ${result5.state_tax:,.0f}")
    print(f"Stage 6 State Tax: ${result6.state_tax:,.0f}")
    print("\nIf both are $0 and you're in PA (or another tax state):")
    print("1. Restart the Streamlit app to pick up code changes")
    print("2. Clear browser cache")
    print("3. Re-run the strategy calculation")
    print("=" * 80)

# Made with Bob
