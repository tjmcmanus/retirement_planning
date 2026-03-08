"""
Basic tests for bucket strategy modules.
Run with: python test_bucket_strategy.py
"""

import sys
from datetime import datetime

def test_market_trend_analysis():
    """Test market trend analysis module."""
    print("\n" + "="*60)
    print("Testing Market Trend Analysis Module")
    print("="*60)
    
    try:
        from market_trend_analysis import (
            get_market_condition,
            MarketTrendConfig,
            format_market_condition_summary,
            MarketCondition
        )
        
        print("✓ Module imports successful")
        
        # Test with default config
        config = MarketTrendConfig()
        print(f"✓ Config created: {config.short_ma_weeks}-week / {config.long_ma_weeks}-week MAs")
        
        # Get market condition
        print("\nFetching current market condition...")
        condition, ma_data = get_market_condition(config)
        
        if condition == MarketCondition.UNKNOWN:
            print("⚠ Unable to fetch market data (may be offline or API issue)")
            return False
        
        print(f"✓ Market condition determined: {condition.value.upper()}")
        
        if ma_data:
            print(f"  - SPY Price: ${ma_data.current_price:.2f}")
            print(f"  - 10-week MA: ${ma_data.short_ma:.2f} ({ma_data.short_trend.value})")
            print(f"  - 50-week MA: ${ma_data.long_ma:.2f} ({ma_data.long_trend.value})")
            print(f"  - Confidence: {ma_data.confidence:.0%}")
            
            # Test summary formatting
            summary = format_market_condition_summary(condition, ma_data)
            print("\n" + summary)
        
        print("\n✓ Market trend analysis module working correctly")
        return True
        
    except Exception as e:
        print(f"✗ Error testing market trend analysis: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_bucket_strategy():
    """Test bucket strategy module."""
    print("\n" + "="*60)
    print("Testing Bucket Strategy Module")
    print("="*60)
    
    try:
        from bucket_strategy import (
            BucketConfig,
            load_bucket_config,
            analyze_portfolio_buckets,
            format_bucket_summary,
            BucketType,
            AssetClass
        )
        
        print("✓ Module imports successful")
        
        # Test config loading
        config = load_bucket_config()
        print(f"✓ Config loaded: enabled={config.enabled}")
        
        # Enable bucket strategy for testing if disabled
        if not config.enabled:
            print("  ⚠ Bucket strategy disabled in config, enabling for test...")
            config.enabled = True
        
        print(f"  - Bucket 1: {config.bucket_1_years} years of expenses")
        print(f"  - Bucket 2: {config.bucket_2_years} years with {config.bucket_2_start_stock_pct}%-{config.bucket_2_end_stock_pct}% stocks")
        print(f"  - Annual expenses: ${config.annual_expenses:,.0f}")
        
        # Test bucket 2 allocation calculation
        for year in [1, 4, 8]:
            stock_pct, bond_pct = config.get_bucket_2_allocation(year)
            print(f"  - Year {year}: {stock_pct:.0f}% stocks, {bond_pct:.0f}% bonds")
        
        # Test portfolio analysis
        print("\nAnalyzing portfolio...")
        summary = analyze_portfolio_buckets(config=config)
        
        print(f"✓ Portfolio analyzed")
        print(f"  - Total value: ${summary.total_portfolio_value:,.2f}")
        print(f"  - Bucket 1: ${summary.bucket_1_value:,.2f} ({summary.bucket_1_pct:.1f}%)")
        print(f"  - Bucket 2: ${summary.bucket_2_value:,.2f} ({summary.bucket_2_pct:.1f}%)")
        print(f"  - Bucket 3: ${summary.bucket_3_value:,.2f} ({summary.bucket_3_pct:.1f}%)")
        print(f"  - Rebalancing needed: {summary.needs_rebalancing}")
        
        if summary.market_condition:
            print(f"  - Market condition: {summary.market_condition.value.upper()}")
        
        # Test summary formatting
        formatted = format_bucket_summary(summary)
        print("\n" + formatted)
        
        print("\n✓ Bucket strategy module working correctly")
        return True
        
    except Exception as e:
        print(f"✗ Error testing bucket strategy: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests."""
    print("\n" + "="*60)
    print("BUCKET STRATEGY MODULE TESTS")
    print("="*60)
    print(f"Test run: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    results = []
    
    # Test market trend analysis
    results.append(("Market Trend Analysis", test_market_trend_analysis()))
    
    # Test bucket strategy
    results.append(("Bucket Strategy", test_bucket_strategy()))
    
    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status}: {name}")
    
    print(f"\nResults: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n✓ All tests passed!")
        return 0
    else:
        print(f"\n✗ {total - passed} test(s) failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())

# Made with Bob
