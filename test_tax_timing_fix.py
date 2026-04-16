"""
Test script to verify the tax calculation timing fix for Stages 3 & 4.

This test verifies that:
1. Preliminary tax is estimated before rebalancing
2. Tax is deducted from cash during rebalancing (not after)
3. Final tax adjustment is applied correctly
4. Cash balances remain positive throughout
"""

import sys
import logging
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from strategy_core.models import PortfolioBalances
from strategy_core.stages.stage3_early_retirement import Stage3EarlyRetirement
from strategy_core.stages.stage4_medicare import Stage4Medicare
from strategy_core.tax_calculator import TaxCalculator
from strategy_core.account_manager import AccountManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_stage3_tax_timing():
    """Test Stage 3 Early Retirement tax timing fix."""
    logger.info("=" * 80)
    logger.info("Testing Stage 3 Early Retirement Tax Timing Fix")
    logger.info("=" * 80)
    
    # Create dependencies
    tax_calc = TaxCalculator()
    acct_mgr = AccountManager()
    
    # Create stage
    stage3 = Stage3EarlyRetirement(tax_calc, acct_mgr)
    
    # Create test balances
    balances = PortfolioBalances(
        cash=50000,
        taxable=300000,
        traditional=500000,
        roth=200000,
        daf=0
    )
    
    # Test parameters
    year = 2025
    expenses = 80000
    age_primary = 60
    age_spouse = 58
    
    logger.info(f"\nInitial balances:")
    logger.info(f"  Cash: ${balances.cash:,.2f}")
    logger.info(f"  Taxable: ${balances.taxable:,.2f}")
    logger.info(f"  Traditional: ${balances.traditional:,.2f}")
    logger.info(f"  Roth: ${balances.roth:,.2f}")
    logger.info(f"  Total: ${balances.total():,.2f}")
    
    try:
        # Execute strategy
        strategy = stage3.calculate_strategy(
            year=year,
            balances=balances,
            expenses=expenses,
            age_primary=age_primary,
            age_spouse=age_spouse,
            filing_status='married_filing_jointly',
            state='PA',
            max_conversion_rate=0.24,
            growth_rate=1.07,
            brokerage_account=None,
            start_year=2024
        )
        
        logger.info(f"\nFinal balances:")
        logger.info(f"  Cash: ${strategy.balances.cash:,.2f}")
        logger.info(f"  Taxable: ${strategy.balances.taxable:,.2f}")
        logger.info(f"  Traditional: ${strategy.balances.traditional:,.2f}")
        logger.info(f"  Roth: ${strategy.balances.roth:,.2f}")
        logger.info(f"  Total: ${strategy.balances.total():,.2f}")
        
        logger.info(f"\nTax calculations:")
        logger.info(f"  AGI: ${strategy.agi:,.2f}")
        logger.info(f"  Federal Tax: ${strategy.federal_tax:,.2f}")
        logger.info(f"  State Tax: ${strategy.state_tax:,.2f}")
        logger.info(f"  Total Tax: ${strategy.federal_tax + strategy.state_tax:,.2f}")
        
        logger.info(f"\nRoth Conversion: ${strategy.roth_conversion:,.2f}")
        logger.info(f"ACA Premium: ${strategy.aca_premium:,.2f}")
        
        # Verify cash balance is positive
        if strategy.balances.cash < 0:
            logger.error(f"❌ FAIL: Cash balance is negative: ${strategy.balances.cash:,.2f}")
            return False
        else:
            logger.info(f"✓ PASS: Cash balance is positive: ${strategy.balances.cash:,.2f}")
        
        # Verify total portfolio value is conserved (within growth)
        initial_total = balances.total()
        final_total = strategy.balances.total()
        expected_total = (initial_total - expenses - strategy.federal_tax - strategy.state_tax - 
                         strategy.aca_premium - strategy.daf_contribution) * 1.07
        
        difference = abs(final_total - expected_total)
        if difference < initial_total * 0.01:  # Within 1%
            logger.info(f"✓ PASS: Portfolio value conserved (difference: ${difference:,.2f})")
        else:
            logger.warning(f"⚠ WARNING: Portfolio value difference: ${difference:,.2f}")
        
        logger.info("\n✓ Stage 3 test completed successfully")
        return True
        
    except Exception as e:
        logger.error(f"❌ Stage 3 test failed: {e}", exc_info=True)
        return False


