"""
Comprehensive tests for estate tax calculations module.

Tests cover:
- Federal estate tax calculations
- TCJA sunset modeling
- State estate taxes
- Inheritance taxes
- Generation-Skipping Transfer Tax (GSTT)
- Comprehensive estate tax analysis
"""

import pytest
from estate_tax_calculations import (
    calculate_federal_estate_tax,
    calculate_state_estate_tax,
    calculate_inheritance_tax,
    calculate_gstt,
    calculate_comprehensive_estate_tax,
    compare_tcja_sunset_impact,
    get_federal_exemption,
    is_tcja_in_effect,
    get_annual_gift_exclusion,
    calculate_lifetime_gift_impact,
    FEDERAL_ESTATE_TAX_EXEMPTIONS,
    STATE_ESTATE_TAXES,
    STATE_INHERITANCE_TAXES,
)


class TestFederalEstateTax:
    """Tests for federal estate tax calculations."""
    
    def test_estate_below_exemption_2024(self):
        """Test estate below exemption threshold."""
        result = calculate_federal_estate_tax(
            gross_estate=10_000_000,
            year=2024,
        )
        
        assert result.gross_estate == 10_000_000
        assert result.exemption_available == FEDERAL_ESTATE_TAX_EXEMPTIONS[2024]
        assert result.taxable_estate == 0
        assert result.estate_tax == 0
        assert result.effective_rate == 0
        assert result.tcja_in_effect is True
    
    def test_estate_above_exemption_2024(self):
        """Test estate above exemption threshold."""
        result = calculate_federal_estate_tax(
            gross_estate=20_000_000,
            year=2024,
        )
        
        exemption = FEDERAL_ESTATE_TAX_EXEMPTIONS[2024]
        expected_taxable = 20_000_000 - exemption
        expected_tax = expected_taxable * 0.40
        
        assert result.gross_estate == 20_000_000
        assert result.taxable_estate == expected_taxable
        assert result.estate_tax == expected_tax
        assert result.effective_rate == expected_tax / 20_000_000
        assert result.tcja_in_effect is True
    
    def test_tcja_sunset_2026(self):
        """Test TCJA sunset impact in 2026."""
        # Same estate in 2025 vs 2026
        result_2025 = calculate_federal_estate_tax(
            gross_estate=15_000_000,
            year=2025,
        )
        
        result_2026 = calculate_federal_estate_tax(
            gross_estate=15_000_000,
            year=2026,
        )
        
        # 2025 should have higher exemption (TCJA in effect)
        assert result_2025.exemption_available > result_2026.exemption_available
        assert result_2025.tcja_in_effect is True
        assert result_2026.tcja_in_effect is False
        
        # 2026 should have higher tax
        assert result_2026.estate_tax > result_2025.estate_tax
    
    def test_portability(self):
        """Test portability from deceased spouse."""
        # First spouse dies with $5M estate, leaving $8.61M unused exemption
        result = calculate_federal_estate_tax(
            gross_estate=20_000_000,
            year=2024,
            portability_from_spouse=8_610_000,
        )
        
        # Total exemption should include portability
        base_exemption = FEDERAL_ESTATE_TAX_EXEMPTIONS[2024]
        expected_total = base_exemption + 8_610_000
        
        assert result.exemption_available == expected_total
        assert result.taxable_estate == max(0, 20_000_000 - expected_total)
    
    def test_prior_exemption_used(self):
        """Test with prior lifetime gifts using exemption."""
        result = calculate_federal_estate_tax(
            gross_estate=15_000_000,
            year=2024,
            prior_exemption_used=5_000_000,
        )
        
        base_exemption = FEDERAL_ESTATE_TAX_EXEMPTIONS[2024]
        expected_available = base_exemption - 5_000_000
        
        assert result.exemption_available == expected_available
        assert result.taxable_estate == 15_000_000 - expected_available
    
    def test_portability_calculation(self):
        """Test portability available for surviving spouse."""
        result = calculate_federal_estate_tax(
            gross_estate=5_000_000,
            year=2024,
        )
        
        base_exemption = FEDERAL_ESTATE_TAX_EXEMPTIONS[2024]
        expected_portability = base_exemption - 5_000_000
        
        assert result.portability_available == expected_portability


