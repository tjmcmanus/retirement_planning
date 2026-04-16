# Scenario Planning API Documentation

## Overview

This document provides comprehensive API documentation for the Scenario Planning & What-If Analysis feature. It covers all modules, classes, functions, and their usage.

## Table of Contents

1. [Module Overview](#module-overview)
2. [scenario_manager.py](#scenario_managerpy)
3. [life_event_modeler.py](#life_event_modelerpy)
4. [scenario_integration.py](#scenario_integrationpy)
5. [Usage Examples](#usage-examples)
6. [Error Handling](#error-handling)

## Module Overview

The Scenario Planning feature consists of three main modules:

| Module | Purpose | Lines of Code |
|--------|---------|---------------|
| `scenario_manager.py` | Core data models and CRUD operations | 783 |
| `life_event_modeler.py` | Life event templates and utilities | 682 |
| `scenario_integration.py` | Integration with Monte Carlo, tax, and strategy modules | 520 |

## scenario_manager.py

### Data Models

#### LifeEventType (Enum)

Enumeration of pre-defined life event types.

```python
class LifeEventType(Enum):
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
```

#### LifeEvent

Represents a significant life event affecting retirement finances.

**Attributes:**

```python
@dataclass
class LifeEvent:
    id: str                          # Unique identifier
    event_type: LifeEventType        # Type of event
    name: str                        # Display name
    start_age: int                   # Starting age
    end_age: int | None = None       # Ending age (None for one-time)
    
    # Financial Impact (annual unless one-time)
    income_change: float = 0.0       # Annual income change
    expense_change: float = 0.0      # Annual expense change
    one_time_amount: float = 0.0     # One-time windfall/expense
    
    # Tax Impact
    taxable_income_change: float = 0.0
    
    # Portfolio Impact
    portfolio_withdrawal: float = 0.0
    portfolio_contribution: float = 0.0
    
    # Metadata
    notes: str = ""
    color: str = "#3B82F6"
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
```

**Methods:**

##### `is_active_at_age(age: int) -> bool`

Check if event is active at given age.

```python
event = LifeEvent(
    id="test",
    event_type=LifeEventType.PART_TIME_WORK,
    name="Part-Time",
    start_age=62,
    end_age=67
)

event.is_active_at_age(65)  # True
event.is_active_at_age(70)  # False
```

##### `get_annual_impact(age: int) -> dict[str, float]`

Get financial impact at specific age.

**Returns:**
```python
{
    "income": float,
    "expense": float,
    "taxable_income": float,
    "portfolio_change": float
}
```

**Example:**
```python
impact = event.get_annual_impact(65)
print(f"Income change: ${impact['income']:,.0f}")
```

##### `to_dict() -> dict[str, Any]`

Convert to dictionary for JSON serialization.

##### `from_dict(data: dict[str, Any]) -> LifeEvent`

Create LifeEvent from dictionary.

#### SocialSecurityConfig

Social Security configuration for a scenario.

```python
@dataclass
class SocialSecurityConfig:
    person1_amount: float = 0.0          # Annual amount
    person1_start_age: int = 70
    person2_amount: float = 0.0          # Annual amount
    person2_start_age: int | None = None
```

#### PensionConfig

Pension configuration for a scenario.

```python
@dataclass
class PensionConfig:
    annual_amount: float
    start_age: int
    cola_rate: float = 0.0               # Cost of living adjustment
    survivor_benefit_pct: float = 0.5    # Percentage for survivor
```

#### PartTimeIncomeConfig

Part-time income configuration.

```python
@dataclass
class PartTimeIncomeConfig:
    annual_amount: float
    start_age: int
    end_age: int
    growth_rate: float = 0.0             # Annual growth rate
```

#### TaxStrategyConfig

Tax strategy configuration.

```python
@dataclass
class TaxStrategyConfig:
    roth_conversion_strategy: Literal["none", "fill_bracket", "aggressive", "custom"] = "fill_bracket"
    tax_harvesting_enabled: bool = True
    target_tax_bracket: float = 0.24
```

#### ScenarioResults

Cached results from scenario analysis.

```python
@dataclass
class ScenarioResults:
    success_probability: float
    median_final_portfolio: float
    p10_final_portfolio: float
    p90_final_portfolio: float
    years_to_depletion_p10: int | None
    total_taxes_paid: float
    total_roth_conversions: float
    average_annual_withdrawal: float
    timestamp: str
```

#### Scenario

Complete retirement planning scenario.

**Attributes:**

```python
@dataclass
class Scenario:
    # Identification
    id: str
    name: str
    description: str
    created_at: str
    modified_at: str
    is_baseline: bool = False
    
    # Financial Parameters
    initial_portfolio: float = 1_500_000.0
    annual_expenses: float = 80_000.0
    inflation_rate: float = 0.029
    portfolio_allocation: dict[str, float]
    
    # Personal Parameters
    person1_age: int = 62
    person2_age: int | None = None
    retirement_age: int = 62
    plan_to_age: int = 95
    is_single: bool = False
    
    # Income Sources
    social_security: SocialSecurityConfig
    pension: PensionConfig | None = None
    part_time_income: PartTimeIncomeConfig | None = None
    
    # Life Events
    life_events: list[LifeEvent]
    
    # Tax Strategy
    tax_strategy: TaxStrategyConfig
    
    # Results (cached)
    last_run_results: ScenarioResults | None = None
```

**Methods:**

##### `update_modified_timestamp()`

Update the modified_at timestamp to current time.

##### `get_life_events_at_age(age: int) -> list[LifeEvent]`

Get all life events active at specific age.

```python
events = scenario.get_life_events_at_age(65)
for event in events:
    print(f"Active: {event.name}")
```

##### `get_total_impact_at_age(age: int) -> dict[str, float]`

Get total financial impact of all events at age.

```python
impact = scenario.get_total_impact_at_age(70)
print(f"Total income change: ${impact['income']:,.0f}")
print(f"Total expense change: ${impact['expense']:,.0f}")
```

##### `clone(new_name: str | None = None) -> Scenario`

Create a deep copy with new ID.

```python
cloned = scenario.clone("Modified Scenario")
cloned.retirement_age = 60
```

##### `to_dict() -> dict[str, Any]`

Convert to dictionary for JSON serialization.

##### `from_dict(data: dict[str, Any]) -> Scenario`

Create Scenario from dictionary.

### ScenarioManager

Manages scenarios with persistence and comparison.

**Constructor:**

```python
def __init__(self, storage_dir: str | Path = "data/scenarios"):
    """
    Initialize scenario manager.
    
    Args:
        storage_dir: Directory for storing scenario JSON files
    """
```

**Methods:**

##### `create_scenario(scenario: Scenario) -> Scenario`

Create and save a new scenario.

```python
manager = ScenarioManager()
scenario = Scenario(name="Test", initial_portfolio=1_000_000)
created = manager.create_scenario(scenario)
```

##### `update_scenario(scenario: Scenario) -> Scenario`

Update an existing scenario.

```python
scenario.annual_expenses = 90_000
updated = manager.update_scenario(scenario)
```

##### `delete_scenario(scenario_id: str) -> bool`

Delete a scenario by ID.

```python
success = manager.delete_scenario(scenario_id)
```

##### `get_scenario(scenario_id: str) -> Scenario | None`

Load a scenario by ID.

```python
scenario = manager.get_scenario(scenario_id)
if scenario:
    print(f"Loaded: {scenario.name}")
```

##### `list_scenarios() -> list[dict[str, Any]]`

List all scenarios with metadata.

```python
scenarios = manager.list_scenarios()
for s in scenarios:
    print(f"{s['name']}: {s['modified_at']}")
```

##### `get_baseline_scenario() -> Scenario | None`

Get the baseline scenario.

```python
baseline = manager.get_baseline_scenario()
```

##### `set_baseline(scenario_id: str) -> bool`

Set a scenario as baseline.

```python
manager.set_baseline(scenario_id)
```

##### `compare_scenarios(scenario_ids: list[str], metrics: list[str] | None = None) -> pd.DataFrame`

Compare multiple scenarios.

```python
comparison = manager.compare_scenarios([id1, id2, id3])
print(comparison)
```

##### `encode_scenario_url(scenario_ids: list[str]) -> str`

Encode scenario IDs for URL sharing.

```python
url_param = manager.encode_scenario_url([id1, id2])
share_url = f"?scenarios={url_param}"
```

##### `decode_scenario_url(encoded: str) -> list[str]`

Decode scenario IDs from URL parameter.

```python
scenario_ids = manager.decode_scenario_url(url_param)
```

### Utility Functions

##### `create_baseline_from_config(config_manager) -> Scenario`

Create baseline scenario from current configuration.

```python
from config import get_config_manager

config = get_config_manager()
baseline = create_baseline_from_config(config)
```

## life_event_modeler.py

### LifeEventTemplates

Pre-defined templates for common life events.

All template methods are static and return a configured `LifeEvent`.

##### `early_retirement(retirement_age: int, expense_reduction: float = 15_000, notes: str = "") -> LifeEvent`

```python
event = LifeEventTemplates.early_retirement(60, expense_reduction=15_000)
```

##### `part_time_work(start_age: int, end_age: int, annual_income: float = 30_000, notes: str = "") -> LifeEvent`

```python
event = LifeEventTemplates.part_time_work(62, 67, annual_income=30_000)
```

##### `inheritance(age: int, amount: float = 500_000, taxable_portion: float = 0.0, notes: str = "") -> LifeEvent`

```python
event = LifeEventTemplates.inheritance(70, amount=500_000)
```

##### `home_purchase(age: int, purchase_price: float = 500_000, down_payment_pct: float = 0.20, annual_costs: float = 15_000, notes: str = "") -> LifeEvent`

```python
event = LifeEventTemplates.home_purchase(
    65, 
    purchase_price=500_000,
    down_payment_pct=0.20
)
```

##### `college_funding(start_age: int, years: int = 4, annual_cost: float = 50_000, notes: str = "") -> LifeEvent`

```python
event = LifeEventTemplates.college_funding(65, years=4, annual_cost=50_000)
```

##### `divorce(age: int, asset_split_pct: float = 0.50, portfolio_value: float = 1_500_000, expense_change: float = -20_000, notes: str = "") -> LifeEvent`

```python
event = LifeEventTemplates.divorce(
    70,
    asset_split_pct=0.50,
    portfolio_value=1_500_000
)
```

##### `remarriage(age: int, combined_income_increase: float = 0, expense_increase: float = 20_000, notes: str = "") -> LifeEvent`

```python
event = LifeEventTemplates.remarriage(72, expense_increase=20_000)
```

##### `disability(age: int, disability_income: float = 40_000, medical_expenses: float = 15_000, duration_years: int | None = None, notes: str = "") -> LifeEvent`

```python
event = LifeEventTemplates.disability(
    65,
    disability_income=40_000,
    medical_expenses=15_000
)
```

##### `major_medical(age: int, one_time_cost: float = 100_000, ongoing_annual_cost: float = 10_000, duration_years: int = 5, notes: str = "") -> LifeEvent`

```python
event = LifeEventTemplates.major_medical(
    75,
    one_time_cost=100_000,
    ongoing_annual_cost=10_000
)
```

##### `business_sale(age: int, sale_proceeds: float = 2_000_000, capital_gains_pct: float = 0.80, notes: str = "") -> LifeEvent`

```python
event = LifeEventTemplates.business_sale(65, sale_proceeds=2_000_000)
```

##### `rental_income(start_age: int, end_age: int | None, annual_income: float = 24_000, annual_expenses: float = 8_000, notes: str = "") -> LifeEvent`

```python
event = LifeEventTemplates.rental_income(
    62,
    None,  # Ongoing
    annual_income=24_000
)
```

##### `downsizing(age: int, home_sale_proceeds: float = 400_000, new_home_cost: float = 250_000, expense_reduction: float = 10_000, notes: str = "") -> LifeEvent`

```python
event = LifeEventTemplates.downsizing(
    75,
    home_sale_proceeds=400_000,
    new_home_cost=250_000
)
```

##### `relocation(age: int, moving_cost: float = 20_000, expense_change: float = -15_000, notes: str = "") -> LifeEvent`

```python
event = LifeEventTemplates.relocation(70, expense_change=-15_000)
```

##### `custom(name: str, start_age: int, end_age: int | None = None, **kwargs: Any) -> LifeEvent`

```python
event = LifeEventTemplates.custom(
    "Custom Event",
    start_age=65,
    income_change=10_000,
    notes="Custom description"
)
```

### Event Utilities

##### `detect_event_conflicts(events: list[LifeEvent]) -> list[dict[str, Any]]`

Detect potential conflicts between events.

```python
conflicts = detect_event_conflicts(scenario.life_events)
for conflict in conflicts:
    print(f"{conflict['severity']}: {conflict['message']}")
```

**Returns:**
```python
[
    {
        "severity": "warning" | "info",
        "event1": str,  # Optional
        "event2": str,  # Optional
        "event": str,   # Optional
        "message": str
    }
]
```

##### `calculate_event_timeline(events: list[LifeEvent], start_age: int, end_age: int) -> dict[int, dict[str, float]]`

Calculate cumulative impact across timeline.

```python
timeline = calculate_event_timeline(events, 60, 95)
for age, impact in timeline.items():
    print(f"Age {age}: Income ${impact['income']:,.0f}")
```

**Returns:**
```python
{
    age: {
        "income": float,
        "expense": float,
        "taxable_income": float,
        "portfolio_change": float,
        "active_events": list[str]
    }
}
```

##### `get_template_list() -> list[dict[str, Any]]`

Get list of all available templates.

```python
templates = get_template_list()
for template in templates:
    print(f"{template['name']}: {template['description']}")
```

## scenario_integration.py

### Monte Carlo Integration

##### `scenario_to_monte_carlo_inputs(scenario: Scenario, n_simulations: int = 10_000, random_seed: int = 42) -> MonteCarloInputs`

Convert scenario to Monte Carlo inputs.

```python
from scenario_integration import scenario_to_monte_carlo_inputs

mc_inputs = scenario_to_monte_carlo_inputs(scenario, n_simulations=10_000)
```

##### `run_scenario_monte_carlo(scenario: Scenario, n_simulations: int = 10_000, include_life_events: bool = True) -> MonteCarloResult`

Run Monte Carlo simulation for scenario.

```python
from scenario_integration import run_scenario_monte_carlo

result = run_scenario_monte_carlo(scenario, n_simulations=10_000)
print(f"Success rate: {result.success_probability:.1%}")
```

##### `adjust_monte_carlo_for_life_events(mc_result: MonteCarloResult, scenario: Scenario) -> MonteCarloResult`

Adjust Monte Carlo results for life events.

```python
adjusted = adjust_monte_carlo_for_life_events(result, scenario)
```

### Tax Calculation Integration

##### `calculate_scenario_taxes(scenario: Scenario, year: int = 2026, filing_status: str = "married_filing_jointly") -> dict[str, Any]`

Calculate estimated taxes across retirement.

```python
from scenario_integration import calculate_scenario_taxes

tax_analysis = calculate_scenario_taxes(scenario, year=2026)
print(f"Total taxes: ${tax_analysis['total_taxes']:,.0f}")
print(f"Avg rate: {tax_analysis['average_effective_rate']:.1%}")
```

**Returns:**
```python
{
    "total_taxes": float,
    "total_income": float,
    "average_effective_rate": float,
    "annual_details": list[dict],
    "filing_status": str,
    "tax_year": int
}
```

##### `compare_scenario_taxes(scenarios: list[Scenario], year: int = 2026, filing_status: str = "married_filing_jointly") -> pd.DataFrame`

Compare tax implications across scenarios.

```python
from scenario_integration import compare_scenario_taxes

tax_comparison = compare_scenario_taxes([scenario1, scenario2])
print(tax_comparison)
```

### Comprehensive Reporting

##### `generate_scenario_report(scenario: Scenario, include_monte_carlo: bool = True, include_taxes: bool = True, n_simulations: int = 10_000) -> dict[str, Any]`

Generate comprehensive scenario report.

```python
from scenario_integration import generate_scenario_report

report = generate_scenario_report(scenario, n_simulations=10_000)
print(f"Success: {report['monte_carlo']['success_probability']:.1%}")
print(f"Taxes: ${report['taxes']['total_taxes']:,.0f}")
```

##### `compare_scenarios_comprehensive(scenarios: list[Scenario], n_simulations: int = 5_000) -> dict[str, Any]`

Generate comprehensive comparison.

```python
from scenario_integration import compare_scenarios_comprehensive

comparison = compare_scenarios_comprehensive([s1, s2, s3])
print(f"Best success rate: {comparison['summary']['best_success_rate']:.1%}")
```

## Usage Examples

### Example 1: Create and Analyze Scenario

```python
from scenario_manager import Scenario, ScenarioManager, SocialSecurityConfig
from life_event_modeler import LifeEventTemplates
from scenario_integration import run_scenario_monte_carlo

# Create scenario
scenario = Scenario(
    name="Early Retirement",
    description="Retire at 60 with part-time work",
    initial_portfolio=1_500_000,
    annual_expenses=70_000,
    retirement_age=60,
    plan_to_age=95,
    social_security=SocialSecurityConfig(
        person1_amount=36_000,
        person1_start_age=70
    )
)

# Add life events
scenario.life_events.append(
    LifeEventTemplates.early_retirement(60, expense_reduction=10_000)
)
scenario.life_events.append(
    LifeEventTemplates.part_time_work(60, 65, annual_income=30_000)
)

# Save scenario
manager = ScenarioManager()
manager.create_scenario(scenario)

# Run analysis
result = run_scenario_monte_carlo(scenario, n_simulations=10_000)
print(f"Success probability: {result.success_probability:.1%}")
print(f"Median final portfolio: ${result.median_final_portfolio:,.0f}")
```

### Example 2: Compare Multiple Scenarios

```python
from scenario_manager import ScenarioManager
from scenario_integration import compare_scenarios_comprehensive

# Load scenarios
manager = ScenarioManager()
baseline = manager.get_baseline_scenario()
early_retire = manager.get_scenario("early_retire_id")
late_retire = manager.get_scenario("late_retire_id")

# Compare
comparison = compare_scenarios_comprehensive(
    [baseline, early_retire, late_retire],
    n_simulations=5_000
)

# Print results
for scenario_report in comparison["scenarios"]:
    print(f"\n{scenario_report['scenario_name']}:")
    print(f"  Success: {scenario_report['monte_carlo']['success_probability']:.1%}")
    print(f"  Final: ${scenario_report['monte_carlo']['median_final_portfolio']:,.0f}")
```

### Example 3: Tax Analysis

```python
from scenario_integration import calculate_scenario_taxes, compare_scenario_taxes

# Analyze single scenario
tax_analysis = calculate_scenario_taxes(scenario, year=2026)
print(f"Total taxes: ${tax_analysis['total_taxes']:,.0f}")
print(f"Average rate: {tax_analysis['average_effective_rate']:.1%}")

# Compare multiple scenarios
tax_comparison = compare_scenario_taxes([scenario1, scenario2, scenario3])
print(tax_comparison)
```

### Example 4: Life Event Timeline

```python
from life_event_modeler import calculate_event_timeline

# Calculate timeline
timeline = calculate_event_timeline(
    scenario.life_events,
    start_age=60,
    end_age=95
)

# Print impacts by age
for age in range(60, 71):
    impact = timeline[age]
    print(f"Age {age}:")
    print(f"  Income: ${impact['income']:,.0f}")
    print(f"  Expenses: ${impact['expense']:,.0f}")
    print(f"  Active events: {', '.join(impact['active_events'])}")
```

## Error Handling

### Common Exceptions

#### ValueError

Raised for invalid parameter values:

```python
try:
    scenario = Scenario(retirement_age=30)  # Too young
except ValueError as e:
    print(f"Invalid parameter: {e}")
```

#### FileNotFoundError

Raised when scenario file not found:

```python
try:
    scenario = manager.get_scenario("invalid_id")
except FileNotFoundError:
    print("Scenario not found")
```

### Validation

All data models include validation in `__post_init__`:

- Scenario: retirement_age, plan_to_age, portfolio values
- LifeEvent: start_age, end_age consistency
- Portfolio allocation: must sum to ~1.0

### Logging

All modules use Python logging:

```python
import logging

# Enable debug logging
logging.basicConfig(level=logging.DEBUG)

# Or set via environment
import os
os.environ['LOG_LEVEL'] = 'DEBUG'
```

## Best Practices

1. **Always validate inputs** before creating scenarios
2. **Use templates** for common life events
3. **Clone scenarios** rather than modifying originals
4. **Cache results** to avoid re-running expensive analyses
5. **Handle exceptions** gracefully in production code
6. **Log important operations** for debugging
7. **Test with small n_simulations** during development

## Version History

- **1.0** (April 2026): Initial release
  - Core scenario management
  - 14 life event templates
  - Monte Carlo integration
  - Tax calculation integration

---

For user-facing documentation, see [User Guide](SCENARIO_PLANNING_USER_GUIDE.md).

For implementation details, see [Implementation Plan](SCENARIO_PLANNING_IMPLEMENTATION.md).