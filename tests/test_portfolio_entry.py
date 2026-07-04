"""
Test script for portfolio data entry functionality
"""

import pandas as pd
from portfolio_data_entry import (
    validate_ticker_symbol,
    validate_portfolio_entry,
    validate_portfolio_dataframe,
    save_portfolio_data,
    create_empty_entry_template
)

def test_ticker_validation():
    """Test ticker symbol validation"""
    print("Testing ticker validation...")
    
    # Test valid ticker
    is_valid, name, sector, error = validate_ticker_symbol('AAPL')
    print(f"AAPL: Valid={is_valid}, Name={name}, Sector={sector}")
    assert is_valid, "AAPL should be valid"
    
    # Test cash
    is_valid, name, sector, error = validate_ticker_symbol('MF:CASH')
    print(f"MF:CASH: Valid={is_valid}, Name={name}, Sector={sector}")
    assert is_valid, "MF:CASH should be valid"
    
    # Test invalid ticker
    is_valid, name, sector, error = validate_ticker_symbol('INVALID123XYZ')
    print(f"INVALID123XYZ: Valid={is_valid}, Error={error}")
    assert not is_valid, "INVALID123XYZ should be invalid"
    
    print("✅ Ticker validation tests passed!\n")

def test_entry_validation():
    """Test portfolio entry validation"""
    print("Testing entry validation...")
    
    # Valid entry
    valid_entry = pd.Series({
        'month': 12,
        'year': 2025,
        'account_name': 'Test Account',
        'account_type': 'Brokerage',
        'symbol': 'AAPL',
        'name': 'Apple Inc.',
        'sector': 'Technology',
        'qty': 100.0,
        'purchase_price': 150.0
    })
    
    is_valid, error = validate_portfolio_entry(valid_entry)
    print(f"Valid entry: Valid={is_valid}")
    assert is_valid, f"Valid entry should pass: {error}"
    
    # Invalid entry (missing required field)
    invalid_entry = pd.Series({
        'month': 12,
        'year': 2025,
        'account_name': '',  # Missing
        'account_type': 'Brokerage',
        'symbol': 'AAPL',
        'name': 'Apple Inc.',
        'sector': 'Technology',
        'qty': 100.0,
        'purchase_price': 150.0
    })
    
    is_valid, error = validate_portfolio_entry(invalid_entry)
    print(f"Invalid entry: Valid={is_valid}, Error={error}")
    assert not is_valid, "Entry with missing account_name should be invalid"
    
    print("✅ Entry validation tests passed!\n")

def test_dataframe_validation():
    """Test dataframe validation"""
    print("Testing dataframe validation...")
    
    test_df = pd.DataFrame([
        {
            'month': 12,
            'year': 2025,
            'account_name': 'Schwab',
            'account_type': 'Brokerage',
            'symbol': 'AAPL',
            'name': 'Apple Inc.',
            'sector': 'Technology',
            'qty': 100.0,
            'purchase_price': 150.0
        },
        {
            'month': 12,
            'year': 2025,
            'account_name': '',  # Invalid
            'account_type': 'Brokerage',
            'symbol': 'GOOGL',
            'name': 'Alphabet',
            'sector': 'Technology',
            'qty': 50.0,
            'purchase_price': 140.0
        }
    ])
    
    valid_df, invalid_df = validate_portfolio_dataframe(test_df)
    print(f"Valid entries: {len(valid_df)}")
    print(f"Invalid entries: {len(invalid_df)}")
    
    assert len(valid_df) == 1, "Should have 1 valid entry"
    assert len(invalid_df) == 1, "Should have 1 invalid entry"
    
    print("✅ Dataframe validation tests passed!\n")

def test_template_creation():
    """Test empty template creation"""
    print("Testing template creation...")
    
    template = create_empty_entry_template(12, 2025)
    print(f"Template shape: {template.shape}")
    print(f"Template columns: {list(template.columns)}")
    
    assert template.shape[0] == 1, "Template should have 1 row"
    assert 'month' in template.columns, "Template should have month column"
    assert template['month'].iloc[0] == 12, "Month should be 12"
    assert template['year'].iloc[0] == 2025, "Year should be 2025"
    
    print("✅ Template creation tests passed!\n")

if __name__ == "__main__":
    print("=" * 60)
    print("Portfolio Data Entry Module Tests")
    print("=" * 60 + "\n")
    
    try:
        test_ticker_validation()
        test_entry_validation()
        test_dataframe_validation()
        test_template_creation()
        
        print("=" * 60)
        print("✅ ALL TESTS PASSED!")
        print("=" * 60)
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()

# Made with Bob
