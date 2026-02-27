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

import pandas as pd
from datetime import datetime
from typing import Dict, Tuple
import logging

logger = logging.getLogger(__name__)

# Constants based on Social Security Administration rules
FULL_RETIREMENT_AGE = 67
EARLY_CLAIMING_REDUCTION_RATE = 0.0667  # ~6.67% per year (5/9 of 1% per month for first 36 months, then 5/12 of 1% per month)
DELAYED_RETIREMENT_CREDIT_RATE = 0.08  # 8% per year (2/3 of 1% per month)
DEFAULT_COLA_RATE = 0.02  # 2% annual COLA (conservative estimate)


def calculate_benefit_at_claiming_age(fra_benefit: float, claiming_age: int, fra: int = FULL_RETIREMENT_AGE) -> float:
    """
    Calculate the monthly benefit amount at a specific claiming age.
    
    The calculation follows SSA rules:
    - Claiming before FRA: Reduced by ~6.67% per year
    - Claiming at FRA: Full benefit amount
    - Claiming after FRA: Increased by 8% per year (up to age 70)
    
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
    if claiming_age < 62:
        logger.warning(f"Claiming age {claiming_age} is below minimum age 62")
        return 0.0
    
    if claiming_age > 70:
        logger.warning(f"Claiming age {claiming_age} is above maximum benefit age 70, using 70")
        claiming_age = 70
    
    years_difference = claiming_age - fra
    
    if years_difference < 0:
        # Early claiming: reduce benefit
        # More precise calculation for early claiming
        months_early = abs(years_difference * 12)
        
        # First 36 months: 5/9 of 1% per month = 0.5556% per month
        # Beyond 36 months: 5/12 of 1% per month = 0.4167% per month
        if months_early <= 36:
            reduction_pct = months_early * (5/9) * 0.01
        else:
            reduction_pct = 36 * (5/9) * 0.01 + (months_early - 36) * (5/12) * 0.01
        
        benefit = fra_benefit * (1 - reduction_pct)
        
    elif years_difference > 0:
        # Delayed claiming: increase benefit by 8% per year
        increase_pct = years_difference * DELAYED_RETIREMENT_CREDIT_RATE
        benefit = fra_benefit * (1 + increase_pct)
        
    else:
        # Claiming at FRA
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
    
    Args:
        person_name: Name of the person
        birth_year: Year of birth
        claiming_age: Age when benefits will be claimed
        fra_benefit: Monthly benefit amount at Full Retirement Age (67)
        start_year: First year of the schedule
        end_year: Last year of the schedule
        cola_rate: Annual COLA rate (default: 2%)
        fra: Full Retirement Age (default: 67)
        
    Returns:
        DataFrame with columns: year, claiming_age, person, monthly_benefit
        
    Example:
        >>> df = generate_ssi_schedule("Tom", 1965, 70, 4223, 2026, 2040, 0.02)
        >>> df[df['year'] == 2036]  # Year Tom is 71 (1 year after claiming at 70)
           year  claiming_age person  monthly_benefit
           2036            71    Tom          5319.30
    """
    schedule_data = []
    claiming_year = birth_year + claiming_age
    
    # Calculate initial benefit at claiming age
    initial_benefit = calculate_benefit_at_claiming_age(fra_benefit, claiming_age, fra)
    
    for year in range(start_year, end_year + 1):
        current_age = year - birth_year
        
        # Only include years where person is at least 60 (for planning purposes)
        if current_age < 60:
            continue
        
        # Before claiming age: no benefits
        if current_age < claiming_age:
            monthly_benefit = 0.0
        else:
            # After claiming: apply COLA adjustments
            years_since_claiming = year - claiming_year
            monthly_benefit = calculate_benefit_with_cola(initial_benefit, years_since_claiming, cola_rate)
        
        schedule_data.append({
            'year': year,
            'claiming_age': current_age,
            'person': person_name,
            'monthly_benefit': monthly_benefit
        })
    
    return pd.DataFrame(schedule_data)


def generate_ssi_schedule_from_config(config_manager, start_year: int = None, end_year: int = None, cola_rate: float = DEFAULT_COLA_RATE) -> pd.DataFrame:
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
    
    schedules = []
    
    # Generate schedule for person 1
    person1_name = config_manager.get("personal_info", "person1_name", "Person1")
    person1_birth_date = config_manager.get("personal_info", "person1_birth_date", "1965-01-01")
    person1_birth_year = int(person1_birth_date.split('-')[0])
    person1_claiming_age = config_manager.get("social_security", "person1_ssi_age", 70)
    person1_fra_benefit = config_manager.get("social_security", "person1_ssi_amount", 0)
    
    if person1_fra_benefit > 0:
        person1_schedule = generate_ssi_schedule(
            person_name=person1_name,
            birth_year=person1_birth_year,
            claiming_age=person1_claiming_age,
            fra_benefit=person1_fra_benefit,
            start_year=start_year,
            end_year=end_year,
            cola_rate=cola_rate
        )
        schedules.append(person1_schedule)
    
    # Generate schedule for person 2
    person2_name = config_manager.get("personal_info", "person2_name", "Person2")
    person2_birth_date = config_manager.get("personal_info", "person2_birth_date", "1967-01-01")
    person2_birth_year = int(person2_birth_date.split('-')[0])
    person2_claiming_age = config_manager.get("social_security", "person2_ssi_age", 70)
    person2_fra_benefit = config_manager.get("social_security", "person2_ssi_amount", 0)
    
    if person2_fra_benefit > 0:
        person2_schedule = generate_ssi_schedule(
            person_name=person2_name,
            birth_year=person2_birth_year,
            claiming_age=person2_claiming_age,
            fra_benefit=person2_fra_benefit,
            start_year=start_year,
            end_year=end_year,
            cola_rate=cola_rate
        )
        schedules.append(person2_schedule)
    
    # Combine schedules
    if schedules:
        combined_df = pd.concat(schedules, ignore_index=True)
        return combined_df.sort_values(['year', 'person']).reset_index(drop=True)
    else:
        # Return empty DataFrame with correct structure
        return pd.DataFrame(columns=['year', 'claiming_age', 'person', 'monthly_benefit'])


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
