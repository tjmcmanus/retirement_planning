# Phase 3: Multi-Currency Support - Implementation Guide

## Executive Summary

**Status**: 📋 Ready for Implementation  
**Priority**: ⭐⭐ MEDIUM  
**Estimated Effort**: 2-3 weeks  
**Dependencies**: Phase 1 Complete ✅, Phase 2 Recommended  
**Last Updated**: March 23, 2026

This document provides a complete implementation guide for Phase 3 of the Brokerage Integration Enhancements, focusing on international holdings and multi-currency portfolio management.

---

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Implementation Components](#implementation-components)
4. [Currency Converter](#currency-converter)
5. [International Holdings](#international-holdings)
6. [Multi-Currency Cost Basis](#multi-currency-cost-basis)
7. [UI Integration](#ui-integration)
8. [Testing Strategy](#testing-strategy)
9. [Deployment Plan](#deployment-plan)

---

## Overview

### Goals

- **Multi-Currency Support**: Handle holdings in 20+ major currencies
- **Real-Time Exchange Rates**: Accurate, up-to-date currency conversion
- **Historical Rates**: Track exchange rates for cost basis calculations
- **Currency-Adjusted Returns**: Calculate performance in user's base currency
- **International Tax Reporting**: Support for foreign holdings tax implications

### Features

#### Currency Support
- **Major Currencies**: USD, EUR, GBP, JPY, CAD, AUD, CHF, CNY, HKD, SGD, NZD, SEK, NOK, DKK, KRW, INR, BRL, MXN, ZAR, RUB
- **Base Currency Selection**: User-selectable base currency (default USD)
- **Real-Time Rates**: Live exchange rates from multiple sources
- **Historical Rates**: 10+ years of historical data for cost basis
- **Rate Caching**: Intelligent caching to minimize API calls

#### International Holdings
- **Foreign Stocks**: TSX (Canada), LSE (UK), HKEX (Hong Kong), etc.
- **ADRs**: American Depositary Receipts
- **Foreign Bonds**: International fixed income
- **Foreign ETFs**: International exchange-traded funds
- **Currency Accounts**: Forex holdings

#### Reporting Features
- Multi-currency portfolio view
- Currency-adjusted returns
- Exchange rate impact analysis
- Foreign withholding tax tracking
- Currency hedging analysis

---

## Architecture

### System Design

```
┌─────────────────────────────────────────────────────────────┐
│                    Portfolio Application                     │
│  ┌────────────────────────────────────────────────────────┐ │
│  │              Currency Converter                        │ │
│  │  - Exchange Rate Fetching                              │ │
│  │  - Rate Caching (Redis/File)                           │ │
│  │  - Historical Rate Storage                             │ │
│  │  - Multi-Source Fallback                               │ │
│  └────────────────┬───────────────────────────────────────┘ │
│                   │                                          │
│  ┌────────────────▼───────────────────────────────────────┐ │
│  │         International Holdings Manager                 │ │
│  │  - Currency Detection                                  │ │
│  │  - Symbol Normalization                                │ │
│  │  - Exchange Identification                             │ │
│  │  - ADR Handling                                        │ │
│  └────────────────┬───────────────────────────────────────┘ │
│                   │                                          │
│  ┌────────────────▼───────────────────────────────────────┐ │
│  │         Multi-Currency Cost Basis                      │ │
│  │  - Purchase Currency Tracking                          │ │
│  │  - Historical Rate Lookup                              │ │
│  │  - Base Currency Conversion                            │ │
│  │  - Currency Gain/Loss Calculation                      │ │
│  └────────────────┬───────────────────────────────────────┘ │
│                   │                                          │
│  ┌────────────────▼───────────────────────────────────────┐ │
│  │              Portfolio Display                         │ │
│  │  - Multi-Currency View                                 │ │
│  │  - Currency Selector                                   │ │
│  │  - Exchange Rate Display                               │ │
│  │  - Currency Impact Analysis                            │ │
│  └────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘

External APIs:
┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐
│  Alpha Vantage   │  │ ExchangeRate-API │  │  ECB (Fallback)  │
│  (Primary)       │  │  (Secondary)     │  │  (Free)          │
└──────────────────┘  └──────────────────┘  └──────────────────┘
```

### Data Flow

```
International Holding Detected
         ↓
Identify Currency & Exchange
         ↓
Fetch Current Exchange Rate
         ↓
Convert to Base Currency
         ↓
Store Original & Converted Values
         ↓
Display in User's Preferred Currency

For Cost Basis:
Purchase Transaction → Lookup Historical Rate → Convert to Base Currency
Sale Transaction → Lookup Historical Rate → Calculate Currency Gain/Loss
```

---

## Implementation Components

### Component 1: Currency Converter

**File**: `components/currency_converter.py`

```python
"""
components/currency_converter.py
=================================
Multi-currency support with exchange rate management.

Features:
- Real-time exchange rates from multiple sources
- Historical rate tracking
- Intelligent caching
- Multi-source fallback
"""

import logging
import requests
from datetime import datetime, timedelta
from typing import Dict, Optional, List
import pandas as pd
from pathlib import Path
import json

logger = logging.getLogger(__name__)


class ExchangeRateSource:
    """Base class for exchange rate sources."""
    
    def get_rate(self, from_currency: str, to_currency: str, date: Optional[datetime] = None) -> Optional[float]:
        """Get exchange rate for currency pair."""
        raise NotImplementedError


class AlphaVantageSource(ExchangeRateSource):
    """Alpha Vantage exchange rate source."""
    
    BASE_URL = "https://www.alphavantage.co/query"
    
    def __init__(self, api_key: str):
        self.api_key = api_key
    
    def get_rate(self, from_currency: str, to_currency: str, date: Optional[datetime] = None) -> Optional[float]:
        """Get exchange rate from Alpha Vantage."""
        try:
            if date:
                # Historical rate
                params = {
                    'function': 'FX_DAILY',
                    'from_symbol': from_currency,
                    'to_symbol': to_currency,
                    'apikey': self.api_key,
                    'outputsize': 'full'
                }
            else:
                # Current rate
                params = {
                    'function': 'CURRENCY_EXCHANGE_RATE',
                    'from_currency': from_currency,
                    'to_currency': to_currency,
                    'apikey': self.api_key
                }
            
            response = requests.get(self.BASE_URL, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            if date:
                # Parse historical data
                time_series = data.get('Time Series FX (Daily)', {})
                date_str = date.strftime('%Y-%m-%d')
                
                # Try exact date first, then previous days
                for i in range(7):
                    check_date = (date - timedelta(days=i)).strftime('%Y-%m-%d')
                    if check_date in time_series:
                        return float(time_series[check_date]['4. close'])
                
                return None
            else:
                # Parse current rate
                rate_data = data.get('Realtime Currency Exchange Rate', {})
                return float(rate_data.get('5. Exchange Rate', 0))
        
        except Exception as e:
            logger.error(f"Alpha Vantage API error: {e}")
            return None


class ExchangeRateAPISource(ExchangeRateSource):
    """ExchangeRate-API source."""
    
    BASE_URL = "https://api.exchangerate-api.com/v4/latest"
    
    def get_rate(self, from_currency: str, to_currency: str, date: Optional[datetime] = None) -> Optional[float]:
        """Get exchange rate from ExchangeRate-API."""
        try:
            # This API doesn't support historical rates in free tier
            if date:
                return None
            
            url = f"{self.BASE_URL}/{from_currency}"
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            rates = data.get('rates', {})
            return rates.get(to_currency)
        
        except Exception as e:
            logger.error(f"ExchangeRate-API error: {e}")
            return None


class ECBSource(ExchangeRateSource):
    """European Central Bank exchange rate source (free, no API key)."""
    
    BASE_URL = "https://api.exchangerate.host"
    
    def get_rate(self, from_currency: str, to_currency: str, date: Optional[datetime] = None) -> Optional[float]:
        """Get exchange rate from ECB."""
        try:
            if date:
                date_str = date.strftime('%Y-%m-%d')
                url = f"{self.BASE_URL}/{date_str}"
            else:
                url = f"{self.BASE_URL}/latest"
            
            params = {
                'base': from_currency,
                'symbols': to_currency
            }
            
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            rates = data.get('rates', {})
            return rates.get(to_currency)
        
        except Exception as e:
            logger.error(f"ECB API error: {e}")
            return None


class CurrencyConverter:
    """
    Multi-currency converter with caching and fallback sources.
    
    Features:
    - Multiple exchange rate sources
    - Intelligent caching
    - Historical rate support
    - Automatic fallback
    """
    
    SUPPORTED_CURRENCIES = [
        'USD', 'EUR', 'GBP', 'JPY', 'CAD', 'AUD', 'CHF', 'CNY',
        'HKD', 'SGD', 'NZD', 'SEK', 'NOK', 'DKK', 'KRW', 'INR',
        'BRL', 'MXN', 'ZAR', 'RUB'
    ]
    
    def __init__(
        self,
        alpha_vantage_key: Optional[str] = None,
        cache_dir: str = "data/currency_cache"
    ):
        """
        Initialize currency converter.
        
        Args:
            alpha_vantage_key: Alpha Vantage API key (optional)
            cache_dir: Directory for rate caching
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize sources
        self.sources: List[ExchangeRateSource] = []
        
        if alpha_vantage_key:
            self.sources.append(AlphaVantageSource(alpha_vantage_key))
        
        self.sources.append(ExchangeRateAPISource())
        self.sources.append(ECBSource())
        
        # Load cache
        self.cache = self._load_cache()
        
        logger.info(f"Initialized CurrencyConverter with {len(self.sources)} sources")
    
    def convert(
        self,
        amount: float,
        from_currency: str,
        to_currency: str,
        date: Optional[datetime] = None
    ) -> Optional[float]:
        """
        Convert amount from one currency to another.
        
        Args:
            amount: Amount to convert
            from_currency: Source currency code
            to_currency: Target currency code
            date: Date for historical rate (None for current)
            
        Returns:
            Converted amount or None if conversion fails
        """
        # Same currency - no conversion needed
        if from_currency == to_currency:
            return amount
        
        # Get exchange rate
        rate = self.get_rate(from_currency, to_currency, date)
        
        if rate is None:
            logger.error(f"Failed to get rate for {from_currency}/{to_currency}")
            return None
        
        return amount * rate
    
    def get_rate(
        self,
        from_currency: str,
        to_currency: str,
        date: Optional[datetime] = None
    ) -> Optional[float]:
        """
        Get exchange rate for currency pair.
        
        Args:
            from_currency: Source currency code
            to_currency: Target currency code
            date: Date for historical rate (None for current)
            
        Returns:
            Exchange rate or None if not available
        """
        # Check cache first
        cache_key = self._get_cache_key(from_currency, to_currency, date)
        
        if cache_key in self.cache:
            cached_data = self.cache[cache_key]
            
            # Check if cache is still valid (1 hour for current, permanent for historical)
            if date or self._is_cache_valid(cached_data['timestamp']):
                return cached_data['rate']
        
        # Try each source
        for source in self.sources:
            try:
                rate = source.get_rate(from_currency, to_currency, date)
                
                if rate is not None:
                    # Cache the rate
                    self._cache_rate(from_currency, to_currency, date, rate)
                    return rate
            
            except Exception as e:
                logger.warning(f"Source {source.__class__.__name__} failed: {e}")
                continue
        
        logger.error(f"All sources failed for {from_currency}/{to_currency}")
        return None
    
    def get_supported_currencies(self) -> List[str]:
        """Get list of supported currency codes."""
        return self.SUPPORTED_CURRENCIES.copy()
    
    def _get_cache_key(
        self,
        from_currency: str,
        to_currency: str,
        date: Optional[datetime]
    ) -> str:
        """Generate cache key for currency pair."""
        if date:
            date_str = date.strftime('%Y-%m-%d')
            return f"{from_currency}_{to_currency}_{date_str}"
        else:
            return f"{from_currency}_{to_currency}_current"
    
    def _is_cache_valid(self, timestamp: str, max_age_hours: int = 1) -> bool:
        """Check if cached rate is still valid."""
        try:
            cached_time = datetime.fromisoformat(timestamp)
            age = datetime.now() - cached_time
            return age < timedelta(hours=max_age_hours)
        except:
            return False
    
    def _cache_rate(
        self,
        from_currency: str,
        to_currency: str,
        date: Optional[datetime],
        rate: float
    ) -> None:
        """Cache exchange rate."""
        cache_key = self._get_cache_key(from_currency, to_currency, date)
        
        self.cache[cache_key] = {
            'rate': rate,
            'timestamp': datetime.now().isoformat()
        }
        
        self._save_cache()
    
    def _load_cache(self) -> Dict:
        """Load cache from file."""
        cache_file = self.cache_dir / "rates.json"
        
        if cache_file.exists():
            try:
                with open(cache_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Failed to load cache: {e}")
        
        return {}
    
    def _save_cache(self) -> None:
        """Save cache to file."""
        cache_file = self.cache_dir / "rates.json"
        
        try:
            with open(cache_file, 'w') as f:
                json.dump(self.cache, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save cache: {e}")
    
    def clear_cache(self) -> None:
        """Clear all cached rates."""
        self.cache = {}
        self._save_cache()
        logger.info("Currency cache cleared")


class CurrencyDetector:
    """Detect currency from symbol and exchange."""
    
    EXCHANGE_CURRENCIES = {
        'NYSE': 'USD',
        'NASDAQ': 'USD',
        'AMEX': 'USD',
        'TSX': 'CAD',
        'TSE': 'JPY',
        'LSE': 'GBP',
        'HKEX': 'HKD',
        'ASX': 'AUD',
        'SIX': 'CHF',
        'XETRA': 'EUR',
        'EURONEXT': 'EUR',
        'BME': 'EUR',
        'BIT': 'EUR'
    }
    
    @classmethod
    def detect_currency(cls, symbol: str, exchange: Optional[str] = None) -> str:
        """
        Detect currency from symbol and exchange.
        
        Args:
            symbol: Security symbol
            exchange: Exchange code
            
        Returns:
            Currency code (default USD)
        """
        # Check exchange first
        if exchange and exchange.upper() in cls.EXCHANGE_CURRENCIES:
            return cls.EXCHANGE_CURRENCIES[exchange.upper()]
        
        # Check symbol suffix (e.g., AAPL.TO for Toronto)
        if '.' in symbol:
            suffix = symbol.split('.')[-1].upper()
            
            suffix_map = {
                'TO': 'CAD',  # Toronto
                'L': 'GBP',   # London
                'HK': 'HKD',  # Hong Kong
                'AX': 'AUD',  # Australia
                'SW': 'CHF',  # Switzerland
                'DE': 'EUR',  # Germany
                'PA': 'EUR',  # Paris
            }
            
            if suffix in suffix_map:
                return suffix_map[suffix]
        
        # Default to USD
        return 'USD'
```

### Component 2: International Holdings Manager

**File**: `components/international_holdings.py`

```python
"""
components/international_holdings.py
====================================
Manage international securities and multi-currency holdings.
"""

import logging
import pandas as pd
from typing import Dict, Optional
from datetime import datetime

from components.currency_converter import CurrencyConverter, CurrencyDetector

logger = logging.getLogger(__name__)


class InternationalHoldingsManager:
    """
    Manage international holdings with currency conversion.
    
    Features:
    - Currency detection
    - Automatic conversion to base currency
    - ADR handling
    - Exchange identification
    """
    
    def __init__(
        self,
        currency_converter: CurrencyConverter,
        base_currency: str = 'USD'
    ):
        """
        Initialize international holdings manager.
        
        Args:
            currency_converter: Currency converter instance
            base_currency: User's base currency
        """
        self.converter = currency_converter
        self.base_currency = base_currency
    
    def process_holdings(self, holdings_df: pd.DataFrame) -> pd.DataFrame:
        """
        Process holdings with currency conversion.
        
        Args:
            holdings_df: Holdings DataFrame
            
        Returns:
            Holdings with currency information and conversions
        """
        if holdings_df.empty:
            return holdings_df
        
        # Add currency columns
        holdings_df['currency'] = holdings_df.apply(
            lambda row: self._detect_currency(row),
            axis=1
        )
        
        # Store original values
        holdings_df['value_original'] = holdings_df.get('value', 0)
        holdings_df['currency_original'] = holdings_df['currency']
        
        # Convert to base currency
        holdings_df['value_base'] = holdings_df.apply(
            lambda row: self._convert_to_base(row),
            axis=1
        )
        
        holdings_df['currency_base'] = self.base_currency
        
        # Calculate exchange rate used
        holdings_df['exchange_rate'] = holdings_df.apply(
            lambda row: self._get_exchange_rate(row),
            axis=1
        )
        
        return holdings_df
    
    def _detect_currency(self, row: pd.Series) -> str:
        """Detect currency for holding."""
        # Check if currency is already specified
        if 'currency' in row and pd.notna(row['currency']):
            return row['currency']
        
        # Detect from symbol and exchange
        symbol = row.get('symbol', '')
        exchange = row.get('exchange', None)
        
        return CurrencyDetector.detect_currency(symbol, exchange)
    
    def _convert_to_base(self, row: pd.Series) -> float:
        """Convert holding value to base currency."""
        value = row.get('value_original', row.get('value', 0))
        currency = row.get('currency', 'USD')
        
        if currency == self.base_currency:
            return value
        
        converted = self.converter.convert(
            amount=value,
            from_currency=currency,
            to_currency=self.base_currency
        )
        
        return converted if converted is not None else value
    
    def _get_exchange_rate(self, row: pd.Series) -> Optional[float]:
        """Get exchange rate used for conversion."""
        currency = row.get('currency', 'USD')
        
        if currency == self.base_currency:
            return 1.0
        
        return self.converter.get_rate(currency, self.base_currency)
    
    def get_currency_breakdown(self, holdings_df: pd.DataFrame) -> pd.DataFrame:
        """
        Get breakdown of holdings by currency.
        
        Args:
            holdings_df: Holdings DataFrame
            
        Returns:
            Currency breakdown DataFrame
        """
        if holdings_df.empty:
            return pd.DataFrame()
        
        breakdown = holdings_df.groupby('currency_original').agg({
            'value_original': 'sum',
            'value_base': 'sum'
        }).reset_index()
        
        breakdown.columns = ['currency', 'value_original', 'value_base']
        
        # Calculate percentage
        total_value = breakdown['value_base'].sum()
        breakdown['percentage'] = (breakdown['value_base'] / total_value * 100).round(2)
        
        return breakdown.sort_values('value_base', ascending=False)
```

### Component 3: Multi-Currency Cost Basis

**File**: `components/multi_currency_cost_basis.py`

```python
"""
components/multi_currency_cost_basis.py
========================================
Cost basis tracking with multi-currency support.
"""

import logging
import pandas as pd
from datetime import datetime
from typing import Dict, List, Optional

from components.currency_converter import CurrencyConverter

logger = logging.getLogger(__name__)


class MultiCurrencyCostBasis:
    """
    Track cost basis across multiple currencies.
    
    Features:
    - Purchase currency tracking
    - Historical rate lookup
    - Currency gain/loss calculation
    - Base currency conversion
    """
    
    def __init__(
        self,
        currency_converter: CurrencyConverter,
        base_currency: str = 'USD'
    ):
        """
        Initialize multi-currency cost basis tracker.
        
        Args:
            currency_converter: Currency converter instance
            base_currency: User's base currency
        """
        self.converter = currency_converter
        self.base_currency = base_currency
    
    def calculate_gains_with_currency(
        self,
        transactions_df: pd.DataFrame
    ) -> pd.DataFrame:
        """
        Calculate gains/losses including currency effects.
        
        Args:
            transactions_df: Transaction history
            
        Returns:
            DataFrame with gains including currency effects
        """
        if transactions_df.empty:
            return pd.DataFrame()
        
        # Ensure required columns exist
        required_cols = ['date', 'type', 'symbol', 'quantity', 'price', 'currency']
        if not all(col in transactions_df.columns for col in required_cols):
            logger.error("Missing required columns for cost basis calculation")
            return pd.DataFrame()
        
        # Sort by date
        transactions_df = transactions_df.sort_values('date').copy()
        
        # Calculate gains for each symbol
        gains_list = []
        
        for symbol in transactions_df['symbol'].unique():
            symbol_txns = transactions_df[transactions_df['symbol'] == symbol]
            symbol_gains = self._calculate_symbol_gains(symbol_txns)
            gains_list.extend(symbol_gains)
        
        if not gains_list:
            return pd.DataFrame()
        
        gains_df = pd.DataFrame(gains_list)
        
        return gains_df
    
    def _calculate_symbol_gains(self, transactions: pd.DataFrame) -> List[Dict]:
        """Calculate gains for a single symbol."""
        gains = []
        lots = []  # Purchase lots (FIFO queue)
        
        for _, txn in transactions.iterrows():
            if txn['type'] == 'BUY':
                # Add to lots
                lot = {
                    'date': txn['date'],
                    'quantity': txn['quantity'],
                    'price': txn['price'],
                    'currency': txn['currency'],
                    'cost_base': self._convert_to_base_historical(
                        txn['price'] * txn['quantity'],
                        txn['currency'],
                        txn['date']
                    )
                }
                lots.append(lot)
            
            elif txn['type'] == 'SELL':
                # Match with lots (FIFO)
                remaining_qty = txn['quantity']
                
                while remaining_qty > 0 and lots:
                    lot = lots[0]
                    
                    # Determine quantity to match
                    match_qty = min(remaining_qty, lot['quantity'])
                    
                    # Calculate proceeds in base currency
                    proceeds_base = self._convert_to_base_historical(
                        txn['price'] * match_qty,
                        txn['currency'],
                        txn['date']
                    )
                    
                    # Calculate cost basis in base currency
                    cost_base = (lot['cost_base'] / lot['quantity']) * match_qty
                    
                    # Calculate gain/loss
                    gain_loss = proceeds_base - cost_base
                    
                    # Calculate currency gain/loss
                    currency_gain = self._calculate_currency_gain(
                        lot, match_qty, txn, proceeds_base
                    )
                    
                    gains.append({
                        'symbol': txn['symbol'],
                        'sale_date': txn['date'],
                        'purchase_date': lot['date'],
                        'quantity': match_qty,
                        'proceeds': proceeds_base,
                        'cost_basis': cost_base,
                        'gain_loss': gain_loss,
                        'currency_gain': currency_gain,
                        'total_gain': gain_loss,
                        'holding_period': (txn['date'] - lot['date']).days
                    })
                    
                    # Update lot
                    lot['quantity'] -= match_qty
                    remaining_qty -= match_qty
                    
                    if lot['quantity'] <= 0:
                        lots.pop(0)
        
        return gains
    
    def _convert_to_base_historical(
        self,
        amount: float,
        currency: str,
        date: datetime
    ) -> float:
        """Convert amount to base currency using historical rate."""
        if currency == self.base_currency:
            return amount
        
        converted = self.converter.convert(
            amount=amount,
            from_currency=currency,
            to_currency=self.base_currency,
            date=date
        )
        
        return converted if converted is not None else amount
    
    def _calculate_currency_gain(
        self,
        purchase_lot: Dict,
        quantity: float,
        sale_txn: pd.Series,
        proceeds_base: float
    ) -> float:
        """Calculate gain/loss due to currency fluctuation."""
        # This is a simplified calculation
        # In practice, you'd track the exact currency movements
        
        if purchase_lot['currency'] == sale_txn['currency']:
            return 0.0
        
        # Calculate what proceeds would have been at purchase rate
        purchase_rate = self.converter.get_rate(
            purchase_lot['currency'],
            self.base_currency,
            purchase_lot['date']
        )
        
        sale_rate = self.converter.get_rate(
            sale_txn['currency'],
            self.base_currency,
            sale_txn['date']
        )
        
        if purchase_rate and sale_rate:
            # Currency effect
            return proceeds_base * ((sale_rate - purchase_rate) / sale_rate)
        
        return 0.0
```

---

## UI Integration

### Portfolio Hub Currency Selector

**File**: `pages/4_portfolio_hub.py` (additions)

```python
def render_currency_selector():
    """Render currency selection UI."""
    st.markdown("### 💱 Currency Settings")
    
    # Initialize currency converter
    if 'currency_converter' not in st.session_state:
        from components.currency_converter import CurrencyConverter
        import os
        
        alpha_vantage_key = os.getenv('ALPHA_VANTAGE_API_KEY')
        st.session_state.currency_converter = CurrencyConverter(alpha_vantage_key)
    
    converter = st.session_state.currency_converter
    
    col1, col2 = st.columns(2)
    
    with col1:
        base_currency = st.selectbox(
            "Base Currency",
            options=converter.get_supported_currencies(),
            index=0,  # USD default
            help="Your preferred currency for portfolio display"
        )
        
        st.session_state.base_currency = base_currency
    
    with col2:
        if st.button("🔄 Refresh Exchange Rates"):
            converter.clear_cache()
            st.success("✅ Exchange rates refreshed!")
    
    # Show current rates for major currencies
    st.markdown("#### Current Exchange Rates")
    
    major_currencies = ['EUR', 'GBP', 'JPY', 'CAD', 'AUD']
    rates_data = []
    
    for currency in major_currencies:
        if currency != base_currency:
            rate = converter.get_rate(currency, base_currency)
            if rate:
                rates_data.append({
                    'Currency': currency,
                    'Rate': f"{rate:.4f}",
                    f'1 {currency} =': f"{rate:.4f} {base_currency}"
                })
    
    if rates_data:
        st.dataframe(pd.DataFrame(rates_data), use_container_width=True)


def render_currency_breakdown(holdings_df: pd.DataFrame):
    """Render currency breakdown of portfolio."""
    from components.international_holdings import InternationalHoldingsManager
    
    if 'currency_converter' not in st.session_state:
        return
    
    base_currency = st.session_state.get('base_currency', 'USD')
    
    manager = InternationalHoldingsManager(
        st.session_state.currency_converter,
        base_currency
    )
    
    # Process holdings
    processed_holdings = manager.process_holdings(holdings_df)
    
    # Get currency breakdown
    breakdown = manager.get_currency_breakdown(processed_holdings)
    
    if not breakdown.empty:
        st.markdown("### 🌍 Currency Exposure")
        
        # Display as chart
        import plotly.express as px
        
        fig = px.pie(
            breakdown,
            values='value_base',
            names='currency',
            title=f'Portfolio by Currency (in {base_currency})'
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
        # Display as table
        st.dataframe(
            breakdown.style.format({
                'value_original': '${:,.2f}',
                'value_base': '${:,.2f}',
                'percentage': '{:.1f}%'
            }),
            use_container_width=True
        )
```

---

## Testing Strategy

### Unit Tests

**File**: `test_currency_converter.py`

```python
"""Tests for currency converter."""

import pytest
from datetime import datetime
from components.currency_converter import CurrencyConverter, CurrencyDetector


def test_currency_detection():
    """Test currency detection from symbols."""
    assert CurrencyDetector.detect_currency('AAPL') == 'USD'
    assert CurrencyDetector.detect_currency('AAPL.TO') == 'CAD'
    assert CurrencyDetector.detect_currency('VOD.L') == 'GBP'
    assert CurrencyDetector.detect_currency('0700.HK') == 'HKD'


def test_same_currency_conversion():
    """Test conversion between same currency."""
    converter = CurrencyConverter()
    
    result = converter.convert(100, 'USD', 'USD')
    assert result == 100


def test_supported_currencies():
    """Test supported currencies list."""
    converter = CurrencyConverter()
    
    currencies = converter.get_supported_currencies()
    assert 'USD' in currencies
    assert 'EUR' in currencies
    assert 'GBP' in currencies
    assert len(currencies) >= 20


def test_cache_functionality():
    """Test rate caching."""
    converter = CurrencyConverter()
    
    # First call - should fetch from API
    rate1 = converter.get_rate('EUR', 'USD')
    
    # Second call - should use cache
    rate2 = converter.get_rate('EUR', 'USD')
    
    assert rate1 == rate2
```

---

## Deployment Plan

### Week 1: Currency Infrastructure
- [ ] Implement `CurrencyConverter` class
- [ ] Integrate exchange rate APIs
- [ ] Implement rate caching
- [ ] Add historical rate tracking
- [ ] Write unit tests

### Week 2: International Holdings
- [ ] Implement `InternationalHoldingsManager`
- [ ] Add currency detection
- [ ] Implement multi-currency cost basis
- [ ] Add currency breakdown views
- [ ] Integration testing

### Week 3: UI & Polish
- [ ] Add currency selector UI
- [ ] Implement currency breakdown charts
- [ ] Add exchange rate display
- [ ] Performance optimization
- [ ] Documentation
- [ ] User acceptance testing

---

## Success Metrics

- ✅ Support 20+ currencies
- ✅ Exchange rate accuracy within 0.1%
- ✅ <5 second currency conversion
- ✅ Historical rate availability 10+ years
- ✅ 99.9% API uptime

---

## Next Steps

1. Review and approve implementation plan
2. Obtain API keys (Alpha Vantage recommended)
3. Begin Week 1 implementation
4. Schedule weekly progress reviews

---

**Document Version**: 1.0  
**Status**: 📋 Ready for Implementation  
**Previous Phase**: Real-Time Sync (Phase 2)