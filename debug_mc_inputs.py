"""
Debug script to check what inputs are being passed to Monte Carlo
"""

from monte_carlo import MonteCarloInputs, PORTFOLIO_PRESETS, run_monte_carlo

# Simulate what the UI might be passing with your exact values
test_cases = [
    {
        "name": "Your Values (SS = $0)",
        "inputs": MonteCarloInputs(
            initial_portfolio=2_689_454.0,
            annual_withdrawal=60_000.0,
            start_age=62,
            end_age=85,
            portfolio_allocation=PORTFOLIO_PRESETS["Moderate (70/30)"],
            inflation_rate=0.029,
            withdrawal_growth_rate=0.029,
            social_security_annual=0.0,  # No SS
            ss_start_age=70,
            n_simulations=1000,
            random_seed=42,
        )
    },
    {
        "name": "Your Values (SS = $40k default)",
        "inputs": MonteCarloInputs(
            initial_portfolio=2_689_454.0,
            annual_withdrawal=60_000.0,
            start_age=62,
            end_age=85,
            portfolio_allocation=PORTFOLIO_PRESETS["Moderate (70/30)"],
            inflation_rate=0.029,
            withdrawal_growth_rate=0.029,
            social_security_annual=40_000.0,  # Default from UI
            ss_start_age=70,
            n_simulations=1000,
            random_seed=42,
        )
    },
    {
        "name": "Inflation as percentage (BUG)",
        "inputs": MonteCarloInputs(
            initial_portfolio=2_689_454.0,
            annual_withdrawal=60_000.0,
            start_age=62,
            end_age=85,
            portfolio_allocation=PORTFOLIO_PRESETS["Moderate (70/30)"],
            inflation_rate=2.9,  # BUG: stored as 2.9 instead of 0.029
            withdrawal_growth_rate=2.9,
            social_security_annual=0.0,
            ss_start_age=70,
            n_simulations=1000,
            random_seed=42,
        )
    },
    {
        "name": "End age before start age (BUG)",
        "inputs": MonteCarloInputs(
            initial_portfolio=2_689_454.0,
            annual_withdrawal=60_000.0,
            start_age=85,  # BUG: swapped
            end_age=62,
            portfolio_allocation=PORTFOLIO_PRESETS["Moderate (70/30)"],
            inflation_rate=0.029,
            withdrawal_growth_rate=0.029,
            social_security_annual=0.0,
            ss_start_age=70,
            n_simulations=1000,
            random_seed=42,
        )
    },
]

print("=" * 80)
print("MONTE CARLO INPUT DEBUGGING")
print("=" * 80)

for test in test_cases:
    print(f"\n{'='*80}")
    print(f"TEST: {test['name']}")
    print(f"{'='*80}")
    
    inputs = test['inputs']
    print(f"Initial Portfolio:     ${inputs.initial_portfolio:,.0f}")
    print(f"Annual Withdrawal:     ${inputs.annual_withdrawal:,.0f}")
    print(f"Start Age:             {inputs.start_age}")
    print(f"End Age:               {inputs.end_age}")
    print(f"Time Horizon:          {inputs.end_age - inputs.start_age} years")
    print(f"Inflation Rate:        {inputs.inflation_rate}")
    print(f"Social Security:       ${inputs.social_security_annual:,.0f}")
    print(f"SS Start Age:          {inputs.ss_start_age}")
    
    try:
        result = run_monte_carlo(inputs)
        print(f"\n✅ SUCCESS PROBABILITY: {result.success_probability * 100:.1f}%")
        print(f"   Median Final:        ${result.median_final_portfolio:,.0f}")
        print(f"   P10 Final:           ${result.p10_final_portfolio:,.0f}")
        
        if result.success_probability == 0:
            print("\n❌ ZERO SUCCESS - Portfolio fails in ALL scenarios!")
            if result.notes:
                print("   Notes:")
                for note in result.notes:
                    print(f"     • {note}")
        elif result.success_probability < 0.75:
            print("\n⚠️  LOW SUCCESS - High risk of portfolio depletion")
        elif result.success_probability < 0.90:
            print("\n🟡 MODERATE SUCCESS - Below 90% target")
        else:
            print("\n✅ HIGH SUCCESS - Portfolio well-positioned")
            
    except Exception as e:
        print(f"\n❌ ERROR: {e}")

print(f"\n{'='*80}")
print("CONCLUSION")
print(f"{'='*80}")
print("\nIf you're seeing 0% success in the UI, check:")
print("1. Is Social Security set to $0 in the UI? (Default is $40k)")
print("2. Is inflation stored as 2.9 instead of 0.029?")
print("3. Are start_age and end_age swapped?")
print("4. Check browser console for JavaScript errors")
print("5. Try clearing browser cache and reloading")

# Made with Bob
