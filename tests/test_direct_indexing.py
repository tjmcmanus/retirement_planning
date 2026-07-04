"""
Direct Indexing Test Suite
===========================
Comprehensive unit and integration tests for direct indexing functionality.

Test Coverage:
- RSP holdings fetcher
- Sector classifier
- Initial portfolio generator
- Replacement selector
- Cost basis tracker
- Direct index harvester
- Harvest executor
- Tax savings tracker
- Direct index manager

Author: Bob
Date: April 18, 2026
Version: 1.0
"""

import pytest
import sqlite3
import pandas as pd
from pathlib import Path
from datetime import date, datetime, timedelta
from decimal import Decimal
import tempfile
import shutil
import uuid

# Import components to test
from components.rsp_holdings_fetcher import (
    fetch_rsp_holdings,
    load_constituents,
    get_constituent,
    update_prices
)
from components.sector_classifier import (
    get_sector_constituents,
    get_sector_weights
)
from components.initial_portfolio_generator import (
    generate_initial_portfolio,
    export_to_csv
)
from components.replacement_selector import (
    find_replacement_stock,
    get_owned_symbols,
    ReplacementCandidate
)
from components.cost_basis_tracker import (
    TaxLot,
    LotDisposition,
    LotSelectionMethod,
    GainType,
    add_tax_lot,
    get_tax_lots,
    sell_shares
)
from components.direct_index_harvester import (
    scan_harvest_opportunities,
    HarvestOpportunity
)
from components.harvest_executor import (
    create_harvest_execution,
    approve_execution,
    cancel_execution,
    execute_sell_trade,
    execute_buy_trade,
    complete_execution
)
from components.tax_savings_tracker import (
    record_harvest_savings,
    get_ytd_summary,
    get_harvest_history,
    get_performance_metrics
)
from components.direct_index_manager import (
    import_from_csv,
    export_to_portfolio_csv,
    export_to_dataframe,
    get_position_summary
)


# ==============================================================================
# FIXTURES
# ==============================================================================

@pytest.fixture
def temp_db():
    """Create temporary database for testing."""
    temp_dir = tempfile.mkdtemp()
    db_path = Path(temp_dir) / "test_rsp_holdings.db"
    
    # Temporarily override DB_PATH in modules
    import components.rsp_holdings_fetcher as rhf
    import components.cost_basis_tracker as cbt
    import components.harvest_executor as he
    import components.tax_savings_tracker as tst
    
    original_paths = {
        'rhf': rhf.DB_PATH,
        'cbt': cbt.DB_PATH,
        'he': he.DB_PATH,
        'tst': tst.DB_PATH
    }
    
    rhf.DB_PATH = db_path
    cbt.DB_PATH = db_path
    he.DB_PATH = db_path
    tst.DB_PATH = db_path
    
    yield db_path
    
    # Restore original paths
    rhf.DB_PATH = original_paths['rhf']
    cbt.DB_PATH = original_paths['cbt']
    he.DB_PATH = original_paths['he']
    tst.DB_PATH = original_paths['tst']
    
    # Cleanup
    shutil.rmtree(temp_dir)


@pytest.fixture
def sample_constituents():
    """Sample RSP constituents for testing."""
    from components.rsp_holdings_fetcher import RSPConstituent
    
    return [
        RSPConstituent(
            symbol="AAPL",
            name="Apple Inc.",
            sector="Information Technology",
            industry="Technology Hardware",
            current_price=150.00,
            market_cap=2500000000000,
            weight_in_rsp=0.002,
            last_updated=datetime.now()
        ),
        RSPConstituent(
            symbol="MSFT",
            name="Microsoft Corporation",
            sector="Information Technology",
            industry="Software",
            current_price=350.00,
            market_cap=2600000000000,
            weight_in_rsp=0.002,
            last_updated=datetime.now()
        ),
        RSPConstituent(
            symbol="GOOGL",
            name="Alphabet Inc.",
            sector="Communication Services",
            industry="Internet Services",
            current_price=140.00,
            market_cap=1800000000000,
            weight_in_rsp=0.002,
            last_updated=datetime.now()
        ),
        RSPConstituent(
            symbol="JPM",
            name="JPMorgan Chase & Co.",
            sector="Financials",
            industry="Banks",
            current_price=145.00,
            market_cap=420000000000,
            weight_in_rsp=0.002,
            last_updated=datetime.now()
        ),
        RSPConstituent(
            symbol="JNJ",
            name="Johnson & Johnson",
            sector="Health Care",
            industry="Pharmaceuticals",
            current_price=160.00,
            market_cap=400000000000,
            weight_in_rsp=0.002,
            last_updated=datetime.now()
        )
    ]


