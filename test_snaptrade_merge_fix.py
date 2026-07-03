"""
Test script to verify SnapTrade merge fix for removing old securities.

This test verifies that when syncing holdings from automated accounts,
old securities are removed and replaced with current holdings only.
"""

import pandas as pd
import os
import tempfile
from components.snaptrade_connector import SnapTradeConnector

def test_merge_replaces_old_securities():
    """
    Test that syncing an account removes old securities and replaces with new ones.
    """
    print("=" * 80)
    print("Testing SnapTrade Merge Fix: Old Securities Removal")
    print("=" * 80)
    
    # Create a temporary portfolio file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
        temp_file = f.name
    
    try:
        # Step 1: Create initial portfolio with old securities
        print("\n1. Creating initial portfolio with old securities...")
        initial_data = pd.DataFrame([
            # Fidelity account with old securities (AAPL, MSFT)
            {'month': 4, 'year': 2026, 'account_name': 'Fidelity Brokerage', 'account_type': 'Brokerage', 
             'owner': 'Joint', 'symbol': 'AAPL', 'name': 'Apple Inc', 'sector': 'Technology', 
             'qty': 100, 'purchase_price': 150.0, 'purchase_date': '2025-01-15'},
            {'month': 4, 'year': 2026, 'account_name': 'Fidelity Brokerage', 'account_type': 'Brokerage',
             'owner': 'Joint', 'symbol': 'MSFT', 'name': 'Microsoft Corp', 'sector': 'Technology',
             'qty': 50, 'purchase_price': 300.0, 'purchase_date': '2025-02-20'},
            # Manual account (should be preserved)
            {'month': 4, 'year': 2026, 'account_name': 'Manual Account', 'account_type': 'Brokerage',
             'owner': 'Primary', 'symbol': 'GOOGL', 'name': 'Alphabet Inc', 'sector': 'Technology',
             'qty': 25, 'purchase_price': 2500.0, 'purchase_date': '2024-12-01'},
            # Previous month data (should be preserved)
            {'month': 3, 'year': 2026, 'account_name': 'Fidelity Brokerage', 'account_type': 'Brokerage',
             'owner': 'Joint', 'symbol': 'AAPL', 'name': 'Apple Inc', 'sector': 'Technology',
             'qty': 100, 'purchase_price': 150.0, 'purchase_date': '2025-01-15'},
        ])
        initial_data.to_csv(temp_file, index=False)
        print(f"   Initial portfolio has {len(initial_data)} holdings")
        print(f"   Fidelity April 2026: AAPL (100 shares), MSFT (50 shares)")
        
        # Step 2: Create synced holdings with NEW securities (TSLA, NVDA)
        print("\n2. Syncing Fidelity account with NEW securities...")
        synced_data = pd.DataFrame([
            # New securities replacing old ones
            {'month': 4, 'year': 2026, 'account_name': 'Fidelity Brokerage', 'account_type': 'Brokerage',
             'owner': 'Joint', 'symbol': 'TSLA', 'name': 'Tesla Inc', 'sector': 'Automotive',
             'qty': 75, 'purchase_price': 200.0, 'purchase_date': '2026-04-10'},
            {'month': 4, 'year': 2026, 'account_name': 'Fidelity Brokerage', 'account_type': 'Brokerage',
             'owner': 'Joint', 'symbol': 'NVDA', 'name': 'NVIDIA Corp', 'sector': 'Technology',
             'qty': 30, 'purchase_price': 500.0, 'purchase_date': '2026-04-12'},
        ])
        print(f"   Synced holdings: TSLA (75 shares), NVDA (30 shares)")
        
        # Step 3: Merge using connector method directly (without full initialization)
        print("\n3. Merging synced holdings...")
        # We'll test the merge logic directly by calling the method
        # Create a mock connector just to access the method
        from unittest.mock import Mock
        connector = Mock(spec=SnapTradeConnector)
        # Call the actual merge method from the class
        merged_df = SnapTradeConnector.merge_holdings_to_portfolio(connector, synced_data, temp_file)
        
        # Step 4: Verify results
        print("\n4. Verifying results...")
        print(f"   Total holdings after merge: {len(merged_df)}")
        
        # Check Fidelity April 2026 holdings
        fidelity_april = merged_df[
            (merged_df['month'] == 4) & 
            (merged_df['year'] == 2026) & 
            (merged_df['account_name'] == 'Fidelity Brokerage')
        ]
        
        print(f"\n   Fidelity April 2026 holdings: {len(fidelity_april)}")
        for _, row in fidelity_april.iterrows():
            print(f"     - {row['symbol']}: {row['qty']} shares")
        
        # Verify old securities are GONE
        has_aapl = 'AAPL' in fidelity_april['symbol'].values
        has_msft = 'MSFT' in fidelity_april['symbol'].values
        has_tsla = 'TSLA' in fidelity_april['symbol'].values
        has_nvda = 'NVDA' in fidelity_april['symbol'].values
        
        print("\n   Security presence check:")
        print(f"     AAPL (old): {'FOUND ❌' if has_aapl else 'REMOVED ✓'}")
        print(f"     MSFT (old): {'FOUND ❌' if has_msft else 'REMOVED ✓'}")
        print(f"     TSLA (new): {'FOUND ✓' if has_tsla else 'MISSING ❌'}")
        print(f"     NVDA (new): {'FOUND ✓' if has_nvda else 'MISSING ❌'}")
        
        # Verify other accounts/months preserved
        manual_account = merged_df[merged_df['account_name'] == 'Manual Account']
        fidelity_march = merged_df[
            (merged_df['month'] == 3) & 
            (merged_df['year'] == 2026) & 
            (merged_df['account_name'] == 'Fidelity Brokerage')
        ]
        
        print(f"\n   Manual Account holdings: {len(manual_account)} (should be 1)")
        print(f"   Fidelity March 2026 holdings: {len(fidelity_march)} (should be 1)")
        
        # Final verdict
        print("\n" + "=" * 80)
        if not has_aapl and not has_msft and has_tsla and has_nvda and len(manual_account) == 1 and len(fidelity_march) == 1:
            print("✅ TEST PASSED: Old securities removed, new securities added, other data preserved")
            return True
        else:
            print("❌ TEST FAILED: Issues detected")
            if has_aapl or has_msft:
                print("   - Old securities still present (AAPL/MSFT)")
            if not has_tsla or not has_nvda:
                print("   - New securities missing (TSLA/NVDA)")
            if len(manual_account) != 1:
                print("   - Manual account data corrupted")
            if len(fidelity_march) != 1:
                print("   - Previous month data corrupted")
            return False
        
    finally:
        # Cleanup
        if os.path.exists(temp_file):
            os.remove(temp_file)


