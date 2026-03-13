"""
test_morningstar_funds.py
=========================
Test script to explore Morningstar data sources for mutual fund category information.

Morningstar provides detailed fund categorization including:
- Morningstar Category (e.g., "Small Blend", "Large Growth")
- Style Box classification
- Asset allocation
- Sector weightings

Run with: python test_morningstar_funds.py
"""

import yfinance as yf
from pprint import pprint


def test_morningstar_via_yfinance():
    """
    Test accessing Morningstar data through yfinance.
    yfinance includes some Morningstar ratings and data.
    """
    
    symbol = "FPBFX"
    print(f"\n{'='*70}")
    print(f"Testing Morningstar data for {symbol} via yfinance")
    print(f"{'='*70}\n")
    
    ticker = yf.Ticker(symbol)
    info = ticker.info
    
    # Morningstar-specific fields in yfinance
    morningstar_fields = {
        'morningstarOverallRating': 'Overall star rating (1-5)',
        'morningstarRiskRating': 'Risk rating',
        'category': 'Morningstar category',
        'fundFamily': 'Fund family/provider',
        'legalType': 'Legal structure',
        'fundInceptionDate': 'Inception date',
        'totalAssets': 'Total assets under management',
        'ytdReturn': 'Year-to-date return',
        'threeYearAverageReturn': '3-year average return',
        'fiveYearAverageReturn': '5-year average return',
    }
    
    print("Morningstar-related fields from yfinance:")
    print("-" * 70)
    for field, description in morningstar_fields.items():
        value = info.get(field, 'NOT FOUND')
        # Convert value to string to handle different types
        value_str = str(value) if value is not None else 'None'
        print(f"{field:30s}: {value_str:30s} # {description}")
    
    return info


def test_morningstar_style_box():
    """
    Morningstar Style Box classification.
    For equity funds: Value/Blend/Growth x Large/Mid/Small
    For bond funds: Duration x Credit Quality
    """
    
    print(f"\n\n{'='*70}")
    print("Morningstar Style Box Analysis")
    print(f"{'='*70}\n")
    
    test_funds = {
        'FPBFX': 'FID PACIFIC BASIN (should be Global or Asia)',
        'VSMAX': 'Vanguard Small Cap Index (should be Small Blend)',
        'VFIAX': 'Vanguard 500 Index (should be Large Blend)',
        'VIGAX': 'Vanguard Growth Index (should be Large Growth)',
        'VVIAX': 'Vanguard Value Index (should be Large Value)',
    }
    
    print(f"{'Symbol':<10} {'Name':<35} {'Category':<25} {'Style'}")
    print("-" * 90)
    
    for symbol, expected in test_funds.items():
        try:
            ticker = yf.Ticker(symbol)
            info = ticker.info
            
            name = info.get('shortName', 'N/A')[:35]
            category = info.get('category', 'NOT FOUND')
            
            # Try to infer style from name/description
            description = info.get('longBusinessSummary', info.get('description', ''))
            
            style_hints = []
            if 'small' in description.lower():
                style_hints.append('Small')
            elif 'large' in description.lower():
                style_hints.append('Large')
            elif 'mid' in description.lower():
                style_hints.append('Mid')
            
            if 'growth' in description.lower():
                style_hints.append('Growth')
            elif 'value' in description.lower():
                style_hints.append('Value')
            elif 'blend' in description.lower():
                style_hints.append('Blend')
            
            style = ' '.join(style_hints) if style_hints else 'Unknown'
            
            print(f"{symbol:<10} {name:<35} {category:<25} {style}")
            
        except Exception as e:
            print(f"{symbol:<10} ERROR: {str(e)}")


