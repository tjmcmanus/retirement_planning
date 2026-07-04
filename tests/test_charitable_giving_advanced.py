"""
Comprehensive tests for advanced charitable giving module.

Tests cover:
- Charitable Remainder Trusts (CRUT and CRAT)
- Charitable Lead Trusts (CLUT and CLAT)
- Private Foundation vs. DAF comparison
- Qualified Charitable Distributions (QCD)
"""

import pytest
from charitable_giving_advanced import (
    calculate_crt_crut,
    calculate_crt_crat,
    calculate_clt_clut,
    calculate_clt_clat,
    calculate_private_foundation,
    calculate_daf,
    compare_foundation_vs_daf,
    calculate_qcd_benefit,
    CRT_MIN_PAYOUT_RATE,
    CRT_MAX_PAYOUT_RATE,
)


class TestCRUT:
    """Tests for Charitable Remainder Unitrust."""
    
    def test_basic_crut(self):
        """Test basic CRUT calculation."""
        result = calculate_crt_crut(
            initial_funding=1_000_000,
            payout_rate=0.05,
            term_years=20,
            donor_age=65,
        )
        
        assert result.crt_type == 'CRUT'
        assert result.initial_funding == 1_000_000
        assert result.payout_rate == 0.05
        assert result.term_years == 20
        assert len(result.annual_payouts) == 20
        assert result.total_income_received > 0
        assert result.charitable_remainder > 0
        assert result.initial_tax_deduction > 0
    
    def test_crut_growth(self):
        """Test that CRUT payouts grow with trust value."""
        result = calculate_crt_crut(
            initial_funding=1_000_000,
            payout_rate=0.05,
            term_years=20,
            donor_age=65,
            growth_rate=0.08,
        )
        
        # Later payouts should be larger due to growth
        first_payout = result.annual_payouts[0]['payout']
        last_payout = result.annual_payouts[-1]['payout']
        assert last_payout > first_payout
    
    def test_crut_min_payout_rate(self):
        """Test CRUT with minimum payout rate."""
        result = calculate_crt_crut(
            initial_funding=1_000_000,
            payout_rate=CRT_MIN_PAYOUT_RATE,
            term_years=20,
            donor_age=65,
        )
        
        assert result.payout_rate == CRT_MIN_PAYOUT_RATE
    
    def test_crut_invalid_payout_rate(self):
        """Test that invalid payout rates raise error."""
        with pytest.raises(ValueError):
            calculate_crt_crut(
                initial_funding=1_000_000,
                payout_rate=0.03,  # Below minimum
                term_years=20,
                donor_age=65,
            )


class TestCRAT:
    """Tests for Charitable Remainder Annuity Trust."""
    
    def test_basic_crat(self):
        """Test basic CRAT calculation."""
        result = calculate_crt_crat(
            initial_funding=1_000_000,
            annual_payout=50_000,
            term_years=20,
            donor_age=65,
        )
        
        assert result.crt_type == 'CRAT'
        assert result.initial_funding == 1_000_000
        assert len(result.annual_payouts) == 20
        assert result.total_income_received > 0
        assert result.charitable_remainder > 0
    
    def test_crat_fixed_payout(self):
        """Test that CRAT payouts are fixed."""
        result = calculate_crt_crat(
            initial_funding=1_000_000,
            annual_payout=50_000,
            term_years=20,
            donor_age=65,
        )
        
        # All payouts should be the same (except possibly last if depleted)
        payouts = [p['payout'] for p in result.annual_payouts[:-1]]
        assert all(p == 50_000 for p in payouts)
    
    def test_crat_depletion(self):
        """Test CRAT with high payout that depletes trust."""
        result = calculate_crt_crat(
            initial_funding=500_000,
            annual_payout=100_000,  # High payout
            term_years=20,
            donor_age=65,
            growth_rate=0.03,  # Low growth
        )
        
        # Trust should deplete before 20 years
        assert len(result.annual_payouts) < 20


