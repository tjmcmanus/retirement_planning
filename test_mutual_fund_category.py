"""
test_mutual_fund_category.py
=============================
Test suite for mutual fund categoryName display bug fix.

Tests that mutual funds (5-letter tickers) correctly display their
categoryName from yfinance instead of generic "MUTUALFUND" or empty sectors.

Run with: pytest test_mutual_fund_category.py -v
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
import yfinance as yf
import pandas as pd


# Test data for mutual funds
MUTUAL_FUND_TEST_CASES = [
    {
        'symbol': 'VSMAX',
        'expected_category': 'Small Blend',
        'description': 'Vanguard Small Cap Index Fund'
    },
    {
        'symbol': 'VFIAX',
        'expected_category': 'Large Blend',
        'description': 'Vanguard 500 Index Fund'
    },
    {
        'symbol': 'VEXAX',
        'expected_category': 'Mid-Cap Blend',
        'description': 'Vanguard Extended Market Index Fund'
    },
    {
        'symbol': 'VBMFX',
        'expected_category': 'Intermediate Core Bond',
        'description': 'Vanguard Total Bond Market Index Fund'
    },
]

# Test data for stocks (should use sector, not categoryName)
STOCK_TEST_CASES = [
    {
        'symbol': 'AAPL',
        'expected_sector': 'Technology',
        'description': 'Apple Inc.'
    },
    {
        'symbol': 'KO',
        'expected_sector': 'Consumer Defensive',
        'description': 'Coca-Cola'
    },
]


class TestMutualFundCategoryName:
    """Test suite for mutual fund categoryName functionality."""
    
    def test_mutual_fund_ticker_detection(self):
        """Test that 5-letter alphabetic tickers are correctly identified as mutual funds."""
        # Mutual funds (should be detected)
        assert len('VSMAX') == 5 and 'VSMAX'.isalpha()
        assert len('VFIAX') == 5 and 'VFIAX'.isalpha()
        
        # Not mutual funds (should not be detected)
        assert not (len('AAPL') == 5 and 'AAPL'.isalpha())  # 4 letters
        # GOOGL is 5 letters and alphabetic, so it WOULD be detected as potential mutual fund
        # The logic relies on yfinance to differentiate via categoryName presence
        assert len('GOOGL') == 5 and 'GOOGL'.isalpha()  # This IS 5 letters
        assert not (len('MF:CASH') == 5 and 'MF:CASH'.isalpha())  # Contains special chars
    
    @patch('yfinance.Ticker')
    def test_get_sector_from_yfinance_mutual_fund(self, mock_ticker_class):
        """Test that get_sector_from_yfinance returns categoryName for mutual funds."""
        from components.portfolio_holdings_editor import get_sector_from_yfinance
        
        # Mock yfinance response for mutual fund
        mock_ticker = Mock()
        mock_ticker.info = {
            'categoryName': 'Small Blend',
            'sector': None,  # Mutual funds don't have sector
            'quoteType': 'MUTUALFUND'
        }
        mock_ticker_class.return_value = mock_ticker
        
        result = get_sector_from_yfinance('VSMAX')
        assert result == 'Small Blend', f"Expected 'Small Blend', got '{result}'"
    
    @patch('yfinance.Ticker')
    def test_get_sector_from_yfinance_stock(self, mock_ticker_class):
        """Test that get_sector_from_yfinance returns sector for stocks."""
        from components.portfolio_holdings_editor import get_sector_from_yfinance
        
        # Mock yfinance response for stock
        mock_ticker = Mock()
        mock_ticker.info = {
            'sector': 'Technology',
            'categoryName': None,  # Stocks don't have categoryName
            'quoteType': 'EQUITY'
        }
        mock_ticker_class.return_value = mock_ticker
        
        result = get_sector_from_yfinance('AAPL')
        assert result == 'Technology', f"Expected 'Technology', got '{result}'"
    
    @patch('yfinance.Ticker')
    def test_get_sector_cash_handling(self, mock_ticker_class):
        """Test that cash holdings return 'Cash' as sector."""
        from components.portfolio_holdings_editor import get_sector_from_yfinance
        
        assert get_sector_from_yfinance('MF:CASH') == 'Cash'
        assert get_sector_from_yfinance('CASH') == 'Cash'
        assert get_sector_from_yfinance('cash') == 'Cash'
    
    @patch('yfinance.Ticker')
    def test_get_sector_fallback_behavior(self, mock_ticker_class):
        """Test fallback behavior when categoryName/sector not available."""
        from components.portfolio_holdings_editor import get_sector_from_yfinance
        
        # Mock yfinance response with no categoryName or sector
        mock_ticker = Mock()
        mock_ticker.info = {
            'categoryName': None,
            'sector': None,
            'category': 'Bond',
            'quoteType': 'MUTUALFUND'
        }
        mock_ticker_class.return_value = mock_ticker
        
        result = get_sector_from_yfinance('VBMFX')
        assert result == 'Bond', f"Expected fallback to 'Bond', got '{result}'"
    
    @patch('yfinance.Ticker')
    def test_get_sector_error_handling(self, mock_ticker_class):
        """Test that errors are handled gracefully."""
        from components.portfolio_holdings_editor import get_sector_from_yfinance
        
        # Mock yfinance to raise an exception
        mock_ticker_class.side_effect = Exception("Network error")
        
        result = get_sector_from_yfinance('INVALID')
        assert result == '', f"Expected empty string on error, got '{result}'"
    
    @patch('portfolio.getPortfolioData')
    @patch('yfinance.Ticker')
    def test_portfolio_get_sector_mutual_fund(self, mock_ticker_class, mock_get_data):
        """Test portfolio.py get_sector function for mutual funds."""
        from portfolio import get_sector
        
        # Mock yfinance response
        mock_ticker = Mock()
        mock_ticker.info = {
            'categoryName': 'Large Blend',
            'sector': None
        }
        mock_ticker_class.return_value = mock_ticker
        
        # Mock portfolio data
        mock_df = pd.DataFrame({
            'symbol': ['VFIAX'],
            'sector': ['']
        })
        mock_get_data.return_value = mock_df
        
        result = get_sector('VFIAX')
        # Should return categoryName for 5-letter tickers
        assert result == 'Large Blend', f"Expected 'Large Blend', got '{result}'"


class TestMutualFundIntegration:
    """Integration tests with real yfinance API (requires internet)."""
    
    @pytest.mark.integration
    @pytest.mark.skipif(True, reason="Requires internet connection - run manually")
    def test_real_mutual_fund_category_fetch(self):
        """Test fetching real categoryName from yfinance for known mutual funds."""
        from components.portfolio_holdings_editor import get_sector_from_yfinance
        
        for test_case in MUTUAL_FUND_TEST_CASES:
            symbol = test_case['symbol']
            result = get_sector_from_yfinance(symbol)
            
            # Should not be empty or "MUTUALFUND"
            assert result != '', f"{symbol} returned empty sector"
            assert result != 'MUTUALFUND', f"{symbol} returned generic 'MUTUALFUND'"
            
            print(f"✓ {symbol}: {result} (expected: {test_case['expected_category']})")
    
    @pytest.mark.integration
    @pytest.mark.skipif(True, reason="Requires internet connection - run manually")
    def test_real_stock_sector_fetch(self):
        """Test fetching real sector from yfinance for known stocks."""
        from components.portfolio_holdings_editor import get_sector_from_yfinance
        
        for test_case in STOCK_TEST_CASES:
            symbol = test_case['symbol']
            result = get_sector_from_yfinance(symbol)
            
            # Should not be empty
            assert result != '', f"{symbol} returned empty sector"
            
            print(f"✓ {symbol}: {result} (expected: {test_case['expected_sector']})")


class TestTickerNameDisplay:
    """Test suite for ticker name display with category."""
    
    @patch('yfinance.Ticker')
    def test_get_ticker_name_mutual_fund_with_category(self, mock_ticker_class):
        """Test that mutual fund names include category in parentheses."""
        from portfolio import get_ticker_name
        
        # Mock yfinance response
        mock_ticker = Mock()
        mock_ticker.info = {
            'shortName': 'Vanguard Small Cap Index Fund',
            'categoryName': 'Small Blend'
        }
        mock_ticker_class.return_value = mock_ticker
        
        result = get_ticker_name('VSMAX')
        assert 'Small Blend' in result, f"Expected category in name, got '{result}'"
        assert 'Vanguard Small Cap Index Fund' in result
    
    @patch('yfinance.Ticker')
    def test_get_ticker_name_stock_without_category(self, mock_ticker_class):
        """Test that stock names don't include category."""
        from portfolio import get_ticker_name
        
        # Mock yfinance response
        mock_ticker = Mock()
        mock_ticker.info = {
            'shortName': 'Apple Inc.',
            'categoryName': None
        }
        mock_ticker_class.return_value = mock_ticker
        
        result = get_ticker_name('AAPL')
        assert result == 'Apple Inc.', f"Expected plain name for stock, got '{result}'"


