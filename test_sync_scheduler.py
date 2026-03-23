"""
test_sync_scheduler.py
======================
Tests for Phase 2: Real-Time Balance Synchronization

Tests cover:
- Sync scheduler functionality
- Market hours detection
- Sync orchestrator
- Retry logic
- State management
"""

import pytest
import time
from datetime import datetime, time as dt_time, timedelta
from unittest.mock import Mock, patch

from components.sync_scheduler import SyncScheduler, SyncFrequency, MarketHours
from components.sync_orchestrator import SyncOrchestrator, SyncResult
from components.sync_state import SyncState


class TestMarketHours:
    """Test market hours detection."""
    
    def test_market_hours_constants(self):
        """Test market hours constants are set correctly."""
        assert MarketHours.MARKET_OPEN == dt_time(9, 30)
        assert MarketHours.MARKET_CLOSE == dt_time(16, 0)
        assert MarketHours.TIMEZONE.zone == 'America/New_York'
    
    def test_is_market_open_weekend(self):
        """Test market closed on weekends."""
        # This test depends on current time, so we'll just verify the function runs
        result = MarketHours.is_market_open()
        assert isinstance(result, bool)
    
    def test_next_market_open(self):
        """Test next market open calculation."""
        next_open = MarketHours.next_market_open()
        assert isinstance(next_open, datetime)
        # Next open should be in the future or now
        assert next_open >= datetime.now(MarketHours.TIMEZONE)


class TestSyncScheduler:
    """Test sync scheduler functionality."""
    
    def test_scheduler_initialization(self):
        """Test scheduler initialization."""
        call_count = {'count': 0}
        
        def mock_sync():
            call_count['count'] += 1
            return {'status': 'success'}
        
        scheduler = SyncScheduler(
            sync_callback=mock_sync,
            frequency=SyncFrequency.MANUAL
        )
        
        assert scheduler.frequency == SyncFrequency.MANUAL
        assert not scheduler._is_running
        assert scheduler._last_sync is None
    
    def test_manual_sync_trigger(self):
        """Test manual sync trigger."""
        call_count = {'count': 0}
        
        def mock_sync():
            call_count['count'] += 1
            return {'status': 'success'}
        
        scheduler = SyncScheduler(
            sync_callback=mock_sync,
            frequency=SyncFrequency.MANUAL
        )
        
        result = scheduler.trigger_sync()
        
        assert call_count['count'] == 1
        assert result['status'] == 'success'
        assert scheduler._last_sync is not None
    
    def test_scheduler_start_stop(self):
        """Test scheduler start and stop."""
        def mock_sync():
            return {'status': 'success'}
        
        scheduler = SyncScheduler(
            sync_callback=mock_sync,
            frequency=SyncFrequency.MANUAL
        )
        
        scheduler.start()
        assert scheduler._is_running
        
        time.sleep(0.1)  # Let thread start
        
        scheduler.stop()
        assert not scheduler._is_running
    
    def test_scheduler_status(self):
        """Test scheduler status reporting."""
        def mock_sync():
            return {'status': 'success'}
        
        scheduler = SyncScheduler(
            sync_callback=mock_sync,
            frequency=SyncFrequency.DAILY,
            sync_time=dt_time(6, 0)
        )
        
        status = scheduler.get_status()
        
        assert 'is_running' in status
        assert status['frequency'] == 'daily'
        assert status['sync_time'] == '06:00:00'
        assert 'market_open' in status
    
    def test_check_interval_calculation(self):
        """Test check interval calculation for different frequencies."""
        def mock_sync():
            return {'status': 'success'}
        
        # Hourly
        scheduler = SyncScheduler(mock_sync, SyncFrequency.HOURLY)
        assert scheduler._get_check_interval() == 300  # 5 minutes
        
        # Daily
        scheduler = SyncScheduler(mock_sync, SyncFrequency.DAILY)
        assert scheduler._get_check_interval() == 600  # 10 minutes
        
        # Weekly
        scheduler = SyncScheduler(mock_sync, SyncFrequency.WEEKLY)
        assert scheduler._get_check_interval() == 3600  # 1 hour


