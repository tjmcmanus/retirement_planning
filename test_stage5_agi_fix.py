"""
Test Stage 5 AGI and Roth Conversion Fix

Verifies that Stage 5 (Social Security) correctly includes Traditional IRA
withdrawals in the AGI calculation when determining Roth conversion amounts.

This test addresses the issue where conversions were calculated without
accounting for Traditional withdrawals needed for buffer replenishment,
causing over-conversions that pushed income into higher tax brackets.
"""

import pytest
from strategy import (
    Stage5SocialSecurity,
    PortfolioBalances,
    MEDICARE_AGE,
    RMD_AGE
)
from config import get_config_manager


def test_stage5_includes_traditional_withdrawals_in_agi():
    """
    Test that Stage 5 includes anticipated Traditional withdrawals in AGI
    calculation for Roth conversion optimization.
    
    Scenario: Year 2036 with significant Traditional withdrawals needed
    for buffer replenishment. The conversion optimizer should account for
    these withdrawals when calculating available bracket room.
    """
    stage = Stage5SocialSecurity()
    
    # Setup: Similar to user's 2036 scenario
    year = 2036
    age_primary = 70
    age_spouse = 69
    
    # Portfolio balances (simplified from user's data)
    balances = PortfolioBalances(
        cash=269_552,
        taxable=412_700,
        traditional=500_000,  # Significant Traditional balance
        roth=200_000,
        daf=0
    )
    
    # Expenses and SS benefits
    expenses = 138_145
    ss_benefits = 62_838
    
    # Target 24% bracket for conversions
    max_conversion_rate = 0.24
    
    # Calculate strategy
    result = stage.calculate_strategy(
        year=year,
        balances=balances,
        expenses=expenses,
        ss_benefits=ss_benefits,
        target_conversion=0,
        prior_magi=300_000,  # For IRMAA calculation
        age_primary=age_primary,
        age_spouse=age_spouse,
        max_conversion_rate=max_conversion_rate,
        start_year=2026,
        growth_rate=1.07
    )
    
    # Verify results
    # 1. Check that Traditional withdrawals occurred
    trad_to_cash = result.transactions.get('traditional_to_cash', 0)
    trad_to_brok = result.transactions.get('traditional_to_brokerage', 0)
    total_trad_withdrawal = trad_to_cash + trad_to_brok
    
    assert total_trad_withdrawal > 0, "Should have Traditional withdrawals for buffer needs"
    
    # 2. Check that Roth conversion is reasonable given the Traditional withdrawals
    roth_conversion = result.transactions.get('traditional_to_roth', 0)
    
    # Calculate what AGI should be
    taxable_ss = result.ss_taxable
    brokerage_ltcg = result.transactions.get('brokerage_ltcg', 0)
    total_agi = taxable_ss + total_trad_withdrawal + roth_conversion + brokerage_ltcg
    
    # 3. Verify AGI matches expected components
    assert abs(result.agi - total_agi) < 100, \
        f"AGI should equal SS + Trad withdrawals + Roth conversion + LTCG: " \
        f"Expected ~${total_agi:,.0f}, got ${result.agi:,.0f}"
    
    # 4. Verify marginal rate is at or below target
    # For 24% bracket in 2036, upper limit is approximately $383,900 for MFJ
    # With significant Traditional withdrawals, conversion should be limited
    assert result.max_rate <= max_conversion_rate + 0.01, \
        f"Marginal rate should be at or below target {max_conversion_rate:.0%}, " \
        f"got {result.max_rate:.0%}"
    
    # 5. Verify conversion is smaller when Traditional withdrawals are large
    # If Traditional withdrawals are > $200k, conversion should be modest
    if total_trad_withdrawal > 200_000:
        assert roth_conversion < 150_000, \
            f"With ${total_trad_withdrawal:,.0f} in Traditional withdrawals, " \
            f"conversion should be limited, got ${roth_conversion:,.0f}"
    
    print(f"\n✓ Stage 5 AGI Fix Test Results:")
    print(f"  Traditional withdrawals: ${total_trad_withdrawal:,.0f}")
    print(f"    - Trad→Cash: ${trad_to_cash:,.0f}")
    print(f"    - Trad→Brok: ${trad_to_brok:,.0f}")
    print(f"  Roth conversion: ${roth_conversion:,.0f}")
    print(f"  Taxable SS: ${taxable_ss:,.0f}")
    print(f"  Total AGI: ${result.agi:,.0f}")
    print(f"  Marginal rate: {result.max_rate:.1%}")
    print(f"  Federal tax: ${result.federal_tax:,.0f}")


