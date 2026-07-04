"""
Test suite for HSA Integration Module

Tests all HSA planning functions including:
- HSA contribution limits and planning
- HSA growth projections
- HSA withdrawal strategies
- Triple tax advantage calculations
"""

import pytest
from hsa_integration import (
    get_hsa_contribution_limit,
    create_hsa_contribution_plan,
    project_hsa_growth,
    analyze_hsa_withdrawal_strategies,
    calculate_hsa_triple_tax_advantage,
    estimate_retirement_healthcare_costs,
    optimize_hsa_contribution_strategy,
    HSA_LIMIT_INDIVIDUAL_2024,
    HSA_LIMIT_FAMILY_2024,
    HSA_CATCHUP_AGE,
    HSA_CATCHUP_AMOUNT,
    MEDICARE_ENROLLMENT_AGE
)


class TestHSAContributionLimits:
    """Test HSA contribution limit calculations"""
    
    def test_2024_individual_limit(self):
        """Test 2024 individual contribution limit"""
        limit = get_hsa_contribution_limit(2024, 'individual', 50)
        assert limit == HSA_LIMIT_INDIVIDUAL_2024
    
    def test_2024_family_limit(self):
        """Test 2024 family contribution limit"""
        limit = get_hsa_contribution_limit(2024, 'family', 50)
        assert limit == HSA_LIMIT_FAMILY_2024
    
    def test_catchup_contribution(self):
        """Test catch-up contribution for age 55+"""
        limit_under_55 = get_hsa_contribution_limit(2024, 'individual', 54)
        limit_55_plus = get_hsa_contribution_limit(2024, 'individual', 55)
        
        assert limit_55_plus == limit_under_55 + HSA_CATCHUP_AMOUNT
        assert limit_55_plus - limit_under_55 == HSA_CATCHUP_AMOUNT
    
    def test_future_year_inflation(self):
        """Test that future years have inflated limits"""
        limit_2024 = get_hsa_contribution_limit(2024, 'individual', 50)
        limit_2034 = get_hsa_contribution_limit(2034, 'individual', 50)
        
        assert limit_2034 > limit_2024
        # Should be roughly 3% annual increase
        assert limit_2034 > limit_2024 * 1.25  # At least 25% increase over 10 years
    
    def test_limit_rounding(self):
        """Test that limits are rounded to nearest $50"""
        limit = get_hsa_contribution_limit(2025, 'individual', 50)
        assert limit % 50 == 0


class TestHSAContributionPlan:
    """Test HSA contribution planning"""
    
    def test_basic_contribution_plan(self):
        """Test basic contribution plan creation"""
        plans = create_hsa_contribution_plan(
            current_age=50,
            coverage_type='family',
            employer_contribution=1000,
            max_out_contributions=True
        )
        
        assert len(plans) == MEDICARE_ENROLLMENT_AGE - 50
        assert all(plan.employer_contribution == 1000 for plan in plans)
        assert all(plan.total_contribution <= plan.contribution_limit for plan in plans)
    
    def test_max_out_contributions(self):
        """Test maxing out contributions"""
        plans = create_hsa_contribution_plan(
            current_age=50,
            coverage_type='family',
            employer_contribution=1000,
            max_out_contributions=True
        )
        
        for plan in plans:
            assert plan.total_contribution == plan.contribution_limit
            assert plan.employee_contribution == plan.contribution_limit - 1000
    
    def test_custom_employee_contribution(self):
        """Test custom employee contribution"""
        plans = create_hsa_contribution_plan(
            current_age=50,
            coverage_type='individual',
            employer_contribution=500,
            max_out_contributions=False,
            custom_employee_contribution=2000
        )
        
        for plan in plans:
            assert plan.employee_contribution <= 2000
            assert plan.total_contribution <= plan.contribution_limit
    
    def test_catchup_eligibility(self):
        """Test catch-up contribution eligibility"""
        plans = create_hsa_contribution_plan(
            current_age=53,
            coverage_type='individual',
            employer_contribution=1000,
            max_out_contributions=True
        )
        
        # Plans before age 55 should not have catch-up
        plans_before_55 = [p for p in plans if p.age < 55]
        assert all(not p.catchup_eligible for p in plans_before_55)
        
        # Plans at age 55+ should have catch-up
        plans_55_plus = [p for p in plans if p.age >= 55]
        assert all(p.catchup_eligible for p in plans_55_plus)
        assert all(p.catchup_amount == HSA_CATCHUP_AMOUNT for p in plans_55_plus)
    
    def test_stops_at_medicare_age(self):
        """Test that contributions stop at Medicare age"""
        plans = create_hsa_contribution_plan(
            current_age=60,
            coverage_type='family',
            employer_contribution=1000,
            max_out_contributions=True
        )
        
        assert len(plans) == MEDICARE_ENROLLMENT_AGE - 60
        assert all(plan.age < MEDICARE_ENROLLMENT_AGE for plan in plans)