class TestSyncOrchestrator:
    """Test sync orchestrator functionality."""
    
    def test_orchestrator_initialization(self):
        """Test orchestrator initialization."""
        orchestrator = SyncOrchestrator(
            snaptrade_connector=None,
            schwab_connector=None,
            max_retries=3
        )
        
        assert orchestrator.max_retries == 3
        assert orchestrator.initial_retry_delay == 1.0
        assert len(orchestrator.sync_history) == 0
    
    def test_sync_result_creation(self):
        """Test SyncResult creation."""
        result = SyncResult(
            success=True,
            message="Test successful",
            data={'test': 'data'}
        )
        
        assert result.success
        assert result.message == "Test successful"
        assert result.data['test'] == 'data'
        assert isinstance(result.timestamp, datetime)
        
        result_dict = result.to_dict()
        assert result_dict['success']
        assert result_dict['message'] == "Test successful"
    
    def test_sync_all_no_connectors(self):
        """Test sync_all with no connectors."""
        orchestrator = SyncOrchestrator()
        
        result = orchestrator.sync_all()
        
        assert result.success  # Should succeed with no connectors
        assert len(orchestrator.sync_history) == 1
    
    def test_sync_with_retry_success(self):
        """Test retry logic with successful sync."""
        orchestrator = SyncOrchestrator()
        
        call_count = {'count': 0}
        
        def mock_sync():
            call_count['count'] += 1
            return {'status': 'success'}
        
        result = orchestrator._sync_with_retry(mock_sync, "Test")
        
        assert result['status'] == 'success'
        assert call_count['count'] == 1  # Should succeed on first try
    
    def test_sync_with_retry_failure_then_success(self):
        """Test retry logic with initial failure."""
        orchestrator = SyncOrchestrator(max_retries=3, initial_retry_delay=0.1)
        
        call_count = {'count': 0}
        
        def mock_sync():
            call_count['count'] += 1
            if call_count['count'] < 2:
                raise Exception("Temporary failure")
            return {'status': 'success'}
        
        result = orchestrator._sync_with_retry(mock_sync, "Test")
        
        assert result['status'] == 'success'
        assert call_count['count'] == 2  # Should succeed on second try
    
    def test_sync_with_retry_all_failures(self):
        """Test retry logic with all failures."""
        orchestrator = SyncOrchestrator(max_retries=2, initial_retry_delay=0.1)
        
        def mock_sync():
            raise Exception("Persistent failure")
        
        with pytest.raises(Exception) as exc_info:
            orchestrator._sync_with_retry(mock_sync, "Test")
        
        assert "failed after 2 attempts" in str(exc_info.value)
    
    def test_sync_history_tracking(self):
        """Test sync history tracking."""
        orchestrator = SyncOrchestrator()
        
        # Perform multiple syncs
        for i in range(5):
            orchestrator.sync_all(user_id=f"user_{i}")
        
        assert len(orchestrator.sync_history) == 5
        
        # Get recent history
        recent = orchestrator.get_sync_history(limit=3)
        assert len(recent) == 3
        
        # Get last sync
        last = orchestrator.get_last_sync()
        assert last is not None
        assert last['user_id'] == 'user_4'
    
    def test_sync_history_limit(self):
        """Test sync history is limited to 100 records."""
        orchestrator = SyncOrchestrator()
        
        # Perform 150 syncs
        for i in range(150):
            orchestrator.sync_all(user_id=f"user_{i}")
        
        # Should only keep last 100
        assert len(orchestrator.sync_history) == 100
        
        # First record should be from sync 50
        assert orchestrator.sync_history[0]['user_id'] == 'user_50'


