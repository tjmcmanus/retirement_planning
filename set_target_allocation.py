"""
set_target_allocation.py
========================
Helper script to set target portfolio allocation for rebalancing.

This should be called from Portfolio Hub > Optimization > Rebalancing
when the user sets or updates their target allocation.

Usage:
    from set_target_allocation import set_target_allocation
    
    set_target_allocation(
        cash_pct=10.0,
        bonds_pct=30.0,
        stocks_pct=60.0,
        drift_threshold_pct=5.0
    )
"""
import logging
from components.rebalancing_cache import get_cache_manager

logger = logging.getLogger(__name__)


def set_target_allocation(
    cash_pct: float,
    bonds_pct: float,
    stocks_pct: float,
    drift_threshold_pct: float = 5.0
) -> bool:
    """
    Set target portfolio allocation and update rebalancing cache.
    
    Args:
        cash_pct: Target cash percentage (0-100)
        bonds_pct: Target bonds percentage (0-100)
        stocks_pct: Target stocks percentage (0-100)
        drift_threshold_pct: Drift threshold percentage (default: 5.0)
    
    Returns:
        True if successful, False otherwise
    
    Raises:
        ValueError: If percentages don't sum to 100
    """
    try:
        # Validate inputs
        if cash_pct < 0 or bonds_pct < 0 or stocks_pct < 0:
            raise ValueError("Percentages cannot be negative")
        
        total = cash_pct + bonds_pct + stocks_pct
        if abs(total - 100.0) > 0.01:
            raise ValueError(f"Target allocations must sum to 100%, got {total}%")
        
        if drift_threshold_pct <= 0:
            raise ValueError("Drift threshold must be positive")
        
        # Save to cache
        cache_mgr = get_cache_manager()
        cache_mgr.save_target_allocation(
            cash_pct=cash_pct,
            bonds_pct=bonds_pct,
            stocks_pct=stocks_pct,
            drift_threshold_pct=drift_threshold_pct
        )
        
        # Update rebalancing analysis with new targets
        logger.info("Updating rebalancing analysis with new target allocation...")
        success = cache_mgr.update_cache()
        
        if success:
            logger.info(f"Target allocation set: {cash_pct}% cash, {bonds_pct}% bonds, {stocks_pct}% stocks")
            return True
        else:
            logger.error("Failed to update rebalancing cache")
            return False
            
    except Exception as e:
        logger.error(f"Failed to set target allocation: {e}")
        return False


def get_target_allocation() -> dict:
    """
    Get current target allocation.
    
    Returns:
        Dictionary with target allocation or None if not set
    """
    try:
        cache_mgr = get_cache_manager()
        target = cache_mgr.get_target_allocation()
        
        if target:
            return {
                'cash_pct': target.cash_pct,
                'bonds_pct': target.bonds_pct,
                'stocks_pct': target.stocks_pct,
                'drift_threshold_pct': target.drift_threshold_pct,
                'last_updated': target.last_updated
            }
        else:
            return None
            
    except Exception as e:
        logger.error(f"Failed to get target allocation: {e}")
        return None


if __name__ == "__main__":
    # Example usage
    import sys
    
    if len(sys.argv) == 4:
        # Command line usage: python set_target_allocation.py 10 30 60
        cash = float(sys.argv[1])
        bonds = float(sys.argv[2])
        stocks = float(sys.argv[3])
        
        print(f"Setting target allocation: {cash}% cash, {bonds}% bonds, {stocks}% stocks")
        success = set_target_allocation(cash, bonds, stocks)
        
        if success:
            print("✅ Target allocation set successfully")
            sys.exit(0)
        else:
            print("❌ Failed to set target allocation")
            sys.exit(1)
    else:
        # Interactive mode
        print("Set Target Portfolio Allocation")
        print("=" * 40)
        
        try:
            cash = float(input("Cash percentage (0-100): "))
            bonds = float(input("Bonds percentage (0-100): "))
            stocks = float(input("Stocks percentage (0-100): "))
            threshold = float(input("Drift threshold percentage (default 5.0): ") or "5.0")
            
            print(f"\nSetting target allocation:")
            print(f"  Cash:   {cash}%")
            print(f"  Bonds:  {bonds}%")
            print(f"  Stocks: {stocks}%")
            print(f"  Drift threshold: {threshold}%")
            
            success = set_target_allocation(cash, bonds, stocks, threshold)
            
            if success:
                print("\n✅ Target allocation set successfully")
                print("   Rebalancing cache updated")
            else:
                print("\n❌ Failed to set target allocation")
                
        except KeyboardInterrupt:
            print("\n\nCancelled")
            sys.exit(1)
        except Exception as e:
            print(f"\n❌ Error: {e}")
            sys.exit(1)

# Made with Bob