class TestCLUT:
    """Tests for Charitable Lead Unitrust."""
    
    def test_basic_clut(self):
        """Test basic CLUT calculation."""
        result = calculate_clt_clut(
            initial_funding=2_000_000,
            payout_rate=0.05,
            term_years=15,
        )
        
        assert result.clt_type == 'CLUT'
        assert result.initial_funding == 2_000_000
        assert result.payout_rate == 0.05
        assert len(result.annual_charitable_payments) == 15
        assert result.total_to_charity > 0
        assert result.remainder_to_heirs > 0
        assert result.estate_tax_savings > 0
    
    def test_clut_estate_tax_savings(self):
        """Test that CLUT provides estate tax savings."""
        result = calculate_clt_clut(
            initial_funding=2_000_000,
            payout_rate=0.05,
            term_years=15,
            estate_tax_rate=0.40,
        )
        
        # Estate tax savings should be 40% of initial funding
        assert result.estate_tax_savings == 2_000_000 * 0.40
    
    def test_clut_net_benefit(self):
        """Test CLUT net benefit calculation."""
        result = calculate_clt_clut(
            initial_funding=2_000_000,
            payout_rate=0.05,
            term_years=15,
        )
        
        assert result.net_benefit > 0


class TestCLAT:
    """Tests for Charitable Lead Annuity Trust."""
    
    def test_basic_clat(self):
        """Test basic CLAT calculation."""
        result = calculate_clt_clat(
            initial_funding=2_000_000,
            annual_payment=100_000,
            term_years=15,
        )
        
        assert result.clt_type == 'CLAT'
        assert result.initial_funding == 2_000_000
        assert len(result.annual_charitable_payments) == 15
        assert result.total_to_charity > 0
        assert result.remainder_to_heirs > 0
    
    def test_clat_fixed_payments(self):
        """Test that CLAT payments are fixed."""
        result = calculate_clt_clat(
            initial_funding=2_000_000,
            annual_payment=100_000,
            term_years=15,
        )
        
        # All payments should be the same
        payments = [p['charitable_payment'] for p in result.annual_charitable_payments]
        assert all(p == 100_000 for p in payments)


class TestPrivateFoundation:
    """Tests for Private Foundation calculations."""
    
    def test_basic_foundation(self):
        """Test basic private foundation calculation."""
        result = calculate_private_foundation(
            initial_funding=5_000_000,
            years=20,
        )
        
        assert result.initial_funding == 5_000_000
        assert len(result.annual_operations) == 20
        assert result.total_grants_made > 0
        assert result.total_admin_costs > 0
        assert result.total_excise_taxes > 0
        assert result.ending_balance > 0
    
    def test_foundation_minimum_distribution(self):
        """Test that foundation meets 5% minimum distribution."""
        result = calculate_private_foundation(
            initial_funding=5_000_000,
            years=20,
            annual_grant_rate=0.05,
        )
        
        # Should make grants of at least 5% annually
        assert result.effective_grant_rate >= 0.05
    
    def test_foundation_excise_tax(self):
        """Test that foundation pays excise tax on investment income."""
        result = calculate_private_foundation(
            initial_funding=5_000_000,
            years=20,
        )
        
        assert result.total_excise_taxes > 0
    
    def test_foundation_admin_costs(self):
        """Test foundation administrative costs."""
        result = calculate_private_foundation(
            initial_funding=5_000_000,
            years=20,
            annual_admin_cost=30_000,
        )
        
        assert result.total_admin_costs >= 30_000 * 20


class TestDAF:
    """Tests for Donor Advised Fund calculations."""
    
    def test_basic_daf(self):
        """Test basic DAF calculation."""
        result = calculate_daf(
            initial_contribution=5_000_000,
            years=20,
        )
        
        assert result.initial_contribution == 5_000_000
        assert len(result.annual_operations) == 20
        assert result.total_grants_made > 0
        assert result.total_fees_paid > 0
        assert result.ending_balance > 0
        assert result.simplicity_score > 90  # DAFs are very simple
    
    def test_daf_lower_fees(self):
        """Test that DAF has lower fees than foundation."""
        daf_result = calculate_daf(
            initial_contribution=5_000_000,
            years=20,
        )
        
        foundation_result = calculate_private_foundation(
            initial_funding=5_000_000,
            years=20,
        )
        
        # DAF should have lower total costs
        daf_costs = daf_result.total_fees_paid
        foundation_costs = foundation_result.total_admin_costs + foundation_result.total_excise_taxes
        
        assert daf_costs < foundation_costs


