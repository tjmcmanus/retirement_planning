#!/usr/bin/env python3
"""
Test Suite: January Bracket-Fill Strategy with 60-Day Rollover

Tests cover:
1. PNC Savings balance assessment
2. Shortfall calculation
3. Roth conversion sizing
4. 60-day rollover mechanics
5. Mid-year supplementation logic
6. Edge cases (negative PNC, insufficient Brokerage, etc.)
"""

import sys
sys.path.insert(0, '.')

import unittest
from datetime import datetime
from strategy_core.january_bracket_fill_strategy import JanuaryBracketFillStrategy
from strategy_core.savings_account_tracker import SavingsAccountTracker
from strategy_core.sixty_day_rollover import SixtyDayRolloverHandler


class TestSavingsAccountTracker(unittest.TestCase):
    """Tests for SavingsAccountTracker (PNC Savings monitoring)."""
    
    def setUp(self):
        """Create tracker instance with 5-month reserve."""
        self.tracker = SavingsAccountTracker(
            account_name="PNC",
            safety_reserve=55667.0  # 5 months × ($133,600 / 12)
        )
    
    RESERVE = 55667.0  # 5 months × ($133,600 / 12)
    
    def test_assess_above_reserve(self):
        """Test assessment when PNC is above safety reserve."""
        snapshot = self.tracker.assess_available_for_spending(100000.0)
        self.assertEqual(snapshot.pnc_balance, 100000.0)
        self.assertEqual(snapshot.safety_reserve, self.RESERVE)
        self.assertAlmostEqual(snapshot.available_for_spending, 100000.0 - self.RESERVE, places=0)
        self.assertFalse(snapshot.is_below_reserve)
        self.assertEqual(snapshot.supplementation_needed, 0.0)
    
    def test_assess_below_reserve(self):
        """Test assessment when PNC is below safety reserve."""
        snapshot = self.tracker.assess_available_for_spending(30000.0)
        self.assertEqual(snapshot.pnc_balance, 30000.0)
        self.assertEqual(snapshot.available_for_spending, 0.0)  # Clamped to 0
        self.assertTrue(snapshot.is_below_reserve)
        self.assertAlmostEqual(snapshot.supplementation_needed, self.RESERVE - 30000.0, places=0)
    
    def test_assess_exactly_at_reserve(self):
        """Test assessment when PNC is exactly at safety reserve."""
        snapshot = self.tracker.assess_available_for_spending(self.RESERVE)
        self.assertEqual(snapshot.pnc_balance, self.RESERVE)
        self.assertEqual(snapshot.available_for_spending, 0.0)
        self.assertFalse(snapshot.is_below_reserve)
        self.assertEqual(snapshot.supplementation_needed, 0.0)
    
    def test_supplementation_need_with_months_of_cash(self):
        """Test supplementation trigger using months of cash."""
        monthly_spending = 11467.33
        
        # Just above threshold (5 months of cash)
        need, amount, reason = self.tracker.assess_supplementation_need(
            pnc_balance=57337.0,
            monthly_spending_rate=monthly_spending
        )
        self.assertFalse(need)
        self.assertEqual(amount, 0.0)
        
        # Below threshold (4 months of cash)
        need, amount, reason = self.tracker.assess_supplementation_need(
            pnc_balance=45870.0,
            monthly_spending_rate=monthly_spending
        )
        self.assertTrue(need)
        self.assertGreater(amount, 0.0)
    
    def test_brokerage_supplementation_plan(self):
        """Test planning Brokerage supplementation."""
        plan = self.tracker.plan_brokerage_supplementation(
            supplementation_amount=20000.0,
            available_brokerage=100000.0,
            brokerage_ltcg_ratio=0.40
        )
        
        self.assertTrue(plan['feasible'])
        self.assertEqual(plan['amount_to_sell'], 20000.0)
        self.assertEqual(plan['basis_realized'], 12000.0)  # 60% of $20k
        self.assertEqual(plan['ltcg_realized'], 8000.0)    # 40% of $20k
    
    def test_brokerage_supplementation_insufficient(self):
        """Test when Brokerage is insufficient for supplementation."""
        plan = self.tracker.plan_brokerage_supplementation(
            supplementation_amount=30000.0,
            available_brokerage=20000.0,
            brokerage_ltcg_ratio=0.40
        )
        
        self.assertFalse(plan['feasible'])
        self.assertEqual(plan['amount_to_sell'], 20000.0)  # Clamped to available


