# Phase 2: Real-Time Balance Synchronization - Implementation Guide

## Executive Summary

**Status**: 📋 Ready for Implementation  
**Priority**: ⭐⭐⭐ HIGH  
**Estimated Effort**: 2-3 weeks  
**Dependencies**: Phase 1 Complete ✅  
**Last Updated**: March 23, 2026

This document provides a complete implementation guide for Phase 2 of the Brokerage Integration Enhancements, focusing on automatic scheduled synchronization of portfolio data.

---

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Implementation Components](#implementation-components)
4. [Sync Scheduler](#sync-scheduler)
5. [Background Sync Engine](#background-sync-engine)
6. [Conflict Resolution](#conflict-resolution)
7. [UI Integration](#ui-integration)
8. [Testing Strategy](#testing-strategy)
9. [Deployment Plan](#deployment-plan)

---

## Overview

### Goals

- **Automatic Synchronization**: Eliminate manual sync triggers with scheduled updates
- **Background Processing**: Non-blocking sync execution
- **Smart Sync**: Delta sync to minimize API calls and improve performance
- **Conflict Resolution**: Handle concurrent updates gracefully
- **User Control**: Flexible scheduling options for different user needs

### Features

#### Sync Scheduling Options
- **Hourly**: For active traders (market hours only: 9:30 AM - 4:00 PM ET)
- **Daily**: Default for most users (6:00 AM local time)
- **Weekly**: For long-term investors (Monday 6:00 AM)
- **Manual**: On-demand sync anytime

#### Smart Sync Capabilities
- Delta sync (only changed data)
- Rate limit management
- Batch processing for multiple accounts
- Intelligent caching
- Network failure handling with exponential backoff

#### User Experience
- Progress notifications
- Sync history and audit log
- Last sync timestamp display
- Error reporting and recovery
- Sync status indicators

---

## Architecture

### System Design

```
┌─────────────────────────────────────────────────────────────┐
│                    Streamlit Application                     │
│  ┌────────────────────────────────────────────────────────┐ │
│  │              Portfolio Hub UI                          │ │
│  │  - Sync Settings                                       │ │
│  │  - Sync Status Display                                 │ │
│  │  - Manual Sync Trigger                                 │ │
│  └────────────────┬───────────────────────────────────────┘ │
│                   │                                          │
│  ┌────────────────▼───────────────────────────────────────┐ │
│  │           Sync Scheduler (Background Thread)           │ │
│  │  - Schedule Management                                 │ │
│  │  - Market Hours Detection                              │ │
│  │  - Sync Trigger Logic                                  │ │
│  └────────────────┬───────────────────────────────────────┘ │
│                   │                                          │
│  ┌────────────────▼───────────────────────────────────────┐ │
│  │              Sync Orchestrator                         │ │
│  │  - Multi-Account Coordination                          │ │
│  │  - Retry Logic (Exponential Backoff)                   │ │
│  │  - Conflict Detection & Resolution                     │ │
│  │  - Progress Tracking                                   │ │
│  └────────────┬───────────────┬───────────────────────────┘ │
│               │               │                              │
│  ┌────────────▼──────┐  ┌────▼──────────────┐              │
│  │  SnapTrade API    │  │  Schwab Direct    │              │
│  │  - Holdings       │  │  - Accounts       │              │
│  │  - Accounts       │  │  - Positions      │              │
│  │  - Transactions   │  │  - Transactions   │              │
│  └────────────┬──────┘  └────┬──────────────┘              │
│               │               │                              │
│  ┌────────────▼───────────────▼───────────────────────────┐ │
│  │              Data Storage Layer                        │ │
│  │  - Portfolio Data (CSV/Parquet)                        │ │
│  │  - Transaction History (SQLite)                        │ │
│  │  - Sync State (Session/File)                           │ │
│  │  - Cache (Parquet)                                     │ │
│  └────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

### Data Flow

```
User Configures Schedule → Scheduler Activates → Market Hours Check
                                                          ↓
                                                    Sync Triggered
                                                          ↓
                                            Orchestrator Coordinates
                                                          ↓
                                    ┌─────────────────────┴─────────────────────┐
                                    ↓                                           ↓
                            SnapTrade Sync                              Schwab Sync
                                    ↓                                           ↓
                            Delta Detection                            Delta Detection
                                    ↓                                           ↓
                            Conflict Check                              Conflict Check
                                    ↓                                           ↓
                            Data Transform                              Data Transform
                                    └─────────────────────┬─────────────────────┘
                                                          ↓
                                                  Merge & Validate
                                                          ↓
                                                  Update Storage
                                                          ↓
                                                  Notify User
```

---

## Implementation Components

### Component 1: Sync Scheduler

**File**: `components/sync_scheduler.py`

```python
"""
components/sync_scheduler.py
============================
Background sync scheduler for automatic portfolio synchronization.

Features:
- Configurable sync schedules (hourly, daily, weekly)
- Market hours detection
- Background thread execution
- Graceful shutdown
"""

import logging
import threading
import time
from datetime import datetime, time as dt_time
from typing import Callable, Optional, Dict, Any
from enum import Enum
import pytz

logger = logging.getLogger(__name__)


class SyncFrequency(Enum):
    """Sync frequency options."""
    MANUAL = "manual"
    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"


class MarketHours:
    """US market hours detection."""
    
    MARKET_OPEN = dt_time(9, 30)  # 9:30 AM ET
    MARKET_CLOSE = dt_time(16, 0)  # 4:00 PM ET
    TIMEZONE = pytz.timezone('America/New_York')
    
    @classmethod
    def is_market_open(cls) -> bool:
        """Check if US market is currently open."""
        now = datetime.now(cls.TIMEZONE)
        
        # Check if weekend
        if now.weekday() >= 5:  # Saturday = 5, Sunday = 6
            return False
        
        # Check if within market hours
        current_time = now.time()
        return cls.MARKET_OPEN <= current_time <= cls.MARKET_CLOSE
    
    @classmethod
    def next_market_open(cls) -> datetime:
        """Get next market open time."""
        now = datetime.now(cls.TIMEZONE)
        
        # If currently in market hours, return now
        if cls.is_market_open():
            return now
        
        # Calculate next market open
        next_open = now.replace(
            hour=cls.MARKET_OPEN.hour,
            minute=cls.MARKET_OPEN.minute,
            second=0,
            microsecond=0
        )
        
        # If past market open today, move to next day
        if now.time() > cls.MARKET_OPEN:
            next_open += timedelta(days=1)
        
        # Skip weekends
        while next_open.weekday() >= 5:
            next_open += timedelta(days=1)
        
        return next_open


class SyncScheduler:
    """
    Background scheduler for automatic portfolio synchronization.
    
    Features:
    - Multiple sync frequencies
    - Market hours awareness
    - Background thread execution
    - Graceful shutdown
    """
    
    def __init__(
        self,
        sync_callback: Callable[[], Dict[str, Any]],
        frequency: SyncFrequency = SyncFrequency.DAILY,
        sync_time: dt_time = dt_time(6, 0),  # 6:00 AM default
        market_hours_only: bool = False
    ):
        """
        Initialize sync scheduler.
        
        Args:
            sync_callback: Function to call for sync (returns sync result dict)
            frequency: How often to sync
            sync_time: Time of day for daily/weekly syncs
            market_hours_only: Only sync during market hours (for hourly)
        """
        self.sync_callback = sync_callback
        self.frequency = frequency
        self.sync_time = sync_time
        self.market_hours_only = market_hours_only
        
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._last_sync: Optional[datetime] = None
        self._is_running = False
        
        logger.info(f"Initialized SyncScheduler: {frequency.value}, time={sync_time}")
    
    def start(self) -> None:
        """Start the background sync scheduler."""
        if self._is_running:
            logger.warning("Scheduler already running")
            return
        
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_scheduler, daemon=True)
        self._thread.start()
        self._is_running = True
        
        logger.info(f"Started sync scheduler: {self.frequency.value}")
    
    def stop(self) -> None:
        """Stop the background sync scheduler."""
        if not self._is_running:
            return
        
        logger.info("Stopping sync scheduler...")
        self._stop_event.set()
        
        if self._thread:
            self._thread.join(timeout=5.0)
        
        self._is_running = False
        logger.info("Sync scheduler stopped")
    
    def trigger_sync(self) -> Dict[str, Any]:
        """Manually trigger a sync."""
        logger.info("Manual sync triggered")
        return self._execute_sync()
    
    def _run_scheduler(self) -> None:
        """Main scheduler loop (runs in background thread)."""
        logger.info("Scheduler thread started")
        
        while not self._stop_event.is_set():
            try:
                if self._should_sync():
                    self._execute_sync()
                
                # Sleep for check interval
                time.sleep(self._get_check_interval())
                
            except Exception as e:
                logger.error(f"Scheduler error: {e}", exc_info=True)
                time.sleep(60)  # Wait 1 minute on error
        
        logger.info("Scheduler thread stopped")
    
    def _should_sync(self) -> bool:
        """Determine if sync should run now."""
        now = datetime.now(MarketHours.TIMEZONE)
        
        # Check market hours if required
        if self.market_hours_only and not MarketHours.is_market_open():
            return False
        
        # Check based on frequency
        if self.frequency == SyncFrequency.MANUAL:
            return False
        
        elif self.frequency == SyncFrequency.HOURLY:
            # Sync every hour (on the hour)
            if self._last_sync is None:
                return True
            
            time_since_last = (now - self._last_sync).total_seconds()
            return time_since_last >= 3600  # 1 hour
        
        elif self.frequency == SyncFrequency.DAILY:
            # Sync once per day at specified time
            if self._last_sync is None:
                return now.time() >= self.sync_time
            
            # Check if we've passed sync time since last sync
            last_sync_date = self._last_sync.date()
            if now.date() > last_sync_date and now.time() >= self.sync_time:
                return True
        
        elif self.frequency == SyncFrequency.WEEKLY:
            # Sync once per week on Monday at specified time
            if self._last_sync is None:
                return now.weekday() == 0 and now.time() >= self.sync_time
            
            # Check if it's Monday and we haven't synced this week
            if now.weekday() == 0 and now.time() >= self.sync_time:
                days_since_last = (now.date() - self._last_sync.date()).days
                return days_since_last >= 7
        
        return False
    
    def _execute_sync(self) -> Dict[str, Any]:
        """Execute the sync callback."""
        try:
            logger.info("Executing scheduled sync...")
            result = self.sync_callback()
            self._last_sync = datetime.now(MarketHours.TIMEZONE)
            logger.info(f"Sync completed: {result.get('status', 'unknown')}")
            return result
            
        except Exception as e:
            logger.error(f"Sync execution failed: {e}", exc_info=True)
            return {
                'status': 'error',
                'error': str(e),
                'timestamp': datetime.now(MarketHours.TIMEZONE).isoformat()
            }
    
    def _get_check_interval(self) -> int:
        """Get interval (seconds) between sync checks."""
        if self.frequency == SyncFrequency.HOURLY:
            return 300  # Check every 5 minutes
        elif self.frequency == SyncFrequency.DAILY:
            return 600  # Check every 10 minutes
        elif self.frequency == SyncFrequency.WEEKLY:
            return 3600  # Check every hour
        else:
            return 60  # Default 1 minute
    
    def get_status(self) -> Dict[str, Any]:
        """Get current scheduler status."""
        return {
            'is_running': self._is_running,
            'frequency': self.frequency.value,
            'sync_time': self.sync_time.isoformat() if self.sync_time else None,
            'market_hours_only': self.market_hours_only,
            'last_sync': self._last_sync.isoformat() if self._last_sync else None,
            'market_open': MarketHours.is_market_open()
        }
```

### Component 2: Sync Orchestrator

**File**: `components/sync_orchestrator.py`

```python
"""
components/sync_orchestrator.py
================================
Coordinates multi-account synchronization with retry logic and conflict resolution.
"""

import logging
import time
from datetime import datetime
from typing import Dict, List, Any, Optional
import pandas as pd

logger = logging.getLogger(__name__)


class SyncResult:
    """Result of a sync operation."""
    
    def __init__(self, success: bool, message: str, data: Optional[Dict] = None):
        self.success = success
        self.message = message
        self.data = data or {}
        self.timestamp = datetime.now()
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'success': self.success,
            'message': self.message,
            'data': self.data,
            'timestamp': self.timestamp.isoformat()
        }


class SyncOrchestrator:
    """
    Orchestrates synchronization across multiple brokerage connections.
    
    Features:
    - Multi-account coordination
    - Retry logic with exponential backoff
    - Conflict detection and resolution
    - Progress tracking
    """
    
    def __init__(
        self,
        snaptrade_connector=None,
        schwab_connector=None,
        max_retries: int = 3,
        initial_retry_delay: float = 1.0
    ):
        """
        Initialize sync orchestrator.
        
        Args:
            snaptrade_connector: SnapTrade connector instance
            schwab_connector: Schwab connector instance
            max_retries: Maximum retry attempts
            initial_retry_delay: Initial delay between retries (seconds)
        """
        self.snaptrade_connector = snaptrade_connector
        self.schwab_connector = schwab_connector
        self.max_retries = max_retries
        self.initial_retry_delay = initial_retry_delay
        
        self.sync_history: List[Dict[str, Any]] = []
    
    def sync_all(self, user_id: str = "default") -> SyncResult:
        """
        Sync all connected accounts.
        
        Args:
            user_id: User identifier
            
        Returns:
            SyncResult with overall sync status
        """
        logger.info(f"Starting sync for user: {user_id}")
        start_time = time.time()
        
        results = {
            'snaptrade': None,
            'schwab': None
        }
        errors = []
        
        # Sync SnapTrade accounts
        if self.snaptrade_connector:
            try:
                results['snaptrade'] = self._sync_with_retry(
                    lambda: self._sync_snaptrade(user_id),
                    "SnapTrade"
                )
            except Exception as e:
                error_msg = f"SnapTrade sync failed: {e}"
                logger.error(error_msg)
                errors.append(error_msg)
        
        # Sync Schwab accounts
        if self.schwab_connector:
            try:
                results['schwab'] = self._sync_with_retry(
                    lambda: self._sync_schwab(user_id),
                    "Schwab"
                )
            except Exception as e:
                error_msg = f"Schwab sync failed: {e}"
                logger.error(error_msg)
                errors.append(error_msg)
        
        # Calculate summary
        duration = time.time() - start_time
        success = len(errors) == 0
        
        sync_record = {
            'timestamp': datetime.now().isoformat(),
            'user_id': user_id,
            'duration': duration,
            'success': success,
            'results': results,
            'errors': errors
        }
        
        self.sync_history.append(sync_record)
        
        # Keep only last 100 sync records
        if len(self.sync_history) > 100:
            self.sync_history = self.sync_history[-100:]
        
        message = "Sync completed successfully" if success else f"Sync completed with errors: {'; '.join(errors)}"
        
        return SyncResult(
            success=success,
            message=message,
            data=sync_record
        )
    
    def _sync_with_retry(self, sync_func, source_name: str) -> Dict[str, Any]:
        """
        Execute sync with exponential backoff retry.
        
        Args:
            sync_func: Function to execute
            source_name: Name of sync source (for logging)
            
        Returns:
            Sync result dictionary
        """
        last_error = None
        
        for attempt in range(self.max_retries):
            try:
                logger.info(f"{source_name} sync attempt {attempt + 1}/{self.max_retries}")
                result = sync_func()
                logger.info(f"{source_name} sync successful")
                return result
                
            except Exception as e:
                last_error = e
                logger.warning(f"{source_name} sync attempt {attempt + 1} failed: {e}")
                
                if attempt < self.max_retries - 1:
                    # Exponential backoff
                    delay = self.initial_retry_delay * (2 ** attempt)
                    logger.info(f"Retrying in {delay} seconds...")
                    time.sleep(delay)
        
        # All retries failed
        raise Exception(f"{source_name} sync failed after {self.max_retries} attempts: {last_error}")
    
    def _sync_snaptrade(self, user_id: str) -> Dict[str, Any]:
        """Sync SnapTrade accounts."""
        if not self.snaptrade_connector:
            return {'status': 'skipped', 'reason': 'No connector'}
        
        # Get current holdings
        holdings_df = self.snaptrade_connector.get_holdings(user_id)
        
        if holdings_df.empty:
            return {
                'status': 'success',
                'accounts': 0,
                'holdings': 0,
                'message': 'No holdings found'
            }
        
        # Detect changes (delta sync)
        changes = self._detect_changes(holdings_df, 'snaptrade')
        
        return {
            'status': 'success',
            'accounts': holdings_df['account_id'].nunique() if 'account_id' in holdings_df.columns else 0,
            'holdings': len(holdings_df),
            'changes': changes
        }
    
    def _sync_schwab(self, user_id: str) -> Dict[str, Any]:
        """Sync Schwab accounts."""
        if not self.schwab_connector:
            return {'status': 'skipped', 'reason': 'No connector'}
        
        # Get accounts and positions
        accounts = self.schwab_connector.get_accounts()
        
        if not accounts:
            return {
                'status': 'success',
                'accounts': 0,
                'positions': 0,
                'message': 'No accounts found'
            }
        
        total_positions = 0
        for account in accounts:
            positions = self.schwab_connector.get_positions(account['accountNumber'])
            total_positions += len(positions)
        
        return {
            'status': 'success',
            'accounts': len(accounts),
            'positions': total_positions
        }
    
    def _detect_changes(self, new_data: pd.DataFrame, source: str) -> Dict[str, int]:
        """
        Detect changes between current and new data (delta sync).
        
        Args:
            new_data: New holdings data
            source: Data source name
            
        Returns:
            Dictionary with change counts
        """
        # This is a simplified version - in production, you'd compare with cached data
        return {
            'added': 0,
            'modified': 0,
            'removed': 0,
            'unchanged': len(new_data)
        }
    
    def get_sync_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent sync history."""
        return self.sync_history[-limit:]
    
    def get_last_sync(self) -> Optional[Dict[str, Any]]:
        """Get last sync record."""
        return self.sync_history[-1] if self.sync_history else None
```

### Component 3: Sync State Manager

**File**: `components/sync_state.py`

```python
"""
components/sync_state.py
========================
Manages sync state persistence and conflict detection.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional
import pandas as pd

logger = logging.getLogger(__name__)


class SyncState:
    """Manages synchronization state and conflict detection."""
    
    def __init__(self, state_file: str = "data/sync_state.json"):
        """
        Initialize sync state manager.
        
        Args:
            state_file: Path to state file
        """
        self.state_file = Path(state_file)
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        
        self.state = self._load_state()
    
    def _load_state(self) -> Dict[str, Any]:
        """Load state from file."""
        if self.state_file.exists():
            try:
                with open(self.state_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Failed to load sync state: {e}")
        
        return {
            'last_sync': None,
            'holdings_hash': None,
            'accounts': {}
        }
    
    def _save_state(self) -> None:
        """Save state to file."""
        try:
            with open(self.state_file, 'w') as f:
                json.dump(self.state, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save sync state: {e}")
    
    def update_sync_time(self) -> None:
        """Update last sync timestamp."""
        self.state['last_sync'] = datetime.now().isoformat()
        self._save_state()
    
    def get_last_sync(self) -> Optional[datetime]:
        """Get last sync timestamp."""
        if self.state['last_sync']:
            return datetime.fromisoformat(self.state['last_sync'])
        return None
    
    def detect_conflicts(self, new_data: pd.DataFrame) -> Dict[str, Any]:
        """
        Detect conflicts between cached and new data.
        
        Args:
            new_data: New holdings data
            
        Returns:
            Dictionary with conflict information
        """
        # Calculate hash of new data
        new_hash = pd.util.hash_pandas_object(new_data).sum()
        old_hash = self.state.get('holdings_hash')
        
        conflicts = {
            'has_conflicts': False,
            'changed': old_hash != new_hash if old_hash else False,
            'details': []
        }
        
        # Update hash
        self.state['holdings_hash'] = int(new_hash)
        self._save_state()
        
        return conflicts
```

---

## UI Integration

### Portfolio Hub Updates

**File**: `pages/4_portfolio_hub.py` (modifications)

```python
# Add to imports
from components.sync_scheduler import SyncScheduler, SyncFrequency
from components.sync_orchestrator import SyncOrchestrator

# Add sync settings section
def render_sync_settings():
    """Render sync scheduler settings."""
    st.markdown("### ⚙️ Automatic Sync Settings")
    
    # Initialize scheduler in session state
    if 'sync_scheduler' not in st.session_state:
        st.session_state.sync_scheduler = None
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        frequency = st.selectbox(
            "Sync Frequency",
            options=[f.value for f in SyncFrequency],
            index=1,  # Daily default
            help="How often to automatically sync your portfolio"
        )
    
    with col2:
        sync_time = st.time_input(
            "Sync Time",
            value=datetime.strptime("06:00", "%H:%M").time(),
            help="Time of day for daily/weekly syncs"
        )
    
    with col3:
        market_hours_only = st.checkbox(
            "Market Hours Only",
            value=False,
            help="Only sync during market hours (9:30 AM - 4:00 PM ET)"
        )
    
    # Start/Stop scheduler
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("▶️ Start Auto-Sync", type="primary"):
            # Create orchestrator
            orchestrator = SyncOrchestrator(
                snaptrade_connector=st.session_state.get('snaptrade_connector'),
                schwab_connector=st.session_state.get('schwab_connector')
            )
            
            # Create and start scheduler
            scheduler = SyncScheduler(
                sync_callback=lambda: orchestrator.sync_all().to_dict(),
                frequency=SyncFrequency(frequency),
                sync_time=sync_time,
                market_hours_only=market_hours_only
            )
            scheduler.start()
            
            st.session_state.sync_scheduler = scheduler
            st.success("✅ Auto-sync started!")
    
    with col2:
        if st.button("⏹️ Stop Auto-Sync"):
            if st.session_state.sync_scheduler:
                st.session_state.sync_scheduler.stop()
                st.session_state.sync_scheduler = None
                st.success("✅ Auto-sync stopped")
    
    # Show scheduler status
    if st.session_state.sync_scheduler:
        status = st.session_state.sync_scheduler.get_status()
        
        st.markdown("#### Scheduler Status")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("Status", "🟢 Running" if status['is_running'] else "🔴 Stopped")
        
        with col2:
            st.metric("Frequency", status['frequency'].title())
        
        with col3:
            last_sync = status.get('last_sync')
            if last_sync:
                last_sync_dt = datetime.fromisoformat(last_sync)
                st.metric("Last Sync", last_sync_dt.strftime("%I:%M %p"))
            else:
                st.metric("Last Sync", "Never")
```

---

## Testing Strategy

### Unit Tests

**File**: `test_sync_scheduler.py`

```python
"""Tests for sync scheduler."""

import pytest
import time
from datetime import datetime, time as dt_time
from components.sync_scheduler import SyncScheduler, SyncFrequency, MarketHours


def test_market_hours_detection():
    """Test market hours detection."""
    # This test depends on current time, so we'll just verify the function runs
    is_open = MarketHours.is_market_open()
    assert isinstance(is_open, bool)


def test_scheduler_initialization():
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


def test_manual_sync_trigger():
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


def test_scheduler_start_stop():
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
```

---

## Deployment Plan

### Week 1: Core Infrastructure
- [ ] Implement `SyncScheduler` class
- [ ] Implement `SyncOrchestrator` class
- [ ] Implement `SyncState` manager
- [ ] Add market hours detection
- [ ] Write unit tests

### Week 2: Integration
- [ ] Integrate with SnapTrade connector
- [ ] Integrate with Schwab connector
- [ ] Add UI controls for sync settings
- [ ] Implement sync status display
- [ ] Add sync history tracking

### Week 3: Testing & Polish
- [ ] End-to-end testing
- [ ] Performance optimization
- [ ] Error handling improvements
- [ ] Documentation
- [ ] User acceptance testing

---

## Success Metrics

- ✅ 99.9% sync success rate
- ✅ <30 second sync time per account
- ✅ <1% conflict rate
- ✅ 100% automatic conflict resolution
- ✅ Zero data loss incidents

---

## Next Steps

1. Review and approve implementation plan
2. Set up development environment
3. Begin Week 1 implementation
4. Schedule weekly progress reviews

---

**Document Version**: 1.0  
**Status**: 📋 Ready for Implementation  
**Next Phase**: Multi-Currency Support (Phase 3)