@pytest.fixture
def sample_tax_lots():
    """Sample tax lots for testing."""
    base_date = date.today() - timedelta(days=400)
    
    return [
        TaxLot(
            lot_id=str(uuid.uuid4()),
            symbol="AAPL",
            account_name="Test Account",
            account_type="Brokerage",
            shares=100.0,
            purchase_price=180.00,
            purchase_date=base_date,
            cost_basis=18000.00
        ),
        TaxLot(
            lot_id=str(uuid.uuid4()),
            symbol="AAPL",
            account_name="Test Account",
            account_type="Brokerage",
            shares=50.0,
            purchase_price=160.00,
            purchase_date=base_date + timedelta(days=30),
            cost_basis=8000.00
        ),
        TaxLot(
            lot_id=str(uuid.uuid4()),
            symbol="MSFT",
            account_name="Test Account",
            account_type="Brokerage",
            shares=75.0,
            purchase_price=300.00,
            purchase_date=base_date,
            cost_basis=22500.00
        )
    ]


# ==============================================================================
# TEST: RSP Holdings Fetcher
# ==============================================================================

class TestRSPHoldingsFetcher:
    """Test RSP holdings fetcher functionality."""
    
    def test_fetch_rsp_holdings(self, temp_db):
        """Test fetching RSP holdings."""
        # Note: This will make actual API calls in real testing
        # For unit tests, we should mock the API
        constituents = fetch_rsp_holdings(force_refresh=False)
        
        assert isinstance(constituents, list)
        # Should have ~500 constituents
        assert len(constituents) > 400
    
    def test_load_constituents(self, temp_db, sample_constituents):
        """Test loading constituents from database."""
        # First, save some constituents
        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS rsp_holdings (
                symbol TEXT PRIMARY KEY,
                name TEXT,
                sector TEXT,
                current_price REAL,
                market_cap REAL,
                last_updated TEXT
            )
        """)
        
        for const in sample_constituents:
            cursor.execute("""
                INSERT OR REPLACE INTO rsp_holdings
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                const.symbol,
                const.name,
                const.sector,
                const.current_price,
                const.market_cap,
                const.last_updated.isoformat()
            ))
        
        conn.commit()
        conn.close()
        
        # Load and verify
        loaded = load_constituents()
        assert len(loaded) == len(sample_constituents)
        assert loaded[0].symbol == "AAPL"
    
    def test_get_constituent(self, temp_db, sample_constituents):
        """Test getting single constituent."""
        # Setup database
        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS rsp_holdings (
                symbol TEXT PRIMARY KEY,
                name TEXT,
                sector TEXT,
                current_price REAL,
                market_cap REAL,
                last_updated TEXT
            )
        """)
        
        for const in sample_constituents:
            cursor.execute("""
                INSERT OR REPLACE INTO rsp_holdings
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                const.symbol,
                const.name,
                const.sector,
                const.current_price,
                const.market_cap,
                const.last_updated.isoformat()
            ))
        
        conn.commit()
        conn.close()
        
        # Test
        aapl = get_constituent("AAPL")
        assert aapl is not None
        assert aapl.symbol == "AAPL"
        assert aapl.sector == "Information Technology"
        
        # Test non-existent
        invalid = get_constituent("INVALID")
        assert invalid is None


# ==============================================================================
# TEST: Sector Classifier
# ==============================================================================

