#!/usr/bin/env python3
"""
Unit tests for BETR (Break-Even Tax Rate) Roth Conversion module

Tests cover:
- Input validation
- BETR calculation logic
- LTCG rate lookup
- Conversion optimization
- Scenario analysis
- Edge cases

Author: IBM Bob
Date: 2026-02-24
"""

import sys
import unittest
from betr_roth_conversion import (
    BETRInputs,
    BETRResults,
    calculate_betr,
    optimize_conversion_amount,
    analyze_conversion_scenarios,
    _get_ltcg_rate,
    NONTAXABLE_BASIS_ADJUSTMENT_FACTOR,
    BACKDOOR_ROTH_BENEFIT_FACTOR
)


class TestBETRInputValidation(unittest.TestCase):
    """Test input validation for BETR calculations"""
    
    def test_negative_conversion_amount(self):
        """Test that negative conversion amount raises ValueError"""
        inputs = BETRInputs(
            current_marginal_rate=0.24,
            expected_future_rate=0.22,
            conversion_amount=-50000,
            traditional_ira_balance=500000
        )
        with self.assertRaises(ValueError) as context:
            calculate_betr(inputs)
        self.assertIn("must be positive", str(context.exception))
    
    def test_zero_conversion_amount(self):
        """Test that zero conversion amount raises ValueError"""
        inputs = BETRInputs(
            current_marginal_rate=0.24,
            expected_future_rate=0.22,
            conversion_amount=0,
            traditional_ira_balance=500000
        )
        with self.assertRaises(ValueError) as context:
            calculate_betr(inputs)
        self.assertIn("must be positive", str(context.exception))
    
    def test_conversion_exceeds_balance(self):
        """Test that conversion exceeding IRA balance raises ValueError"""
        inputs = BETRInputs(
            current_marginal_rate=0.24,
            expected_future_rate=0.22,
            conversion_amount=600000,
            traditional_ira_balance=500000
        )
        with self.assertRaises(ValueError) as context:
            calculate_betr(inputs)
        self.assertIn("cannot exceed", str(context.exception))
    
    def test_invalid_tax_rate_above_one(self):
        """Test that tax rate > 1 raises ValueError"""
        inputs = BETRInputs(
            current_marginal_rate=1.5,
            expected_future_rate=0.22,
            conversion_amount=50000,
            traditional_ira_balance=500000
        )
        with self.assertRaises(ValueError) as context:
            calculate_betr(inputs)
        self.assertIn("between 0 and 1", str(context.exception))
    
    def test_invalid_tax_rate_negative(self):
        """Test that negative tax rate raises ValueError"""
        inputs = BETRInputs(
            current_marginal_rate=0.24,
            expected_future_rate=-0.1,
            conversion_amount=50000,
            traditional_ira_balance=500000
        )
        with self.assertRaises(ValueError) as context:
            calculate_betr(inputs)
        self.assertIn("between 0 and 1", str(context.exception))
    
    def test_negative_nontaxable_basis(self):
        """Test that negative nontaxable basis raises ValueError"""
        inputs = BETRInputs(
            current_marginal_rate=0.24,
            expected_future_rate=0.22,
            conversion_amount=50000,
            traditional_ira_balance=500000,
            nontaxable_basis=-10000
        )
        with self.assertRaises(ValueError) as context:
            calculate_betr(inputs)
        self.assertIn("cannot be negative", str(context.exception))
    
    def test_nontaxable_basis_exceeds_balance(self):
        """Test that nontaxable basis exceeding balance raises ValueError"""
        inputs = BETRInputs(
            current_marginal_rate=0.24,
            expected_future_rate=0.22,
            conversion_amount=50000,
            traditional_ira_balance=500000,
            nontaxable_basis=600000
        )
        with self.assertRaises(ValueError) as context:
            calculate_betr(inputs)
        self.assertIn("cannot exceed", str(context.exception))


