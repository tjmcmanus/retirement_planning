"""
Test Suite for Social Security Optimization Module

Tests all major functions and scenarios including:
- Spousal benefit calculations
- Survivor benefit calculations
- Break-even analysis
- Earnings test impact
- Couple optimization
- Edge cases and boundary conditions
"""

import pytest
import pandas as pd
from ss_optimization import (
    PersonProfile,
    ClaimingStrategy,
    BreakEvenAnalysis,
    EarningsTestImpact,
    calculate_spousal_benefit,
    calculate_survivor_benefit,
    calculate_earnings_test_impact,
    calculate_break_even_age,
    calculate_lifetime_benefits,
    calculate_net_present_value,
    optimize_couple_claiming_strategy,
    generate_claiming_age_comparison,
    FULL_RETIREMENT_AGE,
    MIN_CLAIMING_AGE,
    MAX_BENEFIT_AGE,
    SPOUSAL_BENEFIT_RATE,
    EARNINGS_TEST_LIMIT_UNDER_FRA,
    DEFAULT_LIFE_EXPECTANCY_MALE,
    DEFAULT_LIFE_EXPECTANCY_FEMALE
)


class TestPersonProfile:
    """Test PersonProfile dataclass"""
    
    def test_person_profile_creation(self):
        """Test creating a person profile"""
        person = PersonProfile(
            name="John",
            birth_year=1960,
            fra_benefit=3000,
            gender='M'
        )
        assert person.name == "John"
        assert person.birth_year == 1960
        assert person.fra_benefit == 3000
        assert person.gender == 'M'
        assert person.life_expectancy == DEFAULT_LIFE_EXPECTANCY_MALE
        assert person.current_earnings == 0
    
    def test_person_profile_custom_life_expectancy(self):
        """Test custom life expectancy"""
        person = PersonProfile(
            name="Jane",
            birth_year=1962,
            fra_benefit=2500,
            gender='F',
            life_expectancy=90
        )
        assert person.life_expectancy == 90
    
    def test_person_profile_with_earnings(self):
        """Test profile with current earnings"""
        person = PersonProfile(
            name="Bob",
            birth_year=1965,
            fra_benefit=2800,
            gender='M',
            current_earnings=50000
        )
        assert person.current_earnings == 50000


class TestSpousalBenefits:
    """Test spousal benefit calculations"""
    
    def test_spousal_benefit_at_fra(self):
        """Test spousal benefit when both claim at FRA"""
        worker_benefit = 3000
        spouse_benefit = 1200
        
        spousal = calculate_spousal_benefit(
            worker_fra_benefit=worker_benefit,
            spouse_fra_benefit=spouse_benefit,
            spouse_claiming_age=67,
            worker_claiming_age=67
        )
        
        # Spouse should get 50% of worker's FRA benefit
        expected = worker_benefit * SPOUSAL_BENEFIT_RATE
        assert spousal == expected
    
    def test_spousal_benefit_early_claiming(self):
        """Test spousal benefit with early claiming"""
        worker_benefit = 3000
        spouse_benefit = 1000
        
        spousal = calculate_spousal_benefit(
            worker_fra_benefit=worker_benefit,
            spouse_fra_benefit=spouse_benefit,
            spouse_claiming_age=62,  # Early claiming
            worker_claiming_age=67
        )
        
        # Spousal benefit should be reduced for early claiming
        max_spousal = worker_benefit * SPOUSAL_BENEFIT_RATE
        assert spousal < max_spousal
        assert spousal > spouse_benefit  # But still better than own benefit
    
    def test_spousal_benefit_own_higher(self):
        """Test when own benefit is higher than spousal"""
        worker_benefit = 2000
        spouse_benefit = 2500
        
        spousal = calculate_spousal_benefit(
            worker_fra_benefit=worker_benefit,
            spouse_fra_benefit=spouse_benefit,
            spouse_claiming_age=67,
            worker_claiming_age=67
        )
        
        # Should get own benefit since it's higher
        assert spousal == spouse_benefit
    
    def test_spousal_benefit_delayed_worker(self):
        """Test spousal benefit when worker delays"""
        worker_benefit = 3000
        spouse_benefit = 1200
        
        spousal = calculate_spousal_benefit(
            worker_fra_benefit=worker_benefit,
            spouse_fra_benefit=spouse_benefit,
            spouse_claiming_age=67,
            worker_claiming_age=70  # Worker delays
        )
        
        # Spousal benefit based on worker's FRA, not delayed amount
        expected = worker_benefit * SPOUSAL_BENEFIT_RATE
        assert spousal == expected


