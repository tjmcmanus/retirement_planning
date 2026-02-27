"""
Social Security Income (SSI) Calculator Module

This module provides functions to dynamically calculate Social Security benefits
based on claiming age and Full Retirement Age (FRA) benefit amount.

Key Concepts:
- Full Retirement Age (FRA): Age 67 for most current retirees
- Early claiming reduction: ~6.67% per year before FRA (ages 62-67)
- Delayed retirement credits: 8% per year after FRA (ages 67-70)
- COLA adjustments: Annual cost-of-living adjustments after claiming
"""

import numpy as np
import pandas as pd
from datetime import datetime
from typing import Tuple
import logging

logger = logging.getLogger(__name__)

# Constants based on Social Security Administration rules
FULL_RETIREMENT_AGE = 67
MIN_CLAIMING_AGE = 62                          # Earliest age to claim SSA benefits
MAX_BENEFIT_AGE = 70                           # Age beyond which no additional delayed credits accrue
EARLY_MONTHS_THRESHOLD = 36                    # First 36 months use a higher per-month reduction rate
EARLY_REDUCTION_RATE_FIRST_36 = (5 / 9) * 0.01   # 5/9 of 1% per month (~0.5556%) for first 36 months early
EARLY_REDUCTION_RATE_BEYOND_36 = (5 / 12) * 0.01  # 5/12 of 1% per month (~0.4167%) beyond 36 months early
EARLY_CLAIMING_REDUCTION_RATE = 0.0667  # ~6.67% per year (approximate; precise calc uses monthly rates above)
DELAYED_RETIREMENT_CREDIT_RATE = 0.08  # 8% per year (2/3 of 1% per month)
DEFAULT_COLA_RATE = 0.02  # 2% annual COLA (conservative estimate)
# Note: 'age' stores the person's current age each year, not their benefit-claiming age
SSI_SCHEDULE_COLUMNS: list = ['year', 'age', 'person', 'monthly_benefit']
MIN_SCHEDULE_AGE = 60  # Earliest age included in a generated schedule (no planning relevance before this)


def _clamp_claiming_age(claiming_age: int) -> int:
    """
    Clamp claiming age to the valid SSA benefit range [MIN_CLAIMING_AGE, MAX_BENEFIT_AGE].

    Logs a warning whenever the input is outside the valid range so callers are
    informed of the adjustment without duplicating that logic in every consumer.

    Args:
        claiming_age: Requested claiming age

    Returns:
        Age clamped to [MIN_CLAIMING_AGE, MAX_BENEFIT_AGE]
    """
    if claiming_age < MIN_CLAIMING_AGE:
        logger.warning(
            f"Claiming age {claiming_age} is below minimum age {MIN_CLAIMING_AGE}, "
            f"using {MIN_CLAIMING_AGE}"
        )
        return MIN_CLAIMING_AGE
    if claiming_age > MAX_BENEFIT_AGE:
        logger.warning(
            f"Claiming age {claiming_age} is above maximum benefit age {MAX_BENEFIT_AGE}, "
            f"using {MAX_BENEFIT_AGE}"
        )
        return MAX_BENEFIT_AGE
    return claiming_age


def _calculate_early_claiming_reduction(months_early: int) -> float:
    """
    Calculate the benefit reduction percentage for early claiming.

    SSA applies two distinct per-month rates:
    - First EARLY_MONTHS_THRESHOLD months: EARLY_REDUCTION_RATE_FIRST_36 per month
    - Each additional month beyond that: EARLY_REDUCTION_RATE_BEYOND_36 per month

    Args:
        months_early: Number of months before FRA the benefit is claimed (must be >= 0)

    Returns:
        Reduction as a decimal fraction (e.g. 0.20 represents a 20% reduction)
    """
    if months_early <= EARLY_MONTHS_THRESHOLD:
        return months_early * EARLY_REDUCTION_RATE_FIRST_36
    return (
        EARLY_MONTHS_THRESHOLD * EARLY_REDUCTION_RATE_FIRST_36
        + (months_early - EARLY_MONTHS_THRESHOLD) * EARLY_REDUCTION_RATE_BEYOND_36
    )


