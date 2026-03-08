"""
Export functionality for LTC and HSA analysis results.

Provides functions to export analysis results to various formats:
- CSV for spreadsheet analysis
- JSON for data interchange
- PDF reports (requires reportlab)
- Markdown reports
"""

import pandas as pd
import json
from datetime import datetime
from typing import Dict, List, Any
import io


def export_ltc_analysis_to_csv(
    cost_comparison: pd.DataFrame,
    medicaid_analysis: Any,
    insurance_analysis: Any = None,
    ltc_probability: Dict = None
) -> str:
    """
    Export LTC analysis to CSV format.
    
    Args:
        cost_comparison: DataFrame with cost comparison
        medicaid_analysis: MedicaidSpendDownAnalysis object
        insurance_analysis: LTCInsuranceAnalysis object (optional)
        ltc_probability: Dictionary with LTC probability data (optional)
        
    Returns:
        CSV string
    """
    output = io.StringIO()
    
    # Header
    output.write(f"Long-Term Care Analysis Report\n")
    output.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    output.write("\n")
    
    # Cost Comparison
    output.write("=== COST COMPARISON BY CARE TYPE ===\n")
    cost_comparison.to_csv(output, index=False)
    output.write("\n")
    
    # Medicaid Analysis
    output.write("=== MEDICAID ELIGIBILITY ANALYSIS ===\n")
    output.write(f"Current Assets,${medicaid_analysis.current_assets:,.2f}\n")
    output.write(f"Asset Limit,${medicaid_analysis.asset_limit:,.2f}\n")
    output.write(f"Excess Assets,${medicaid_analysis.excess_assets:,.2f}\n")
    output.write(f"Months to Qualify,{medicaid_analysis.months_to_qualify}\n")
    output.write(f"Protected Spouse Assets,${medicaid_analysis.protected_spouse_assets:,.2f}\n")
    output.write("\n")
    
    output.write("Spend-Down Strategies:\n")
    for i, strategy in enumerate(medicaid_analysis.spend_down_strategies, 1):
        output.write(f"{i},{strategy}\n")
    output.write("\n")
    
    output.write("Lookback Period Concerns:\n")
    for i, concern in enumerate(medicaid_analysis.lookback_concerns, 1):
        output.write(f"{i},{concern}\n")
    output.write("\n")
    
    # Insurance Analysis
    if insurance_analysis:
        output.write("=== LTC INSURANCE VS SELF-INSURANCE ===\n")
        output.write(f"Annual Premium,${insurance_analysis.annual_premium:,.2f}\n")
        output.write(f"Total Premiums Paid,${insurance_analysis.total_premiums_paid:,.2f}\n")
        output.write(f"Daily Benefit,${insurance_analysis.daily_benefit:,.2f}\n")
        output.write(f"Benefit Period (Years),{insurance_analysis.benefit_period_years}\n")
        output.write(f"Total Insurance Benefit,${insurance_analysis.total_insurance_benefit:,.2f}\n")
        output.write(f"Self-Insurance Cost,${insurance_analysis.self_insurance_cost:,.2f}\n")
        output.write(f"Break-Even Year,{insurance_analysis.break_even_year}\n")
        output.write(f"Recommendation,{insurance_analysis.recommendation}\n")
        output.write("\n")
        
        output.write("Analysis Notes:\n")
        for i, note in enumerate(insurance_analysis.notes, 1):
            output.write(f"{i},{note}\n")
        output.write("\n")
    
    # LTC Probability
    if ltc_probability:
        output.write("=== LTC PROBABILITY ===\n")
        output.write(f"Probability of Any LTC,{ltc_probability['any_ltc']*100:.1f}%\n")
        output.write(f"Expected Duration (Years),{ltc_probability['expected_duration_years']:.1f}\n")
        output.write(f"Less Than 1 Year,{ltc_probability['less_than_1_year']*100:.1f}%\n")
        output.write(f"1-3 Years,{ltc_probability['1_to_3_years']*100:.1f}%\n")
        output.write(f"3-5 Years,{ltc_probability['3_to_5_years']*100:.1f}%\n")
        output.write(f"More Than 5 Years,{ltc_probability['more_than_5_years']*100:.1f}%\n")
    
    return output.getvalue()


