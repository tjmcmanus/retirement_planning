"""
Test LTCG estimation in buffer needs calculation.

This test verifies that the calculate_anticipated_buffer_needs function
correctly estimates LTCG from anticipated brokerage withdrawals using
the cost basis ratio from the BrokerageAccount.
"""

import pytest
from strategy import (
    calculate_anticipated_buffer_needs,
    PortfolioBalances,
    BrokerageAccount,
    BROKERAGE_LTCG_RATIO
)


def test_ltcg_estimation_with_brokerage_account():
    """Test LTCG estimation using actual brokerage account tracking."""
    # Create a brokerage account with known LTCG ratio
    brokerage_account = BrokerageAccount()
    
    # Add initial transfer: $100k with $100k basis (no gains yet)
    brokerage_account.add_transfer(2024, 100000, "initial")
    
    # Simulate growth: 50% gain (value = $150k, basis = $100k, gains = $50k)
    brokerage_account.apply_annual_growth(1.50, 2025)
    
    # Verify LTCG ratio: $50k gains / $150k value = 33.33%
    assert abs(brokerage_account.ltcg_ratio - 0.3333) < 0.01
    
    # Create portfolio balances with brokerage needing withdrawal
    balances = PortfolioBalances(
        cash=5000,  # Low cash, will need replenishment
        taxable=150000,  # Brokerage account value
        traditional=500000,
        roth=200000,
        daf=0
    )
    
    # Calculate anticipated needs with brokerage account
    anticipated_needs = calculate_anticipated_buffer_needs(
        balances=balances,
        expenses=50000,
        age_primary=62,
        federal_tax=5000,
        irmaa_penalty=0,
        aca_premium=0,
        medical_costs=0,
        brokerage_account=brokerage_account
    )
    
    # Verify that brokerage withdrawal is anticipated
    assert anticipated_needs['brokerage_to_cash'] > 0
    
    # Verify LTCG estimation: should be ~33.33% of brokerage withdrawal
    expected_ltcg = anticipated_needs['brokerage_to_cash'] * brokerage_account.ltcg_ratio
    assert abs(anticipated_needs['estimated_ltcg'] - expected_ltcg) < 1.0
    
    print(f"✓ Brokerage withdrawal: ${anticipated_needs['brokerage_to_cash']:,.0f}")
    print(f"✓ Estimated LTCG: ${anticipated_needs['estimated_ltcg']:,.0f}")
    print(f"✓ LTCG ratio used: {brokerage_account.ltcg_ratio:.1%}")


def test_ltcg_estimation_without_brokerage_account():
    """Test LTCG estimation using default ratio when no brokerage account provided."""
    # Create portfolio balances
    balances = PortfolioBalances(
        cash=5000,
        taxable=150000,
        traditional=500000,
        roth=200000,
        daf=0
    )
    
    # Calculate anticipated needs WITHOUT brokerage account
    anticipated_needs = calculate_anticipated_buffer_needs(
        balances=balances,
        expenses=50000,
        age_primary=62,
        federal_tax=5000,
        irmaa_penalty=0,
        aca_premium=0,
        medical_costs=0,
        brokerage_account=None  # No brokerage account tracking
    )
    
    # Verify that brokerage withdrawal is anticipated
    assert anticipated_needs['brokerage_to_cash'] > 0
    
    # Verify LTCG estimation uses default 40% ratio
    expected_ltcg = anticipated_needs['brokerage_to_cash'] * BROKERAGE_LTCG_RATIO
    assert abs(anticipated_needs['estimated_ltcg'] - expected_ltcg) < 1.0
    
    print(f"✓ Brokerage withdrawal: ${anticipated_needs['brokerage_to_cash']:,.0f}")
    print(f"✓ Estimated LTCG (default): ${anticipated_needs['estimated_ltcg']:,.0f}")
    print(f"✓ Default LTCG ratio: {BROKERAGE_LTCG_RATIO:.1%}")


def test_ltcg_estimation_no_brokerage_withdrawal():
    """Test that LTCG is zero when no brokerage withdrawal is needed."""
    # Create portfolio with sufficient cash AND no brokerage account
    balances = PortfolioBalances(
        cash=100000,  # Plenty of cash
        taxable=0,  # No brokerage account
        traditional=500000,
        roth=200000,
        daf=0
    )
    
    # Calculate anticipated needs
    anticipated_needs = calculate_anticipated_buffer_needs(
        balances=balances,
        expenses=50000,
        age_primary=62,
        federal_tax=5000,
        irmaa_penalty=0,
        aca_premium=0,
        medical_costs=0,
        brokerage_account=None
    )
    
    # Verify no brokerage withdrawal and no LTCG
    assert anticipated_needs['brokerage_to_cash'] == 0
    assert anticipated_needs['estimated_ltcg'] == 0
    
    print("✓ No brokerage withdrawal needed, LTCG = $0")


