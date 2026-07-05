"""
scenario_manager.py
===================
Scenario Planning & What-If Analysis - Core Management Module

This module provides the core functionality for creating, managing, and comparing
retirement planning scenarios. It enables users to explore multiple "what-if"
scenarios side-by-side with different parameters and life events.

Key Features:
- Scenario CRUD operations
- JSON-based persistence
- Scenario comparison logic
- URL parameter encoding/decoding
- Data validation and integrity checks
"""

from __future__ import annotations

import base64
import binascii
import json
import logging
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Literal

import pandas as pd

# Configure logging
logger = logging.getLogger(__name__)


def _cfg_default(section: str, key: str, fallback: Any) -> Any:
    """Read a value from ConfigManager, falling back silently if unavailable."""
    try:
        from config import get_config_manager
        return get_config_manager().get(section, key, fallback)
    except (ImportError, AttributeError, KeyError):
        logger.debug(
            "Could not read %s/%s from ConfigManager, using fallback %r",
            section, key, fallback, exc_info=True,
        )
        return fallback


# ============================================================================
# Data Models
# ============================================================================

class LifeEventType(Enum):
    """Pre-defined life event types with standard impacts."""
    
    EARLY_RETIREMENT = "early_retirement"
    PART_TIME_WORK = "part_time_work"
    INHERITANCE = "inheritance"
    HOME_PURCHASE = "home_purchase"
    COLLEGE_FUNDING = "college_funding"
    DIVORCE = "divorce"
    REMARRIAGE = "remarriage"
    DISABILITY = "disability"
    MAJOR_MEDICAL = "major_medical"
    BUSINESS_SALE = "business_sale"
    RENTAL_INCOME = "rental_income"
    DOWNSIZING = "downsizing"
    RELOCATION = "relocation"
    CUSTOM = "custom"


@dataclass
class LifeEvent:
    """
    Represents a significant life event affecting retirement finances.
    
    Life events can have one-time or recurring impacts on income, expenses,
    and portfolio values. They are applied at specific ages and can span
    multiple years.
    """
    
    id: str
    event_type: LifeEventType
    name: str
    start_age: int
    end_age: int | None = None  # None for one-time events
    
    # Financial Impact (annual amounts unless one-time)
    income_change: float = 0.0  # Annual income change (can be negative)
    expense_change: float = 0.0  # Annual expense change (can be negative)
    one_time_amount: float = 0.0  # One-time windfall (positive) or expense (negative)
    
    # Tax Impact
    taxable_income_change: float = 0.0  # Change in taxable income
    
    # Portfolio Impact
    portfolio_withdrawal: float = 0.0  # One-time withdrawal from portfolio
    portfolio_contribution: float = 0.0  # One-time contribution to portfolio
    
    # Metadata
    notes: str = ""
    color: str = "#3B82F6"  # For visualization (default blue)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def __post_init__(self):
        """Validate life event data after initialization."""
        if self.start_age < 0 or self.start_age > 120:
            raise ValueError(f"Invalid start_age: {self.start_age}")
        
        if self.end_age is not None:
            if self.end_age < self.start_age:
                raise ValueError(f"end_age ({self.end_age}) must be >= start_age ({self.start_age})")
            if self.end_age > 120:
                raise ValueError(f"Invalid end_age: {self.end_age}")
    
    def is_active_at_age(self, age: int) -> bool:
        """Check if this event is active at the given age."""
        if age < self.start_age:
            return False
        if self.end_age is None:
            return age == self.start_age  # One-time event
        return age <= self.end_age
    
    def get_annual_impact(self, age: int) -> dict[str, float]:
        """
        Get the financial impact of this event at a specific age.
        
        Returns:
            Dictionary with keys: income, expense, taxable_income, portfolio_change
        """
        if not self.is_active_at_age(age):
            return {
                "income": 0.0,
                "expense": 0.0,
                "taxable_income": 0.0,
                "portfolio_change": 0.0,
            }
        
        # One-time impacts only apply at start_age
        is_start_year = (age == self.start_age)
        
        return {
            "income": self.income_change,
            "expense": self.expense_change,
            "taxable_income": self.taxable_income_change,
            "portfolio_change": (
                self.one_time_amount + self.portfolio_contribution - self.portfolio_withdrawal
                if is_start_year else 0.0
            ),
        }
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        data = asdict(self)
        data["event_type"] = self.event_type.value
        return data
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> LifeEvent:
        """Create LifeEvent from dictionary."""
        data = data.copy()
        data["event_type"] = LifeEventType(data["event_type"])
        return cls(**data)


