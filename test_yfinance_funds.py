"""
test_yfinance_funds.py
======================
Test script to explore yfinance FundsData scraper for mutual fund category information.

Run with: python test_yfinance_funds.py
"""

import yfinance as yf
import json
from pprint import pprint


def test_vsmax_fund_data():
    """Test fetching fund data for VSMAX using various yfinance methods."""
    
    symbol = "VSMAX"
    print(f"\n{'='*70}")
    print(f"Testing yfinance data for {symbol}")
    print(f"{'='*70}\n")
    
    # Method 1: Standard ticker.info
    print("=" * 70)
    print("METHOD 1: ticker.info")
    print("=" * 70)
    ticker = yf.Ticker(symbol)
    info = ticker.info
    
    print(f"\nAll available keys in info:")
    print(sorted(info.keys()))
    
    print(f"\n\nRelevant fields:")
    relevant_fields = [
        'symbol', 'shortName', 'longName', 'quoteType',
        'category', 'categoryName', 'fundFamily', 'legalType',
        'sector', 'industry', 'description'
    ]
    
    for field in relevant_fields:
        value = info.get(field, 'NOT FOUND')
        print(f"  {field:20s}: {value}")
    
    # Method 2: Try to access FundsData if available
    print(f"\n\n{'='*70}")
    print("METHOD 2: Exploring ticker object attributes")
    print("=" * 70)
    
    print(f"\nTicker object attributes:")
    attrs = [attr for attr in dir(ticker) if not attr.startswith('_')]
    for attr in attrs[:20]:  # Show first 20
        print(f"  - {attr}")
    
    # Method 3: Check if there's fund-specific data
    print(f"\n\n{'='*70}")
    print("METHOD 3: Fund-specific methods")
    print("=" * 70)
    
    try:
        if hasattr(ticker, 'funds_data'):
            print("\nFunds data found!")
            print(ticker.funds_data)
        else:
            print("\nNo funds_data attribute found")
    except Exception as e:
        print(f"\nError accessing funds_data: {e}")
    
    # Method 4: Check description field
    print(f"\n\n{'='*70}")
    print("METHOD 4: Description field analysis")
    print("=" * 70)
    
    description = info.get('description', '')
    if description:
        print(f"\nDescription length: {len(description)} characters")
        print(f"\nFirst 500 characters:")
        print(description[:500])
        
        # Look for category-related keywords
        keywords = ['blend', 'growth', 'value', 'small', 'mid', 'large', 'cap', 'bond', 'equity']
        found_keywords = [kw for kw in keywords if kw.lower() in description.lower()]
        if found_keywords:
            print(f"\n\nFound category keywords in description: {', '.join(found_keywords)}")
    else:
        print("\nNo description available")
    
    # Method 5: Try fund_performance if available
    print(f"\n\n{'='*70}")
    print("METHOD 5: Fund performance data")
    print("=" * 70)
    
    try:
        if hasattr(ticker, 'fund_performance'):
            perf = ticker.fund_performance
            print("\nFund performance data:")
            print(perf)
        else:
            print("\nNo fund_performance attribute")
    except Exception as e:
        print(f"\nError: {e}")
    
    # Method 6: Check asset profile
    print(f"\n\n{'='*70}")
    print("METHOD 6: Asset profile")
    print("=" * 70)
    
    try:
        if hasattr(ticker, 'asset_profile'):
            profile = ticker.asset_profile
            print("\nAsset profile:")
            pprint(profile)
        else:
            print("\nNo asset_profile attribute")
    except Exception as e:
        print(f"\nError: {e}")
    
    # Method 7: Try to get fund category from morningstar style
    print(f"\n\n{'='*70}")
    print("METHOD 7: Morningstar style/category")
    print("=" * 70)
    
    morningstar_fields = [
        'morningstarOverallRating',
        'morningstarRiskRating', 
        'fundInceptionDate',
        'fundFamily',
        'legalType'
    ]
    
    for field in morningstar_fields:
        value = info.get(field, 'NOT FOUND')
        print(f"  {field:30s}: {value}")
    
    print(f"\n{'='*70}")
    print("SUMMARY")
    print(f"{'='*70}\n")
    
    # Determine best field for category
    category_candidates = {
        'category': info.get('category'),
        'legalType': info.get('legalType'),
        'quoteType': info.get('quoteType'),
        'fundFamily': info.get('fundFamily'),
    }
    
    print("Category candidates:")
    for field, value in category_candidates.items():
        if value:
            print(f"  ✓ {field:15s}: {value}")
        else:
            print(f"  ✗ {field:15s}: (empty)")
    
    # Method 8: Check for fund_overview, sector_weightings, asset_classes
    print(f"\n\n{'='*70}")
    print("METHOD 8: Fund overview, sector weightings, asset classes")
    print("=" * 70)
    
    fund_attrs = ['fund_overview', 'sector_weightings', 'asset_classes',
                  'top_holdings', 'fund_holding_info', 'fund_sector_weightings']
    
    for attr in fund_attrs:
        try:
            if hasattr(ticker, attr):
                data = getattr(ticker, attr)
                print(f"\n✓ Found {attr}:")
                if data is not None:
                    if isinstance(data, dict):
                        pprint(data)
                    else:
                        print(data)
                else:
                    print("  (None)")
            else:
                print(f"\n✗ No {attr} attribute")
        except Exception as e:
            print(f"\n⚠️  Error accessing {attr}: {e}")
    
    # Recommendation
    print(f"\n{'='*70}")
    print("RECOMMENDATION")
    print(f"{'='*70}\n")
    
    if info.get('category'):
        print(f"✅ Use 'category' field: {info.get('category')}")
    elif 'small' in description.lower() and 'cap' in description.lower():
        print("⚠️  Parse from description: Likely 'Small Cap' fund")
    else:
        print("❌ No clear category field available")
        print("   Consider using fundFamily or legalType as fallback")


def test_multiple_funds():
    """Test multiple mutual funds to see pattern."""
    
    test_symbols = ['VSMAX', 'VFIAX', 'VEXAX', 'VBMFX']
    
    print(f"\n\n{'='*70}")
    print("TESTING MULTIPLE FUNDS")
    print(f"{'='*70}\n")
    
    results = []
    for symbol in test_symbols:
        ticker = yf.Ticker(symbol)
        info = ticker.info
        
        result = {
            'symbol': symbol,
            'name': info.get('shortName', 'N/A'),
            'category': info.get('category', 'N/A'),
            'fundFamily': info.get('fundFamily', 'N/A'),
            'legalType': info.get('legalType', 'N/A'),
            'quoteType': info.get('quoteType', 'N/A'),
        }
        results.append(result)
    
    # Print table
    print(f"{'Symbol':<10} {'Name':<30} {'Category':<20} {'Fund Family':<20}")
    print("-" * 80)
    for r in results:
        print(f"{r['symbol']:<10} {r['name']:<30} {r['category']:<20} {r['fundFamily']:<20}")


if __name__ == '__main__':
    test_vsmax_fund_data()
    test_multiple_funds()
    
    print(f"\n\n{'='*70}")
    print("TEST COMPLETE")
    print(f"{'='*70}\n")

# Made with Bob
