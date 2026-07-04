"""
Test Options Support in Portfolio System
Tests the ability to handle stock options with OCC format symbols
and support for negative quantities (covered calls, cash-secured puts)
"""

import pytest
from portfolio_data_entry import (
    is_option_symbol,
    validate_ticker_symbol,
    validate_portfolio_entry,
    VALID_SECTORS
)
import pandas as pd


def test_is_option_symbol():
    """Test detection of options contracts in OCC format."""
    
    # Test valid call option
    is_opt, underlying, opt_type = is_option_symbol("SOFI  260402C00020000")
    assert is_opt == True
    assert underlying == "SOFI"
    assert opt_type == "Call"
    
    # Test valid put option
    is_opt, underlying, opt_type = is_option_symbol("AAPL  260115P00150000")
    assert is_opt == True
    assert underlying == "AAPL"
    assert opt_type == "Put"
    
    # Test regular stock symbol
    is_opt, underlying, opt_type = is_option_symbol("AAPL")
    assert is_opt == False
    assert underlying == ""
    assert opt_type == ""
    
    # Test mutual fund
    is_opt, underlying, opt_type = is_option_symbol("VFIAX")
    assert is_opt == False
    
    # Test cash
    is_opt, underlying, opt_type = is_option_symbol("MF:CASH")
    assert is_opt == False


def test_valid_sectors_include_options():
    """Test that VALID_SECTORS includes options categories."""
    assert "Options:Call" in VALID_SECTORS
    assert "Options:Put" in VALID_SECTORS


def test_validate_ticker_symbol_options():
    """Test validation of options symbols."""
    
    # Test call option (underlying SOFI should be valid)
    is_valid, name, sector, error = validate_ticker_symbol("SOFI  260402C00020000")
    assert is_valid == True
    assert "Call" in name
    assert sector == "Options:Call"
    assert error == ""
    
    # Test put option
    is_valid, name, sector, error = validate_ticker_symbol("AAPL  260115P00150000")
    assert is_valid == True
    assert "Put" in name
    assert sector == "Options:Put"
    assert error == ""


def test_validate_portfolio_entry_positive_qty():
    """Test that regular stocks require positive quantity."""
    
    # Valid entry with positive quantity
    row = pd.Series({
        'month': 3,
        'year': 2026,
        'account_name': 'Test Account',
        'account_type': 'Brokerage',
        'owner': 'Joint',
        'symbol': 'AAPL',
        'qty': 10.0,
        'purchase_price': 150.00
    })
    
    is_valid, error = validate_portfolio_entry(row)
    assert is_valid == True
    assert error == ""
    
    # Invalid entry with negative quantity for stock
    row['qty'] = -10.0
    is_valid, error = validate_portfolio_entry(row)
    assert is_valid == False
    assert "positive" in error.lower()


def test_validate_portfolio_entry_negative_qty_options():
    """Test that options allow negative quantity (short positions)."""
    
    # Valid covered call (negative quantity)
    row = pd.Series({
        'month': 3,
        'year': 2026,
        'account_name': 'Test Account',
        'account_type': 'Brokerage',
        'owner': 'Joint',
        'symbol': 'SOFI  260402C00020000',  # Call option
        'qty': -1.0,  # Negative = short position (covered call)
        'purchase_price': 0.50
    })
    
    is_valid, error = validate_portfolio_entry(row)
    assert is_valid == True, f"Expected valid but got error: {error}"
    assert error == ""
    
    # Valid cash-secured put (negative quantity)
    row['symbol'] = 'AAPL  260115P00150000'  # Put option
    row['qty'] = -2.0  # Negative = short position (cash-secured put)
    
    is_valid, error = validate_portfolio_entry(row)
    assert is_valid == True, f"Expected valid but got error: {error}"
    assert error == ""
    
    # Valid long call (positive quantity)
    row['qty'] = 1.0  # Positive = long position
    
    is_valid, error = validate_portfolio_entry(row)
    assert is_valid == True
    assert error == ""


def test_validate_portfolio_entry_zero_qty():
    """Test that zero quantity is not allowed for any security."""
    
    # Zero quantity for stock
    row = pd.Series({
        'month': 3,
        'year': 2026,
        'account_name': 'Test Account',
        'account_type': 'Brokerage',
        'owner': 'Joint',
        'symbol': 'AAPL',
        'qty': 0.0,
        'purchase_price': 150.00
    })
    
    is_valid, error = validate_portfolio_entry(row)
    assert is_valid == False
    assert "zero" in error.lower()
    
    # Zero quantity for option
    row['symbol'] = 'SOFI  260402C00020000'
    is_valid, error = validate_portfolio_entry(row)
    assert is_valid == False
    assert "zero" in error.lower()


def test_options_symbol_format_variations():
    """Test various options symbol format edge cases."""
    
    # Multi-letter underlying
    is_opt, underlying, opt_type = is_option_symbol("TSLA  260320C00200000")
    assert is_opt == True
    assert underlying == "TSLA"
    assert opt_type == "Call"
    
    # Single letter underlying
    is_opt, underlying, opt_type = is_option_symbol("F     260215P00010000")
    assert is_opt == True
    assert underlying == "F"
    assert opt_type == "Put"
    
    # Invalid format (too short)
    is_opt, underlying, opt_type = is_option_symbol("AAPL")
    assert is_opt == False
    
    # Invalid format (no date/strike)
    is_opt, underlying, opt_type = is_option_symbol("AAPL  CALL")
    assert is_opt == False


if __name__ == "__main__":
    print("Running options support tests...")
    
    print("\n1. Testing is_option_symbol()...")
    test_is_option_symbol()
    print("   ✓ Options detection working")
    
    print("\n2. Testing VALID_SECTORS...")
    test_valid_sectors_include_options()
    print("   ✓ Options sectors added")
    
    print("\n3. Testing validate_ticker_symbol() for options...")
    test_validate_ticker_symbol_options()
    print("   ✓ Options validation working")
    
    print("\n4. Testing positive quantity validation...")
    test_validate_portfolio_entry_positive_qty()
    print("   ✓ Stocks require positive quantity")
    
    print("\n5. Testing negative quantity for options...")
    test_validate_portfolio_entry_negative_qty_options()
    print("   ✓ Options allow negative quantity")
    
    print("\n6. Testing zero quantity validation...")
    test_validate_portfolio_entry_zero_qty()
    print("   ✓ Zero quantity rejected")
    
    print("\n7. Testing options symbol format variations...")
    test_options_symbol_format_variations()
    print("   ✓ Various formats handled correctly")
    
    print("\n✅ All tests passed!")

# Made with Bob