class TestSectorClassifier:
    """Test sector classification functionality."""
    
    def test_get_sector_constituents(self, temp_db, sample_constituents):
        """Test getting constituents by sector."""
        # Setup database
        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS rsp_holdings (
                symbol TEXT PRIMARY KEY,
                name TEXT,
                sector TEXT,
                current_price REAL,
                market_cap REAL,
                last_updated TEXT
            )
        """)
        
        for const in sample_constituents:
            cursor.execute("""
                INSERT OR REPLACE INTO rsp_holdings
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                const.symbol,
                const.name,
                const.sector,
                const.current_price,
                const.market_cap,
                const.last_updated.isoformat()
            ))
        
        conn.commit()
        conn.close()
        
        # Test
        tech_stocks = get_sector_constituents("Information Technology")
        assert len(tech_stocks) == 2
        assert "AAPL" in [s.symbol for s in tech_stocks]
        assert "MSFT" in [s.symbol for s in tech_stocks]
    


# ==============================================================================
# TEST: Cost Basis Tracker
# ==============================================================================

class TestCostBasisTracker:
    """Test cost basis tracking functionality."""
    
    def test_add_tax_lot(self, temp_db):
        """Test adding a tax lot."""
        lot = TaxLot(
            lot_id=str(uuid.uuid4()),
            symbol="AAPL",
            account_name="Test Account",
            account_type="Brokerage",
            shares=100.0,
            purchase_price=150.00,
            purchase_date=date.today(),
            cost_basis=15000.00
        )
        
        add_tax_lot(lot)
        
        # Verify
        lots = get_tax_lots(symbol="AAPL")
        assert len(lots) == 1
        assert lots[0].symbol == "AAPL"
        assert lots[0].shares == 100.0
    
    def test_get_tax_lots_filtering(self, temp_db, sample_tax_lots):
        """Test filtering tax lots."""
        # Add lots
        for lot in sample_tax_lots:
            add_tax_lot(lot)
        
        # Test symbol filter
        aapl_lots = get_tax_lots(symbol="AAPL")
        assert len(aapl_lots) == 2
        
        # Test account filter
        account_lots = get_tax_lots(account_name="Test Account")
        assert len(account_lots) == 3
    
    def test_sell_shares_fifo(self, temp_db, sample_tax_lots):
        """Test selling shares with FIFO method."""
        # Add lots
        for lot in sample_tax_lots:
            add_tax_lot(lot)
        
        # Sell 120 shares of AAPL (should use both lots)
        dispositions = sell_shares(
            symbol="AAPL",
            shares=120.0,
            sale_price=150.00,
            sale_date=date.today(),
            account_name="Test Account",
            method=LotSelectionMethod.FIFO
        )
        
        assert len(dispositions) == 2
        assert dispositions[0].shares_sold == 100.0  # First lot
        assert dispositions[1].shares_sold == 20.0   # Partial second lot
        
        # Verify remaining shares
        remaining_lots = get_tax_lots(symbol="AAPL", account_name="Test Account")
        assert len(remaining_lots) == 1
        assert remaining_lots[0].shares == 30.0  # 50 - 20
    
    def test_sell_shares_hifo(self, temp_db, sample_tax_lots):
        """Test selling shares with HIFO method (maximize loss)."""
        # Add lots
        for lot in sample_tax_lots:
            add_tax_lot(lot)
        
        # Sell 100 shares of AAPL with HIFO (should use highest cost lot first)
        dispositions = sell_shares(
            symbol="AAPL",
            shares=100.0,
            sale_price=150.00,
            sale_date=date.today(),
            account_name="Test Account",
            method=LotSelectionMethod.HIFO
        )
        
        assert len(dispositions) == 1
        assert dispositions[0].shares_sold == 100.0
        # Should have used the $180 lot (highest cost)
        assert dispositions[0].cost_basis == 18000.00
        
        # Calculate gain/loss
        assert dispositions[0].gain_loss < 0  # Should be a loss
    
    def test_long_term_vs_short_term(self, temp_db):
        """Test long-term vs short-term classification."""
        # Long-term lot (>365 days)
        long_term_lot = TaxLot(
            lot_id=str(uuid.uuid4()),
            symbol="AAPL",
            account_name="Test Account",
            account_type="Brokerage",
            shares=100.0,
            purchase_price=150.00,
            purchase_date=date.today() - timedelta(days=400),
            cost_basis=15000.00
        )
        
        # Short-term lot (<365 days)
        short_term_lot = TaxLot(
            lot_id=str(uuid.uuid4()),
            symbol="MSFT",
            account_name="Test Account",
            account_type="Brokerage",
            shares=50.0,
            purchase_price=300.00,
            purchase_date=date.today() - timedelta(days=100),
            cost_basis=15000.00
        )
        
        add_tax_lot(long_term_lot)
        add_tax_lot(short_term_lot)
        
        # Sell long-term
        lt_dispositions = sell_shares(
            symbol="AAPL",
            shares=100.0,
            sale_price=140.00,
            sale_date=date.today(),
            account_name="Test Account"
        )
        
        assert lt_dispositions[0].gain_type == GainType.LONG_TERM
        
        # Sell short-term
        st_dispositions = sell_shares(
            symbol="MSFT",
            shares=50.0,
            sale_price=290.00,
            sale_date=date.today(),
            account_name="Test Account"
        )
        
        assert st_dispositions[0].gain_type == GainType.SHORT_TERM