class TestStateEstateTax:
    """Tests for state estate tax calculations."""
    
    def test_no_estate_tax_state(self):
        """Test state with no estate tax."""
        result = calculate_state_estate_tax(
            gross_estate=10_000_000,
            state_code='FL',  # Florida has no estate tax
        )
        
        assert result is None
    
    def test_massachusetts_estate_tax(self):
        """Test Massachusetts estate tax (lowest exemption)."""
        result = calculate_state_estate_tax(
            gross_estate=3_000_000,
            state_code='MA',
        )
        
        assert result is not None
        assert result.state == 'MA'
        assert result.exemption == 2_000_000
        assert result.taxable_estate == 1_000_000
        assert result.estate_tax > 0
    
    def test_oregon_estate_tax(self):
        """Test Oregon estate tax (also low exemption)."""
        result = calculate_state_estate_tax(
            gross_estate=2_000_000,
            state_code='OR',
        )
        
        assert result is not None
        assert result.state == 'OR'
        assert result.exemption == 1_000_000
        assert result.taxable_estate == 1_000_000
        assert result.estate_tax > 0
    
    def test_connecticut_matches_federal(self):
        """Test Connecticut (matches federal exemption)."""
        result = calculate_state_estate_tax(
            gross_estate=15_000_000,
            state_code='CT',
        )
        
        assert result is not None
        assert result.state == 'CT'
        assert result.exemption == 13_610_000  # Matches federal 2024
        assert result.taxable_estate == 15_000_000 - 13_610_000
    
    def test_washington_progressive_rates(self):
        """Test Washington state with progressive rates."""
        result = calculate_state_estate_tax(
            gross_estate=10_000_000,
            state_code='WA',
        )
        
        assert result is not None
        assert result.state == 'WA'
        assert result.estate_tax > 0
        assert result.effective_rate > 0


class TestInheritanceTax:
    """Tests for inheritance tax calculations."""
    
    def test_no_inheritance_tax_state(self):
        """Test state with no inheritance tax."""
        result = calculate_inheritance_tax(
            inheritance_amount=1_000_000,
            relationship='child',
            state_code='NY',  # New York has no inheritance tax
        )
        
        assert result is None
    
    def test_pennsylvania_child_inheritance(self):
        """Test Pennsylvania inheritance tax for child."""
        result = calculate_inheritance_tax(
            inheritance_amount=1_000_000,
            relationship='child',
            state_code='PA',
            beneficiary_name='John Doe',
        )
        
        assert result is not None
        assert result.state == 'PA'
        assert result.relationship == 'child'
        assert result.inheritance_tax == 1_000_000 * 0.045  # 4.5% for children
    
    def test_pennsylvania_sibling_inheritance(self):
        """Test Pennsylvania inheritance tax for sibling."""
        result = calculate_inheritance_tax(
            inheritance_amount=500_000,
            relationship='sibling',
            state_code='PA',
        )
        
        assert result is not None
        assert result.inheritance_tax == 500_000 * 0.12  # 12% for siblings
    
    def test_nebraska_with_exemption(self):
        """Test Nebraska inheritance tax with exemption."""
        result = calculate_inheritance_tax(
            inheritance_amount=100_000,
            relationship='child',
            state_code='NE',
        )
        
        assert result is not None
        assert result.exemption == 40_000
        assert result.taxable_amount == 60_000
        assert result.inheritance_tax == 60_000 * 0.01  # 1% for children
    
    def test_spouse_exempt(self):
        """Test that spouse is exempt from inheritance tax."""
        result = calculate_inheritance_tax(
            inheritance_amount=5_000_000,
            relationship='spouse',
            state_code='PA',
        )
        
        assert result is not None
        assert result.inheritance_tax == 0  # Spouse is exempt


class TestGSTT:
    """Tests for Generation-Skipping Transfer Tax."""
    
    def test_gstt_below_exemption(self):
        """Test GSTT with transfer below exemption."""
        result = calculate_gstt(
            transfer_amount=5_000_000,
            year=2024,
        )
        
        assert result.transfer_amount == 5_000_000
        assert result.exemption_available == FEDERAL_ESTATE_TAX_EXEMPTIONS[2024]
        assert result.taxable_amount == 0
        assert result.gstt_tax == 0
    
    def test_gstt_above_exemption(self):
        """Test GSTT with transfer above exemption."""
        exemption = FEDERAL_ESTATE_TAX_EXEMPTIONS[2024]
        transfer = exemption + 5_000_000
        
        result = calculate_gstt(
            transfer_amount=transfer,
            year=2024,
        )
        
        assert result.taxable_amount == 5_000_000
        assert result.gstt_tax == 5_000_000 * 0.40  # 40% rate
    
    def test_gstt_with_prior_exemption_used(self):
        """Test GSTT with prior exemption already used."""
        result = calculate_gstt(
            transfer_amount=10_000_000,
            year=2024,
            prior_exemption_used=8_000_000,
        )
        
        base_exemption = FEDERAL_ESTATE_TAX_EXEMPTIONS[2024]
        available = base_exemption - 8_000_000
        expected_taxable = 10_000_000 - available
        
        assert result.exemption_available == available
        assert result.taxable_amount == expected_taxable
        assert result.gstt_tax == expected_taxable * 0.40
    
    def test_gstt_sunset_impact(self):
        """Test GSTT exemption reduction after TCJA sunset."""
        # Same transfer in 2025 vs 2026
        result_2025 = calculate_gstt(
            transfer_amount=10_000_000,
            year=2025,
        )
        
        result_2026 = calculate_gstt(
            transfer_amount=10_000_000,
            year=2026,
        )
        
        # 2026 should have lower exemption and higher tax
        assert result_2026.exemption_available < result_2025.exemption_available
        assert result_2026.gstt_tax > result_2025.gstt_tax


