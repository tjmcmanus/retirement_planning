"""
components/reporting/section_renderers.py
==========================================
Section renderers for report generation.

Each renderer handles a specific section type and knows how to
collect data and render it to a PDF.
"""
from __future__ import annotations

from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime
import logging
import re

import pandas as pd
import streamlit as st

from .pdf_generator import PDFGenerator

logger = logging.getLogger(__name__)


def parse_bullet_text(text: str) -> Tuple[str, List[str]]:
    """
    Parse text containing bullet points into intro text and bullet list.
    
    Args:
        text: Text that may contain bullet points (•)
        
    Returns:
        tuple: (intro_text, bullet_items)
    """
    # Split on bullet character
    parts = text.split('•')
    intro = parts[0].strip()
    bullets = [item.strip() for item in parts[1:] if item.strip()]
    
    return intro, bullets


class SectionRenderer:
    """Base class for section renderers."""
    
    def __init__(self, section_config: Dict[str, Any]):
        """
        Initialize section renderer.
        
        Args:
            section_config: Section configuration from template
        """
        self.section_id = section_config.get('section_id', 'unknown')
        self.title = section_config.get('title', 'Untitled Section')
        self.config = section_config.get('config', {})
    
    def render(self, pdf: PDFGenerator, data: Dict[str, Any]):
        """
        Render section to PDF.
        
        Args:
            pdf: PDFGenerator instance
            data: Collected data for the report
        """
        raise NotImplementedError("Subclasses must implement render()")
    
    def collect_data(self) -> Dict[str, Any]:
        """
        Collect data needed for this section.
        
        Returns:
            Dictionary of collected data
        """
        return {}


class TitlePageRenderer(SectionRenderer):
    """Render title page."""
    
    def render(self, pdf: PDFGenerator, data: Dict[str, Any]):
        """Render title page with branding."""
        title = data.get('report_title', 'Retirement Planning Report')
        subtitle = data.get('report_subtitle')
        prepared_for = data.get('prepared_for')
        date = data.get('report_date', datetime.now().strftime("%B %d, %Y"))
        
        disclaimer = None
        if self.config.get('show_disclaimer'):
            disclaimer = self.config.get(
                'disclaimer_text',
                'This report is for informational purposes only.'
            )
        
        pdf.add_title_page(
            title=title,
            subtitle=subtitle,
            prepared_for=prepared_for,
            date=date,
            disclaimer=disclaimer
        )
        
        logger.debug("Rendered title page")


class ExecutiveSummaryRenderer(SectionRenderer):
    """Render executive summary with key metrics."""
    
    def render(self, pdf: PDFGenerator, data: Dict[str, Any]):
        """Render executive summary section."""
        pdf.add_section(self.title, "", level=1)
        
        # Key metrics
        metrics = self.config.get('include_metrics', [])
        if metrics and 'metrics' in data:
            pdf.add_section("Key Metrics", "", level=2)
            
            metrics_data = []
            for metric_id in metrics:
                if metric_id in data['metrics']:
                    metric_info = data['metrics'][metric_id]
                    metrics_data.append({
                        'Metric': metric_info.get('name', metric_id),
                        'Value': metric_info.get('value', 'N/A'),
                        'Status': metric_info.get('status', '')
                    })
            
            if metrics_data:
                metrics_df = pd.DataFrame(metrics_data)
                pdf.add_table(metrics_df, style='colorful')
        
        # Key findings
        if self.config.get('include_key_findings') and 'key_findings' in data:
            pdf.add_section("Key Findings", "", level=2)
            findings = data['key_findings']
            if isinstance(findings, list):
                pdf.add_bullet_list(findings)
            else:
                pdf.add_section("", findings, level=3)
        
        # Recommendations
        if self.config.get('include_recommendations') and 'recommendations' in data:
            pdf.add_section("Recommendations", "", level=2)
            recommendations = data['recommendations']
            if isinstance(recommendations, list):
                pdf.add_bullet_list(recommendations)
            else:
                pdf.add_section("", recommendations, level=3)
        
        # Action items
        if self.config.get('include_action_items') and 'action_items' in data:
            pdf.add_section("Action Items", "", level=2)
            action_items = data['action_items']
            if isinstance(action_items, list):
                pdf.add_bullet_list(action_items)
        
        logger.debug("Rendered executive summary")


class CurrentPositionRenderer(SectionRenderer):
    """Render current financial position."""
    
    def render(self, pdf: PDFGenerator, data: Dict[str, Any]):
        """Render current position section."""
        pdf.add_section(self.title, "", level=1)
        
        # Net worth statement
        if self.config.get('include_net_worth_statement'):
            # Use the same rendering logic as NetWorthStatementRenderer
            from components.shared import (
                _compute_net_worth_summary,
                _get_real_estate_rows,
            )
            
            pdf.add_section("Net Worth Statement", "", level=2)
            
            # Get portfolio data
            if 'portfolio' not in data or data.get('portfolio') is None:
                pdf.add_section("", "No portfolio data available.", level=3)
                return
            
            portfolio_df = data['portfolio']
            
            if portfolio_df.empty:
                pdf.add_section("", "Portfolio data is empty.", level=3)
                return
            
            # Get net worth history for summary calculations
            networth_history = data.get('net_worth', pd.DataFrame())
            
            if 'account_type' in portfolio_df.columns and 'account_name' in portfolio_df.columns:
                # Add real estate if available
                re_rows = _get_real_estate_rows()
                combined_df = pd.concat([portfolio_df, re_rows], ignore_index=True) if not re_rows.empty else portfolio_df
                
                # Group by account type and account name
                acct_grp = combined_df.groupby(['account_type', 'account_name'], as_index=False)['market_value'].sum()
                
                # Define account type order and labels (matching dashboard)
                account_type_order = ['Savings', 'Brokerage', 'Traditional', 'Roth', 'Real Estate']
                account_type_labels = {
                    'Savings': 'Savings',
                    'Brokerage': 'Investment',
                    'Traditional': 'Tax Deferred',
                    'Roth': 'Tax Free',
                    'Real Estate': 'Real Estate'
                }
                
                # Build hierarchical table data
                table_data = []
                type_totals = {}
                
                for acct_type in account_type_order:
                    accounts = acct_grp[acct_grp['account_type'] == acct_type]
                    if accounts.empty:
                        continue
                    
                    type_total = accounts['market_value'].sum()
                    type_totals[acct_type] = type_total
                    label = account_type_labels.get(acct_type, acct_type)
                    
                    # Add first account with type label and total
                    first_account = accounts.iloc[0]
                    table_data.append([
                        label,
                        f"${type_total:,.0f}",
                        f"${first_account['market_value']:,.0f}",
                        first_account['account_name']
                    ])
                    
                    # Add remaining accounts (empty type and total columns)
                    for _, account in accounts.iloc[1:].iterrows():
                        table_data.append([
                            "",
                            "",
                            f"${account['market_value']:,.0f}",
                            account['account_name']
                        ])
                
                # Calculate totals
                grand_total = sum(type_totals.values())
                
                # Add summary rows
                if len(networth_history) >= 2:
                    summary = _compute_net_worth_summary(networth_history)
                    mom_change = summary['mom_change']
                    ytd_gain = summary['ytd_gain']
                    rolling_gain = summary['rolling_gain']
                    
                    table_data.append(['', '', '', ''])  # Spacer
                    table_data.append([
                        'Total Net Worth',
                        f"${grand_total:,.0f}",
                        'Change from Last Month',
                        f"${mom_change:,.0f}"
                    ])
                    table_data.append([
                        'Year to Date Gains (Losses)',
                        '',
                        '',
                        f"${ytd_gain:,.0f}"
                    ])
                    table_data.append([
                        'Rolling 12 Month Gains (Losses)',
                        '',
                        '',
                        f"${rolling_gain:,.0f}"
                    ])
                else:
                    table_data.append(['', '', '', ''])  # Spacer
                    table_data.append([
                        'Total Net Worth',
                        f"${grand_total:,.0f}",
                        '',
                        ''
                    ])
                
                # Create DataFrame for table
                statement_df = pd.DataFrame(
                    table_data,
                    columns=['TYPE', 'TYPE TOTAL', 'ACCOUNT TOTAL', 'ACCOUNT']
                )
                
                pdf.add_table(statement_df, title="Account Balances")
        
        # Account summary
        if self.config.get('include_account_summary') and 'accounts' in data:
            pdf.add_section("Account Summary", "", level=2)
            accounts_df = data['accounts']
            if isinstance(accounts_df, pd.DataFrame):
                pdf.add_table(accounts_df)
        
        # Asset allocation
        if self.config.get('include_asset_allocation') and 'asset_allocation' in data:
            pdf.add_section("Asset Allocation", "", level=2)
            
            if 'asset_allocation_chart' in data:
                pdf.add_chart(
                    data['asset_allocation_chart'],
                    title="Current Asset Allocation",
                    width=5,
                    height=4
                )
        
        logger.debug("Rendered current position")


