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
from datetime import datetime, timedelta, time as dt_time
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

# Made with Bob
