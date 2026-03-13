---
layout: default
title: Getting Started
---

# Getting Started

This guide will help you install and configure the Financial Planner application.

## Quick Start

1. **Clone the repository**
2. **Install dependencies**
3. **Configure your data**
4. **Run the application**

## Installation

### Prerequisites

Before installing, ensure you have:

- **Python 3.9 or higher**
  - Check version: `python --version` or `python3 --version`
  - Download from [python.org](https://www.python.org/downloads/)

- **pip** (Python package installer)
  - Usually included with Python
  - Check version: `pip --version` or `pip3 --version`

- **Git** (optional, for cloning)
  - Download from [git-scm.com](https://git-scm.com/)

### Setup Steps

#### 1. Clone or Download the Repository

```bash
git clone https://github.com/yourusername/retirement_planning.git
cd retirement_planning
```

Or download and extract the ZIP file from GitHub.

#### 2. Create a Virtual Environment (Recommended)

**On macOS/Linux:**
```bash
python3 -m venv .venv
source .venv/bin/activate
```

**On Windows:**
```cmd
python -m venv .venv
.venv\Scripts\activate
```

#### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

This installs all required packages including:
- streamlit (web interface)
- pandas (data processing)
- numpy (numerical computations)
- plotly (interactive charts)
- yfinance (market data)
- and more...

#### 4. Set Up Configuration Files

Copy the sample configuration:
```bash
cp .env.example .env
```

Edit `.env` to add your API keys (optional):
```
SNAPTRADE_CLIENT_ID=your_client_id_here
SNAPTRADE_CONSUMER_KEY=your_consumer_key_here
```

## Configuration

### Method 1: Configuration Page (Recommended)

1. Launch the application
2. Navigate to the **Configuration** page (⚙️)
3. Fill in your personal information:
   - Names and birth dates
   - Current ages
   - Retirement ages
   - Life expectancy
4. Configure financial settings:
   - Filing status
   - State of residence
   - Income sources
   - Expense projections
5. Save your configuration

The configuration is stored in `retirement_config.json`.

### Method 2: Manual Configuration

Create or edit `retirement_config.json`:

```json
{
  "person1_name": "John",
  "person2_name": "Jane",
  "person1_birth_date": "1965-01-15",
  "person2_birth_date": "1967-03-20",
  "person1_current_age": 59,
  "person2_current_age": 57,
  "person1_retirement_age": 65,
  "person2_retirement_age": 65,
  "person1_life_expectancy": 95,
  "person2_life_expectancy": 95,
  "filing_status": "Married Filing Jointly",
  "state": "CA",
  "annual_expenses": 80000,
  "expense_growth_rate": 0.03
}
```

## Data Files Setup

### Required Files

#### 1. Portfolio Data (`portfolio_data_truth.csv`)

This is your primary data file containing all account information.

**Format:**
```csv
Account,Type,Owner,Balance,Basis,Contribution,Annual_Return
401k,401k,Person1,500000,500000,0,0.07
Roth IRA,Roth IRA,Person1,100000,80000,7000,0.07
Brokerage,Taxable,Joint,250000,200000,0,0.07
```

**Columns:**
- `Account`: Account name/identifier
- `Type`: Account type (401k, Roth IRA, Traditional IRA, Taxable, HSA)
- `Owner`: Person1, Person2, or Joint
- `Balance`: Current account balance
- `Basis`: Cost basis (for taxable accounts and Roth)
- `Contribution`: Annual contribution amount
- `Annual_Return`: Expected annual return (e.g., 0.07 for 7%)

**Sample file:** Use `portfolio_data_truth.sample.csv` as a template

#### 2. Tax Reference Files

These files are included with the application:

- `standard.csv` - Federal income tax brackets
- `cap_gains.csv` - Capital gains tax rates
- `irmaa.csv` - Medicare IRMAA thresholds
- `atm.csv` - Alternative Minimum Tax
- `rmd.csv` - Required Minimum Distribution tables

#### 3. Social Security Files

- `ssincome.csv` - Social Security benefit estimates

**Format:**
```csv
Person,Age,Monthly_Benefit
Person1,62,2500
Person1,67,3500
Person1,70,4300
```

## Running the Application

### Method 1: Using Run Scripts (Recommended)

**On macOS/Linux:**
```bash
./run.sh
```

**On Windows:**
```cmd
run.bat
```

The application will open in your default web browser at `http://localhost:8501`

### Method 2: Manual Start

```bash
streamlit run planning_app.py
```

### Method 3: With Custom Port

```bash
streamlit run planning_app.py --server.port 8502
```

## First-Time Setup Checklist

- [ ] Python 3.9+ installed
- [ ] Virtual environment created and activated
- [ ] Dependencies installed (`pip install -r requirements.txt`)
- [ ] Configuration file created (`retirement_config.json`)
- [ ] Portfolio data file created (`portfolio_data_truth.csv`)
- [ ] Application launches successfully
- [ ] Configuration page accessible
- [ ] Dashboard displays data correctly

## Quick Start with Sample Data

To quickly explore the application with sample data:

1. Copy the sample files:
```bash
cp portfolio_data_truth.sample.csv portfolio_data_truth.csv
cp financial_data_sample.csv financial_data.csv
```

2. Run the application:
```bash
./run.sh
```

3. Navigate through the tabs to explore features

## Troubleshooting

### "ModuleNotFoundError"

**Problem:** Missing Python packages

**Solution:**
```bash
pip install -r requirements.txt
```

### "FileNotFoundError" for CSV files

**Problem:** Required data files not found

**Solution:**
- Ensure `portfolio_data_truth.csv` exists in the project directory
- Check that tax reference files are present
- Use sample files as templates

### Application Won't Start

**Problem:** Port already in use

**Solution:**
```bash
# Use a different port
streamlit run planning_app.py --server.port 8502
```

**Problem:** Virtual environment not activated

**Solution:**
```bash
# Activate virtual environment first
source .venv/bin/activate  # macOS/Linux
.venv\Scripts\activate     # Windows
```

### Portfolio Data Not Loading

**Problem:** CSV format issues

**Solution:**
- Check CSV file has correct headers
- Ensure no extra commas or quotes
- Verify numeric values don't have currency symbols
- Use UTF-8 encoding

## Next Steps

Once installed and running:

1. **Configure Your Profile** - Visit the Configuration page
2. **Enter Portfolio Data** - Use Portfolio Hub to add accounts
3. **Review Dashboard** - Check your financial overview
4. **Explore Strategies** - Try different withdrawal strategies
5. **Run Simulations** - Use Monte Carlo analysis

## Additional Resources

- [Features Overview](features.md) - Complete feature list
- [User Guides](guides.md) - Detailed tutorials
- [API Reference](api-reference.md) - Technical documentation
- [GitHub Repository](https://github.com/yourusername/retirement_planning)

## Getting Help

- Check the [Troubleshooting Guide](../README.md#troubleshooting)
- Review [Known Issues](../README.md#known-issues--limitations)
- Open an issue on [GitHub](https://github.com/yourusername/retirement_planning/issues)

---

[← Back to Home](../index.md) | [Next: Features →](features.md)