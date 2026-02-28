#!/bin/bash

# Tax & Retirement Planning Application - Run Script
# This script sets up and runs the Streamlit application

set -e  # Exit on error

echo "=================================="
echo "Tax & Retirement Planning App"
echo "=================================="
echo ""

# Check if Python 3 is installed
if ! command -v python3 &> /dev/null; then
    echo "Error: Python 3 is not installed."
    echo "Please install Python 3.8 or higher from https://www.python.org/"
    exit 1
fi

echo "✓ Python 3 found: $(python3 --version)"
echo ""

# Check if virtual environment exists
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv .venv
    echo "✓ Virtual environment created"
    echo ""
fi

# Activate virtual environment
echo "Activating virtual environment..."
source .venv/bin/activate
echo "✓ Virtual environment activated"
echo ""

# Install/upgrade pip
echo "Upgrading pip..."
pip install --upgrade pip --quiet
echo "✓ pip upgraded"
echo ""

# Install requirements
echo "Installing dependencies..."
if [ -f "requirements.txt" ]; then
    pip install -r requirements.txt --quiet
    echo "✓ Dependencies installed"
else
    echo "Warning: requirements.txt not found"
    echo "Installing minimal dependencies..."
    pip install streamlit pandas numpy plotly yfinance streamlit-card streamlit-extras --quiet
fi
echo ""

# Check for required Python module files
echo "Checking for required Python modules..."
REQUIRED_MODULES=(
    "planning_app.py"
    "load_data.py"
    "calculations.py"
    "portfolio.py"
    "portfolio_data_entry.py"
    "income_expense.py"
    "strategy.py"
    "betr_roth_conversion.py"
    "ssibenefits.py"
    "config.py"
    "components/sidebar.py"
)

MISSING_FILES=()
for file in "${REQUIRED_MODULES[@]}"; do
    if [ ! -f "$file" ]; then
        MISSING_FILES+=("$file")
    fi
done

# Check for required CSV data files
echo "Checking for required data files..."
REQUIRED_CSV_FILES=(
    "income_rates.csv"
    "cap_gains.csv"
    "standard.csv"
    "irmaa.csv"
    "atm.csv"
    "rmd.csv"
    "ssincome.csv"
)

for file in "${REQUIRED_CSV_FILES[@]}"; do
    if [ ! -f "$file" ]; then
        MISSING_FILES+=("$file")
    fi
done

# Check for portfolio data file (optional but recommended)
if [ ! -f "portfolio_data_truth.csv" ]; then
    echo "⚠ Warning: portfolio_data_truth.csv not found"
    echo "  You can create this file using the Portfolio Data Entry page in the app"
fi

if [ ${#MISSING_FILES[@]} -gt 0 ]; then
    echo ""
    echo "⚠ Warning: Missing required data files:"
    for file in "${MISSING_FILES[@]}"; do
        echo "  - $file"
    done
    echo ""
    echo "The application may not work correctly without these files."
    echo "Please ensure all required CSV files are present."
    echo ""
    read -p "Continue anyway? (y/N) " -n 1 -r
    echo ""
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Exiting..."
        exit 1
    fi
else
    echo "✓ All required data files found"
fi
echo ""

# Run the application
echo "=================================="
echo "Starting Streamlit application..."
echo "=================================="
echo ""
echo "The application will open in your default browser."
echo "If it doesn't open automatically, navigate to:"
echo "  http://localhost:8501"
echo ""
echo "Press Ctrl+C to stop the application"
echo ""

streamlit run planning_app.py

# Made with Bob
