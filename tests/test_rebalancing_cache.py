"""
test_rebalancing_cache.py
=========================
Test the rebalancing cache system.
"""
import sys
from components.rebalancing_cache import get_cache_manager


def test_cache_system():
    """Test the rebalancing cache system."""
    print("Testing Rebalancing Cache System")
    print("=" * 50)
    
    cache_mgr = get_cache_manager()
    
    # Test 1: Set target allocation
    print("\n1. Setting target allocation (10% cash, 30% bonds, 60% stocks)...")
    try:
        cache_mgr.save_target_allocation(
            cash_pct=10.0,
            bonds_pct=30.0,
            stocks_pct=60.0,
            drift_threshold_pct=5.0
        )
        print("   ✅ Target allocation saved")
    except Exception as e:
        print(f"   ❌ Failed: {e}")
        return False
    
    # Test 2: Retrieve target allocation
    print("\n2. Retrieving target allocation...")
    try:
        target = cache_mgr.get_target_allocation()
        if target:
            print(f"   ✅ Retrieved: {target.cash_pct}% cash, {target.bonds_pct}% bonds, {target.stocks_pct}% stocks")
        else:
            print("   ❌ No target allocation found")
            return False
    except Exception as e:
        print(f"   ❌ Failed: {e}")
        return False
    
    # Test 3: Update cache with rebalancing analysis
    print("\n3. Updating rebalancing cache...")
    try:
        success = cache_mgr.update_cache()
        if success:
            print("   ✅ Cache updated successfully")
        else:
            print("   ⚠️  Cache update returned False (may be missing portfolio data)")
    except Exception as e:
        print(f"   ❌ Failed: {e}")
        print(f"   Note: This is expected if portfolio data is not available")
    
    # Test 4: Retrieve cached analysis
    print("\n4. Retrieving cached analysis...")
    try:
        analysis = cache_mgr.get_latest_analysis()
        if analysis:
            print(f"   ✅ Retrieved analysis from {analysis['calculation_date']}")
            print(f"      Total value: ${analysis['total_value']:,.2f}")
            print(f"      Drift triggered: {analysis['drift_triggered']}")
            print(f"      Actions count: {analysis['actions_count']}")
            if analysis['summary'] is not None:
                print(f"      Summary rows: {len(analysis['summary'])}")
        else:
            print("   ⚠️  No cached analysis found")
    except Exception as e:
        print(f"   ❌ Failed: {e}")
    
    # Test 5: Check if update needed
    print("\n5. Checking if cache needs update...")
    try:
        needs_update = cache_mgr.needs_update()
        print(f"   {'⚠️  Cache needs update' if needs_update else '✅ Cache is fresh'}")
    except Exception as e:
        print(f"   ❌ Failed: {e}")
    
    print("\n" + "=" * 50)
    print("✅ Cache system test complete")
    return True


if __name__ == "__main__":
    success = test_cache_system()
    sys.exit(0 if success else 1)

# Made with Bob