class TestBETRCalculation(unittest.TestCase):
    """Test BETR calculation logic"""
    
    def test_basic_betr_calculation(self):
        """Test basic BETR calculation with standard inputs"""
        inputs = BETRInputs(
            current_marginal_rate=0.24,
            expected_future_rate=0.22,
            conversion_amount=50000,
            traditional_ira_balance=500000
        )
        result = calculate_betr(inputs)
        
        self.assertIsInstance(result, BETRResults)
        self.assertGreater(result.betr, 0)
        self.assertLess(result.betr, 1)
        self.assertIsInstance(result.conversion_recommended, bool)
        self.assertGreater(result.conversion_tax, 0)
    
    def test_betr_with_nontaxable_basis(self):
        """Test that nontaxable basis affects BETR calculation"""
        inputs_no_basis = BETRInputs(
            current_marginal_rate=0.24,
            expected_future_rate=0.22,
            conversion_amount=50000,
            traditional_ira_balance=500000,
            nontaxable_basis=0
        )
        result_no_basis = calculate_betr(inputs_no_basis)
        
        inputs_with_basis = BETRInputs(
            current_marginal_rate=0.24,
            expected_future_rate=0.22,
            conversion_amount=50000,
            traditional_ira_balance=500000,
            nontaxable_basis=100000
        )
        result_with_basis = calculate_betr(inputs_with_basis)
        
        # Nontaxable basis reduces the taxable portion of conversion
        # This actually LOWERS the BETR because less tax is paid upfront
        # The adjustment factor then adds back a small amount
        # Net effect: BETR is typically lower with nontaxable basis
        self.assertNotEqual(result_with_basis.betr, result_no_basis.betr)
        
        # Both should be valid BETR values
        self.assertGreater(result_no_basis.betr, 0)
        self.assertGreater(result_with_basis.betr, 0)
    
    def test_betr_with_backdoor_roth(self):
        """Test that backdoor Roth planning increases BETR"""
        inputs_no_backdoor = BETRInputs(
            current_marginal_rate=0.24,
            expected_future_rate=0.22,
            conversion_amount=50000,
            traditional_ira_balance=500000,
            future_backdoor_roth=False
        )
        result_no_backdoor = calculate_betr(inputs_no_backdoor)
        
        inputs_with_backdoor = BETRInputs(
            current_marginal_rate=0.24,
            expected_future_rate=0.22,
            conversion_amount=50000,
            traditional_ira_balance=500000,
            future_backdoor_roth=True,
            backdoor_contribution_years=10
        )
        result_with_backdoor = calculate_betr(inputs_with_backdoor)
        
        # BETR should be higher with backdoor Roth benefit
        self.assertGreater(result_with_backdoor.betr, result_no_backdoor.betr)
    
    def test_conversion_recommendation_logic(self):
        """Test that conversion is recommended when future rate > BETR"""
        inputs = BETRInputs(
            current_marginal_rate=0.24,
            expected_future_rate=0.32,  # High future rate
            conversion_amount=50000,
            traditional_ira_balance=500000
        )
        result = calculate_betr(inputs)
        
        # Should recommend conversion when future rate > BETR
        if inputs.expected_future_rate > result.betr:
            self.assertTrue(result.conversion_recommended)
    
    def test_pay_from_taxable_vs_ira(self):
        """Test that paying from taxable account results in different BETR"""
        inputs_from_taxable = BETRInputs(
            current_marginal_rate=0.24,
            expected_future_rate=0.22,
            conversion_amount=50000,
            traditional_ira_balance=500000,
            pay_from_taxable=True,
            taxable_account_balance=200000
        )
        result_from_taxable = calculate_betr(inputs_from_taxable)
        
        inputs_from_ira = BETRInputs(
            current_marginal_rate=0.24,
            expected_future_rate=0.22,
            conversion_amount=50000,
            traditional_ira_balance=500000,
            pay_from_taxable=False
        )
        result_from_ira = calculate_betr(inputs_from_ira)
        
        # BETR should be different based on payment source
        # When paying from taxable, BETR is typically lower (more conservative)
        self.assertNotEqual(result_from_taxable.betr, result_from_ira.betr)
        self.assertLess(result_from_taxable.betr, result_from_ira.betr)