def test_alternative_approaches():
    """
    Test alternative approaches to get fund category.
    """
    
    print(f"\n\n{'='*70}")
    print("Alternative Approaches for Fund Categorization")
    print(f"{'='*70}\n")
    
    symbol = "VSMAX"
    ticker = yf.Ticker(symbol)
    info = ticker.info
    
    print("Approach 1: Parse fund name")
    print("-" * 70)
    name = info.get('shortName', '')
    print(f"Fund name: {name}")
    
    # Common patterns in fund names
    name_lower = name.lower()
    if 'small' in name_lower and 'cap' in name_lower:
        if 'growth' in name_lower:
            category = 'Small Growth'
        elif 'value' in name_lower:
            category = 'Small Value'
        else:
            category = 'Small Blend'
        print(f"Inferred category: {category}")
    
    print("\n\nApproach 2: Use quoteType + fundFamily")
    print("-" * 70)
    quote_type = info.get('quoteType', 'N/A')
    fund_family = info.get('fundFamily', 'N/A')
    print(f"Quote Type: {quote_type}")
    print(f"Fund Family: {fund_family}")
    
    print("\n\nApproach 3: Check if category field exists but is empty")
    print("-" * 70)
    category = info.get('category')
    print(f"Category value: '{category}'")
    print(f"Category type: {type(category)}")
    print(f"Category is None: {category is None}")
    print(f"Category is empty string: {category == ''}")
    
    print("\n\nApproach 4: All info keys containing 'cat', 'style', or 'type'")
    print("-" * 70)
    relevant_keys = [k for k in info.keys() if any(word in k.lower() for word in ['cat', 'style', 'type', 'class'])]
    for key in sorted(relevant_keys):
        print(f"  {key:40s}: {info[key]}")


def recommendations():
    """
    Provide recommendations based on findings.
    """
    
    print(f"\n\n{'='*70}")
    print("RECOMMENDATIONS")
    print(f"{'='*70}\n")
    
    print("""
Based on yfinance limitations with mutual fund categories:

OPTION 1: Use yfinance 'category' field (if available)
  Pros: Direct from API, no parsing needed
  Cons: May be empty or unreliable for some funds
  
OPTION 2: Parse fund name for keywords
  Pros: Works for most Vanguard/Fidelity funds with descriptive names
  Cons: Requires pattern matching, may miss some funds
  Keywords: Small/Mid/Large + Growth/Value/Blend + Cap/Index
  
OPTION 3: Use fundFamily + legalType as fallback
  Pros: Always available
  Cons: Not as descriptive (e.g., "Vanguard" + "Open End Fund")
  
OPTION 4: Hybrid approach (RECOMMENDED)
  1. Try 'category' field first
  2. If empty, parse fund name for size/style keywords
  3. If still empty, use fundFamily as generic category
  4. Last resort: use quoteType (e.g., "MUTUALFUND")

OPTION 5: External Morningstar API (requires API key)
  Pros: Most accurate, comprehensive data
  Cons: Requires paid API subscription, additional dependency
  
RECOMMENDED IMPLEMENTATION:
  Use hybrid approach (Option 4) for best balance of accuracy and reliability.
  """)
    
    print("\nExample implementation:")
    print("-" * 70)
    print("""
def get_fund_category(symbol: str) -> str:
    ticker = yf.Ticker(symbol)
    info = ticker.info
    
    # Try category field
    category = info.get('category', '').strip()
    if category:
        return category
    
    # Parse fund name
    name = info.get('shortName', '').lower()
    
    # Size
    size = ''
    if 'small' in name and 'cap' in name:
        size = 'Small'
    elif 'mid' in name and 'cap' in name:
        size = 'Mid'
    elif 'large' in name and 'cap' in name:
        size = 'Large'
    
    # Style
    style = ''
    if 'growth' in name:
        style = 'Growth'
    elif 'value' in name:
        style = 'Value'
    elif 'blend' in name or 'index' in name:
        style = 'Blend'
    
    if size and style:
        return f"{size} {style}"
    
    # Fallback to fund family
    return info.get('fundFamily', info.get('quoteType', 'Mutual Fund'))
    """)


if __name__ == '__main__':
    test_morningstar_via_yfinance()
    test_morningstar_style_box()
    test_alternative_approaches()
    recommendations()
    
    print(f"\n\n{'='*70}")
    print("TEST COMPLETE")
    print(f"{'='*70}\n")
    
    print("\nNOTE: For production use with many funds, consider:")
    print("  - Caching results to avoid repeated API calls")
    print("  - Implementing retry logic for failed lookups")
    print("  - Maintaining a local mapping for common funds")
    print("  - Using Morningstar Direct API if budget allows")

# Made with Bob