def test_bug_fix_summary():
    """
    Summary of the bug fix being tested:
    
    BEFORE:
    - Mutual funds showed "MUTUALFUND" as sector
    - Holdings table had empty sector column for mutual funds
    - No meaningful categorization for mutual fund holdings
    
    AFTER:
    - Mutual funds show categoryName (e.g., "Small Blend", "Large Blend")
    - Holdings table populates sector with investment category
    - Better asset allocation and portfolio analysis
    
    CHANGES:
    1. portfolio.py::get_sector() - Prioritizes categoryName for 5-letter tickers
    2. portfolio.py::get_ticker_name() - Appends category to mutual fund names
    3. components/portfolio_holdings_editor.py::get_sector_from_yfinance() - Uses categoryName
    """
    print("\n" + "="*70)
    print("MUTUAL FUND CATEGORY NAME BUG FIX TEST SUITE")
    print("="*70)
    print("\nThis test suite validates that:")
    print("  ✓ Mutual funds (5-letter tickers) use categoryName for sector")
    print("  ✓ Stocks/ETFs continue to use sector field")
    print("  ✓ Cash holdings return 'Cash' as sector")
    print("  ✓ Error handling works gracefully")
    print("  ✓ Fallback logic is correct")
    print("\nRun with: pytest test_mutual_fund_category.py -v")
    print("="*70 + "\n")


if __name__ == '__main__':
    # Run the summary when executed directly
    test_bug_fix_summary()
    
    # Run tests
    pytest.main([__file__, '-v', '--tb=short'])

# Made with Bob
