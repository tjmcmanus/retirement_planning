"""
Test suite for Long-Term Care (LTC) Planning Module

Tests all LTC planning functions including:
- Nursing home cost projections
- Medicaid spend-down analysis
- LTC insurance vs self-insurance comparison
- LTC probability calculations
"""

import pytest
import pandas as pd
from ltc_planning import (
    get_nursing_home_cost,
    project_ltc_costs,
    analyze_medicaid_spend_down,
    analyze_ltc_insurance_vs_self_insurance,
    calculate_ltc_probability,
    generate_ltc_cost_comparison,
    NATIONAL_NURSING_HOME_PRIVATE,
    NATIONAL_NURSING_HOME_SEMI,
    STATE_NURSING_HOME_COSTS,
    MEDICAID_ASSET_LIMIT_SINGLE,
    MEDICAID_ASSET_LIMIT_MARRIED_APPLICANT,
    LTC_INFLATION_RATE
)


class TestNursingHomeCosts:
    """Test nursing home cost retrieval"""
    
    def test_national_private_room(self):
        """Test national average for private room"""
        cost = get_nursing_home_cost('National', 'private')
        assert cost == NATIONAL_NURSING_HOME_PRIVATE
        assert cost > 0
    
    def test_national_semi_private_room(self):
        """Test national average for semi-private room"""
        cost = get_nursing_home_cost('National', 'semi-private')
        assert cost == NATIONAL_NURSING_HOME_SEMI
        assert cost < NATIONAL_NURSING_HOME_PRIVATE
    
    def test_state_specific_cost(self):
        """Test state-specific costs"""
        ca_cost = get_nursing_home_cost('CA', 'private')
        tx_cost = get_nursing_home_cost('TX', 'private')
        
        assert ca_cost == STATE_NURSING_HOME_COSTS['CA']
        assert tx_cost == STATE_NURSING_HOME_COSTS['TX']
        assert ca_cost > tx_cost  # CA is more expensive than TX
    
    def test_semi_private_discount(self):
        """Test that semi-private is cheaper than private"""
        private = get_nursing_home_cost('CA', 'private')
        semi = get_nursing_home_cost('CA', 'semi-private')
        
        assert semi < private
        assert semi == pytest.approx(private * 0.88, rel=0.01)
    
    def test_invalid_state_uses_national(self):
        """Test that invalid state code uses national average"""
        cost = get_nursing_home_cost('XX', 'private')
        assert cost == NATIONAL_NURSING_HOME_PRIVATE


class TestLTCCostProjections:
    """Test LTC cost projections with inflation"""
    
    def test_nursing_home_projection(self):
        """Test nursing home cost projection"""
        projection = project_ltc_costs(
            'nursing_home_private',
            years_until_need=10,
            years_of_care=3,
            state='National'
        )
        
        assert projection.care_type == 'nursing_home_private'
        assert projection.years_needed == 3
        assert projection.annual_cost > NATIONAL_NURSING_HOME_PRIVATE  # Inflated
        assert projection.inflation_adjusted_total > projection.total_cost
    
    def test_assisted_living_projection(self):
        """Test assisted living cost projection"""
        projection = project_ltc_costs(
            'assisted_living',
            years_until_need=5,
            years_of_care=2,
            state='National'
        )
        
        assert projection.care_type == 'assisted_living'
        assert projection.years_needed == 2
        assert projection.annual_cost > 0
    
    def test_home_health_full_time(self):
        """Test full-time home health aide projection"""
        projection = project_ltc_costs(
            'home_health_full',
            years_until_need=0,
            years_of_care=1,
            state='National'
        )
        
        # Full-time should be more expensive than part-time
        assert projection.annual_cost > 75_504  # More than part-time base
    
    def test_inflation_impact(self):
        """Test that inflation increases costs over time"""
        projection_now = project_ltc_costs(
            'nursing_home_private',
            years_until_need=0,
            years_of_care=1,
            state='National'
        )
        
        projection_future = project_ltc_costs(
            'nursing_home_private',
            years_until_need=10,
            years_of_care=1,
            state='National'
        )
        
        assert projection_future.annual_cost > projection_now.annual_cost
        expected_ratio = (1 + LTC_INFLATION_RATE) ** 10
        assert projection_future.annual_cost == pytest.approx(
            projection_now.annual_cost * expected_ratio,
            rel=0.01
        )
    
    def test_multi_year_inflation(self):
        """Test inflation over multiple years of care"""
        projection = project_ltc_costs(
            'nursing_home_private',
            years_until_need=5,
            years_of_care=3,
            state='National'
        )
        
        # Inflation-adjusted total should be higher than simple total
        assert projection.inflation_adjusted_total > projection.total_cost
        
        # Should be roughly 3 years of inflated costs
        assert projection.total_cost == pytest.approx(
            projection.annual_cost * 3,
            rel=0.01
        )


