#!/usr/bin/env python3
"""
Test AGICalculator Integration in Stages 3 & 4

Validates that the new AGICalculator produces correct AGI and tax calculations
that match the expected values from manual bracket-fill analysis.
"""

import sys
sys.path.insert(0, '.')

from strategy_core.agi_calculator import AGICalculator
from strategy_core.tax_calculator import TaxCalculator

def test_2027_bracket_fill_scenario():
    """
    Test 2027 scenario matching bracket_fill_full_agi.py expected values.
    
    2027 scenario: Tom 61, Sarah 60 (MFJ)
    - Traditional withdrawal: $73,083 (spending shortfall)
    - Roth conversion: $0 (no bracket space left)
    - Brokerage LTCG: $2,233
    - Brokerage basis: $3,350
    - DAF: $60,000 (stock transfer)
    """
    
    print("=" * 70)
    print("TEST: 2027 Bracket-Fill Scenario (AGI Calculator Integration)")
    print("=" * 70)
    print()
    
    # Setup
    year = 2027
    filing_status = 'married_filing_jointly'
    age_primary = 61
    age_spouse = 60
    
    trad_withdrawal = 73083
    roth_conversion = 0
    brokerage_ltcg = 2233
    brokerage_basis = 3350
    daf_fmv = 60000
    
    # Create calculator
    tax_calc = TaxCalculator()
    agi_calc = AGICalculator(tax_calc)
    
    # Calculate
    result = agi_calc.calculate_agi_and_taxes(
        year=year,
        filing_status=filing_status,
        age_primary=age_primary,
        age_spouse=age_spouse,
        traditional_withdrawal=trad_withdrawal,
        roth_conversion=roth_conversion,
        brokerage_ltcg=brokerage_ltcg,
        brokerage_basis=brokerage_basis,
        daf_fmv=daf_fmv,
        state='PA',
        pa_rate=0.0573,
        property_tax=0.0,
        daf_carryforward_prior=0.0,
        tax_calculator=tax_calc
    )
    
    # Print results
    print("INPUTS:")
    print(f"  Traditional withdrawal:  ${trad_withdrawal:>10,.0f}")
    print(f"  Roth conversion:         ${roth_conversion:>10,.0f}")
    print(f"  Brokerage basis:         ${brokerage_basis:>10,.0f}")
    print(f"  Brokerage LTCG:          ${brokerage_ltcg:>10,.0f}")
    print(f"  DAF FMV:                 ${daf_fmv:>10,.0f}")
    print()
    
    print("AGI COMPONENTS:")
    print(f"  Gross ordinary income:   ${result['gross_ordinary']:>10,.0f}")
    print(f"    = Trad + Roth (NOT basis)")
    print(f"  LTCG:                    ${brokerage_ltcg:>10,.0f}")
    print(f"  Pre-deduction AGI:       ${result['agi_pre_deduction']:>10,.0f}")
    print()
    print(f"  NOTE: Brokerage basis (${brokerage_basis:,.0f}) is NOT included in income.")
    print(f"        Basis is return of capital. Only gain (${brokerage_ltcg:,.0f}) is taxable.")
    print()
    
    print("DAF DEDUCTION (30% AGI Limit):")
    print(f"  30% of AGI:              ${result['daf_30pct_limit']:>10,.0f}")
    print(f"  DAF FMV available:       ${daf_fmv:>10,.0f}")
    print(f"  Deductible this year:    ${result['daf_deductible_this_year']:>10,.0f}")
    print(f"  Carryforward to 2028:    ${result['daf_carryforward_new']:>10,.0f}")
    print()
    
    print("DEDUCTION CHOICE:")
    print(f"  Standard deduction:      ${result['std_deduction']:>10,.0f}")
    print(f"  SALT (PA + property):    ${result['salt']:>10,.0f}")
    print(f"  Itemized (DAF + SALT):   ${result['itemized_deduction']:>10,.0f}")
    print(f"  Deduction chosen:        ${result['deduction']:>10,.0f}")
    print(f"  Type:                    {result['deduction_type']}")
    print()
    
    print("TAXABLE INCOME:")
    print(f"  Gross ordinary:          ${result['gross_ordinary']:>10,.0f}")
    print(f"  Less deduction:          ${result['deduction']:>10,.0f}")
    print(f"  Taxable ordinary:        ${result['taxable_ordinary']:>10,.0f}")
    print(f"  LTCG (stacked on top):   ${brokerage_ltcg:>10,.0f}")
    print()
    
    print("TAXES:")
    print(f"  Federal ordinary:        ${result['federal_ordinary_tax']:>10,.0f}")
    print(f"  Federal LTCG:            ${result['ltcg_tax']:>10,.0f}")
    print(f"  PA state tax:            ${result['state_tax']:>10,.0f}")
    print(f"  TOTAL TAX 2027:          ${result['total_tax']:>10,.0f}")
    print()
    
    # Validation checks
    print("VALIDATION CHECKS:")
    print()
    
    checks_passed = 0
    checks_total = 0
    
    # Check 1: AGI calculation (basis NOT included)
    expected_gross_ordinary = trad_withdrawal + roth_conversion
    if result['gross_ordinary'] == expected_gross_ordinary:
        print("  ✓ Gross ordinary income correct (basis NOT included)")
        checks_passed += 1
    else:
        print(f"  ✗ Gross ordinary: expected {expected_gross_ordinary:,.0f}, got {result['gross_ordinary']:,.0f}")
    checks_total += 1
    
    # Check 2: Pre-deduction AGI includes only LTCG gain (not basis)
    expected_agi = expected_gross_ordinary + brokerage_ltcg
    if result['agi_pre_deduction'] == expected_agi:
        print("  ✓ Pre-deduction AGI correct (includes LTCG)")
        checks_passed += 1
    else:
        print(f"  ✗ AGI: expected {expected_agi:,.0f}, got {result['agi_pre_deduction']:,.0f}")
    checks_total += 1
    
    # Check 3: DAF deduction respects 30% limit
    if result['daf_deductible_this_year'] <= result['daf_30pct_limit']:
        print("  ✓ DAF deduction respects 30% AGI limit")
        checks_passed += 1
    else:
        print(f"  ✗ DAF deduction {result['daf_deductible_this_year']:,.0f} exceeds 30% limit {result['daf_30pct_limit']:,.0f}")
    checks_total += 1
    
    # Check 4: DAF carryforward is correct
    expected_carryforward = daf_fmv - result['daf_deductible_this_year']
    if result['daf_carryforward_new'] == expected_carryforward:
        print("  ✓ DAF carryforward correct")
        checks_passed += 1
    else:
        print(f"  ✗ Carryforward: expected {expected_carryforward:,.0f}, got {result['daf_carryforward_new']:,.0f}")
    checks_total += 1
    
    # Check 5: Standard deduction (MFJ age 61/60 in 2027 should be around $35,500)
    if result['std_deduction'] > 34000 and result['std_deduction'] < 37000:
        print(f"  ✓ Standard deduction reasonable: ${result['std_deduction']:,.0f}")
        checks_passed += 1
    else:
        print(f"  ✗ Standard deduction seems off: ${result['std_deduction']:,.0f}")
    checks_total += 1
    
    # Check 6: Total tax should be roughly $4,100-4,200
    # With standard deduction of $35,500, taxable ordinary is $37,583 (lower now that basis is excluded)
    # At ~12% federal + 5.73% PA, total should be around $4,100-$4,200
    if result['total_tax'] > 3800 and result['total_tax'] < 4400:
        print(f"  ✓ Total tax in expected range: ${result['total_tax']:,.0f}")
        checks_passed += 1
    else:
        print(f"  ✗ Total tax out of expected range: ${result['total_tax']:,.0f} (expected ~$4,100-4,200)")
    checks_total += 1
    
    print()
    print(f"RESULT: {checks_passed}/{checks_total} validation checks passed")
    print()
    
    return checks_passed == checks_total