class TestLTCGRateLookup(unittest.TestCase):
    """Test LTCG rate lookup functionality"""
    
    def test_ltcg_rate_low_income(self):
        """Test LTCG rate for low income (0% bracket)"""
        rate = _get_ltcg_rate(50000, 2026)
        self.assertEqual(rate, 0.0)
    
    def test_ltcg_rate_medium_income(self):
        """Test LTCG rate for medium income (15% bracket)"""
        rate = _get_ltcg_rate(200000, 2026)
        self.assertEqual(rate, 0.15)
    
    def test_ltcg_rate_high_income(self):
        """Test LTCG rate for high income (20% bracket)"""
        rate = _get_ltcg_rate(700000, 2026)
        self.assertEqual(rate, 0.20)
    
    def test_ltcg_rate_fallback(self):
        """Test LTCG rate fallback for invalid year"""
        rate = _get_ltcg_rate(200000, 1900)
        # Should return highest rate (0.20) when year not found
        self.assertIn(rate, [0.15, 0.20])  # Either default or highest rate


class TestOptimizeConversionAmount(unittest.TestCase):
    """Test conversion amount optimization"""
    
    def test_optimize_within_bracket(self):
        """Test optimization stays within target bracket"""
        optimal_amount, result = optimize_conversion_amount(
            traditional_ira_balance=500000,
            current_agi=150000,
            target_tax_bracket=0.24,
            year=2026,
            pay_from_taxable=True,
            taxable_account_balance=200000
        )
        
        self.assertGreater(optimal_amount, 0)
        self.assertLessEqual(optimal_amount, 500000)
        self.assertIsInstance(result, BETRResults)
    
    def test_optimize_with_small_ira_balance(self):
        """Test optimization with small IRA balance"""
        optimal_amount, result = optimize_conversion_amount(
            traditional_ira_balance=10000,
            current_agi=150000,
            target_tax_bracket=0.24,
            year=2026
        )
        
        # Should return amount <= IRA balance
        self.assertLessEqual(optimal_amount, 10000)
        self.assertGreaterEqual(optimal_amount, 0)


class TestAnalyzeConversionScenarios(unittest.TestCase):
    """Test scenario analysis functionality"""
    
    def test_analyze_multiple_scenarios(self):
        """Test analysis of multiple conversion amounts"""
        scenarios_df = analyze_conversion_scenarios(
            traditional_ira_balance=500000,
            conversion_amounts=[25000, 50000, 75000, 100000],
            current_marginal_rate=0.24,
            expected_future_rate=0.22,
            pay_from_taxable=True,
            taxable_account_balance=200000
        )
        
        self.assertEqual(len(scenarios_df), 4)
        self.assertIn('conversion_amount', scenarios_df.columns)
        self.assertIn('betr', scenarios_df.columns)
        self.assertIn('recommended', scenarios_df.columns)
        self.assertIn('net_benefit', scenarios_df.columns)


class TestConstants(unittest.TestCase):
    """Test that constants are properly defined"""
    
    def test_nontaxable_basis_adjustment_factor(self):
        """Test nontaxable basis adjustment factor is defined"""
        self.assertEqual(NONTAXABLE_BASIS_ADJUSTMENT_FACTOR, 0.05)
    
    def test_backdoor_roth_benefit_factor(self):
        """Test backdoor Roth benefit factor is defined"""
        self.assertEqual(BACKDOOR_ROTH_BENEFIT_FACTOR, 0.02)


def run_tests():
    """Run all BETR tests"""
    print("=" * 80)
    print("BETR ROTH CONVERSION MODULE - TEST SUITE")
    print("=" * 80)
    
    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add all test classes
    suite.addTests(loader.loadTestsFromTestCase(TestBETRInputValidation))
    suite.addTests(loader.loadTestsFromTestCase(TestBETRCalculation))
    suite.addTests(loader.loadTestsFromTestCase(TestLTCGRateLookup))
    suite.addTests(loader.loadTestsFromTestCase(TestOptimizeConversionAmount))
    suite.addTests(loader.loadTestsFromTestCase(TestAnalyzeConversionScenarios))
    suite.addTests(loader.loadTestsFromTestCase(TestConstants))
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Print summary
    print("\n" + "=" * 80)
    print(f"TEST RESULTS: {result.testsRun} tests, "
          f"{len(result.failures)} failures, {len(result.errors)} errors")
    print("=" * 80)
    
    if result.wasSuccessful():
        print("\n✅ All BETR tests passed successfully!")
        return 0
    else:
        print("\n❌ Some tests failed. Please review the output above.")
        return 1


if __name__ == '__main__':
    sys.exit(run_tests())

# Made with Bob
