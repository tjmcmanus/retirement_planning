"""
Tax Savings Monitoring Script
==============================
Monitor and compare smart security selection vs FIFO baseline over time.

This script provides detailed metrics on:
- Tax savings achieved
- LTCG differences
- Drift improvements
- Security selection patterns
- Performance trends

Usage:
    python3 monitor_tax_savings.py [--amount AMOUNT] [--runs RUNS]

Author: Bob
Date: 2026-03-17
"""

import argparse
import pandas as pd
import numpy as np
from datetime import datetime
from typing import Dict, List, Tuple
import statistics

from security_selection_integration import (
    withdraw_from_brokerage_smart,
    DEFAULT_TARGET_ALLOCATION,
)
from strategy import BrokerageAccount


def create_test_portfolio(scenario: str = 'balanced') -> pd.DataFrame:
    """Create test portfolio with different scenarios."""
    
    if scenario == 'balanced':
        return pd.DataFrame([
            {
                'symbol': 'VTI',
                'account_type': 'Brokerage',
                'qty': 500,
                'purchase_price': 200.0,
                'current_price': 240.0,
                'market_value': 120000.0,
                'sector': 'Stocks',
                'name': 'Vanguard Total Stock Market ETF',
                'holding_period_days': 730,
                'asset_class': 'Stocks',
            },
            {
                'symbol': 'BND',
                'account_type': 'Brokerage',
                'qty': 1000,
                'purchase_price': 80.0,
                'current_price': 78.0,
                'market_value': 78000.0,
                'sector': 'Bond',
                'name': 'Vanguard Total Bond Market ETF',
                'holding_period_days': 1095,
                'asset_class': 'Bonds',
            },
            {
                'symbol': 'AAPL',
                'account_type': 'Brokerage',
                'qty': 100,
                'purchase_price': 150.0,
                'current_price': 180.0,
                'market_value': 18000.0,
                'sector': 'Technology',
                'name': 'Apple Inc.',
                'holding_period_days': 400,
                'asset_class': 'Stocks',
            },
            {
                'symbol': 'GOOGL',
                'account_type': 'Brokerage',
                'qty': 50,
                'purchase_price': 2800.0,
                'current_price': 2500.0,
                'market_value': 125000.0,
                'sector': 'Technology',
                'name': 'Alphabet Inc.',
                'holding_period_days': 200,
                'asset_class': 'Stocks',
            },
            {
                'symbol': 'MF:CASH',
                'account_type': 'Brokerage',
                'qty': 25000,
                'purchase_price': 1.0,
                'current_price': 1.0,
                'market_value': 25000.0,
                'sector': 'MF:Cash',
                'name': 'Cash',
                'holding_period_days': 0,
                'asset_class': 'Cash',
            },
        ])
    
    elif scenario == 'high_gains':
        # Portfolio with significant unrealized gains
        return pd.DataFrame([
            {
                'symbol': 'NVDA',
                'account_type': 'Brokerage',
                'qty': 200,
                'purchase_price': 100.0,
                'current_price': 500.0,
                'market_value': 100000.0,
                'sector': 'Technology',
                'name': 'NVIDIA Corp',
                'holding_period_days': 800,
                'asset_class': 'Stocks',
            },
            {
                'symbol': 'TSLA',
                'account_type': 'Brokerage',
                'qty': 300,
                'purchase_price': 150.0,
                'current_price': 250.0,
                'market_value': 75000.0,
                'sector': 'Technology',
                'name': 'Tesla Inc',
                'holding_period_days': 600,
                'asset_class': 'Stocks',
            },
        ])
    
    elif scenario == 'losses':
        # Portfolio with losses for harvesting
        return pd.DataFrame([
            {
                'symbol': 'XYZ',
                'account_type': 'Brokerage',
                'qty': 1000,
                'purchase_price': 100.0,
                'current_price': 80.0,
                'market_value': 80000.0,
                'sector': 'Technology',
                'name': 'Loss Position',
                'holding_period_days': 400,
                'asset_class': 'Stocks',
            },
            {
                'symbol': 'ABC',
                'account_type': 'Brokerage',
                'qty': 500,
                'purchase_price': 200.0,
                'current_price': 150.0,
                'market_value': 75000.0,
                'sector': 'Healthcare',
                'name': 'Another Loss',
                'holding_period_days': 500,
                'asset_class': 'Stocks',
            },
        ])
    
    return create_test_portfolio('balanced')


def create_brokerage_account(initial_balance: float = 300000) -> BrokerageAccount:
    """Create a brokerage account with history."""
    account = BrokerageAccount()
    account.add_transfer(2020, initial_balance, "initial_portfolio")
    
    # Apply growth for 4 years
    for year in range(2021, 2025):
        account.apply_annual_growth(1.07, year)
    
    return account