class TestMedicaidSpendDown:
    """Test Medicaid eligibility and spend-down analysis"""
    
    def test_single_person_eligible(self):
        """Test single person already eligible"""
        analysis = analyze_medicaid_spend_down(
            current_assets=1500,
            is_married=False
        )
        
        assert analysis.current_assets == 1500
        assert analysis.asset_limit == MEDICAID_ASSET_LIMIT_SINGLE
        assert analysis.excess_assets == 0
        assert analysis.months_to_qualify == 0
        assert "Currently eligible" in analysis.spend_down_strategies[0]
    
    def test_single_person_excess_assets(self):
        """Test single person with excess assets"""
        analysis = analyze_medicaid_spend_down(
            current_assets=100_000,
            is_married=False
        )
        
        assert analysis.excess_assets > 0
        assert analysis.months_to_qualify > 0
        assert len(analysis.spend_down_strategies) > 1
    
    def test_married_couple_asset_limits(self):
        """Test married couple asset limits"""
        analysis = analyze_medicaid_spend_down(
            current_assets=50_000,
            is_married=True,
            spouse_assets=100_000
        )
        
        assert analysis.protected_spouse_assets > 0
        assert analysis.asset_limit > MEDICAID_ASSET_LIMIT_SINGLE
    
    def test_spend_down_strategies(self):
        """Test that spend-down strategies are provided"""
        analysis = analyze_medicaid_spend_down(
            current_assets=200_000,
            is_married=True,
            spouse_assets=50_000
        )
        
        strategies = analysis.spend_down_strategies
        assert len(strategies) > 0
        
        # Should include common strategies
        strategy_text = ' '.join(strategies)
        assert any(keyword in strategy_text.lower() for keyword in 
                  ['pay', 'debt', 'home', 'annuity', 'spouse'])
    
    def test_lookback_period_no_transfers(self):
        """Test lookback period with no transfers"""
        analysis = analyze_medicaid_spend_down(
            current_assets=50_000,
            is_married=False,
            recent_transfers=[]
        )
        
        assert len(analysis.lookback_concerns) == 1
        assert "No concerning" in analysis.lookback_concerns[0]
    
    def test_lookback_period_with_transfers(self):
        """Test lookback period with recent transfers"""
        analysis = analyze_medicaid_spend_down(
            current_assets=50_000,
            is_married=False,
            recent_transfers=[(50_000, 24)]  # $50k transferred 24 months ago
        )
        
        assert len(analysis.lookback_concerns) > 0
        assert any("penalty" in concern.lower() for concern in analysis.lookback_concerns)


class TestLTCInsuranceAnalysis:
    """Test LTC insurance vs self-insurance comparison"""
    
    def test_basic_insurance_analysis(self):
        """Test basic insurance analysis"""
        analysis = analyze_ltc_insurance_vs_self_insurance(
            current_age=55,
            annual_premium=3000,
            daily_benefit=200,
            benefit_period_years=3,
            waiting_period_days=90,
            years_until_need=10,
            expected_years_of_care=3,
            state='National',
            inflation_protection=True
        )
        
        assert analysis.annual_premium == 3000
        assert analysis.total_premiums_paid > 0
        assert analysis.total_insurance_benefit > 0
        assert analysis.self_insurance_cost > 0
        assert analysis.break_even_year > 0
        assert len(analysis.recommendation) > 0
        assert len(analysis.notes) > 0
    
    def test_insurance_recommended(self):
        """Test case where insurance is recommended"""
        # High benefit, low premium scenario
        analysis = analyze_ltc_insurance_vs_self_insurance(
            current_age=50,
            annual_premium=2000,
            daily_benefit=300,
            benefit_period_years=5,
            waiting_period_days=0,
            years_until_need=15,
            expected_years_of_care=5,
            state='National',
            inflation_protection=True
        )
        
        # With good terms, insurance should be beneficial
        net_benefit = analysis.total_insurance_benefit - analysis.total_premiums_paid
        assert net_benefit > 0
    
    def test_self_insurance_better(self):
        """Test case where self-insurance is better"""
        # High premium, low benefit scenario
        analysis = analyze_ltc_insurance_vs_self_insurance(
            current_age=60,
            annual_premium=8000,
            daily_benefit=150,
            benefit_period_years=2,
            waiting_period_days=180,
            years_until_need=5,
            expected_years_of_care=2,
            state='TX',  # Lower cost state
            inflation_protection=False
        )
        
        # High premiums with low benefits should favor self-insurance
        assert "Self-Insurance" in analysis.recommendation or "Marginally" in analysis.recommendation
    
    def test_inflation_protection_impact(self):
        """Test impact of inflation protection"""
        without_inflation = analyze_ltc_insurance_vs_self_insurance(
            current_age=55,
            annual_premium=3000,
            daily_benefit=200,
            benefit_period_years=3,
            waiting_period_days=90,
            years_until_need=10,
            expected_years_of_care=3,
            inflation_protection=False
        )
        
        with_inflation = analyze_ltc_insurance_vs_self_insurance(
            current_age=55,
            annual_premium=3000,
            daily_benefit=200,
            benefit_period_years=3,
            waiting_period_days=90,
            years_until_need=10,
            expected_years_of_care=3,
            inflation_protection=True
        )
        
        # With inflation protection, daily benefit should be higher
        assert with_inflation.daily_benefit > without_inflation.daily_benefit
    
    def test_waiting_period_cost(self):
        """Test that waiting period affects analysis"""
        no_waiting = analyze_ltc_insurance_vs_self_insurance(
            current_age=55,
            annual_premium=3000,
            daily_benefit=200,
            benefit_period_years=3,
            waiting_period_days=0,
            years_until_need=10,
            expected_years_of_care=3
        )
        
        with_waiting = analyze_ltc_insurance_vs_self_insurance(
            current_age=55,
            annual_premium=3000,
            daily_benefit=200,
            benefit_period_years=3,
            waiting_period_days=90,
            years_until_need=10,
            expected_years_of_care=3
        )
        
        # Waiting period should be mentioned in notes
        assert any("waiting" in note.lower() for note in with_waiting.notes)


