#!/usr/bin/env python3
"""
Test script for optimized buffer replenishment routing.

This tests the tax optimization where Traditional funds are routed directly
to Cash instead of through Brokerage when Brokerage can't maintain both
cash needs and its own buffer target.
"""

from strategy import build_withdrawal_strategy_display
import pandas as pd

def test_optimized_routing():
    """Test the optimized routing logic"""
    print('Testing optimized buffer replenishment strategy...\n')
    print('='*80)
    
    # Test scenario: Low brokerage balance that can't cover both cash and buffer
    strategy_df, balances_df = build_withdrawal_strategy_display(
        start_year=2033,
        end_year=2035,
        initial_cash=50000,
        initial_taxable=200000,  # Low brokerage
        initial_traditional=800000,
        initial_roth=300000,
        person1_age=65,
        person2_age=63,
        annual_expenses=120000
    )
    
    # Display 2033 results
    year_2033 = strategy_df[strategy_df['Year'] == 2033].iloc[0]
    
    trad_to_cash_col = 'Trad→\nCash'
    trad_to_brok_col = 'Trad→\nBrok'
    brok_to_cash_col = 'Brok→\nCash'
    cash_replen_col = 'Cash\nReplen'
    brok_replen_col = 'Brok\nReplen'
    
    print('\nYear 2033 Fund Movements:')
    print(f"  Traditional → Cash: ${year_2033[trad_to_cash_col]:,.2f}")
    print(f"  Traditional → Brokerage: ${year_2033[trad_to_brok_col]:,.2f}")
    print(f"  Brokerage → Cash: ${year_2033[brok_to_cash_col]:,.2f}")
    print(f"  Cash Replenishment: ${year_2033[cash_replen_col]:,.2f}")
    print(f"  Brokerage Replenishment: ${year_2033[brok_replen_col]:,.2f}")
    
    print('\n' + '='*80)
    print('OPTIMIZATION ANALYSIS:')
    print('='*80)
    
    trad_to_cash = year_2033[trad_to_cash_col]
    trad_to_brok = year_2033[trad_to_brok_col]
    brok_to_cash = year_2033[brok_to_cash_col]
    
    if trad_to_cash > 0 and trad_to_brok == 0:
        print('✓ OPTIMIZATION ACTIVE!')
        print(f'  Traditional funds routed directly to Cash: ${trad_to_cash:,.2f}')
        print(f'  This avoids routing through Brokerage (Trad→Brok→Cash)')
        print(f'\nTax Savings:')
        print(f'  - Pays ordinary income tax once on ${trad_to_cash:,.2f}')
        print(f'  - Avoids LTCG on ~40% when funds move Brok→Cash')
        ltcg_avoided = trad_to_cash * 0.40 * 0.15  # 40% LTCG at 15% rate
        print(f'  - Estimated LTCG tax saved: ${ltcg_avoided:,.2f}')
    elif trad_to_brok > 0 and brok_to_cash > trad_to_brok:
        print('⚠ SUBOPTIMAL ROUTING DETECTED')
        print(f'  Traditional → Brokerage: ${trad_to_brok:,.2f}')
        print(f'  Brokerage → Cash: ${brok_to_cash:,.2f}')
        print(f'  This creates double taxation:')
        print(f'    1. Ordinary income tax on Trad→Brok')
        print(f'    2. LTCG when those funds move Brok→Cash')
    else:
        print('ℹ Normal routing (Brokerage sufficient for both buffers)')
        print(f'  Brokerage → Cash: ${brok_to_cash:,.2f}')
        print(f'  Traditional → Brokerage: ${trad_to_brok:,.2f}')
    
    print('\n' + '='*80)
    
    # Show balances
    print('\nAccount Balances After 2033:')
    bal_2033 = balances_df[balances_df['Year'] == 2033].iloc[0]
    # Get column names dynamically
    cols = balances_df.columns.tolist()
    for col in cols:
        if col != 'Year':
            print(f"  {col}: ${bal_2033[col]:,.2f}")
    
    return strategy_df, balances_df

if __name__ == '__main__':
    test_optimized_routing()

# Made with Bob
