"""
Portfolio Factor Analysis Component
====================================
UI component for displaying factor-based portfolio analysis.

Provides institutional-grade factor analysis across four key investment factors:
- Value: Low P/E, P/B ratios (undervalued stocks)
- Growth: High earnings/revenue growth
- Momentum: Recent price trends and relative strength
- Quality: High ROE, low debt, stable earnings

Author: Bob
Date: 2026-03-17
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from typing import Dict, Optional
import logging

logger = logging.getLogger(__name__)

# Import factor analysis module
try:
    from portfolio_factors import (
        fetch_factor_data,
        calculate_portfolio_factor_exposure,
        FactorMetrics,
        PortfolioFactorExposure,
        DataQuality,
        PortfolioStyle,
    )
    FACTOR_ANALYSIS_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Factor analysis module not available: {e}")
    FACTOR_ANALYSIS_AVAILABLE = False


def render_factor_analysis_tab(portdf: pd.DataFrame, curr_month: int, curr_year: int):
    """
    Render the Factor Analysis tab.
    
    Args:
        portdf: Portfolio DataFrame with holdings
        curr_month: Current month
        curr_year: Current year
    """
    if not FACTOR_ANALYSIS_AVAILABLE:
        st.error("❌ Factor analysis module not available. Please check installation.")
        return
    
    if portdf.empty:
        st.warning("📊 No portfolio data available. Please add holdings to analyze factors.")
        return
    
    st.markdown("### 🎯 Factor-Based Portfolio Analysis")
    st.caption("Institutional-grade analysis of your portfolio's factor exposures")
    
    # Map column names to standard format
    # Portfolio display uses 'Ticker' and 'Current value'
    
    # Check if required columns exist (with either name)
    has_ticker = 'Ticker' in portdf.columns or 'symbol' in portdf.columns
    has_value = 'Current value' in portdf.columns or 'market_value' in portdf.columns
    
    if not has_ticker or not has_value:
        st.error(f"Portfolio data missing required columns. Found: {portdf.columns.tolist()}")
        return
    
    # Create working DataFrame with standard column names
    stocks_df: pd.DataFrame = portdf.copy()
    
    # Rename columns to standard format
    if 'Ticker' in stocks_df.columns:
        stocks_df['symbol'] = stocks_df['Ticker']
    if 'Current value' in stocks_df.columns:
        stocks_df['market_value'] = stocks_df['Current value']
    
    # Filter to stocks only (exclude cash)
    stocks_df = stocks_df[stocks_df['symbol'].notna()].copy()
    stocks_df = stocks_df[stocks_df['symbol'] != 'Cash'].copy()
    
    if stocks_df.empty:
        st.info("No stock holdings found in portfolio.")
        return
    
    # Fetch factor data with progress bar
    with st.spinner("🔍 Analyzing factor exposures..."):
        factor_data = _fetch_factor_data_for_portfolio(stocks_df)
    
    if not factor_data:
        st.error("Unable to fetch factor data. Please try again later.")
        return
    
    # Calculate portfolio exposure
    exposure = calculate_portfolio_factor_exposure(stocks_df, factor_data)
    
    if exposure.analyzed_holdings == 0:
        st.warning("No factor data available for portfolio holdings.")
        return
    
    # Display results in sections
    _render_summary_cards(exposure)
    
    st.markdown("---")
    
    col1, col2 = st.columns(2)
    
    with col1:
        _render_factor_radar_chart(exposure)
        _render_factor_tilts(exposure)
    
    with col2:
        _render_style_classification(exposure)
        _render_factor_balance(exposure)
    
    st.markdown("---")
    
    _render_top_holdings_by_factor(exposure)
    
    st.markdown("---")
    
    _render_holdings_detail_table(stocks_df, factor_data, curr_month, curr_year)


def _fetch_factor_data_for_portfolio(portdf: pd.DataFrame) -> Dict[str, FactorMetrics]:
    """Fetch factor data for all holdings in portfolio."""
    factor_data = {}
    symbols = portdf['symbol'].unique()
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    for i, symbol in enumerate(symbols):
        status_text.text(f"Fetching data for {symbol}... ({i+1}/{len(symbols)})")
        try:
            metrics = fetch_factor_data(symbol, use_cache=True)
            factor_data[symbol] = metrics
        except Exception as e:
            logger.error(f"Error fetching factor data for {symbol}: {e}")
        
        progress_bar.progress((i + 1) / len(symbols))
    
    progress_bar.empty()
    status_text.empty()
    
    return factor_data


def _render_summary_cards(exposure: PortfolioFactorExposure):
    """Render summary metric cards."""
    col1, col2, col3, col4, col5 = st.columns(5)
    
    with col1:
        st.metric(
            label="📊 Holdings Analyzed",
            value=f"{exposure.analyzed_holdings}/{exposure.total_holdings}",
            delta=f"{exposure.coverage_pct:.0f}% coverage"
        )
    
    with col2:
        st.metric(
            label="🎨 Primary Style",
            value=exposure.primary_style.value,
            delta=f"{exposure.style_purity:.0f}% purity"
        )
    
    with col3:
        dominant = exposure.get_dominant_factors(threshold=60.0)
        st.metric(
            label="⭐ Dominant Factors",
            value=len(dominant),
            delta=", ".join(dominant) if dominant else "Balanced"
        )
    
    with col4:
        st.metric(
            label="📈 Factor Concentration",
            value=f"{exposure.factor_concentration:.0f}%",
            delta="Lower is better",
            delta_color="inverse"
        )
    
    with col5:
        avg_exposure = (
            exposure.value_exposure + exposure.growth_exposure +
            exposure.momentum_exposure + exposure.quality_exposure
        ) / 4
        st.metric(
            label="🎯 Avg Factor Score",
            value=f"{avg_exposure:.0f}",
            delta="vs 50 benchmark"
        )


def _render_factor_radar_chart(exposure: PortfolioFactorExposure):
    """Render radar chart of factor exposures."""
    st.markdown("#### Factor Exposure Radar")
    
    categories = ['Value', 'Growth', 'Momentum', 'Quality']
    portfolio_values = [
        exposure.value_exposure,
        exposure.growth_exposure,
        exposure.momentum_exposure,
        exposure.quality_exposure,
    ]
    benchmark_values = [50, 50, 50, 50]
    
    fig = go.Figure()
    
    # Portfolio trace
    fig.add_trace(go.Scatterpolar(
        r=portfolio_values + [portfolio_values[0]],
        theta=categories + [categories[0]],
        fill='toself',
        name='Portfolio',
        line_color='rgb(0, 123, 255)',
        fillcolor='rgba(0, 123, 255, 0.3)',
    ))
    
    # Benchmark trace
    fig.add_trace(go.Scatterpolar(
        r=benchmark_values + [benchmark_values[0]],
        theta=categories + [categories[0]],
        fill='toself',
        name='Benchmark (S&P 500)',
        line_color='rgb(108, 117, 125)',
        fillcolor='rgba(108, 117, 125, 0.1)',
        line_dash='dash',
    ))
    
    fig.update_layout(
        polar=dict(
            radialaxis=dict(
                visible=True,
                range=[0, 100],
                tickvals=[0, 25, 50, 75, 100],
            )
        ),
        showlegend=True,
        height=400,
        margin=dict(l=80, r=80, t=40, b=40),
    )
    
    st.plotly_chart(fig, use_container_width=True)


def _render_factor_tilts(exposure: PortfolioFactorExposure):
    """Render factor tilts vs benchmark."""
    st.markdown("#### Factor Tilts vs Benchmark")
    st.caption("Positive = Overweight, Negative = Underweight")
    
    tilts_df = pd.DataFrame({
        'Factor': ['Value', 'Growth', 'Momentum', 'Quality'],
        'Tilt': [
            exposure.value_tilt,
            exposure.growth_tilt,
            exposure.momentum_tilt,
            exposure.quality_tilt,
        ]
    })
    
    # Color code based on tilt direction
    colors = ['green' if t > 0 else 'red' for t in tilts_df['Tilt']]
    
    fig = go.Figure(data=[
        go.Bar(
            x=tilts_df['Factor'],
            y=tilts_df['Tilt'],
            marker_color=colors,
            text=[f"{t:+.1f}" for t in tilts_df['Tilt']],
            textposition='outside',
        )
    ])
    
    fig.update_layout(
        yaxis_title="Tilt",
        height=300,
        margin=dict(l=40, r=40, t=20, b=40),
        showlegend=False,
    )
    
    fig.add_hline(y=0, line_dash="dash", line_color="gray")
    
    st.plotly_chart(fig, use_container_width=True)


def _render_style_classification(exposure: PortfolioFactorExposure):
    """Render style classification."""
    st.markdown("#### Style Classification")
    
    # Style box visualization
    style_emoji = {
        PortfolioStyle.VALUE: "💰",
        PortfolioStyle.GROWTH: "🚀",
        PortfolioStyle.BLEND: "⚖️",
        PortfolioStyle.QUALITY: "⭐",
        PortfolioStyle.MOMENTUM: "📈",
        PortfolioStyle.BALANCED: "🎯",
    }
    
    st.markdown(f"### {style_emoji.get(exposure.primary_style, '📊')} {exposure.primary_style.value}")
    
    if exposure.secondary_style:
        st.caption(f"Secondary: {style_emoji.get(exposure.secondary_style, '📊')} {exposure.secondary_style.value}")
    
    st.metric(
        label="Style Purity",
        value=f"{exposure.style_purity:.1f}%",
        help="How strongly the portfolio exhibits this style (higher = more pure)"
    )
    
    # Style description
    style_descriptions = {
        PortfolioStyle.VALUE: "Focus on undervalued stocks with low P/E and P/B ratios",
        PortfolioStyle.GROWTH: "Emphasis on companies with high earnings and revenue growth",
        PortfolioStyle.BLEND: "Balanced mix of value and growth characteristics",
        PortfolioStyle.QUALITY: "High-quality companies with strong fundamentals",
        PortfolioStyle.MOMENTUM: "Stocks with strong recent price performance",
        PortfolioStyle.BALANCED: "Well-diversified across all factor exposures",
    }
    
    st.info(style_descriptions.get(exposure.primary_style, "Mixed factor exposures"))


def _render_factor_balance(exposure: PortfolioFactorExposure):
    """Render factor balance pie chart."""
    st.markdown("#### Factor Balance")
    
    balance = exposure.get_factor_balance()
    
    fig = go.Figure(data=[go.Pie(
        labels=list(balance.keys()),
        values=list(balance.values()),
        hole=0.4,
        marker_colors=['#007bff', '#28a745', '#ffc107', '#dc3545'],
    )])
    
    fig.update_layout(
        height=300,
        margin=dict(l=20, r=20, t=20, b=20),
        showlegend=True,
    )
    
    st.plotly_chart(fig, use_container_width=True)


def _render_top_holdings_by_factor(exposure: PortfolioFactorExposure):
    """Render top holdings for each factor."""
    st.markdown("#### Top Holdings by Factor")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.markdown("**💰 Value**")
        for symbol, weight, score in exposure.value_holdings[:5]:
            st.markdown(f"- **{symbol}**: {score:.0f} ({weight*100:.1f}%)")
    
    with col2:
        st.markdown("**🚀 Growth**")
        for symbol, weight, score in exposure.growth_holdings[:5]:
            st.markdown(f"- **{symbol}**: {score:.0f} ({weight*100:.1f}%)")
    
    with col3:
        st.markdown("**📈 Momentum**")
        for symbol, weight, score in exposure.momentum_holdings[:5]:
            st.markdown(f"- **{symbol}**: {score:.0f} ({weight*100:.1f}%)")
    
    with col4:
        st.markdown("**⭐ Quality**")
        for symbol, weight, score in exposure.quality_holdings[:5]:
            st.markdown(f"- **{symbol}**: {score:.0f} ({weight*100:.1f}%)")


def _render_holdings_detail_table(portdf: pd.DataFrame, factor_data: Dict[str, FactorMetrics], curr_month: int, curr_year: int):
    """Render detailed holdings table with factor scores."""
    st.markdown("#### Holdings Detail")
    
    # Build detail table
    details = []
    for _, row in portdf.iterrows():
        symbol = row['symbol']
        if symbol not in factor_data:
            continue
        
        metrics = factor_data[symbol]
        details.append({
            'Symbol': symbol,
            'Value': portdf[portdf['symbol'] == symbol]['market_value'].iloc[0],
            'Weight %': (row['market_value'] / portdf['market_value'].sum()) * 100,
            'Value Score': metrics.value_score,
            'Growth Score': metrics.growth_score,
            'Momentum Score': metrics.momentum_score,
            'Quality Score': metrics.quality_score,
            'Overall': metrics.get_overall_score(),
            'Data Quality': metrics.data_quality.value,
        })
    
    if details:
        detail_df = pd.DataFrame(details)
        detail_df = detail_df.sort_values('Weight %', ascending=False)
        
        # Format columns
        detail_df['Value'] = detail_df['Value'].apply(lambda x: f"${x:,.0f}")
        detail_df['Weight %'] = detail_df['Weight %'].apply(lambda x: f"{x:.1f}%")
        
        # Color code scores
        st.dataframe(
            detail_df,
            use_container_width=True,
            hide_index=True,
            column_config={
                'Value Score': st.column_config.ProgressColumn(
                    'Value',
                    format="%.0f",
                    min_value=0,
                    max_value=100,
                ),
                'Growth Score': st.column_config.ProgressColumn(
                    'Growth',
                    format="%.0f",
                    min_value=0,
                    max_value=100,
                ),
                'Momentum Score': st.column_config.ProgressColumn(
                    'Momentum',
                    format="%.0f",
                    min_value=0,
                    max_value=100,
                ),
                'Quality Score': st.column_config.ProgressColumn(
                    'Quality',
                    format="%.0f",
                    min_value=0,
                    max_value=100,
                ),
                'Overall': st.column_config.ProgressColumn(
                    'Overall',
                    format="%.0f",
                    min_value=0,
                    max_value=100,
                ),
            }
        )
        
        # Download button
        csv = detail_df.to_csv(index=False)
        st.download_button(
            label="📥 Download Factor Analysis",
            data=csv,
            file_name=f"factor_analysis_{curr_year}_{curr_month:02d}.csv",
            mime="text/csv",
        )
    else:
        st.info("No factor data available for holdings.")


# Made with Bob