class TestSixtyDayRolloverHandler(unittest.TestCase):
    """Tests for 60-day rollover mechanics."""
    
    def setUp(self):
        """Create handler instance."""
        self.handler = SixtyDayRolloverHandler()
    
    def test_plan_conversion_basic(self):
        """Test basic 60-day rollover plan."""
        plan = self.handler.plan_conversion_with_withholding(
            conversion_amount=50000.0,
            estimated_tax_rate=0.12,
            conversion_date=datetime(2027, 1, 15),
            available_cash=100000.0,
            available_brokerage=200000.0
        )
        
        self.assertEqual(plan.conversion_amount, 50000.0)
        self.assertEqual(plan.withholding_amount, 6000.0)  # 12% of $50k
        self.assertEqual(plan.net_conversion_deposit, 44000.0)
        self.assertEqual(plan.redeposit_amount, 6000.0)
    
    def test_redeposit_deadline(self):
        """Test 60-day redeposit deadline calculation."""
        conversion_date = datetime(2027, 1, 15)
        plan = self.handler.plan_conversion_with_withholding(
            conversion_amount=50000.0,
            estimated_tax_rate=0.12,
            conversion_date=conversion_date,
            available_cash=100000.0,
            available_brokerage=200000.0
        )
        
        # 60 days from Jan 15 should be Mar 16 (31 days in Jan, 28 in Feb, 16 in Mar)
        expected_deadline = datetime(2027, 3, 16)
        self.assertEqual(plan.redeposit_deadline, expected_deadline)
    
    def test_redeposit_source_cash_priority(self):
        """Test that cash is prioritized for redeposit."""
        plan = self.handler.plan_conversion_with_withholding(
            conversion_amount=50000.0,
            estimated_tax_rate=0.12,
            conversion_date=datetime(2027, 1, 15),
            available_cash=20000.0,
            available_brokerage=0.0
        )
        
        self.assertEqual(plan.source_for_redeposit, 'cash')
    
    def test_redeposit_source_brokerage_fallback(self):
        """Test fallback to brokerage when cash insufficient."""
        plan = self.handler.plan_conversion_with_withholding(
            conversion_amount=50000.0,
            estimated_tax_rate=0.12,
            conversion_date=datetime(2027, 1, 15),
            available_cash=2000.0,
            available_brokerage=10000.0
        )
        
        self.assertEqual(plan.source_for_redeposit, 'cash_and_brokerage')
    
    def test_validate_redeposit_feasible(self):
        """Test redeposit feasibility check."""
        is_feasible, message = self.handler.validate_redeposit_feasibility(
            withholding_amount=6000.0,
            available_cash=10000.0,
            available_brokerage=0.0
        )
        
        self.assertTrue(is_feasible)
        self.assertIn('feasible', message.lower())
    
    def test_validate_redeposit_infeasible(self):
        """Test redeposit infeasibility check."""
        is_feasible, message = self.handler.validate_redeposit_feasibility(
            withholding_amount=20000.0,
            available_cash=5000.0,
            available_brokerage=5000.0
        )
        
        self.assertFalse(is_feasible)
        self.assertIn('cannot', message.lower())


class TestJanuaryBracketFillStrategy(unittest.TestCase):
    """Tests for complete January Bracket-Fill Strategy."""
    
    def setUp(self):
        """Create strategy instance with 5-month reserve."""
        _annual = 137608.0
        self.strategy = JanuaryBracketFillStrategy(
            annual_expenses=_annual,
            savings_account_safety_reserve=round(_annual / 12 * 5),  # ≈ $57,337
            bracket_12_upper=103000.0,
            standard_deduction=35500.0
        )
    
    def test_plan_no_shortfall(self):
        """Test when PNC covers annual need."""
        plan = self.strategy.plan_january_withdrawal(
            pnc_savings_balance_jan1=200000.0,
            estimated_tax_rate=0.1228,
            aca_premium=24000.0,
            conversion_date=datetime(2027, 1, 15)
        )
        
        # With sufficient PNC, shortfall should be 0
        self.assertEqual(plan.pnc_shortfall, 0.0)
        self.assertEqual(plan.traditional_withdrawal_for_spending, 0.0)
    
    def test_plan_with_shortfall(self):
        """Test when PNC has shortfall (your 2027 case)."""
        plan = self.strategy.plan_january_withdrawal(
            pnc_savings_balance_jan1=138772.54,
            estimated_tax_rate=0.1228,
            aca_premium=24000.0,
            conversion_date=datetime(2027, 1, 15)
        )
        
        # Should calculate shortfall
        annual_need = 137608.0 + 24000.0
        expected_shortfall = annual_need - 138772.54
        self.assertAlmostEqual(plan.pnc_shortfall, expected_shortfall, places=0)
        
        # Should have withdrawal for shortfall
        self.assertGreater(plan.traditional_withdrawal_for_spending, 0)
        
        # Should have Roth conversion opportunity
        self.assertGreater(plan.roth_conversion_amount, 0)
    
    def test_roth_conversion_bracket_available(self):
        """Test Roth conversion uses available bracket space."""
        plan = self.strategy.plan_january_withdrawal(
            pnc_savings_balance_jan1=138772.54,
            estimated_tax_rate=0.1228,
            aca_premium=24000.0,
            conversion_date=datetime(2027, 1, 15)
        )
        
        # Available bracket = 103,000 - 35,500 = 67,500
        # Conversion should be within available bracket
        available_bracket = self.strategy.bracket_12_upper - self.strategy.standard_deduction
        self.assertLessEqual(plan.roth_conversion_amount, available_bracket)
    
    def test_midyear_pnc_assessment(self):
        """Test mid-year PNC assessment."""
        # Simulate healthy PNC
        need, amount, reason = self.strategy.assess_midyear_savings_account(
            current_pnc_savings_balance=80000.0,
            months_elapsed=6,
            monthly_spending_rate=11467.33
        )
        
        self.assertFalse(need)
        self.assertEqual(amount, 0.0)
        
        # Simulate low PNC
        need, amount, reason = self.strategy.assess_midyear_savings_account(
            current_pnc_savings_balance=30000.0,
            months_elapsed=6,
            monthly_spending_rate=11467.33
        )
        
        self.assertTrue(need)
        self.assertGreater(amount, 0.0)
    
    def test_midyear_supplementation(self):
        """Test mid-year supplementation planning."""
        plan = self.strategy.plan_midyear_supplementation(
            pnc_savings_balance=30000.0,
            available_brokerage=200000.0,
            brokerage_ltcg_ratio=0.40
        )
        
        # Reserve = 5 months of $137,608/yr = $57,337; supplement = $57,337 - $30,000 = $27,337
        expected_supplement = self.strategy.savings_account_safety_reserve - 30000.0
        self.assertTrue(plan['supplementation_needed'])
        self.assertAlmostEqual(plan['amount'], expected_supplement, delta=10.0)
        self.assertAlmostEqual(plan['ltcg_realized'], expected_supplement * 0.40, delta=5.0)
    
    def test_2027_scenario(self):
        """Test the actual 2027 scenario from example."""
        plan = self.strategy.plan_january_withdrawal(
            pnc_savings_balance_jan1=138772.54,
            estimated_tax_rate=0.1228,
            aca_premium=24000.0,
            conversion_date=datetime(2027, 1, 15)
        )
        
        # Verify key numbers match example output
        self.assertAlmostEqual(plan.total_annual_need, 161608.0, places=0)
        self.assertGreater(plan.traditional_withdrawal_for_spending, 20000.0)
        self.assertLess(plan.traditional_withdrawal_for_spending, 30000.0)
        self.assertGreater(plan.roth_conversion_amount, 40000.0)
        self.assertLess(plan.roth_conversion_amount, 50000.0)


