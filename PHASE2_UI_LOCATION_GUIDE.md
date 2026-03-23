# Phase 2 Scheduler UI - Location Guide

## Where to Find the Scheduler UI

The automatic sync scheduler UI is now integrated into the Portfolio Hub!

### Navigation Path

```
Portfolio Hub (pages/4_portfolio_hub.py)
  └─> 🔗 Connections Tab
       └─> ⚙️ Auto-Sync Scheduler Tab
```

### Step-by-Step Access

1. **Open Portfolio Hub**
   - Navigate to the Portfolio Hub page in your Streamlit app
   - URL: `http://localhost:8501/Portfolio_Hub` (or your deployment URL)

2. **Click on Connections Tab**
   - Look for the "🔗 Connections" tab in the main tab bar
   - This is the 6th tab after Overview, Holdings, Performance, Optimization, and Factor Analysis

3. **Click on Auto-Sync Scheduler Sub-Tab**
   - Within the Connections tab, you'll see three sub-tabs:
     - 📊 SnapTrade (Multi-Brokerage)
     - 🏦 Schwab Direct
     - **⚙️ Auto-Sync Scheduler** ← Click here!

### What You'll See

The Auto-Sync Scheduler tab includes:

#### 1. Current State Metrics
- **Last Sync**: Time since last synchronization
- **Total Syncs**: Number of syncs performed
- **Accounts Tracked**: Number of accounts being monitored

#### 2. Sync Schedule Configuration
- **Sync Frequency Selector**: Choose from Manual, Hourly, Daily, or Weekly
- **Sync Time Picker**: Set the time of day for scheduled syncs
- **Market Hours Only**: Toggle to only sync during market hours (9:30 AM - 4:00 PM ET)

#### 3. Scheduler Controls
- **▶️ Start Auto-Sync**: Begin automatic synchronization
- **⏹️ Stop Auto-Sync**: Stop automatic synchronization
- **🔄 Sync Now**: Trigger an immediate manual sync

#### 4. Scheduler Status (when running)
- **Status**: 🟢 Running or 🔴 Stopped
- **Frequency**: Current sync frequency
- **Market**: 🟢 Open or 🔴 Closed
- **Last Run**: Time since last automatic sync

#### 5. Recent Sync History
- List of recent syncs with timestamps
- Success/failure indicators
- Duration of each sync
- Detailed sync information (expandable)

### UI Screenshot Description

