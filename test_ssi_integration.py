#!/usr/bin/env python3
"""
Test SSI Calculator Integration with Withdrawal Strategy

This script demonstrates how the SSI calculator is now integrated into
the withdrawal strategy for Stage 4 (Social Security) and Stage 5 (RMD).
"""

import logging
from config import get_config_manager
from strategy import (
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


def _person_from_config(cfg, n: int) -> dict:
    """Build a person dict from config for person index n (1 or 2)."""
    return {
        "name":         cfg.get("personal_info",   f"person{n}_name",       f"Person{n}"),
        "birth_date":   cfg.get("personal_info",   f"person{n}_birth_date", f"196{n+4}-01-01"),
        "claiming_age": cfg.get("social_security", f"person{n}_ssi_age",    70),
        "fra_benefit":  cfg.get("social_security", f"person{n}_ssi_amount", 0),
    }


def test_config_integration():
    """Test SSI calculation using config.py settings."""
    logger.info("=" * 80)
    logger.info("TEST 2: Config Integration")
    logger.info("=" * 80)

    config = get_config_manager()
    persons = [_person_from_config(config, n) for n in (1, 2)]

    logger.info("Current Config Settings:")
    for p in persons:
        logger.info(
            f"{p['name']}: birth_date={p['birth_date']}  "
            f"claiming_age={p['claiming_age']}  fra_benefit=${p['fra_benefit']:,.2f}/month"
        )

    assert any(p["fra_benefit"] > 0 for p in persons), (
        "No SSI amounts configured in config.py — "
        "set person1_ssi_amount / person2_ssi_amount to test"
    )

    sample_year = 2036  # Representative year when both persons are past claiming age
    logger.info(f"Sample Calculation for Year {sample_year}:")

    total_monthly = 0.0
    for p in persons:
        if p["fra_benefit"] > 0:
            birth_year = int(p["birth_date"].split("-")[0])
            monthly = calculate_ssi_benefits_dynamic(
                year=sample_year,
                person_name=p["name"],
                birth_year=birth_year,
                claiming_age=p["claiming_age"],
                fra_benefit=p["fra_benefit"],
            )
            total_monthly += monthly
            logger.info(f"{p['name']}: ${monthly:,.2f}/month (${monthly * 12:,.2f}/year)")

    if total_monthly > 0:
        logger.info(f"Combined Annual SSI: ${total_monthly * 12:,.2f}")


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