class RetirementStrategyRenderer(SectionRenderer):
    """Render retirement income strategy."""
    
    def render(self, pdf: PDFGenerator, data: Dict[str, Any]):
        """Render retirement strategy section."""
        pdf.add_section(self.title, "", level=1)
        
        # Withdrawal plan
        if self.config.get('include_withdrawal_plan') and 'withdrawal_plan' in data:
            pdf.add_section("Withdrawal Plan", "", level=2)
            
            plan_df = data['withdrawal_plan']
            if isinstance(plan_df, pd.DataFrame):
                # Show first 10 years
                pdf.add_table(plan_df.head(10), title="Projected Withdrawals (First 10 Years)")
        
        # Income sources
        if self.config.get('include_income_sources') and 'income_sources' in data:
            pdf.add_section("Income Sources", "", level=2)
            
            if 'income_chart' in data:
                pdf.add_chart(
                    data['income_chart'],
                    title="Projected Income Sources",
                    width=6,
                    height=4
                )
        
        # Life stages
        if self.config.get('include_life_stages') and 'life_stages' in data:
            pdf.add_section("Life Stage Strategy", "", level=2)
            
            stages = data['life_stages']
            if isinstance(stages, list):
                for stage in stages:
                    pdf.add_section(stage.get('name', ''), stage.get('description', ''), level=3)
        
        logger.debug("Rendered retirement strategy")


class TaxAnalysisRenderer(SectionRenderer):
    """Render tax planning analysis."""
    
    def render(self, pdf: PDFGenerator, data: Dict[str, Any]):
        """Render tax analysis section."""
        pdf.add_section(self.title, "", level=1)
        
        section_id = self.section_id
        
        # Current Tax Situation section
        if section_id == 'current_tax_situation':
            if 'current_tax' in data and data['current_tax']:
                tax_data = data['current_tax']
                if isinstance(tax_data, dict):
                    if self.config.get('include_current_year_projection'):
                        pdf.add_section("Current Year Projection", "", level=2)
                        summary_items = []
                        if 'federal_tax' in tax_data:
                            summary_items.append(f"Estimated Federal Tax: ${tax_data['federal_tax']:,.0f}")
                        if 'state_tax' in tax_data:
                            summary_items.append(f"Estimated State Tax: ${tax_data['state_tax']:,.0f}")
                        if 'total_tax' in tax_data:
                            summary_items.append(f"Total Tax: ${tax_data['total_tax']:,.0f}")
                        
                        if summary_items:
                            pdf.add_bullet_list(summary_items)
                    
                    if self.config.get('include_effective_rate') and 'effective_rate' in tax_data:
                        pdf.add_section("Effective Tax Rate", f"{tax_data['effective_rate'] * 100:.1f}%", level=2)
                    
                    if self.config.get('include_marginal_rate') and 'marginal_rate' in tax_data:
                        pdf.add_section("Marginal Tax Rate", f"{tax_data['marginal_rate'] * 100:.1f}%", level=2)
                    
                    if self.config.get('include_irmaa_status') and 'irmaa_status' in tax_data:
                        pdf.add_section("IRMAA Status", tax_data['irmaa_status'], level=2)
            else:
                pdf.add_section("", "Tax data not available. Please configure income sources in the Configuration page to enable tax calculations.", level=2)
        
        # Roth Conversion Analysis section
        elif section_id == 'roth_conversion_analysis':
            if 'roth_conversion' in data and data['roth_conversion']:
                roth_data = data['roth_conversion']
                
                if self.config.get('include_optimal_conversion_amount'):
                    pdf.add_section("Optimal Conversion Amount", "", level=2)
                    if isinstance(roth_data, dict) and 'optimal_amount' in roth_data:
                        pdf.add_section("", f"Recommended conversion: ${roth_data['optimal_amount']:,.0f}", level=3)
                
                if self.config.get('include_multi_year_strategy'):
                    pdf.add_section("Multi-Year Strategy", "", level=2)
                    if isinstance(roth_data, dict) and 'multi_year_plan' in roth_data:
                        plan = roth_data['multi_year_plan']
                        if isinstance(plan, pd.DataFrame) and not plan.empty:
                            # Format the DataFrame for display
                            formatted_plan = plan.copy()
                            
                            # Format Year as integer (0 decimals)
                            if 'Year' in formatted_plan.columns:
                                formatted_plan['Year'] = formatted_plan['Year'].astype(int)
                            
                            # Format dollar amounts with 2 decimals and commas
                            dollar_columns = ['Conversion Amount', 'Estimated Tax', 'Traditional Balance', 'Roth Balance']
                            for col in dollar_columns:
                                if col in formatted_plan.columns:
                                    formatted_plan[col] = formatted_plan[col].apply(lambda x: f"${x:,.2f}")
                            
                            pdf.add_table(formatted_plan)
                
                if self.config.get('include_tax_cost_analysis') and 'roth_conversion_chart' in data:
                    pdf.add_section("Tax Cost Analysis", "", level=2)
                    pdf.add_chart(
                        data['roth_conversion_chart'],
                        title="Roth Conversion Tax Impact",
                        width=6,
                        height=4
                    )
            else:
                pdf.add_section("", "Roth conversion analysis not available. This requires tax projection data.", level=2)
        
        # Tax Loss Harvesting section
        elif section_id == 'tax_harvesting':
            if 'tax_harvesting' in data and data['tax_harvesting'] is not None:
                harvesting_data = data['tax_harvesting']
                
                if self.config.get('include_current_opportunities'):
                    pdf.add_section("Current Opportunities", "", level=2)
                    if isinstance(harvesting_data, pd.DataFrame) and not harvesting_data.empty:
                        pdf.add_table(harvesting_data, title="Tax Loss Harvesting Opportunities")
                    else:
                        pdf.add_section("", "No tax loss harvesting opportunities identified at this time.", level=3)
                
                if self.config.get('include_historical_analysis'):
                    pdf.add_section("Historical Analysis", "", level=2)
                    pdf.add_section("", "Historical harvesting data would appear here when available.", level=3)
                
                if self.config.get('include_wash_sale_tracking'):
                    pdf.add_section("Wash Sale Tracking", "", level=2)
                    pdf.add_section("", "Wash sale tracking data would appear here when available.", level=3)
            else:
                pdf.add_section("", "Tax loss harvesting analysis requires portfolio holdings with cost basis data.", level=2)
        
        # Charitable Giving section
        elif section_id == 'charitable_giving':
            if 'charitable_giving' in data and data['charitable_giving']:
                giving_data = data['charitable_giving']
                
                if self.config.get('include_daf_analysis'):
                    pdf.add_section("Donor-Advised Fund (DAF) Analysis", "", level=2)
                    if isinstance(giving_data, dict) and 'daf_benefit' in giving_data:
                        pdf.add_section("", f"Estimated tax benefit: ${giving_data['daf_benefit']:,.0f}", level=3)
                    else:
                        pdf.add_section("", "DAF analysis available when charitable giving goals are configured.", level=3)
                
                if self.config.get('include_qcd_analysis'):
                    pdf.add_section("Qualified Charitable Distribution (QCD) Analysis", "", level=2)
                    if isinstance(giving_data, dict) and 'qcd_benefit' in giving_data:
                        pdf.add_section("", f"Potential QCD benefit: ${giving_data['qcd_benefit']:,.0f}", level=3)
                    else:
                        pdf.add_section("", "QCD analysis available for individuals age 70½ or older with IRA accounts.", level=3)
                
                if self.config.get('include_bunching_strategy'):
                    pdf.add_section("Bunching Strategy", "", level=2)
                    pdf.add_section("", "Charitable bunching strategy analysis would appear here when configured.", level=3)
                
                if self.config.get('include_tax_savings'):
                    pdf.add_section("Tax Savings Summary", "", level=2)
                    if isinstance(giving_data, dict) and 'total_savings' in giving_data:
                        pdf.add_section("", f"Total estimated tax savings: ${giving_data['total_savings']:,.0f}", level=3)
            else:
                pdf.add_section("", "Charitable giving analysis not available. Configure charitable goals in the strategy settings.", level=2)
        
        # Multi-Year Tax Projections section
        elif section_id == 'multi_year_projections':
            if 'tax_projections' in data and data['tax_projections'] is not None:
                proj_data = data['tax_projections']
                
                years = self.config.get('projection_years', 10)
                pdf.add_section(f"{years}-Year Tax Projection", "", level=2)
                
                if isinstance(proj_data, pd.DataFrame) and not proj_data.empty:
                    # Format the DataFrame for display
                    formatted_proj = proj_data.head(years).copy()
                    
                    # Format Year as integer (0 decimals)
                    if 'Year' in formatted_proj.columns:
                        formatted_proj['Year'] = formatted_proj['Year'].astype(int)
                    
                    # Format dollar amounts with 2 decimals and commas
                    dollar_columns = ['Income', 'Federal Tax', 'State Tax', 'Total Tax']
                    for col in dollar_columns:
                        if col in formatted_proj.columns:
                            formatted_proj[col] = formatted_proj[col].apply(lambda x: f"${x:,.2f}")
                    
                    # Format Effective Rate as percentage with 1 decimal
                    if 'Effective Rate' in formatted_proj.columns:
                        formatted_proj['Effective Rate'] = formatted_proj['Effective Rate'].apply(lambda x: f"{x:.1f}")
                    
                    # Show table
                    pdf.add_table(formatted_proj, title=f"Tax Projections (Next {years} Years)")
                    
                    # Show chart if configured
                    if self.config.get('include_charts') and 'tax_projection_chart' in data:
                        pdf.add_chart(
                            data['tax_projection_chart'],
                            title="Multi-Year Tax Projection",
                            width=6,
                            height=4
                        )
                    
                    if self.config.get('include_bracket_analysis'):
                        pdf.add_section("Tax Bracket Analysis", "", level=2)
                        pdf.add_section("", "Tax bracket progression analysis would appear here.", level=3)
                else:
                    pdf.add_section("", "Multi-year tax projections require retirement strategy configuration.", level=3)
            else:
                pdf.add_section("", "Tax projections not available. Run retirement strategy analysis first.", level=2)
        
        # Generic tax analysis (backward compatibility)
        else:
            # Current tax
            if self.config.get('include_current_tax') and 'current_tax' in data:
                pdf.add_section("Current Tax Situation", "", level=2)
                
                tax_data = data['current_tax']
                if isinstance(tax_data, dict):
                    summary = f"""
                    Estimated Federal Tax: ${tax_data.get('federal_tax', 0):,.0f}
                    Estimated State Tax: ${tax_data.get('state_tax', 0):,.0f}
                    Effective Tax Rate: {tax_data.get('effective_rate', 0) * 100:.1f}%
                    Marginal Tax Rate: {tax_data.get('marginal_rate', 0) * 100:.1f}%
                    """
                    pdf.add_section("", summary, level=3)
            
            # Roth conversion
            if self.config.get('include_roth_conversion') and 'roth_conversion' in data:
                pdf.add_section("Roth Conversion Analysis", "", level=2)
                
                if 'roth_conversion_chart' in data:
                    pdf.add_chart(
                        data['roth_conversion_chart'],
                        title="Optimal Roth Conversion Strategy",
                        width=6,
                        height=4
                    )
            
            # Tax harvesting
            if self.config.get('include_tax_harvesting') and 'tax_harvesting' in data:
                pdf.add_section("Tax Loss Harvesting", "", level=2)
                
                harvesting_data = data['tax_harvesting']
                if isinstance(harvesting_data, pd.DataFrame) and not harvesting_data.empty:
                    pdf.add_table(harvesting_data, title="Harvesting Opportunities")
        
        logger.debug(f"Rendered tax analysis section: {section_id}")


