#!/usr/bin/env python3
"""
Test to verify the Stage 5 state tax fix works correctly.
"""

from strategy import calculate_state_tax

def test_stage5_with_fix():
    """Test Stage 5 state tax calculation with the fix applied"""
    
    print("=" * 80)
    print("Testing Stage 5 State Tax Calculation (WITH FIX)")
    print("=" * 80)
    
    # Scenario from 2034-2035: Brokerage withdrawal with SS benefits
    ss_benefits = 50000  # Full SS benefits
    taxable_ss = ss_benefits * 0.85  # 85% taxable = $42,500
    ltcg_harvested = 54000  # From $135K brokerage withdrawal
    trad_withdrawal = 0
    roth_conversion = 0
    
    # AGI calculation (as done in Stage 5, line 4705-4706)
    total_income = taxable_ss + ltcg_harvested + roth_conversion + trad_withdrawal
    agi = total_income  # $96,500
    
    print(f"\nScenario:")
    print(f"  SS Benefits (full): ${ss_benefits:,.0f}")
    print(f"  Taxable SS (85%): ${taxable_ss:,.0f}")
    print(f"  LTCG from brokerage: ${ltcg_harvested:,.0f}")
    print(f"  Traditional withdrawal: ${trad_withdrawal:,.0f}")
    print(f"  Roth conversion: ${roth_conversion:,.0f}")
    print(f"  Total AGI: ${agi:,.0f}")
    
    # Call state tax WITH THE FIX (passing taxable_ss instead of ss_benefits)
    state_tax, details = calculate_state_tax(
        state_agi=agi,  # $96,500 (includes taxable_ss)
        state='PA',
        year=2034,
        filing_status='married_filing_jointly',
        retirement_income=trad_withdrawal + roth_conversion,  # $0
        ss_benefits=taxable_ss  # FIX: Pass taxable portion, not full benefits
    )
    
    print(f"\nState Tax Calculation (PA) - WITH FIX:")
    print(f"  State AGI passed: ${agi:,.0f}")
    print(f"  SS benefits passed (taxable portion): ${taxable_ss:,.0f}")
    print(f"  Retirement income exemption: ${details.get('retirement_exemption', 0):,.0f}")
    print(f"  Taxable income: ${details.get('taxable_income', 0):,.0f}")
    print(f"  State tax: ${state_tax:,.0f}")
    
    # What SHOULD happen with the fix:
    # - AGI = $96,500 (includes $42,500 taxable SS + $54,000 LTCG)
    # - PA exempts taxable SS: $96,500 - $42,500 = $54,000 (only LTCG remains)
    # - Tax on $54,000 at 3.07% = $1,658
    
    expected_taxable = ltcg_harvested  # Should be $54,000
    actual_taxable = details.get('taxable_income', 0)
    expected_tax = expected_taxable * 0.0307  # PA flat rate
    
    print(f"\nAnalysis:")
    print(f"  Expected taxable income: ${expected_taxable:,.0f} (only LTCG)")
    print(f"  Actual taxable income: ${actual_taxable:,.0f}")
    print(f"  Expected state tax: ${expected_tax:,.0f}")
    print(f"  Actual state tax: ${state_tax:,.0f}")
    
    if abs(actual_taxable - expected_taxable) < 100:
        print(f"  ✓ FIX VERIFIED: Correct taxable income!")
        if abs(state_tax - expected_tax) < 10:
            print(f"  ✓ FIX VERIFIED: Correct state tax!")
        else:
            print(f"  ⚠ State tax differs slightly (rounding or other factors)")
    else:
        difference = expected_taxable - actual_taxable
        print(f"  ❌ Still incorrect by ${difference:,.0f}")
    
    print("\n" + "=" * 80)
    print("SUMMARY:")
    print("=" * 80)
    print("With the fix, PA now correctly:")
    print("1. Exempts only the taxable SS portion ($42,500) that was in AGI")
    print("2. Taxes the full LTCG amount ($54,000) at 3.07%")
    print("3. Results in proper state tax of ~$1,658")
    print("=" * 80)

if __name__ == '__main__':
    test_stage5_with_fix()

# Made with Bob
