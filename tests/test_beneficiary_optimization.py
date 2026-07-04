"""
Comprehensive tests for beneficiary optimization module.

Tests cover:
- SECURE Act 2.0 10-year rule
- Stretch IRA for Eligible Designated Beneficiaries
- Spousal rollover vs. inherited IRA comparison
- Trust beneficiary modeling
- Beneficiary strategy comparisons
"""

import pytest
from beneficiary_optimization import (
    calculate_inherited_ira_10_year_rule,
    calculate_stretch_ira,
    compare_spousal_options,
    calculate_trust_beneficiary,
    get_rmd_start_age,
    get_life_expectancy,
    is_eligible_designated_beneficiary,
    compare_beneficiary_strategies,
)


class TestRMDStartAge:
    """Tests for RMD starting age (SECURE Act 2.0)."""
    
    def test_rmd_age_2023(self):
        """Test RMD age for 2023."""
        assert get_rmd_start_age(2023) == 73
    
    def test_rmd_age_2033(self):
        """Test RMD age for 2033 and beyond."""
        assert get_rmd_start_age(2033) == 75
        assert get_rmd_start_age(2040) == 75
    
    def test_rmd_age_pre_secure_2(self):
        """Test RMD age before SECURE Act 2.0."""
        assert get_rmd_start_age(2022) == 72


class TestLifeExpectancy:
    """Tests for life expectancy tables."""
    
    def test_uniform_table(self):
        """Test uniform lifetime table lookup."""
        assert get_life_expectancy(75, 'uniform') == 24.6
        assert get_life_expectancy(85, 'uniform') == 16.0
    
    def test_single_table(self):
        """Test single life expectancy table lookup."""
        assert get_life_expectancy(50, 'single') == 36.5
        assert get_life_expectancy(70, 'single') == 19.8


class TestEligibleDesignatedBeneficiary:
    """Tests for EDB qualification."""
    
    def test_spouse_always_edb(self):
        """Test that spouse is always EDB."""
        assert is_eligible_designated_beneficiary('spouse', 50, 70) is True
    
    def test_minor_child_edb(self):
        """Test minor child as EDB."""
        assert is_eligible_designated_beneficiary('minor_child', 18, 70) is True
        assert is_eligible_designated_beneficiary('minor_child', 21, 70) is False
    
    def test_disabled_edb(self):
        """Test disabled individual as EDB."""
        assert is_eligible_designated_beneficiary('other', 40, 70, is_disabled=True) is True
    
    def test_not_more_than_10_years_younger(self):
        """Test beneficiary not more than 10 years younger."""
        assert is_eligible_designated_beneficiary('other', 65, 70) is True
        assert is_eligible_designated_beneficiary('other', 55, 70) is False


class TestInheritedIRA10YearRule:
    """Tests for 10-year rule calculations."""
    
    def test_basic_10_year_calculation(self):
        """Test basic 10-year rule calculation."""
        result = calculate_inherited_ira_10_year_rule(
            initial_balance=500_000,
            beneficiary_age=45,
            beneficiary_tax_rate=0.24,
            annual_growth_rate=0.07,
        )
        
        assert result.initial_balance == 500_000
        assert result.beneficiary_type == 'non-spouse'
        assert result.is_edb is False
        assert result.distribution_method == '10-year'
        assert len(result.annual_distributions) == 10
        assert result.total_distributions > 500_000  # Growth
        assert result.total_taxes_paid > 0
        assert result.net_to_beneficiary > 0
    
    def test_roth_ira_10_year(self):
        """Test 10-year rule with Roth IRA (tax-free)."""
        result = calculate_inherited_ira_10_year_rule(
            initial_balance=500_000,
            beneficiary_age=45,
            beneficiary_tax_rate=0.24,
            account_type='Roth IRA',
        )
        
        assert result.total_taxes_paid == 0
        assert result.net_to_beneficiary == result.total_distributions
    
    def test_high_growth_scenario(self):
        """Test with high growth rate."""
        result = calculate_inherited_ira_10_year_rule(
            initial_balance=500_000,
            beneficiary_age=45,
            beneficiary_tax_rate=0.24,
            annual_growth_rate=0.12,
        )
        
        assert result.total_distributions > 700_000  # Significant growth


class TestStretchIRA:
    """Tests for stretch IRA calculations."""
    
    def test_basic_stretch_calculation(self):
        """Test basic stretch IRA calculation."""
        result = calculate_stretch_ira(
            initial_balance=500_000,
            beneficiary_age=45,
            beneficiary_tax_rate=0.24,
            annual_growth_rate=0.07,
        )
        
        assert result.beneficiary_age == 45
        assert result.life_expectancy > 0
        assert len(result.annual_rmds) > 10  # Should last many years
        assert result.total_distributions > 500_000
        assert result.total_growth > 0
        assert result.net_inherited > 0
    
    def test_stretch_vs_10_year(self):
        """Test that stretch provides more total distributions than 10-year."""
        stretch_result = calculate_stretch_ira(
            initial_balance=500_000,
            beneficiary_age=45,
            beneficiary_tax_rate=0.24,
        )
        
        ten_year_result = calculate_inherited_ira_10_year_rule(
            initial_balance=500_000,
            beneficiary_age=45,
            beneficiary_tax_rate=0.24,
        )
        
        # Stretch should provide more total distributions due to longer growth period
        assert stretch_result.total_distributions > ten_year_result.total_distributions
    
    def test_older_beneficiary_shorter_stretch(self):
        """Test that older beneficiaries have shorter stretch periods."""
        young_result = calculate_stretch_ira(
            initial_balance=500_000,
            beneficiary_age=30,
        )
        
        old_result = calculate_stretch_ira(
            initial_balance=500_000,
            beneficiary_age=70,
        )
        
        assert young_result.years_of_distributions > old_result.years_of_distributions