class PortfolioAnalysisRenderer(SectionRenderer):
    """Render portfolio analysis."""
    
    def render(self, pdf: PDFGenerator, data: Dict[str, Any]):
        """Render portfolio analysis section."""
        pdf.add_section(self.title, "", level=1)
        
        section_id = self.section_id
        
        # Portfolio Summary section
        if section_id == 'portfolio_summary':
            if self.config.get('include_total_value') and 'portfolio' in data:
                portfolio_df = data['portfolio']
                if isinstance(portfolio_df, pd.DataFrame) and not portfolio_df.empty:
                    total_value = portfolio_df['market_value'].sum()
                    pdf.add_section("Total Portfolio Value", f"${total_value:,.2f}", level=2)
            
            if self.config.get('include_account_breakdown') and 'accounts' in data:
                pdf.add_section("Account Breakdown", "", level=2)
                accounts_df = data['accounts']
                if isinstance(accounts_df, pd.DataFrame) and not accounts_df.empty:
                    pdf.add_table(accounts_df)
            
            if self.config.get('include_asset_allocation') and 'asset_allocation_chart' in data:
                pdf.add_section("Asset Allocation", "", level=2)
                pdf.add_chart(
                    data['asset_allocation_chart'],
                    title="Current Asset Allocation",
                    width=5,
                    height=4
                )
        
        # Holdings Detail section
        elif section_id == 'holdings_detail':
            if self.config.get('include_all_positions') and 'holdings' in data:
                holdings_df = data['holdings']
                if isinstance(holdings_df, pd.DataFrame) and not holdings_df.empty:
                    if self.config.get('group_by_account'):
                        pdf.add_section("Holdings by Account", "", level=2)
                        # Group by account if account_name column exists
                        if 'account_name' in holdings_df.columns:
                            for account in holdings_df['account_name'].unique():
                                account_holdings = holdings_df[holdings_df['account_name'] == account]
                                pdf.add_section(account, "", level=3)
                                pdf.add_table(account_holdings)
                        else:
                            pdf.add_table(holdings_df)
                    else:
                        pdf.add_section("All Holdings", "", level=2)
                        pdf.add_table(holdings_df)
        
        # Performance Analysis section
        elif section_id == 'performance_analysis':
            has_content = False
            
            if self.config.get('include_returns'):
                pdf.add_section("Returns", "", level=2)
                if 'performance' in data and data['performance'] is not None:
                    perf_data = data['performance']
                    if isinstance(perf_data, pd.DataFrame) and not perf_data.empty:
                        pdf.add_table(perf_data)
                        has_content = True
                    else:
                        pdf.add_section("", "Performance data requires historical portfolio values.", level=3)
                else:
                    pdf.add_section("", "Performance data requires historical portfolio values.", level=3)
            
            if self.config.get('include_benchmark_comparison'):
                pdf.add_section("Benchmark Comparison", "", level=2)
                if 'performance_chart' in data:
                    pdf.add_chart(
                        data['performance_chart'],
                        title="Portfolio vs Benchmark",
                        width=6,
                        height=4
                    )
                    has_content = True
                else:
                    pdf.add_section("", "Benchmark comparison requires performance tracking to be enabled.", level=3)
            
            if self.config.get('include_risk_metrics'):
                pdf.add_section("Risk Metrics", "", level=2)
                if 'risk_metrics' in data and data['risk_metrics']:
                    risk_data = data['risk_metrics']
                    if isinstance(risk_data, dict):
                        for metric, value in risk_data.items():
                            pdf.add_section(f"{metric}:", str(value), level=3)
                        has_content = True
                    else:
                        pdf.add_section("", "Risk metrics calculated from historical performance data.", level=3)
                else:
                    pdf.add_section("", "Risk metrics calculated from historical performance data.", level=3)
            
            if not has_content:
                logger.info("Performance analysis section has no data")
        
        # Factor Analysis section
        elif section_id == 'factor_analysis':
            has_content = False
            
            if self.config.get('include_factor_exposures'):
                pdf.add_section("Factor Exposures", "", level=2)
                if 'factor_chart' in data:
                    pdf.add_chart(
                        data['factor_chart'],
                        title="Portfolio Factor Exposures",
                        width=6,
                        height=4
                    )
                    has_content = True
                else:
                    pdf.add_section("", "Factor analysis available through Portfolio Hub > Factor Analysis.", level=3)
            
            if self.config.get('include_sector_breakdown'):
                pdf.add_section("Sector Breakdown", "", level=2)
                if 'sector_breakdown' in data and data['sector_breakdown'] is not None:
                    sector_data = data['sector_breakdown']
                    if isinstance(sector_data, pd.DataFrame) and not sector_data.empty:
                        pdf.add_table(sector_data)
                        has_content = True
                    else:
                        pdf.add_section("", "Sector breakdown requires holdings with sector classifications.", level=3)
                else:
                    pdf.add_section("", "Sector breakdown requires holdings with sector classifications.", level=3)
            
            if not has_content:
                logger.info("Factor analysis section has no data")
        
        # Rebalancing section
        elif section_id == 'rebalancing':
            has_content = False
            
            if self.config.get('include_current_vs_target'):
                pdf.add_section("Current vs Target Allocation", "", level=2)
                if 'rebalancing_analysis' in data and data['rebalancing_analysis'] is not None:
                    rebal_data = data['rebalancing_analysis']
                    if isinstance(rebal_data, pd.DataFrame) and not rebal_data.empty:
                        pdf.add_table(rebal_data)
                        has_content = True
                    else:
                        pdf.add_section("", "Rebalancing analysis requires target allocation to be configured.", level=3)
                else:
                    pdf.add_section("", "Rebalancing analysis requires target allocation to be configured in Portfolio Hub.", level=3)
            
            if self.config.get('include_trade_recommendations'):
                pdf.add_section("Recommended Trades", "", level=2)
                if 'trade_recommendations' in data and data['trade_recommendations']:
                    trades = data['trade_recommendations']
                    if isinstance(trades, list) and trades:
                        pdf.add_bullet_list(trades)
                        has_content = True
                    elif isinstance(trades, pd.DataFrame) and not trades.empty:
                        pdf.add_table(trades)
                        has_content = True
                    else:
                        pdf.add_section("", "No rebalancing trades recommended at this time.", level=3)
                else:
                    pdf.add_section("", "Trade recommendations generated when portfolio drifts from target allocation.", level=3)
            
            if not has_content:
                logger.info("Rebalancing section has no data")
        
        # Risk Assessment section
        elif section_id == 'risk_assessment':
            has_content = False
            
            if self.config.get('include_volatility'):
                pdf.add_section("Volatility Analysis", "", level=2)
                if 'volatility_metrics' in data and data['volatility_metrics']:
                    vol_data = data['volatility_metrics']
                    if isinstance(vol_data, dict):
                        for metric, value in vol_data.items():
                            pdf.add_section(f"{metric}:", str(value), level=3)
                        has_content = True
                    else:
                        pdf.add_section("", "Volatility metrics calculated from historical returns.", level=3)
                else:
                    pdf.add_section("", "Volatility metrics calculated from historical returns.", level=3)
            
            if self.config.get('include_drawdown_analysis'):
                pdf.add_section("Drawdown Analysis", "", level=2)
                if 'drawdown_chart' in data:
                    pdf.add_chart(
                        data['drawdown_chart'],
                        title="Historical Drawdowns",
                        width=6,
                        height=4
                    )
                    has_content = True
                else:
                    pdf.add_section("", "Drawdown analysis requires historical portfolio values.", level=3)
            
            if not has_content:
                logger.info("Risk assessment section has no data")
        
        # Generic portfolio analysis (backward compatibility)
        else:
            # Holdings
            if self.config.get('include_holdings') and 'holdings' in data:
                pdf.add_section("Current Holdings", "", level=2)
                
                holdings_df = data['holdings']
                if isinstance(holdings_df, pd.DataFrame) and not holdings_df.empty:
                    pdf.add_table(holdings_df.head(20), title="Top 20 Holdings")
            
            # Performance
            if self.config.get('include_performance') and 'performance' in data:
                pdf.add_section("Performance Metrics", "", level=2)
                
                perf_data = data['performance']
                if isinstance(perf_data, pd.DataFrame) and not perf_data.empty:
                    pdf.add_table(perf_data)
                
                if 'performance_chart' in data:
                    pdf.add_chart(
                        data['performance_chart'],
                        title="Portfolio Performance",
                        width=6,
                        height=4
                    )
            
            # Factor analysis
            if self.config.get('include_factor_analysis') and 'factor_analysis' in data:
                pdf.add_section("Factor Analysis", "", level=2)
                
                if 'factor_chart' in data:
                    pdf.add_chart(
                        data['factor_chart'],
                        title="Factor Exposures",
                        width=6,
                        height=4
                    )
        
        logger.debug(f"Rendered portfolio analysis section: {section_id}")


