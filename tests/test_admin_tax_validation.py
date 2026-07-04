#!/usr/bin/env python3
"""
test_admin_tax_validation.py

Test suite for the admin tax data validation functionality.
Tests the validation logic added to pages/9_admin_tax_data.py
"""

import sys
import pandas as pd
from io import StringIO

# Color codes for terminal output
GREEN = '\033[92m'
RED = '\033[91m'
BLUE = '\033[94m'
RESET = '\033[0m'
BOLD = '\033[1m'


def print_test(name: str, passed: bool, details: str = "") -> None:
    """Print test result."""
    status = f"{GREEN}✓ PASS{RESET}" if passed else f"{RED}✗ FAIL{RESET}"
    print(f"  {status}  {name}")
    if details:
        print(f"         {details}")


def test_validate_function_exists():
    """Test that validate_uploaded_data function exists."""
    try:
        # Import the module dynamically to avoid streamlit initialization
        import importlib.util
        spec = importlib.util.spec_from_file_location("admin_tax", "pages/9_admin_tax_data.py")
        if spec and spec.loader:
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            
            if not hasattr(module, 'validate_uploaded_data'):
                return False, "validate_uploaded_data function not found"
            
            if not hasattr(module, 'create_backup'):
                return False, "create_backup function not found"
            
            return True, "Validation functions exist"
    except Exception as e:
        return False, f"Error: {e}"


def test_schema_definitions():
    """Test that TAX_DATA_SCHEMAS is properly defined."""
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location("admin_tax", "pages/9_admin_tax_data.py")
        if spec and spec.loader:
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            
            if not hasattr(module, 'TAX_DATA_SCHEMAS'):
                return False, "TAX_DATA_SCHEMAS not found"
            
            schemas = module.TAX_DATA_SCHEMAS
            expected_files = [
                "standard.csv", "income_rates.csv", "cap_gains.csv",
                "ira_limits.csv", "irmaa.csv", "rmd.csv",
                "ssincome.csv", "atm.csv"
            ]
            
            missing = [f for f in expected_files if f not in schemas]
            if missing:
                return False, f"Missing schemas: {', '.join(missing)}"
            
            return True, f"All {len(expected_files)} schemas defined"
    except Exception as e:
        return False, f"Error: {e}"


def test_valid_standard_csv():
    """Test validation with valid standard.csv data."""
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location("admin_tax", "pages/9_admin_tax_data.py")
        if spec and spec.loader:
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            
            # Create valid test data
            csv_data = """year,filing_status,deduction
2024,married_filing_jointly,29200
2024,single,14600
2025,married_filing_jointly,30000
2025,single,15000"""
            
            df = pd.read_csv(StringIO(csv_data))
            is_valid, errors = module.validate_uploaded_data(df, "standard.csv")
            
            if not is_valid:
                return False, f"Valid data rejected: {errors}"
            
            return True, "Valid standard.csv data accepted"
    except Exception as e:
        return False, f"Error: {e}"


def test_missing_columns():
    """Test validation catches missing required columns."""
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location("admin_tax", "pages/9_admin_tax_data.py")
        if spec and spec.loader:
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            
            # Missing 'deduction' column
            csv_data = """year,filing_status
2024,married_filing_jointly
2024,single"""
            
            df = pd.read_csv(StringIO(csv_data))
            is_valid, errors = module.validate_uploaded_data(df, "standard.csv")
            
            if is_valid:
                return False, "Missing column not detected"
            
            if not any("deduction" in str(e) for e in errors):
                return False, f"Wrong error message: {errors}"
            
            return True, "Missing columns detected correctly"
    except Exception as e:
        return False, f"Error: {e}"


def test_invalid_filing_status():
    """Test validation catches invalid filing_status values."""
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location("admin_tax", "pages/9_admin_tax_data.py")
        if spec and spec.loader:
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            
            # Invalid filing_status
            csv_data = """year,filing_status,deduction
2024,invalid_status,29200
2024,single,14600"""
            
            df = pd.read_csv(StringIO(csv_data))
            is_valid, errors = module.validate_uploaded_data(df, "standard.csv")
            
            if is_valid:
                return False, "Invalid filing_status not detected"
            
            if not any("filing_status" in str(e) for e in errors):
                return False, f"Wrong error message: {errors}"
            
            return True, "Invalid filing_status detected correctly"
    except Exception as e:
        return False, f"Error: {e}"


def test_invalid_year_range():
    """Test validation catches years outside reasonable range."""
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location("admin_tax", "pages/9_admin_tax_data.py")
        if spec and spec.loader:
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            
            # Year outside range
            csv_data = """year,filing_status,deduction
1999,married_filing_jointly,29200
2024,single,14600"""
            
            df = pd.read_csv(StringIO(csv_data))
            is_valid, errors = module.validate_uploaded_data(df, "standard.csv")
            
            if is_valid:
                return False, "Invalid year range not detected"
            
            if not any("2020-2100" in str(e) for e in errors):
                return False, f"Wrong error message: {errors}"
            
            return True, "Invalid year range detected correctly"
    except Exception as e:
        return False, f"Error: {e}"


def test_non_numeric_year():
    """Test validation catches non-numeric year values."""
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location("admin_tax", "pages/9_admin_tax_data.py")
        if spec and spec.loader:
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            
            # Non-numeric year
            csv_data = """year,filing_status,deduction
abc,married_filing_jointly,29200
2024,single,14600"""
            
            df = pd.read_csv(StringIO(csv_data))
            is_valid, errors = module.validate_uploaded_data(df, "standard.csv")
            
            if is_valid:
                return False, "Non-numeric year not detected"
            
            if not any("year" in str(e).lower() and "numeric" in str(e).lower() for e in errors):
                return False, f"Wrong error message: {errors}"
            
            return True, "Non-numeric year detected correctly"
    except Exception as e:
        return False, f"Error: {e}"


def main():
    """Run all tests."""
    print(f"\n{BOLD}{BLUE}{'=' * 70}{RESET}")
    print(f"{BOLD}{BLUE}{'Admin Tax Data Validation Tests':^70}{RESET}")
    print(f"{BOLD}{BLUE}{'=' * 70}{RESET}\n")
    
    tests = [
        ("Validation Functions Exist", test_validate_function_exists),
        ("Schema Definitions Complete", test_schema_definitions),
        ("Valid Data Accepted", test_valid_standard_csv),
        ("Missing Columns Detected", test_missing_columns),
        ("Invalid Filing Status Detected", test_invalid_filing_status),
        ("Invalid Year Range Detected", test_invalid_year_range),
        ("Non-Numeric Year Detected", test_non_numeric_year),
    ]
    
    results = []
    for name, test_func in tests:
        try:
            passed, details = test_func()
            results.append((name, passed, details))
            print_test(name, passed, details)
        except Exception as e:
            results.append((name, False, f"Test crashed: {e}"))
            print_test(name, False, f"Test crashed: {e}")
    
    # Summary
    total = len(results)
    passed = sum(1 for _, p, _ in results if p)
    failed = total - passed
    
    print(f"\n{BOLD}{'─' * 70}{RESET}")
    print(f"{BOLD}Summary:{RESET} {passed}/{total} tests passed")
    
    if failed > 0:
        print(f"{RED}{BOLD}⚠ {failed} test(s) failed{RESET}\n")
        sys.exit(1)
    else:
        print(f"{GREEN}{BOLD}✓ All validation tests passed!{RESET}\n")
        sys.exit(0)


if __name__ == "__main__":
    main()

# Made with Bob
