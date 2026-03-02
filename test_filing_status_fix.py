#!/usr/bin/env python3
"""
Test script to verify the filing status fix for get_std_deduction()
"""

from config import get_config_manager
from load_data import get_std_deduction

def test_filing_status_integration():
    """Test that filing status is correctly passed to get_std_deduction"""
    
    # Test the filing status retrieval
    config = get_config_manager()
    filing_status = config.get_filing_status()
    print(f'✓ Current filing status: {filing_status}')
    
    # Test get_std_deduction with filing status
    std_ded_df = get_std_deduction(2024, filing_status)
    print(f'✓ Standard deduction for 2024 ({filing_status}):')
    print(f'  Deduction amount: ${std_ded_df.iloc[0]["deduction"]:,.0f}')
    
    # Test with both filing statuses to ensure they return different values
    married_df = get_std_deduction(2024, 'married_filing_jointly')
    single_df = get_std_deduction(2024, 'single')
    
    married_ded = married_df.iloc[0]['deduction']
    single_ded = single_df.iloc[0]['deduction']
    
    print(f'\n✓ Married filing jointly deduction: ${married_ded:,.0f}')
    print(f'✓ Single filer deduction: ${single_ded:,.0f}')
    
    assert married_ded != single_ded, 'Filing status does not affect standard deduction'
    print('\n✓ SUCCESS: Filing status correctly affects standard deduction')

if __name__ == '__main__':
    success = test_filing_status_integration()
    exit(0 if success else 1)

# Made with Bob
