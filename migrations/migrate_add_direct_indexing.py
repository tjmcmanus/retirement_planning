"""
Database Migration: Add Direct Indexing Tables
===============================================
Creates database tables for Direct Indexing functionality.

This migration adds:
- rsp_holdings: RSP constituent reference data
- direct_index_positions: User's actual direct index holdings
- harvest_history: Track all tax loss harvesting transactions
- replacement_mappings: Primary to secondary stock mappings
- initial_setup_history: Track initial portfolio setup

Author: Bob
Date: April 16, 2026
Version: 1.0
"""

import sqlite3
import logging
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)

# Database path
DB_PATH = Path("data/rsp_holdings.db")


def create_tables(conn: sqlite3.Connection) -> None:
    """
    Create all direct indexing tables.
    
    Args:
        conn: SQLite database connection
    """
    cursor = conn.cursor()
    
    # 1. RSP Holdings (reference data)
    logger.info("Creating rsp_holdings table...")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS rsp_holdings (
            symbol TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            sector TEXT NOT NULL,
            industry TEXT,
            market_cap REAL,
            weight_in_rsp REAL,
            current_price REAL,
            last_updated TIMESTAMP
        )
    """)
    
    # Create index on sector for faster queries
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_rsp_sector 
        ON rsp_holdings(sector)
    """)
    
    # 2. Direct Index Positions (user's actual holdings)
    logger.info("Creating direct_index_positions table...")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS direct_index_positions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_name TEXT NOT NULL,
            account_type TEXT NOT NULL,
            symbol TEXT NOT NULL,
            shares REAL NOT NULL,
            purchase_price REAL NOT NULL,
            purchase_date DATE NOT NULL,
            cost_basis REAL NOT NULL,
            is_replacement BOOLEAN DEFAULT 0,
            replaced_symbol TEXT,
            lot_id TEXT,
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (symbol) REFERENCES rsp_holdings(symbol)
        )
    """)
    
    # Create indexes for faster queries
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_positions_account 
        ON direct_index_positions(account_name, account_type)
    """)
    
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_positions_symbol 
        ON direct_index_positions(symbol)
    """)
    
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_positions_purchase_date 
        ON direct_index_positions(purchase_date)
    """)
    
    # 3. Harvest History (track all harvests)
    logger.info("Creating harvest_history table...")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS harvest_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            harvest_date DATE NOT NULL,
            account_name TEXT NOT NULL,
            account_type TEXT NOT NULL,
            
            -- Sold position
            sold_symbol TEXT NOT NULL,
            sold_shares REAL NOT NULL,
            sold_price REAL NOT NULL,
            cost_basis REAL NOT NULL,
            realized_loss REAL NOT NULL,
            holding_period_days INTEGER,
            
            -- Replacement position
            replacement_symbol TEXT,
            replacement_shares REAL,
            replacement_price REAL,
            replacement_cost REAL,
            
            -- Tax impact
            tax_savings_estimate REAL,
            marginal_tax_rate REAL,
            ltcg_rate REAL,
            
            -- Status tracking
            status TEXT DEFAULT 'pending',
            approved_by TEXT,
            approved_at TIMESTAMP,
            executed_at TIMESTAMP,
            
            -- Additional info
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            
            FOREIGN KEY (sold_symbol) REFERENCES rsp_holdings(symbol),
            FOREIGN KEY (replacement_symbol) REFERENCES rsp_holdings(symbol)
        )
    """)
    
    # Create indexes
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_harvest_date 
        ON harvest_history(harvest_date)
    """)
    
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_harvest_status 
        ON harvest_history(status)
    """)
    
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_harvest_account 
        ON harvest_history(account_name, account_type)
    """)
    
    # 4. Replacement Stock Mappings (primary -> secondary)
    logger.info("Creating replacement_mappings table...")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS replacement_mappings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            primary_symbol TEXT NOT NULL,
            secondary_symbol TEXT NOT NULL,
            sector TEXT NOT NULL,
            priority INTEGER DEFAULT 1,
            correlation REAL,
            is_active BOOLEAN DEFAULT 1,
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            
            UNIQUE(primary_symbol, secondary_symbol),
            FOREIGN KEY (primary_symbol) REFERENCES rsp_holdings(symbol),
            FOREIGN KEY (secondary_symbol) REFERENCES rsp_holdings(symbol)
        )
    """)
    
    # Create indexes
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_replacement_primary 
        ON replacement_mappings(primary_symbol)
    """)
    
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_replacement_sector 
        ON replacement_mappings(sector)
    """)
    
    # 5. Initial Setup History
    logger.info("Creating initial_setup_history table...")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS initial_setup_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            setup_date DATE NOT NULL,
            total_investment REAL NOT NULL,
            actual_investment REAL,
            num_stocks INTEGER NOT NULL,
            account_name TEXT NOT NULL,
            account_type TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            purchase_file_path TEXT,
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            completed_at TIMESTAMP
        )
    """)
    
    # 6. Update Metadata (for tracking data refreshes)
    logger.info("Creating update_metadata table...")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS update_metadata (
            key TEXT PRIMARY KEY,
            value TEXT,
            updated_at TIMESTAMP
        )
    """)
    
    conn.commit()
    logger.info("All tables created successfully")


def add_sample_data(conn: sqlite3.Connection) -> None:
    """
    Add sample data for testing (optional).
    
    Args:
        conn: SQLite database connection
    """
    cursor = conn.cursor()
    
    # Check if we already have data
    cursor.execute("SELECT COUNT(*) FROM rsp_holdings")
    count = cursor.fetchone()[0]
    
    if count > 0:
        logger.info(f"Database already has {count} RSP holdings, skipping sample data")
        return
    
    logger.info("Adding sample RSP holdings data...")
    
    # Sample data for testing
    sample_holdings = [
        ('AAPL', 'Apple Inc.', 'Information Technology', 'Technology Hardware', 3000000000000, 0.2, 150.00),
        ('MSFT', 'Microsoft Corp.', 'Information Technology', 'Software', 2800000000000, 0.2, 380.00),
        ('GOOGL', 'Alphabet Inc.', 'Communication Services', 'Internet Content', 1800000000000, 0.2, 140.00),
        ('AMZN', 'Amazon.com Inc.', 'Consumer Discretionary', 'Internet Retail', 1700000000000, 0.2, 170.00),
        ('NVDA', 'NVIDIA Corp.', 'Information Technology', 'Semiconductors', 1600000000000, 0.2, 500.00),
        ('META', 'Meta Platforms Inc.', 'Communication Services', 'Internet Content', 1200000000000, 0.2, 450.00),
        ('TSLA', 'Tesla Inc.', 'Consumer Discretionary', 'Auto Manufacturers', 800000000000, 0.2, 250.00),
        ('BRK.B', 'Berkshire Hathaway', 'Financials', 'Insurance', 900000000000, 0.2, 450.00),
        ('JPM', 'JPMorgan Chase', 'Financials', 'Banks', 500000000000, 0.2, 180.00),
        ('JNJ', 'Johnson & Johnson', 'Health Care', 'Pharmaceuticals', 450000000000, 0.2, 160.00),
    ]
    
    now = datetime.now().isoformat()
    
    for symbol, name, sector, industry, market_cap, weight, price in sample_holdings:
        cursor.execute("""
            INSERT OR IGNORE INTO rsp_holdings 
            (symbol, name, sector, industry, market_cap, weight_in_rsp, current_price, last_updated)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (symbol, name, sector, industry, market_cap, weight, price, now))
    
    conn.commit()
    logger.info(f"Added {len(sample_holdings)} sample holdings")