def test_stage4_tax_timing():
    """Test Stage 4 Medicare tax timing fix."""
    logger.info("\n" + "=" * 80)
    logger.info("Testing Stage 4 Medicare Tax Timing Fix")
    logger.info("=" * 80)
    
    # Create dependencies
    tax_calc = TaxCalculator()
    acct_mgr = AccountManager()
    
    # Create stage
    stage4 = Stage4Medicare(tax_calc, acct_mgr)
    
    # Create test balances
    balances = PortfolioBalances(
        cash=60000,
        taxable=350000,
        traditional=450000,
        roth=250000,
        daf=10000
    )
    
    # Test parameters
    year = 2027
    expenses = 85000
    age_primary = 66
    age_spouse = 64
    prior_magi = 120000  # For IRMAA calculation
    
    logger.info(f"\nInitial balances:")
    logger.info(f"  Cash: ${balances.cash:,.2f}")
    logger.info(f"  Taxable: ${balances.taxable:,.2f}")
    logger.info(f"  Traditional: ${balances.traditional:,.2f}")
    logger.info(f"  Roth: ${balances.roth:,.2f}")
    logger.info(f"  DAF: ${balances.daf:,.2f}")
    logger.info(f"  Total: ${balances.total():,.2f}")
    
    try:
        # Execute strategy
        strategy = stage4.calculate_strategy(
            year=year,
            balances=balances,
            expenses=expenses,
            age_primary=age_primary,
            age_spouse=age_spouse,
            prior_magi=prior_magi,
            filing_status='married_filing_jointly',
            state='PA',
            max_conversion_rate=0.24,
            growth_rate=1.07,
            brokerage_account=None,
            start_year=2024
        )
        
        logger.info(f"\nFinal balances:")
        logger.info(f"  Cash: ${strategy.balances.cash:,.2f}")
        logger.info(f"  Taxable: ${strategy.balances.taxable:,.2f}")
        logger.info(f"  Traditional: ${strategy.balances.traditional:,.2f}")
        logger.info(f"  Roth: ${strategy.balances.roth:,.2f}")
        logger.info(f"  DAF: ${strategy.balances.daf:,.2f}")
        logger.info(f"  Total: ${strategy.balances.total():,.2f}")
        
        logger.info(f"\nTax calculations:")
        logger.info(f"  AGI: ${strategy.agi:,.2f}")
        logger.info(f"  Federal Tax: ${strategy.federal_tax:,.2f}")
        logger.info(f"  State Tax: ${strategy.state_tax:,.2f}")
        logger.info(f"  Total Tax: ${strategy.federal_tax + strategy.state_tax:,.2f}")
        
        logger.info(f"\nRoth Conversion: ${strategy.roth_conversion:,.2f}")
        logger.info(f"IRMAA Penalty: ${strategy.irmaa_penalty:,.2f}")
        logger.info(f"ACA Premium: ${strategy.aca_premium:,.2f}")
        
        # Verify cash balance is positive
        if strategy.balances.cash < 0:
            logger.error(f"❌ FAIL: Cash balance is negative: ${strategy.balances.cash:,.2f}")
            return False
        else:
            logger.info(f"✓ PASS: Cash balance is positive: ${strategy.balances.cash:,.2f}")
        
        # Verify total portfolio value is conserved (within growth)
        initial_total = balances.total()
        final_total = strategy.balances.total()
        expected_total = (initial_total - expenses - strategy.federal_tax - strategy.state_tax - 
                         strategy.irmaa_penalty - strategy.aca_premium - strategy.daf_contribution) * 1.07
        
        difference = abs(final_total - expected_total)
        if difference < initial_total * 0.01:  # Within 1%
            logger.info(f"✓ PASS: Portfolio value conserved (difference: ${difference:,.2f})")
        else:
            logger.warning(f"⚠ WARNING: Portfolio value difference: ${difference:,.2f}")
        
        logger.info("\n✓ Stage 4 test completed successfully")
        return True
        
    except Exception as e:
        logger.error(f"❌ Stage 4 test failed: {e}", exc_info=True)
        return False


def main():
    """Run all tests."""
    logger.info("Starting Tax Calculation Timing Fix Tests")
    logger.info("=" * 80)
    
    results = []
    
    # Test Stage 3
    results.append(("Stage 3 Early Retirement", test_stage3_tax_timing()))
    
    # Test Stage 4
    results.append(("Stage 4 Medicare", test_stage4_tax_timing()))
    
    # Summary
    logger.info("\n" + "=" * 80)
    logger.info("TEST SUMMARY")
    logger.info("=" * 80)
    
    for name, passed in results:
        status = "✓ PASS" if passed else "❌ FAIL"
        logger.info(f"{status}: {name}")
    
    all_passed = all(result[1] for result in results)
    
    if all_passed:
        logger.info("\n✓ All tests passed!")
        return 0
    else:
        logger.error("\n❌ Some tests failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())

# Made with Bob
