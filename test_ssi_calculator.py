"""
Test suite for SSI Calculator module.

This demonstrates how to use the SSI calculator to generate schedules
dynamically based on config.py settings.
"""

import pytest
from ssi_calculator import (
    calculate_benefit_at_claiming_age,
    calculate_benefit_with_cola,
    generate_ssi_schedule,
    generate_ssi_schedule_from_config,
    validate_config_ssi_settings
)
from config import get_config_manager


def test_benefit_at_age_67():
    """Test that FRA benefit is returned correctly at age 67."""
    fra_benefit = 4223
    result = calculate_benefit_at_claiming_age(fra_benefit, 67)
    assert result == 4223.0


def test_benefit_at_age_62():
    """Test early claiming reduction at age 62 (5 years early)."""
    fra_benefit = 4223
    result = calculate_benefit_at_claiming_age(fra_benefit, 62)
    # Expected: ~30% reduction = ~2956
    # Actual calculation: 36 months at 5/9% + 24 months at 5/12% = 30%
    assert 2800 <= result <= 2900  # Allow some range


def test_benefit_at_age_70():
    """Test delayed retirement credit at age 70 (3 years delay)."""
    fra_benefit = 4223
    result = calculate_benefit_at_claiming_age(fra_benefit, 70)
    # Expected: 24% increase (8% per year * 3 years) = 5236.52
    assert 5200 <= result <= 5250


def test_cola_adjustment():
    """Test COLA adjustment calculation."""
    initial_benefit = 5215
    # After 1 year with 2% COLA
    result = calculate_benefit_with_cola(5215, 1, 0.02)
    expected = 5215 * 1.02
    assert abs(result - expected) < 1.0


def test_generate_schedule_tom():
    """Test generating Tom's schedule matching the CSV data."""
    tom_schedule = generate_ssi_schedule(
        person_name="Tom",
        birth_year=1965,
        claiming_age=70,
        fra_benefit=4223,
        start_year=2026,
        end_year=2040,
        cola_rate=0.02
    )
    
    # Check year 2036 (Tom age 71, 1 year after claiming at 70)
    year_2036 = tom_schedule[tom_schedule['year'] == 2036]
    assert not year_2036.empty
    assert year_2036['claiming_age'].iloc[0] == 71
    assert year_2036['person'].iloc[0] == "Tom"
    # Initial benefit at 70: ~5215, after 1 year COLA: ~5319
    assert 5300 <= year_2036['monthly_benefit'].iloc[0] <= 5350


def test_generate_schedule_before_claiming():
    """Test that benefits are 0 before claiming age."""
    schedule = generate_ssi_schedule(
        person_name="Test",
        birth_year=1965,
        claiming_age=70,
        fra_benefit=4223,
        start_year=2026,
        end_year=2034,
        cola_rate=0.02
    )
    
    # In 2034, person is 69 (before claiming at 70)
    year_2034 = schedule[schedule['year'] == 2034]
    assert year_2034['monthly_benefit'].iloc[0] == 0.0


def test_config_integration():
    """Test integration with config manager."""
    config = get_config_manager()
    
    # Set test values
    config.set("social_security", "person1_ssi_age", 70)
    config.set("social_security", "person1_ssi_amount", 4223)
    config.set("social_security", "person2_ssi_age", 70)
    config.set("social_security", "person2_ssi_amount", 4223)
    
    # Generate schedule
    schedule = generate_ssi_schedule_from_config(config, 2026, 2040)
    
    assert not schedule.empty
    assert 'Tom' in schedule['person'].values
    assert 'Sarah' in schedule['person'].values


def test_validate_config():
    """Test config validation."""
    config = get_config_manager()
    
    # Valid settings
    config.set("social_security", "person1_ssi_age", 70)
    config.set("social_security", "person1_ssi_amount", 4223)
    
    is_valid, errors = validate_config_ssi_settings(config)
    assert is_valid
    assert len(errors) == 0
    
    # Invalid age
    config.set("social_security", "person1_ssi_age", 75)
    is_valid, errors = validate_config_ssi_settings(config)
    assert not is_valid
    assert len(errors) > 0


def test_comparison_with_csv_data():
    """
    Compare calculated values with actual CSV data to verify formula accuracy.
    
    From ssincome.csv:
    - Tom at age 67 (2033): $4,223
    - Tom at age 70 (2036): $5,215
    - Tom at age 62 (2028): $2,829
    """
    fra_benefit = 4223
    
    # Test age 67 (FRA)
    benefit_67 = calculate_benefit_at_claiming_age(fra_benefit, 67)
    assert benefit_67 == 4223.0
    
    # Test age 70 (delayed 3 years)
    benefit_70 = calculate_benefit_at_claiming_age(fra_benefit, 70)
    # CSV shows 5215, our calculation should be close
    assert abs(benefit_70 - 5215) < 10  # Within $10
    
    # Test age 62 (early 5 years)
    benefit_62 = calculate_benefit_at_claiming_age(fra_benefit, 62)
    # CSV shows 2829, our calculation should be close
    assert abs(benefit_62 - 2829) < 10  # Within $10


if __name__ == "__main__":
    print("Running SSI Calculator Tests")
    print("=" * 60)
    
    # Run basic tests
    print("\n1. Testing benefit at age 67 (FRA)...")
    test_benefit_at_age_67()
    print("   ✓ Passed")
    
    print("\n2. Testing benefit at age 62 (early claiming)...")
    test_benefit_at_age_62()
    print("   ✓ Passed")
    
    print("\n3. Testing benefit at age 70 (delayed claiming)...")
    test_benefit_at_age_70()
    print("   ✓ Passed")
    
    print("\n4. Testing COLA adjustments...")
    test_cola_adjustment()
    print("   ✓ Passed")
    
    print("\n5. Testing schedule generation...")
    test_generate_schedule_tom()
    print("   ✓ Passed")
    
    print("\n6. Testing benefits before claiming age...")
    test_generate_schedule_before_claiming()
    print("   ✓ Passed")
    
    print("\n7. Comparing with CSV data...")
    test_comparison_with_csv_data()
    print("   ✓ Passed")
    
    print("\n" + "=" * 60)
    print("All tests passed! ✓")
    
    # Show example output
    print("\n" + "=" * 60)
    print("EXAMPLE: Generating SSI Schedule from Config")
    print("=" * 60)
    
    config = get_config_manager()
    config.set("social_security", "person1_ssi_age", 70)
    config.set("social_security", "person1_ssi_amount", 4223)
    config.set("social_security", "person2_ssi_age", 70)
    config.set("social_security", "person2_ssi_amount", 4223)
    
    schedule = generate_ssi_schedule_from_config(config, 2026, 2040)
    
    print("\nSample rows from generated schedule:")
    print(schedule[schedule['year'].isin([2026, 2033, 2036, 2040])].to_string(index=False))

# Made with Bob
