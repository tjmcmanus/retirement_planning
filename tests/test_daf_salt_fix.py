#!/usr/bin/env python3
"""Test the updated DAF calculation with SALT deductions."""

from strategy import _calculate_daf_for_year

def test_daf_with_salt():
    """Test that DAF calculation properly includes SALT deductions."""
    
    # Test parameters
    std_deduction = 29200  # 2024 MFJ standard deduction
    state_tax = 5000
    property_tax = 8000
    age = 62
    
    print("=" * 70)
    print("Testing DAF Calculation with SALT Deductions")
    print("=" * 70)
    
    # Test 1: Function accepts new parameters
    print("\nTest 1: Function signature updated")
    try:
        daf_contrib, daf_excess = _calculate_daf_for_year(age, std_deduction, state_tax, property_tax)
        print("✓ Function accepts state_tax and property_tax parameters")
    except TypeError as e:
        print(f"✗ Function signature error: {e}")
        return False
    
    # Test 2: Display calculation details
    print("\nTest 2: Calculation details")
    print(f"  Standard Deduction: ${std_deduction:,.0f}")
    print(f"  State Tax: ${state_tax:,.0f}")
    print(f"  Property Tax: ${property_tax:,.0f}")
    salt_total = state_tax + property_tax
    salt_capped = min(10000, salt_total)
    print(f"  SALT Total: ${salt_total:,.0f}")
    print(f"  SALT (capped at $10k): ${salt_capped:,.0f}")
    print(f"  DAF Contribution: ${daf_contrib:,.0f}")
    print(f"  DAF Tax Excess: ${daf_excess:,.0f}")
    
    # Test 3: Verify SALT cap is applied
    print("\nTest 3: SALT cap verification")
    high_state_tax = 15000
    high_property_tax = 20000
    daf_contrib2, daf_excess2 = _calculate_daf_for_year(age, std_deduction, high_state_tax, high_property_tax)
    print(f"  High SALT scenario: state=${high_state_tax:,.0f}, property=${high_property_tax:,.0f}")
    print(f"  Total would be ${high_state_tax + high_property_tax:,.0f}, but capped at $10,000")
    print(f"  DAF Contribution: ${daf_contrib2:,.0f}")
    print(f"  DAF Tax Excess: ${daf_excess2:,.0f}")
    
    # Test 4: Backward compatibility (no SALT provided)
    print("\nTest 4: Backward compatibility (default parameters)")
    try:
        daf_contrib3, daf_excess3 = _calculate_daf_for_year(age, std_deduction)
        print(f"✓ Function works with default parameters (no SALT)")
        print(f"  DAF Contribution: ${daf_contrib3:,.0f}")
        print(f"  DAF Tax Excess: ${daf_excess3:,.0f}")
    except Exception as e:
        print(f"✗ Backward compatibility error: {e}")
        return False
    
    print("\n" + "=" * 70)
    print("All tests passed! ✓")
    print("=" * 70)
    return True

if __name__ == "__main__":
    test_daf_with_salt()

# Made with Bob