class TestSurvivorBenefits:
    """Test survivor benefit calculations"""
    
    def test_survivor_benefit_at_fra(self):
        """Test survivor benefit at FRA"""
        deceased_benefit = 3500
        survivor_benefit = 2000
        
        survivor = calculate_survivor_benefit(
            deceased_benefit=deceased_benefit,
            survivor_fra_benefit=survivor_benefit,
            survivor_claiming_age=67,
            deceased_claiming_age=70
        )
        
        # Survivor gets 100% of deceased's benefit
        assert survivor == deceased_benefit
    
    def test_survivor_benefit_early_claiming(self):
        """Test survivor benefit with early claiming"""
        deceased_benefit = 3500
        survivor_benefit = 2000
        
        survivor = calculate_survivor_benefit(
            deceased_benefit=deceased_benefit,
            survivor_fra_benefit=survivor_benefit,
            survivor_claiming_age=62,
            deceased_claiming_age=70
        )
        
        # Survivor benefit reduced for early claiming
        assert survivor < deceased_benefit
        assert survivor > survivor_benefit
    
    def test_survivor_benefit_own_higher(self):
        """Test when survivor's own benefit is higher"""
        deceased_benefit = 2000
        survivor_benefit = 3000
        
        survivor = calculate_survivor_benefit(
            deceased_benefit=deceased_benefit,
            survivor_fra_benefit=survivor_benefit,
            survivor_claiming_age=67,
            deceased_claiming_age=67
        )
        
        # Should get own benefit since it's higher
        assert survivor == survivor_benefit


class TestEarningsTest:
    """Test earnings test impact calculations"""
    
    def test_no_earnings_test_at_fra(self):
        """Test no earnings test at or after FRA"""
        impact = calculate_earnings_test_impact(
            annual_earnings=100000,
            age=67,
            monthly_benefit=2500
        )
        
        assert impact.annual_reduction == 0
        assert impact.monthly_benefit_after == impact.monthly_benefit_before
        assert impact.months_withheld == 0
    
    def test_earnings_test_under_fra(self):
        """Test earnings test under FRA"""
        impact = calculate_earnings_test_impact(
            annual_earnings=50000,
            age=64,
            monthly_benefit=2000
        )
        
        # Should have reduction since earnings exceed limit
        assert impact.annual_reduction > 0
        assert impact.monthly_benefit_after < impact.monthly_benefit_before
        assert impact.months_withheld > 0
    
    def test_earnings_test_under_limit(self):
        """Test earnings under the limit"""
        impact = calculate_earnings_test_impact(
            annual_earnings=20000,  # Under limit
            age=64,
            monthly_benefit=2000
        )
        
        # No reduction since under limit
        assert impact.annual_reduction == 0
        assert impact.monthly_benefit_after == impact.monthly_benefit_before
    
    def test_earnings_test_fra_year(self):
        """Test earnings test in year reaching FRA"""
        impact = calculate_earnings_test_impact(
            annual_earnings=80000,
            age=66,  # Year reaching FRA
            monthly_benefit=2500
        )
        
        # Should have reduction but with different rate
        assert impact.annual_reduction > 0
        # FRA year has higher limit and lower reduction rate


class TestBreakEvenAnalysis:
    """Test break-even analysis"""
    
    def test_break_even_62_vs_70(self):
        """Test break-even between age 62 and 70"""
        analysis = calculate_break_even_age(
            fra_benefit=2500,
            early_age=62,
            late_age=70,
            cola_rate=0.02
        )
        
        assert analysis.early_age == 62
        assert analysis.late_age == 70
        assert analysis.break_even_age > 70  # Should be in 80s
        assert analysis.break_even_age < 90
        assert analysis.monthly_difference > 0
        assert analysis.years_to_break_even > 0
    
    def test_break_even_67_vs_70(self):
        """Test break-even between FRA and 70"""
        analysis = calculate_break_even_age(
            fra_benefit=2500,
            early_age=67,
            late_age=70,
            cola_rate=0.02
        )
        
        assert analysis.break_even_age > 70
        # Break-even for 67 vs 70 should be earlier than 62 vs 70
        assert analysis.break_even_age < 90
    
    def test_break_even_with_high_cola(self):
        """Test break-even with higher COLA"""
        analysis_low = calculate_break_even_age(
            fra_benefit=2500,
            early_age=62,
            late_age=70,
            cola_rate=0.02
        )
        
        analysis_high = calculate_break_even_age(
            fra_benefit=2500,
            early_age=62,
            late_age=70,
            cola_rate=0.04
        )
        
        # Higher COLA should favor early claiming (higher break-even age)
        assert analysis_high.break_even_age >= analysis_low.break_even_age