class TestComprehensiveEstateTax:
    """Tests for comprehensive estate tax analysis."""
    
    def test_federal_only(self):
        """Test comprehensive analysis with federal tax only."""
        result = calculate_comprehensive_estate_tax(
            gross_estate=20_000_000,
            year=2024,
        )
        
        assert result.federal_result is not None
        assert result.state_result is None
        assert len(result.inheritance_results) == 0
        assert result.gstt_result is None
        assert result.total_estate_tax == result.federal_result.estate_tax
        assert result.total_tax_burden == result.federal_result.estate_tax
    
    def test_federal_and_state(self):
        """Test comprehensive analysis with federal and state taxes."""
        result = calculate_comprehensive_estate_tax(
            gross_estate=15_000_000,
            year=2024,
            state_code='NY',
        )
        
        assert result.federal_result is not None
        assert result.state_result is not None
        assert result.total_estate_tax == (
            result.federal_result.estate_tax + result.state_result.estate_tax
        )
    
    def test_with_beneficiaries(self):
        """Test comprehensive analysis with inheritance taxes."""
        beneficiaries = [
            {'name': 'Child 1', 'relationship': 'child', 'amount': 2_000_000},
            {'name': 'Child 2', 'relationship': 'child', 'amount': 2_000_000},
            {'name': 'Sibling', 'relationship': 'sibling', 'amount': 500_000},
        ]
        
        result = calculate_comprehensive_estate_tax(
            gross_estate=10_000_000,
            year=2024,
            state_code='PA',
            beneficiaries=beneficiaries,
        )
        
        assert len(result.inheritance_results) == 3
        assert result.total_inheritance_tax > 0
    
    def test_with_gstt(self):
        """Test comprehensive analysis with GSTT."""
        result = calculate_comprehensive_estate_tax(
            gross_estate=20_000_000,
            year=2024,
            skip_person_transfers=5_000_000,
        )
        
        assert result.gstt_result is not None
        assert result.total_gstt_tax == result.gstt_result.gstt_tax
        assert result.total_tax_burden == (
            result.total_estate_tax + result.total_gstt_tax
        )
    
    def test_complete_scenario(self):
        """Test complete scenario with all tax types."""
        beneficiaries = [
            {'name': 'Child 1', 'relationship': 'child', 'amount': 3_000_000},
            {'name': 'Child 2', 'relationship': 'child', 'amount': 3_000_000},
        ]
        
        result = calculate_comprehensive_estate_tax(
            gross_estate=25_000_000,
            year=2024,
            state_code='NY',
            beneficiaries=beneficiaries,
            skip_person_transfers=5_000_000,
            prior_exemption_used=2_000_000,
        )
        
        assert result.federal_result is not None
        assert result.state_result is not None
        assert result.gstt_result is not None
        assert result.total_tax_burden > 0
        assert result.net_to_heirs == result.federal_result.gross_estate - result.total_tax_burden
        assert 0 <= result.effective_total_rate <= 1


class TestTCJASunsetComparison:
    """Tests for TCJA sunset impact comparison."""
    
    def test_sunset_comparison_basic(self):
        """Test basic TCJA sunset comparison."""
        comparison = compare_tcja_sunset_impact(
            gross_estate=15_000_000,
        )
        
        assert 'year_2025' in comparison
        assert 'year_2026' in comparison
        assert 'impact' in comparison
        
        # 2026 should have higher tax due to lower exemption
        assert comparison['year_2026']['total_tax'] > comparison['year_2025']['total_tax']
        assert comparison['impact']['tax_increase'] > 0
    
    def test_sunset_comparison_with_state(self):
        """Test TCJA sunset comparison with state taxes."""
        comparison = compare_tcja_sunset_impact(
            gross_estate=20_000_000,
            state_code='NY',
        )
        
        assert comparison['state'] == 'NY'
        assert comparison['impact']['exemption_reduction'] > 0
        assert comparison['impact']['tax_increase'] > 0
    
    def test_sunset_comparison_below_2026_exemption(self):
        """Test comparison for estate below 2026 exemption."""
        # Estate that's below both exemptions
        comparison = compare_tcja_sunset_impact(
            gross_estate=6_000_000,
        )
        
        # Should have no tax in either year
        assert comparison['year_2025']['total_tax'] == 0
        assert comparison['year_2026']['total_tax'] == 0
        assert comparison['impact']['tax_increase'] == 0
    
    def test_sunset_comparison_between_exemptions(self):
        """Test comparison for estate between 2026 and 2025 exemptions."""
        # Estate that's above 2026 exemption but below 2025 exemption
        comparison = compare_tcja_sunset_impact(
            gross_estate=10_000_000,
        )
        
        # Should have no tax in 2025 but tax in 2026
        assert comparison['year_2025']['total_tax'] == 0
        assert comparison['year_2026']['total_tax'] > 0


