"""
components/fund_type_inference.py
==================================
Intelligent fund type inference from fund names and symbols.

Analyzes fund names to determine appropriate MF: categories:
- MF:US (US equity funds)
- MF:Global (International/global equity funds)
- MF:Bond (Bond/fixed income funds)
- MF:Balanced (Balanced/target date funds)
- MF:Commodity (Commodity/real estate funds)
- Empty string if cannot determine with confidence
"""

import re
import logging
from typing import Optional

logger = logging.getLogger(__name__)


# Keywords for each fund category
# Priority order for categories (checked first to last)
# More specific categories should be checked before generic ones
FUND_TYPE_KEYWORDS = {
    'MF:Bond': [
        # Bond types
        'bond', 'fixed income', 'treasury', 'government', 'municipal', 'corporate bond',
        'high yield', 'investment grade', 'income', 'debt',
        # Specific bond terms
        'tips', 'inflation protected', 'aggregate bond', 'total bond',
        'short term bond', 'intermediate bond', 'long term bond', 'long-term',
        'credit', 'mortgage', 'asset backed',
    ],
    
    'MF:Global': [
        # International regions (higher priority - check before US)
        'international', 'global', 'world', 'foreign', 'overseas',
        'emerging market', 'emerging', 'developed market',
        # Specific regions/countries
        'europe', 'european', 'asia', 'asian', 'pacific', 'latin america',
        'china', 'japan', 'india', 'ex-us', 'ex us', 'eafe',
        # Regional descriptors
        'pacific-basin', 'pacific basin', 'far east', 'middle east',
        'africa', 'frontier',
    ],
    
    'MF:Commodity': [
        # Real estate (check before generic terms)
        'real estate', 'reit', 'property', 'realty',
        # Commodities
        'commodity', 'commodities', 'natural resources', 'precious metals',
        'gold', 'silver', 'energy', 'materials',
    ],
    
    'MF:Balanced': [
        # Balanced/mixed
        'balanced', 'allocation', 'target date', 'target retirement',
        'lifecycle', 'life cycle', 'retirement', 'moderate',
        'conservative allocation', 'aggressive allocation',
        # Multi-asset
        'multi-asset', 'diversified', 'income and growth',
    ],
    
    'MF:US': [
        # US equity indicators (only if no other category matches)
        'us equity', 'u.s. equity', 'american', 'domestic',
        'large cap', 'mid cap', 'small cap', 'mega cap',
        'growth', 'value', 'blend', 'core',
        's&p 500', 's&p500', 'dow jones', 'russell',
        'dividend', 'equity income', 'stock',
        'total stock', 'total market',
        '500 index',  # Matches "500 Index Fund"
    ],
}

# Additional patterns for special cases
SPECIAL_PATTERNS = {
    'MF:Balanced': [
        r'\bwellington\b',  # Vanguard Wellington is a balanced fund
        r'\bwellesley\b',   # Vanguard Wellesley is also balanced
    ],
}