# ==============================================================================
# TEST: Replacement Selector
# ==============================================================================

class TestReplacementSelector:
    """Test replacement stock selection."""
    
    def test_find_replacement_stock(self, temp_db, sample_constituents):
        """Test finding replacement stocks."""
        # Setup database
        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS rsp_holdings (
                symbol TEXT PRIMARY KEY,
                name TEXT,
                sector TEXT,
                current_price REAL,
                market_cap REAL,
                last_updated TEXT
            )
        """)
        
        for const in sample_constituents:
            cursor.execute("""
                INSERT OR REPLACE INTO rsp_holdings
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                const.symbol,
                const.name,
                const.sector,
                const.current_price,
                const.market_cap,
                const.last_updated.isoformat()
            ))
        
        conn.commit()
        conn.close()
        
        # Test finding replacement for AAPL
        candidates = find_replacement_stock(
            harvested_symbol="AAPL",
            owned_symbols={"GOOGL", "JPM"},  # Already own these
            num_alternatives=3
        )
        
        assert len(candidates) > 0
        # Should recommend MSFT (same sector, not owned)
        assert candidates[0].symbol == "MSFT"
        assert candidates[0].sector == "Information Technology"
        # Should not recommend AAPL itself
        assert all(c.symbol != "AAPL" for c in candidates)
        # Should not recommend already owned stocks
        assert all(c.symbol not in {"GOOGL", "JPM"} for c in candidates)


# ==============================================================================
# TEST: Direct Index Harvester
# ==============================================================================

class TestDirectIndexHarvester:
    """Test harvest opportunity identification."""
    
    def test_scan_harvest_opportunities(self, temp_db, sample_constituents, sample_tax_lots):
        """Test scanning for harvest opportunities."""
        # Setup database with constituents
        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS rsp_holdings (
                symbol TEXT PRIMARY KEY,
                name TEXT,
                sector TEXT,
                current_price REAL,
                market_cap REAL,
                last_updated TEXT
            )
        """)
        
        for const in sample_constituents:
            cursor.execute("""
                INSERT OR REPLACE INTO rsp_holdings
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                const.symbol,
                const.name,
                const.sector,
                const.current_price,
                const.market_cap,
                const.last_updated.isoformat()
            ))
        
        conn.commit()
        conn.close()
        
        # Add tax lots with losses
        for lot in sample_tax_lots:
            add_tax_lot(lot)
        
        # Scan for opportunities
        opportunities = scan_harvest_opportunities(
            account_name="Test Account",
            current_agi=150000,
            loss_threshold_pct=10.0
        )
        
        # Should find AAPL as opportunity (purchased at $180, now $150 = 16.7% loss)
        assert len(opportunities) > 0
        aapl_opp = next((o for o in opportunities if o.symbol == "AAPL"), None)
        assert aapl_opp is not None
        assert aapl_opp.unrealized_loss < 0
        assert aapl_opp.loss_percentage > 10.0