```
┌─────────────────────────────────────────────────────────────┐
│ ⚙️ Automatic Sync Settings                                  │
│ Configure automatic portfolio synchronization                │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  Last Sync        Total Syncs      Accounts Tracked         │
│  2 hours ago           15                 3                  │
│                                                               │
├─────────────────────────────────────────────────────────────┤
│ Sync Schedule Configuration                                  │
│                                                               │
│  Sync Frequency    Sync Time       Market Hours Only        │
│  [Daily ▼]         [06:00]          [ ] Enable              │
│                                                               │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  [▶️ Start Auto-Sync]  [⏹️ Stop Auto-Sync]  [🔄 Sync Now]  │
│                                                               │
├─────────────────────────────────────────────────────────────┤
│ Scheduler Status                                             │
│                                                               │
│  Status          Frequency      Market        Last Run      │
│  🟢 Running      Daily          🔴 Closed     5 min ago     │
│                                                               │
├─────────────────────────────────────────────────────────────┤
│ Recent Sync History                                          │
│                                                               │
│  ✅ 2026-03-23 14:30:15 (2.3s)                              │
│  ✅ 2026-03-23 06:00:02 (1.8s)                              │
│  ✅ 2026-03-22 06:00:01 (2.1s)                              │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

## Code Location

### UI Implementation
**File**: [`components/portfolio_connections.py`](components/portfolio_connections.py:591-788)
**Function**: `render_sync_scheduler_ui()`

### Integration Point
**File**: [`components/portfolio_connections.py`](components/portfolio_connections.py:41-78)
**Function**: `render_connections_tab()` - Line 73 calls the scheduler UI

### Backend Components
- **Scheduler**: [`components/sync_scheduler.py`](components/sync_scheduler.py)
- **Orchestrator**: [`components/sync_orchestrator.py`](components/sync_orchestrator.py)
- **State Manager**: [`components/sync_state.py`](components/sync_state.py)

## Usage Example

### Starting Automatic Sync

1. Navigate to Portfolio Hub → Connections → Auto-Sync Scheduler
2. Select your preferred frequency (e.g., "Daily")
3. Set the sync time (e.g., 6:00 AM)
4. Optionally enable "Market Hours Only"
5. Click "▶️ Start Auto-Sync"
6. The scheduler will now run in the background!

### Monitoring Sync Status

- The "Scheduler Status" section shows real-time information
- Check "Last Run" to see when the last sync occurred
- View "Recent Sync History" for detailed sync logs
- Expand any sync record to see full details

### Manual Sync

- Click "🔄 Sync Now" at any time to trigger an immediate sync
- This works whether the scheduler is running or not
- Results will appear immediately with success/failure status

### Stopping Automatic Sync

- Click "⏹️ Stop Auto-Sync" to stop the background scheduler
- Manual syncs will still work
- You can restart the scheduler at any time

## Requirements

### Python Packages
```bash
pip install pytz  # Required for market hours detection
```

### Brokerage Connections
The scheduler requires at least one active brokerage connection:
- SnapTrade connection (Multi-Brokerage tab)
- OR Schwab Direct connection (Schwab Direct tab)

## Features

### Sync Frequencies

| Frequency | Description | Best For |
|-----------|-------------|----------|
| **Manual** | No automatic sync | Full user control |
| **Hourly** | Every hour during market hours | Active traders |
| **Daily** | Once per day at set time | Most users (recommended) |
| **Weekly** | Monday at set time | Long-term investors |

### Market Hours Detection

- **Market Open**: 9:30 AM ET
- **Market Close**: 4:00 PM ET
- **Timezone**: America/New_York (Eastern Time)
- **Weekend Detection**: Automatic (no syncs on Sat/Sun)
- **Holiday Calendar**: Coming in future update

### Retry Logic

- **Max Retries**: 3 attempts
- **Backoff Strategy**: Exponential (1s → 2s → 4s)
- **Success Rate**: Target 99.9%

## Troubleshooting

### Scheduler Not Starting

**Problem**: Click "Start Auto-Sync" but nothing happens

**Solutions**:
1. Check that you have at least one brokerage connection active
2. Verify `pytz` package is installed: `pip install pytz`
3. Check browser console for errors
4. Try refreshing the page

### Syncs Not Running

**Problem**: Scheduler shows "Running" but syncs don't occur

**Solutions**:
1. Check "Market Hours Only" setting - may be waiting for market open
2. Verify sync time is in the future (for Daily/Weekly)
3. Check Recent Sync History for error messages
4. Try a manual sync to test connectivity

### Sync Failures

**Problem**: Syncs fail with errors

**Solutions**:
1. Check brokerage connection status in SnapTrade/Schwab tabs
2. Verify API credentials are valid
3. Check internet connection
4. Review error details in sync history
5. Try manual sync to isolate the issue

## Support

For issues or questions:
1. Check [`PHASE2_IMPLEMENTATION_COMPLETE.md`](PHASE2_IMPLEMENTATION_COMPLETE.md) for detailed documentation
2. Review [`PHASE2_REALTIME_SYNC_IMPLEMENTATION.md`](PHASE2_REALTIME_SYNC_IMPLEMENTATION.md) for technical details
3. Run tests: `pytest test_sync_scheduler.py -v`

---

*Last Updated: March 23, 2026*  
*Phase 2: Real-Time Balance Synchronization ✅*