def run_comparison(
    amount: float,
    portfolio_df: pd.DataFrame,
    agi: float = 100000,
    filing_status: str = 'single',
) -> Dict:
    """Run a single comparison between smart and FIFO."""
    
    # Smart selection
    smart_account = create_brokerage_account()
    basis_smart, ltcg_smart, plan_smart = withdraw_from_brokerage_smart(
        amount=amount,
        brokerage_account=smart_account,
        portfolio_df=portfolio_df,
        year=2024,
        target_allocation=DEFAULT_TARGET_ALLOCATION,
        current_agi=agi,
        filing_status=filing_status,
    )
    
    # FIFO baseline
    fifo_account = create_brokerage_account()
    basis_fifo, ltcg_fifo = fifo_account.withdraw_fifo(amount, 2024)
    
    # Calculate taxes (15% LTCG rate for this AGI)
    tax_rate = 0.15
    tax_smart = ltcg_smart * tax_rate
    tax_fifo = ltcg_fifo * tax_rate
    tax_savings = tax_fifo - tax_smart
    savings_pct = (tax_savings / tax_fifo * 100) if tax_fifo > 0 else 0
    
    return {
        'amount': amount,
        'basis_smart': basis_smart,
        'ltcg_smart': ltcg_smart,
        'tax_smart': tax_smart,
        'basis_fifo': basis_fifo,
        'ltcg_fifo': ltcg_fifo,
        'tax_fifo': tax_fifo,
        'tax_savings': tax_savings,
        'savings_pct': savings_pct,
        'drift_improvement': plan_smart.drift_improvement if plan_smart else 0,
        'securities_selected': len(plan_smart.securities) if plan_smart else 0,
        'estimated_tax': plan_smart.estimated_tax if plan_smart else 0,
    }


def print_summary(results: List[Dict]):
    """Print summary statistics."""
    if not results:
        print("No results to summarize")
        return
    
    print("\n" + "="*80)
    print("TAX SAVINGS MONITORING SUMMARY")
    print("="*80)
    
    # Overall statistics
    total_withdrawn = sum(r['amount'] for r in results)
    total_tax_smart = sum(r['tax_smart'] for r in results)
    total_tax_fifo = sum(r['tax_fifo'] for r in results)
    total_savings = sum(r['tax_savings'] for r in results)
    avg_savings_pct = statistics.mean(r['savings_pct'] for r in results)
    avg_drift_improvement = statistics.mean(r['drift_improvement'] for r in results)
    
    print(f"\nOverall Performance ({len(results)} runs):")
    print(f"  Total withdrawn: ${total_withdrawn:,.0f}")
    print(f"  Total tax (Smart): ${total_tax_smart:,.0f}")
    print(f"  Total tax (FIFO): ${total_tax_fifo:,.0f}")
    print(f"  Total savings: ${total_savings:,.0f}")
    print(f"  Average savings: {avg_savings_pct:.1f}%")
    print(f"  Average drift improvement: {avg_drift_improvement:+.2f}%")
    
    # Per-run breakdown
    print(f"\nPer-Run Details:")
    print(f"{'Run':<6} {'Amount':<12} {'LTCG Smart':<12} {'LTCG FIFO':<12} {'Tax Savings':<12} {'Savings %':<10} {'Drift':<8}")
    print("-" * 80)
    
    for i, r in enumerate(results, 1):
        print(f"{i:<6} ${r['amount']:<11,.0f} ${r['ltcg_smart']:<11,.0f} "
              f"${r['ltcg_fifo']:<11,.0f} ${r['tax_savings']:<11,.0f} "
              f"{r['savings_pct']:<9.1f}% {r['drift_improvement']:+.2f}%")
    
    # Statistics
    if len(results) > 1:
        savings_values = [r['tax_savings'] for r in results]
        savings_pcts = [r['savings_pct'] for r in results]
        
        print(f"\nStatistics:")
        print(f"  Tax Savings:")
        print(f"    Min: ${min(savings_values):,.0f}")
        print(f"    Max: ${max(savings_values):,.0f}")
        print(f"    Median: ${statistics.median(savings_values):,.0f}")
        print(f"    Std Dev: ${statistics.stdev(savings_values):,.0f}")
        
        print(f"  Savings Percentage:")
        print(f"    Min: {min(savings_pcts):.1f}%")
        print(f"    Max: {max(savings_pcts):.1f}%")
        print(f"    Median: {statistics.median(savings_pcts):.1f}%")
    
    print("\n" + "="*80)


def main():
    """Main monitoring function."""
    parser = argparse.ArgumentParser(description='Monitor tax savings: Smart vs FIFO')
    parser.add_argument('--amount', type=float, default=50000,
                       help='Withdrawal amount (default: 50000)')
    parser.add_argument('--runs', type=int, default=5,
                       help='Number of test runs (default: 5)')
    parser.add_argument('--scenario', choices=['balanced', 'high_gains', 'losses'],
                       default='balanced', help='Portfolio scenario (default: balanced)')
    parser.add_argument('--agi', type=float, default=100000,
                       help='Current AGI (default: 100000)')
    
    args = parser.parse_args()
    
    print(f"Running {args.runs} comparison(s) with ${args.amount:,.0f} withdrawals")
    print(f"Scenario: {args.scenario}, AGI: ${args.agi:,.0f}")
    
    # Create portfolio
    portfolio_df = create_test_portfolio(args.scenario)
    
    # Run comparisons
    results = []
    for i in range(args.runs):
        print(f"\nRun {i+1}/{args.runs}...", end=' ')
        result = run_comparison(args.amount, portfolio_df, args.agi)
        results.append(result)
        print(f"Savings: ${result['tax_savings']:,.0f} ({result['savings_pct']:.1f}%)")
    
    # Print summary
    print_summary(results)
    
    # Export to CSV
    df = pd.DataFrame(results)
    filename = f"tax_savings_monitor_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    df.to_csv(filename, index=False)
    print(f"\nResults exported to: {filename}")


if __name__ == '__main__':
    main()

# Made with Bob
