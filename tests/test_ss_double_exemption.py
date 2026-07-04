#!/usr/bin/env python3
"""
Test to verify the SS double-exemption bug in PA state tax calculation.
"""

from strategy import calculate_state_tax

def test_ss_double_exemption():
    """Test that SS is not being double-exempted in PA"""
    
    print("=" * 80)
    print("Testing SS Double-Exemption Bug in PA")
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
    
    # Call state tax as done in Stage 5 (line 4872-4878)
    state_tax, details = calculate_state_tax(
        state_agi=agi,  # $96,500 (includes taxable_ss)
        state='PA',
        year=2034,
        filing_status='married_filing_jointly',
        retirement_income=trad_withdrawal + roth_conversion,  # $0
        ss_benefits=ss_benefits  # $50,000 (FULL amount)
    )
    
    print(f"\nState Tax Calculation (PA):")
    print(f"  State AGI passed: ${agi:,.0f}")
    print(f"  Retirement income exemption: ${details.get('retirement_exemption', 0):,.0f}")
    print(f"  Taxable income: ${details.get('taxable_income', 0):,.0f}")
    print(f"  State tax: ${state_tax:,.0f}")
    
    # What SHOULD happen:
    # - AGI = $96,500 (includes $42,500 taxable SS + $54,000 LTCG)
    # - PA exempts SS: $96,500 - $42,500 = $54,000 (only LTCG remains)
    # - Tax on $54,000 at 3.07% = $1,658
    
    # What ACTUALLY happens:
    # - AGI = $96,500 (includes $42,500 taxable SS + $54,000 LTCG)
    # - PA exempts FULL SS: $96,500 - $50,000 = $46,500
    # - Tax on $46,500 at 3.07% = $1,428
    
    expected_taxable = ltcg_harvested  # Should be $54,000
    actual_taxable = details.get('taxable_income', 0)
    
    print(f"\nAnalysis:")
    print(f"  Expected taxable income: ${expected_taxable:,.0f} (only LTCG)")
    print(f"  Actual taxable income: ${actual_taxable:,.0f}")
    
    if actual_taxable < expected_taxable:
        difference = expected_taxable - actual_taxable
        print(f"  ❌ BUG CONFIRMED: Under-taxed by ${difference:,.0f}")
        print(f"     This is because PA is exempting the FULL SS benefits (${ss_benefits:,.0f})")
        print(f"     but the AGI already only includes TAXABLE SS (${taxable_ss:,.0f})")
        print(f"     Difference: ${ss_benefits:,.0f} - ${taxable_ss:,.0f} = ${ss_benefits - taxable_ss:,.0f}")
        print(f"     This ${ss_benefits - taxable_ss:,.0f} is being incorrectly exempted from LTCG!")
    else:
        print(f"  ✓ Correct calculation")
    
    print("\n" + "=" * 80)
    print("SOLUTION:")
    print("=" * 80)
    print("When calling calculate_state_tax(), pass taxable_ss instead of ss_benefits")
    print("for states that exempt SS. This way, the exemption only removes what was")
    print("actually included in the AGI, not the full SS amount.")
    print("=" * 80)

if __name__ == '__main__':
    test_ss_double_exemption()

# Made with Bob