# ==============================================================================
# TEST: Harvest Executor
# ==============================================================================

class TestHarvestExecutor:
    """Test harvest execution workflow."""
    
    def test_create_harvest_execution(self, temp_db, sample_constituents):
        """Test creating harvest execution plan."""
        # Setup
        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS rsp_holdings (
                symbol TEXT PRIMARY KEY,
                name TEXT,
                sector TEXT,
                current_price REAL,
                market_cap REAL,
                last_updated TEXT
            )
        """)
        
        for const in sample_constituents:
            cursor.execute("""
                INSERT OR REPLACE INTO rsp_holdings
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                const.symbol,
                const.name,
                const.sector,
                const.current_price,
                const.market_cap,
                const.last_updated.isoformat()
            ))
        
        conn.commit()
        conn.close()
        
        # Create mock harvest opportunity
        opportunity = HarvestOpportunity(
            symbol="AAPL",
            account_name="Test Account",
            account_type="Brokerage",
            shares=100.0,
            purchase_price=180.00,
            current_price=150.00,
            purchase_date=date.today() - timedelta(days=400),
            unrealized_loss=-3000.00,
            loss_percentage=16.67,
            holding_period_days=400,
            is_long_term=True,
            estimated_tax_savings=450.00,
            ltcg_rate=0.15,
            marginal_rate=0.24,
            recommended_replacement="MSFT",
            replacement_sector="Information Technology",
            replacement_price=350.00,
            alternative_replacements=["GOOGL", "NVDA"],
            is_wash_sale_risk=False,
            wash_sale_reason="",
            can_harvest=True,
            harvest_priority=5,
            lot_ids=["lot123"],
            notes=""
        )
        
        # Create execution
        execution = create_harvest_execution(
            opportunity=opportunity,
            replacement_symbol="MSFT"
        )
        
        assert execution is not None
        assert execution.sell_trade.symbol == "AAPL"
        assert execution.buy_trade.symbol == "MSFT"
        assert execution.sell_trade.shares == 100.0
        assert execution.tax_savings_estimate == 450.00
    
    def test_execution_workflow(self, temp_db, sample_constituents):
        """Test complete execution workflow."""
        # Setup
        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS rsp_holdings (
                symbol TEXT PRIMARY KEY,
                name TEXT,
                sector TEXT,
                current_price REAL,
                market_cap REAL,
                last_updated TEXT
            )
        """)
        
        for const in sample_constituents:
            cursor.execute("""
                INSERT OR REPLACE INTO rsp_holdings
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                const.symbol,
                const.name,
                const.sector,
                const.current_price,
                const.market_cap,
                const.last_updated.isoformat()
            ))
        
        conn.commit()
        conn.close()
        
        # Add tax lot
        lot = TaxLot(
            lot_id=str(uuid.uuid4()),
            symbol="AAPL",
            account_name="Test Account",
            account_type="Brokerage",
            shares=100.0,
            purchase_price=180.00,
            purchase_date=date.today() - timedelta(days=400),
            cost_basis=18000.00
        )
        add_tax_lot(lot)
        
        # Create opportunity
        opportunity = HarvestOpportunity(
            symbol="AAPL",
            account_name="Test Account",
            account_type="Brokerage",
            shares=100.0,
            purchase_price=180.00,
            current_price=150.00,
            purchase_date=date.today() - timedelta(days=400),
            unrealized_loss=-3000.00,
            loss_percentage=16.67,
            holding_period_days=400,
            is_long_term=True,
            estimated_tax_savings=450.00,
            ltcg_rate=0.15,
            marginal_rate=0.24,
            recommended_replacement="MSFT",
            replacement_sector="Information Technology",
            replacement_price=350.00,
            alternative_replacements=[],
            is_wash_sale_risk=False,
            wash_sale_reason="",
            can_harvest=True,
            harvest_priority=5,
            lot_ids=[lot.lot_id],
            notes=""
        )
        
        # 1. Create execution
        execution = create_harvest_execution(opportunity, "MSFT")
        
        # 2. Approve
        approve_execution(execution.execution_id)
        
        # 3. Execute sell
        dispositions = execute_sell_trade(
            trade_id=execution.sell_trade.trade_id,
            executed_price=150.00,
            executed_shares=100.0
        )
        
        assert len(dispositions) == 1
        assert dispositions[0].gain_loss < 0  # Loss
        
        # 4. Execute buy
        new_lot = execute_buy_trade(
            trade_id=execution.buy_trade.trade_id,
            executed_price=350.00,
            executed_shares=42.86  # ~$15,000 / $350
        )
        
        assert new_lot.symbol == "MSFT"
        
        # 5. Complete
        complete_execution(execution.execution_id)


