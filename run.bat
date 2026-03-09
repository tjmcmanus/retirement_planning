@echo off
REM Tax & Retirement Planning Application - Windows Run Script
REM This script sets up and runs the Streamlit application
REM
REM WARNING: This script has NOT been tested on Windows systems.
REM If you encounter issues, please use the manual installation method
REM described in README.md and report any problems.

setlocal enabledelayedexpansion

echo ==================================
echo Tax ^& Retirement Planning App
echo ==================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo Error: Python is not installed or not in PATH.
    echo Please install Python 3.8 or higher from https://www.python.org/
    echo Make sure to check "Add Python to PATH" during installation.
    pause
    exit /b 1
)

for /f "tokens=*" %%i in ('python --version') do set PYTHON_VERSION=%%i
echo [32m✓[0m Python found: %PYTHON_VERSION%
echo.

REM Check if virtual environment exists
if not exist ".venv" (
    echo Creating virtual environment...
    python -m venv .venv
    if errorlevel 1 (
        echo Error: Failed to create virtual environment
        pause
        exit /b 1
    )
    echo [32m✓[0m Virtual environment created
    echo.
)

REM Activate virtual environment
echo Activating virtual environment...
call .venv\Scripts\activate.bat
if errorlevel 1 (
    echo Error: Failed to activate virtual environment
    pause
    exit /b 1
)
REM Re-enable delayed expansion after activation
setlocal enabledelayedexpansion
echo [32m✓[0m Virtual environment activated
echo.

REM Install/upgrade pip
echo Upgrading pip...
python -m pip install --upgrade pip --quiet
echo [32m✓[0m pip upgraded
echo.

REM Install requirements
echo Installing dependencies...
if exist "requirements.txt" (
    pip install -r requirements.txt --quiet
    if errorlevel 1 (
        echo Warning: Some dependencies may have failed to install
    ) else (
        echo [32m✓[0m Dependencies installed
    )
) else (
    echo Warning: requirements.txt not found
    echo Installing minimal dependencies...
    pip install streamlit pandas numpy plotly yfinance streamlit-card streamlit-extras --quiet
)
echo.

REM Check for required Python module files
echo Checking for required Python modules...
set MISSING_COUNT=0

set "REQUIRED_MODULES=planning_app.py load_data.py calculations.py portfolio.py portfolio_data_entry.py income_expense.py strategy.py betr_roth_conversion.py ssibenefits.py config.py components\sidebar.py"

for %%f in (%REQUIRED_MODULES%) do (
    if not exist "%%f" (
        echo   [31m✗[0m Missing: %%f
        set /a MISSING_COUNT+=1
    )
)

REM Check for required CSV data files
echo Checking for required data files...
set "REQUIRED_CSV=income_rates.csv cap_gains.csv standard.csv irmaa.csv atm.csv rmd.csv ssincome.csv"

for %%f in (%REQUIRED_CSV%) do (
    if not exist "%%f" (
        echo   [31m✗[0m Missing: %%f
        set /a MISSING_COUNT+=1
    )
)

REM Check for portfolio data file (optional but recommended)
if not exist "portfolio_data_truth.csv" (
    echo [33m⚠[0m Warning: portfolio_data_truth.csv not found
    echo   You can create this file using the Portfolio Data Entry page in the app
)

if !MISSING_COUNT! gtr 0 (
    echo.
    echo [33m⚠[0m Warning: !MISSING_COUNT! required file(s) missing
    echo.
    echo The application may not work correctly without these files.
    echo Please ensure all required CSV files are present.
    echo.
    set /p CONTINUE="Continue anyway? (y/N): "
    if /i not "!CONTINUE!"=="y" (
        echo Exiting...
        pause
        exit /b 1
    )
) else (
    echo [32m✓[0m All required data files found
)
echo.

REM Run the application
echo ==================================
echo Starting Streamlit application...
echo ==================================
echo.
echo The application will open in your default browser.
echo If it doesn't open automatically, navigate to:
echo   http://localhost:8501
echo.
echo Press Ctrl+C to stop the application
echo.

streamlit run planning_app.py

REM Made with Bob

@REM Made with Bob