def export_ltc_analysis_to_json(
    cost_comparison: pd.DataFrame,
    medicaid_analysis: Any,
    insurance_analysis: Any = None,
    ltc_probability: Dict = None
) -> str:
    """
    Export LTC analysis to JSON format.
    
    Args:
        cost_comparison: DataFrame with cost comparison
        medicaid_analysis: MedicaidSpendDownAnalysis object
        insurance_analysis: LTCInsuranceAnalysis object (optional)
        ltc_probability: Dictionary with LTC probability data (optional)
        
    Returns:
        JSON string
    """
    data = {
        "report_type": "Long-Term Care Analysis",
        "generated": datetime.now().isoformat(),
        "cost_comparison": cost_comparison.to_dict('records'),
        "medicaid_analysis": {
            "current_assets": medicaid_analysis.current_assets,
            "asset_limit": medicaid_analysis.asset_limit,
            "excess_assets": medicaid_analysis.excess_assets,
            "months_to_qualify": medicaid_analysis.months_to_qualify,
            "protected_spouse_assets": medicaid_analysis.protected_spouse_assets,
            "spend_down_strategies": medicaid_analysis.spend_down_strategies,
            "lookback_concerns": medicaid_analysis.lookback_concerns
        }
    }
    
    if insurance_analysis:
        data["insurance_analysis"] = {
            "annual_premium": insurance_analysis.annual_premium,
            "total_premiums_paid": insurance_analysis.total_premiums_paid,
            "daily_benefit": insurance_analysis.daily_benefit,
            "benefit_period_years": insurance_analysis.benefit_period_years,
            "total_insurance_benefit": insurance_analysis.total_insurance_benefit,
            "self_insurance_cost": insurance_analysis.self_insurance_cost,
            "break_even_year": insurance_analysis.break_even_year,
            "recommendation": insurance_analysis.recommendation,
            "notes": insurance_analysis.notes
        }
    
    if ltc_probability:
        data["ltc_probability"] = ltc_probability
    
    return json.dumps(data, indent=2)