def test_no_daf_scenario():
    """Test scenario without DAF contribution."""
    print("=" * 70)
    print("TEST: Scenario Without DAF (Standard Deduction Should Apply)")
    print("=" * 70)
    print()
    
    year = 2027
    filing_status = 'married_filing_jointly'
    age_primary = 61
    age_spouse = 60
    
    trad_withdrawal = 50000
    roth_conversion = 10000
    brokerage_ltcg = 5000
    brokerage_basis = 1000
    daf_fmv = 0  # No DAF this year
    
    tax_calc = TaxCalculator()
    agi_calc = AGICalculator(tax_calc)
    
    result = agi_calc.calculate_agi_and_taxes(
        year=year,
        filing_status=filing_status,
        age_primary=age_primary,
        age_spouse=age_spouse,
        traditional_withdrawal=trad_withdrawal,
        roth_conversion=roth_conversion,
        brokerage_ltcg=brokerage_ltcg,
        brokerage_basis=brokerage_basis,
        daf_fmv=daf_fmv,
        state='PA',
        pa_rate=0.0573,
        property_tax=0.0,
        daf_carryforward_prior=0.0,
        tax_calculator=tax_calc
    )
    
    print(f"  Gross ordinary:     ${result['gross_ordinary']:>10,.0f}")
    print(f"  Deduction type:     {result['deduction_type']}")
    print(f"  Deduction amount:   ${result['deduction']:>10,.0f}")
    print(f"  Taxable ordinary:   ${result['taxable_ordinary']:>10,.0f}")
    print(f"  Total tax:          ${result['total_tax']:>10,.0f}")
    print()
    
    # Validation: should use standard deduction
    if result['deduction_type'] == 'STANDARD':
        print("  ✓ Standard deduction chosen (no DAF)")
        return True
    else:
        print(f"  ✗ Expected STANDARD deduction, got {result['deduction_type']}")
        return False

if __name__ == '__main__':
    try:
        test1_passed = test_2027_bracket_fill_scenario()
        print()
        test2_passed = test_no_daf_scenario()
        print()
        
        if test1_passed and test2_passed:
            print("=" * 70)
            print("ALL TESTS PASSED ✓")
            print("=" * 70)
            sys.exit(0)
        else:
            print("=" * 70)
            print("SOME TESTS FAILED ✗")
            print("=" * 70)
            sys.exit(1)
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
