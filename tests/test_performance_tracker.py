#!/usr/bin/env python3
"""
test_performance_tracker.py
============================
Comprehensive tests for the performance tracking system.

Tests:
1. Database creation and schema
2. Snapshot recording
3. TWR calculations
4. Performance metrics
5. Backfill functionality
6. Edge cases and error handling
"""

import sys
import unittest
from pathlib import Path
from datetime import date, timedelta
from decimal import Decimal
import tempfile
import shutil

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from components.performance_tracker import (
    PerformanceTracker,
    PerformanceSnapshot,
    PerformanceMetrics
)


class TestPerformanceTracker(unittest.TestCase):
    """Test suite for PerformanceTracker."""
    
    def setUp(self):
        """Set up test database."""
        # Create temporary directory for test database
        self.test_dir = tempfile.mkdtemp()
        self.test_db = Path(self.test_dir) / "test_performance.db"
        self.tracker = PerformanceTracker(db_path=self.test_db)
    
    def tearDown(self):
        """Clean up test database."""
        shutil.rmtree(self.test_dir, ignore_errors=True)
    
    def test_database_creation(self):
        """Test that database and tables are created correctly."""
        self.assertTrue(self.test_db.exists(), "Database file should exist")
        
        # Verify tables exist
        import sqlite3
        with sqlite3.connect(self.test_db) as conn:
            cursor = conn.cursor()
            
            # Check portfolio_snapshots table
            cursor.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name='portfolio_snapshots'
            """)
            self.assertIsNotNone(cursor.fetchone(), "portfolio_snapshots table should exist")
            
            # Check account_snapshots table
            cursor.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name='account_snapshots'
            """)
            self.assertIsNotNone(cursor.fetchone(), "account_snapshots table should exist")
    
    def test_record_snapshot(self):
        """Test recording a portfolio snapshot."""
        snapshot = PerformanceSnapshot(
            snapshot_date=date(2024, 1, 1),
            total_value=Decimal('100000.00'),
            account_breakdown={
                'Traditional:IRA': Decimal('60000.00'),
                'Roth:Roth IRA': Decimal('40000.00')
            },
            cash_flow=Decimal('0'),
            notes="Test snapshot"
        )
        
        snapshot_id = self.tracker.record_snapshot(snapshot)
        self.assertIsNotNone(snapshot_id, "Should return snapshot ID")
        self.assertGreater(snapshot_id, 0, "Snapshot ID should be positive")
        
        # Verify snapshot was recorded
        snapshots = self.tracker.get_snapshots()
        self.assertEqual(len(snapshots), 1, "Should have 1 snapshot")
        self.assertEqual(snapshots.iloc[0]['total_value'], 100000.00)
    
    def test_multiple_snapshots(self):
        """Test recording multiple snapshots."""
        dates = [date(2024, i, 1) for i in range(1, 7)]  # Jan-Jun 2024
        values = [100000, 102000, 105000, 103000, 108000, 110000]
        
        for d, v in zip(dates, values):
            snapshot = PerformanceSnapshot(
                snapshot_date=d,
                total_value=Decimal(str(v)),
                account_breakdown={'Test:Account': Decimal(str(v))},
                cash_flow=Decimal('0')
            )
            self.tracker.record_snapshot(snapshot)
        
        snapshots = self.tracker.get_snapshots()
        self.assertEqual(len(snapshots), 6, "Should have 6 snapshots")
        
        # Verify chronological order
        for i in range(len(snapshots) - 1):
            self.assertLess(
                snapshots.iloc[i]['snapshot_date'],
                snapshots.iloc[i + 1]['snapshot_date'],
                "Snapshots should be in chronological order"
            )
    
    def test_twr_calculation_no_cash_flows(self):
        """Test TWR calculation without cash flows."""
        # Create snapshots with 10% return
        snapshots_data = [
            (date(2024, 1, 1), 100000),
            (date(2024, 2, 1), 110000),  # 10% return
        ]
        
        for d, v in snapshots_data:
            snapshot = PerformanceSnapshot(
                snapshot_date=d,
                total_value=Decimal(str(v)),
                account_breakdown={'Test:Account': Decimal(str(v))},
                cash_flow=Decimal('0')
            )
            self.tracker.record_snapshot(snapshot)
        
        twr = self.tracker.calculate_twr(date(2024, 1, 1), date(2024, 2, 1))
        self.assertIsNotNone(twr, "TWR should be calculated")
        self.assertAlmostEqual(twr, 0.10, places=4, msg="TWR should be 10%")
    
    def test_twr_calculation_with_cash_flows(self):
        """Test TWR calculation with cash flows."""
        # Month 1: Start with $100k
        # Month 2: Grow to $110k (10% return), then add $10k deposit
        # Month 3: End with $132k (10% return on $120k)
        
        snapshots_data = [
            (date(2024, 1, 1), 100000, 0),
            (date(2024, 2, 1), 120000, 10000),  # $110k + $10k deposit
            (date(2024, 3, 1), 132000, 0),      # 10% return on $120k
        ]
        
        for d, v, cf in snapshots_data:
            snapshot = PerformanceSnapshot(
                snapshot_date=d,
                total_value=Decimal(str(v)),
                account_breakdown={'Test:Account': Decimal(str(v))},
                cash_flow=Decimal(str(cf))
            )
            self.tracker.record_snapshot(snapshot)
        
        twr = self.tracker.calculate_twr(date(2024, 1, 1), date(2024, 3, 1))
        self.assertIsNotNone(twr, "TWR should be calculated")
        # TWR should be approximately 21% (10% + 10% compounded)
        self.assertAlmostEqual(twr, 0.21, places=2, msg="TWR should be ~21%")
    
    def test_performance_metrics(self):
        """Test comprehensive performance metrics calculation."""
        # Create 12 months of data with varying returns
        base_date = date(2024, 1, 1)
        values = [100000, 102000, 105000, 103000, 108000, 110000,
                  112000, 115000, 113000, 118000, 120000, 125000]
        
        for i, v in enumerate(values):
            d = date(2024, i + 1, 1)
            snapshot = PerformanceSnapshot(
                snapshot_date=d,
                total_value=Decimal(str(v)),
                account_breakdown={'Test:Account': Decimal(str(v))},
                cash_flow=Decimal('0')
            )
            self.tracker.record_snapshot(snapshot)
        
        metrics = self.tracker.calculate_performance_metrics(
            date(2024, 1, 1),
            date(2024, 12, 1)
        )
        
        self.assertIsNotNone(metrics, "Metrics should be calculated")
        self.assertIsInstance(metrics, PerformanceMetrics)
        self.assertGreater(metrics.twr, 0, "TWR should be positive")
        self.assertGreater(metrics.annualized_return, 0, "Annualized return should be positive")
        self.assertGreater(metrics.volatility, 0, "Volatility should be positive")
    
    def test_get_snapshots_date_range(self):
        """Test retrieving snapshots for a specific date range."""
        # Create snapshots for 6 months
        for i in range(1, 7):
            snapshot = PerformanceSnapshot(
                snapshot_date=date(2024, i, 1),
                total_value=Decimal('100000'),
                account_breakdown={'Test:Account': Decimal('100000')},
                cash_flow=Decimal('0')
            )
            self.tracker.record_snapshot(snapshot)
        
        # Get snapshots for Q1 only
        q1_snapshots = self.tracker.get_snapshots(
            start_date=date(2024, 1, 1),
            end_date=date(2024, 3, 31)
        )
        
        self.assertEqual(len(q1_snapshots), 3, "Should have 3 Q1 snapshots")
    
    def test_period_performance(self):
        """Test getting performance for standard periods."""
        # Create 13 months of data
        base_value = 100000
        for i in range(13):
            d = date(2024, 1, 1) + timedelta(days=30 * i)
            value = base_value * (1.01 ** i)  # 1% monthly growth
            snapshot = PerformanceSnapshot(
                snapshot_date=d,
                total_value=Decimal(str(value)),
                account_breakdown={'Test:Account': Decimal(str(value))},
                cash_flow=Decimal('0')
            )
            self.tracker.record_snapshot(snapshot)
        
        # Test different periods
        periods = ['1M', '3M', '6M', '1Y']
        for period in periods:
            metrics = self.tracker.get_period_performance(period)
            if metrics:
                self.assertIsInstance(metrics, PerformanceMetrics)
                self.assertIsNotNone(metrics.twr)
    
    def test_insufficient_data(self):
        """Test handling of insufficient data."""
        # Only one snapshot
        snapshot = PerformanceSnapshot(
            snapshot_date=date(2024, 1, 1),
            total_value=Decimal('100000'),
            account_breakdown={'Test:Account': Decimal('100000')},
            cash_flow=Decimal('0')
        )
        self.tracker.record_snapshot(snapshot)
        
        twr = self.tracker.calculate_twr(date(2024, 1, 1), date(2024, 2, 1))
        self.assertIsNone(twr, "TWR should be None with insufficient data")
    
    def test_update_existing_snapshot(self):
        """Test updating an existing snapshot."""
        snapshot_date = date(2024, 1, 1)
        
        # Record initial snapshot
        snapshot1 = PerformanceSnapshot(
            snapshot_date=snapshot_date,
            total_value=Decimal('100000'),
            account_breakdown={'Test:Account': Decimal('100000')},
            cash_flow=Decimal('0')
        )
        self.tracker.record_snapshot(snapshot1)
        
        # Update with new value
        snapshot2 = PerformanceSnapshot(
            snapshot_date=snapshot_date,
            total_value=Decimal('105000'),
            account_breakdown={'Test:Account': Decimal('105000')},
            cash_flow=Decimal('0'),
            notes="Updated"
        )
        self.tracker.record_snapshot(snapshot2)
        
        # Verify only one snapshot exists with updated value
        snapshots = self.tracker.get_snapshots()
        self.assertEqual(len(snapshots), 1, "Should have only 1 snapshot")
        self.assertEqual(snapshots.iloc[0]['total_value'], 105000.00)


def run_tests():
    """Run all tests and display results."""
    print("=" * 70)
    print("Performance Tracker Test Suite")
    print("=" * 70)
    print()
    
    # Create test suite
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromTestCase(TestPerformanceTracker)
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Summary
    print()
    print("=" * 70)
    if result.wasSuccessful():
        print("✅ All tests passed!")
    else:
        print("❌ Some tests failed")
        print(f"   Failures: {len(result.failures)}")
        print(f"   Errors: {len(result.errors)}")
    print("=" * 70)
    
    return 0 if result.wasSuccessful() else 1


if __name__ == '__main__':
    sys.exit(run_tests())

# Made with Bob