def calculate_benefit_at_claiming_age(fra_benefit: float, claiming_age: int, fra: int = FULL_RETIREMENT_AGE) -> float:
    """
    Calculate the monthly benefit amount at a specific claiming age.

    The calculation follows SSA rules:
    - Claiming before FRA: Reduced using the two-tier monthly reduction schedule
    - Claiming at FRA: Full benefit amount
    - Claiming after FRA: Increased by 8% per year (up to age MAX_BENEFIT_AGE)

    Claiming ages outside [MIN_CLAIMING_AGE, MAX_BENEFIT_AGE] are clamped to the
    nearest valid bound and a warning is logged.

    Args:
        fra_benefit: Monthly benefit amount at Full Retirement Age (age 67)
        claiming_age: Age when benefits are claimed (typically 62-70)
        fra: Full Retirement Age (default: 67)

    Returns:
        Monthly benefit amount at claiming age

    Example:
        >>> calculate_benefit_at_claiming_age(4223, 70)
        5215.0  # Approximately 23.5% increase for 3 years of delay
        >>> calculate_benefit_at_claiming_age(4223, 62)
        2829.0  # Approximately 33% reduction for 5 years early
    """
    clamped_age = _clamp_claiming_age(claiming_age)
    years_difference = clamped_age - fra

    if years_difference < 0:
        # Early claiming: reduce benefit using the precise two-tier monthly schedule
        months_early = abs(years_difference * 12)
        reduction_pct = _calculate_early_claiming_reduction(months_early)
        benefit = fra_benefit * (1 - reduction_pct)
    elif years_difference > 0:
        # Delayed claiming: increase benefit by DELAYED_RETIREMENT_CREDIT_RATE per year
        increase_pct = years_difference * DELAYED_RETIREMENT_CREDIT_RATE
        benefit = fra_benefit * (1 + increase_pct)
    else:
        # Claiming exactly at FRA
        benefit = fra_benefit

    return round(benefit, 2)


def calculate_benefit_with_cola(initial_benefit: float, years_since_claiming: int, cola_rate: float = DEFAULT_COLA_RATE) -> float:
    """
    Calculate benefit amount after applying COLA adjustments.
    
    Args:
        initial_benefit: Monthly benefit at claiming age
        years_since_claiming: Number of years since benefits were claimed
        cola_rate: Annual COLA rate (default: 2%)
        
    Returns:
        Monthly benefit amount after COLA adjustments
        
    Example:
        >>> calculate_benefit_with_cola(5215, 1, 0.02)
        5319.3  # After 1 year of 2% COLA
    """
    if years_since_claiming < 0:
        return 0.0
    
    benefit_with_cola = initial_benefit * ((1 + cola_rate) ** years_since_claiming)
    return round(benefit_with_cola, 2)


def generate_ssi_schedule(
    person_name: str,
    birth_year: int,
    claiming_age: int,
    fra_benefit: float,
    start_year: int,
    end_year: int,
    cola_rate: float = DEFAULT_COLA_RATE,
    fra: int = FULL_RETIREMENT_AGE
) -> pd.DataFrame:
    """
    Generate a complete SSI schedule for a person from start_year to end_year.

    The output always contains exactly one row per year in [start_year, end_year].
    Years before the person reaches MIN_SCHEDULE_AGE (age 60) are included with
    ``monthly_benefit = 0.0``, as are years before the claiming year.

    Args:
        person_name: Name of the person
        birth_year: Year of birth
        claiming_age: Age when benefits will be claimed
        fra_benefit: Monthly benefit amount at Full Retirement Age (67)
        start_year: First year of the schedule (inclusive)
        end_year: Last year of the schedule (inclusive)
        cola_rate: Annual COLA rate (default: 2%)
        fra: Full Retirement Age (default: 67)

    Returns:
        DataFrame with columns: year, age, person, monthly_benefit.
        Rows before the claiming year have ``monthly_benefit = 0.0``.
        The DataFrame always spans [start_year, end_year] with no gaps.

    Example:
        >>> df = generate_ssi_schedule("Tom", 1965, 70, 4223, 2026, 2040, 0.02)
        >>> df[df['year'] == 2035].iloc[0]['monthly_benefit']  # Claiming year (age 70)
        5236.52
        >>> df[df['year'] == 2036].iloc[0]['monthly_benefit']  # 1 year after claiming
        5319.30
        >>> df[df['year'] == 2034].iloc[0]['monthly_benefit']  # Before claiming (age 69)
        0.0
    """
    if start_year > end_year:
        return pd.DataFrame(columns=SSI_SCHEDULE_COLUMNS)

    # Pre-compute benefit at claiming age once
    claiming_year = birth_year + claiming_age
    initial_benefit = calculate_benefit_at_claiming_age(fra_benefit, claiming_age, fra)

    # Build the full year range — output always spans [start_year, end_year]
    years = np.arange(start_year, end_year + 1)
    years_since_claiming = years - claiming_year

    # Compute COLA-adjusted benefits for all years, then zero out pre-claiming years.
    # Using a mask assignment avoids np.where's eager evaluation of both branches.
    monthly_benefits = np.round(initial_benefit * ((1 + cola_rate) ** years_since_claiming), 2)
    monthly_benefits[years_since_claiming < 0] = 0.0

    return pd.DataFrame({
        'year': years,
        'age': years - birth_year,
        'person': person_name,
        'monthly_benefit': monthly_benefits,
    })