class MonteCarloRenderer(SectionRenderer):
    """Render Monte Carlo simulation results."""
    
    def render(self, pdf: PDFGenerator, data: Dict[str, Any]):
        """Render Monte Carlo section."""
        pdf.add_section(self.title, "", level=1)
        
        # Success rate
        if self.config.get('include_success_rate') and 'monte_carlo' in data:
            mc_data = data.get('monte_carlo')
            
            if mc_data is not None and isinstance(mc_data, dict):
                success_rate = mc_data.get('success_rate', 0) * 100  # Convert to percentage
                n_sims = mc_data.get('n_simulations', 10000)
                median_final = mc_data.get('median_final_portfolio', 0)
                p10_final = mc_data.get('p10_final_portfolio', 0)
                p90_final = mc_data.get('p90_final_portfolio', 0)
                annual_withdrawal = mc_data.get('annual_withdrawal', 0)
                initial_portfolio = mc_data.get('initial_portfolio', 0)
                social_security = mc_data.get('social_security_annual', 0)
                ss_start_age = mc_data.get('ss_start_age')
                filing_status = mc_data.get('filing_status', 'Unknown')
                
                pdf.add_section("Success Rate", "", level=2)
                
                # Success rate with interpretation
                success_text = f"Plan Success Rate: {success_rate:.1f}%"
                if success_rate >= 90:
                    success_text += " (Excellent - High confidence in plan success)"
                elif success_rate >= 75:
                    success_text += " (Good - Moderate confidence, consider adjustments)"
                else:
                    success_text += " (Needs Attention - Plan may require significant adjustments)"
                
                pdf.add_section("", success_text, level=3)
                
                # Add simulation parameters
                sim_params = [
                    f"Based on {n_sims:,} Monte Carlo simulations",
                    f"Filing Status: {filing_status}"
                ]
                if annual_withdrawal > 0:
                    withdrawal_pct = (annual_withdrawal / initial_portfolio * 100) if initial_portfolio > 0 else 0
                    sim_params.append(f"Annual Withdrawal: ${annual_withdrawal:,.0f} ({withdrawal_pct:.2f}% of initial portfolio)")
                if initial_portfolio > 0:
                    sim_params.append(f"Starting Portfolio: ${initial_portfolio:,.0f}")
                if social_security > 0:
                    ss_text = f"Social Security: ${social_security:,.0f}/year"
                    if ss_start_age:
                        ss_text += f" (starting at age {ss_start_age})"
                    sim_params.append(ss_text)
                
                for param in sim_params:
                    pdf.add_section("", param, level=3)
                
                # Portfolio outcomes
                pdf.add_section("Portfolio Outcomes", "", level=2)
                outcomes_bullets = [
                    f"Median Final Portfolio: ${median_final:,.2f}",
                    f"10th Percentile (Worst Case): ${p10_final:,.2f}",
                    f"90th Percentile (Best Case): ${p90_final:,.2f}"
                ]
                pdf.add_bullet_list(outcomes_bullets)
                
                # Add interpretation
                interpretation = (
                    "The median outcome represents the middle scenario across all simulations. "
                    "The 10th percentile shows the worst 10% of outcomes, while the 90th percentile "
                    "shows the best 10% of outcomes. This range helps you understand the potential "
                    "variability in your retirement plan."
                )
                pdf.add_section("", interpretation, level=3)
                
                # Safe Withdrawal Rates
                if 'safe_withdrawal_rates' in mc_data:
                    swr_data = mc_data['safe_withdrawal_rates']
                    pdf.add_section("Safe Withdrawal Rates", "", level=2)
                    
                    pdf.add_section("",
                        "Safe withdrawal rates represent the maximum annual spending amount that maintains "
                        "your target success probability. These rates are adjusted annually for inflation.",
                        level=3)
                    
                    swr_bullets = []
                    
                    # 90% confidence (conservative)
                    if '90_percent_confidence' in swr_data:
                        swr_90 = swr_data['90_percent_confidence']
                        swr_bullets.append(
                            f"Conservative (90% confidence): ${swr_90['annual_amount']:,.0f}/year "
                            f"({swr_90['percentage']:.2f}% of portfolio)"
                        )
                    
                    # 75% confidence (moderate)
                    if '75_percent_confidence' in swr_data:
                        swr_75 = swr_data['75_percent_confidence']
                        swr_bullets.append(
                            f"Moderate (75% confidence): ${swr_75['annual_amount']:,.0f}/year "
                            f"({swr_75['percentage']:.2f}% of portfolio)"
                        )
                    
                    # 65% confidence (aggressive)
                    if '65_percent_confidence' in swr_data:
                        swr_65 = swr_data['65_percent_confidence']
                        swr_bullets.append(
                            f"Aggressive (65% confidence): ${swr_65['annual_amount']:,.0f}/year "
                            f"({swr_65['percentage']:.2f}% of portfolio)"
                        )
                    
                    if swr_bullets:
                        pdf.add_bullet_list(swr_bullets)
                        
                        # Add context
                        inflation_rate = swr_data.get('inflation_rate', 0.03) * 100
                        pdf.add_section("",
                            f"All withdrawal rates assume {inflation_rate:.1f}% annual inflation adjustment. "
                            "Higher confidence levels provide greater certainty but lower withdrawal amounts. "
                            "Most financial planners recommend the 90% confidence level for retirement planning.",
                            level=3)
            else:
                pdf.add_section("Success Rate", "Monte Carlo simulation data not available. Run Monte Carlo analysis to see success rate projections.", level=2)
        
        # Scenarios
        if self.config.get('include_scenarios') and 'monte_carlo_scenarios' in data:
            pdf.add_section("Scenario Analysis", "", level=2)
            
            if 'monte_carlo_chart' in data:
                pdf.add_chart(
                    data['monte_carlo_chart'],
                    title="Monte Carlo Simulation Results",
                    width=6,
                    height=4
                )
        elif self.config.get('include_scenarios'):
            pdf.add_section("Scenario Analysis", "Monte Carlo scenarios not available. Run Monte Carlo analysis on the Monte Carlo page to generate scenario projections.", level=2)
        
        # Stress tests
        if self.config.get('include_stress_tests') and 'stress_tests' in data:
            pdf.add_section("Stress Testing", "", level=2)
            
            stress_tests = data.get('stress_tests')
            if stress_tests and isinstance(stress_tests, list) and len(stress_tests) > 0:
                # Add introduction
                pdf.add_section("",
                    "Stress tests evaluate how your retirement plan performs under adverse market conditions. "
                    "Each scenario models a specific historical crisis or economic shock.",
                    level=3)
                
                # Create table data with word-wrapped descriptions
                # Import Paragraph for word wrapping
                from reportlab.platypus import Paragraph
                from reportlab.lib.styles import getSampleStyleSheet
                
                styles = getSampleStyleSheet()
                normal_style = styles['Normal']
                normal_style.fontSize = 9
                normal_style.leading = 11
                
                table_data = [['Scenario', 'Description', 'Success', 'Assessment']]  # Header row
                
                for test in stress_tests:
                    success_rate = test.get('success_probability', 0) * 100
                    
                    # Add text status for black and white printing
                    if success_rate >= 90:
                        status = "Excellent"
                    elif success_rate >= 75:
                        status = "Good"
                    elif success_rate >= 60:
                        status = "Moderate"
                    else:
                        status = "Poor"
                    
                    # Get scenario name and wrap in Paragraph for word wrapping
                    scenario_name = test.get('scenario_name', 'Unknown')
                    scenario_short = scenario_name.replace('Financial Crisis', 'Crisis').replace('(Japan-style)', '').strip()
                    scenario_paragraph = Paragraph(scenario_short, normal_style)
                    
                    # Wrap description in Paragraph for word wrapping
                    description = test.get('description', '')
                    desc_paragraph = Paragraph(description, normal_style)
                    
                    table_data.append([
                        scenario_paragraph,  # Use Paragraph for word wrapping
                        desc_paragraph,  # Use Paragraph for word wrapping
                        f"{success_rate:.1f}%",
                        status
                    ])
                
                # Create table directly with ReportLab (bypass DataFrame to preserve Paragraph objects)
                from reportlab.platypus import Table, TableStyle
                from reportlab.lib import colors
                from reportlab.lib.units import inch
                
                # Column widths: Scenario (1.5"), Description (3.8"), Success (0.9"), Assessment (0.8")
                col_widths = [1.5*inch, 3.8*inch, 0.9*inch, 0.8*inch]
                
                table = Table(table_data, colWidths=col_widths)
                table.setStyle(TableStyle([
                    # Header row styling
                    ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, 0), 10),
                    ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                    
                    # Data rows styling
                    ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                    ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
                    ('ALIGN', (0, 1), (0, -1), 'LEFT'),  # Scenario left-aligned
                    ('ALIGN', (1, 1), (1, -1), 'LEFT'),  # Description left-aligned
                    ('ALIGN', (2, 1), (2, -1), 'CENTER'),  # Success centered
                    ('ALIGN', (3, 1), (3, -1), 'CENTER'),  # Assessment centered
                    ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                    ('FONTSIZE', (0, 1), (-1, -1), 9),
                    ('TOPPADDING', (0, 1), (-1, -1), 6),
                    ('BOTTOMPADDING', (0, 1), (-1, -1), 6),
                    ('LEFTPADDING', (0, 0), (-1, -1), 6),
                    ('RIGHTPADDING', (0, 0), (-1, -1), 6),
                    
                    # Grid
                    ('GRID', (0, 0), (-1, -1), 1, colors.black),
                    ('VALIGN', (0, 0), (-1, -1), 'TOP'),  # Vertical align to top for wrapped text
                ]))
                
                # Add title and table to PDF
                from reportlab.platypus import Spacer
                pdf.story.append(Paragraph("Stress Test Results", pdf.styles['Heading3']))
                pdf.story.append(Spacer(1, 0.1*inch))
                pdf.story.append(table)
                pdf.story.append(Spacer(1, 0.2*inch))
                
                # Add interpretation
                interpretation = (
                    "A robust retirement plan should maintain reasonable success rates even under stress scenarios. "
                    "If success rates drop significantly below 75% in multiple scenarios, consider adjusting your "
                    "withdrawal strategy, increasing savings, or modifying your asset allocation."
                )
                pdf.add_section("", interpretation, level=3)
            else:
                pdf.add_section("", "Stress test results not available.", level=3)
        elif self.config.get('include_stress_tests'):
            pdf.add_section("Stress Testing", "Stress test results not available. Run stress tests on the Monte Carlo page to see how your plan performs under adverse conditions.", level=2)
        
        logger.debug("Rendered Monte Carlo analysis")


