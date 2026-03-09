"""
Configuration module for retirement planning application.
Stores and manages application constants and user preferences.
"""

import json
import os
from datetime import datetime
from typing import Dict, Any, Optional

# Default configuration file path
CONFIG_FILE = "retirement_config.json"

# Default configuration values
DEFAULT_CONFIG = {
    "personal_info": {
        "is_single_person": False,  # True if planning for single person, False for couple
        "person1_name": "Tom",
        "person1_birth_date": "1965-01-01",
        "person1_retirement_age": 62,
        "person1_retirement_year": 2026,  # Year of retirement
        "person2_name": "Sarah",
        "person2_birth_date": "1967-01-01",
        "person2_retirement_age": 62,
        "person2_retirement_year": 2028,  # Year of retirement
        "retirement_state": "FL",  # State for retirement (affects state tax calculations)
        # List of children: each entry is {"name": str, "birth_date": "YYYY-MM-DD"}
        "children": [],
    },
    "financial_assumptions": {
        "expected_annual_expenses": 50000,
        "expense_inflation_rate": 3.0,
        "expected_rate_of_return": 6.0,
        "years_of_expenses_in_cash": 4,
        "accumulation_cash_buffer_months": 6,
    },
    "income": {
        "person1_annual_wages": 0,  # Annual wages/salary for person 1
        "person2_annual_wages": 0,  # Annual wages/salary for person 2
        "wage_inflation_rate": 3.0,  # Annual wage increase percentage
        # Accumulation-phase contribution rates (% of gross wages, 0–100)
        "contribution_401k_percent": 10.0,   # Pre-tax Traditional 401k contribution rate
        "contribution_roth_percent": 5.0,    # Roth 401k / Roth IRA contribution rate
        "contribution_brokerage_percent": 5.0,  # After-tax brokerage contribution rate
    },
    "social_security": {
        "person1_ssi_age": 70,
        "person1_ssi_amount": 0,
        "person2_ssi_age": 70,
        "person2_ssi_amount": 0,
    },
    "healthcare": {
        "aca_insurance_monthly": 0,
        "aca_start_age": 62,
        "aca_end_age": 65,
        "medicare_start_age": 65,
        "person1_preretirement_coverage_type": "None",  # Pre-retirement coverage type: "None", "Employer", or "ACA Marketplace"
        "person1_preretirement_insurance_monthly": 0,  # Monthly premium for person1's pre-retirement insurance
        "person1_retirement_coverage_type": "None",  # Retirement coverage type: "None", "Employer Retiree", or "ACA Marketplace"
        "person1_aca_insurance_monthly": 0,  # Monthly premium for person1's retirement insurance
        "person1_aca_start_age": 62,
        "person1_aca_end_age": 65,
        "person1_medicare_start_age": 65,
        "person2_preretirement_coverage_type": "None",  # Pre-retirement coverage type: "None", "Employer", or "ACA Marketplace"
        "person2_preretirement_insurance_monthly": 0,  # Monthly premium for person2's pre-retirement insurance
        "person2_retirement_coverage_type": "None",  # Retirement coverage type: "None", "Employer Retiree", or "ACA Marketplace"
        "person2_aca_insurance_monthly": 0,  # Monthly premium for person2's retirement insurance
        "person2_aca_start_age": 62,
        "person2_aca_end_age": 65,
        "person2_medicare_start_age": 65,
    },
    "tax_strategy": {
        "max_roth_conversion_tax_rate": 12,
    },
    "charitable_giving": {
        "annual_charitable_giving": 0,
        "charitable_giving_start_age": 65,
        "charitable_giving_end_age": 95,
        "charitable_giving_inflation_rate": 2.0,
        "has_daf": False,
        "daf_provider": "",
        "daf_initial_contribution": 0,
        "daf_annual_contribution": 0,
        "daf_contribution_start_age": 60,
        "daf_contribution_end_age": 75,
    },
    "rebalancing_preferences": {
        "cash_symbol": "MF:CASH",
        "bonds_traditional": "VBTLX (Vanguard Total Bond Market Admiral)",
        "bonds_roth": "BND (Vanguard Total Bond Market ETF)",
        "bonds_brokerage": "VGIT (Vanguard Intermediate-Term Treasury ETF)",
        "stocks_traditional": "VFIAX (Vanguard 500 Index Admiral)",
        "stocks_roth": "VTI (Vanguard Total Market ETF)",
        "stocks_brokerage": "VTI (Vanguard Total Market ETF)",
    },
    "bucket_strategy": {
        "enabled": False,
        "bucket_1_years": 2,
        "bucket_2_years": 8,
        "bucket_2_start_stock_pct": 10,
        "bucket_2_end_stock_pct": 80,
        "market_trend_adjustment": {
            "enabled": True,
            "short_ma_weeks": 10,
            "long_ma_weeks": 50,
            "bull_adjustment": 0.0,
            "warning_adjustment": -10.0,
            "bear_adjustment": -20.0
        }
    },
    "metadata": {
        "last_updated": None,
        "version": "1.0"
    }
}


