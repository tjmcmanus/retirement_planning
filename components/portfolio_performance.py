"""
components/portfolio_performance.py
====================================
Portfolio Performance & Analytics Component - Professional-grade performance metrics and visualizations.

Features:
- Performance summary cards (TWR, MWR, Sharpe, Sortino, Max Drawdown, Alpha, Beta)
- Time period selector (1Y, 3Y, 5Y, All)
- Benchmark selector (S&P 500, custom ticker)
- Performance chart with drawdown shading
- Attribution analysis (contributions vs growth)
- Risk-return scatter plot
- Drawdown recovery timeline
- PDF export functionality
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Optional
from datetime import datetime, timedelta
import io

import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
import streamlit as st

if TYPE_CHECKING:
    from pandas import DataFrame

try:
    from portfolio_analytics import calculate_portfolio_analytics  # type: ignore[import]
    ANALYTICS_AVAILABLE = True
except ImportError:
    ANALYTICS_AVAILABLE = False
    calculate_portfolio_analytics = None  # type: ignore[assignment]


def render_performance_tab(
    portdf: DataFrame,
    networth: DataFrame,
    curr_month: int,
    curr_year: int,
) -> None:
    """
    Render the Performance & Analytics tab.
    
    Args:
        portdf: Current portfolio display DataFrame
        networth: Net worth history DataFrame
        curr_month: Current month (1-12)
        curr_year: Current year
    """
    st.markdown("### 📈 Portfolio Performance & Analytics")
    st.caption("Professional-grade performance metrics and risk-adjusted returns")
    
    if not ANALYTICS_AVAILABLE:
        st.error("❌ Analytics module not available. Please ensure portfolio_analytics.py is installed.")
        return
    
    if networth.empty or len(networth) < 2:
        st.warning("⚠️ Performance analytics require at least 2 months of historical data.")
        st.info("💡 Continue tracking your portfolio to unlock performance analytics.")
        return
    
    # ========================================================================
    # TIME PERIOD & BENCHMARK SELECTORS
    # ========================================================================
    st.markdown("#### ⚙️ Analysis Settings")
    
    col_period, col_benchmark, col_export = st.columns([2, 2, 1])
    
    with col_period:
        # Calculate available periods
        data_months = len(networth)
        period_options = ['All Time']
        
        if data_months >= 12:
            period_options.insert(0, '1 Year')
        if data_months >= 36:
            period_options.insert(0, '3 Years')
        if data_months >= 60:
            period_options.insert(0, '5 Years')
        
        selected_period = st.selectbox(
            "📅 Time Period",
            options=period_options,
            index=0,
            help="Select time period for analysis"
        )
        
        # Ensure networth index is DatetimeIndex
        if not isinstance(networth.index, pd.DatetimeIndex):
            networth.index = pd.to_datetime(networth.index)
        
        # Calculate start date based on selection
        if selected_period == '1 Year':
            start_date = networth.index[-1] - pd.DateOffset(months=12)
        elif selected_period == '3 Years':
            start_date = networth.index[-1] - pd.DateOffset(months=36)
        elif selected_period == '5 Years':
            start_date = networth.index[-1] - pd.DateOffset(months=60)
        else:  # All Time
            start_date = networth.index[0]
        
        # Filter data
        analysis_data = networth[networth.index >= start_date].copy()
    
    with col_benchmark:
        benchmark_options = [
            'S&P 500 (^GSPC)',
            'Nasdaq (^IXIC)',
            'Dow Jones (^DJI)',
            'Russell 2000 (^RUT)',
            'Total Stock Market (VTI)',
            'Custom Ticker'
        ]
        
        selected_benchmark = st.selectbox(
            "📊 Benchmark",
            options=benchmark_options,
            index=0,
            help="Select benchmark for comparison"
        )
        
        # Extract ticker symbol
        if selected_benchmark == 'Custom Ticker':
            benchmark_ticker = st.text_input(
                "Enter ticker symbol:",
                value="SPY",
                help="Enter any valid ticker symbol"
            )
        else:
            benchmark_ticker = selected_benchmark.split('(')[1].rstrip(')')
    
    with col_export:
        st.markdown("&nbsp;")  # Spacing
        export_pdf = st.button(
            "📄 Export PDF",
            use_container_width=True,
            help="Export performance report as PDF"
        )
    
    st.markdown("---")
    
    # ========================================================================
    # CALCULATE ANALYTICS
    # ========================================================================
    
    # Validate data before processing
    if analysis_data.empty:
        st.warning("⚠️ No data available for the selected time period.")
        return
    
    if 'total' not in analysis_data.columns:
        st.error("❌ Portfolio data is missing the 'total' column. Please check your data configuration.")
        st.info(f"Available columns: {', '.join(analysis_data.columns.tolist())}")
        return
    
    with st.spinner("📊 Calculating performance metrics..."):
        try:
            # Convert to pandas Series with datetime index
            portfolio_series = pd.Series(
                analysis_data['total'].values,  # type: ignore[union-attr]
                index=analysis_data.index
            )
            
            analytics_result = calculate_portfolio_analytics(  # type: ignore[misc]
                portfolio_values=portfolio_series,
                contributions=None,  # TODO: Add contribution tracking
                withdrawals=None,
                benchmark_symbol=benchmark_ticker,
                risk_free_rate=0.04,
            )
            
            # Convert PerformanceMetrics to dict for easier access
            # Handle None values from analytics_result
            alpha_val = getattr(analytics_result, 'alpha', None)
            beta_val = getattr(analytics_result, 'beta', None)
            
            analytics = {
                'time_weighted_return': analytics_result.time_weighted_return or 0.0,
                'money_weighted_return': analytics_result.money_weighted_return or 0.0,
                'sharpe_ratio': analytics_result.sharpe_ratio or 0.0,
                'sortino_ratio': analytics_result.sortino_ratio or 0.0,
                'max_drawdown': (analytics_result.max_drawdown_pct or 0.0) / 100,
                'volatility': analytics_result.volatility or 0.0,
                'alpha': alpha_val if alpha_val is not None else 0.0,
                'beta': beta_val if beta_val is not None else 1.0,
                'benchmark_returns': getattr(analytics_result, 'benchmark_returns', []),
                'drawdown_info': {
                    'max_drawdown': (analytics_result.max_drawdown_pct or 0.0) / 100,
                    'max_drawdown_start': analytics_result.max_drawdown_start,
                    'max_drawdown_end': analytics_result.max_drawdown_end,
                    'current_drawdown': (analytics_result.current_drawdown_pct or 0.0) / 100,
                    'recovery_months': analytics_result.recovery_days // 30 if analytics_result.recovery_days else 0,
                },
                'drawdowns': [],  # TODO: Add drawdown series
            }
        except Exception as e:
            st.error(f"❌ Error calculating analytics: {str(e)}")
            st.info("💡 This may be due to insufficient data or invalid benchmark ticker.")
            import traceback
            st.code(traceback.format_exc())
            return
    
    # ========================================================================
    # PERFORMANCE SUMMARY CARDS
    # ========================================================================
    st.markdown("#### 📊 Performance Summary")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        twr = analytics.get('time_weighted_return', 0.0) * 100
        twr_color = "normal" if twr >= 0 else "inverse"
        st.metric(
            "Time-Weighted Return",
            f"{twr:+.2f}%",
            help="Pure investment performance, eliminates cash flow effects"
        )
    
    with col2:
        mwr = analytics.get('money_weighted_return', 0.0) * 100
        mwr_color = "normal" if mwr >= 0 else "inverse"
        st.metric(
            "Money-Weighted Return",
            f"{mwr:+.2f}%",
            help="Accounts for timing of contributions/withdrawals (IRR)"
        )
    
    with col3:
        sharpe = analytics.get('sharpe_ratio', 0.0)
        sharpe_label = "🟢 Excellent" if sharpe > 1.5 else ("🟡 Good" if sharpe > 1.0 else ("🟠 Fair" if sharpe > 0.5 else "🔴 Poor"))
        st.metric(
            "Sharpe Ratio",
            f"{sharpe:.2f}",
            sharpe_label,
            help="Risk-adjusted return. >1.0 is good, >2.0 is excellent"
        )
    
    with col4:
        sortino = analytics.get('sortino_ratio', 0.0)
        sortino_label = "🟢 Excellent" if sortino > 2.0 else ("🟡 Good" if sortino > 1.5 else ("🟠 Fair" if sortino > 1.0 else "🔴 Poor"))
        st.metric(
            "Sortino Ratio",
            f"{sortino:.2f}",
            sortino_label,
            help="Downside risk-adjusted return. Higher is better"
        )
    
    # Second row of metrics
    col5, col6, col7, col8 = st.columns(4)
    
    with col5:
        max_dd = analytics.get('max_drawdown', 0.0) * 100
        st.metric(
            "Maximum Drawdown",
            f"{max_dd:.2f}%",
            help="Largest peak-to-trough decline"
        )
    
    with col6:
        volatility = analytics.get('volatility', 0.0) * 100
        st.metric(
            "Volatility (Annual)",
            f"{volatility:.2f}%",
            help="Standard deviation of returns (annualized)"
        )
    
    with col7:
        alpha = analytics.get('alpha', 0.0) * 100
        alpha_color = "normal" if alpha >= 0 else "inverse"
        st.metric(
            "Alpha",
            f"{alpha:+.2f}%",
            help="Excess return vs benchmark (annualized)"
        )
    
    with col8:
        beta = analytics.get('beta', 1.0)
        beta_label = "🔵 Defensive" if beta < 0.8 else ("🟢 Neutral" if beta < 1.2 else "🔴 Aggressive")
        st.metric(
            "Beta",
            f"{beta:.2f}",
            beta_label,
            help="Market sensitivity. 1.0 = market, <1.0 = less volatile, >1.0 = more volatile"
        )
    
    st.markdown("---")
    
    # ========================================================================
    # PERFORMANCE CHART WITH DRAWDOWN
    # ========================================================================
    st.markdown("#### 📈 Performance vs Benchmark")
    
    # Get benchmark data
    benchmark_returns = analytics.get('benchmark_returns', [])
    
    # Debug info
    if not benchmark_returns:
        st.warning(
            f"⚠️ Benchmark data not available for comparison. "
            f"This may be due to: (1) Network connectivity issues, (2) Invalid ticker symbol, "
            f"or (3) Insufficient historical data for {benchmark_ticker}. "
            f"Try selecting a different benchmark or check your internet connection."
        )
        # Show portfolio-only chart
        fig_perf = go.Figure()
        fig_perf.add_trace(go.Scatter(
            x=analysis_data.index,
            y=analysis_data['total'],
            mode='lines',
            name='Your Portfolio',
            line=dict(color='#4c78a8', width=2),
            hovertemplate='%{x|%b %Y}<br>Portfolio: $%{y:,.0f}<extra></extra>',
        ))
        fig_perf.update_layout(
            xaxis_title='Date',
            yaxis_title='Portfolio Value ($)',
            plot_bgcolor='white',
            paper_bgcolor='white',
            margin=dict(t=40, l=10, r=10, b=10),
            yaxis=dict(tickformat='$,.0f'),
            hovermode='x unified',
        )
        st.plotly_chart(fig_perf, use_container_width=True)
    elif len(benchmark_returns) != len(analysis_data):
        st.warning(
            f"⚠️ Benchmark data length mismatch. Portfolio has {len(analysis_data)} periods "
            f"but benchmark has {len(benchmark_returns)} periods. Showing portfolio only."
        )
        # Show portfolio-only chart
        fig_perf = go.Figure()
        fig_perf.add_trace(go.Scatter(
            x=analysis_data.index,
            y=analysis_data['total'],
            mode='lines',
            name='Your Portfolio',
            line=dict(color='#4c78a8', width=2),
            hovertemplate='%{x|%b %Y}<br>Portfolio: $%{y:,.0f}<extra></extra>',
        ))
        fig_perf.update_layout(
            xaxis_title='Date',
            yaxis_title='Portfolio Value ($)',
            plot_bgcolor='white',
            paper_bgcolor='white',
            margin=dict(t=40, l=10, r=10, b=10),
            yaxis=dict(tickformat='$,.0f'),
            hovermode='x unified',
        )
        st.plotly_chart(fig_perf, use_container_width=True)
    else:
        # Calculate benchmark cumulative values
        start_value = float(analysis_data['total'].iloc[0])  # type: ignore[union-attr]
        benchmark_values = [start_value]
        for ret in benchmark_returns[1:]:
            benchmark_values.append(benchmark_values[-1] * (1 + ret))
        
        # Create performance chart
        fig_perf = go.Figure()
        
        # Portfolio line
        fig_perf.add_trace(go.Scatter(
            x=analysis_data.index,
            y=analysis_data['total'],
            mode='lines',
            name='Your Portfolio',
            line=dict(color='#4c78a8', width=2),
            hovertemplate='%{x|%b %Y}<br>Portfolio: $%{y:,.0f}<extra></extra>',
        ))
        
        # Benchmark line
        fig_perf.add_trace(go.Scatter(
            x=analysis_data.index,
            y=benchmark_values,
            mode='lines',
            name=f'Benchmark ({benchmark_ticker})',
            line=dict(color='#f58518', width=2, dash='dash'),
            hovertemplate='%{x|%b %Y}<br>Benchmark: $%{y:,.0f}<extra></extra>',
        ))
        
        # Add drawdown shading
        drawdown_info = analytics.get('drawdown_info', {})
        if drawdown_info:
            max_dd_start = drawdown_info.get('max_drawdown_start')
            max_dd_end = drawdown_info.get('max_drawdown_end')
            
            if max_dd_start is not None and max_dd_end is not None:
                # Add shaded region for max drawdown period
                fig_perf.add_vrect(
                    x0=analysis_data.index[max_dd_start],
                    x1=analysis_data.index[max_dd_end],
                    fillcolor="red",
                    opacity=0.1,
                    layer="below",
                    line_width=0,
                    annotation_text="Max Drawdown Period",
                    annotation_position="top left",
                )
        
        fig_perf.update_layout(
            xaxis_title='Date',
            yaxis_title='Portfolio Value ($)',
            plot_bgcolor='white',
            paper_bgcolor='white',
            legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1),
            margin=dict(t=40, l=10, r=10, b=10),
            yaxis=dict(tickformat='$,.0f'),
            hovermode='x unified',
        )
        
        st.plotly_chart(fig_perf, use_container_width=True)
    
    st.markdown("---")
    
    # ========================================================================
    # ATTRIBUTION ANALYSIS
    # ========================================================================
    st.markdown("#### 🎯 Return Attribution")
    
    col_attr1, col_attr2 = st.columns(2)
    
    with col_attr1:
        st.markdown("##### Contributions vs Growth")
        
        # Calculate attribution
        start_value = float(analysis_data['total'].iloc[0])  # type: ignore[union-attr]
        end_value = float(analysis_data['total'].iloc[-1])  # type: ignore[union-attr]
        total_return = end_value - start_value
        
        # Estimate contributions (simplified - would need actual contribution data)
        # For now, assume contributions are the difference between expected growth and actual
        expected_growth = start_value * (twr / 100)
        estimated_contributions = total_return - expected_growth
        
        if estimated_contributions < 0:
            estimated_contributions = 0
            growth = total_return
        else:
            growth = expected_growth
        
        # Create pie chart
        fig_attr = px.pie(
            names=['Investment Growth', 'Contributions'],
            values=[max(0, growth), max(0, estimated_contributions)],
            color_discrete_sequence=['#4c78a8', '#72b7b2'],
            title='',
        )
        fig_attr.update_traces(
            textinfo='label+percent+value',
            texttemplate='%{label}<br>$%{value:,.0f}<br>(%{percent})',
            hovertemplate='%{label}<br>$%{value:,.0f}<br>%{percent}<extra></extra>',
        )
        fig_attr.update_layout(
            margin=dict(t=20, l=10, r=10, b=10),
            height=300,
        )
        st.plotly_chart(fig_attr, use_container_width=True)
        
        st.caption(
            "💡 **Note:** Contribution tracking requires transaction history. "
            "This is an estimate based on returns."
        )
    
    with col_attr2:
        st.markdown("##### Risk-Return Profile")
        
        # Create risk-return scatter
        fig_risk = go.Figure()
        
        # Portfolio point
        fig_risk.add_trace(go.Scatter(
            x=[volatility],
            y=[twr],
            mode='markers+text',
            name='Your Portfolio',
            marker=dict(size=15, color='#4c78a8'),
            text=['Portfolio'],
            textposition='top center',
            hovertemplate='Volatility: %{x:.2f}%<br>Return: %{y:.2f}%<extra></extra>',
        ))
        
        # Benchmark point (if available)
        if benchmark_returns:
            bench_vol = np.std(benchmark_returns) * np.sqrt(12) * 100  # Annualized
            bench_ret = (np.prod([1 + r for r in benchmark_returns]) - 1) * 100
            
            fig_risk.add_trace(go.Scatter(
                x=[bench_vol],
                y=[bench_ret],
                mode='markers+text',
                name='Benchmark',
                marker=dict(size=15, color='#f58518', symbol='diamond'),
                text=['Benchmark'],
                textposition='top center',
                hovertemplate='Volatility: %{x:.2f}%<br>Return: %{y:.2f}%<extra></extra>',
            ))
        
        # Add quadrant lines
        fig_risk.add_hline(y=0, line_dash="dash", line_color="gray", opacity=0.5)
        fig_risk.add_vline(x=volatility, line_dash="dash", line_color="gray", opacity=0.5)
        
        fig_risk.update_layout(
            xaxis_title='Risk (Volatility %)',
            yaxis_title='Return (%)',
            plot_bgcolor='white',
            paper_bgcolor='white',
            showlegend=False,
            margin=dict(t=20, l=10, r=10, b=10),
            height=300,
        )
        
        st.plotly_chart(fig_risk, use_container_width=True)
        
        # Interpretation
        if twr > 0 and volatility < 15:
            st.success("🟢 **Excellent:** High returns with low risk")
        elif twr > 0:
            st.info("🔵 **Good:** Positive returns, moderate risk")
        elif volatility < 15:
            st.warning("🟡 **Defensive:** Low risk but limited returns")
        else:
            st.error("🔴 **High Risk:** High volatility with negative returns")
    
    st.markdown("---")
    
    # ========================================================================
    # DRAWDOWN ANALYSIS
    # ========================================================================
    st.markdown("#### 📉 Drawdown Analysis")
    
    drawdown_info = analytics.get('drawdown_info', {})
    
    if drawdown_info:
        col_dd1, col_dd2, col_dd3 = st.columns(3)
        
        with col_dd1:
            max_dd = drawdown_info.get('max_drawdown', 0.0) * 100
            st.metric(
                "Maximum Drawdown",
                f"{max_dd:.2f}%",
                help="Largest peak-to-trough decline"
            )
        
        with col_dd2:
            recovery_months = drawdown_info.get('recovery_months', 0)
            if recovery_months > 0:
                st.metric(
                    "Recovery Period",
                    f"{recovery_months} months",
                    help="Time to recover from max drawdown"
                )
            else:
                st.metric(
                    "Recovery Period",
                    "Not recovered",
                    help="Portfolio has not recovered from max drawdown"
                )
        
        with col_dd3:
            current_dd = drawdown_info.get('current_drawdown', 0.0) * 100
            st.metric(
                "Current Drawdown",
                f"{current_dd:.2f}%",
                help="Current decline from peak"
            )
        
        # Drawdown timeline chart
        st.markdown("##### Drawdown Timeline")
        
        drawdowns = analytics.get('drawdowns', [])
        if drawdowns:
            fig_dd = go.Figure()
            
            fig_dd.add_trace(go.Scatter(
                x=analysis_data.index,
                y=[dd * 100 for dd in drawdowns],
                mode='lines',
                fill='tozeroy',
                name='Drawdown',
                line=dict(color='#ff4b4b', width=2),
                fillcolor='rgba(255, 75, 75, 0.2)',
                hovertemplate='%{x|%b %Y}<br>Drawdown: %{y:.2f}%<extra></extra>',
            ))
            
            fig_dd.update_layout(
                xaxis_title='Date',
                yaxis_title='Drawdown (%)',
                plot_bgcolor='white',
                paper_bgcolor='white',
                margin=dict(t=20, l=10, r=10, b=10),
                yaxis=dict(tickformat='.2f'),
                hovermode='x unified',
            )
            
            st.plotly_chart(fig_dd, use_container_width=True)
    else:
        st.info("📊 Drawdown analysis not available")
    
    st.markdown("---")
    
    # ========================================================================
    # PERFORMANCE INSIGHTS
    # ========================================================================
    st.markdown("#### 💡 Performance Insights")
    
    insights = []
    
    # Return insights
    if twr > 10:
        insights.append("🟢 **Strong Performance:** Your portfolio has delivered excellent returns")
    elif twr > 5:
        insights.append("🟡 **Moderate Performance:** Your portfolio is performing reasonably well")
    elif twr > 0:
        insights.append("🟠 **Modest Performance:** Your portfolio has positive but limited returns")
    else:
        insights.append("🔴 **Underperformance:** Your portfolio has negative returns")
    
    # Risk insights
    if sharpe > 1.5:
        insights.append("🟢 **Excellent Risk-Adjusted Returns:** High Sharpe ratio indicates strong risk-adjusted performance")
    elif sharpe > 1.0:
        insights.append("🟡 **Good Risk-Adjusted Returns:** Sharpe ratio above 1.0 is solid")
    elif sharpe > 0.5:
        insights.append("🟠 **Fair Risk-Adjusted Returns:** Consider reducing volatility or improving returns")
    else:
        insights.append("🔴 **Poor Risk-Adjusted Returns:** Returns don't justify the risk taken")
    
    # Alpha insights
    if alpha > 2:
        insights.append(f"🟢 **Outperforming Benchmark:** You're beating {benchmark_ticker} by {alpha:.2f}% annually")
    elif alpha > 0:
        insights.append(f"🟡 **Slight Outperformance:** You're ahead of {benchmark_ticker} by {alpha:.2f}% annually")
    elif alpha > -2:
        insights.append(f"🟠 **Slight Underperformance:** You're behind {benchmark_ticker} by {abs(alpha):.2f}% annually")
    else:
        insights.append(f"🔴 **Significant Underperformance:** You're trailing {benchmark_ticker} by {abs(alpha):.2f}% annually")
    
    # Beta insights
    if beta < 0.8:
        insights.append("🔵 **Defensive Portfolio:** Lower volatility than market (Beta < 0.8)")
    elif beta > 1.2:
        insights.append("🔴 **Aggressive Portfolio:** Higher volatility than market (Beta > 1.2)")
    else:
        insights.append("🟢 **Balanced Portfolio:** Similar volatility to market (Beta ≈ 1.0)")
    
    # Drawdown insights
    if max_dd < -20:
        insights.append(f"🔴 **High Drawdown Risk:** Maximum drawdown of {abs(max_dd):.1f}% indicates significant volatility")
    elif max_dd < -10:
        insights.append(f"🟡 **Moderate Drawdown:** Maximum drawdown of {abs(max_dd):.1f}% is within normal range")
    else:
        insights.append(f"🟢 **Low Drawdown:** Maximum drawdown of {abs(max_dd):.1f}% shows good downside protection")
    
    for insight in insights:
        st.markdown(f"- {insight}")
    
    # ========================================================================
    # PDF EXPORT
    # ========================================================================
    if export_pdf:
        st.info("📄 PDF export functionality coming soon! This will generate a comprehensive performance report.")
        # TODO: Implement PDF export using reportlab or similar

# Made with Bob