class AssumptionsRenderer(SectionRenderer):
    """Render assumptions and methodology."""
    
    def render(self, pdf: PDFGenerator, data: Dict[str, Any]):
        """Render assumptions section."""
        pdf.add_section(self.title, "", level=1)
        
        # Return assumptions
        if self.config.get('include_return_assumptions') and 'assumptions' in data:
            pdf.add_section("Return Assumptions", "", level=2)
            
            assumptions = data['assumptions']
            if 'returns' in assumptions:
                returns_text = "\n".join([
                    f"• {k}: {v}% annually"
                    for k, v in assumptions['returns'].items()
                ])
                pdf.add_section("", returns_text, level=3)
        
        # Inflation assumptions
        if self.config.get('include_inflation_assumptions') and 'assumptions' in data:
            pdf.add_section("Inflation Assumptions", "", level=2)
            
            assumptions = data['assumptions']
            inflation = assumptions.get('inflation', 3.0)
            pdf.add_section("", f"Assumed inflation rate: {inflation}% annually", level=3)
        
        # Methodology
        if self.config.get('include_methodology'):
            pdf.add_section("Methodology", "", level=2)
            
            methodology_text = """
            This retirement plan uses a comprehensive financial planning approach that considers:
            
            • Multi-stage withdrawal strategies optimized for tax efficiency
            • Monte Carlo simulation with 1,000+ scenarios
            • Historical market data and forward-looking assumptions
            • Tax-aware portfolio management
            • Social Security optimization
            • Healthcare cost projections including Medicare and IRMAA
            """
            pdf.add_section("", methodology_text, level=3)
        
        logger.debug("Rendered assumptions")


