# Test Validation Guide

## Overview

The `test_app_functionality.py` script provides comprehensive validation of the retirement planning application's functionality, configuration, and structure.

## Running the Tests

```bash
python3 test_app_functionality.py
```

## Test Coverage

The test suite validates 11 critical aspects of the application:

### 1. Configuration File (retirement_config.json)
- **Validates**: File exists and contains valid JSON
- **Checks**: All required configuration sections present
- **Sections**: personal_info, financial_assumptions, income, social_security, healthcare, tax_strategy

### 2. Config Module (config.py)
- **Validates**: ConfigManager class loads successfully
- **Checks**: Can retrieve configuration values
- **Tests**: `get()` method functionality

### 3. Config Fallback to Defaults
- **Validates**: Application works without config file
- **Checks**: DEFAULT_CONFIG provides fallback values
- **Purpose**: Ensures app works on fresh installations

### 4. Required Application Files
- **Validates**: All core application files exist
- **Files Checked**:
  - `planning_app.py` (entry point)
  - `config.py`, `portfolio.py`, `calculations.py`, `load_data.py`
  - `components/shared.py`, `components/navbar.py`, `components/sidebar.py`
  - All 6 main page files (`pages/3_dashboard.py` through `pages/8_advanced_strategies.py`)

### 5. Required Data Files
- **Validates**: Tax and benefit data files exist
- **Files Checked**:
  - `income_rates.csv` (federal tax brackets)
  - `cap_gains.csv` (capital gains rates)
  - `standard.csv` (standard deductions)
  - `irmaa.csv` (Medicare surcharges)
  - `rmd.csv` (required minimum distributions)
  - `ssincome.csv` (Social Security income limits)

### 6. Python Syntax Validation
- **Validates**: All Python files have valid syntax
- **Method**: Uses Python AST parser
- **Files**: All 13 core application files

### 7. Module Imports
- **Validates**: Key modules can be imported
- **Tests**:
  - `config.ConfigManager`
  - `portfolio.get_current_price`
  - `calculations.calculate_taxable_income`
  - `load_data.get_income_tax_brackets`

### 8. Requirements File
- **Validates**: `requirements.txt` exists and contains key dependencies
- **Required Packages**:
  - streamlit (≥1.31.0)
  - pandas
  - numpy
  - plotly
  - streamlit-option-menu

### 9. Page Structure
- **Validates**: All pages have proper imports
- **Checks**: Navbar component imported
- **Purpose**: Ensures consistent navigation across pages

### 10. Shared Initialization
- **Validates**: `components/shared.py` has required functions
- **Functions**:
  - `init_page()` - Shared page initialization
  - `auto_rerun_if_rebuilding()` - Auto-refresh on data rebuild

### 11. Navigation Routes
- **Validates**: `components/navbar.py` has all route definitions
- **Routes**:
  - Dashboard
  - Portfolio
  - Strategy
  - Monte Carlo
  - Advanced Strategies

## Test Output

### Success (Exit Code 0)
```
✓ All tests passed!

Application is ready to run:
  streamlit run planning_app.py
```

### Failure (Exit Code 1)
```
⚠ X test(s) failed
```

Each failed test shows:
- Test name
- Failure reason
- Specific details about what's missing or incorrect

## Configuration File Handling

The application gracefully handles missing configuration files:

1. **File Exists**: Loads from `retirement_config.json`
2. **File Missing**: Uses `DEFAULT_CONFIG` from `config.py`
3. **File Corrupted**: Falls back to `DEFAULT_CONFIG` with warning

This ensures the application works immediately after:
- Fresh installation
- Unzipping project files
- Configuration file deletion

## Common Issues and Solutions

### Issue: "retirement_config.json not found"
**Solution**: This is expected on first run. The app will create a default configuration.

### Issue: "Module import failed"
**Solution**: Install dependencies:
```bash
pip install -r requirements.txt
```

### Issue: "Data file missing"
**Solution**: Ensure all CSV files are present in the project root directory.

### Issue: "Syntax error in file"
**Solution**: Check the specific file and line number reported in the error.

## Integration with CI/CD

This test can be integrated into continuous integration pipelines:

```yaml
# Example GitHub Actions workflow
- name: Run functionality tests
  run: python3 test_app_functionality.py
```

## Test Maintenance

When adding new features:

1. **New Pages**: Add to `test_required_files()` and `test_page_structure()`
2. **New Data Files**: Add to `test_data_files()`
3. **New Config Sections**: Add to `test_config_file()`
4. **New Dependencies**: Add to `test_requirements()`

## Related Documentation

- [`HYBRID_ARCHITECTURE_IMPLEMENTATION.md`](HYBRID_ARCHITECTURE_IMPLEMENTATION.md) - Architecture details
- [`DASHBOARD_REVIEW.md`](DASHBOARD_REVIEW.md) - Dashboard analysis
- [`CONFIG_GUIDE.md`](CONFIG_GUIDE.md) - Configuration reference
- [`README.md`](README.md) - Main project documentation

---

**Last Updated**: March 2, 2026  
**Test Version**: 1.0  
**Test Coverage**: 11 validation checks  
**Exit Code**: 0 = Success, 1 = Failure