"""
Configuration module for retirement planning application.
Stores and manages application constants and user preferences.
"""

import copy
import json
import os
from datetime import datetime, date
from typing import Dict, Any, Optional, Tuple

# Default configuration file path
CONFIG_FILE = "retirement_config.json"

# Default configuration values
DEFAULT_CONFIG = {
    "personal_info": {
        "is_single_person": False,
        "person1_name": "Tom",
        "person1_birth_date": "1966-05-16",
        "person1_retirement_date": "2026-10-02",
        "person1_retirement_age": 60,
        "person1_retirement_year": 2026,
        "person2_name": "Sarah",
        "person2_birth_date": "1967-03-22",
        "person2_retirement_date": "2026-07-15",
        "person2_retirement_age": 59,
        "person2_retirement_year": 2026,
        "retirement_state": "PA",
        "children": [
            {"name": "Edwin", "birth_date": "2000-07-09", "special_needs": False},
        ],
        "surviving_spouse_mode": False,
        "decedent_person": None,
        "date_of_death": None,
    },
    "financial_assumptions": {
        "expected_annual_expenses": 148600,
        "expense_inflation_rate": 3.0,
        "expected_rate_of_return": 6.0,
        "years_of_expenses_in_cash": 2,
        "accumulation_cash_buffer_months": 6,
        "brokerage_rebalance_trigger_multiplier": 1.0,
    },
    "income": {
        "person1_annual_wages": 250000,
        "person2_annual_wages": 120000,
        "wage_inflation_rate": 3.0,
        "contribution_401k_percent": 10.0,
        "contribution_roth_percent": 5.0,
        "contribution_brokerage_percent": 5.0,
    },
    "expenses": {
        "living_expenses": {
            "property_tax": 5000,
            "homeowners_insurance": 1000,
            "auto_insurance": 4000,
            "food_groceries": 12000,
            "utilities_phone": 2400,
            "utilities_internet": 3600,
            "utilities_cable": 0,
            "utilities_electric": 6000,
            "utilities_gas": 3600,
            "utilities_water": 3000,
            "gifts_donations": 20000,
            "other_living": 10000,
        },
        "big_ticket_items": [
            {"name": "Sarah car", "amount": 70000.0, "frequency_years": 10, "start_year": 2021, "end_year": 2056},
            {"name": "Tom car",   "amount": 70000.0, "frequency_years": 10, "start_year": 2024, "end_year": 2056},
        ],
        "entertainment_expenses": {
            "travel_vacations": 30000,
            "dining_out": 18000,
            "clothing": 10000,
            "hobbies": 10000,
            "entertainment_other": 10000,
            "retirement_decline_enabled": True,
            "retirement_decline_percent": 20,
            "retirement_decline_start_age": 72,
        },
    },
    "social_security": {
        "person1_ssi_age": 70,
        "person1_ssi_amount": 4205,
        "person2_ssi_age": 70,
        "person2_ssi_amount": 4205,
        "person1_birth_year": 1960,
        "person1_gender": "M",
        "person1_life_expectancy": 84,
        "person1_current_earnings": 0,
        "person2_birth_year": 1962,
        "person2_gender": "F",
        "person2_life_expectancy": 87,
        "person2_current_earnings": 0,
    },
    "healthcare": {
        "aca_insurance_monthly": 0,
        "aca_start_age": 62,
        "aca_end_age": 65,
        "medicare_start_age": 65,
        "person1_preretirement_coverage_type": "Employer",
        "person1_preretirement_insurance_monthly": 400,
        "person1_retirement_coverage_type": "Employer Retiree",
        "person1_aca_insurance_monthly": 1000,
        "person1_aca_start_age": 62,
        "person1_aca_end_age": 65,
        "person1_medicare_start_age": 65,
        "person2_preretirement_coverage_type": "Employer",
        "person2_preretirement_insurance_monthly": 200,
        "person2_retirement_coverage_type": "Employer Retiree",
        "person2_aca_insurance_monthly": 240,
        "person2_aca_start_age": 62,
        "person2_aca_end_age": 65,
        "person2_medicare_start_age": 65,
        "person1_conditions": ["atherosclerosis"],
        "person2_conditions": ["type1_diabetes"],
    },
    "tax_strategy": {
        "max_roth_conversion_tax_rate": 24,
        "stage_1_max_conversion_rate": 32,
        "stage_2_max_conversion_rate": 32,
        "stage_3_max_conversion_rate": 32,
        "stage_4_max_conversion_rate": 32,
        "stage_5_max_conversion_rate": 24,
        "stage_6_max_conversion_rate": 24,
        "stage_7_max_conversion_rate": 15,
    },
    "charitable_giving": {
        "annual_charitable_giving": 30000,
        "charitable_giving_start_age": 61,
        "charitable_giving_end_age": 95,
        "charitable_giving_inflation_rate": 2.0,
        "has_daf": True,
        "daf_provider": "",
        "daf_initial_contribution": 230000,
        "daf_annual_contribution": 60000,
        "daf_contribution_start_age": 61,
        "daf_contribution_end_age": 75,
        "daf_trad_prefund_enabled": True,
        "daf_trad_prefund_amount": 625000,
        "daf_trad_prefund_start_year": 2027,
        "daf_trad_prefund_end_year": 2027,
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
        "enabled": True,
        "bucket_1_years": 2.0,
        "bucket_2_years": 8,
        "bucket_2_start_stock_pct": 10,
        "bucket_2_end_stock_pct": 80,
        "market_trend_adjustment": {
            "enabled": True,
            "short_ma_weeks": 10,
            "long_ma_weeks": 50,
            "bull_adjustment": 0.0,
            "warning_adjustment": -10.0,
            "bear_adjustment": -20.0,
        },
    },
    "portfolio_accounts": {
        "accounts": [
            {"account_name": "Schwab-8457",                      "account_type": "Traditional", "owner": "Joint"},
            {"account_name": "Schwab-6471",                      "account_type": "Roth",        "owner": "Sarah"},
            {"account_name": "Schwab-5553",                      "account_type": "Roth",        "owner": "Tom"},
            {"account_name": "PNC",                              "account_type": "Savings",     "owner": "Joint"},
            {"account_name": "IBM Pension (Legecy)",             "account_type": "Traditional", "owner": "Tom"},
            {"account_name": "IBM Pension",                      "account_type": "Traditional", "owner": "Tom"},
            {"account_name": "IBM ESPP",                         "account_type": "Brokerage",   "owner": "Joint"},
            {"account_name": "Highmark Pension (Legacy)",        "account_type": "Traditional", "owner": "Sarah"},
            {"account_name": "Highmark Pension",                 "account_type": "Traditional", "owner": "Sarah"},
            {"account_name": "Highmark 401k",                    "account_type": "Traditional", "owner": "Sarah"},
            {"account_name": "CVS 401k",                         "account_type": "Traditional", "owner": "Sarah"},
            {"account_name": "CAPGEMINI SAFE HARBOR 401(K) PLAN","account_type": "Traditional", "owner": "Sarah"},
            {"account_name": "IBM 401(K) PLAN",                  "account_type": "Traditional", "owner": "Tom"},
        ],
    },
    "real_estate": {
        "properties": [
            {"property_name": "McManus Home", "address": "1259 Denniston Street", "purchase_price": 280000},
        ],
    },
    "metadata": {
        "last_updated": None,
        "version": "1.0",
    },
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
                return copy.deepcopy(DEFAULT_CONFIG)
        else:
            return copy.deepcopy(DEFAULT_CONFIG)
    
    def _merge_with_defaults(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Merge loaded config with defaults to ensure all keys exist.
        
        Args:
            config: Loaded configuration
            
        Returns:
            Merged configuration
        """
        merged = copy.deepcopy(DEFAULT_CONFIG)
        for section, values in config.items():
            if section in merged and isinstance(values, dict):
                merged[section].update(values)
            else:
                merged[section] = values
        return merged
    
    def save_config(self) -> bool:
        """
        Save current configuration to file.

        Before overwriting, the existing file is copied to the ``.backups/``
        directory with a timestamp suffix so the previous state can always be
        recovered.  The backup is silently skipped if no current file exists
        (first-time save).

        Returns:
            True if successful, False otherwise
        """
        import shutil
        from pathlib import Path

        # --- Backup existing config before overwriting ---
        config_path = Path(self.config_file)
        if config_path.exists():
            try:
                backup_dir = Path(".backups")
                backup_dir.mkdir(exist_ok=True)
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                stem = config_path.stem   # "retirement_config"
                suffix = config_path.suffix  # ".json"
                backup_path = backup_dir / f"{stem}_{timestamp}{suffix}"
                shutil.copy2(config_path, backup_path)
            except Exception as backup_exc:
                # Backup failure is non-fatal — log it but continue with the save.
                print(f"Warning: could not back up {self.config_file}: {backup_exc}")

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
        """Reset configuration to default values.

        Backs up the current file to ``.backups/`` before resetting so the
        previous state can always be recovered.
        """
        import shutil
        from pathlib import Path

        config_path = Path(self.config_file)
        if config_path.exists():
            try:
                backup_dir = Path(".backups")
                backup_dir.mkdir(exist_ok=True)
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                stem = config_path.stem
                suffix = config_path.suffix
                backup_path = backup_dir / f"{stem}_{timestamp}{suffix}"
                shutil.copy2(config_path, backup_path)
            except Exception as backup_exc:
                print(f"Warning: could not back up {self.config_file} before reset: {backup_exc}")

        self.config = copy.deepcopy(DEFAULT_CONFIG)
    
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
    
    def get_retirement_fraction(self, person_num: int, year: int) -> float:
        """
        Return the fraction of *year* that person *person_num* is still employed.

        - If the person retires before the year starts  → 0.0
        - If the person retires after the year ends     → 1.0
        - If the person retires during *year*           → elapsed days / days-in-year
          (from Jan 1 up to, but not including, the retirement date)

        The retirement date is read from ``person{n}_retirement_date`` in
        personal_info.  If that key is absent the function falls back to the
        integer ``person{n}_retirement_year`` and returns 0.0 or 1.0 with no
        partial-year proration (preserving the old behaviour for configs that
        pre-date the retirement-date feature).

        Args:
            person_num: 1 or 2
            year:       Calendar year to evaluate

        Returns:
            float in [0.0, 1.0]
        """
        ret_date_str = self.get("personal_info", f"person{person_num}_retirement_date", None)

        if ret_date_str:
            try:
                ret_date = datetime.strptime(ret_date_str, "%Y-%m-%d").date()
            except ValueError:
                ret_date = None
        else:
            ret_date = None

        if ret_date is None:
            # Fall back to integer retirement year (no partial-year proration)
            ret_year = self.get("personal_info", f"person{person_num}_retirement_year",
                                datetime.now().year)
            return 0.0 if year >= ret_year else 1.0

        ret_year = ret_date.year

        if year < ret_year:
            return 1.0          # fully working
        if year > ret_year:
            return 0.0          # fully retired

        # Partial year: days worked = Jan 1 through the day before retirement_date
        year_start = date(year, 1, 1)
        days_in_year = 366 if (year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)) else 365
        days_worked = max(0, (ret_date - year_start).days)   # 0 if retired on Jan 1
        return days_worked / days_in_year

    def get_annual_wages(self, year: int) -> float:
        """
        Get total annual wages for both persons in a given year.

        Wages are only counted while the person is still employed.  In the
        retirement year the wages are prorated by the fraction of the year
        worked (derived from the configured retirement date).

        Args:
            year: Year to calculate wages for

        Returns:
            Total annual wages for both persons (prorated in retirement year)
        """
        current_year = datetime.now().year
        wage_inflation_rate = self.get("income", "wage_inflation_rate", 3.0) / 100.0

        total_wages = 0.0

        # Person 1
        fraction1 = self.get_retirement_fraction(1, year)
        if fraction1 > 0:
            person1_base_wages = self.get("income", "person1_annual_wages", 0)
            years_diff = year - current_year
            total_wages += person1_base_wages * ((1 + wage_inflation_rate) ** years_diff) * fraction1

        # Person 2
        fraction2 = self.get_retirement_fraction(2, year)
        if fraction2 > 0:
            person2_base_wages = self.get("income", "person2_annual_wages", 0)
            years_diff = year - current_year
            total_wages += person2_base_wages * ((1 + wage_inflation_rate) ** years_diff) * fraction2

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


def retirement_date_to_age_and_year(retirement_date_str: str, birth_date_str: str) -> tuple:
    """
    Derive retirement_age (int) and retirement_year (int) from a retirement date string
    and a birth date string, both in "YYYY-MM-DD" format.

    The retirement_age is the age the person turns in the retirement year (birth year
    subtracted from retirement year), which matches the convention used throughout the
    rest of the codebase.

    Returns:
        (retirement_age, retirement_year)
    """
    try:
        birth_year = int(birth_date_str.split("-")[0])
        ret_year   = int(retirement_date_str.split("-")[0])
        ret_age    = ret_year - birth_year
        return ret_age, ret_year
    except (AttributeError, ValueError, IndexError):
        return 62, datetime.now().year


def default_retirement_date(birth_date_str: str, default_age: int = 60) -> str:
    """
    Return the default planned retirement date as a "YYYY-MM-DD" string.

    Defaults to the person's birthday in the year they turn *default_age*.
    If birth_date_str is unparseable, returns the first day of (current year + default_age).

    Args:
        birth_date_str: Birth date in "YYYY-MM-DD" format.
        default_age:    Age to retire at for the default (default 60).

    Returns:
        "YYYY-MM-DD" string.
    """
    try:
        parts = birth_date_str.split("-")
        birth_year  = int(parts[0])
        birth_month = parts[1]
        birth_day   = parts[2]
        ret_year = birth_year + default_age
        return f"{ret_year}-{birth_month}-{birth_day}"
    except (AttributeError, ValueError, IndexError):
        return f"{datetime.now().year + default_age}-01-01"


# Module-level cache — valid within a single process/worker lifetime.
_config_manager = None

_SESSION_KEY = "_retirement_config_manager"


def get_config_manager() -> ConfigManager:
    """
    Get the configuration manager instance.

    The instance is stored in st.session_state so it survives Streamlit
    re-runs within the same browser session.  A module-level reference is
    kept as a fast fallback for code that calls this outside a Streamlit
    request context (e.g. unit tests or CLI scripts).

    Returns:
        ConfigManager instance
    """
    global _config_manager
    try:
        import streamlit as st
        if _SESSION_KEY not in st.session_state:
            # First access this session — load from file.
            st.session_state[_SESSION_KEY] = ConfigManager()
        _config_manager = st.session_state[_SESSION_KEY]
        return _config_manager
    except (ImportError, AttributeError):
        # Not running inside Streamlit — fall back to module-level global.
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
    """Reload configuration from file, replacing both the session and module cache."""
    global _config_manager
    fresh = ConfigManager()
    _config_manager = fresh
    try:
        import streamlit as st
        st.session_state[_SESSION_KEY] = fresh
    except (ImportError, AttributeError):
        pass

# Made with Bob
