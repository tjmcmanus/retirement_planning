#!/usr/bin/env python3
"""
test_app_functionality.py

Comprehensive test suite to validate the retirement planning application
functionality, including configuration loading, data imports, and page structure.

Run with: python3 test_app_functionality.py
"""

import os
import sys
import json
import importlib.util
from pathlib import Path
from typing import List, Tuple, Dict, Any

# Color codes for terminal output
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'
BOLD = '\033[1m'


def print_header(text: str) -> None:
    """Print a formatted header."""
    print(f"\n{BOLD}{BLUE}{'=' * 70}{RESET}")
    print(f"{BOLD}{BLUE}{text:^70}{RESET}")
    print(f"{BOLD}{BLUE}{'=' * 70}{RESET}\n")


def print_test(name: str, passed: bool, details: str = "") -> None:
    """Print test result."""
    status = f"{GREEN}✓ PASS{RESET}" if passed else f"{RED}✗ FAIL{RESET}"
    print(f"  {status}  {name}")
    if details:
        print(f"         {details}")


def test_config_file() -> Tuple[bool, str]:
    """Test that retirement_config.json exists and is valid."""
    try:
        if not os.path.exists("retirement_config.json"):
            return False, "File does not exist"
        
        with open("retirement_config.json", 'r') as f:
            config = json.load(f)
        
        # Check required sections
        required_sections = [
            "personal_info", "financial_assumptions", "income",
            "social_security", "healthcare", "tax_strategy"
        ]
        missing = [s for s in required_sections if s not in config]
        if missing:
            return False, f"Missing sections: {', '.join(missing)}"
        
        return True, f"Valid JSON with {len(config)} sections"
    except json.JSONDecodeError as e:
        return False, f"Invalid JSON: {e}"
    except Exception as e:
        return False, f"Error: {e}"


def test_config_module() -> Tuple[bool, str]:
    """Test that config.py loads and ConfigManager works."""
    try:
        from config import ConfigManager, DEFAULT_CONFIG
        
        # Test with existing file
        mgr = ConfigManager()
        
        # Test get method
        person1_name = mgr.get("personal_info", "person1_name")
        if not person1_name:
            return False, "Could not retrieve person1_name"
        
        # Test that defaults are available
        if not DEFAULT_CONFIG:
            return False, "DEFAULT_CONFIG is empty"
        
        return True, f"ConfigManager loaded, person1_name='{person1_name}'"
    except Exception as e:
        return False, f"Error: {e}"


def test_config_fallback() -> Tuple[bool, str]:
    """Test that config falls back to defaults when file is missing."""
    try:
        from config import ConfigManager, DEFAULT_CONFIG
        
        # Test with non-existent file
        mgr = ConfigManager("nonexistent_config.json")
        
        # Should still work with defaults
        person1_name = mgr.get("personal_info", "person1_name")
        if not person1_name:
            return False, "Fallback failed - no person1_name"
        
        return True, f"Fallback works, using default person1_name='{person1_name}'"
    except Exception as e:
        return False, f"Error: {e}"


def test_required_files() -> Tuple[bool, str]:
    """Test that all required application files exist."""
    required_files = [
        "planning_app.py",
        "config.py",
        "portfolio.py",
        "calculations.py",
        "load_data.py",
        "components/shared.py",
        "components/navbar.py",
        "components/sidebar.py",
        "pages/3_dashboard.py",
        "pages/4_portfolio.py",
        "pages/5_strategy.py",
        "pages/6_monte_carlo.py",
        "pages/7_flow_of_funds.py",
        "pages/8_advanced_strategies.py",
    ]
    
    missing = [f for f in required_files if not os.path.exists(f)]
    if missing:
        return False, f"Missing files: {', '.join(missing)}"
    
    return True, f"All {len(required_files)} required files present"


def test_data_files() -> Tuple[bool, str]:
    """Test that required data files exist."""
    required_data = [
        "income_rates.csv",
        "cap_gains.csv",
        "standard.csv",
        "irmaa.csv",
        "rmd.csv",
        "ssincome.csv",
    ]
    
    missing = [f for f in required_data if not os.path.exists(f)]
    if missing:
        return False, f"Missing data files: {', '.join(missing)}"
    
    return True, f"All {len(required_data)} data files present"


def test_python_syntax() -> Tuple[bool, str]:
    """Test that all Python files have valid syntax."""
    import ast
    
    python_files = [
        "planning_app.py",
        "config.py",
        "portfolio.py",
        "calculations.py",
        "components/shared.py",
        "components/navbar.py",
        "components/sidebar.py",
        "pages/3_dashboard.py",
        "pages/4_portfolio.py",
        "pages/5_strategy.py",
        "pages/6_monte_carlo.py",
        "pages/7_flow_of_funds.py",
        "pages/8_advanced_strategies.py",
    ]
    
    errors = []
    for filepath in python_files:
        try:
            with open(filepath) as f:
                ast.parse(f.read())
        except SyntaxError as e:
            errors.append(f"{filepath}:{e.lineno}")
    
    if errors:
        return False, f"Syntax errors in: {', '.join(errors)}"
    
    return True, f"All {len(python_files)} files have valid syntax"