class TestLifetimeBenefits:
    """Test lifetime benefit calculations"""
    
    def test_lifetime_benefits_basic(self):
        """Test basic lifetime benefits calculation"""
        lifetime = calculate_lifetime_benefits(
            fra_benefit=2500,
            claiming_age=67,
            life_expectancy=87,
            cola_rate=0.02
        )
        
        # Should be positive and reasonable
        assert lifetime > 0
        # Rough check: 20 years * 12 months * ~2500 = ~600k
        assert lifetime > 500000
        assert lifetime < 1000000
    
    def test_lifetime_benefits_early_vs_late(self):
        """Test that delayed claiming can have higher lifetime benefits"""
        early = calculate_lifetime_benefits(
            fra_benefit=2500,
            claiming_age=62,
            life_expectancy=87,
            cola_rate=0.02
        )
        
        late = calculate_lifetime_benefits(
            fra_benefit=2500,
            claiming_age=70,
            life_expectancy=87,
            cola_rate=0.02
        )
        
        # With long life expectancy, delayed claiming should win
        assert late > early
    
    def test_lifetime_benefits_short_life(self):
        """Test with shorter life expectancy"""
        early = calculate_lifetime_benefits(
            fra_benefit=2500,
            claiming_age=62,
            life_expectancy=75,  # Shorter
            cola_rate=0.02
        )
        
        late = calculate_lifetime_benefits(
            fra_benefit=2500,
            claiming_age=70,
            life_expectancy=75,
            cola_rate=0.02
        )
        
        # With short life expectancy, early claiming should win
        assert early > late


class TestNPVCalculations:
    """Test net present value calculations"""
    
    def test_npv_basic(self):
        """Test basic NPV calculation"""
        npv = calculate_net_present_value(
            fra_benefit=2500,
            claiming_age=67,
            life_expectancy=87,
            discount_rate=0.03,
            cola_rate=0.02
        )
        
        assert npv > 0
        # NPV should be less than lifetime total due to discounting
        lifetime = calculate_lifetime_benefits(2500, 67, 87, 0.02)
        assert npv < lifetime
    
    def test_npv_higher_discount_rate(self):
        """Test NPV with different discount rates"""
        npv_low = calculate_net_present_value(
            fra_benefit=2500,
            claiming_age=67,
            life_expectancy=87,
            discount_rate=0.02,
            cola_rate=0.02
        )
        
        npv_high = calculate_net_present_value(
            fra_benefit=2500,
            claiming_age=67,
            life_expectancy=87,
            discount_rate=0.05,
            cola_rate=0.02
        )
        
        # Higher discount rate should result in lower NPV
        assert npv_high < npv_low


class TestCoupleOptimization:
    """Test couple claiming strategy optimization"""
    
    def test_couple_optimization_basic(self):
        """Test basic couple optimization"""
        person1 = PersonProfile(
            name="John",
            birth_year=1960,
            fra_benefit=3000,
            gender='M',
            life_expectancy=84
        )
        
        person2 = PersonProfile(
            name="Jane",
            birth_year=1962,
            fra_benefit=2000,
            gender='F',
            life_expectancy=87
        )
        
        strategies = optimize_couple_claiming_strategy(person1, person2)
        
        # Should return multiple strategies
        assert len(strategies) > 0
        assert len(strategies) <= 16  # 4 ages x 4 ages
        
        # Should be sorted by NPV (highest first)
        for i in range(len(strategies) - 1):
            assert strategies[i].net_present_value >= strategies[i+1].net_present_value
        
        # All strategies should have valid data
        for strategy in strategies:
            assert strategy.person1_claiming_age >= MIN_CLAIMING_AGE
            assert strategy.person1_claiming_age <= MAX_BENEFIT_AGE
            assert strategy.person2_claiming_age >= MIN_CLAIMING_AGE
            assert strategy.person2_claiming_age <= MAX_BENEFIT_AGE
            assert strategy.total_lifetime_benefits > 0
            assert strategy.net_present_value > 0
            assert len(strategy.notes) > 0
    
    def test_couple_optimization_equal_benefits(self):
        """Test optimization with equal benefits"""
        person1 = PersonProfile(
            name="Person1",
            birth_year=1960,
            fra_benefit=2500,
            gender='M'
        )
        
        person2 = PersonProfile(
            name="Person2",
            birth_year=1960,
            fra_benefit=2500,
            gender='F'
        )
        
        strategies = optimize_couple_claiming_strategy(person1, person2)
        
        assert len(strategies) > 0
        # With equal benefits and similar life expectancy, 
        # both delaying should be near optimal
        top_strategy = strategies[0]
        assert top_strategy.person1_claiming_age >= 67
        assert top_strategy.person2_claiming_age >= 67