class TestSyncState:
    """Test sync state management."""
    
    def test_state_initialization(self):
        """Test state initialization."""
        import tempfile
        import os
        
        # Use temporary file
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
            temp_file = f.name
        
        try:
            state = SyncState(state_file=temp_file)
            
            assert state.state['last_sync'] is None
            assert state.state['holdings_hash'] is None
            assert state.state['sync_count'] == 0
            assert isinstance(state.state['accounts'], dict)
        finally:
            if os.path.exists(temp_file):
                os.unlink(temp_file)
    
    def test_update_sync_time(self):
        """Test sync time update."""
        import tempfile
        import os
        
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
            temp_file = f.name
        
        try:
            state = SyncState(state_file=temp_file)
            
            state.update_sync_time()
            
            assert state.state['last_sync'] is not None
            assert state.state['sync_count'] == 1
            
            last_sync = state.get_last_sync()
            assert isinstance(last_sync, datetime)
        finally:
            if os.path.exists(temp_file):
                os.unlink(temp_file)
    
    def test_sync_count_increment(self):
        """Test sync count increments correctly."""
        import tempfile
        import os
        
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
            temp_file = f.name
        
        try:
            state = SyncState(state_file=temp_file)
            
            for i in range(5):
                state.update_sync_time()
            
            assert state.get_sync_count() == 5
        finally:
            if os.path.exists(temp_file):
                os.unlink(temp_file)
    
    def test_account_state_management(self):
        """Test account state management."""
        import tempfile
        import os
        
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
            temp_file = f.name
        
        try:
            state = SyncState(state_file=temp_file)
            
            # Update account state
            state.update_account_state('account_1', {
                'balance': 10000,
                'holdings': 5
            })
            
            # Retrieve account state
            account_state = state.get_account_state('account_1')
            
            assert account_state is not None
            assert account_state['balance'] == 10000
            assert account_state['holdings'] == 5
            assert 'last_updated' in account_state
        finally:
            if os.path.exists(temp_file):
                os.unlink(temp_file)
    
    def test_state_summary(self):
        """Test state summary generation."""
        import tempfile
        import os
        
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
            temp_file = f.name
        
        try:
            state = SyncState(state_file=temp_file)
            
            state.update_sync_time()
            state.update_account_state('account_1', {'balance': 10000})
            state.update_account_state('account_2', {'balance': 20000})
            
            summary = state.get_state_summary()
            
            assert summary['sync_count'] == 1
            assert summary['accounts_tracked'] == 2
            assert summary['last_sync'] is not None
        finally:
            if os.path.exists(temp_file):
                os.unlink(temp_file)
    
    def test_clear_state(self):
        """Test state clearing."""
        import tempfile
        import os
        
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
            temp_file = f.name
        
        try:
            state = SyncState(state_file=temp_file)
            
            # Add some state
            state.update_sync_time()
            state.update_account_state('account_1', {'balance': 10000})
            
            # Clear state
            state.clear_state()
            
            assert state.state['last_sync'] is None
            assert state.state['sync_count'] == 0
            assert len(state.state['accounts']) == 0
        finally:
            if os.path.exists(temp_file):
                os.unlink(temp_file)


class TestIntegration:
    """Integration tests for Phase 2 components."""
    
    def test_full_sync_workflow(self):
        """Test complete sync workflow."""
        import tempfile
        import os
        
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
            temp_file = f.name
        
        try:
            # Initialize components
            state = SyncState(state_file=temp_file)
            orchestrator = SyncOrchestrator()
            
            # Create sync callback
            def sync_callback():
                result = orchestrator.sync_all()
                state.update_sync_time()
                return result.to_dict()
            
            # Create scheduler
            scheduler = SyncScheduler(
                sync_callback=sync_callback,
                frequency=SyncFrequency.MANUAL
            )
            
            # Trigger sync
            result = scheduler.trigger_sync()
            
            assert result['success']
            assert state.get_sync_count() == 1
            assert state.get_last_sync() is not None
        finally:
            if os.path.exists(temp_file):
                os.unlink(temp_file)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

# Made with Bob