def test_imports() -> Tuple[bool, str]:
    """Test that key modules can be imported."""
    modules_to_test = [
        ("config", "ConfigManager"),
        ("portfolio", "get_current_price"),
        ("calculations", "calculate_taxable_income"),
        ("load_data", "get_income_tax_brackets"),
    ]
    
    errors = []
    for module_name, attr_name in modules_to_test:
        try:
            module = __import__(module_name)
            if not hasattr(module, attr_name):
                errors.append(f"{module_name}.{attr_name} not found")
        except ImportError as e:
            errors.append(f"{module_name}: {e}")
    
    if errors:
        return False, f"Import errors: {'; '.join(errors)}"
    
    return True, f"All {len(modules_to_test)} key modules import successfully"


def test_requirements() -> Tuple[bool, str]:
    """Test that requirements.txt exists and contains key dependencies."""
    try:
        if not os.path.exists("requirements.txt"):
            return False, "requirements.txt not found"
        
        with open("requirements.txt") as f:
            reqs = f.read()
        
        required_packages = [
            "streamlit",
            "pandas",
            "numpy",
            "plotly",
            "streamlit-option-menu",
        ]
        
        missing = [pkg for pkg in required_packages if pkg not in reqs.lower()]
        if missing:
            return False, f"Missing packages: {', '.join(missing)}"
        
        return True, f"All {len(required_packages)} required packages listed"
    except Exception as e:
        return False, f"Error: {e}"


def test_page_structure() -> Tuple[bool, str]:
    """Test that pages have proper structure (imports navbar)."""
    pages_to_check = [
        "pages/3_dashboard.py",
        "pages/4_portfolio.py",
        "pages/5_strategy.py",
        "pages/6_monte_carlo.py",
        "pages/7_flow_of_funds.py",
        "pages/8_advanced_strategies.py",
    ]
    
    issues = []
    for page in pages_to_check:
        try:
            with open(page) as f:
                content = f.read()
            
            # Check for navbar import (either style)
            has_navbar = (
                "from components.navbar import navbar" in content or
                "from components import navbar" in content or
                "import components.navbar" in content
            )
            
            if not has_navbar:
                issues.append(f"{page}: missing navbar import")
        except Exception as e:
            issues.append(f"{page}: {e}")
    
    if issues:
        return False, f"Issues: {'; '.join(issues)}"
    
    return True, f"All {len(pages_to_check)} pages have proper structure"


def test_shared_init() -> Tuple[bool, str]:
    """Test that components/shared.py has init_page function."""
    try:
        with open("components/shared.py") as f:
            content = f.read()
        
        if "def init_page(" not in content:
            return False, "init_page() function not found"
        
        if "def auto_rerun_if_rebuilding(" not in content:
            return False, "auto_rerun_if_rebuilding() function not found"
        
        return True, "Shared initialization functions present"
    except Exception as e:
        return False, f"Error: {e}"


def test_navbar_routes() -> Tuple[bool, str]:
    """Test that navbar has proper route definitions."""
    try:
        with open("components/navbar.py") as f:
            content = f.read()
        
        if "NAV_ROUTES" not in content:
            return False, "NAV_ROUTES not defined"
        
        required_routes = [
            "Dashboard", "Portfolio", "Strategy",
            "Monte Carlo", "Flow of Funds", "Advanced"
        ]
        
        missing = [r for r in required_routes if r not in content]
        if missing:
            return False, f"Missing routes: {', '.join(missing)}"
        
        return True, f"All {len(required_routes)} navigation routes defined"
    except Exception as e:
        return False, f"Error: {e}"


def run_all_tests() -> Dict[str, Tuple[bool, str]]:
    """Run all tests and return results."""
    tests = [
        ("Configuration File (retirement_config.json)", test_config_file),
        ("Config Module (config.py)", test_config_module),
        ("Config Fallback to Defaults", test_config_fallback),
        ("Required Application Files", test_required_files),
        ("Required Data Files", test_data_files),
        ("Python Syntax Validation", test_python_syntax),
        ("Module Imports", test_imports),
        ("Requirements File", test_requirements),
        ("Page Structure", test_page_structure),
        ("Shared Initialization", test_shared_init),
        ("Navigation Routes", test_navbar_routes),
    ]
    
    results = {}
    for name, test_func in tests:
        try:
            passed, details = test_func()
            results[name] = (passed, details)
        except Exception as e:
            results[name] = (False, f"Test crashed: {e}")
    
    return results


def main():
    """Main test runner."""
    print_header("Retirement Planning Application - Functionality Tests")
    
    print(f"{BOLD}Working Directory:{RESET} {os.getcwd()}")
    print(f"{BOLD}Python Version:{RESET} {sys.version.split()[0]}\n")
    
    results = run_all_tests()
    
    # Print results
    print(f"\n{BOLD}Test Results:{RESET}\n")
    for name, (passed, details) in results.items():
        print_test(name, passed, details)
    
    # Summary
    total = len(results)
    passed = sum(1 for p, _ in results.values() if p)
    failed = total - passed
    
    print(f"\n{BOLD}{'─' * 70}{RESET}")
    print(f"{BOLD}Summary:{RESET} {passed}/{total} tests passed")
    
    if failed > 0:
        print(f"{RED}{BOLD}⚠ {failed} test(s) failed{RESET}")
        sys.exit(1)
    else:
        print(f"{GREEN}{BOLD}✓ All tests passed!{RESET}")
        print(f"\n{BOLD}Application is ready to run:{RESET}")
        print(f"  streamlit run planning_app.py\n")
        sys.exit(0)


if __name__ == "__main__":
    main()

# Made with Bob