def _get_person_schedule(
    config_manager,
    person_key: str,
    start_year: int,
    end_year: int,
    cola_rate: float,
) -> "pd.DataFrame | None":
    """
    Retrieve config values for one person and return their SSI schedule DataFrame.

    Args:
        config_manager: ConfigManager instance from config.py
        person_key: Config key prefix for the person (e.g. ``"person1"``, ``"person2"``)
        start_year: First year of the schedule
        end_year: Last year of the schedule
        cola_rate: Annual COLA rate

    Returns:
        DataFrame with SSI schedule, or ``None`` if no FRA benefit is configured
    """
    name = config_manager.get("personal_info", f"{person_key}_name", person_key.capitalize())
    birth_date = config_manager.get("personal_info", f"{person_key}_birth_date", "1965-01-01")
    birth_year = datetime.strptime(birth_date, "%Y-%m-%d").year
    claiming_age = config_manager.get("social_security", f"{person_key}_ssi_age", 70)
    fra_benefit = config_manager.get("social_security", f"{person_key}_ssi_amount", 0)

    if fra_benefit <= 0:
        return None

    return generate_ssi_schedule(
        person_name=name,
        birth_year=birth_year,
        claiming_age=claiming_age,
        fra_benefit=fra_benefit,
        start_year=start_year,
        end_year=end_year,
        cola_rate=cola_rate,
    )


def generate_ssi_schedule_from_config(config_manager, start_year: "int | None" = None, end_year: "int | None" = None, cola_rate: float = DEFAULT_COLA_RATE) -> pd.DataFrame:
    """
    Generate SSI schedules for both persons based on config.py settings.
    
    Args:
        config_manager: ConfigManager instance from config.py
        start_year: First year of schedule (default: current year)
        end_year: Last year of schedule (default: start_year + 30)
        cola_rate: Annual COLA rate (default: 2%)
        
    Returns:
        Combined DataFrame with SSI schedules for both persons
        
    Example:
        >>> from config import get_config_manager
        >>> config = get_config_manager()
        >>> df = generate_ssi_schedule_from_config(config)
    """
    if start_year is None:
        start_year = datetime.now().year

    if end_year is None:
        end_year = start_year + 30

    schedules = [
        schedule
        for key in ("person1", "person2")
        if (schedule := _get_person_schedule(config_manager, key, start_year, end_year, cola_rate)) is not None
    ]

    if schedules:
        return pd.concat(schedules, ignore_index=True).sort_values(['year', 'person']).reset_index(drop=True)

    return pd.DataFrame(columns=SSI_SCHEDULE_COLUMNS)


def export_ssi_schedule_to_csv(schedule_df: pd.DataFrame, filename: str = "ssincome.csv") -> None:
    """
    Export SSI schedule to CSV file.
    
    Args:
        schedule_df: DataFrame with SSI schedule
        filename: Output CSV filename
    """
    schedule_df.to_csv(filename, index=False)
    logger.info(f"SSI schedule exported to {filename}")


def validate_config_ssi_settings(config_manager) -> Tuple[bool, list]:
    """
    Validate SSI settings in config.
    
    Args:
        config_manager: ConfigManager instance
        
    Returns:
        Tuple of (is_valid, list_of_errors)
    """
    errors = []
    
    # Check person 1
    person1_age = config_manager.get("social_security", "person1_ssi_age", 0)
    person1_amount = config_manager.get("social_security", "person1_ssi_amount", 0)
    
    if person1_amount > 0:
        if person1_age < 62 or person1_age > 70:
            errors.append(f"Person 1 SSI claiming age {person1_age} must be between 62 and 70")
    
    # Check person 2
    person2_age = config_manager.get("social_security", "person2_ssi_age", 0)
    person2_amount = config_manager.get("social_security", "person2_ssi_amount", 0)
    
    if person2_amount > 0:
        if person2_age < 62 or person2_age > 70:
            errors.append(f"Person 2 SSI claiming age {person2_age} must be between 62 and 70")
    
    return len(errors) == 0, errors


# Example usage and testing
if __name__ == "__main__":
    # Example: Calculate benefits at different claiming ages for someone with $4,223 FRA benefit
    fra_benefit = 4223
    
    print("Social Security Benefit Calculator")
    print("=" * 50)
    print(f"Full Retirement Age (67) Benefit: ${fra_benefit:,.2f}/month\n")
    
    print("Benefits at Different Claiming Ages:")
    print("-" * 50)
    for age in range(62, 71):
        benefit = calculate_benefit_at_claiming_age(fra_benefit, age)
        pct_change = ((benefit / fra_benefit) - 1) * 100
        print(f"Age {age}: ${benefit:,.2f}/month ({pct_change:+.1f}%)")
    
    print("\n" + "=" * 50)
    print("\nExample: Tom's Schedule (Born 1965, Claims at 70, FRA Benefit $4,223)")
    print("-" * 50)
    
    tom_schedule = generate_ssi_schedule(
        person_name="Tom",
        birth_year=1965,
        claiming_age=70,
        fra_benefit=4223,
        start_year=2026,
        end_year=2040,
        cola_rate=0.02
    )
    
    # Show key years
    key_years = [2026, 2033, 2036, 2040]
    for year in key_years:
        row = tom_schedule[tom_schedule['year'] == year]
        if not row.empty:
            age = row['claiming_age'].iloc[0]
            benefit = row['monthly_benefit'].iloc[0]
            print(f"Year {year} (Age {age}): ${benefit:,.2f}/month")

# Made with Bob
