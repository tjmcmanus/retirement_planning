"""
Test to verify the BETR tax bracket fix.

This test verifies that getNextHigherTaxRate correctly returns the next
tax bracket instead of using a fixed 0.08 increment.
"""

import pandas as pd
from calculations import getNextHigherTaxRate
from load_data import get_income_tax_brackets


def test_next_higher_tax_rate():
    """Test that getNextHigherTaxRate returns correct next bracket."""
    
    # Get 2026 tax brackets
    tax_brackets_df = get_income_tax_brackets(2026)
    
    print("Testing getNextHigherTaxRate function:")
    print("=" * 60)
    
    # Test cases: (current_rate, expected_next_rate)
    test_cases = [
        (0.10, 0.12, "10% -> 12%"),
        (0.12, 0.22, "12% -> 22%"),
        (0.22, 0.24, "22% -> 24%"),
        (0.24, 0.32, "24% -> 32%"),
        (0.32, 0.35, "32% -> 35%"),
        (0.35, 0.37, "35% -> 37%"),
        (0.37, 0.37, "37% -> 37% (already at top)"),
    ]
    
    all_passed = True
    
    for current_rate, expected_next, description in test_cases:
        try:
            next_rate = getNextHigherTaxRate(current_rate, tax_brackets_df)
            passed = abs(next_rate - expected_next) < 0.0001
            
            status = "✓ PASS" if passed else "✗ FAIL"
            print(f"{status}: {description}")
            print(f"  Current: {current_rate:.2%}, Expected: {expected_next:.2%}, Got: {next_rate:.2%}")
            
            if not passed:
                all_passed = False
                
        except Exception as e:
            print(f"✗ FAIL: {description}")
            print(f"  Error: {e}")
            all_passed = False
    
    print("=" * 60)
    
    # Demonstrate the old bug
    print("\nDemonstrating the OLD BUG (fixed 0.08 increment):")
    print("-" * 60)
    
    bug_cases = [
        (0.12, 0.12 + 0.08, 0.22, "12% + 0.08 = 20% (WRONG, should be 22%)"),
        (0.22, 0.22 + 0.08, 0.24, "22% + 0.08 = 30% (WRONG, should be 24%)"),
        (0.24, 0.24 + 0.08, 0.32, "24% + 0.08 = 32% (CORRECT by coincidence)"),
    ]
    
    for current, old_calc, correct, description in bug_cases:
        print(f"  {description}")
        if abs(old_calc - correct) > 0.0001:
            print(f"    ⚠️  Old calculation was INCORRECT!")
        else:
            print(f"    ✓  Old calculation happened to be correct")
    
    print("=" * 60)
    
    if all_passed:
        print("\n✓ All tests PASSED! The fix is working correctly.")
    else:
        print("\n✗ Some tests FAILED! Please review the implementation.")
    
    return all_passed


if __name__ == "__main__":
    success = test_next_higher_tax_rate()
    exit(0 if success else 1)

# Made with Bob
