#!/usr/bin/env python3
"""
Full 2028 scenario test showing Traditional->Cash withdrawal through entire flow.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logging
logging.basicConfig(level=logging.WARNING, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

from strategy_core.stages.stage3_early_retirement import Stage3EarlyRetirement
from strategy_core.tax_calculator import TaxCalculator
from strategy_core.models import PortfolioBalances

def test_2028_full_flow():
    """Test full 2028 flow with Traditional->Cash."""
    logger.info("=" * 80)
    logger.info("2028 FULL FLOW TEST")
    logger.info("=" * 80)
    
    try:
        stage3 = Stage3EarlyRetirement(tax_calculator=TaxCalculator())
        
        # 2028 parameters from your output
        year = 2028
        balances = PortfolioBalances(
            cash=108415.51,
            taxable=316481.25,
            traditional=448665.04,
            roth=73833.0,
            daf=0.0,
        )
        expenses = 148823.05
        aca_premium = 30935.0
        age_primary = 62
        age_spouse = 61
        filing_status = 'married_filing_jointly'
        state = 'PA'
        
        logger.info(f"\nINPUT STATE:")
        logger.info(f"  Year: {year}")
        logger.info(f"  Cash: ${balances.cash:,.2f}")
        logger.info(f"  Traditional: ${balances.traditional:,.2f}")
        logger.info(f"  Taxable: ${balances.taxable:,.2f}")
        logger.info(f"  Expenses: ${expenses:,.2f}")
        logger.info(f"  ACA Premium: ${aca_premium:,.2f}")
        
        # Call calculate_strategy
        logger.info(f"\nCALLING calculate_strategy()...")
        strategy_result = stage3.calculate_strategy(
            year=year,
            balances=balances,
            expenses=expenses,
            age_primary=age_primary,
            age_spouse=age_spouse,
            filing_status=filing_status,
            state=state,
            max_conversion_rate=0.24,
            growth_rate=1.06,
            brokerage_account=None,
            start_year=2026
        )
        
        logger.info(f"\nOUTPUT:")
        logger.info(f"  Roth conversion: ${strategy_result.roth_conversion:,.0f}")
        logger.info(f"  Traditional → Cash: ${strategy_result.transactions.get('traditional_to_cash', 0):,.0f}")
        logger.info(f"  Brokerage → Cash: ${strategy_result.transactions.get('brokerage_to_cash', 0):,.0f}")
        logger.info(f"  Roth → Cash: ${strategy_result.transactions.get('roth_to_cash', 0):,.0f}")
        
        # Check if Traditional->Cash is in the output
        trad_to_cash = strategy_result.transactions.get('traditional_to_cash', 0)
        if trad_to_cash > 0:
            logger.info(f"\n✓ Traditional→Cash IS in transaction log: ${trad_to_cash:,.0f}")
            return True
        else:
            logger.error(f"\n✗ Traditional→Cash is ZERO in transaction log")
            logger.error(f"  This is the problem!")
            
            # Check intermediate state
            logger.info(f"\nINVESTIGATION:")
            _jan_plan = stage3._plan_january_bracket_fill_withdrawal(
                year=year,
                pnc_savings_balance=balances.cash,
                annual_expenses=expenses,
                aca_premium=aca_premium,
                age_primary=age_primary,
                age_spouse=age_spouse,
                filing_status=filing_status,
            )
            if _jan_plan:
                logger.info(f"  January plan shortfall: ${_jan_plan['pnc_shortfall']:,.0f}")
            else:
                logger.error(f"  January plan is None!")
            
            return False
        
    except Exception as e:
        logger.error(f"✗ Exception: {e}", exc_info=True)
        return False

if __name__ == '__main__':
    success = test_2028_full_flow()
    sys.exit(0 if success else 1)