@dataclass
class SocialSecurityConfig:
    """Social Security configuration for a scenario."""
    
    person1_amount: float = 0.0  # Annual amount
    person1_start_age: int = 70
    person2_amount: float = 0.0  # Annual amount
    person2_start_age: int | None = None
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SocialSecurityConfig:
        """Create from dictionary."""
        return cls(**data)


@dataclass
class PensionConfig:
    """Pension configuration for a scenario."""
    
    annual_amount: float
    start_age: int
    cola_rate: float = 0.0  # Cost of living adjustment rate
    survivor_benefit_pct: float = 0.5  # Percentage for surviving spouse
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PensionConfig:
        """Create from dictionary."""
        return cls(**data)


@dataclass
class PartTimeIncomeConfig:
    """Part-time income configuration for a scenario."""
    
    annual_amount: float
    start_age: int
    end_age: int
    growth_rate: float = 0.0  # Annual growth rate
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PartTimeIncomeConfig:
        """Create from dictionary."""
        return cls(**data)


@dataclass
class TaxStrategyConfig:
    """Tax strategy configuration for a scenario."""
    
    roth_conversion_strategy: Literal["none", "fill_bracket", "aggressive", "custom"] = "fill_bracket"
    tax_harvesting_enabled: bool = True
    target_tax_bracket: float = 0.24  # For custom strategy
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TaxStrategyConfig:
        """Create from dictionary."""
        return cls(**data)


@dataclass
class ScenarioResults:
    """Cached results from running a scenario analysis."""
    
    success_probability: float
    median_final_portfolio: float
    p10_final_portfolio: float
    p90_final_portfolio: float
    years_to_depletion_p10: int | None
    total_taxes_paid: float
    total_roth_conversions: float
    average_annual_withdrawal: float
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ScenarioResults:
        """Create from dictionary."""
        return cls(**data)