class TestUtilityFunctions:
    """Tests for utility functions."""
    
    def test_get_federal_exemption_known_year(self):
        """Test getting exemption for known year."""
        exemption = get_federal_exemption(2024)
        assert exemption == FEDERAL_ESTATE_TAX_EXEMPTIONS[2024]
    
    def test_get_federal_exemption_future_year(self):
        """Test getting exemption for future year (projection)."""
        exemption = get_federal_exemption(2040)
        assert exemption > FEDERAL_ESTATE_TAX_EXEMPTIONS[2035]
    
    def test_is_tcja_in_effect(self):
        """Test TCJA status check."""
        assert is_tcja_in_effect(2024) is True
        assert is_tcja_in_effect(2025) is True
        assert is_tcja_in_effect(2026) is False
        assert is_tcja_in_effect(2027) is False
    
    def test_get_annual_gift_exclusion(self):
        """Test annual gift exclusion retrieval."""
        exclusion_2024 = get_annual_gift_exclusion(2024)
        assert exclusion_2024 == 18_000
        
        # Future year should be projected
        exclusion_2030 = get_annual_gift_exclusion(2030)
        assert exclusion_2030 >= 18_000
    
    def test_calculate_lifetime_gift_impact(self):
        """Test lifetime gift impact calculation."""
        result = calculate_lifetime_gift_impact(
            annual_gifts=20_000,  # $2k over exclusion per recipient
            years=10,
            num_recipients=3,
            year_start=2024,
        )
        
        assert result['total_gifts'] == 20_000 * 10 * 3
        assert result['exemption_used'] > 0  # Some gifts over exclusion
        assert result['within_exclusion'] > 0
        assert result['years'] == 10
        assert result['recipients'] == 3


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""
    
    def test_zero_estate(self):
        """Test with zero estate value."""
        result = calculate_federal_estate_tax(
            gross_estate=0,
            year=2024,
        )
        
        assert result.estate_tax == 0
        assert result.effective_rate == 0
    
    def test_negative_estate(self):
        """Test with negative estate value (debts exceed assets)."""
        result = calculate_federal_estate_tax(
            gross_estate=-1_000_000,
            year=2024,
        )
        
        assert result.estate_tax == 0
    
    def test_very_large_estate(self):
        """Test with very large estate."""
        result = calculate_federal_estate_tax(
            gross_estate=1_000_000_000,  # $1 billion
            year=2024,
        )
        
        assert result.estate_tax > 0
        assert result.effective_rate > 0
        assert result.effective_rate < 0.40  # Should be less than max rate
    
    def test_exemption_exactly_used(self):
        """Test when estate exactly equals exemption."""
        exemption = FEDERAL_ESTATE_TAX_EXEMPTIONS[2024]
        result = calculate_federal_estate_tax(
            gross_estate=exemption,
            year=2024,
        )
        
        assert result.taxable_estate == 0
        assert result.estate_tax == 0
        assert result.portability_available == 0


class TestStateSpecificRules:
    """Tests for state-specific estate tax rules."""
    
    def test_massachusetts_cliff_tax(self):
        """Test Massachusetts cliff tax (no exemption if over threshold)."""
        # Just over the exemption
        result = calculate_state_estate_tax(
            gross_estate=2_100_000,
            state_code='MA',
        )
        
        assert result is not None
        # MA has cliff tax - entire estate is taxable if over exemption
        assert result.estate_tax > 0
    
    def test_new_york_cliff_tax(self):
        """Test New York cliff tax (if estate > 105% of exemption)."""
        exemption = STATE_ESTATE_TAXES['NY']['exemption']
        
        # Just over 105% threshold
        result = calculate_state_estate_tax(
            gross_estate=exemption * 1.06,
            state_code='NY',
        )
        
        assert result is not None
        assert result.estate_tax > 0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

# Made with Bob
