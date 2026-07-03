#!/bin/bash

# Direct Indexing Setup Script
# =============================
# Quick setup script for Direct Indexing functionality
#
# Author: Bob
# Date: April 18, 2026

echo "=========================================="
echo "Direct Indexing Setup"
echo "=========================================="
echo ""

# Check if Python is available
if ! command -v python3 &> /dev/null; then
    echo "❌ Error: Python 3 is not installed"
    exit 1
fi

echo "✓ Python 3 found"
echo ""

# Step 1: Run database migration
echo "Step 1: Creating database tables..."
python3 migrate_add_direct_indexing.py

if [ $? -ne 0 ]; then
    echo "❌ Error: Database migration failed"
    exit 1
fi

echo ""
echo "✓ Database tables created"
echo ""

# Step 2: Fetch RSP holdings
echo "Step 2: Fetching RSP holdings from Yahoo Finance..."
echo "(This may take a few minutes...)"
python3 -c "from components.rsp_holdings_fetcher import fetch_rsp_holdings; fetch_rsp_holdings(force_refresh=True)"

if [ $? -ne 0 ]; then
    echo "⚠️  Warning: Failed to fetch RSP holdings"
    echo "   You can run this manually later:"
    echo "   python3 -c \"from components.rsp_holdings_fetcher import fetch_rsp_holdings; fetch_rsp_holdings(force_refresh=True)\""
else
    echo "✓ RSP holdings fetched"
fi

echo ""
echo "=========================================="
echo "Setup Complete!"
echo "=========================================="
echo ""
echo "Next steps:"
echo ""
echo "1. Start the application:"
echo "   streamlit run planning_app.py"
echo ""
echo "2. Navigate to 'Direct Indexing' in the sidebar"
echo ""
echo "3. Follow the User Guide:"
echo "   See DIRECT_INDEXING_USER_GUIDE.md"
echo ""
echo "Database location: data/rsp_holdings.db"
echo ""

# Made with Bob