class TestLTCProbability:
    """Test LTC probability calculations"""
    
    def test_male_probability(self):
        """Test LTC probability for male"""
        prob = calculate_ltc_probability(65, 'M')
        
        assert 0 < prob['any_ltc'] <= 1
        assert prob['expected_duration_years'] == 3.0
        assert prob['any_ltc'] == pytest.approx(0.70, abs=0.1)
    
    def test_female_probability(self):
        """Test LTC probability for female"""
        prob = calculate_ltc_probability(65, 'F')
        
        assert 0 < prob['any_ltc'] <= 1
        assert prob['expected_duration_years'] == 3.7
        assert prob['expected_duration_years'] > 3.0  # Females have longer duration
    
    def test_age_adjustment(self):
        """Test that probability adjusts with age"""
        prob_young = calculate_ltc_probability(50, 'M')
        prob_old = calculate_ltc_probability(75, 'M')
        
        assert prob_old['any_ltc'] > prob_young['any_ltc']
    
    def test_duration_breakdown(self):
        """Test that duration probabilities sum correctly"""
        prob = calculate_ltc_probability(65, 'M')
        
        total_duration_prob = (
            prob['less_than_1_year'] +
            prob['1_to_3_years'] +
            prob['3_to_5_years'] +
            prob['more_than_5_years']
        )
        
        # Should approximately equal total probability
        assert total_duration_prob == pytest.approx(prob['any_ltc'], rel=0.01)


class TestCostComparison:
    """Test cost comparison table generation"""
    
    def test_comparison_table_structure(self):
        """Test that comparison table has correct structure"""
        df = generate_ltc_cost_comparison('National', 10)
        
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 6  # 6 care types
        assert 'Care Type' in df.columns
        assert 'Current Annual Cost' in df.columns
        assert 'Projected Annual Cost' in df.columns
        assert 'Monthly Cost' in df.columns
        assert '3-Year Total Cost' in df.columns
    
    def test_comparison_costs_reasonable(self):
        """Test that costs are in reasonable ranges"""
        df = generate_ltc_cost_comparison('National', 0)
        
        # Nursing home should be most expensive
        nursing_home_cost = df[df['Care Type'].str.contains('Nursing Home - Private')]['Current Annual Cost'].values[0]
        adult_day_care_cost = df[df['Care Type'].str.contains('Adult Day Care')]['Current Annual Cost'].values[0]
        
        assert nursing_home_cost > adult_day_care_cost
        assert nursing_home_cost > 50_000  # Reasonable minimum
        assert nursing_home_cost < 500_000  # Reasonable maximum
    
    def test_inflation_projection(self):
        """Test that future costs are inflated"""
        df_now = generate_ltc_cost_comparison('National', 0)
        df_future = generate_ltc_cost_comparison('National', 10)
        
        # Future costs should be higher
        for care_type in df_now['Care Type']:
            current_cost = df_now[df_now['Care Type'] == care_type]['Projected Annual Cost'].values[0]
            future_cost = df_future[df_future['Care Type'] == care_type]['Projected Annual Cost'].values[0]
            
            assert future_cost > current_cost
    
    def test_state_specific_comparison(self):
        """Test state-specific cost comparison"""
        df_ca = generate_ltc_cost_comparison('CA', 0)
        df_tx = generate_ltc_cost_comparison('TX', 0)
        
        # California should be more expensive than Texas
        ca_nursing = df_ca[df_ca['Care Type'].str.contains('Nursing Home - Private')]['Current Annual Cost'].values[0]
        tx_nursing = df_tx[df_tx['Care Type'].str.contains('Nursing Home - Private')]['Current Annual Cost'].values[0]
        
        assert ca_nursing > tx_nursing


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

# Made with Bob
