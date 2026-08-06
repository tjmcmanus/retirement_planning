#!/usr/bin/env python3
"""
Test script to diagnose why 2028 January strategy isn't working.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logging
logging.basicConfig(level=logging.DEBUG, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

from strategy_core.stages.stage3_early_retirement import Stage3EarlyRetirement
from strategy_core.tax_calculator import TaxCalculator
from strategy_core.models import PortfolioBalances

def test_2028_january_plan():
    """Test the January plan generation for 2028."""
    logger.info("=" * 80)
    logger.info("2028 JANUARY BRACKET-FILL DIAGNOSTIC")
    logger.info("=" * 80)
    
    try:
        stage3 = Stage3EarlyRetirement(tax_calculator=TaxCalculator())
        
        # 2028 parameters
        year = 2028
        pnc_savings = 108415.51
        annual_expenses = 148823.05
        aca_premium = 30935.0  # From your data
        age_primary = 62
        age_spouse = 61
        filing_status = 'married_filing_jointly'
        
        logger.info(f"\nINPUT PARAMETERS:")
        logger.info(f"  Year: {year}")
        logger.info(f"  PNC Savings: ${pnc_savings:,.2f}")
        logger.info(f"  Annual Expenses: ${annual_expenses:,.2f}")
        logger.info(f"  ACA Premium: ${aca_premium:,.2f}")
        logger.info(f"  Ages: {age_primary}/{age_spouse}")
        
        # Call the method
        _jan_plan = stage3._plan_january_bracket_fill_withdrawal(
            year=year,
            pnc_savings_balance=pnc_savings,
            annual_expenses=annual_expenses,
            aca_premium=aca_premium,
            age_primary=age_primary,
            age_spouse=age_spouse,
            filing_status=filing_status,
        )
        
        if _jan_plan is None:
            logger.error("✗ _jan_plan returned None")
            logger.error("  This is why Traditional→Cash is $0 for 2028!")
            return False
        
        logger.info(f"\n✓ Plan generated successfully")
        logger.info(f"  PNC Shortfall: ${_jan_plan['pnc_shortfall']:,.2f}")
        logger.info(f"  Traditional Withdrawal: ${_jan_plan['traditional_withdrawal']:,.2f}")
        logger.info(f"  Roth Conversion: ${_jan_plan['roth_conversion']:,.2f}")
        
        return True
        
    except Exception as e:
        logger.error(f"✗ Exception: {e}", exc_info=True)
        return False

if __name__ == '__main__':
    success = test_2028_january_plan()
    sys.exit(0 if success else 1)