@dataclass
class Scenario:
    """
    Complete retirement planning scenario with all parameters and life events.
    
    A scenario represents a complete set of assumptions and parameters for
    retirement planning, including financial parameters, personal information,
    income sources, life events, and tax strategies.
    """
    
    # Identification
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = "Untitled Scenario"
    description: str = ""
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    modified_at: str = field(default_factory=lambda: datetime.now().isoformat())
    is_baseline: bool = False
    
    # Financial Parameters
    initial_portfolio: float = field(
        default_factory=lambda: _cfg_default(
            "financial_assumptions", "expected_total_portfolio", 1_500_000.0
        )
    )
    annual_expenses: float = field(
        default_factory=lambda: float(
            _cfg_default("financial_assumptions", "expected_annual_expenses", 80_000.0)
        )
    )
    inflation_rate: float = 0.029
    portfolio_allocation: dict[str, float] = field(default_factory=lambda: {
        "stocks": 0.70,
        "bonds": 0.25,
        "cash": 0.05,
    })
    
    # Personal Parameters
    person1_age: int = 62
    person2_age: int | None = None
    retirement_age: int = field(
        default_factory=lambda: int(
            _cfg_default("personal_info", "person1_retirement_age", 62)
        )
    )
    plan_to_age: int = 95
    is_single: bool = False
    
    # Income Sources
    social_security: SocialSecurityConfig = field(default_factory=SocialSecurityConfig)
    pension: PensionConfig | None = None
    part_time_income: PartTimeIncomeConfig | None = None
    
    # Life Events
    life_events: list[LifeEvent] = field(default_factory=list)
    
    # Tax Strategy
    tax_strategy: TaxStrategyConfig = field(default_factory=TaxStrategyConfig)
    
    # Results (cached)
    last_run_results: ScenarioResults | None = None
    
    def __post_init__(self):
        """Validate scenario data after initialization."""
        if self.initial_portfolio < 0:
            raise ValueError("initial_portfolio must be non-negative")
        if self.annual_expenses < 0:
            raise ValueError("annual_expenses must be non-negative")
        if not 0 <= self.inflation_rate <= 1:
            raise ValueError("inflation_rate must be between 0 and 1")
        if self.retirement_age < 40 or self.retirement_age > 80:
            raise ValueError("retirement_age must be between 40 and 80")
        if self.plan_to_age < self.retirement_age or self.plan_to_age > 120:
            raise ValueError("plan_to_age must be between retirement_age and 120")
        
        # Validate portfolio allocation sums to ~1.0
        total_allocation = sum(self.portfolio_allocation.values())
        if not (0.99 <= total_allocation <= 1.01):
            raise ValueError(f"Portfolio allocation must sum to 1.0, got {total_allocation}")
    
    def update_modified_timestamp(self):
        """Update the modified_at timestamp to current time."""
        self.modified_at = datetime.now().isoformat()
    
    def get_life_events_at_age(self, age: int) -> list[LifeEvent]:
        """Get all life events active at a specific age."""
        return [event for event in self.life_events if event.is_active_at_age(age)]
    
    def get_total_impact_at_age(self, age: int) -> dict[str, float]:
        """
        Get the total financial impact of all life events at a specific age.
        
        Returns:
            Dictionary with aggregated impacts: income, expense, taxable_income, portfolio_change
        """
        total_impact = {
            "income": 0.0,
            "expense": 0.0,
            "taxable_income": 0.0,
            "portfolio_change": 0.0,
        }
        
        for event in self.life_events:
            impact = event.get_annual_impact(age)
            for key in total_impact:
                total_impact[key] += impact[key]
        
        return total_impact
    
    def clone(self, new_name: str | None = None) -> Scenario:
        """
        Create a deep copy of this scenario with a new ID.
        
        Args:
            new_name: Optional new name for the cloned scenario
        
        Returns:
            New Scenario instance with copied data
        """
        data = self.to_dict()
        data["id"] = str(uuid.uuid4())
        data["name"] = new_name or f"{self.name} (Copy)"
        data["created_at"] = datetime.now().isoformat()
        data["modified_at"] = datetime.now().isoformat()
        data["is_baseline"] = False
        return Scenario.from_dict(data)
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "created_at": self.created_at,
            "modified_at": self.modified_at,
            "is_baseline": self.is_baseline,
            "financial": {
                "initial_portfolio": self.initial_portfolio,
                "annual_expenses": self.annual_expenses,
                "inflation_rate": self.inflation_rate,
                "portfolio_allocation": self.portfolio_allocation,
            },
            "personal": {
                "person1_age": self.person1_age,
                "person2_age": self.person2_age,
                "retirement_age": self.retirement_age,
                "plan_to_age": self.plan_to_age,
                "is_single": self.is_single,
            },
            "income_sources": {
                "social_security": self.social_security.to_dict(),
                "pension": self.pension.to_dict() if self.pension else None,
                "part_time_income": self.part_time_income.to_dict() if self.part_time_income else None,
            },
            "life_events": [event.to_dict() for event in self.life_events],
            "tax_strategy": self.tax_strategy.to_dict(),
            "last_run_results": self.last_run_results.to_dict() if self.last_run_results else None,
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Scenario:
        """Create Scenario from dictionary."""
        # Extract nested structures
        financial = data.get("financial", {})
        personal = data.get("personal", {})
        income_sources = data.get("income_sources", {})
        
        # Parse life events
        life_events = [
            LifeEvent.from_dict(event_data)
            for event_data in data.get("life_events", [])
        ]
        
        # Parse optional income sources
        pension = None
        if income_sources.get("pension"):
            pension = PensionConfig.from_dict(income_sources["pension"])
        
        part_time_income = None
        if income_sources.get("part_time_income"):
            part_time_income = PartTimeIncomeConfig.from_dict(income_sources["part_time_income"])
        
        # Parse results if present
        last_run_results = None
        if data.get("last_run_results"):
            last_run_results = ScenarioResults.from_dict(data["last_run_results"])
        
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            name=data.get("name", "Untitled Scenario"),
            description=data.get("description", ""),
            created_at=data.get("created_at", datetime.now().isoformat()),
            modified_at=data.get("modified_at", datetime.now().isoformat()),
            is_baseline=data.get("is_baseline", False),
            initial_portfolio=financial.get(
                "initial_portfolio",
                _cfg_default("financial_assumptions", "expected_total_portfolio", 1_500_000.0),
            ),
            annual_expenses=financial.get(
                "annual_expenses",
                float(_cfg_default("financial_assumptions", "expected_annual_expenses", 80_000.0)),
            ),
            inflation_rate=financial.get("inflation_rate", 0.029),
            portfolio_allocation=financial.get("portfolio_allocation", {
                "stocks": 0.70, "bonds": 0.25, "cash": 0.05
            }),
            person1_age=personal.get("person1_age", 62),
            person2_age=personal.get("person2_age"),
            retirement_age=personal.get(
                "retirement_age",
                int(_cfg_default("personal_info", "person1_retirement_age", 62)),
            ),
            plan_to_age=personal.get("plan_to_age", 95),
            is_single=personal.get("is_single", False),
            social_security=SocialSecurityConfig.from_dict(
                income_sources.get("social_security", {})
            ),
            pension=pension,
            part_time_income=part_time_income,
            life_events=life_events,
            tax_strategy=TaxStrategyConfig.from_dict(data.get("tax_strategy", {})),
            last_run_results=last_run_results,
        )