class AppendicesRenderer(SectionRenderer):
    """Render appendices."""
    
    def render(self, pdf: PDFGenerator, data: Dict[str, Any]):
        """Render appendices section."""
        pdf.add_section(self.title, "", level=1)
        
        # Detailed projections
        if self.config.get('include_detailed_projections') and 'detailed_projections' in data:
            pdf.add_section("Detailed Year-by-Year Projections", "", level=2)
            
            proj_df = data['detailed_projections']
            if isinstance(proj_df, pd.DataFrame):
                # Split into chunks if too large
                chunk_size = 15
                for i in range(0, len(proj_df), chunk_size):
                    chunk = proj_df.iloc[i:i+chunk_size]
                    pdf.add_table(chunk, title=f"Years {chunk.iloc[0]['Year']}-{chunk.iloc[-1]['Year']}")
                    if i + chunk_size < len(proj_df):
                        pdf.add_page_break()
        
        # Glossary
        if self.config.get('include_glossary'):
            pdf.add_section("Glossary of Terms", "", level=2)
            
            glossary = {
                'RMD': 'Required Minimum Distribution - Mandatory withdrawals from tax-deferred accounts',
                'Roth Conversion': 'Converting traditional IRA funds to Roth IRA, paying taxes now',
                'IRMAA': 'Income-Related Monthly Adjustment Amount - Medicare premium surcharge',
                'QCD': 'Qualified Charitable Distribution - Tax-free donation from IRA',
                'DAF': 'Donor-Advised Fund - Charitable giving vehicle with tax benefits',
            }
            
            for term, definition in glossary.items():
                pdf.add_section(f"{term}:", definition, level=3)
        
        logger.debug("Rendered appendices")

class NetWorthStatementRenderer(SectionRenderer):
    """Render detailed net worth statement matching dashboard visualization."""
    
    def render(self, pdf: PDFGenerator, data: Dict[str, Any]):
        """Render net worth statement section with hierarchical account breakdown."""
        from components.shared import (
            _compute_net_worth_summary,
            _get_real_estate_rows,
            ACCOUNT_TYPE_MAP,
        )
        
        pdf.add_section(self.title, "", level=1)
        
        # Get portfolio data
        if 'portfolio' not in data or data.get('portfolio') is None:
            pdf.add_section("", "No portfolio data available.", level=2)
            logger.warning("No portfolio data for net worth statement")
            return
        
        portfolio_df = data['portfolio']
        
        # Additional check for empty DataFrame
        if portfolio_df.empty:
            pdf.add_section("", "Portfolio data is empty.", level=2)
            logger.warning("Portfolio data is empty for net worth statement")
            return
        
        # Get net worth history for summary calculations
        networth_history = data.get('networth_history', pd.DataFrame())
        
        # Build account grouping (Type | Type Total | Account Total | Account)
        # Check what columns we have
        logger.info(f"Portfolio columns: {portfolio_df.columns.tolist()}")
        logger.info(f"Portfolio shape: {portfolio_df.shape}")
        
        if 'account_type' in portfolio_df.columns and 'account_name' in portfolio_df.columns:
            # Add real estate if available
            re_rows = _get_real_estate_rows()
            combined_df = pd.concat([portfolio_df, re_rows], ignore_index=True) if not re_rows.empty else portfolio_df
            
            # Group by account type and account name
            acct_grp = combined_df.groupby(['account_type', 'account_name'], as_index=False)['market_value'].sum()
            logger.info(f"Account groups: {len(acct_grp)} accounts")
            
            # Define account type order and labels (matching dashboard)
            # Map database account types to display labels
            account_type_order = ['Savings', 'Brokerage', 'Traditional', 'Roth', 'Real Estate']
            account_type_labels = {
                'Savings': 'Savings',
                'Brokerage': 'Investment',
                'Traditional': 'Tax Deferred',
                'Roth': 'Tax Free',
                'Real Estate': 'Real Estate'
            }
            
            # Build hierarchical table data
            table_data = []
            type_totals = {}
            
            for acct_type in account_type_order:
                accounts = acct_grp[acct_grp['account_type'] == acct_type]
                if accounts.empty:
                    continue
                
                type_total = accounts['market_value'].sum()
                type_totals[acct_type] = type_total
                label = account_type_labels.get(acct_type, acct_type)
                
                # Add first account with type label and total
                first_account = accounts.iloc[0]
                table_data.append([
                    label,
                    f"${type_total:,.2f}",
                    f"${first_account['market_value']:,.2f}",
                    first_account['account_name']
                ])
                
                # Add remaining accounts (empty type and total columns)
                for _, account in accounts.iloc[1:].iterrows():
                    table_data.append([
                        "",
                        "",
                        f"${account['market_value']:,.2f}",
                        account['account_name']
                    ])
            
            # Calculate totals
            grand_total = sum(type_totals.values())
            
            # Add summary rows
            if len(networth_history) >= 2:
                summary = _compute_net_worth_summary(networth_history)
                mom_change = summary['mom_change']
                ytd_gain = summary['ytd_gain']
                rolling_gain = summary['rolling_gain']
                
                table_data.append(['', '', '', ''])  # Spacer
                table_data.append([
                    'Total Net Worth',
                    f"${grand_total:,.2f}",
                    'Change from Last Month',
                    f"${mom_change:,.2f}"
                ])
                table_data.append([
                    'Year to Date Gains (Losses)',
                    '',
                    '',
                    f"${ytd_gain:,.2f}"
                ])
                table_data.append([
                    'Rolling 12 Month Gains (Losses)',
                    '',
                    '',
                    f"${rolling_gain:,.2f}"
                ])
            else:
                table_data.append(['', '', '', ''])  # Spacer
                table_data.append([
                    'Total Net Worth',
                    f"${grand_total:,.2f}",
                    '',
                    ''
                ])
            
            # Create DataFrame for table
            statement_df = pd.DataFrame(
                table_data,
                columns=['TYPE', 'TYPE TOTAL', 'ACCOUNT TOTAL', 'ACCOUNT']
            )
            
            pdf.add_table(statement_df, title="Net Worth Statement")
        else:
            # Fallback: simple summary by account type
            if 'account_type' in portfolio_df.columns:
                summary = portfolio_df.groupby('account_type')['market_value'].sum().reset_index()
                summary.columns = ['Account Type', 'Total Value']
                summary['Total Value'] = summary['Total Value'].apply(lambda x: f"${x:,.2f}")
                pdf.add_table(summary, title="Net Worth by Account Type")
        
        logger.debug("Rendered net worth statement")