class TestHSAGrowthProjection:
    """Test HSA balance growth projections"""
    
    def test_basic_projection(self):
        """Test basic HSA growth projection"""
        projection = project_hsa_growth(
            current_balance=10000,
            current_age=50,
            coverage_type='family',
            employer_contribution=1000,
            employee_contribution=7000,
            investment_return=0.06,
            annual_medical_expenses=0
        )
        
        assert projection.current_balance == 10000
        assert projection.years_to_medicare == 15
        assert projection.total_contributions > 0
        assert projection.investment_growth > 0
        assert projection.final_balance > projection.current_balance
    
    def test_no_medical_expenses(self):
        """Test projection without medical expenses"""
        projection = project_hsa_growth(
            current_balance=5000,
            current_age=55,
            coverage_type='individual',
            employer_contribution=500,
            employee_contribution=3500,
            investment_return=0.06,
            annual_medical_expenses=0
        )
        
        # Balance should only grow
        assert projection.final_balance > projection.current_balance
        assert all(proj['ending_balance'] >= proj['beginning_balance'] 
                  for proj in projection.annual_projections)
    
    def test_with_medical_expenses(self):
        """Test projection with annual medical expenses"""
        projection_no_expenses = project_hsa_growth(
            current_balance=10000,
            current_age=50,
            coverage_type='family',
            employer_contribution=1000,
            employee_contribution=7000,
            investment_return=0.06,
            annual_medical_expenses=0
        )
        
        projection_with_expenses = project_hsa_growth(
            current_balance=10000,
            current_age=50,
            coverage_type='family',
            employer_contribution=1000,
            employee_contribution=7000,
            investment_return=0.06,
            annual_medical_expenses=3000
        )
        
        # With expenses, final balance should be lower
        assert projection_with_expenses.final_balance < projection_no_expenses.final_balance
    
    def test_investment_growth(self):
        """Test that investment growth is calculated correctly"""
        projection = project_hsa_growth(
            current_balance=10000,
            current_age=60,
            coverage_type='individual',
            employer_contribution=1000,
            employee_contribution=3000,
            investment_return=0.08,
            annual_medical_expenses=0
        )
        
        assert projection.investment_growth > 0
        # Growth should be significant with 8% return
        assert projection.investment_growth > projection.total_contributions * 0.1
    
    def test_annual_projections_structure(self):
        """Test structure of annual projections"""
        projection = project_hsa_growth(
            current_balance=5000,
            current_age=55,
            coverage_type='family',
            employer_contribution=1000,
            employee_contribution=7000,
            investment_return=0.06,
            annual_medical_expenses=2000
        )
        
        assert len(projection.annual_projections) == 10  # 55 to 65
        
        for proj in projection.annual_projections:
            assert 'year' in proj
            assert 'age' in proj
            assert 'beginning_balance' in proj
            assert 'contributions' in proj
            assert 'medical_expenses' in proj
            assert 'investment_growth' in proj
            assert 'ending_balance' in proj