# ============================================================================
# Scenario Manager
# ============================================================================

class ScenarioManager:
    """
    Manages retirement planning scenarios with persistence and comparison.
    
    Provides CRUD operations for scenarios, JSON-based storage, and utilities
    for scenario comparison and analysis.
    """
    
    def __init__(self, storage_dir: str | Path = "data/scenarios"):
        """
        Initialize the scenario manager.
        
        Args:
            storage_dir: Directory for storing scenario JSON files
        """
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"ScenarioManager initialized with storage: {self.storage_dir}")
    
    def create_scenario(self, scenario: Scenario) -> Scenario:
        """
        Create a new scenario and save it to storage.
        
        Args:
            scenario: Scenario to create
        
        Returns:
            The created scenario
        """
        scenario.update_modified_timestamp()
        self._save_scenario(scenario)
        logger.info(f"Created scenario: {scenario.name} (ID: {scenario.id})")
        return scenario
    
    def update_scenario(self, scenario: Scenario) -> Scenario:
        """
        Update an existing scenario.
        
        Args:
            scenario: Scenario to update
        
        Returns:
            The updated scenario
        """
        scenario.update_modified_timestamp()
        self._save_scenario(scenario)
        logger.info(f"Updated scenario: {scenario.name} (ID: {scenario.id})")
        return scenario
    
    def delete_scenario(self, scenario_id: str) -> bool:
        """
        Delete a scenario by ID.
        
        Args:
            scenario_id: ID of scenario to delete
        
        Returns:
            True if deleted, False if not found
        """
        file_path = self._get_scenario_path(scenario_id)
        if file_path.exists():
            file_path.unlink()
            logger.info(f"Deleted scenario ID: {scenario_id}")
            return True
        logger.warning(f"Scenario not found for deletion: {scenario_id}")
        return False
    
    def get_scenario(self, scenario_id: str) -> Scenario | None:
        """
        Load a scenario by ID.
        
        Args:
            scenario_id: ID of scenario to load
        
        Returns:
            Scenario if found, None otherwise
        """
        file_path = self._get_scenario_path(scenario_id)
        if not file_path.exists():
            logger.warning(f"Scenario not found: {scenario_id}")
            return None
        
        try:
            with open(file_path, "r") as f:
                data = json.load(f)
            scenario = Scenario.from_dict(data)
            logger.debug(f"Loaded scenario: {scenario.name} (ID: {scenario_id})")
            return scenario
        except (OSError, json.JSONDecodeError, KeyError, ValueError) as e:
            logger.error(f"Error loading scenario {scenario_id}: {e}", exc_info=True)
            return None
    
    def list_scenarios(self) -> list[dict[str, Any]]:
        """
        List all scenarios with basic metadata.
        
        Returns:
            List of dictionaries with scenario metadata
        """
        scenarios = []
        for file_path in self.storage_dir.glob("*.json"):
            try:
                with open(file_path, "r") as f:
                    data = json.load(f)
                scenarios.append({
                    "id": data.get("id"),
                    "name": data.get("name"),
                    "description": data.get("description"),
                    "created_at": data.get("created_at"),
                    "modified_at": data.get("modified_at"),
                    "is_baseline": data.get("is_baseline", False),
                })
            except (OSError, json.JSONDecodeError) as e:
                logger.error(f"Error reading scenario file {file_path}: {e}", exc_info=True)
        
        # Sort by modified date (most recent first)
        scenarios.sort(key=lambda x: x.get("modified_at", ""), reverse=True)
        logger.debug(f"Listed {len(scenarios)} scenarios")
        return scenarios
    
    def get_baseline_scenario(self) -> Scenario | None:
        """
        Get the baseline scenario (if one exists).
        
        Returns:
            Baseline scenario or None
        """
        for scenario_meta in self.list_scenarios():
            if scenario_meta.get("is_baseline"):
                return self.get_scenario(scenario_meta["id"])
        return None
    
    def set_baseline(self, scenario_id: str) -> bool:
        """
        Set a scenario as the baseline (unsets any existing baseline).
        
        Args:
            scenario_id: ID of scenario to set as baseline
        
        Returns:
            True if successful, False otherwise
        """
        # Unset existing baseline
        for scenario_meta in self.list_scenarios():
            if scenario_meta.get("is_baseline"):
                scenario = self.get_scenario(scenario_meta["id"])
                if scenario:
                    scenario.is_baseline = False
                    self._save_scenario(scenario)
        
        # Set new baseline
        scenario = self.get_scenario(scenario_id)
        if scenario:
            scenario.is_baseline = True
            self._save_scenario(scenario)
            logger.info(f"Set baseline scenario: {scenario.name}")
            return True
        return False
    
    def compare_scenarios(
        self,
        scenario_ids: list[str],
        metrics: list[str] | None = None
    ) -> pd.DataFrame:
        """
        Compare multiple scenarios side-by-side.
        
        Args:
            scenario_ids: List of scenario IDs to compare (max 4)
            metrics: Optional list of specific metrics to compare
        
        Returns:
            DataFrame with comparison data
        """
        if len(scenario_ids) > 4:
            raise ValueError("Maximum 4 scenarios can be compared at once")
        
        scenarios = [self.get_scenario(sid) for sid in scenario_ids]
        scenarios = [s for s in scenarios if s is not None]
        
        if not scenarios:
            return pd.DataFrame()
        
        # Default metrics if not specified
        if metrics is None:
            metrics = [
                "name",
                "initial_portfolio",
                "annual_expenses",
                "retirement_age",
                "plan_to_age",
                "success_probability",
                "median_final_portfolio",
            ]
        
        comparison_data = []
        for scenario in scenarios:
            row = {"Scenario": scenario.name}
            
            for metric in metrics:
                if metric == "name":
                    continue
                elif metric == "success_probability" and scenario.last_run_results:
                    row["Success Rate"] = f"{scenario.last_run_results.success_probability:.1%}"
                elif metric == "median_final_portfolio" and scenario.last_run_results:
                    row["Final Portfolio"] = f"${scenario.last_run_results.median_final_portfolio:,.0f}"
                elif metric == "initial_portfolio":
                    row["Starting Portfolio"] = f"${scenario.initial_portfolio:,.0f}"
                elif metric == "annual_expenses":
                    row["Annual Expenses"] = f"${scenario.annual_expenses:,.0f}"
                elif metric == "retirement_age":
                    row["Retirement Age"] = str(scenario.retirement_age)
                elif metric == "plan_to_age":
                    row["Plan To Age"] = str(scenario.plan_to_age)
            
            comparison_data.append(row)
        
        return pd.DataFrame(comparison_data)
    
    def encode_scenario_url(self, scenario_ids: list[str]) -> str:
        """
        Encode scenario IDs into a URL parameter.
        
        Args:
            scenario_ids: List of scenario IDs to encode
        
        Returns:
            Base64-encoded URL parameter string
        """
        data = {"scenario_ids": scenario_ids}
        json_str = json.dumps(data)
        encoded = base64.urlsafe_b64encode(json_str.encode()).decode()
        logger.debug(f"Encoded {len(scenario_ids)} scenarios to URL parameter")
        return encoded
    
    def decode_scenario_url(self, encoded: str) -> list[str]:
        """
        Decode scenario IDs from a URL parameter.
        
        Args:
            encoded: Base64-encoded URL parameter
        
        Returns:
            List of scenario IDs
        """
        try:
            json_str = base64.urlsafe_b64decode(encoded.encode()).decode()
            data = json.loads(json_str)
            scenario_ids = data.get("scenario_ids", [])
            logger.debug(f"Decoded {len(scenario_ids)} scenarios from URL parameter")
            return scenario_ids
        except (binascii.Error, json.JSONDecodeError, KeyError, UnicodeDecodeError) as e:
            logger.error(f"Error decoding URL parameter: {e}", exc_info=True)
            return []
    
    def _save_scenario(self, scenario: Scenario):
        """Save scenario to JSON file atomically (write-then-replace)."""
        file_path = self._get_scenario_path(scenario.id)
        tmp_path = file_path.with_suffix(".tmp")
        try:
            with open(tmp_path, "w") as f:
                json.dump(scenario.to_dict(), f, indent=2)
            tmp_path.replace(file_path)
        except (OSError, IOError):
            tmp_path.unlink(missing_ok=True)
            raise
    
    def _get_scenario_path(self, scenario_id: str) -> Path:
        """Get file path for a scenario ID.

        Raises ValueError if the resolved path escapes the storage directory,
        defending against path-traversal attacks via crafted scenario IDs.
        """
        candidate = (self.storage_dir / f"{scenario_id}.json").resolve()
        if not str(candidate).startswith(str(self.storage_dir.resolve())):
            raise ValueError(
                f"Invalid scenario_id {scenario_id!r}: resolves outside storage directory"
            )
        return candidate


