#!/bin/bash
#
# Retirement Withdrawal Strategy Runner
# 
# This script runs the example withdrawal strategy calculations
# and generates comprehensive reports for retirement planning.
#
# Usage:
#   ./run_strategy.sh
#   bash run_strategy.sh
#

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

echo -e "${BLUE}================================================================================================${NC}"
echo -e "${BLUE}                    RETIREMENT WITHDRAWAL STRATEGY - RUNNER${NC}"
echo -e "${BLUE}================================================================================================${NC}"
echo ""

# Check if Python 3 is available
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}❌ Error: python3 is not installed or not in PATH${NC}"
    echo "Please install Python 3 to run this script."
    exit 1
fi

echo -e "${GREEN}✓${NC} Python 3 found: $(python3 --version)"

# Check if required Python packages are installed
echo ""
echo -e "${YELLOW}Checking required Python packages...${NC}"

REQUIRED_PACKAGES=("pandas" "numpy" "streamlit" "yfinance")
MISSING_PACKAGES=()

for package in "${REQUIRED_PACKAGES[@]}"; do
    if python3 -c "import $package" 2>/dev/null; then
        echo -e "${GREEN}✓${NC} $package installed"
    else
        echo -e "${RED}✗${NC} $package NOT installed"
        MISSING_PACKAGES+=("$package")
    fi
done

if [ ${#MISSING_PACKAGES[@]} -gt 0 ]; then
    echo ""
    echo -e "${YELLOW}⚠️  Missing packages detected. Install with:${NC}"
    echo "   pip3 install ${MISSING_PACKAGES[*]}"
    echo ""
    read -p "Would you like to install missing packages now? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo -e "${YELLOW}Installing missing packages...${NC}"
        pip3 install "${MISSING_PACKAGES[@]}"
        echo -e "${GREEN}✓${NC} Packages installed successfully"
    else
        echo -e "${RED}❌ Cannot proceed without required packages${NC}"
        exit 1
    fi
fi

# Check if required data files exist
echo ""
echo -e "${YELLOW}Checking required data files...${NC}"

REQUIRED_FILES=(
    "withdrawal_strategy.py"
    "example_withdrawal_strategy.py"
    "load_data.py"
    "calculations.py"
    "ssibenefits.py"
    "portfolio_data_truth.csv"
    "income_rates.csv"
    "cap_gains.csv"
    "standard.csv"
    "irmaa.csv"
    "ssincome.csv"
    "rmd.csv"
)

MISSING_FILES=()

for file in "${REQUIRED_FILES[@]}"; do
    if [ -f "$file" ]; then
        echo -e "${GREEN}✓${NC} $file"
    else
        echo -e "${RED}✗${NC} $file NOT FOUND"
        MISSING_FILES+=("$file")
    fi
done

if [ ${#MISSING_FILES[@]} -gt 0 ]; then
    echo ""
    echo -e "${RED}❌ Error: Missing required files${NC}"
    echo "Please ensure all required files are in the current directory."
    exit 1
fi

# Run the example withdrawal strategy
echo ""
echo -e "${BLUE}================================================================================================${NC}"
echo -e "${BLUE}                    RUNNING WITHDRAWAL STRATEGY EXAMPLES${NC}"
echo -e "${BLUE}================================================================================================${NC}"
echo ""

python3 example_withdrawal_strategy.py

EXIT_CODE=$?

if [ $EXIT_CODE -eq 0 ]; then
    echo ""
    echo -e "${GREEN}================================================================================================${NC}"
    echo -e "${GREEN}                    ✅ STRATEGY CALCULATION COMPLETED SUCCESSFULLY${NC}"
    echo -e "${GREEN}================================================================================================${NC}"
    echo ""
    echo -e "${YELLOW}Generated Output Files:${NC}"
    
    OUTPUT_FILES=(
        "example1_strategy.csv"
        "example2_early_retire.csv"
        "example3_high_income.csv"
        "example4_custom.csv"
    )
    
    for file in "${OUTPUT_FILES[@]}"; do
        if [ -f "$file" ]; then
            SIZE=$(ls -lh "$file" | awk '{print $5}')
            echo -e "  ${GREEN}✓${NC} $file (${SIZE})"
        fi
    done
    
    echo ""
    echo -e "${YELLOW}Next Steps:${NC}"
    echo "  1. Review the generated CSV files for detailed year-by-year strategies"
    echo "  2. Open CSV files in Excel or Google Sheets for analysis"
    echo "  3. Compare different scenarios to optimize your retirement plan"
    echo "  4. Adjust parameters in example_withdrawal_strategy.py for custom scenarios"
    echo ""
    echo -e "${BLUE}For more information, see:${NC}"
    echo "  - WITHDRAWAL_STRATEGY_README.md - Complete documentation"
    echo "  - IMPLEMENTATION_SUMMARY.md - Implementation overview"
    echo ""
else
    echo ""
    echo -e "${RED}================================================================================================${NC}"
    echo -e "${RED}                    ❌ STRATEGY CALCULATION FAILED${NC}"
    echo -e "${RED}================================================================================================${NC}"
    echo ""
    echo -e "${YELLOW}Troubleshooting:${NC}"
    echo "  1. Check that all required CSV data files are present"
    echo "  2. Verify portfolio_data_truth.csv has data for current month/year"
    echo "  3. Ensure ssincome.csv has data for person names (Tom, Sarah)"
    echo "  4. Review error messages above for specific issues"
    echo ""
    echo -e "${YELLOW}For help, see:${NC}"
    echo "  - WITHDRAWAL_STRATEGY_README.md (Troubleshooting section)"
    echo ""
    exit $EXIT_CODE
fi

echo -e "${BLUE}================================================================================================${NC}"

# Made with Bob