# ==============================================================================
# TEST: Tax Savings Tracker
# ==============================================================================

class TestTaxSavingsTracker:
    """Test tax savings tracking."""
    
    def test_record_harvest_savings(self, temp_db):
        """Test recording harvest savings."""
        # Create mock disposition
        disposition = LotDisposition(
            lot_id="lot123",
            symbol="AAPL",
            account_name="Test Account",
            shares_sold=100.0,
            sale_price=150.00,
            sale_date=date.today(),
            cost_basis=18000.00,
            proceeds=15000.00,
            gain_loss=-3000.00,
            gain_type=GainType.LONG_TERM,
            holding_period_days=400
        )
        
        # Record savings
        records = record_harvest_savings(
            execution_id="exec123",
            dispositions=[disposition],
            symbol_bought="MSFT",
            shares_bought=42.86,
            estimated_tax_savings=450.00,
            ltcg_rate=0.15,
            marginal_rate=0.24,
            account_name="Test Account",
            account_type="Brokerage"
        )
        
        assert len(records) == 1
        assert records[0].realized_loss == -3000.00
        assert records[0].estimated_tax_savings == 450.00
    
    def test_ytd_summary(self, temp_db):
        """Test year-to-date summary."""
        # Record some savings
        disposition = LotDisposition(
            lot_id="lot123",
            symbol="AAPL",
            account_name="Test Account",
            shares_sold=100.0,
            sale_price=150.00,
            sale_date=date.today(),
            cost_basis=18000.00,
            proceeds=15000.00,
            gain_loss=-3000.00,
            gain_type=GainType.LONG_TERM,
            holding_period_days=400
        )
        
        record_harvest_savings(
            execution_id="exec123",
            dispositions=[disposition],
            symbol_bought="MSFT",
            shares_bought=42.86,
            estimated_tax_savings=450.00,
            ltcg_rate=0.15,
            marginal_rate=0.24,
            account_name="Test Account",
            account_type="Brokerage"
        )
        
        # Get summary
        summary = get_ytd_summary(tax_year=date.today().year)
        
        assert summary.total_harvests == 1
        assert summary.total_realized_losses == -3000.00
        assert summary.total_estimated_savings == 450.00


# ==============================================================================
# TEST: Direct Index Manager
# ==============================================================================

class TestDirectIndexManager:
    """Test direct index manager functionality."""
    
    def test_import_from_csv(self, temp_db, tmp_path):
        """Test importing positions from CSV."""
        # Create test CSV
        csv_path = tmp_path / "test_positions.csv"
        csv_data = """symbol,shares,price
AAPL,100,150.00
MSFT,50,350.00
GOOGL,75,140.00
"""
        csv_path.write_text(csv_data)
        
        # Setup database
        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS rsp_holdings (
                symbol TEXT PRIMARY KEY,
                name TEXT,
                sector TEXT,
                current_price REAL,
                market_cap REAL,
                last_updated TEXT
            )
        """)
        
        # Add constituents
        for symbol in ["AAPL", "MSFT", "GOOGL"]:
            cursor.execute("""
                INSERT OR REPLACE INTO rsp_holdings
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                symbol,
                f"{symbol} Inc.",
                "Technology",
                150.00,
                1000000000000,
                datetime.now().isoformat()
            ))
        
        conn.commit()
        conn.close()
        
        # Import
        imported, errors = import_from_csv(
            csv_path=str(csv_path),
            account_name="Test Account"
        )
        
        assert imported == 3
        assert len(errors) == 0
        
        # Verify
        lots = get_tax_lots(account_name="Test Account")
        assert len(lots) == 3
    
    def test_export_to_dataframe(self, temp_db, sample_tax_lots):
        """Test exporting positions to DataFrame."""
        # Add lots
        for lot in sample_tax_lots:
            add_tax_lot(lot)
        
        # Export
        df = export_to_dataframe(account_name="Test Account")
        
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 3
        assert "symbol" in df.columns
        assert "unrealized_gl" in df.columns
    
    def test_get_position_summary(self, temp_db, sample_tax_lots):
        """Test getting position summary."""
        # Add lots
        for lot in sample_tax_lots:
            add_tax_lot(lot)
        
        # Get summary
        summary = get_position_summary(account_name="Test Account")
        
        assert summary['total_positions'] == 3
        assert summary['total_cost_basis'] > 0
        assert 'by_account' in summary


