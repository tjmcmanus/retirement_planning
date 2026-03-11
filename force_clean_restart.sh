#!/bin/bash
# Force clean restart script for Streamlit app

echo "=========================================="
echo "Force Clean Restart"
echo "=========================================="

# 1. Kill any running Streamlit processes
echo "1. Killing any running Streamlit processes..."
pkill -f streamlit
sleep 2

# 2. Remove Python bytecode cache
echo "2. Removing Python bytecode cache..."
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null
find . -type f -name "*.pyc" -delete 2>/dev/null
find . -type f -name "*.pyo" -delete 2>/dev/null

# 3. Remove Streamlit cache
echo "3. Removing Streamlit cache..."
rm -rf .streamlit/cache 2>/dev/null

# 4. Verify the fix is in place
echo "4. Verifying code changes..."
if grep -q "ss_benefits=taxable_ss" strategy.py; then
    echo "   ✓ Stage 5/6 fix confirmed in strategy.py"
else
    echo "   ✗ WARNING: Fix not found in strategy.py!"
fi

if grep -q "State tax is now calculated in the strategy engine" pages/5_strategy.py; then
    echo "   ✓ Display fix confirmed in pages/5_strategy.py"
else
    echo "   ✗ WARNING: Display fix not found in pages/5_strategy.py!"
fi

echo ""
echo "=========================================="
echo "Cleanup complete!"
echo "=========================================="
echo ""
echo "Now restart Streamlit with:"
echo "  streamlit run planning_app.py"
echo ""
echo "Or run this script with 'auto' to start automatically:"
echo "  ./force_clean_restart.sh auto"
echo "=========================================="

# Auto-start if requested
if [ "$1" = "auto" ]; then
    echo ""
    echo "Starting Streamlit..."
    streamlit run planning_app.py
fi

# Made with Bob
