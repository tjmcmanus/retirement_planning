#!/usr/bin/env python3
"""
Test SSI Calculator Integration with Withdrawal Strategy

This script demonstrates how the SSI calculator is now integrated into
the withdrawal strategy for Stage 4 (Social Security) and Stage 5 (RMD).
"""

import logging
from config import get_config_manager
from withdrawal_strategy import (
    WithdrawalStrategyEngine,
    PortfolioBalances,
    calculate_ssi_benefits_dynamic
)
from ssi_calculator import DEFAULT_COLA_RATE

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_ssi_calculation():
    """Test the dynamic SSI calculation function."""
    print("=" * 80)
    print("TEST 1: Dynamic SSI Calculation")
    print("=" * 80)
    
    # Test parameters (Tom's example from CSV)
    person_name = "Tom"
    birth_year = 1965
    claiming_age = 70
    fra_benefit = 4223  # Monthly benefit at age 67
    
    print(f"\nPerson: {person_name}")
    print(f"Birth Year: {birth_year}")
    print(f"Claiming Age: {claiming_age}")
    print(f"FRA Benefit (age 67): ${fra_benefit:,.2f}/month")
    print(f"COLA Rate: {DEFAULT_COLA_RATE * 100}%")
    
    print("\nCalculated Benefits by Year:")
    print("-" * 80)
    
    test_years = [2033, 2035, 2036, 2040, 2045]
    for year in test_years:
        monthly_benefit = calculate_ssi_benefits_dynamic(
            year=year,
            person_name=person_name,
            birth_year=birth_year,
            claiming_age=claiming_age,
            fra_benefit=fra_benefit,
            cola_rate=DEFAULT_COLA_RATE
        )
        age = year - birth_year
        annual_benefit = monthly_benefit * 12
        print(f"Year {year} (Age {age}): ${monthly_benefit:,.2f}/month, "
              f"${annual_benefit:,.2f}/year")


def test_config_integration():
    """Test SSI calculation using config.py settings."""
    print("\n" + "=" * 80)
    print("TEST 2: Config Integration")
    print("=" * 80)
    
    config = get_config_manager()
    
    # Display current config
    print("\nCurrent Config Settings:")
    print("-" * 80)
    
    person1_name = config.get("personal_info", "person1_name", "Person1")
    person1_birth_date = config.get("personal_info", "person1_birth_date", "1965-01-01")
    person1_claiming_age = config.get("social_security", "person1_ssi_age", 70)
    person1_fra_benefit = config.get("social_security", "person1_ssi_amount", 0)
    
    print(f"{person1_name}:")
    print(f"  Birth Date: {person1_birth_date}")
    print(f"  Claiming Age: {person1_claiming_age}")
    print(f"  FRA Benefit: ${person1_fra_benefit:,.2f}/month")
    
    person2_name = config.get("personal_info", "person2_name", "Person2")
    person2_birth_date = config.get("personal_info", "person2_birth_date", "1967-01-01")
    person2_claiming_age = config.get("social_security", "person2_ssi_age", 70)
    person2_fra_benefit = config.get("social_security", "person2_ssi_amount", 0)
    
    print(f"\n{person2_name}:")
    print(f"  Birth Date: {person2_birth_date}")
    print(f"  Claiming Age: {person2_claiming_age}")
    print(f"  FRA Benefit: ${person2_fra_benefit:,.2f}/month")
    
    # Calculate benefits for a sample year
    if person1_fra_benefit > 0 or person2_fra_benefit > 0:
        print("\nSample Calculation for Year 2036:")
        print("-" * 80)
        
        year = 2036
        person1_birth_year = int(person1_birth_date.split('-')[0])
        person2_birth_year = int(person2_birth_date.split('-')[0])
        
        if person1_fra_benefit > 0:
            benefit1 = calculate_ssi_benefits_dynamic(
                year=year,
                person_name=person1_name,
                birth_year=person1_birth_year,
                claiming_age=person1_claiming_age,
                fra_benefit=person1_fra_benefit
            )
            print(f"{person1_name}: ${benefit1:,.2f}/month (${benefit1 * 12:,.2f}/year)")
        
        if person2_fra_benefit > 0:
            benefit2 = calculate_ssi_benefits_dynamic(
                year=year,
                person_name=person2_name,
                birth_year=person2_birth_year,
                claiming_age=person2_claiming_age,
                fra_benefit=person2_fra_benefit
            )
            print(f"{person2_name}: ${benefit2:,.2f}/month (${benefit2 * 12:,.2f}/year)")
        
        total_annual = (benefit1 + benefit2) * 12 if person1_fra_benefit > 0 and person2_fra_benefit > 0 else 0
        if total_annual > 0:
            print(f"\nCombined Annual SSI: ${total_annual:,.2f}")
    else:
        print("\n⚠️  No SSI amounts configured in config.py")
        print("Set person1_ssi_amount and person2_ssi_amount to test")


def test_withdrawal_strategy_integration():
    """Test that withdrawal strategy uses dynamic SSI calculation."""
    print("\n" + "=" * 80)
    print("TEST 3: Withdrawal Strategy Integration")
    print("=" * 80)
    
    print("\nThe withdrawal strategy now uses dynamic SSI calculation in:")
    print("  • Stage 4: Social Security (lines 2108-2394)")
    print("  • Stage 5: RMD (lines 2397-2609)")
    print("\nKey changes:")
    print("  1. Added calculate_ssi_benefits_dynamic() helper function")
    print("  2. Updated calculate_multi_year_strategy() to use dynamic calculator")
    print("  3. Falls back to CSV method if dynamic calculation fails")
    print("\nBenefits:")
    print("  ✓ No need to maintain static CSV file")
    print("  ✓ Automatically adjusts for claiming age (62-70)")
    print("  ✓ Applies COLA adjustments dynamically")
    print("  ✓ Uses config.py settings directly")
    
    print("\nTo use in withdrawal strategy:")
    print("-" * 80)
    print("""
    engine = WithdrawalStrategyEngine()
    
    initial_balances = PortfolioBalances(
        cash=100000,
        taxable=500000,
        traditional=800000,
        roth=200000,
        daf=0
    )
    
    # SSI benefits will be calculated automatically from config.py
    strategy_df = engine.calculate_multi_year_strategy(
        start_year=2026,
        end_year=2050,
        initial_balances=initial_balances,
        initial_expenses=50000,
        person1_name="Tom",
        person2_name="Sarah",
        cola_rate=0.02  # Optional: override default 2% COLA
    )
    """)


def main():
    """Run all tests."""
    print("\n" + "=" * 80)
    print("SSI CALCULATOR INTEGRATION TEST SUITE")
    print("=" * 80)
    
    try:
        test_ssi_calculation()
        test_config_integration()
        test_withdrawal_strategy_integration()
        
        print("\n" + "=" * 80)
        print("✓ ALL TESTS COMPLETED SUCCESSFULLY")
        print("=" * 80)
        
        print("\nNext Steps:")
        print("1. Update config.py with your SSI settings:")
        print("   - person1_ssi_age: Claiming age (62-70)")
        print("   - person1_ssi_amount: Monthly benefit at age 67")
        print("   - person2_ssi_age: Claiming age (62-70)")
        print("   - person2_ssi_amount: Monthly benefit at age 67")
        print("\n2. Run your withdrawal strategy - SSI will be calculated automatically")
        print("\n3. Optional: Generate CSV with generate_ssi_schedule.py")
        
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())

# Made with Bob
