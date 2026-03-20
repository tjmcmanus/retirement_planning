#!/usr/bin/env python3
"""Quick integration test for short-term market forecast."""

from market_trend_shortterm import (
    get_shortterm_market_condition,
    ShortTermMarketTrendConfig,
    format_shortterm_market_summary,
    get_tactical_recommendations
)

def main():
    print("Testing Short-Term Market Forecast Integration")
    print("=" * 60)
    
    config = ShortTermMarketTrendConfig()
    condition, data = get_shortterm_market_condition(config, use_cache=False)
    
    print(f"\nShort-term Market Condition: {condition.value.upper()}")
    
    if data:
        print(f"\nCurrent SPY Price: ${data.current_price:.2f}")
        print(f"10-Day EMA: ${data.short_ema:.2f}")
        print(f"50-Day EMA: ${data.long_ema:.2f}")
        print(f"Confidence: {data.confidence:.0%}")
        print(f"Days in Trend: {data.days_in_trend}")
        
        print("\n" + "=" * 60)
        print("FULL SUMMARY:")
        print("=" * 60)
        print(format_shortterm_market_summary(condition, data))
        
        print("\n" + "=" * 60)
        print("TACTICAL RECOMMENDATIONS:")
        print("=" * 60)
        recommendations = get_tactical_recommendations(condition, data)
        for i, rec in enumerate(recommendations, 1):
            print(f"{i}. {rec}")
    else:
        print("\nNo market data available")
    
    print("\n" + "=" * 60)
    print("Integration test completed successfully!")

if __name__ == "__main__":
    main()

# Made with Bob
