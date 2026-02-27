#!/usr/bin/env python3
"""
Generate SSI Schedule from Config

This script generates a Social Security Income schedule based on the
settings in config.py and exports it to a CSV file.

Usage:
    python generate_ssi_schedule.py
    python generate_ssi_schedule.py --start-year 2026 --end-year 2050
    python generate_ssi_schedule.py --cola 0.025 --output my_schedule.csv
"""

import argparse
from datetime import datetime
from ssi_calculator import generate_ssi_schedule_from_config, validate_config_ssi_settings
from config import get_config_manager


def main():
    parser = argparse.ArgumentParser(
        description='Generate SSI schedule from config.py settings'
    )
    parser.add_argument(
        '--start-year',
        type=int,
        default=datetime.now().year,
        help='First year of schedule (default: current year)'
    )
    parser.add_argument(
        '--end-year',
        type=int,
        default=None,
        help='Last year of schedule (default: start_year + 30)'
    )
    parser.add_argument(
        '--cola',
        type=float,
        default=0.02,
        help='Annual COLA rate as decimal (default: 0.02 for 2%%)'
    )
    parser.add_argument(
        '--output',
        type=str,
        default='ssincome_generated.csv',
        help='Output CSV filename (default: ssincome_generated.csv)'
    )
    parser.add_argument(
        '--validate-only',
        action='store_true',
        help='Only validate config without generating schedule'
    )
    
    args = parser.parse_args()
    
    # Load configuration
    print("Loading configuration from config.py...")
    config = get_config_manager()
    
    # Validate configuration
    print("\nValidating SSI settings...")
    is_valid, errors = validate_config_ssi_settings(config)
    
    if not is_valid:
        print("❌ Configuration validation failed:")
        for error in errors:
            print(f"   - {error}")
        return 1
    
    print("✓ Configuration is valid")
    
    # Display current settings
    print("\nCurrent SSI Configuration:")
    print("-" * 60)
    person1_name = config.get("personal_info", "person1_name", "Person1")
    person1_age = config.get("social_security", "person1_ssi_age", 0)
    person1_amount = config.get("social_security", "person1_ssi_amount", 0)
    
    person2_name = config.get("personal_info", "person2_name", "Person2")
    person2_age = config.get("social_security", "person2_ssi_age", 0)
    person2_amount = config.get("social_security", "person2_ssi_amount", 0)
    
    print(f"{person1_name}:")
    print(f"  - Claiming Age: {person1_age}")
    print(f"  - FRA Benefit (age 67): ${person1_amount:,.2f}/month")
    
    print(f"\n{person2_name}:")
    print(f"  - Claiming Age: {person2_age}")
    print(f"  - FRA Benefit (age 67): ${person2_amount:,.2f}/month")
    
    print(f"\nCOLA Rate: {args.cola * 100:.1f}%")
    
    if args.validate_only:
        print("\n✓ Validation complete (--validate-only flag set)")
        return 0
    
    # Set end year if not provided
    end_year = args.end_year if args.end_year else args.start_year + 30
    
    print(f"\nGenerating schedule from {args.start_year} to {end_year}...")
    
    # Generate schedule
    schedule = generate_ssi_schedule_from_config(
        config_manager=config,
        start_year=args.start_year,
        end_year=end_year,
        cola_rate=args.cola
    )
    
    if schedule.empty:
        print("⚠️  No schedule generated. Check that SSI amounts are set in config.py")
        return 1
    
    # Export to CSV
    schedule.to_csv(args.output, index=False)
    print(f"✓ Schedule exported to: {args.output}")
    
    # Display summary statistics
    print("\nSchedule Summary:")
    print("-" * 60)
    print(f"Total rows: {len(schedule)}")
    print(f"Years covered: {args.start_year} - {end_year}")
    print(f"Persons: {', '.join(schedule['person'].unique())}")
    
    # Show sample data
    print("\nSample Data (first 10 rows):")
    print(schedule.head(10).to_string(index=False))
    
    # Show key milestone years
    print("\nKey Milestone Years:")
    print("-" * 60)
    
    for person in schedule['person'].unique():
        person_data = schedule[schedule['person'] == person]
        
        # Find first year with benefits
        first_benefit = person_data[person_data['monthly_benefit'] > 0]
        if not first_benefit.empty:
            first_row = first_benefit.iloc[0]
            print(f"\n{person} starts receiving benefits:")
            print(f"  Year {first_row['year']} (Age {first_row['claiming_age']}): "
                  f"${first_row['monthly_benefit']:,.2f}/month")
            
            # Show 5 years later
            five_years_later = person_data[
                person_data['year'] == first_row['year'] + 5
            ]
            if not five_years_later.empty:
                later_row = five_years_later.iloc[0]
                print(f"  Year {later_row['year']} (Age {later_row['claiming_age']}): "
                      f"${later_row['monthly_benefit']:,.2f}/month")
    
    print("\n" + "=" * 60)
    print("✓ Schedule generation complete!")
    print("=" * 60)
    
    return 0


if __name__ == "__main__":
    exit(main())

# Made with Bob