def verify_tables(conn: sqlite3.Connection) -> bool:
    """
    Verify all tables were created successfully.
    
    Args:
        conn: SQLite database connection
    
    Returns:
        True if all tables exist, False otherwise
    """
    cursor = conn.cursor()
    
    expected_tables = [
        'rsp_holdings',
        'direct_index_positions',
        'harvest_history',
        'replacement_mappings',
        'initial_setup_history',
        'update_metadata'
    ]
    
    cursor.execute("""
        SELECT name FROM sqlite_master 
        WHERE type='table' 
        ORDER BY name
    """)
    
    existing_tables = [row[0] for row in cursor.fetchall()]
    
    all_exist = True
    for table in expected_tables:
        if table in existing_tables:
            logger.info(f"✓ Table '{table}' exists")
        else:
            logger.error(f"✗ Table '{table}' missing")
            all_exist = False
    
    return all_exist


def run_migration(add_samples: bool = False) -> bool:
    """
    Run the database migration.
    
    Args:
        add_samples: Whether to add sample data for testing
    
    Returns:
        True if migration successful, False otherwise
    """
    try:
        # Ensure data directory exists
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        
        # Connect to database
        logger.info(f"Connecting to database: {DB_PATH}")
        conn = sqlite3.connect(DB_PATH)
        
        # Create tables
        create_tables(conn)
        
        # Add sample data if requested
        if add_samples:
            add_sample_data(conn)
        
        # Verify tables
        success = verify_tables(conn)
        
        # Close connection
        conn.close()
        
        if success:
            logger.info("Migration completed successfully!")
        else:
            logger.error("Migration completed with errors")
        
        return success
        
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        return False


def main():
    """Main function."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    print("=" * 60)
    print("Direct Indexing Database Migration")
    print("=" * 60)
    print()
    
    # Run migration
    success = run_migration(add_samples=True)
    
    if success:
        print("\n✓ Migration completed successfully!")
        print(f"\nDatabase location: {DB_PATH.absolute()}")
        print("\nNext steps:")
        print("1. Run: python components/rsp_holdings_fetcher.py")
        print("   to fetch full RSP holdings from Yahoo Finance")
        print("2. Run: python components/initial_portfolio_generator.py")
        print("   to generate your initial portfolio")
    else:
        print("\n✗ Migration failed. Check logs for details.")
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())

# Made with Bob