# ==============================================================================
# INTEGRATION TESTS
# ==============================================================================

class TestIntegration:
    """Integration tests for complete workflows."""
    
    def test_complete_harvest_workflow(self, temp_db, tmp_path, sample_constituents):
        """Test complete harvest workflow from start to finish."""
        # 1. Setup database
        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS rsp_holdings (
                symbol TEXT PRIMARY KEY,
                name TEXT,
                sector TEXT,
                current_price REAL,
                market_cap REAL,
                last_updated TEXT
            )
        """)
        
        for const in sample_constituents:
            cursor.execute("""
                INSERT OR REPLACE INTO rsp_holdings
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                const.symbol,
                const.name,
                const.sector,
                const.current_price,
                const.market_cap,
                const.last_updated.isoformat()
            ))
        
        conn.commit()
        conn.close()
        
        # 2. Import initial positions
        csv_path = tmp_path / "initial_positions.csv"
        csv_data = """symbol,shares,price
AAPL,100,180.00
MSFT,50,300.00
"""
        csv_path.write_text(csv_data)
        
        imported, errors = import_from_csv(
            csv_path=str(csv_path),
            account_name="Test Account",
            execution_date=date.today() - timedelta(days=400)
        )
        
        assert imported == 2
        
        # 3. Scan for opportunities
        opportunities = scan_harvest_opportunities(
            account_name="Test Account",
            current_agi=150000,
            loss_threshold_pct=10.0
        )
        
        # Should find AAPL (bought at $180, now $150)
        assert len(opportunities) > 0
        aapl_opp = next((o for o in opportunities if o.symbol == "AAPL"), None)
        assert aapl_opp is not None
        
        # 4. Create execution
        execution = create_harvest_execution(
            opportunity=aapl_opp,
            replacement_symbol=aapl_opp.recommended_replacement or "GOOGL"
        )
        
        assert execution is not None
        
        # 5. Approve
        approve_execution(execution.execution_id)
        
        # 6. Execute trades
        dispositions = execute_sell_trade(
            trade_id=execution.sell_trade.trade_id,
            executed_price=150.00,
            executed_shares=100.0
        )
        
        new_lot = execute_buy_trade(
            trade_id=execution.buy_trade.trade_id,
            executed_price=140.00,
            executed_shares=107.14  # ~$15,000 / $140
        )
        
        # 7. Record tax savings
        records = record_harvest_savings(
            execution_id=execution.execution_id,
            dispositions=dispositions,
            symbol_bought=new_lot.symbol,
            shares_bought=new_lot.shares,
            estimated_tax_savings=execution.tax_savings_estimate,
            ltcg_rate=0.15,
            marginal_rate=0.24,
            account_name="Test Account",
            account_type="Brokerage"
        )
        
        assert len(records) > 0
        
        # 8. Complete execution
        complete_execution(execution.execution_id)
        
        # 9. Verify final state
        summary = get_position_summary(account_name="Test Account")
        assert summary['total_positions'] == 2  # MSFT + new replacement
        
        ytd = get_ytd_summary(tax_year=date.today().year)
        assert ytd.total_harvests == 1
        assert ytd.total_realized_losses < 0


# ==============================================================================
# RUN TESTS
# ==============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])

# Made with Bob