def test_stage5_conversion_respects_bracket_with_ss_and_trad():
    """
    Test that conversions stay within target bracket when both SS income
    and Traditional withdrawals are present.
    """
    stage = Stage5SocialSecurity()
    
    year = 2037
    age_primary = 71
    age_spouse = 70
    
    # Scenario: High Traditional withdrawal needs
    balances = PortfolioBalances(
        cash=276_291,
        taxable=381_003,
        traditional=450_000,
        roth=250_000,
        daf=0
    )
    
    expenses = 134_856
    ss_benefits = 126_933  # Higher SS benefits
    
    result = stage.calculate_strategy(
        year=year,
        balances=balances,
        expenses=expenses,
        ss_benefits=ss_benefits,
        target_conversion=0,
        prior_magi=350_000,
        age_primary=age_primary,
        age_spouse=age_spouse,
        max_conversion_rate=0.24,
        start_year=2026,
        growth_rate=1.07
    )
    
    # With higher SS benefits, there should be less room for conversion
    roth_conversion = result.transactions.get('traditional_to_roth', 0)
    
    # Verify marginal rate stays at target
    assert result.max_rate <= 0.25, \
        f"Marginal rate should stay at or below 24% bracket, got {result.max_rate:.1%}"
    
    # Verify AGI components sum correctly
    trad_withdrawal = (result.transactions.get('traditional_to_cash', 0) + 
                      result.transactions.get('traditional_to_brokerage', 0))
    brokerage_ltcg = result.transactions.get('brokerage_ltcg', 0)
    expected_agi = result.ss_taxable + trad_withdrawal + roth_conversion + brokerage_ltcg
    
    assert abs(result.agi - expected_agi) < 100, \
        f"AGI components should sum correctly: Expected ${expected_agi:,.0f}, got ${result.agi:,.0f}"
    
    print(f"\n✓ Stage 5 Bracket Respect Test Results:")
    print(f"  SS benefits: ${ss_benefits:,.0f} (${result.ss_taxable:,.0f} taxable)")
    print(f"  Traditional withdrawals: ${trad_withdrawal:,.0f}")
    print(f"  Roth conversion: ${roth_conversion:,.0f}")
    print(f"  AGI: ${result.agi:,.0f}")
    print(f"  Marginal rate: {result.max_rate:.1%}")


def test_stage5_no_conversion_when_bracket_full():
    """
    Test that no conversion occurs when SS + Traditional withdrawals
    already fill the target bracket.
    """
    stage = Stage5SocialSecurity()
    
    year = 2038
    age_primary = 72
    age_spouse = 71
    
    # Scenario: Very high expenses requiring large Traditional withdrawals
    balances = PortfolioBalances(
        cash=269_713,
        taxable=379_924,
        traditional=400_000,
        roth=300_000,
        daf=0
    )
    
    expenses = 200_000  # High expenses
    ss_benefits = 129_472
    
    result = stage.calculate_strategy(
        year=year,
        balances=balances,
        expenses=expenses,
        ss_benefits=ss_benefits,
        target_conversion=0,
        prior_magi=400_000,
        age_primary=age_primary,
        age_spouse=age_spouse,
        max_conversion_rate=0.24,
        start_year=2026,
        growth_rate=1.07
    )
    
    # With high expenses, Traditional withdrawals should be large
    trad_withdrawal = (result.transactions.get('traditional_to_cash', 0) + 
                      result.transactions.get('traditional_to_brokerage', 0))
    
    # Conversion should be minimal or zero if bracket is already full
    roth_conversion = result.transactions.get('traditional_to_roth', 0)
    
    # If Traditional withdrawals + SS already exceed ~$300k, conversion should be very small
    if result.ss_taxable + trad_withdrawal > 300_000:
        assert roth_conversion < 50_000, \
            f"Conversion should be minimal when bracket is nearly full, got ${roth_conversion:,.0f}"
    
    print(f"\n✓ Stage 5 Full Bracket Test Results:")
    print(f"  Expenses: ${expenses:,.0f}")
    print(f"  SS taxable: ${result.ss_taxable:,.0f}")
    print(f"  Traditional withdrawals: ${trad_withdrawal:,.0f}")
    print(f"  Roth conversion: ${roth_conversion:,.0f}")
    print(f"  AGI: ${result.agi:,.0f}")
    print(f"  Marginal rate: {result.max_rate:.1%}")


if __name__ == "__main__":
    print("Testing Stage 5 AGI and Roth Conversion Fix...")
    print("=" * 70)
    
    test_stage5_includes_traditional_withdrawals_in_agi()
    test_stage5_conversion_respects_bracket_with_ss_and_trad()
    test_stage5_no_conversion_when_bracket_full()
    
    print("\n" + "=" * 70)
    print("✓ All Stage 5 AGI fix tests passed!")

# Made with Bob