# ============================================================================
# Utility Functions
# ============================================================================

def create_baseline_from_config(config_manager) -> Scenario:
    """
    Create a baseline scenario from the current configuration.
    
    Args:
        config_manager: ConfigManager instance
    
    Returns:
        Baseline Scenario
    """
    from load_data import get_net_worth
    from datetime import datetime
    
    # Get portfolio value - get_net_worth returns a tuple: (cash, taxable, tax_deferred, tax_free, total, expenses, daf)
    today_str = datetime.now().strftime('%m/%d/%Y')
    try:
        cash, taxable, tax_deferred, tax_free, total, _, _ = get_net_worth(today_str)
        initial_portfolio = float(cash + taxable + tax_deferred + tax_free)
        if initial_portfolio < 10_000:
            initial_portfolio = 1_500_000.0  # Default if no data
    except (RuntimeError, ValueError, KeyError) as e:
        logger.warning(f"Could not load portfolio data: {e}", exc_info=True)
        initial_portfolio = 1_500_000.0  # Default
    
    # Get configuration values
    person1_age = config_manager.calculate_age(
        config_manager.get("personal_info", "person1_birth_date", "1965-01-01")
    )
    person2_birth = config_manager.get("personal_info", "person2_birth_date")
    person2_age = config_manager.calculate_age(person2_birth) if person2_birth else None
    
    is_single = config_manager.get("personal_info", "is_single_person", False)
    
    scenario = Scenario(
        name="Baseline (Current Plan)",
        description="Current retirement plan based on configuration",
        is_baseline=True,
        initial_portfolio=initial_portfolio,
        annual_expenses=config_manager.get("financial_assumptions", "expected_annual_expenses", 80_000),
        inflation_rate=config_manager.get("financial_assumptions", "expense_inflation_rate", 3.0) / 100,
        person1_age=person1_age,
        person2_age=person2_age,
        retirement_age=config_manager.get("personal_info", "person1_retirement_age", 62),
        plan_to_age=95,
        is_single=is_single,
        social_security=SocialSecurityConfig(
            person1_amount=config_manager.get("social_security", "person1_ssi_amount", 0) * 12,
            person1_start_age=config_manager.get("social_security", "person1_ssi_age", 70),
            person2_amount=config_manager.get("social_security", "person2_ssi_amount", 0) * 12 if not is_single else 0,
            person2_start_age=config_manager.get("social_security", "person2_ssi_age", 67) if not is_single else None,
        ),
    )
    
    logger.info("Created baseline scenario from configuration")
    return scenario


# Made with Bob