class TestHSAWithdrawalStrategies:
    """Test HSA withdrawal strategy analysis"""
    
    def test_three_strategies_returned(self):
        """Test that three strategies are returned"""
        strategies = analyze_hsa_withdrawal_strategies(
            hsa_balance_at_retirement=100000,
            annual_medical_expenses=8000,
            retirement_age=65,
            life_expectancy=85,
            marginal_tax_rate=0.22
        )
        
        assert len(strategies) == 3
        assert all(hasattr(s, 'strategy_name') for s in strategies)
        assert all(hasattr(s, 'total_tax_savings') for s in strategies)
    
    def test_deplete_early_strategy(self):
        """Test HSA First - Deplete Early strategy"""
        strategies = analyze_hsa_withdrawal_strategies(
            hsa_balance_at_retirement=80000,
            annual_medical_expenses=10000,
            retirement_age=65,
            life_expectancy=85,
            marginal_tax_rate=0.22
        )
        
        deplete_early = strategies[0]
        assert "Deplete Early" in deplete_early.strategy_name
        assert deplete_early.hsa_withdrawals == 80000
        assert deplete_early.years_hsa_lasts == 8  # 80000 / 10000
    
    def test_preserve_hsa_strategy(self):
        """Test Preserve HSA - Let It Grow strategy"""
        strategies = analyze_hsa_withdrawal_strategies(
            hsa_balance_at_retirement=100000,
            annual_medical_expenses=8000,
            retirement_age=65,
            life_expectancy=85,
            marginal_tax_rate=0.22
        )
        
        preserve = strategies[1]
        assert "Preserve" in preserve.strategy_name or "Grow" in preserve.strategy_name
        # HSA should grow during preservation period
        assert preserve.hsa_withdrawals > 100000
    
    def test_balanced_strategy(self):
        """Test Balanced - Proportional Use strategy"""
        strategies = analyze_hsa_withdrawal_strategies(
            hsa_balance_at_retirement=100000,
            annual_medical_expenses=8000,
            retirement_age=65,
            life_expectancy=85,
            marginal_tax_rate=0.22
        )
        
        balanced = strategies[2]
        assert "Balanced" in balanced.strategy_name or "Proportional" in balanced.strategy_name
        assert balanced.years_hsa_lasts == 20  # Full retirement period
    
    def test_tax_savings_calculation(self):
        """Test that tax savings are calculated"""
        strategies = analyze_hsa_withdrawal_strategies(
            hsa_balance_at_retirement=100000,
            annual_medical_expenses=8000,
            retirement_age=65,
            life_expectancy=85,
            marginal_tax_rate=0.24
        )
        
        for strategy in strategies:
            assert strategy.total_tax_savings > 0
            # Tax savings should be roughly HSA withdrawals * tax rate
            assert strategy.total_tax_savings > strategy.hsa_withdrawals * 0.15


class TestTripleTaxAdvantage:
    """Test HSA triple tax advantage calculations"""
    
    def test_basic_tax_advantage(self):
        """Test basic triple tax advantage calculation"""
        advantage = calculate_hsa_triple_tax_advantage(
            total_contributions=100000,
            investment_growth=50000,
            marginal_tax_rate=0.22,
            capital_gains_rate=0.15,
            years_invested=20
        )
        
        assert advantage.total_contributions == 100000
        assert advantage.investment_growth == 50000
        assert advantage.tax_savings_contributions > 0
        assert advantage.tax_savings_growth > 0
        assert advantage.tax_savings_withdrawals > 0
        assert advantage.total_tax_advantage > 0
    
    def test_contribution_tax_savings(self):
        """Test tax savings on contributions"""
        advantage = calculate_hsa_triple_tax_advantage(
            total_contributions=50000,
            investment_growth=20000,
            marginal_tax_rate=0.24,
            capital_gains_rate=0.15,
            years_invested=15
        )
        
        # Tax savings should be contributions * marginal rate
        expected_savings = 50000 * 0.24
        assert advantage.tax_savings_contributions == pytest.approx(expected_savings, rel=0.01)
    
    def test_growth_tax_savings(self):
        """Test tax savings on investment growth"""
        advantage = calculate_hsa_triple_tax_advantage(
            total_contributions=100000,
            investment_growth=60000,
            marginal_tax_rate=0.22,
            capital_gains_rate=0.15,
            years_invested=20
        )
        
        # Tax savings should be growth * capital gains rate
        expected_savings = 60000 * 0.15
        assert advantage.tax_savings_growth == pytest.approx(expected_savings, rel=0.01)
    
    def test_total_advantage(self):
        """Test total tax advantage calculation"""
        advantage = calculate_hsa_triple_tax_advantage(
            total_contributions=80000,
            investment_growth=40000,
            marginal_tax_rate=0.22,
            capital_gains_rate=0.15,
            years_invested=18
        )
        
        # Total should be sum of all three advantages
        total = (
            advantage.tax_savings_contributions +
            advantage.tax_savings_growth +
            advantage.tax_savings_withdrawals
        )
        assert advantage.total_tax_advantage == pytest.approx(total, rel=0.01)
    
    def test_equivalent_taxable_account(self):
        """Test equivalent taxable account calculation"""
        advantage = calculate_hsa_triple_tax_advantage(
            total_contributions=100000,
            investment_growth=50000,
            marginal_tax_rate=0.24,
            capital_gains_rate=0.15,
            years_invested=20
        )
        
        # Equivalent taxable should be higher than HSA value
        hsa_value = advantage.total_contributions + advantage.investment_growth
        assert advantage.equivalent_taxable_account > hsa_value