def export_hsa_analysis_to_csv(
    projection: Any,
    strategies: List[Any] = None,
    tax_advantage: Any = None,
    healthcare_costs: Dict = None
) -> str:
    """
    Export HSA analysis to CSV format.
    
    Args:
        projection: HSAProjection object
        strategies: List of HSAWithdrawalStrategy objects (optional)
        tax_advantage: HSATaxAdvantageAnalysis object (optional)
        healthcare_costs: Dictionary with healthcare cost estimates (optional)
        
    Returns:
        CSV string
    """
    output = io.StringIO()
    
    # Header
    output.write(f"Health Savings Account (HSA) Analysis Report\n")
    output.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    output.write("\n")
    
    # HSA Projection Summary
    output.write("=== HSA GROWTH PROJECTION SUMMARY ===\n")
    output.write(f"Current Balance,${projection.current_balance:,.2f}\n")
    output.write(f"Years to Medicare,{projection.years_to_medicare}\n")
    output.write(f"Total Contributions,${projection.total_contributions:,.2f}\n")
    output.write(f"Investment Growth,${projection.investment_growth:,.2f}\n")
    output.write(f"Final Balance at Age 65,${projection.final_balance:,.2f}\n")
    output.write("\n")
    
    # Year-by-Year Projection
    output.write("=== YEAR-BY-YEAR PROJECTION ===\n")
    proj_df = pd.DataFrame(projection.annual_projections)
    proj_df.to_csv(output, index=False)
    output.write("\n")
    
    # Withdrawal Strategies
    if strategies:
        output.write("=== RETIREMENT WITHDRAWAL STRATEGIES ===\n")
        for i, strategy in enumerate(strategies, 1):
            output.write(f"\nStrategy {i}: {strategy.strategy_name}\n")
            output.write(f"Annual Medical Expenses,${strategy.annual_medical_expenses:,.2f}\n")
            output.write(f"HSA Withdrawals,${strategy.hsa_withdrawals:,.2f}\n")
            output.write(f"Taxable Withdrawals,${strategy.taxable_withdrawals:,.2f}\n")
            output.write(f"Years HSA Lasts,{strategy.years_hsa_lasts}\n")
            output.write(f"Total Tax Savings,${strategy.total_tax_savings:,.2f}\n")
            output.write("\nStrategy Notes:\n")
            for j, note in enumerate(strategy.notes, 1):
                output.write(f"{j},{note}\n")
        output.write("\n")
    
    # Triple Tax Advantage
    if tax_advantage:
        output.write("=== TRIPLE TAX ADVANTAGE ANALYSIS ===\n")
        output.write(f"Total Contributions,${tax_advantage.total_contributions:,.2f}\n")
        output.write(f"Tax Savings on Contributions,${tax_advantage.tax_savings_contributions:,.2f}\n")
        output.write(f"Investment Growth,${tax_advantage.investment_growth:,.2f}\n")
        output.write(f"Tax Savings on Growth,${tax_advantage.tax_savings_growth:,.2f}\n")
        output.write(f"Qualified Withdrawals,${tax_advantage.qualified_withdrawals:,.2f}\n")
        output.write(f"Tax Savings on Withdrawals,${tax_advantage.tax_savings_withdrawals:,.2f}\n")
        output.write(f"Total Tax Advantage,${tax_advantage.total_tax_advantage:,.2f}\n")
        output.write(f"Equivalent Taxable Account,${tax_advantage.equivalent_taxable_account:,.2f}\n")
        output.write("\n")
    
    # Healthcare Costs
    if healthcare_costs:
        output.write("=== RETIREMENT HEALTHCARE COST ESTIMATES ===\n")
        output.write(f"Base Healthcare,${healthcare_costs['base_healthcare']:,.2f}\n")
        output.write(f"Medicare Premiums,${healthcare_costs['medicare_premiums']:,.2f}\n")
        output.write(f"Out-of-Pocket,${healthcare_costs['out_of_pocket']:,.2f}\n")
        output.write(f"Long-Term Care,${healthcare_costs['long_term_care']:,.2f}\n")
        output.write(f"Total Healthcare Costs,${healthcare_costs['total_healthcare_costs']:,.2f}\n")
        output.write(f"Annual Average,${healthcare_costs['annual_average']:,.2f}\n")
    
    return output.getvalue()


def export_hsa_analysis_to_json(
    projection: Any,
    strategies: List[Any] = None,
    tax_advantage: Any = None,
    healthcare_costs: Dict = None
) -> str:
    """
    Export HSA analysis to JSON format.
    
    Args:
        projection: HSAProjection object
        strategies: List of HSAWithdrawalStrategy objects (optional)
        tax_advantage: HSATaxAdvantageAnalysis object (optional)
        healthcare_costs: Dictionary with healthcare cost estimates (optional)
        
    Returns:
        JSON string
    """
    data = {
        "report_type": "Health Savings Account Analysis",
        "generated": datetime.now().isoformat(),
        "projection": {
            "current_balance": projection.current_balance,
            "years_to_medicare": projection.years_to_medicare,
            "total_contributions": projection.total_contributions,
            "investment_growth": projection.investment_growth,
            "final_balance": projection.final_balance,
            "annual_projections": projection.annual_projections
        }
    }
    
    if strategies:
        data["withdrawal_strategies"] = [
            {
                "strategy_name": s.strategy_name,
                "annual_medical_expenses": s.annual_medical_expenses,
                "hsa_withdrawals": s.hsa_withdrawals,
                "taxable_withdrawals": s.taxable_withdrawals,
                "years_hsa_lasts": s.years_hsa_lasts,
                "total_tax_savings": s.total_tax_savings,
                "notes": s.notes
            }
            for s in strategies
        ]
    
    if tax_advantage:
        data["triple_tax_advantage"] = {
            "total_contributions": tax_advantage.total_contributions,
            "tax_savings_contributions": tax_advantage.tax_savings_contributions,
            "investment_growth": tax_advantage.investment_growth,
            "tax_savings_growth": tax_advantage.tax_savings_growth,
            "qualified_withdrawals": tax_advantage.qualified_withdrawals,
            "tax_savings_withdrawals": tax_advantage.tax_savings_withdrawals,
            "total_tax_advantage": tax_advantage.total_tax_advantage,
            "equivalent_taxable_account": tax_advantage.equivalent_taxable_account
        }
    
    if healthcare_costs:
        data["healthcare_costs"] = healthcare_costs
    
    return json.dumps(data, indent=2)