class ConfigManager:
    """Manages application configuration with file persistence."""
    
    def __init__(self, config_file: str = CONFIG_FILE):
        """
        Initialize configuration manager.
        
        Args:
            config_file: Path to configuration file
        """
        self.config_file = config_file
        self.config = self._load_config()
    
    def _load_config(self) -> Dict[str, Any]:
        """
        Load configuration from file or create default.
        
        Returns:
            Configuration dictionary
        """
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r') as f:
                    config = json.load(f)
                    # Merge with defaults to ensure all keys exist
                    return self._merge_with_defaults(config)
            except (json.JSONDecodeError, IOError) as e:
                print(f"Error loading config file: {e}. Using defaults.")
                return DEFAULT_CONFIG.copy()
        else:
            return DEFAULT_CONFIG.copy()
    
    def _merge_with_defaults(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Merge loaded config with defaults to ensure all keys exist.
        
        Args:
            config: Loaded configuration
            
        Returns:
            Merged configuration
        """
        merged = DEFAULT_CONFIG.copy()
        for section, values in config.items():
            if section in merged and isinstance(values, dict):
                merged[section].update(values)
            else:
                merged[section] = values
        return merged
    
    def save_config(self) -> bool:
        """
        Save current configuration to file.
        
        Returns:
            True if successful, False otherwise
        """
        try:
            self.config["metadata"]["last_updated"] = datetime.now().isoformat()
            with open(self.config_file, 'w') as f:
                json.dump(self.config, f, indent=2)
            return True
        except IOError as e:
            print(f"Error saving config file: {e}")
            return False
    
    def get(self, section: str, key: str, default: Any = None) -> Any:
        """
        Get a configuration value.
        
        Args:
            section: Configuration section
            key: Configuration key
            default: Default value if not found
            
        Returns:
            Configuration value or default
        """
        return self.config.get(section, {}).get(key, default)
    
    def set(self, section: str, key: str, value: Any) -> None:
        """
        Set a configuration value.
        
        Args:
            section: Configuration section
            key: Configuration key
            value: Value to set
        """
        if section not in self.config:
            self.config[section] = {}
        self.config[section][key] = value
    
    def get_section(self, section: str) -> Dict[str, Any]:
        """
        Get entire configuration section.
        
        Args:
            section: Configuration section name
            
        Returns:
            Section dictionary
        """
        return self.config.get(section, {})
    
    def update_section(self, section: str, values: Dict[str, Any]) -> None:
        """
        Update entire configuration section.
        
        Args:
            section: Configuration section name
            values: Dictionary of values to update
        """
        if section not in self.config:
            self.config[section] = {}
        self.config[section].update(values)
    
    def reset_to_defaults(self) -> None:
        """Reset configuration to default values."""
        self.config = DEFAULT_CONFIG.copy()
    
    def export_config(self) -> str:
        """
        Export configuration as JSON string.
        
        Returns:
            JSON string of configuration
        """
        return json.dumps(self.config, indent=2)
    
    def import_config(self, json_str: str) -> bool:
        """
        Import configuration from JSON string.
        
        Args:
            json_str: JSON string to import
            
        Returns:
            True if successful, False otherwise
        """
        try:
            imported = json.loads(json_str)
            self.config = self._merge_with_defaults(imported)
            return True
        except json.JSONDecodeError as e:
            print(f"Error importing config: {e}")
            return False
    
    def calculate_age(self, birth_date_str: str, as_of_date: Optional[datetime] = None) -> int:
        """
        Calculate age from birth date.
        
        Args:
            birth_date_str: Birth date in YYYY-MM-DD format
            as_of_date: Date to calculate age as of (default: today)
            
        Returns:
            Age in years
        """
        try:
            birth_date = datetime.strptime(birth_date_str, "%Y-%m-%d")
            if as_of_date is None:
                as_of_date = datetime.now()
            age = as_of_date.year - birth_date.year
            if (as_of_date.month, as_of_date.day) < (birth_date.month, birth_date.day):
                age -= 1
            return age
        except ValueError:
            return 0
    def get_filing_status(self) -> str:
        """
        Determine filing status based on personal information.
        
        Returns:
            'married_filing_jointly' if not single person and person2_name is provided, 'single' otherwise
        """
        # Check if explicitly set to single person mode
        is_single_person = self.get("personal_info", "is_single_person", False)
        if is_single_person:
            return "single"
        
        # Otherwise, check if person2_name is provided
        person2_name = self.get("personal_info", "person2_name", "")
        if person2_name and person2_name.strip():
            return "married_filing_jointly"
        return "single"
    
    
    def get_person_age(self, person_num: int, as_of_date: Optional[datetime] = None) -> int:
        """
        Get current age of person.
        
        Args:
            person_num: Person number (1 or 2)
            as_of_date: Date to calculate age as of (default: today)
            
        Returns:
            Age in years
        """
        birth_date = self.get("personal_info", f"person{person_num}_birth_date")
        if birth_date:
            return self.calculate_age(birth_date, as_of_date)
        return 0
    
    def get_annual_wages(self, year: int) -> float:
        """
        Get total annual wages for both persons in a given year.
        
        Wages are only counted if the person has not yet retired.
        Applies wage inflation from current year to target year.
        
        Args:
            year: Year to calculate wages for
            
        Returns:
            Total annual wages for both persons
        """
        current_year = datetime.now().year
        wage_inflation_rate = self.get("income", "wage_inflation_rate", 3.0) / 100.0
        
        total_wages = 0.0
        
        # Check person 1
        person1_retirement_year = self.get("personal_info", "person1_retirement_year", current_year)
        if year < person1_retirement_year:
            person1_base_wages = self.get("income", "person1_annual_wages", 0)
            years_diff = year - current_year
            person1_wages = person1_base_wages * ((1 + wage_inflation_rate) ** years_diff)
            total_wages += person1_wages
        
        # Check person 2
        person2_retirement_year = self.get("personal_info", "person2_retirement_year", current_year)
        if year < person2_retirement_year:
            person2_base_wages = self.get("income", "person2_annual_wages", 0)
            years_diff = year - current_year
            person2_wages = person2_base_wages * ((1 + wage_inflation_rate) ** years_diff)
            total_wages += person2_wages
        
        return total_wages
    
    def has_wages_in_year(self, year: int) -> bool:
        """
        Check if either person has wages in a given year.
        
        Args:
            year: Year to check
            
        Returns:
            True if either person has wages in that year
        """
        return self.get_annual_wages(year) > 0


# Global configuration instance
_config_manager = None


def get_config_manager() -> ConfigManager:
    """
    Get global configuration manager instance.
    
    Returns:
        ConfigManager instance
    """
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigManager()
    return _config_manager


def get_value_with_session_override(section: str, key: str, session_key: str, default: Any = None) -> Any:
    """
    Get a configuration value with session state override.
    Checks session state first, then falls back to config.py.
    
    Args:
        section: Configuration section
        key: Configuration key
        session_key: Session state key to check first
        default: Default value if not found in either location
        
    Returns:
        Value from session state if present, otherwise from config, otherwise default
    """
    try:
        import streamlit as st
        if session_key in st.session_state:
            return st.session_state[session_key]
    except (ImportError, AttributeError, KeyError):
        pass
    
    config_mgr = get_config_manager()
    return config_mgr.get(section, key, default)


def reload_config() -> None:
    """Reload configuration from file."""
    global _config_manager
    _config_manager = ConfigManager()

# Made with Bob