def test_ltcg_estimation_high_gain_scenario():
    """Test LTCG estimation with high gains (e.g., 100% gain)."""
    # Create brokerage account with 100% gain
    brokerage_account = BrokerageAccount()
    brokerage_account.add_transfer(2024, 100000, "initial")
    brokerage_account.apply_annual_growth(2.0, 2025)  # 100% gain
    
    # LTCG ratio should be 50% (gains = value / 2)
    assert abs(brokerage_account.ltcg_ratio - 0.50) < 0.01
    
    # Create portfolio needing withdrawal
    balances = PortfolioBalances(
        cash=5000,
        taxable=200000,  # Account value after 100% gain
        traditional=500000,
        roth=200000,
        daf=0
    )
    
    # Calculate anticipated needs
    anticipated_needs = calculate_anticipated_buffer_needs(
        balances=balances,
        expenses=50000,
        age_primary=62,
        federal_tax=5000,
        irmaa_penalty=0,
        aca_premium=0,
        medical_costs=0,
        brokerage_account=brokerage_account
    )
    
    # Verify LTCG is 50% of withdrawal
    if anticipated_needs['brokerage_to_cash'] > 0:
        expected_ltcg = anticipated_needs['brokerage_to_cash'] * 0.50
        assert abs(anticipated_needs['estimated_ltcg'] - expected_ltcg) < 1.0
        
        print(f"✓ High gain scenario (100% gain):")
        print(f"  Brokerage withdrawal: ${anticipated_needs['brokerage_to_cash']:,.0f}")
        print(f"  Estimated LTCG (50%): ${anticipated_needs['estimated_ltcg']:,.0f}")


def test_ltcg_estimation_low_gain_scenario():
    """Test LTCG estimation with low gains (e.g., 10% gain)."""
    # Create brokerage account with 10% gain
    brokerage_account = BrokerageAccount()
    brokerage_account.add_transfer(2024, 100000, "initial")
    brokerage_account.apply_annual_growth(1.10, 2025)  # 10% gain
    
    # LTCG ratio should be ~9.09% (gains = 10k, value = 110k)
    expected_ratio = 10000 / 110000
    assert abs(brokerage_account.ltcg_ratio - expected_ratio) < 0.001
    
    # Create portfolio needing withdrawal
    balances = PortfolioBalances(
        cash=5000,
        taxable=110000,
        traditional=500000,
        roth=200000,
        daf=0
    )
    
    # Calculate anticipated needs
    anticipated_needs = calculate_anticipated_buffer_needs(
        balances=balances,
        expenses=50000,
        age_primary=62,
        federal_tax=5000,
        irmaa_penalty=0,
        aca_premium=0,
        medical_costs=0,
        brokerage_account=brokerage_account
    )
    
    # Verify LTCG is ~9.09% of withdrawal
    if anticipated_needs['brokerage_to_cash'] > 0:
        expected_ltcg = anticipated_needs['brokerage_to_cash'] * expected_ratio
        assert abs(anticipated_needs['estimated_ltcg'] - expected_ltcg) < 1.0
        
        print(f"✓ Low gain scenario (10% gain):")
        print(f"  Brokerage withdrawal: ${anticipated_needs['brokerage_to_cash']:,.0f}")
        print(f"  Estimated LTCG (~9%): ${anticipated_needs['estimated_ltcg']:,.0f}")


if __name__ == "__main__":
    print("Testing LTCG Estimation in Buffer Needs Calculation\n")
    print("=" * 60)
    
    print("\n1. Testing with brokerage account tracking:")
    test_ltcg_estimation_with_brokerage_account()
    
    print("\n2. Testing without brokerage account (default ratio):")
    test_ltcg_estimation_without_brokerage_account()
    
    print("\n3. Testing no brokerage withdrawal scenario:")
    test_ltcg_estimation_no_brokerage_withdrawal()
    
    print("\n4. Testing high gain scenario:")
    test_ltcg_estimation_high_gain_scenario()
    
    print("\n5. Testing low gain scenario:")
    test_ltcg_estimation_low_gain_scenario()
    
    print("\n" + "=" * 60)
    print("All LTCG estimation tests passed! ✓")

# Made with Bob
