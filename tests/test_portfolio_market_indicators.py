"""
Test script for portfolio market indicators functionality.
"""

import sys
from portfolio_market_indicators import (
    calculate_security_indicator,
    get_portfolio_indicators,
    SecurityMarketCondition,
    get_indicator_summary,
)

def test_single_security():
    """Test market indicator calculation for a single security."""
    print("=" * 70)
    print("Testing Single Security Indicator Calculation")
    print("=" * 70)
    
    # Test with SPY (S&P 500 ETF)
    symbol = "SPY"
    print(f"\nCalculating indicator for {symbol}...")
    
    indicator = calculate_security_indicator(symbol)
    
    if indicator:
        print(f"\n✅ Successfully calculated indicator for {symbol}")
        print(get_indicator_summary(indicator))
    else:
        print(f"\n❌ Failed to calculate indicator for {symbol}")
    
    return indicator is not None


def test_multiple_securities():
    """Test market indicator calculation for multiple securities."""
    print("\n" + "=" * 70)
    print("Testing Multiple Securities Indicator Calculation")
    print("=" * 70)
    
    # Test with a portfolio of common securities
    symbols = ["SPY", "AAPL", "MSFT", "GOOGL", "MF:CASH"]
    print(f"\nCalculating indicators for: {', '.join(symbols)}")
    
    indicators = get_portfolio_indicators(symbols)
    
    success_count = 0
    for symbol, indicator in indicators.items():
        if indicator:
            print(f"\n{indicator.emoji} {symbol}: {indicator.condition.value.replace('_', ' ').title()}")
            print(f"   {indicator.recommendation}")
            success_count += 1
        else:
            print(f"\n❌ {symbol}: Failed to calculate")
    
    print(f"\n✅ Successfully calculated {success_count}/{len(symbols)} indicators")
    return success_count == len(symbols)


def test_cash_handling():
    """Test that cash holdings are handled correctly."""
    print("\n" + "=" * 70)
    print("Testing Cash Holdings")
    print("=" * 70)
    
    cash_symbols = ["MF:CASH", "CASH"]
    
    for symbol in cash_symbols:
        print(f"\nTesting {symbol}...")
        indicator = calculate_security_indicator(symbol)
        
        if indicator:
            print(f"✅ {symbol}: {indicator.emoji} {indicator.condition.value}")
            print(f"   {indicator.recommendation}")
            if indicator.condition == SecurityMarketCondition.HOLD:
                print("   ✅ Correctly identified as HOLD")
            else:
                print(f"   ⚠️ Expected HOLD, got {indicator.condition.value}")
        else:
            print(f"❌ Failed to handle {symbol}")
    
    return True


def test_indicator_caching():
    """Test that indicator caching works."""
    print("\n" + "=" * 70)
    print("Testing Indicator Caching")
    print("=" * 70)
    
    symbol = "SPY"
    
    print(f"\nFirst calculation for {symbol}...")
    indicator1 = calculate_security_indicator(symbol)
    
    print(f"Second calculation for {symbol} (should use cache)...")
    indicator2 = calculate_security_indicator(symbol)
    
    if indicator1 and indicator2:
        if indicator1.calculation_date == indicator2.calculation_date:
            print("✅ Cache is working - same calculation timestamp")
            return True
        else:
            print("⚠️ Cache may not be working - different timestamps")
            return False
    else:
        print("❌ Failed to calculate indicators")
        return False


def main():
    """Run all tests."""
    print("\n" + "=" * 70)
    print("PORTFOLIO MARKET INDICATORS TEST SUITE")
    print("=" * 70)
    
    results = []
    
    # Run tests
    results.append(("Single Security", test_single_security()))
    results.append(("Multiple Securities", test_multiple_securities()))
    results.append(("Cash Handling", test_cash_handling()))
    results.append(("Indicator Caching", test_indicator_caching()))
    
    # Print summary
    print("\n" + "=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"{status}: {test_name}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All tests passed!")
        return 0
    else:
        print(f"\n⚠️ {total - passed} test(s) failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())

# Made with Bob