class NetWorthTrendsRenderer(SectionRenderer):
    """Render net worth trends and analysis."""
    
    def render(self, pdf: PDFGenerator, data: Dict[str, Any]):
        """Render net worth trends section."""
        pdf.add_section(self.title, "", level=1)
        
        # Historical chart
        if self.config.get('include_historical_chart') and 'net_worth_chart' in data:
            pdf.add_chart(
                data['net_worth_chart'],
                title="Net Worth Historical Trend",
                width=6,
                height=4
            )
        
        # Growth analysis
        if self.config.get('include_growth_analysis') and 'net_worth' in data:
            pdf.add_section("Growth Analysis", "", level=2)
            
            nw = data['net_worth']
            if isinstance(nw, pd.DataFrame) and len(nw) >= 2:
                current = nw['total'].iloc[-1]
                month_ago = nw['total'].iloc[-2]
                mom_change = current - month_ago
                mom_pct = (mom_change / month_ago * 100) if month_ago != 0 else 0
                
                analysis_text = f"""
                Month-over-Month Change: ${mom_change:,.0f} ({mom_pct:+.1f}%)
                
                Your net worth has {'increased' if mom_change > 0 else 'decreased'} by 
                ${abs(mom_change):,.0f} over the past month.
                """
                pdf.add_section("", analysis_text, level=3)
        
        logger.debug("Rendered net worth trends")


class AccountBreakdownRenderer(SectionRenderer):
    """Render account breakdown by type."""
    
    def render(self, pdf: PDFGenerator, data: Dict[str, Any]):
        """Render account breakdown section."""
        pdf.add_section(self.title, "", level=1)
        
        # Account summary
        if self.config.get('include_account_summary') and 'accounts' in data:
            pdf.add_section("Summary by Account Type", "", level=2)
            
            accounts_df = data['accounts']
            if isinstance(accounts_df, pd.DataFrame):
                pdf.add_table(accounts_df)
        
        # Allocation chart
        if self.config.get('include_allocation_chart') and 'asset_allocation_chart' in data:
            pdf.add_chart(
                data['asset_allocation_chart'],
                title="Account Type Allocation",
                width=5,
                height=4
            )
        
        logger.debug("Rendered account breakdown")


class MarketForecastLongTermRenderer(SectionRenderer):
    """Render long-term market forecast."""
    
    def render(self, pdf: PDFGenerator, data: Dict[str, Any]):
        """Render long-term market forecast section."""
        pdf.add_section(self.title, "", level=1)
        
        # Outlook
        pdf.add_section("Long-term market outlook (5-10 years)", "", level=2)
        pdf.add_section("", "The long-term economic outlook remains constructive, supported by:", level=3)
        pdf.add_bullet_list([
            "Continued technological innovation and productivity gains",
            "Demographic trends favoring growth in key markets",
            "Central bank policies supporting economic stability",
            "Structural shifts in global trade and supply chains"
        ])
        
        # Expected Returns
        pdf.add_section("Expected Returns (Annualized)", "", level=2)
        pdf.add_bullet_list([
            "U.S. Large Cap Equities: 7-9%",
            "U.S. Small Cap Equities: 8-10%",
            "International Developed: 6-8%",
            "Emerging Markets: 8-11%",
            "Investment Grade Bonds: 3-5%",
            "High Yield Bonds: 5-7%"
        ])
        
        # Key Risks
        pdf.add_section("Key Risks", "", level=2)
        pdf.add_bullet_list([
            "Geopolitical tensions and policy uncertainty",
            "Inflation persistence above target levels",
            "Potential for economic slowdown or recession",
            "Market valuation concerns in certain sectors"
        ])
        
        # Add market indicators if available
        if 'market_indicators' in data:
            pdf.add_section("Market Indicators", "", level=2)
            indicators = data['market_indicators']
            if isinstance(indicators, pd.DataFrame):
                pdf.add_table(indicators, title="Key Economic Indicators")
        
        logger.debug("Rendered long-term market forecast")


class MarketForecastIntermediateRenderer(SectionRenderer):
    """Render intermediate-term market forecast."""
    
    def render(self, pdf: PDFGenerator, data: Dict[str, Any]):
        """Render intermediate-term market forecast section."""
        pdf.add_section(self.title, "", level=1)
        
        # Outlook
        pdf.add_section("Intermediate-term market outlook (6-18 months)", "", level=2)
        pdf.add_section("", "Near-term market conditions suggest:", level=3)
        pdf.add_bullet_list([
            "Moderate economic growth with potential headwinds",
            "Continued volatility as markets digest policy changes",
            "Sector rotation opportunities as economic cycle evolves",
            "Interest rate environment stabilizing at higher levels"
        ])
        
        # Technical Indicators
        pdf.add_section("Technical Indicators", "", level=2)
        pdf.add_bullet_list([
            "Market breadth showing mixed signals",
            "Momentum indicators suggest consolidation phase",
            "Volatility levels elevated but declining from peaks",
            "Sentiment indicators showing cautious optimism"
        ])
        
        # Recommended Positioning
        pdf.add_section("Recommended Positioning", "", level=2)
        pdf.add_bullet_list([
            "Maintain diversified exposure across asset classes",
            "Consider defensive sectors for stability",
            "Opportunistic additions in quality growth names",
            "Monitor fixed income duration given rate environment"
        ])
        
        logger.debug("Rendered intermediate-term market forecast")


class MarketStressIndicatorRenderer(SectionRenderer):
    """Render market stress indicators."""
    
    def render(self, pdf: PDFGenerator, data: Dict[str, Any]):
        """Render market stress indicators section."""
        pdf.add_section(self.title, "", level=1)
        
        # Stress level
        if 'market_stress' in data:
            stress_data = data['market_stress']
            stress_level = stress_data.get('level', 'Unknown')
            
            pdf.add_section("Current Stress Level", "", level=2)
            pdf.add_section("", f"Market Stress Level: {stress_level}", level=3)
            
            interpretation = {
                'Low': 'Markets are operating normally with low volatility.',
                'Moderate': 'Some elevated volatility but within normal ranges.',
                'Elevated': 'Increased market stress requiring attention.',
                'High': 'Significant market stress - consider defensive positioning.'
            }
            
            if stress_level in interpretation:
                pdf.add_section("", interpretation[stress_level], level=3)
        
        # Volatility metrics
        pdf.add_section("Understanding Stress Indicators", "", level=2)
        pdf.add_section("", "Key Stress Indicators:", level=3)
        pdf.add_bullet_list([
            "VIX (Volatility Index): Measures expected market volatility",
            "Credit Spreads: Indicates credit market stress",
            "Correlation: Shows asset class relationships",
            "Liquidity Metrics: Measures market depth and efficiency"
        ])
        
        pdf.add_section("", "These indicators help assess overall market health and potential risks to portfolio performance.", level=3)
        
        logger.debug("Rendered market stress indicators")