class TestEdgeCases(unittest.TestCase):
    """Test edge cases and error conditions."""
    
    def setUp(self):
        """Create instances."""
        self.strategy = JanuaryBracketFillStrategy()
        self.tracker = SavingsAccountTracker()
    
    def test_zero_pnc_balance(self):
        """Test with zero PNC balance."""
        plan = self.strategy.plan_january_withdrawal(
            pnc_savings_balance_jan1=0.0,
            estimated_tax_rate=0.1228,
            aca_premium=24000.0,
            conversion_date=datetime(2027, 1, 15)
        )
        
        # Should calculate full annual need as shortfall
        self.assertGreater(plan.pnc_shortfall, 161000.0)
    
    def test_negative_pnc_balance(self):
        """Test with negative PNC balance (shouldn't happen, but test robustness)."""
        # Use the default tracker (safety_reserve = 55667)
        tracker = SavingsAccountTracker(account_name="PNC", safety_reserve=55667.0)
        snapshot = tracker.assess_available_for_spending(-5000.0)
        self.assertEqual(snapshot.pnc_balance, -5000.0)
        self.assertTrue(snapshot.is_below_reserve)
        self.assertEqual(snapshot.supplementation_needed, 60667.0)  # 55667 - (-5000)
    
    def test_very_high_expenses(self):
        """Test with unusually high expenses."""
        strategy = JanuaryBracketFillStrategy(annual_expenses=500000.0)
        plan = strategy.plan_january_withdrawal(
            pnc_savings_balance_jan1=100000.0,
            estimated_tax_rate=0.24,
            aca_premium=0.0,
            conversion_date=datetime(2027, 1, 15)
        )
        
        # Should calculate large shortfall
        self.assertGreaterEqual(plan.pnc_shortfall, 400000.0)
    
    def test_conversion_with_zero_bracket_space(self):
        """Test Roth conversion when bracket is full."""
        # Set bracket = standard deduction (no space)
        strategy = JanuaryBracketFillStrategy(
            annual_expenses=50000.0,
            bracket_12_upper=35500.0,  # Same as std deduction
            standard_deduction=35500.0
        )
        
        plan = strategy.plan_january_withdrawal(
            pnc_savings_balance_jan1=100000.0,
            estimated_tax_rate=0.1228,
            aca_premium=0.0,
            conversion_date=datetime(2027, 1, 15)
        )
        
        # No bracket space for conversion
        self.assertEqual(plan.roth_conversion_amount, 0.0)


def run_tests():
    """Run all tests."""
    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add all test classes
    suite.addTests(loader.loadTestsFromTestCase(TestSavingsAccountTracker))
    suite.addTests(loader.loadTestsFromTestCase(TestSixtyDayRolloverHandler))
    suite.addTests(loader.loadTestsFromTestCase(TestJanuaryBracketFillStrategy))
    suite.addTests(loader.loadTestsFromTestCase(TestEdgeCases))
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Return exit code
    return 0 if result.wasSuccessful() else 1


if __name__ == '__main__':
    exit_code = run_tests()
    sys.exit(exit_code)
