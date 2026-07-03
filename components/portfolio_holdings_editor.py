"""
components/portfolio_holdings_editor.py
========================================
Portfolio Holdings Editor Component - Inline editable table for managing portfolio holdings.

Features:
- Inline editable data table using st.data_editor
- Add/delete row functionality
- Real-time validation (ticker symbols, dates, numbers)
- Automatic price fetching on symbol entry
- Save to portfolio_data_truth.csv
- Import from CSV
- Copy from previous month
- Backup management
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Tuple
import os
import shutil
from datetime import datetime, date

import pandas as pd
import streamlit as st
import yfinance as yf

if TYPE_CHECKING:
    from pandas import DataFrame

from portfolio_data_entry import (
    PORTFOLIO_TRUTH_FILE,
    VALID_ACCOUNT_TYPES,
    VALID_ACCOUNT_OWNERS,
    VALID_SECTORS,
    get_valid_account_owners,
    validate_ticker_symbol,
    validate_portfolio_entry,
    save_portfolio_data,
)
from portfolio_db import db_get_by_month, db_load_all, db_upsert, db_overwrite_month, enrich_holdings
from portfolio_market_indicators import (
    calculate_security_indicator,
    get_portfolio_indicators,
    SecurityMarketCondition,
)


def get_current_price(symbol: str) -> float:
    """
    Fetch current price for a ticker symbol.
    Mutual funds need longer period as they update less frequently.
    Options contracts return 0.0 (manual entry required).
    
    Args:
        symbol: Ticker symbol (e.g., 'AAPL', 'GOOGL', 'SOFI  260402C00020000')
    
    Returns:
        Current price, or 1.0 for cash/money market, or 0.0 for options
    """
    if symbol.upper() in ['MF:CASH', 'CASH']:
        return 1.0
    
    # Check if this is an options contract
    from portfolio_data_entry import is_option_symbol
    is_option, underlying, option_type = is_option_symbol(symbol)
    
    if is_option:
        # Options contracts don't have reliable price data in yfinance
        # Return 0.0 to indicate manual price entry is needed
        return 0.0
    
    try:
        ticker = yf.Ticker(symbol)
        
        # Mutual funds (5-letter tickers) need longer period
        if len(symbol) == 5 and symbol.isalpha():
            period = '5d'
        else:
            period = '1d'
        
        hist = ticker.history(period=period)
        if not hist.empty:
            return float(hist['Close'].iloc[-1])
        return 0.0
    except Exception:
        return 0.0


def get_sector_from_yfinance(symbol: str) -> str:
    """
    Fetch sector information from Yahoo Finance.
    For mutual funds (5-letter tickers), uses 'category' field.
    For stocks/ETFs, uses 'sector' field.
    For options contracts, returns 'Options:Call' or 'Options:Put'.
    
    Args:
        symbol: Ticker symbol
    
    Returns:
        Sector name or empty string if not found
    """
    if symbol.upper() in ['MF:CASH', 'CASH']:
        return 'Cash'
    
    # Check if this is an options contract
    from portfolio_data_entry import is_option_symbol
    is_option, underlying, option_type = is_option_symbol(symbol)
    
    if is_option:
        return f'Options:{option_type}'
    
    try:
        ticker = yf.Ticker(symbol)
        info = ticker.info
        
        # For mutual funds (5-letter alphabetic tickers), use 'category' field
        # Note: yfinance uses 'category' not 'categoryName' for mutual funds
        if len(symbol) == 5 and symbol.isalpha():
            category = info.get('category', '')
            if category:
                return category
        
        # For stocks/ETFs, use sector
        sector = info.get('sector', '')
        if sector:
            return sector
        
        # Fallback to category if sector not found
        category = info.get('category', '')
        if category:
            return category
        
        # Last resort: use quoteType
        quote_type = info.get('quoteType', '')
        return quote_type if quote_type else ''
        
    except Exception as e:
        return ''


def create_empty_row(month: int, year: int) -> dict:
    """
    Create an empty row template for new holdings.
    
    Args:
        month: Month (1-12)
        year: Year (e.g., 2026)
    
    Returns:
        Dictionary with empty/default values
    """
    return {
        'month': month,
        'year': year,
        'account_name': '',
        'account_type': 'Brokerage',
        'owner': 'Joint',
        'symbol': '',
        'name': '',
        'sector': '',
        'qty': 0.0,
        'purchase_price': 0.0,
        'purchase_date': date.today().strftime('%Y-%m-%d'),
    }


def load_portfolio_data(month: int, year: int) -> DataFrame:
    """
    Load portfolio data for a specific month/year from portfolio.db.

    Args:
        month: Month (1-12)
        year: Year (e.g., 2026)

    Returns:
        DataFrame with portfolio holdings for the specified month/year
    """
    required_cols = [
        'month', 'year', 'account_name', 'account_type', 'owner',
        'symbol', 'name', 'sector', 'qty', 'purchase_price', 'purchase_date',
    ]
    filtered = db_get_by_month(month, year).copy()

    if filtered.empty:
        return pd.DataFrame({
            'month': pd.Series(dtype='int'),
            'year': pd.Series(dtype='int'),
            'account_name': pd.Series(dtype='str'),
            'account_type': pd.Series(dtype='str'),
            'owner': pd.Series(dtype='str'),
            'symbol': pd.Series(dtype='str'),
            'name': pd.Series(dtype='str'),
            'sector': pd.Series(dtype='str'),
            'qty': pd.Series(dtype='float'),
            'purchase_price': pd.Series(dtype='float'),
            'purchase_date': pd.Series(dtype='datetime64[ns]'),
        })

    # Fill missing owner values with 'Joint' as default
    filtered['owner'] = filtered['owner'].fillna('Joint')
    filtered.loc[filtered['owner'].astype(str).str.strip() == '', 'owner'] = 'Joint'

    # Convert purchase_date to datetime for compatibility with DateColumn
    if not filtered.empty:
        filtered['purchase_date'] = pd.to_datetime(filtered['purchase_date'], errors='coerce')

    result: DataFrame = filtered[required_cols]  # type: ignore[assignment]
    return result


def copy_from_previous_month(month: int, year: int) -> Tuple[bool, str, DataFrame]:
    """
    Copy holdings from the previous month.
    
    Args:
        month: Target month (1-12)
        year: Target year (e.g., 2026)
    
    Returns:
        Tuple of (success, message, dataframe)
    """
    # Calculate previous month/year
    prev_month = month - 1 if month > 1 else 12
    prev_year = year if month > 1 else year - 1
    
    prev_data = db_get_by_month(prev_month, prev_year).copy()

    if prev_data.empty:
        return False, f"No data found for {prev_month}/{prev_year}", pd.DataFrame()
    
    # Update month/year to current
    prev_data['month'] = month
    prev_data['year'] = year
    
    # Convert purchase_date to datetime for compatibility with DateColumn
    if 'purchase_date' in prev_data.columns:
        prev_data['purchase_date'] = pd.to_datetime(prev_data['purchase_date'], errors='coerce')
    
    result_df: DataFrame = prev_data  # type: ignore[assignment]
    return True, f"Copied {len(prev_data)} holdings from {prev_month}/{prev_year}", result_df


def create_backup() -> Tuple[bool, str]:
    """
    Export a timestamped CSV backup from portfolio.db.

    Returns:
        Tuple of (success, message)
    """
    try:
        from portfolio_db import db_load_all
        df = db_load_all()
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_file = f'portfolio_data_truth_backup_{timestamp}.csv'
        df.to_csv(backup_file, index=False)
        return True, f"Backup created: {backup_file} ({len(df)} rows)"
    except Exception as e:
        return False, f"Backup failed: {str(e)}"


def render_holdings_tab(
    portdf: DataFrame,
    curr_month: int,
    curr_year: int,
    _eff_port_month: int,
    _eff_port_year: int,
) -> None:
    """
    Render the Holdings editor tab.
    
    Args:
        portdf: Current portfolio display DataFrame (for reference)
        curr_month: Current month (1-12)
        curr_year: Current year
        _eff_port_month: Effective portfolio month (may differ if data stale)
        _eff_port_year: Effective portfolio year
    """
    st.markdown("### 📝 Portfolio Holdings Editor")
    st.caption("Edit your portfolio holdings inline. Changes are saved to portfolio_data_truth.csv")
    
    # Initialize session state for holdings data
    if 'holdings_data' not in st.session_state:
        st.session_state.holdings_data = load_portfolio_data(curr_month, curr_year)
    
    if 'holdings_modified' not in st.session_state:
        st.session_state.holdings_modified = False
    
    # ========================================================================
    # TOOLBAR - Quick Actions
    # ========================================================================
    st.markdown("#### ⚡ Quick Actions")
    
    col1, col2, col3, col4, col5 = st.columns(5)
    
    with col1:
        if st.button("➕ Add Row", use_container_width=True, help="Add a new empty row"):
            new_row = create_empty_row(curr_month, curr_year)
            st.session_state.holdings_data = pd.concat([
                st.session_state.holdings_data,
                pd.DataFrame([new_row])
            ], ignore_index=True)
            st.session_state.holdings_modified = True
            st.rerun()
    
    with col2:
        if st.button("📋 Copy Previous", use_container_width=True, help="Copy holdings from previous month"):
            success, message, prev_data = copy_from_previous_month(curr_month, curr_year)
            if success:
                st.session_state.holdings_data = prev_data
                st.session_state.holdings_modified = True
                st.success(message)
                st.rerun()
            else:
                st.error(message)
    
    with col3:
        if st.button("🔄 Reload", use_container_width=True, help="Reload from file (discard unsaved changes)"):
            st.session_state.holdings_data = load_portfolio_data(curr_month, curr_year)
            st.session_state.holdings_modified = False
            st.info("Data reloaded from file")
            st.rerun()
    
    with col4:
        if st.button("💾 Backup", use_container_width=True, help="Create a backup of portfolio data"):
            success, message = create_backup()
            if success:
                st.success(message)
            else:
                st.error(message)
    
    with col5:
        # File upload for CSV import
        uploaded_file = st.file_uploader(
            "📥 Import CSV",
            type=['csv'],
            help="Import holdings from CSV file",
            label_visibility="collapsed",
            key="csv_upload"
        )
        if uploaded_file is not None:
            try:
                imported_data = pd.read_csv(uploaded_file)
                # Validate required columns
                required_cols = ['month', 'year', 'account_name', 'account_type', 'owner',
                                'symbol', 'name', 'sector', 'qty', 'purchase_price']
                if all(col in imported_data.columns for col in required_cols):
                    st.session_state.holdings_data = imported_data
                    st.session_state.holdings_modified = True
                    st.success(f"Imported {len(imported_data)} rows")
                    st.rerun()
                else:
                    st.error(f"CSV missing required columns: {required_cols}")
            except Exception as e:
                st.error(f"Import failed: {str(e)}")
    
    # ── Name & Sector Enrichment row ─────────────────────────────────────────
    enrich_col1, enrich_col2 = st.columns([1, 3])
    with enrich_col1:
        if st.button(
            "🔄 Enrich Names & Sectors",
            use_container_width=True,
            help="Fetch missing names and GICS sectors from Yahoo Finance for holdings "
                 "with blank names or generic sector values (Stock, Mutual Fund, Unknown…).",
            key="enrich_sectors_btn",
        ):
            with st.spinner("🔍 Fetching names & sectors from Yahoo Finance…"):
                _m, _y = curr_month, curr_year
                result = enrich_holdings(month=_m, year=_y)
            if result['enriched'] == 0 and result['failed'] == 0:
                st.info("✅ All holdings already complete — nothing to update.")
            elif result['enriched'] > 0:
                st.success(
                    f"✅ Updated {result['enriched']} holding(s). "
                    f"{result['unchanged']} already complete. "
                    f"{result['failed']} symbol(s) had no data."
                )
                st.session_state.holdings_data = load_portfolio_data(_m, _y)
                st.rerun()
            else:
                st.warning(
                    f"⚠️ Enrichment complete — "
                    f"{result['failed']} symbol(s) returned no data from Yahoo Finance."
                )
    with enrich_col2:
        st.caption(
            "Fills blank names and stale sector values (Stock, Mutual Fund, Unknown, blank) "
            "using live Yahoo Finance data. Runs automatically after a brokerage sync."
        )

    st.markdown("---")

    # ========================================================================
    # MARKET INDICATORS
    # ========================================================================
    st.markdown("#### 📊 Holdings Data with Market Indicators")
    
    if st.session_state.holdings_data.empty:
        st.info("No holdings for this month. Click '➕ Add Row' or '📋 Copy Previous' to get started.")
        return
    
    # Initialize previous symbols tracking in session state
    if 'previous_symbols' not in st.session_state:
        # On first load, initialize with current symbols to avoid treating everything as "changed"
        st.session_state.previous_symbols = {
            idx: row['symbol'] for idx, row in st.session_state.holdings_data.iterrows()
        }
    
    # Calculate market indicators for all unique symbols
    with st.spinner("📈 Calculating market indicators..."):
        unique_symbols = st.session_state.holdings_data['symbol'].unique().tolist()
        indicators = get_portfolio_indicators(unique_symbols)
    
    # Identify which symbols actually changed (user edited the symbol column)
    changed_symbols = set()
    for idx, row in st.session_state.holdings_data.iterrows():
        prev_symbol = st.session_state.previous_symbols.get(idx, '')
        curr_symbol = str(row['symbol']) if 'symbol' in row else ''
        if prev_symbol and prev_symbol != curr_symbol:
            changed_symbols.add(idx)
    
    # Fetch name + sector for symbols that changed or have empty fields
    enrichment_cache: dict[str, tuple[str, str]] = {}  # symbol → (name, sector)
    if changed_symbols:
        with st.spinner("🔍 Fetching name & sector for updated symbols…"):
            from portfolio_db import _fetch_name_and_sector
            for idx in changed_symbols:
                symbol = str(st.session_state.holdings_data.loc[idx, 'symbol']).strip()
                if symbol:
                    enrichment_cache[symbol] = _fetch_name_and_sector(symbol)
    
    # Add market indicator column and conditionally update sectors in display data
    display_data = st.session_state.holdings_data.copy().reset_index(drop=True)
    
    def get_indicator_display(symbol: str) -> str:
        """Get display string for market indicator."""
        ind = indicators.get(symbol)
        if ind is not None:
            return ind.emoji + " " + ind.condition.value.replace('_', ' ').title()
        return "❓ Unknown"
    
    def _get_enrichment(row, row_idx: int) -> tuple[str, str]:
        """
        Return (name, sector) to display.
        Auto-fills from yfinance ONLY when the user just changed the symbol in
        that row.  Existing non-stale values are always preserved.
        """
        from portfolio_db import _STALE_SECTORS
        symbol         = str(row['symbol']).strip()
        current_name   = str(row.get('name',   '')).strip()
        current_sector = str(row.get('sector', '')).strip()

        # Numeric symbols → cash balance row, special-case sector
        if symbol and symbol[0].isdigit():
            return current_name, 'MF:Cash'

        # If symbol changed, apply fetched values where current is blank/stale
        if row_idx in changed_symbols and symbol in enrichment_cache:
            fetched_name, fetched_sector = enrichment_cache[symbol]
            out_name   = fetched_name   if (fetched_name   and not current_name)   else current_name
            out_sector = fetched_sector if (fetched_sector and current_sector in _STALE_SECTORS) else current_sector
            return out_name, out_sector

        # Preserve whatever is already stored
        out_sector = current_sector if current_sector and current_sector != 'nan' else ''
        return current_name, out_sector

    # Apply to display_data in one pass
    _enriched = display_data.apply(lambda row: _get_enrichment(row, row.name), axis=1)
    display_data['name']   = [v[0] for v in _enriched]
    display_data['sector'] = [v[1] for v in _enriched]
    display_data['Market Indicator'] = display_data['symbol'].apply(get_indicator_display)
    
    # Update previous symbols tracking for next render
    st.session_state.previous_symbols = {idx: row['symbol'] for idx, row in display_data.iterrows()}
    
    # Configure column types for data editor
    column_config = {
        'month': st.column_config.NumberColumn(
            'Month',
            help='Month (1-12)',
            min_value=1,
            max_value=12,
            step=1,
            format='%d',
        ),
        'year': st.column_config.NumberColumn(
            'Year',
            help='Year',
            min_value=2000,
            max_value=2100,
            step=1,
            format='%d',
        ),
        'account_name': st.column_config.TextColumn(
            'Account',
            help='Account name (e.g., Schwab, Vanguard)',
            max_chars=50,
        ),
        'account_type': st.column_config.SelectboxColumn(
            'Type',
            help='Account type',
            options=VALID_ACCOUNT_TYPES,
        ),
        'owner': st.column_config.SelectboxColumn(
            'Owner',
            help='Account owner',
            options=get_valid_account_owners(),
        ),
        'symbol': st.column_config.TextColumn(
            'Symbol',
            help='Ticker symbol (e.g., AAPL, GOOGL, MF:CASH)',
            max_chars=20,
        ),
        'name': st.column_config.TextColumn(
            'Name',
            help='Security name',
            max_chars=100,
        ),
        'sector': st.column_config.TextColumn(
            'Sector',
            help=(
                'Asset sector or fund category. '
                'Stocks: Technology, Healthcare, Financial Services… '
                'Funds: MF:US, MF:Bond, MF:Global, MF:Large-Cap, MF:Reit, MF:Cash… '
                'Other: Options:Call, Options:Put, MF:OTHER.'
            ),
            max_chars=60,
        ),
        'qty': st.column_config.NumberColumn(
            'Quantity',
            help='Number of shares/units (negative for short options positions)',
            format='%.4f',
        ),
        'purchase_price': st.column_config.NumberColumn(
            'Purchase Price',
            help='Price per share at purchase',
            min_value=0.0,
            format='$%.2f',
        ),
        'purchase_date': st.column_config.DateColumn(
            'Purchase Date',
            help='Date of purchase',
            format='YYYY-MM-DD',
        ),
        'Market Indicator': st.column_config.TextColumn(
            'Market Indicator',
            help='Market condition based on 10-week and 50-week moving averages',
            disabled=True,  # Read-only column
        ),
    }
    
    # Calculate dynamic height based on dataset size
    # Base height for header + controls, plus ~35px per row
    # Min height: 300px, Max height: 800px for usability
    num_rows = len(display_data)
    row_height = 35  # Approximate height per row in pixels
    header_height = 100  # Height for header and controls
    calculated_height = header_height + (num_rows * row_height)
    dynamic_height = max(300, min(calculated_height, 800))
    
    # Display editable dataframe with market indicators
    edited_data = st.data_editor(
        display_data,
        column_config=column_config,
        num_rows="dynamic",  # Allow adding/deleting rows
        use_container_width=True,
        height=dynamic_height,
        hide_index=True,
        key="holdings_editor",
    )
    
    # Remove the Market Indicator column before saving (it's calculated, not stored)
    if 'Market Indicator' in edited_data.columns:
        edited_data = edited_data.drop(columns=['Market Indicator'])
    
    # Track if data was modified
    if not edited_data.equals(st.session_state.holdings_data):
        st.session_state.holdings_data = edited_data
        st.session_state.holdings_modified = True
    
    # ========================================================================
    # VALIDATION & SAVE
    # ========================================================================
    st.markdown("---")
    st.markdown("#### 💾 Save Changes")
    
    col_save1, col_save2, col_save3 = st.columns([2, 1, 1])
    
    with col_save1:
        if st.session_state.holdings_modified:
            st.warning(f"⚠️ You have unsaved changes ({len(st.session_state.holdings_data)} rows)")
        else:
            st.info("✅ No unsaved changes")
    
    with col_save2:
        validate_button = st.button("🔍 Validate", use_container_width=True, help="Check for errors before saving")
    
    with col_save3:
        save_button = st.button("💾 Save to File", use_container_width=True, type="primary", help="Save changes to portfolio_data_truth.csv")
    
    # Validation
    if validate_button:
        st.markdown("#### 🔍 Validation Results")
        
        errors = []
        warnings = []
        
        for idx, row in st.session_state.holdings_data.iterrows():
            row_num = int(idx) + 1 if isinstance(idx, (int, float)) else idx  # type: ignore[arg-type]
            # Validate entry
            is_valid, error_msg = validate_portfolio_entry(row)
            
            if not is_valid:
                errors.append(f"Row {row_num}: {error_msg}")
            
            # Check ticker symbol if not cash
            symbol = str(row['symbol']).strip().upper()
            if symbol and symbol not in ['MF:CASH', 'CASH']:
                is_valid_ticker, name, sector, ticker_error = validate_ticker_symbol(symbol)
                if not is_valid_ticker:
                    warnings.append(f"Row {row_num}: {ticker_error}")
                elif not str(row['name']).strip() or not str(row['sector']).strip():
                    warnings.append(f"Row {row_num}: Symbol '{symbol}' found but name/sector not filled. Suggested: {name} / {sector}")
        
        if errors:
            st.error(f"❌ Found {len(errors)} error(s):")
            for error in errors:
                st.markdown(f"- {error}")
        
        if warnings:
            st.warning(f"⚠️ Found {len(warnings)} warning(s):")
            for warning in warnings:
                st.markdown(f"- {warning}")
        
        if not errors and not warnings:
            st.success("✅ All validations passed! Ready to save.")
    
    # Save
    if save_button:
        st.markdown("#### 💾 Saving...")
        
        # Validate before saving
        errors = []
        for idx, row in st.session_state.holdings_data.iterrows():
            row_num = int(idx) + 1 if isinstance(idx, (int, float)) else idx  # type: ignore[arg-type]
            is_valid, error_msg = validate_portfolio_entry(row)
            if not is_valid:
                errors.append(f"Row {row_num}: {error_msg}")
        
        if errors:
            st.error(f"❌ Cannot save - found {len(errors)} error(s):")
            for error in errors[:5]:  # Show first 5 errors
                st.markdown(f"- {error}")
            if len(errors) > 5:
                st.markdown(f"... and {len(errors) - 5} more errors")
            st.info("💡 Click '🔍 Validate' to see all errors")
        else:
            # Save to file
            success, message = save_portfolio_data(st.session_state.holdings_data, append=True)
            
            if success:
                st.success(f"✅ {message}")
                st.session_state.holdings_modified = False
                
                # Offer to reload portfolio
                st.info("💡 Portfolio data saved. Refresh the page or switch tabs to see updated values.")
            else:
                st.error(f"❌ Save failed: {message}")
    
    # ========================================================================
    # HELPER TOOLS
    # ========================================================================
    st.markdown("---")
    st.markdown("#### 🛠️ Helper Tools")
    
    with st.expander("🔍 Lookup Ticker Symbol", expanded=False):
        st.caption("Validate a ticker symbol and get its name and sector")
        
        lookup_symbol = st.text_input("Enter ticker symbol:", key="lookup_symbol", placeholder="e.g., AAPL, GOOGL")
        
        if st.button("🔍 Lookup", key="lookup_button"):
            if lookup_symbol:
                is_valid, name, sector, error = validate_ticker_symbol(lookup_symbol.strip().upper())
                
                if is_valid:
                    st.success(f"✅ **{lookup_symbol.upper()}** found!")
                    st.markdown(f"**Name:** {name}")
                    st.markdown(f"**Sector:** {sector}")
                    
                    # Get current price
                    current_price = get_current_price(lookup_symbol.strip().upper())
                    if current_price > 0:
                        st.markdown(f"**Current Price:** ${current_price:.2f}")
                else:
                    st.error(f"❌ {error}")
            else:
                st.warning("Please enter a ticker symbol")
    
    with st.expander("📥 Download Current Data", expanded=False):
        st.caption("Export current holdings to CSV")
        
        if not st.session_state.holdings_data.empty:
            csv = st.session_state.holdings_data.to_csv(index=False)
            st.download_button(
                label="📥 Download CSV",
                data=csv,
                file_name=f"portfolio_holdings_{curr_month}_{curr_year}.csv",
                mime="text/csv",
                use_container_width=True,
            )
        else:
            st.info("No data to export")
    
    with st.expander("📊 Data Summary", expanded=False):
        if not st.session_state.holdings_data.empty:
            st.markdown(f"**Total Holdings:** {len(st.session_state.holdings_data)}")
            st.markdown(f"**Accounts:** {st.session_state.holdings_data['account_name'].nunique()}")
            st.markdown(f"**Unique Symbols:** {st.session_state.holdings_data['symbol'].nunique()}")
            
            # Group by account type
            by_type = st.session_state.holdings_data.groupby('account_type').size()
            st.markdown("**By Account Type:**")
            for acc_type, count in by_type.items():
                st.markdown(f"- {acc_type}: {count} holdings")
            
            # Market indicator summary
            st.markdown("---")
            st.markdown("**Market Indicators:**")
            indicator_counts = {}
            for symbol in st.session_state.holdings_data['symbol'].unique():
                ind = indicators.get(symbol)
                if ind is not None:
                    condition = ind.condition.value
                    indicator_counts[condition] = indicator_counts.get(condition, 0) + 1
            
            for condition, count in sorted(indicator_counts.items()):
                emoji_map = {
                    'strong_buy': '🚀',
                    'buy': '📈',
                    'hold': '➖',
                    'caution': '⚠️',
                    'sell': '📉',
                    'unknown': '❓'
                }
                emoji = emoji_map.get(condition, '❓')
                st.markdown(f"- {emoji} {condition.replace('_', ' ').title()}: {count} securities")
        else:
            st.info("No data to summarize")
    
    with st.expander("📈 Market Indicator Details", expanded=False):
        st.caption("Detailed market analysis for each security")
        
        if not st.session_state.holdings_data.empty:
            for symbol in st.session_state.holdings_data['symbol'].unique():
                ind = indicators.get(symbol)
                if ind is not None:
                    with st.container():
                        col1, col2 = st.columns([1, 3])
                        with col1:
                            st.markdown(f"### {ind.emoji} **{symbol}**")
                        with col2:
                            st.markdown(f"**{ind.recommendation}**")
                            st.caption(
                                f"Price: ${ind.current_price:.2f} | "
                                f"10-Week MA: ${ind.short_ma:.2f} ({ind.short_trend}) | "
                                f"50-Week MA: ${ind.long_ma:.2f} ({ind.long_trend}) | "
                                f"Confidence: {ind.confidence:.0%}"
                            )
                        st.markdown("---")
        else:
            st.info("No holdings to analyze")

# Made with Bob