class TestFoundationVsDAF:
    """Tests for Foundation vs. DAF comparison."""
    
    def test_comparison(self):
        """Test foundation vs. DAF comparison."""
        result = compare_foundation_vs_daf(
            contribution_amount=5_000_000,
            years=20,
        )
        
        assert 'Private Foundation' in result.strategies
        assert 'Donor Advised Fund' in result.strategies
        assert result.recommended_strategy in ['Private Foundation', 'Donor Advised Fund']
        assert len(result.key_factors) > 0
        assert len(result.tax_efficiency_ranking) == 2
    
    def test_small_contribution_favors_daf(self):
        """Test that small contributions favor DAF."""
        result = compare_foundation_vs_daf(
            contribution_amount=500_000,  # Small amount
            years=20,
        )
        
        # Should recommend DAF for small amounts
        assert result.recommended_strategy == 'Donor Advised Fund'
    
    def test_large_contribution(self):
        """Test comparison with large contribution."""
        result = compare_foundation_vs_daf(
            contribution_amount=10_000_000,  # Large amount
            years=20,
        )
        
        assert result.recommended_strategy in ['Private Foundation', 'Donor Advised Fund']


class TestQCD:
    """Tests for Qualified Charitable Distribution."""
    
    def test_eligible_qcd(self):
        """Test QCD for eligible donor."""
        result = calculate_qcd_benefit(
            ira_balance=500_000,
            donor_age=72,
            qcd_amount=50_000,
            marginal_tax_rate=0.24,
        )
        
        assert result['eligible'] is True
        assert result['qcd_amount'] == 50_000
        assert result['tax_savings'] == 50_000 * 0.24
        assert result['total_benefit'] > 0
    
    def test_qcd_too_young(self):
        """Test QCD for donor under 70.5."""
        result = calculate_qcd_benefit(
            ira_balance=500_000,
            donor_age=65,
            qcd_amount=50_000,
        )
        
        assert result['eligible'] is False
        assert 'reason' in result
    
    def test_qcd_max_limit(self):
        """Test QCD with amount over limit."""
        result = calculate_qcd_benefit(
            ira_balance=500_000,
            donor_age=72,
            qcd_amount=150_000,  # Over $105k limit
        )
        
        assert result['eligible'] is True
        assert result['qcd_amount'] == 105_000  # Capped at limit
    
    def test_qcd_exceeds_balance(self):
        """Test QCD amount exceeding IRA balance."""
        result = calculate_qcd_benefit(
            ira_balance=50_000,
            donor_age=72,
            qcd_amount=100_000,
        )
        
        assert result['eligible'] is True
        assert result['qcd_amount'] == 50_000  # Capped at balance
    
    def test_qcd_irmaa_savings(self):
        """Test QCD IRMAA savings for large amounts."""
        result = calculate_qcd_benefit(
            ira_balance=500_000,
            donor_age=72,
            qcd_amount=75_000,  # Large amount
        )
        
        assert result['irmaa_savings'] > 0


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""
    
    def test_zero_funding(self):
        """Test with zero funding."""
        result = calculate_crt_crut(
            initial_funding=0,
            payout_rate=0.05,
            term_years=20,
            donor_age=65,
        )
        
        assert result.total_income_received == 0
        assert result.charitable_remainder == 0
    
    def test_very_high_payout_rate(self):
        """Test with maximum payout rate."""
        result = calculate_crt_crut(
            initial_funding=1_000_000,
            payout_rate=CRT_MAX_PAYOUT_RATE,
            term_years=20,
            donor_age=65,
        )
        
        assert result.payout_rate == CRT_MAX_PAYOUT_RATE
    
    def test_one_year_term(self):
        """Test with one-year term."""
        result = calculate_crt_crut(
            initial_funding=1_000_000,
            payout_rate=0.05,
            term_years=1,
            donor_age=65,
        )
        
        assert len(result.annual_payouts) == 1


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

# Made with Bob
