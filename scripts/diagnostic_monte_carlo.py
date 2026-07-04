"""
Diagnostic Monte Carlo Analysis
Shows detailed year-by-year breakdown of portfolio depletion
"""

import numpy as np
from monte_carlo import (
    MonteCarloInputs,
    PORTFOLIO_PRESETS,
    _compute_portfolio_stats,
    _simulate_returns,
)

def run_diagnostic_simulation():
    """Run a detailed diagnostic of the Monte Carlo simulation."""
    
    # Your exact parameters
    inputs = MonteCarloInputs(
        initial_portfolio=2_689_454.0,
        annual_withdrawal=60_000.0,
        start_age=62,
        end_age=85,
        portfolio_allocation=PORTFOLIO_PRESETS["Moderate (70/30)"],
        inflation_rate=0.029,
        withdrawal_growth_rate=0.029,
        social_security_annual=0.0,
        ss_start_age=70,
        n_simulations=1000,  # Smaller for diagnostic
        random_seed=42,
    )
    
    n_years = inputs.end_age - inputs.start_age
    n_sims = inputs.n_simulations
    
    # Compute portfolio statistics
    port_mean, port_std = _compute_portfolio_stats(inputs.portfolio_allocation)
    
    print("=" * 80)
    print("DIAGNOSTIC MONTE CARLO ANALYSIS")
    print("=" * 80)
    print(f"\nINPUT PARAMETERS:")
    print(f"  Initial Portfolio:     ${inputs.initial_portfolio:,.0f}")
    print(f"  Annual Withdrawal:     ${inputs.annual_withdrawal:,.0f}")
    print(f"  Initial Withdrawal %:  {inputs.annual_withdrawal / inputs.initial_portfolio * 100:.2f}%")
    print(f"  Retirement Age:        {inputs.start_age}")
    print(f"  Plan To Age:           {inputs.end_age}")
    print(f"  Time Horizon:          {n_years} years")
    print(f"  Inflation Rate:        {inputs.inflation_rate * 100:.1f}%")
    print(f"  Social Security:       ${inputs.social_security_annual:,.0f}/year (age {inputs.ss_start_age})")
    print(f"\nPORTFOLIO STATISTICS:")
    print(f"  Expected Return:       {port_mean * 100:.2f}%")
    print(f"  Standard Deviation:    {port_std * 100:.2f}%")
    
    # Generate returns
    rng = np.random.default_rng(inputs.random_seed)
    returns = _simulate_returns(port_mean, port_std, n_years, n_sims, rng)
    
    # Simulate portfolio paths
    portfolio_paths = np.zeros((n_sims, n_years))
    portfolio = np.full(n_sims, float(inputs.initial_portfolio))
    annual_withdrawal = float(inputs.annual_withdrawal)
    
    print(f"\n{'='*80}")
    print("YEAR-BY-YEAR ANALYSIS (Median Scenario)")
    print(f"{'='*80}")
    print(f"{'Age':<5} {'Year':<5} {'Start Bal':<15} {'Return':<10} {'After Growth':<15} "
          f"{'Withdrawal':<15} {'End Balance':<15} {'Success %':<10}")
    print("-" * 80)
    
    for yr in range(n_years):
        age = inputs.start_age + yr
        
        # Store starting balance
        start_balance = portfolio.copy()
        
        # Grow portfolio
        portfolio = portfolio * returns[:, yr]
        after_growth = portfolio.copy()
        
        # Social Security income
        ss_income = float(inputs.social_security_annual) if age >= inputs.ss_start_age else 0.0
        
        # Net withdrawal
        net_withdrawal = max(0.0, annual_withdrawal - ss_income)
        
        # Subtract withdrawal
        portfolio = np.maximum(0.0, portfolio - net_withdrawal)
        portfolio_paths[:, yr] = portfolio
        
        # Calculate statistics for this year
        median_start = np.median(start_balance)
        median_return = np.median(returns[:, yr])
        median_after_growth = np.median(after_growth)
        median_end = np.median(portfolio)
        success_rate = (portfolio > 0).mean() * 100
        
        print(f"{age:<5} {yr+1:<5} ${median_start:>13,.0f} "
              f"{(median_return - 1) * 100:>8.1f}% ${median_after_growth:>13,.0f} "
              f"${net_withdrawal:>13,.0f} ${median_end:>13,.0f} {success_rate:>9.1f}%")
        
        # Grow withdrawal with inflation
        annual_withdrawal *= (1.0 + inputs.inflation_rate)
    
    # Final statistics
    final_portfolios = portfolio_paths[:, -1]
    success_mask = final_portfolios > 0
    success_probability = float(success_mask.mean())
    
    print(f"\n{'='*80}")
    print("FINAL RESULTS")
    print(f"{'='*80}")
    print(f"Success Probability:        {success_probability * 100:.1f}%")
    print(f"Median Final Portfolio:     ${np.median(final_portfolios):,.0f}")
    print(f"10th Percentile Final:      ${np.percentile(final_portfolios, 10):,.0f}")
    print(f"90th Percentile Final:      ${np.percentile(final_portfolios, 90):,.0f}")
    
    # Find when portfolio depletes
    p10_path = np.percentile(portfolio_paths, 10, axis=0)
    p50_path = np.percentile(portfolio_paths, 50, axis=0)
    
    depletion_10 = np.where(p10_path <= 0)[0]
    depletion_50 = np.where(p50_path <= 0)[0]
    
    print(f"\nDEPLETION ANALYSIS:")
    if len(depletion_10) > 0:
        depletion_age_10 = inputs.start_age + depletion_10[0]
        print(f"  10th Percentile depletes at age: {depletion_age_10}")
    else:
        print(f"  10th Percentile: Portfolio survives ✅")
    
    if len(depletion_50) > 0:
        depletion_age_50 = inputs.start_age + depletion_50[0]
        print(f"  Median depletes at age:          {depletion_age_50}")
    else:
        print(f"  Median: Portfolio survives ✅")
    
    # Show worst-case scenarios
    print(f"\n{'='*80}")
    print("WORST-CASE SCENARIOS (Bottom 5%)")
    print(f"{'='*80}")
    
    # Find the 5 worst simulations
    final_sorted_idx = np.argsort(final_portfolios)[:50]  # Bottom 50 sims
    
    print(f"\nFirst 5 years of worst scenarios:")
    print(f"{'Sim':<5} {'Age 62':<12} {'Age 63':<12} {'Age 64':<12} {'Age 65':<12} {'Age 66':<12}")
    print("-" * 65)
    for i, idx in enumerate(final_sorted_idx[:5]):
        print(f"{i+1:<5} ", end="")
        for yr in range(min(5, n_years)):
            print(f"${portfolio_paths[idx, yr]:>10,.0f}  ", end="")
        print()
    
    # Calculate cumulative withdrawal
    total_withdrawn = 0
    withdrawal = inputs.annual_withdrawal
    for yr in range(n_years):
        age = inputs.start_age + yr
        ss_income = inputs.social_security_annual if age >= inputs.ss_start_age else 0.0
        net_withdrawal = max(0.0, withdrawal - ss_income)
        total_withdrawn += net_withdrawal
        withdrawal *= (1.0 + inputs.inflation_rate)
    
    print(f"\n{'='*80}")
    print("WITHDRAWAL ANALYSIS")
    print(f"{'='*80}")
    print(f"Total Net Withdrawals (23 years):  ${total_withdrawn:,.0f}")
    print(f"Initial Portfolio:                 ${inputs.initial_portfolio:,.0f}")
    print(f"Withdrawals as % of Initial:       {total_withdrawn / inputs.initial_portfolio * 100:.1f}%")
    print(f"\nFinal Year Withdrawal (age 84):    ${inputs.annual_withdrawal * (1.029 ** 22):,.0f}")
    print(f"Final Year Withdrawal Rate:        {(inputs.annual_withdrawal * (1.029 ** 22)) / inputs.initial_portfolio * 100:.2f}%")
    
    print(f"\n{'='*80}")
    print("KEY INSIGHTS")
    print(f"{'='*80}")
    
    if success_probability == 0:
        print("❌ Portfolio fails in ALL scenarios because:")
        print("   1. Withdrawals grow with inflation (2.9%/year)")
        print("   2. No Social Security income to offset withdrawals")
        print("   3. Market volatility causes some years with negative returns")
        print("   4. Sequence-of-returns risk: poor early returns deplete portfolio faster")
        print("\n💡 RECOMMENDATIONS:")
        print("   • Add Social Security income (~$40k/year at age 70)")
        print("   • Reduce initial withdrawal to $50k/year")
        print("   • Delay retirement to age 65 (shorter horizon)")
        print("   • Consider a more conservative allocation initially")
    elif success_probability < 0.75:
        print("⚠️  Portfolio has low success probability")
        print("   Consider adjusting parameters to improve outcomes")
    elif success_probability < 0.90:
        print("🟡 Portfolio has moderate success probability")
        print("   Close to target, but could be improved")
    else:
        print("✅ Portfolio has high success probability")
        print("   Well-positioned for retirement")

if __name__ == "__main__":
    run_diagnostic_simulation()

# Made with Bob
