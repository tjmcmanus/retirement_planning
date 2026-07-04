#!/usr/bin/env python3
"""
Test to verify state tax calculation on brokerage withdrawals in Stage 5 and Stage 6.

This test checks that when money moves from Brokerage to Cash (containing LTCG),
it is properly taxed at the state level.
"""

import sys
import pandas as pd
from strategy import calculate_state_tax

def test_brokerage_withdrawal_state_tax():
    """Test that brokerage withdrawals are properly taxed at state level"""
    
    print("=" * 80)
    print("Testing State Tax on Brokerage Withdrawals")
    print("=" * 80)
    
    # Scenario: $135,000 moved from Brokerage to Cash
    # Assume 40% is LTCG = $54,000 taxable
    brokerage_withdrawal = 135000
    ltcg_portion = brokerage_withdrawal * 0.40  # $54,000
    
    # Test Case 1: California (high-tax state)
    print("\n--- Test Case 1: California ---")
    state_agi = ltcg_portion  # Only LTCG in AGI
    retirement_income = 0  # Brokerage withdrawal is NOT retirement income
    ss_benefits = 0
    
    state_tax_ca, details_ca = calculate_state_tax(
        state_agi=state_agi,
        state='CA',
        year=2034,
        filing_status='married_filing_jointly',
        retirement_income=retirement_income,
        ss_benefits=ss_benefits
    )
    
    print(f"Brokerage withdrawal: ${brokerage_withdrawal:,.0f}")
    print(f"LTCG portion (40%): ${ltcg_portion:,.0f}")
    print(f"State AGI: ${state_agi:,.0f}")
    print(f"Retirement income exemption: ${details_ca.get('retirement_exemption', 0):,.0f}")
    print(f"Taxable income: ${details_ca.get('taxable_income', 0):,.0f}")
    print(f"State tax (CA): ${state_tax_ca:,.0f}")
    
    if state_tax_ca == 0:
        print("❌ ERROR: State tax is $0 on $54,000 LTCG in California!")
    else:
        print(f"✓ State tax calculated: ${state_tax_ca:,.0f}")
    
    # Test Case 2: Pennsylvania (retirement-friendly, but LTCG should still be taxed)
    print("\n--- Test Case 2: Pennsylvania ---")
    state_tax_pa, details_pa = calculate_state_tax(
        state_agi=state_agi,
        state='PA',
        year=2034,
        filing_status='married_filing_jointly',
        retirement_income=retirement_income,
        ss_benefits=ss_benefits
    )
    
    print(f"State AGI: ${state_agi:,.0f}")
    print(f"Retirement income exemption: ${details_pa.get('retirement_exemption', 0):,.0f}")
    print(f"Taxable income: ${details_pa.get('taxable_income', 0):,.0f}")
    print(f"State tax (PA): ${state_tax_pa:,.0f}")
    
    # PA exempts retirement income but NOT capital gains
    # However, if retirement_income=0, no exemption should apply
    if state_tax_pa == 0 and ltcg_portion > 0:
        print("❌ ERROR: State tax is $0 on LTCG in Pennsylvania!")
    else:
        print(f"✓ State tax calculated: ${state_tax_pa:,.0f}")
    
    # Test Case 3: With Traditional IRA withdrawal + Brokerage
    print("\n--- Test Case 3: Traditional IRA + Brokerage (PA) ---")
    trad_withdrawal = 50000
    total_agi = trad_withdrawal + ltcg_portion  # $104,000
    
    state_tax_pa_mixed, details_pa_mixed = calculate_state_tax(
        state_agi=total_agi,
        state='PA',
        year=2034,
        filing_status='married_filing_jointly',
        retirement_income=trad_withdrawal,  # Only IRA withdrawal
        ss_benefits=ss_benefits
    )
    
    print(f"Traditional IRA withdrawal: ${trad_withdrawal:,.0f}")
    print(f"LTCG from brokerage: ${ltcg_portion:,.0f}")
    print(f"Total State AGI: ${total_agi:,.0f}")
    print(f"Retirement income exemption: ${details_pa_mixed.get('retirement_exemption', 0):,.0f}")
    print(f"Taxable income: ${details_pa_mixed.get('taxable_income', 0):,.0f}")
    print(f"State tax (PA): ${state_tax_pa_mixed:,.0f}")
    
    # PA should exempt the $50k IRA withdrawal but tax the $54k LTCG
    expected_taxable = ltcg_portion  # $54,000
    actual_taxable = details_pa_mixed.get('taxable_income', 0)
    
    if abs(actual_taxable - expected_taxable) < 100:
        print(f"✓ Correct: PA exempted IRA withdrawal, taxing only LTCG")
    else:
        print(f"❌ ERROR: Expected taxable income ~${expected_taxable:,.0f}, got ${actual_taxable:,.0f}")
    
    print("\n" + "=" * 80)
    print("Summary:")
    print("=" * 80)
    print("The issue is that brokerage withdrawals (LTCG) should ALWAYS be included")
    print("in state AGI and taxed accordingly. Retirement income exemptions should")
    print("only apply to IRA/401k distributions, NOT to capital gains from brokerage.")
    print("=" * 80)

if __name__ == '__main__':
    test_brokerage_withdrawal_state_tax()

# Made with Bob
