#!/bin/bash
# Force restart script - clears all caches and restarts Streamlit

echo "🛑 Stopping any running Streamlit processes..."
pkill -f streamlit

echo "🗑️  Clearing Python cache..."
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null
find . -type f -name "*.pyc" -delete 2>/dev/null
find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null

echo "🗑️  Clearing Streamlit cache..."
rm -rf .streamlit/cache 2>/dev/null

echo "⏳ Waiting for processes to stop..."
sleep 2

echo ""
echo "✅ Cache cleared and processes stopped!"
echo ""
echo "📝 Next steps:"
echo "1. Run: streamlit run planning_app.py"
echo "2. Navigate to the Strategy page"
echo "3. Verify 2026 AGI shows $371,350 (not $247,000)"
echo ""
echo "Expected 2026 values:"
echo "  - AGI: $371,350"
echo "  - MAGI: $371,350"
echo "  - Taxable Income: $339,150"
echo "  - Effective Rate: ~21.9%"

# Made with Bob
