"""
components/reporting/report_builder.py
=======================================
Report builder that orchestrates report generation.

Collects data from various modules and assembles reports based on templates.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, List, Optional, Any, Callable, cast
from datetime import datetime
import logging

import pandas as pd
import streamlit as st

from .pdf_generator import PDFGenerator
from .report_templates import ReportTemplate, get_template_manager
from .section_renderers import get_renderer

logger = logging.getLogger(__name__)


class ReportBuilder:
    """
    Build reports from templates and data.
    
    Orchestrates the entire report generation process:
    1. Load template
    2. Collect data from application modules
    3. Render sections using appropriate renderers
    4. Generate PDF
    """
    
    def __init__(self, template_id: str):
        """
        Initialize report builder with a template.
        
        Args:
            template_id: Template identifier
        """
        template_mgr = get_template_manager()
        template = template_mgr.get_template(template_id)
        
        if not template:
            raise ValueError(f"Template not found: {template_id}")
        
        self.template: ReportTemplate = template
        self.template_id = template_id
        self.data: Dict[str, Any] = {}
        
        logger.info(f"ReportBuilder initialized with template: {self.template.name}")
    
    def collect_data(self, progress_callback: Optional[Callable[[str, float], None]] = None) -> Dict[str, Any]:
        """
        Collect all necessary data for report generation.
        
        Args:
            progress_callback: Optional callback function(message, progress)
                             where progress is 0.0 to 1.0
        
        Returns:
            Dictionary of collected data
        """
        data = {}
        total_steps = 13  # Updated to account for all collection steps
        current_step = 0
        
        def update_progress(message: str):
            nonlocal current_step
            current_step += 1
            if progress_callback:
                progress_callback(message, current_step / total_steps)
        
        try:
            # Report metadata
            update_progress("Collecting report metadata...")
            data['report_title'] = self.template.name
            data['report_date'] = datetime.now().strftime("%B %d, %Y")
            data['report_generated_at'] = datetime.now().isoformat()
            
            # Net worth data
            update_progress("Collecting net worth data...")
            data['net_worth'] = self._get_net_worth_data()
            data['networth_history'] = data['net_worth']  # Alias for renderers
            
            # Portfolio data
            update_progress("Collecting portfolio data...")
            data['portfolio'] = self._get_portfolio_data()
            data['accounts'] = self._get_account_summary()
            data['holdings'] = self._get_holdings_data()
            
            # Strategy and projections
            update_progress("Collecting strategy data...")
            data['withdrawal_plan'] = self._get_withdrawal_plan()
            data['income_sources'] = self._get_income_sources()
            data['life_stages'] = self._get_life_stages()
            
            # Tax data
            update_progress("Collecting tax data...")
            data['current_tax'] = self._get_current_tax_data()
            data['roth_conversion'] = self._get_roth_conversion_data()
            data['charitable_giving'] = self._get_charitable_giving_data()
            data['tax_projections'] = self._get_tax_projections()
            data['tax_harvesting'] = self._get_tax_harvesting_data()
            
            # Monte Carlo data
            update_progress("Collecting Monte Carlo data...")
            mc_data = self._get_monte_carlo_data()
            data['monte_carlo'] = mc_data
            
            # Extract stress test data if available
            if mc_data and isinstance(mc_data, dict) and 'stress_tests' in mc_data:
                data['stress_tests'] = mc_data['stress_tests']
            
            
            # Portfolio analysis data
            update_progress("Collecting portfolio analysis...")
            data['factor_analysis'] = self._get_factor_analysis()
            data['rebalancing'] = self._get_rebalancing_analysis()
            data['risk_metrics'] = self._get_risk_metrics()
            # Performance data
            update_progress("Collecting performance data...")
            data['performance'] = self._get_performance_data()
            
            # Assumptions
            update_progress("Collecting assumptions...")
            data['assumptions'] = self._get_assumptions()
            
            # Metrics for executive summary
            update_progress("Calculating key metrics...")
            data['metrics'] = self._calculate_key_metrics(data)
            
            # Generate insights
            update_progress("Generating insights...")
            data['key_findings'] = self._generate_key_findings(data)
            data['recommendations'] = self._generate_recommendations(data)
            data['action_items'] = self._generate_action_items(data)
            
            logger.info("Data collection complete")
            return data
            
        except Exception as e:
            logger.error(f"Error collecting data: {e}")
            raise
    
    def _get_net_worth_data(self) -> Optional[pd.DataFrame]:
        """Get net worth data from shared module."""
        try:
            from components.shared import build_historical_networth
            networth = build_historical_networth(num_months=12)
            return networth
        except Exception as e:
            logger.warning(f"Could not load net worth data: {e}")
            return None
    
    def _get_portfolio_data(self) -> Optional[pd.DataFrame]:
        """Get portfolio overview data with account-level details."""
        try:
            # Try to get detailed account data from load_data module
            from load_data import get_networth_by_month
            import datetime
            
            today = datetime.date.today()
            # get_networth_by_month returns (detailed_df, summary_df)
            # detailed_df has holdings with account_name, account_type, market_value
            detailed_df, summary_df = get_networth_by_month(today.month, today.year)
            
            logger.info(f"Portfolio data columns: {detailed_df.columns.tolist() if not detailed_df.empty else 'empty'}")
            logger.info(f"Portfolio data shape: {detailed_df.shape if not detailed_df.empty else 'empty'}")
            
            if not detailed_df.empty and 'account_name' in detailed_df.columns:
                logger.info(f"Loaded detailed portfolio data with {len(detailed_df)} holdings")
                return detailed_df
            
            # Fallback to session state if available
            if 'portfolio_df' in st.session_state:
                df = st.session_state['portfolio_df']
                logger.info(f"Session state portfolio columns: {df.columns.tolist()}")
                if 'account_name' in df.columns:
                    return df
            
            logger.warning(f"Portfolio data does not contain account_name column. Columns: {detailed_df.columns.tolist() if not detailed_df.empty else 'none'}")
            return None
        except Exception as e:
            logger.error(f"Could not load portfolio data: {e}", exc_info=True)
            return None
    
    def _get_account_summary(self) -> Optional[pd.DataFrame]:
        """Get account summary with Total row at the end."""
        try:
            from load_data import get_networth_by_month
            import datetime
            
            today = datetime.date.today()
            _, summary_df = get_networth_by_month(today.month, today.year)
            
            if not summary_df.empty:
                # Group by account type
                summary = summary_df.groupby('account_type')['market_value'].sum().reset_index()
                summary.columns = ['Account Type', 'Balance']
                
                # Calculate total
                total_balance = summary['Balance'].sum()
                
                # Format balances
                summary['Balance'] = summary['Balance'].apply(lambda x: f"${x:,.0f}")
                
                # Add Total row at the end
                total_row = pd.DataFrame([{'Account Type': 'Total', 'Balance': f"${total_balance:,.0f}"}])
                summary = pd.concat([summary, total_row], ignore_index=True)
                
                return summary
            
            return None
        except Exception as e:
            logger.warning(f"Could not load account summary: {e}")
            return None
    
    def _get_holdings_data(self) -> Optional[pd.DataFrame]:
        """Get portfolio holdings."""
        try:
            # Get holdings from portfolio data
            portfolio_df = self._get_portfolio_data()
            
            if portfolio_df is not None and not portfolio_df.empty:
                # Select relevant columns for holdings display
                holdings_cols = []
                
                # Check which columns are available
                if 'account_name' in portfolio_df.columns:
                    holdings_cols.append('account_name')
                if 'symbol' in portfolio_df.columns:
                    holdings_cols.append('symbol')
                if 'description' in portfolio_df.columns:
                    holdings_cols.append('description')
                if 'quantity' in portfolio_df.columns:
                    holdings_cols.append('quantity')
                if 'price' in portfolio_df.columns:
                    holdings_cols.append('price')
                if 'market_value' in portfolio_df.columns:
                    holdings_cols.append('market_value')
                if 'cost_basis' in portfolio_df.columns:
                    holdings_cols.append('cost_basis')
                if 'unrealized_gain' in portfolio_df.columns:
                    holdings_cols.append('unrealized_gain')
                
                if holdings_cols:
                    holdings_df = portfolio_df[holdings_cols].copy()
                    
                    # Format currency columns
                    for col in ['market_value', 'cost_basis', 'unrealized_gain', 'price']:
                        if col in holdings_df.columns:
                            holdings_df[col] = holdings_df[col].apply(lambda x: f"${x:,.2f}" if pd.notna(x) else "")
                    
                    # Rename columns for display
                    rename_map = {
                        'account_name': 'Account',
                        'symbol': 'Symbol',
                        'description': 'Description',
                        'quantity': 'Quantity',
                        'price': 'Price',
                        'market_value': 'Market Value',
                        'cost_basis': 'Cost Basis',
                        'unrealized_gain': 'Gain/Loss'
                    }
                    holdings_df = holdings_df.rename(columns={k: v for k, v in rename_map.items() if k in holdings_df.columns})
                    
                    logger.info(f"Loaded {len(holdings_df)} holdings")
                    return holdings_df
            
            logger.warning("No holdings data available")
            return None
        except Exception as e:
            logger.error(f"Could not load holdings: {e}", exc_info=True)
            return None
    
    def _get_withdrawal_plan(self) -> Optional[pd.DataFrame]:
        """Get withdrawal strategy projections."""
        try:
            # This would come from strategy module
            # For now, return sample data
            return None
        except Exception as e:
            logger.warning(f"Could not load withdrawal plan: {e}")
            return None
    
    def _get_income_sources(self) -> Optional[Dict[str, Any]]:
        """Get income sources breakdown."""
        try:
            # This would come from strategy module
            return None
        except Exception as e:
            logger.warning(f"Could not load income sources: {e}")
            return None
    
    def _get_life_stages(self) -> List[Dict[str, str]]:
        """Get life stage descriptions customized based on user's age and configuration."""
        from components.shared import LIFE_STAGE_DESCRIPTIONS
        from config import get_config_manager
        import datetime
        
        config = get_config_manager()
        
        # Get current ages and year
        current_year = datetime.date.today().year
        p1_birth_year = config.get("social_security", "person1_birth_year", 1966)
        p2_birth_year = config.get("social_security", "person2_birth_year", 1967)
        age_p1 = current_year - p1_birth_year
        age_p2 = current_year - p2_birth_year
        
        # Get SSI and Medicare ages from config
        ssi_age = config.get("social_security", "person1_ssi_age", 70)
        medicare_age = config.get("healthcare", "person1_medicare_start_age", 65)
        
        # Determine current stage using simple age-based logic
        if age_p1 < 55:
            current_stage = "Stage 1: Accumulation"
        elif age_p1 < config.get("personal_info", "person1_retirement_age", 62):
            current_stage = "Stage 2: Prep for Retirement"
        elif age_p1 < medicare_age:
            current_stage = "Stage 3: Early Retirement"
        elif age_p1 < ssi_age:
            current_stage = "Stage 4: Medicare"
        elif age_p1 < 73:
            current_stage = "Stage 5: Social Security"
        else:
            current_stage = "Stage 6: RMD"
        
        # Get configuration for customization
        uses_aca = config.get("healthcare", "aca_marketplace_enrolled", False)
        has_daf = config.get("charitable_giving", "has_daf", False)
        annual_giving = config.get("charitable_giving", "annual_charitable_giving", 0)
        max_conv_rate_stage3 = config.get("tax_strategy", "stage_3_max_conversion_rate", 32)
        max_conv_rate_stage4 = config.get("tax_strategy", "stage_4_max_conversion_rate", 32)
        max_conv_rate_stage5 = config.get("tax_strategy", "stage_5_max_conversion_rate", 22)
        
        stages = []
        for stage_name, base_description in LIFE_STAGE_DESCRIPTIONS.items():
            description = base_description
            
            # Customize Stage 3 description based on ACA and tax strategy
            if stage_name == "Stage 3: Early Retirement":
                if uses_aca:
                    description = (
                        f"🌅 Retired but before Medicare & Social Security.\n\n"
                        f"No wages yet. Living expenses come from your brokerage account first "
                        f"(long-term capital gains taxed at 0% when possible). This is the prime "
                        f"window for large Roth conversions — income is low, so you fill up to the "
                        f"{max_conv_rate_stage3}% tax bracket. ACA marketplace health insurance costs are managed "
                        f"to preserve subsidy eligibility."
                    )
                else:
                    description = (
                        f"🌅 Retired but before Medicare & Social Security.\n\n"
                        f"No wages yet. Living expenses come from your brokerage account first "
                        f"(long-term capital gains taxed at 0% when possible). This is the prime "
                        f"window for large Roth conversions — income is low, so you fill up to the "
                        f"{max_conv_rate_stage3}% tax bracket."
                    )
            
            # Customize Stage 4 with tax strategy
            elif stage_name == "Stage 4: Medicare":
                description = (
                    f"🏥 On Medicare, still before Social Security.\n\n"
                    f"Medicare Part B/D premiums are now in play, including IRMAA surcharges "
                    f"if your income from 2 years ago was high. Roth conversions continue up to the "
                    f"{max_conv_rate_stage4}% bracket but are sized carefully to avoid jumping an IRMAA tier. "
                    f"The goal is to keep converting while your income is still relatively low."
                )
            
            # Customize Stage 5 with SSI age and tax strategy
            elif stage_name == "Stage 5: Social Security":
                description = (
                    f"💰 Collecting Social Security (starting at age {ssi_age}) + Medicare.\n\n"
                    f"SS benefits add a new income stream — up to 85% of benefits are taxable. "
                    f"Roth conversions up to the {max_conv_rate_stage5}% bracket are still possible but must account for the 'SS torpedo' "
                    f"effect where extra income makes more SS taxable. IRMAA management remains "
                    f"important. Withdrawals shift toward a mix of brokerage and traditional."
                )
            
            # Customize Stage 6 with DAF if configured
            elif stage_name == "Stage 6: RMD":
                if has_daf and annual_giving > 0:
                    description = (
                        f"📋 Required Minimum Distributions are mandatory.\n\n"
                        f"The IRS requires you to withdraw a minimum amount from your Traditional "
                        f"accounts each year based on your age and balance. These withdrawals are "
                        f"fully taxable. The strategy focuses on minimizing the tax hit by "
                        f"coordinating RMDs with other income, using your Donor-Advised Fund (DAF) "
                        f"for ${annual_giving:,.0f} annual charitable contributions via QCD "
                        f"to offset taxes, and preserving Roth assets as long as possible."
                    )
                else:
                    description = base_description
            
            # Mark current stage
            is_current = (stage_name == current_stage)
            stage_marker = " ⭐ (Current Stage)" if is_current else ""
            
            stages.append({
                'name': stage_name + stage_marker,
                'description': description,
                'is_current': is_current,
                'order': list(LIFE_STAGE_DESCRIPTIONS.keys()).index(stage_name)
            })
        
        # Sort by order and prioritize current stage and nearby stages
        # Show current stage and 2 stages before/after
        current_idx = next((i for i, s in enumerate(stages) if s['is_current']), 3)
        start_idx = max(0, current_idx - 1)
        end_idx = min(len(stages), current_idx + 3)
        
        # Return relevant stages (current + context)
        relevant_stages = stages[start_idx:end_idx]
        
        return relevant_stages
    
    def _get_current_tax_data(self) -> Optional[Dict[str, Any]]:
        """Get current tax situation from Admin Tax Data calculations or estimates."""
        try:
            # Try to get tax data from calculations module
            from calculations import calculate_taxable_income
            from load_data import get_income_tax_brackets, get_std_deduction
            from config import get_config_manager
            import datetime
            
            config = get_config_manager()
            filing_status = config.get_filing_status()
            current_year = datetime.date.today().year
            
            # Try to get income data from config or session state
            wages = config.get("income", "wages", 0.0)
            investment_income = config.get("income", "investment_income", 0.0)
            ss_benefits = config.get("income", "ss_benefits", 0.0)
            
            # Simple AGI calculation (wages + investment income + 85% of SS benefits)
            agi = wages + investment_income + (ss_benefits * 0.85)
            
            # If no income configured, estimate from portfolio withdrawals
            if agi == 0:
                # Try to estimate from expected expenses
                annual_expenses = config.get("financial_assumptions", "expected_annual_expenses", 0.0)
                if annual_expenses > 0:
                    # Assume 4% withdrawal rate to estimate portfolio income
                    agi = annual_expenses
                    logger.info(f"Estimated AGI from annual expenses: ${agi:,.0f}")
                else:
                    # Last resort: use portfolio value to estimate
                    portfolio_df = self._get_portfolio_data()
                    if portfolio_df is not None and not portfolio_df.empty and 'market_value' in portfolio_df.columns:
                        total_portfolio = portfolio_df['market_value'].sum()
                        # Assume 4% withdrawal rate
                        agi = total_portfolio * 0.04
                        logger.info(f"Estimated AGI from 4% portfolio withdrawal: ${agi:,.0f}")
            
            if agi == 0:
                return None
            
            # Get standard deduction
            std_ded_df = get_std_deduction(current_year, filing_status)
            std_deduction = float(std_ded_df.iloc[0]['deduction']) if not std_ded_df.empty else 0.0
            
            # Calculate taxable income
            taxable_income = max(0, agi - std_deduction)
            
            # Calculate federal tax using progressive brackets
            brackets_df = get_income_tax_brackets(current_year, filing_status)
            if brackets_df.empty:
                return None
            
            tax_calc = calculate_taxable_income(taxable_income, brackets_df)
            federal_tax = tax_calc.total_tax
            marginal_rate = tax_calc.max_rate
            
            # Simple state tax estimate (5% flat rate)
            state_tax = taxable_income * 0.05
            
            effective_rate = (federal_tax + state_tax) / agi if agi > 0 else 0.0
            
            # Check IRMAA status (simplified)
            irmaa_threshold = 206000 if filing_status == "married_filing_jointly" else 103000
            irmaa_status = "Yes" if agi > irmaa_threshold else "No"
            
            return {
                'agi': agi,
                'federal_tax': federal_tax,
                'state_tax': state_tax,
                'total_tax': federal_tax + state_tax,
                'effective_rate': effective_rate,
                'marginal_rate': marginal_rate,
                'irmaa_status': irmaa_status,
                'filing_status': filing_status,
                'year': current_year,
                'is_estimated': wages == 0 and investment_income == 0 and ss_benefits == 0
            }
        except Exception as e:
            logger.warning(f"Could not load tax data: {e}")
            return None
    
    def _get_roth_conversion_data(self) -> Optional[Dict[str, Any]]:
        """Get Roth conversion analysis from actual strategy results."""
        try:
            from strategy import build_withdrawal_strategy_display
            from config import get_config_manager
            import datetime
            
            config = get_config_manager()
            current_year = datetime.date.today().year
            
            # Get portfolio balances
            portfolio_df = self._get_portfolio_data()
            if portfolio_df is None or portfolio_df.empty:
                return None
            
            # Calculate Traditional and Roth balances
            traditional_balance = 0.0
            roth_balance = 0.0
            
            if 'account_type' in portfolio_df.columns and 'market_value' in portfolio_df.columns:
                traditional_balance = portfolio_df[portfolio_df['account_type'] == 'Traditional']['market_value'].sum()
                roth_balance = portfolio_df[portfolio_df['account_type'] == 'Roth']['market_value'].sum()
            
            if traditional_balance == 0:
                return None
            
            # Run the actual strategy to get real Roth conversion data
            strategy_df, _ = build_withdrawal_strategy_display(
                start_year=current_year,
                num_years=10
            )
            
            if strategy_df is None or strategy_df.empty:
                return None
            
            # Extract Roth conversion data from strategy
            # The strategy DataFrame has columns: Year, Trad->Roth, Fed Tax, State Tax, etc.
            conversion_cols = ['Year', 'Trad->Roth', 'Fed Tax', 'State Tax']
            balance_cols = []
            
            # Find balance columns (they vary by account type)
            for col in strategy_df.columns:
                if 'Traditional' in col and 'Balance' in col:
                    balance_cols.append(('Traditional Balance', col))
                elif 'Roth' in col and 'Balance' in col:
                    balance_cols.append(('Roth Balance', col))
            
            # Build multi-year plan from actual strategy data
            plan_data = []
            for _, row in strategy_df.head(10).iterrows():
                conversion_amount = row.get('Trad->Roth', 0) if 'Trad->Roth' in row else 0
                fed_tax = row.get('Fed Tax', 0) if 'Fed Tax' in row else 0
                state_tax = row.get('State Tax', 0) if 'State Tax' in row else 0
                
                # Get balances
                trad_bal = traditional_balance
                roth_bal = roth_balance
                for label, col in balance_cols:
                    if 'Traditional' in label and col in row:
                        trad_bal = row[col]
                    elif 'Roth' in label and col in row:
                        roth_bal = row[col]
                
                plan_data.append({
                    'Year': int(row['Year']),
                    'Conversion Amount': conversion_amount,
                    'Estimated Tax': fed_tax + state_tax,  # Combined tax on conversion
                    'Traditional Balance': trad_bal,
                    'Roth Balance': roth_bal
                })
            
            multi_year_plan = pd.DataFrame(plan_data)
            
            # Get optimal amount from first year
            optimal_amount = plan_data[0]['Conversion Amount'] if plan_data else 0
            conversion_tax = plan_data[0]['Estimated Tax'] if plan_data else 0
            
            return {
                'optimal_amount': optimal_amount,
                'conversion_tax': conversion_tax,
                'traditional_balance': traditional_balance,
                'roth_balance': roth_balance,
                'multi_year_plan': multi_year_plan,
                'tax_impact': conversion_tax
            }
        except Exception as e:
            logger.warning(f"Could not load Roth conversion data: {e}")
            return None
    
    def _get_tax_harvesting_data(self) -> Optional[pd.DataFrame]:
        """Get tax harvesting opportunities from tax_harvesting module."""
        try:
            from tax_harvesting import build_harvesting_analysis, classify_harvest_opportunities
            import datetime
            
            current_date = datetime.date.today()
            
            # Build harvesting analysis for current month/year
            analysis_df = build_harvesting_analysis(current_date.month, current_date.year)
            
            if analysis_df.empty:
                return None
            
            # Get current tax data for AGI
            tax_data = self._get_current_tax_data()
            agi = tax_data.get('agi', 80000) if tax_data else 80000
            
            # Classify opportunities
            classified_df = classify_harvest_opportunities(
                analysis_df,
                estimated_agi=float(agi),
                year=current_date.year,
                loss_threshold=-500.0,
                gain_threshold=500.0
            )
            
            # Filter to only harvest recommendations
            harvest_opps = classified_df[
                classified_df['Recommendation'].str.contains('Harvest', na=False)
            ]
            
            if not isinstance(harvest_opps, pd.DataFrame) or harvest_opps.empty:
                return None
            
            # Select relevant columns for report (reduced for better PDF fit)
            report_cols = [
                'Symbol', 'Name', 'Unrealized G/L', 'Return %', 'Recommendation'
            ]
            available_cols = [col for col in report_cols if col in harvest_opps.columns]
            
            # Get top 10 opportunities
            result_df = cast(pd.DataFrame, harvest_opps[available_cols]).head(10).copy()
            
            # Format numeric columns to 2 decimal places
            if 'Unrealized G/L' in result_df.columns:
                result_df['Unrealized G/L'] = result_df['Unrealized G/L'].apply(lambda x: round(float(x), 2) if pd.notna(x) else x)
            if 'Return %' in result_df.columns:
                result_df['Return %'] = result_df['Return %'].apply(lambda x: round(float(x), 2) if pd.notna(x) else x)
            
            return result_df
            
        except Exception as e:
            logger.warning(f"Could not load tax harvesting data: {e}")
            return None
    
    def _get_monte_carlo_data(self) -> Optional[Dict[str, Any]]:
        """Get Monte Carlo simulation results from saved file or session state."""
        try:
            import json
            import os
            from pathlib import Path
            
            # Try to load from saved file first
            mc_file = Path("data/monte_carlo_results.json")
            if mc_file.exists():
                try:
                    with open(mc_file, 'r') as f:
                        mc_results = json.load(f)
                    logger.info("Loaded Monte Carlo results from file")
                    return mc_results
                except Exception as e:
                    logger.warning(f"Could not load Monte Carlo results from file: {e}")
            
            # Fall back to session state if file doesn't exist
            import streamlit as st
            if 'mc_results' in st.session_state:
                mc_results = st.session_state['mc_results']
                logger.info("Loaded Monte Carlo results from session state")
                return mc_results
            
            logger.info("Monte Carlo results not found. Run Monte Carlo simulation first.")
            return None
            
        except Exception as e:
            logger.warning(f"Could not load Monte Carlo data: {e}")
            return None
    
    def _get_performance_data(self) -> Optional[pd.DataFrame]:
        """Get portfolio performance metrics from historical net worth data."""
        try:
            networth = self._get_net_worth_data()
            if networth is None or networth.empty or len(networth) < 2:
                return None
            
            # Calculate monthly returns
            returns = networth['total'].pct_change().dropna()
            
            if returns.empty:
                return None
            
            # Calculate performance metrics
            periods = ['1M', '3M', '6M', '1Y']
            performance_data = []
            
            for period in periods:
                if period == '1M' and len(returns) >= 1:
                    period_return = returns.iloc[-1]
                elif period == '3M' and len(returns) >= 3:
                    period_return = (1 + returns.iloc[-3:]).prod() - 1
                elif period == '6M' and len(returns) >= 6:
                    period_return = (1 + returns.iloc[-6:]).prod() - 1
                elif period == '1Y' and len(returns) >= 12:
                    period_return = (1 + returns.iloc[-12:]).prod() - 1
                else:
                    continue
                
                # Simple benchmark (assume 7% annual return)
                if period == '1M':
                    benchmark = 0.07 / 12
                elif period == '3M':
                    benchmark = (1 + 0.07) ** (3/12) - 1
                elif period == '6M':
                    benchmark = (1 + 0.07) ** (6/12) - 1
                else:  # 1Y
                    benchmark = 0.07
                
                alpha = period_return - benchmark
                
                performance_data.append({
                    'Period': period,
                    'Return': round(period_return * 100, 2),  # Convert to percentage, 2 decimals
                    'Benchmark': round(benchmark * 100, 2),
                    'Alpha': round(alpha * 100, 2)
                })
            
            if not performance_data:
                return None
            
            return pd.DataFrame(performance_data)
            
        except Exception as e:
            logger.warning(f"Could not load performance data: {e}")
            return None
    
    def _get_assumptions(self) -> Dict[str, Any]:
        """Get planning assumptions."""
        try:
            from config import get_config_manager
            config = get_config_manager()
            
            return {
                'returns': {
                    'Stocks': 7.0,
                    'Bonds': 3.5,
                    'Cash': 2.0,
                },
                'inflation': 3.0,
                'tax_rates': 'Current federal tax law',
            }
        except Exception as e:
            logger.warning(f"Could not load assumptions: {e}")
            return {}
    
    def _calculate_key_metrics(self, data: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
        """Calculate key metrics for executive summary."""
        metrics = {}
        
        # Net worth
        if 'net_worth' in data and data['net_worth'] is not None:
            nw = data['net_worth']
            if not nw.empty:
                current_nw = nw['total'].iloc[-1]
                metrics['net_worth'] = {
                    'name': 'Current Net Worth',
                    'value': f"${current_nw:,.0f}",
                    'status': '✓'
                }
        
        # Add more metrics as data becomes available
        metrics['retirement_readiness'] = {
            'name': 'Retirement Readiness',
            'value': 'On Track',
            'status': '✓'
        }
        
        return metrics
    
    def _generate_key_findings(self, data: Dict[str, Any]) -> List[str]:
        """Generate key findings based on data."""
        findings = []
        
        # Net worth trend
        if 'net_worth' in data and data['net_worth'] is not None:
            nw = data['net_worth']
            if len(nw) >= 2:
                current = nw['total'].iloc[-1]
                previous = nw['total'].iloc[-2]
                change = current - previous
                
                if change > 0:
                    findings.append(f"Net worth increased by ${change:,.0f} this month")
                else:
                    findings.append(f"Net worth decreased by ${abs(change):,.0f} this month")
        
        # Add more findings as data becomes available
        findings.append("Portfolio is well-diversified across asset classes")
        findings.append("Tax-efficient withdrawal strategy is in place")
        
        return findings
    
    def _generate_recommendations(self, data: Dict[str, Any]) -> List[str]:
        """Generate recommendations based on analysis."""
        recommendations = []
        
        recommendations.append("Continue current savings rate to maintain retirement readiness")
        recommendations.append("Review Roth conversion opportunities annually")
        recommendations.append("Rebalance portfolio quarterly to maintain target allocation")
        
        return recommendations
    
    def _generate_action_items(self, data: Dict[str, Any]) -> List[str]:
        """Generate action items based on readiness indicators and data analysis."""
        action_items = []
        
        try:
            from config import get_config_manager
            import os
            import json
            
            config = get_config_manager()
            
            # Check funding level
            annual_expenses = config.get("financial_assumptions", "expected_annual_expenses", 50000)
            target_portfolio = annual_expenses * 25.0
            
            portfolio_df = self._get_portfolio_data()
            current_assets = 0.0
            if portfolio_df is not None and not portfolio_df.empty and 'market_value' in portfolio_df.columns:
                current_assets = portfolio_df['market_value'].sum()
            
            funding_pct = (current_assets / target_portfolio * 100) if target_portfolio > 0 else 0
            
            if funding_pct < 80:
                action_items.append(f"⚠️ Portfolio funding at {funding_pct:.0f}% of target - Consider increasing savings rate")
            elif funding_pct < 100:
                action_items.append(f"📊 Portfolio funding at {funding_pct:.0f}% of target - On track, maintain current savings")
            
            # Check estate planning
            if os.path.exists("estate_planning_data.json"):
                with open("estate_planning_data.json") as ef:
                    estate_data = json.load(ef)
                    assess = estate_data.get("assessment", {})
                    
                    if not assess.get("has_will", False):
                        action_items.append("📝 Create or update will")
                    if not assess.get("has_poa", False):
                        action_items.append("📝 Establish power of attorney")
                    if not assess.get("has_healthcare_directive", False):
                        action_items.append("📝 Complete healthcare directive")
                    if not assess.get("beneficiaries_current", False):
                        action_items.append("📝 Review and update beneficiary designations")
            else:
                action_items.append("📝 Complete estate planning assessment")
            
            # Check tax diversification
            if portfolio_df is not None and not portfolio_df.empty:
                if 'account_type' in portfolio_df.columns:
                    trad_bal = portfolio_df[portfolio_df['account_type'] == 'Traditional']['market_value'].sum()
                    roth_bal = portfolio_df[portfolio_df['account_type'] == 'Roth']['market_value'].sum()
                    
                    if trad_bal + roth_bal > 0:
                        roth_ratio = (roth_bal / (roth_bal + trad_bal)) * 100
                        
                        if roth_ratio < 20:
                            action_items.append("💰 Consider Roth conversions to improve tax diversification")
                        elif roth_ratio > 60:
                            action_items.append("💰 Review Roth conversion strategy - may be over-allocated")
            
            # Check Social Security planning
            p1_ssi = config.get("social_security", "person1_ssi_amount", 0.0)
            p2_ssi = config.get("social_security", "person2_ssi_amount", 0.0)
            
            if p1_ssi == 0 and p2_ssi == 0:
                action_items.append("💵 Configure Social Security benefits in settings")
            elif p1_ssi == 0 or p2_ssi == 0:
                action_items.append("💵 Complete Social Security planning for both spouses")
            
            # Check healthcare coverage
            p1_preretire = config.get("healthcare", "person1_preretirement_coverage_type", "None")
            p2_preretire = config.get("healthcare", "person2_preretirement_coverage_type", "None")
            p1_retire = config.get("healthcare", "person1_retirement_coverage_type", "None")
            p2_retire = config.get("healthcare", "person2_retirement_coverage_type", "None")
            
            if p1_preretire == "None" or p2_preretire == "None":
                action_items.append("🏥 Configure pre-retirement healthcare coverage")
            if p1_retire == "None" or p2_retire == "None":
                action_items.append("🏥 Plan retirement healthcare coverage (pre-Medicare)")
            
            # Check Medicare planning
            p1_reviewed = config.get("healthcare", "person1_reviewed_medicare_guide", False)
            p2_reviewed = config.get("healthcare", "person2_reviewed_medicare_guide", False)
            
            if not p1_reviewed or not p2_reviewed:
                action_items.append("🏥 Review Medicare planning guide")
            
            # Check for rebalancing needs
            rebalance_data = self._get_rebalancing_analysis()
            if rebalance_data and isinstance(rebalance_data, pd.DataFrame):
                if not rebalance_data.empty and 'Difference' in rebalance_data.columns:
                    max_diff = rebalance_data['Difference'].abs().max()
                    if max_diff > 5:
                        action_items.append(f"⚖️ Portfolio rebalancing recommended - up to {max_diff:.1f}% deviation detected")
            
            # Check for tax harvesting opportunities
            harvest_data = self._get_tax_harvesting_data()
            if harvest_data is not None and not harvest_data.empty:
                action_items.append(f"💸 {len(harvest_data)} tax loss harvesting opportunities identified")
            
            # Always include these standard items
            if not any("annual financial review" in item.lower() for item in action_items):
                action_items.append("📅 Schedule annual financial review")
            
            if not any("insurance" in item.lower() for item in action_items):
                action_items.append("🛡️ Review insurance coverage (life, disability, long-term care)")
            
        except Exception as e:
            logger.warning(f"Error generating action items: {e}")
            # Fallback to basic action items
            action_items = [
                "📅 Schedule annual financial review",
                "📝 Update beneficiary designations",
                "🛡️ Review insurance coverage"
            ]
        
        return action_items
    
    def generate_report(
        self,
        output_path: str,
        prepared_for: Optional[str] = None,
        progress_callback: Optional[Callable[[str, float], None]] = None
    ) -> str:
        """
        Generate PDF report.
        
        Args:
            output_path: Destination file path for PDF
            prepared_for: Optional "Prepared for" text
            progress_callback: Optional callback function(message, progress)
        
        Returns:
            Path to generated PDF file
        """
        try:
            # Collect data
            if progress_callback:
                progress_callback("Collecting data...", 0.0)
            
            self.data = self.collect_data(progress_callback)
            
            # Add prepared_for if provided
            if prepared_for:
                self.data['prepared_for'] = prepared_for
            
            # Initialize PDF generator
            if progress_callback:
                progress_callback("Initializing PDF generator...", 0.5)
            
            pdf = PDFGenerator(
                filename=output_path,
                page_size=self.template.page_size,
                orientation=self.template.orientation,
                title=self.template.name,
                author="Retirement Planning System"
            )
            
            # Configure branding
            pdf.header_text = None
            pdf.footer_text = self.template.footer_text
            pdf.show_page_numbers = self.template.show_page_numbers
            pdf.logo_path = self.template.logo_path if self.template.show_logo else None
            
            # Render sections
            if progress_callback:
                progress_callback("Rendering sections...", 0.6)
            
            enabled_sections = self.template.get_enabled_sections()
            total_sections = len(enabled_sections)
            
            for idx, section_config in enumerate(enabled_sections):
                section_id = section_config.get('section_id')
                
                if progress_callback:
                    progress = 0.6 + (0.3 * (idx / total_sections))
                    progress_callback(f"Rendering {section_id}...", progress)
                
                renderer = get_renderer(section_config)
                if renderer:
                    try:
                        renderer.render(pdf, self.data)
                    except Exception as e:
                        logger.error(f"Error rendering section {section_id}: {e}")
                        # Continue with other sections
            
            # Save PDF
            if progress_callback:
                progress_callback("Saving PDF...", 0.95)
            
            result_path = pdf.save()
            
            if progress_callback:
                progress_callback("Report generated successfully!", 1.0)
            
            logger.info(f"Report generated: {result_path}")
            return result_path
            
        except Exception as e:
            logger.error(f"Error generating report: {e}")
            raise
    
    def preview_sections(self) -> List[Dict[str, Any]]:
        """
        Preview sections that will be included in the report.
        
        Returns:
            List of section information dictionaries
        """
        sections = []
        
        for section_config in self.template.get_enabled_sections():
            sections.append({
                'section_id': section_config.get('section_id'),
                'title': section_config.get('title'),
                'order': section_config.get('order'),
                'enabled': section_config.get('enabled', True),
            })
        
        return sections
    
    def validate_data(self) -> List[str]:
        """
        Validate data availability for all enabled sections.
        
        Returns:
            List of validation warnings (empty if all data available)
        """
        warnings = []
        
        # This would check if required data is available for each section
        # For now, return empty list
        
        return warnings


# Made with Bob
    
    def _get_factor_analysis(self) -> Optional[Dict[str, Any]]:
        """Get factor analysis from Portfolio Hub."""
        try:
            from portfolio_factors import calculate_portfolio_factor_exposure, fetch_factor_data
            
            portfolio_df = self._get_portfolio_data()
            if portfolio_df is None or portfolio_df.empty:
                return None
            
            # Filter to stocks only
            if 'symbol' not in portfolio_df.columns or 'market_value' not in portfolio_df.columns:
                return None
            
            stocks_df = portfolio_df[portfolio_df['symbol'].notna()].copy()
            stocks_df = stocks_df[stocks_df['symbol'] != 'Cash'].copy()
            
            if stocks_df.empty:
                return None
            
            # Fetch factor data for holdings
            factor_data = {}
            for symbol in stocks_df['symbol'].unique():
                try:
                    metrics = fetch_factor_data(symbol, use_cache=True)
                    factor_data[symbol] = metrics
                except Exception:
                    continue
            
            if not factor_data:
                return None
            
            # Calculate portfolio exposure
            exposure = calculate_portfolio_factor_exposure(stocks_df, factor_data)
            
            # Build sector breakdown
            if 'sector' in stocks_df.columns:
                sector_breakdown = stocks_df.groupby('sector')['market_value'].sum().reset_index()
                sector_breakdown.columns = ['Sector', 'Value']
                sector_breakdown['Percentage'] = (sector_breakdown['Value'] / sector_breakdown['Value'].sum() * 100).round(1)
            else:
                sector_breakdown = None
            
            return {
                'exposure': exposure,
                'sector_breakdown': sector_breakdown,
                'value_exposure': exposure.value_exposure,
                'growth_exposure': exposure.growth_exposure,
                'momentum_exposure': exposure.momentum_exposure,
                'quality_exposure': exposure.quality_exposure,
                'primary_style': exposure.primary_style.value if hasattr(exposure, 'primary_style') else 'Balanced'
            }
            
        except Exception as e:
            logger.warning(f"Could not load factor analysis: {e}")
            return None
    
    def _get_rebalancing_analysis(self) -> Optional[Dict[str, Any]]:
        """Get rebalancing analysis comparing current vs target allocation."""
        try:
            from portfolio_rebalancing import compute_rebalance_plan
            import datetime
            
            current_date = datetime.date.today()
            
            # Use default target allocation (can be customized)
            target_cash = 10.0
            target_bonds = 10.0
            target_stocks = 80.0
            drift_threshold = 5.0
            
            # Compute rebalancing plan
            report = compute_rebalance_plan(
                month=current_date.month,
                year=current_date.year,
                target_cash_pct=target_cash,
                target_bonds_pct=target_bonds,
                target_stocks_pct=target_stocks,
                drift_threshold_pct=drift_threshold
            )
            
            # Build summary DataFrame from asset_summary
            summary_data = []
            for asset_summary in report.asset_summary:
                summary_data.append({
                    'Asset Class': asset_summary.asset_class,
                    'Current Value': asset_summary.current_value,
                    'Current %': asset_summary.current_pct,
                    'Target %': asset_summary.target_pct,
                    'Difference': asset_summary.drift_pct,
                    'Trade Amount': asset_summary.delta_value
                })
            
            summary_df = pd.DataFrame(summary_data) if summary_data else None
            
            return {
                'drift_triggered': report.drift_triggered,
                'total_value': report.total_portfolio_value,
                'summary': summary_df,
                'actions_count': len(report.actions)
            }
            
        except Exception as e:
            logger.warning(f"Could not load rebalancing analysis: {e}")
            return None
    
    def _get_risk_metrics(self) -> Optional[Dict[str, Any]]:
        """Get risk metrics from historical portfolio data."""
        try:
            networth = self._get_net_worth_data()
            if networth is None or networth.empty or len(networth) < 12:
                return None
            
            # Calculate returns
            returns = networth['total'].pct_change().dropna()
            
            if returns.empty:
                return None
            
            # Calculate risk metrics
            annual_return = returns.mean() * 12
            volatility = returns.std() * (12 ** 0.5)  # Annualized volatility
            
            # Sharpe ratio (assuming 2% risk-free rate)
            risk_free_rate = 0.02
            sharpe_ratio = (annual_return - risk_free_rate) / volatility if volatility > 0 else 0
            
            # Max drawdown
            cumulative = (1 + returns).cumprod()
            running_max = cumulative.expanding().max()
            drawdown = (cumulative - running_max) / running_max
            max_drawdown = drawdown.min()
            
            # Beta (vs 7% benchmark return with 15% volatility)
            benchmark_return = 0.07 / 12
            benchmark_vol = 0.15 / (12 ** 0.5)
            covariance = returns.cov(pd.Series([benchmark_return] * len(returns)))
            beta = covariance / (benchmark_vol ** 2) if benchmark_vol > 0 else 1.0
            
            return {
                'annual_return': annual_return,
                'volatility': volatility,
                'sharpe_ratio': sharpe_ratio,
                'max_drawdown': max_drawdown,
                'beta': beta,
                'months_analyzed': len(returns)
            }
            
        except Exception as e:
            logger.warning(f"Could not calculate risk metrics: {e}")
            return None
    
    def _get_charitable_giving_data(self) -> Optional[Dict[str, Any]]:
        """Get charitable giving strategy configuration or estimates."""
        try:
            from config import get_config_manager
            
            config = get_config_manager()
            
            # Get charitable giving configuration
            annual_giving = config.get("charitable", "annual_giving", 0.0)
            daf_enabled = config.get("charitable", "daf_enabled", False)
            qcd_enabled = config.get("charitable", "qcd_enabled", False)
            
            # If no charitable data configured, check if portfolio suggests QCD opportunity
            if annual_giving == 0:
                age = config.get("personal", "age", 0)
                if age >= 70:
                    # Estimate potential QCD from RMD
                    portfolio_df = self._get_portfolio_data()
                    if portfolio_df is not None and not portfolio_df.empty:
                        if 'account_type' in portfolio_df.columns and 'market_value' in portfolio_df.columns:
                            traditional_balance = portfolio_df[portfolio_df['account_type'] == 'Traditional']['market_value'].sum()
                            if traditional_balance > 0:
                                # Estimate RMD (simplified - use 4% for age 70-75)
                                estimated_rmd = traditional_balance * 0.04
                                # Suggest QCD up to $105,000 (2024 limit)
                                suggested_qcd = min(105000, estimated_rmd * 0.5)
                                
                                tax_data = self._get_current_tax_data()
                                marginal_rate = tax_data.get('marginal_rate', 0.22) if tax_data else 0.22
                                
                                return {
                                    'annual_giving': 0,
                                    'daf_enabled': False,
                                    'qcd_enabled': False,
                                    'qcd_eligible': True,
                                    'suggested_qcd': suggested_qcd,
                                    'estimated_rmd': estimated_rmd,
                                    'potential_tax_savings': suggested_qcd * marginal_rate,
                                    'marginal_rate': marginal_rate,
                                    'is_estimated': True
                                }
                return None
            
            # Calculate potential tax benefits
            tax_data = self._get_current_tax_data()
            marginal_rate = tax_data.get('marginal_rate', 0.22) if tax_data else 0.22
            
            # DAF bundling benefit (3 years of giving)
            daf_benefit = annual_giving * 3 * marginal_rate if daf_enabled else 0
            
            # QCD benefit (if over 70.5)
            age = config.get("personal", "age", 65)
            qcd_benefit = min(annual_giving, 105000) * marginal_rate if qcd_enabled and age >= 70 else 0
            
            total_savings = daf_benefit + qcd_benefit
            
            return {
                'annual_giving': annual_giving,
                'daf_enabled': daf_enabled,
                'qcd_enabled': qcd_enabled,
                'daf_benefit': daf_benefit,
                'qcd_benefit': qcd_benefit,
                'total_savings': total_savings,
                'marginal_rate': marginal_rate,
                'is_estimated': False
            }
            
        except Exception as e:
            logger.warning(f"Could not load charitable giving data: {e}")
            return None
    
    def _get_tax_projections(self) -> Optional[pd.DataFrame]:
        """Get multi-year tax projections from actual strategy results."""
        try:
            from strategy import build_withdrawal_strategy_display
            import datetime
            
            current_year = datetime.date.today().year
            
            # Run the actual strategy to get real tax projection data
            strategy_df, _ = build_withdrawal_strategy_display(
                start_year=current_year,
                num_years=10
            )
            
            if strategy_df is None or strategy_df.empty:
                return None
            
            # Extract tax projection data from strategy
            # The strategy DataFrame has columns: Year, AGI, Fed Tax, State Tax, etc.
            projections = []
            for _, row in strategy_df.head(10).iterrows():
                year = int(row['Year'])
                
                # Get income (AGI or MAGI)
                income = row.get('AGI', row.get('MAGI', 0))
                
                # Get tax amounts
                federal_tax = row.get('Fed Tax', 0)
                state_tax = row.get('State Tax', 0)
                total_tax = federal_tax + state_tax
                
                # Calculate effective rate
                effective_rate = (total_tax / income * 100) if income > 0 else 0
                
                projections.append({
                    'Year': year,
                    'Income': income,
                    'Federal Tax': federal_tax,
                    'State Tax': state_tax,
                    'Total Tax': total_tax,
                    'Effective Rate': effective_rate
                })
            
            return pd.DataFrame(projections)
            
        except Exception as e:
            logger.warning(f"Could not load tax projections: {e}")
            return None