def export_ltc_analysis_to_markdown(
    cost_comparison: pd.DataFrame,
    medicaid_analysis: Any,
    insurance_analysis: Any = None,
    ltc_probability: Dict = None
) -> str:
    """
    Export LTC analysis to Markdown format.
    
    Args:
        cost_comparison: DataFrame with cost comparison
        medicaid_analysis: MedicaidSpendDownAnalysis object
        insurance_analysis: LTCInsuranceAnalysis object (optional)
        ltc_probability: Dictionary with LTC probability data (optional)
        
    Returns:
        Markdown string
    """
    output = []
    
    # Header
    output.append("# Long-Term Care Analysis Report")
    output.append(f"\n**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    # Cost Comparison
    output.append("## Cost Comparison by Care Type\n")
    output.append(cost_comparison.to_markdown(index=False))
    output.append("\n")
    
    # Medicaid Analysis
    output.append("## Medicaid Eligibility Analysis\n")
    output.append(f"- **Current Assets:** ${medicaid_analysis.current_assets:,.2f}")
    output.append(f"- **Asset Limit:** ${medicaid_analysis.asset_limit:,.2f}")
    output.append(f"- **Excess Assets:** ${medicaid_analysis.excess_assets:,.2f}")
    output.append(f"- **Months to Qualify:** {medicaid_analysis.months_to_qualify}")
    output.append(f"- **Protected Spouse Assets:** ${medicaid_analysis.protected_spouse_assets:,.2f}\n")
    
    output.append("### Spend-Down Strategies\n")
    for strategy in medicaid_analysis.spend_down_strategies:
        output.append(f"- {strategy}")
    output.append("\n")
    
    output.append("### Lookback Period Concerns\n")
    for concern in medicaid_analysis.lookback_concerns:
        output.append(f"- {concern}")
    output.append("\n")
    
    # Insurance Analysis
    if insurance_analysis:
        output.append("## LTC Insurance vs Self-Insurance\n")
        output.append(f"- **Annual Premium:** ${insurance_analysis.annual_premium:,.2f}")
        output.append(f"- **Total Premiums Paid:** ${insurance_analysis.total_premiums_paid:,.2f}")
        output.append(f"- **Daily Benefit:** ${insurance_analysis.daily_benefit:,.2f}")
        output.append(f"- **Benefit Period:** {insurance_analysis.benefit_period_years} years")
        output.append(f"- **Total Insurance Benefit:** ${insurance_analysis.total_insurance_benefit:,.2f}")
        output.append(f"- **Self-Insurance Cost:** ${insurance_analysis.self_insurance_cost:,.2f}")
        output.append(f"- **Break-Even Year:** {insurance_analysis.break_even_year}")
        output.append(f"- **Recommendation:** {insurance_analysis.recommendation}\n")
        
        output.append("### Analysis Notes\n")
        for note in insurance_analysis.notes:
            output.append(f"- {note}")
        output.append("\n")
    
    # LTC Probability
    if ltc_probability:
        output.append("## LTC Probability\n")
        output.append(f"- **Probability of Any LTC:** {ltc_probability['any_ltc']*100:.1f}%")
        output.append(f"- **Expected Duration:** {ltc_probability['expected_duration_years']:.1f} years")
        output.append(f"- **Less Than 1 Year:** {ltc_probability['less_than_1_year']*100:.1f}%")
        output.append(f"- **1-3 Years:** {ltc_probability['1_to_3_years']*100:.1f}%")
        output.append(f"- **3-5 Years:** {ltc_probability['3_to_5_years']*100:.1f}%")
        output.append(f"- **More Than 5 Years:** {ltc_probability['more_than_5_years']*100:.1f}%")
    
    return "\n".join(output)


def export_hsa_analysis_to_markdown(
    projection: Any,
    strategies: List[Any] = None,
    tax_advantage: Any = None,
    healthcare_costs: Dict = None
) -> str:
    """
    Export HSA analysis to Markdown format.
    
    Args:
        projection: HSAProjection object
        strategies: List of HSAWithdrawalStrategy objects (optional)
        tax_advantage: HSATaxAdvantageAnalysis object (optional)
        healthcare_costs: Dictionary with healthcare cost estimates (optional)
        
    Returns:
        Markdown string
    """
    output = []
    
    # Header
    output.append("# Health Savings Account (HSA) Analysis Report")
    output.append(f"\n**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    # HSA Projection Summary
    output.append("## HSA Growth Projection Summary\n")
    output.append(f"- **Current Balance:** ${projection.current_balance:,.2f}")
    output.append(f"- **Years to Medicare:** {projection.years_to_medicare}")
    output.append(f"- **Total Contributions:** ${projection.total_contributions:,.2f}")
    output.append(f"- **Investment Growth:** ${projection.investment_growth:,.2f}")
    output.append(f"- **Final Balance at Age 65:** ${projection.final_balance:,.2f}\n")
    
    # Year-by-Year Projection
    output.append("## Year-by-Year Projection\n")
    proj_df = pd.DataFrame(projection.annual_projections)
    output.append(proj_df.to_markdown(index=False))
    output.append("\n")
    
    # Withdrawal Strategies
    if strategies:
        output.append("## Retirement Withdrawal Strategies\n")
        for i, strategy in enumerate(strategies, 1):
            output.append(f"### Strategy {i}: {strategy.strategy_name}\n")
            output.append(f"- **Annual Medical Expenses:** ${strategy.annual_medical_expenses:,.2f}")
            output.append(f"- **HSA Withdrawals:** ${strategy.hsa_withdrawals:,.2f}")
            output.append(f"- **Taxable Withdrawals:** ${strategy.taxable_withdrawals:,.2f}")
            output.append(f"- **Years HSA Lasts:** {strategy.years_hsa_lasts}")
            output.append(f"- **Total Tax Savings:** ${strategy.total_tax_savings:,.2f}\n")
            
            output.append("**Strategy Notes:**\n")
            for note in strategy.notes:
                output.append(f"- {note}")
            output.append("\n")
    
    # Triple Tax Advantage
    if tax_advantage:
        output.append("## Triple Tax Advantage Analysis\n")
        output.append(f"- **Total Contributions:** ${tax_advantage.total_contributions:,.2f}")
        output.append(f"- **Tax Savings on Contributions:** ${tax_advantage.tax_savings_contributions:,.2f}")
        output.append(f"- **Investment Growth:** ${tax_advantage.investment_growth:,.2f}")
        output.append(f"- **Tax Savings on Growth:** ${tax_advantage.tax_savings_growth:,.2f}")
        output.append(f"- **Qualified Withdrawals:** ${tax_advantage.qualified_withdrawals:,.2f}")
        output.append(f"- **Tax Savings on Withdrawals:** ${tax_advantage.tax_savings_withdrawals:,.2f}")
        output.append(f"- **Total Tax Advantage:** ${tax_advantage.total_tax_advantage:,.2f}")
        output.append(f"- **Equivalent Taxable Account:** ${tax_advantage.equivalent_taxable_account:,.2f}\n")
    
    # Healthcare Costs
    if healthcare_costs:
        output.append("## Retirement Healthcare Cost Estimates\n")
        output.append(f"- **Base Healthcare:** ${healthcare_costs['base_healthcare']:,.2f}")
        output.append(f"- **Medicare Premiums:** ${healthcare_costs['medicare_premiums']:,.2f}")
        output.append(f"- **Out-of-Pocket:** ${healthcare_costs['out_of_pocket']:,.2f}")
        output.append(f"- **Long-Term Care:** ${healthcare_costs['long_term_care']:,.2f}")
        output.append(f"- **Total Healthcare Costs:** ${healthcare_costs['total_healthcare_costs']:,.2f}")
        output.append(f"- **Annual Average:** ${healthcare_costs['annual_average']:,.2f}")
    
    return "\n".join(output)

# Made with Bob