class TestRetirementHealthcareCosts:
    """Test retirement healthcare cost estimates"""
    
    def test_basic_cost_estimate(self):
        """Test basic healthcare cost estimate"""
        costs = estimate_retirement_healthcare_costs(
            retirement_age=65,
            life_expectancy=85,
            include_ltc=False
        )
        
        assert 'total_healthcare_costs' in costs
        assert 'annual_average' in costs
        assert 'base_healthcare' in costs
        assert 'medicare_premiums' in costs
        assert 'out_of_pocket' in costs
        assert costs['total_healthcare_costs'] > 0
    
    def test_longer_retirement_higher_costs(self):
        """Test that longer retirement means higher costs"""
        costs_20_years = estimate_retirement_healthcare_costs(
            retirement_age=65,
            life_expectancy=85,
            include_ltc=False
        )
        
        costs_30_years = estimate_retirement_healthcare_costs(
            retirement_age=65,
            life_expectancy=95,
            include_ltc=False
        )
        
        assert costs_30_years['total_healthcare_costs'] > costs_20_years['total_healthcare_costs']
    
    def test_ltc_inclusion(self):
        """Test including long-term care costs"""
        costs_without_ltc = estimate_retirement_healthcare_costs(
            retirement_age=65,
            life_expectancy=85,
            include_ltc=False
        )
        
        costs_with_ltc = estimate_retirement_healthcare_costs(
            retirement_age=65,
            life_expectancy=85,
            include_ltc=True,
            ltc_years=3
        )
        
        assert costs_with_ltc['long_term_care'] > 0
        assert costs_with_ltc['total_healthcare_costs'] > costs_without_ltc['total_healthcare_costs']
    
    def test_annual_average_calculation(self):
        """Test annual average calculation"""
        costs = estimate_retirement_healthcare_costs(
            retirement_age=65,
            life_expectancy=85,
            include_ltc=False
        )
        
        years = 85 - 65
        expected_average = costs['total_healthcare_costs'] / years
        assert costs['annual_average'] == pytest.approx(expected_average, rel=0.01)


class TestHSAOptimization:
    """Test HSA contribution optimization"""
    
    def test_basic_optimization(self):
        """Test basic HSA optimization"""
        result = optimize_hsa_contribution_strategy(
            current_age=50,
            current_income=100000,
            current_hsa_balance=20000,
            employer_contribution=1000,
            marginal_tax_rate=0.22,
            coverage_type='family'
        )
        
        assert 'max_annual_contribution' in result
        assert 'recommended_employee_contribution' in result
        assert 'annual_tax_savings' in result
        assert 'projected_balance_at_65' in result
        assert 'coverage_percentage' in result
        assert 'recommendation' in result
    
    def test_tax_savings_calculation(self):
        """Test tax savings calculation in optimization"""
        result = optimize_hsa_contribution_strategy(
            current_age=50,
            current_income=100000,
            current_hsa_balance=10000,
            employer_contribution=1000,
            marginal_tax_rate=0.24,
            coverage_type='individual'
        )
        
        # Tax savings should be employee contribution * tax rate
        expected_savings = result['recommended_employee_contribution'] * 0.24
        assert result['annual_tax_savings'] == pytest.approx(expected_savings, rel=0.01)
    
    def test_coverage_percentage(self):
        """Test coverage percentage calculation"""
        result = optimize_hsa_contribution_strategy(
            current_age=55,
            current_income=150000,
            current_hsa_balance=50000,
            employer_contribution=2000,
            marginal_tax_rate=0.24,
            coverage_type='family'
        )
        
        assert 0 <= result['coverage_percentage'] <= 200  # Reasonable range
    
    def test_recommendation_logic(self):
        """Test that recommendations are appropriate"""
        # High coverage scenario
        result_high = optimize_hsa_contribution_strategy(
            current_age=55,
            current_income=150000,
            current_hsa_balance=100000,
            employer_contribution=3000,
            marginal_tax_rate=0.24,
            coverage_type='family'
        )
        
        # Low coverage scenario
        result_low = optimize_hsa_contribution_strategy(
            current_age=60,
            current_income=80000,
            current_hsa_balance=5000,
            employer_contribution=500,
            marginal_tax_rate=0.22,
            coverage_type='individual'
        )
        
        # High coverage should have better recommendation
        assert "Excellent" in result_high['recommendation'] or "Good" in result_high['recommendation']
        # Low coverage should suggest improvement
        assert "consider" in result_low['recommendation'].lower() or "low" in result_low['recommendation'].lower()


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

# Made with Bob