class PerformanceAttributionRenderer(SectionRenderer):
    """Render performance attribution analysis."""
    
    def render(self, pdf: PDFGenerator, data: Dict[str, Any]):
        """Render performance attribution section."""
        pdf.add_section(self.title, "", level=1)
        
        # Returns by account
        if self.config.get('include_returns_by_account') and 'performance' in data:
            pdf.add_section("Returns by Account", "", level=2)
            
            perf_data = data['performance']
            if isinstance(perf_data, pd.DataFrame):
                pdf.add_table(perf_data, title="Account Performance")
        
        # Contribution analysis
        if self.config.get('include_contribution_analysis'):
            pdf.add_section("Contribution Analysis", "", level=2)
            
            pdf.add_section("", "Performance contribution shows which accounts and asset classes contributed most to overall portfolio returns.", level=3)
            pdf.add_section("", "This analysis helps identify:", level=3)
            pdf.add_bullet_list([
                "Top performing accounts",
                "Asset classes driving returns",
                "Areas needing attention",
                "Rebalancing opportunities"
            ])
        
        logger.debug("Rendered performance attribution")



class IntroductionRenderer(SectionRenderer):
    """Render professional introduction section for comprehensive financial plan."""
    
    def render(self, pdf: PDFGenerator, data: Dict[str, Any]):
        """Render introduction section with client profile and planning context."""
        from config import get_config_manager
        import datetime
        
        pdf.add_section(self.title, "", level=1)
        
        config = get_config_manager()
        
        # Client Profile
        if self.config.get('include_client_profile'):
            pdf.add_section("Client Profile", "", level=2)
            
            # Get client information
            p1_name = config.get("personal_info", "person1_name", "Client")
            p2_name = config.get("personal_info", "person2_name", "")
            is_single = config.get("personal_info", "is_single_person", False)
            
            p1_birth_year = config.get("social_security", "person1_birth_year", 1966)
            p2_birth_year = config.get("social_security", "person2_birth_year", 1967)
            current_year = datetime.date.today().year
            p1_age = current_year - p1_birth_year
            p2_age = current_year - p2_birth_year
            
            retirement_state = config.get("personal_info", "retirement_state", "")
            
            # Build profile text
            if is_single:
                profile_text = f"This comprehensive financial plan has been prepared for {p1_name}, age {p1_age}"
            else:
                profile_text = f"This comprehensive financial plan has been prepared for {p1_name} (age {p1_age}) and {p2_name} (age {p2_age})"
            
            if retirement_state:
                profile_text += f", residing in {retirement_state}"
            
            profile_text += "."
            
            pdf.add_section("", profile_text, level=3)
        
        # Life Stage Context
        if self.config.get('include_life_stage'):
            pdf.add_section("Current Life Stage", "", level=2)
            
            # Get life stage from strategy data if available
            stage_text = "Your current life stage will guide the strategies and recommendations in this plan."
            
            try:
                # Check if we have life stages data from report builder
                if 'life_stages' in data and data['life_stages']:
                    stages_data = data['life_stages']
                    if isinstance(stages_data, dict) and 'current_stage' in stages_data:
                        current_stage = stages_data['current_stage']
                        stage_desc = stages_data.get('description', '')
                        stage_text = f"You are currently in {current_stage}. {stage_desc}"
                
            except Exception as e:
                logger.warning(f"Could not determine life stage: {e}")
            
            pdf.add_section("", stage_text, level=3)
        
        # Planning Objectives
        if self.config.get('include_planning_objectives'):
            pdf.add_section("Planning Objectives", "", level=2)
            
            objectives_intro = "This comprehensive financial plan is designed to help you achieve your retirement goals through:"
            pdf.add_section("", objectives_intro, level=3)
            
            objectives_bullets = [
                "Optimizing your investment strategy and asset allocation",
                "Maximizing tax efficiency through strategic Roth conversions and tax-loss harvesting",
                "Ensuring adequate income throughout retirement",
                "Managing healthcare costs and Medicare planning",
                "Preserving wealth for legacy and charitable giving",
                "Adapting to changing market conditions and life circumstances"
            ]
            pdf.add_bullet_list(objectives_bullets)
        
        # Scope of Plan
        if self.config.get('include_scope'):
            pdf.add_section("Scope of This Plan", "", level=2)
            
            scope_intro = (
                "This financial plan provides a comprehensive analysis of your current financial position and "
                "projects your retirement readiness over a multi-decade time horizon. The plan includes:"
            )
            pdf.add_section("", scope_intro, level=3)
            
            scope_bullets = [
                "Current net worth statement and account analysis",
                "Retirement income strategy with life-stage specific recommendations",
                "Tax planning analysis including Roth conversion opportunities",
                "Portfolio analysis with performance attribution and rebalancing guidance",
                "Monte Carlo simulation results showing probability of success",
                "Detailed assumptions and methodology"
            ]
            pdf.add_bullet_list(scope_bullets)
            
            scope_disclaimer = (
                "This plan is based on the information you have provided and current tax laws. It should be "
                "reviewed and updated regularly as your circumstances change or as tax laws are modified."
            )
            pdf.add_section("", scope_disclaimer, level=3)
        
        logger.debug("Rendered introduction section")


# Renderer registry
SECTION_RENDERERS = {
    'title_page': TitlePageRenderer,
    'introduction': IntroductionRenderer,
    'executive_summary': ExecutiveSummaryRenderer,
    'current_position': CurrentPositionRenderer,
    'retirement_strategy': RetirementStrategyRenderer,
    'tax_analysis': TaxAnalysisRenderer,
    'portfolio_analysis': PortfolioAnalysisRenderer,
    'monte_carlo': MonteCarloRenderer,
    'assumptions': AssumptionsRenderer,
    'appendices': AppendicesRenderer,
    # Tax planning template sections (use TaxAnalysisRenderer for all)
    'current_tax_situation': TaxAnalysisRenderer,
    'roth_conversion_analysis': TaxAnalysisRenderer,
    'tax_harvesting': TaxAnalysisRenderer,
    'charitable_giving': TaxAnalysisRenderer,
    'multi_year_projections': TaxAnalysisRenderer,
    # Portfolio review template sections (use PortfolioAnalysisRenderer)
    'portfolio_summary': PortfolioAnalysisRenderer,
    'holdings_detail': PortfolioAnalysisRenderer,
    'performance_analysis': PortfolioAnalysisRenderer,
    'factor_analysis': PortfolioAnalysisRenderer,
    'rebalancing': PortfolioAnalysisRenderer,
    'risk_assessment': PortfolioAnalysisRenderer,
    # Monte Carlo template sections (use MonteCarloRenderer)
    'simulation_overview': MonteCarloRenderer,
    'probability_analysis': MonteCarloRenderer,
    'scenario_comparison': MonteCarloRenderer,
    'stress_testing': MonteCarloRenderer,
    'sensitivity_analysis': MonteCarloRenderer,
    'recommendations': ExecutiveSummaryRenderer,
    # Net worth report template sections
    'net_worth_statement': NetWorthStatementRenderer,
    'net_worth_trends': NetWorthTrendsRenderer,
    'account_breakdown': AccountBreakdownRenderer,
    'asset_allocation': PortfolioAnalysisRenderer,
    'market_forecast_longterm': MarketForecastLongTermRenderer,
    'market_forecast_intermediate': MarketForecastIntermediateRenderer,
    'market_stress_indicator': MarketStressIndicatorRenderer,
    'performance_attribution': PerformanceAttributionRenderer,
}


def get_renderer(section_config: Dict[str, Any]) -> Optional[SectionRenderer]:
    """
    Get appropriate renderer for a section.
    
    Args:
        section_config: Section configuration from template
        
    Returns:
        SectionRenderer instance or None if not found
    """
    section_id = section_config.get('section_id')
    if not section_id:
        logger.warning("Section config missing section_id")
        return None
    
    renderer_class = SECTION_RENDERERS.get(section_id)
    
    if renderer_class:
        return renderer_class(section_config)
    
    logger.warning(f"No renderer found for section: {section_id}")
    return None


# Made with Bob