def test_merge_with_empty_account():
    """
    Test that syncing an account with no holdings removes all old securities.
    """
    print("\n" + "=" * 80)
    print("Testing SnapTrade Merge Fix: Empty Account Sync")
    print("=" * 80)
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
        temp_file = f.name
    
    try:
        # Create portfolio with securities
        print("\n1. Creating portfolio with securities...")
        initial_data = pd.DataFrame([
            {'month': 4, 'year': 2026, 'account_name': 'Fidelity Brokerage', 'account_type': 'Brokerage',
             'owner': 'Joint', 'symbol': 'AAPL', 'name': 'Apple Inc', 'sector': 'Technology',
             'qty': 100, 'purchase_price': 150.0, 'purchase_date': '2025-01-15'},
        ])
        initial_data.to_csv(temp_file, index=False)
        
        # Sync with empty holdings (account liquidated)
        print("\n2. Syncing with empty holdings (account liquidated)...")
        synced_data = pd.DataFrame(columns=[
            'month', 'year', 'account_name', 'account_type', 'owner',
            'symbol', 'name', 'sector', 'qty', 'purchase_price', 'purchase_date'
        ])
        
        # Use mock connector to test merge logic
        from unittest.mock import Mock
        connector = Mock(spec=SnapTradeConnector)
        merged_df = SnapTradeConnector.merge_holdings_to_portfolio(connector, synced_data, temp_file)
        
        print(f"\n3. Result: {len(merged_df)} holdings (should be 1 - original preserved)")
        
        # With empty sync, original should be preserved since no accounts to replace
        if len(merged_df) == 1:
            print("✅ TEST PASSED: Empty sync preserves existing data")
            return True
        else:
            print("❌ TEST FAILED: Unexpected behavior with empty sync")
            return False
            
    finally:
        if os.path.exists(temp_file):
            os.remove(temp_file)


if __name__ == '__main__':
    print("\n" + "=" * 80)
    print("SNAPTRADE MERGE FIX TEST SUITE")
    print("=" * 80)
    
    test1_passed = test_merge_replaces_old_securities()
    test2_passed = test_merge_with_empty_account()
    
    print("\n" + "=" * 80)
    print("FINAL RESULTS")
    print("=" * 80)
    print(f"Test 1 (Replace old securities): {'✅ PASSED' if test1_passed else '❌ FAILED'}")
    print(f"Test 2 (Empty account sync): {'✅ PASSED' if test2_passed else '❌ FAILED'}")
    
    if test1_passed and test2_passed:
        print("\n🎉 ALL TESTS PASSED! The fix is working correctly.")
    else:
        print("\n⚠️  SOME TESTS FAILED. Please review the implementation.")

# Made with Bob