def infer_fund_type(symbol: str, fund_name: str) -> str:
    """
    Infer the fund type (sector) from symbol and fund name.
    
    Args:
        symbol: Fund ticker symbol (e.g., 'VUSUX', 'FPBFX')
        fund_name: Full fund name (e.g., 'Vanguard Long-Term Treasury Fund Admiral')
    
    Returns:
        Fund type string (e.g., 'MF:Bond', 'MF:Global') or empty string if cannot determine
    
    Examples:
        >>> infer_fund_type('VUSUX', 'Vanguard Long-Term Treasury Fund Admiral')
        'MF:Bond'
        
        >>> infer_fund_type('FPBFX', 'Fidelity Pacific-Basin Fund')
        'MF:Global'
        
        >>> infer_fund_type('VTSAX', 'Vanguard Total Stock Market Index Fund')
        'MF:US'
    """
    if not fund_name:
        logger.debug(f"No fund name provided for symbol {symbol}")
        return ''
    
    # Normalize the fund name for matching
    name_lower = fund_name.lower()
    
    # Check special patterns first (regex-based)
    for category, patterns in SPECIAL_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, name_lower):
                logger.info(f"Matched special pattern '{pattern}' for {category}")
                return category
    
    # Score each category based on keyword matches
    scores = {category: 0 for category in FUND_TYPE_KEYWORDS.keys()}
    
    for category, keywords in FUND_TYPE_KEYWORDS.items():
        for keyword in keywords:
            # Use word boundaries for more accurate matching
            pattern = r'\b' + re.escape(keyword) + r'\b'
            if re.search(pattern, name_lower):
                # Weight longer keywords more heavily (more specific)
                weight = len(keyword.split())
                scores[category] += weight
                logger.debug(f"Matched '{keyword}' for {category} (weight: {weight})")
    
    # Find the category with the highest score
    max_score = max(scores.values())
    
    if max_score == 0:
        logger.info(f"Could not infer fund type for '{fund_name}' - no keyword matches")
        return ''
    
    # Get all categories with the max score
    top_categories = [cat for cat, score in scores.items() if score == max_score]
    
    # Priority order if there's a tie (more specific categories first)
    priority_order = ['MF:Bond', 'MF:Global', 'MF:Commodity', 'MF:Balanced', 'MF:US']
    
    for category in priority_order:
        if category in top_categories:
            logger.info(f"Inferred fund type '{category}' for '{fund_name}' (score: {max_score})")
            return category
    
    # Fallback to first match (shouldn't happen with priority order)
    result = top_categories[0]
    logger.info(f"Inferred fund type '{result}' for '{fund_name}' (score: {max_score})")
    return result


def get_fund_type_for_holding(symbol: str, name: str, symbol_type_code: str) -> str:
    """
    Get fund type for a holding, only if it's a fund (OEF, CEF, ETF).
    
    Args:
        symbol: Fund ticker symbol
        name: Fund name
        symbol_type_code: Type code from brokerage (e.g., 'oef', 'cef', 'etf', 'cs')
    
    Returns:
        Fund type string or empty string
    """
    # Only infer for funds, not individual stocks
    if symbol_type_code.lower() not in ['oef', 'cef', 'etf']:
        logger.debug(f"Symbol {symbol} is not a fund (type: {symbol_type_code}), skipping inference")
        return ''
    
    return infer_fund_type(symbol, name)


# Test cases for validation
if __name__ == '__main__':
    # Configure logging for tests
    logging.basicConfig(level=logging.INFO)
    
    test_cases = [
        ('VUSUX', 'Vanguard Long-Term Treasury Fund Admiral', 'MF:Bond'),
        ('FPBFX', 'Fidelity Pacific-Basin Fund', 'MF:Global'),
        ('VTSAX', 'Vanguard Total Stock Market Index Fund', 'MF:US'),
        ('VBTLX', 'Vanguard Total Bond Market Index Fund', 'MF:Bond'),
        ('VTIAX', 'Vanguard Total International Stock Index Fund', 'MF:Global'),
        ('VWELX', 'Vanguard Wellington Fund', 'MF:Balanced'),
        ('VGSIX', 'Vanguard REIT Index Fund', 'MF:Commodity'),
        ('PRRRX', 'PIMCO Real Estate Real Return Strategy Fund', 'MF:Commodity'),
        ('VFIAX', 'Vanguard 500 Index Fund', 'MF:US'),
        ('VGSLX', 'Vanguard Real Estate Index Fund', 'MF:Commodity'),
        ('VTMFX', 'Vanguard Target Retirement 2025 Fund', 'MF:Balanced'),
        ('VEMBX', 'Vanguard Emerging Markets Bond Index Fund', 'MF:Bond'),  # Bond takes priority over Global
        ('UNKNOWN', 'Some Random Fund Name', ''),  # Should return empty
    ]
    
    print("Running fund type inference tests...\n")
    passed = 0
    failed = 0
    
    for symbol, name, expected in test_cases:
        result = infer_fund_type(symbol, name)
        status = "✓ PASS" if result == expected else "✗ FAIL"
        if result == expected:
            passed += 1
        else:
            failed += 1
        print(f"{status}: {symbol} - {name}")
        print(f"  Expected: '{expected}', Got: '{result}'")
        print()
    
    print(f"\nResults: {passed} passed, {failed} failed out of {len(test_cases)} tests")

# Made with Bob