class TestSpousalOptions:
    """Tests for spousal beneficiary options."""
    
    def test_spousal_comparison_young_spouse(self):
        """Test spousal options for young spouse (under RMD age)."""
        result = compare_spousal_options(
            initial_balance=800_000,
            spouse_age=55,
            spouse_tax_rate=0.24,
        )
        
        assert result.rollover_option is not None
        assert result.inherited_option is not None
        assert result.recommended_option in ['rollover', 'inherited']
        assert len(result.key_factors) > 0
        assert result.savings_amount >= 0
    
    def test_spousal_comparison_old_spouse(self):
        """Test spousal options for older spouse (over RMD age)."""
        result = compare_spousal_options(
            initial_balance=800_000,
            spouse_age=75,
            spouse_tax_rate=0.24,
        )
        
        assert result.rollover_option is not None
        assert result.inherited_option is not None
        assert result.recommended_option in ['rollover', 'inherited']
    
    def test_spousal_options_roth(self):
        """Test spousal options with Roth IRA."""
        result = compare_spousal_options(
            initial_balance=800_000,
            spouse_age=62,
            spouse_tax_rate=0.24,
            account_type='Roth IRA',
        )
        
        # Roth should have no taxes
        assert result.rollover_option.total_taxes_paid == 0
        assert result.inherited_option.total_taxes_paid == 0


class TestTrustBeneficiary:
    """Tests for trust as beneficiary."""
    
    def test_conduit_trust(self):
        """Test conduit trust (passes through distributions)."""
        result = calculate_trust_beneficiary(
            initial_balance=1_000_000,
            trust_type='conduit',
            oldest_beneficiary_age=40,
        )
        
        assert result.trust_type == 'conduit'
        assert result.qualifies_as_designated_beneficiary is True
        assert result.total_trust_taxes >= 0
        assert result.total_beneficiary_taxes > 0  # Beneficiaries pay tax
        assert result.net_to_beneficiaries > 0
    
    def test_accumulation_trust(self):
        """Test accumulation trust (trust pays taxes)."""
        result = calculate_trust_beneficiary(
            initial_balance=1_000_000,
            trust_type='accumulation',
            oldest_beneficiary_age=40,
        )
        
        assert result.trust_type == 'accumulation'
        assert result.qualifies_as_designated_beneficiary is False
        assert result.total_trust_taxes > 0  # Trust pays tax at high rates
    
    def test_see_through_trust(self):
        """Test see-through trust (hybrid)."""
        result = calculate_trust_beneficiary(
            initial_balance=1_000_000,
            trust_type='see-through',
            oldest_beneficiary_age=40,
        )
        
        assert result.trust_type == 'see-through'
        assert result.qualifies_as_designated_beneficiary is True
    
    def test_trust_admin_costs(self):
        """Test that trust administration costs are included."""
        result = calculate_trust_beneficiary(
            initial_balance=1_000_000,
            trust_type='conduit',
            oldest_beneficiary_age=40,
            annual_admin_cost=10_000,
        )
        
        assert result.trust_administration_costs > 0
        assert result.trust_administration_costs >= 10_000


class TestBeneficiaryComparison:
    """Tests for comparing multiple beneficiary strategies."""
    
    def test_compare_strategies(self):
        """Test comparing multiple beneficiary strategies."""
        scenarios = [
            {
                'name': 'Child (10-year)',
                'beneficiary_type': 'non-spouse',
                'age': 45,
                'tax_rate': 0.24,
            },
            {
                'name': 'Spouse (rollover)',
                'beneficiary_type': 'spouse',
                'age': 62,
                'tax_rate': 0.24,
            },
            {
                'name': 'Trust',
                'beneficiary_type': 'trust',
                'trust_type': 'conduit',
                'age': 40,
            },
        ]
        
        df = compare_beneficiary_strategies(
            initial_balance=1_000_000,
            scenarios=scenarios,
        )
        
        assert len(df) == 3
        assert 'Scenario' in df.columns
        assert 'Net to Beneficiary' in df.columns
        assert all(df['Net to Beneficiary'] > 0)


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""
    
    def test_zero_balance(self):
        """Test with zero IRA balance."""
        result = calculate_inherited_ira_10_year_rule(
            initial_balance=0,
            beneficiary_age=45,
        )
        
        assert result.total_distributions == 0
        assert result.total_taxes_paid == 0
    
    def test_very_high_tax_rate(self):
        """Test with very high tax rate."""
        result = calculate_inherited_ira_10_year_rule(
            initial_balance=500_000,
            beneficiary_age=45,
            beneficiary_tax_rate=0.50,
        )
        
        assert result.effective_tax_rate > 0.40
    
    def test_very_old_beneficiary(self):
        """Test with very old beneficiary."""
        result = calculate_stretch_ira(
            initial_balance=500_000,
            beneficiary_age=95,
        )
        
        assert result.years_of_distributions < 10


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

# Made with Bob