class TestClaimingAgeComparison:
    """Test claiming age comparison table generation"""
    
    def test_comparison_table_generation(self):
        """Test generating comparison table"""
        df = generate_claiming_age_comparison(
            fra_benefit=2500,
            life_expectancy=87,
            cola_rate=0.02,
            discount_rate=0.03
        )
        
        # Should have rows for ages 62-70
        assert len(df) == 9
        
        # Should have all required columns
        required_columns = [
            'Claiming Age',
            'Monthly Benefit',
            'Annual Benefit',
            'Lifetime Total',
            'Net Present Value',
            'Break-Even Age',
            'Reduction/Increase'
        ]
        for col in required_columns:
            assert col in df.columns
        
        # Values should increase with age
        assert df['Monthly Benefit'].is_monotonic_increasing
        
        # NPV should be reasonable
        assert all(df['Net Present Value'] > 0)
    
    def test_comparison_table_values(self):
        """Test comparison table has reasonable values"""
        df = generate_claiming_age_comparison(
            fra_benefit=2500,
            life_expectancy=87,
            cola_rate=0.02,
            discount_rate=0.03
        )
        
        # Age 67 (FRA) should have no reduction/increase
        fra_row = df[df['Claiming Age'] == 67].iloc[0]
        assert '0.0%' in fra_row['Reduction/Increase']
        
        # Age 62 should show reduction
        early_row = df[df['Claiming Age'] == 62].iloc[0]
        assert '-' in early_row['Reduction/Increase']
        
        # Age 70 should show increase (check for positive percentage)
        late_row = df[df['Claiming Age'] == 70].iloc[0]
        # Extract percentage value and check it's positive
        pct_str = late_row['Reduction/Increase'].replace('%', '')
        assert float(pct_str) > 0


class TestEdgeCases:
    """Test edge cases and boundary conditions"""
    
    def test_minimum_claiming_age(self):
        """Test minimum claiming age (62)"""
        analysis = calculate_break_even_age(
            fra_benefit=2500,
            early_age=MIN_CLAIMING_AGE,
            late_age=67,
            cola_rate=0.02
        )
        assert analysis.early_age == MIN_CLAIMING_AGE
    
    def test_maximum_benefit_age(self):
        """Test maximum benefit age (70)"""
        analysis = calculate_break_even_age(
            fra_benefit=2500,
            early_age=67,
            late_age=MAX_BENEFIT_AGE,
            cola_rate=0.02
        )
        assert analysis.late_age == MAX_BENEFIT_AGE
    
    def test_zero_benefit(self):
        """Test with zero benefit amount"""
        lifetime = calculate_lifetime_benefits(
            fra_benefit=0,
            claiming_age=67,
            life_expectancy=87,
            cola_rate=0.02
        )
        assert lifetime == 0
    
    def test_very_high_benefit(self):
        """Test with very high benefit (max SS benefit ~$4,873 in 2024)"""
        lifetime = calculate_lifetime_benefits(
            fra_benefit=5000,
            claiming_age=67,
            life_expectancy=87,
            cola_rate=0.02
        )
        assert lifetime > 0
        assert lifetime < 3000000  # Reasonable upper bound
    
    def test_zero_cola(self):
        """Test with zero COLA"""
        analysis = calculate_break_even_age(
            fra_benefit=2500,
            early_age=62,
            late_age=70,
            cola_rate=0.0
        )
        assert analysis.break_even_age > 0
    
    def test_high_cola(self):
        """Test with high COLA"""
        analysis = calculate_break_even_age(
            fra_benefit=2500,
            early_age=62,
            late_age=70,
            cola_rate=0.10  # 10% COLA
        )
        assert analysis.break_even_age > 0


def test_all_functions_importable():
    """Test that all functions can be imported"""
    from ss_optimization import (
        calculate_spousal_benefit,
        calculate_survivor_benefit,
        calculate_earnings_test_impact,
        calculate_break_even_age,
        calculate_lifetime_benefits,
        calculate_net_present_value,
        optimize_couple_claiming_strategy,
        generate_claiming_age_comparison
    )
    assert callable(calculate_spousal_benefit)
    assert callable(calculate_survivor_benefit)
    assert callable(calculate_earnings_test_impact)
    assert callable(calculate_break_even_age)
    assert callable(calculate_lifetime_benefits)
    assert callable(calculate_net_present_value)
    assert callable(optimize_couple_claiming_strategy)
    assert callable(generate_claiming_age_comparison)


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v", "--tb=short"])

# Made with Bob
