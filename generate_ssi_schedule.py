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
import logging
import os
from datetime import datetime
from ssi_calculator import generate_ssi_schedule_from_config, validate_config_ssi_settings
from config import get_config_manager

# Configure logging — matches project-wide convention from calculations.py.
# Default level is WARNING; set LOG_LEVEL=INFO (or DEBUG) to see progress output.
log_level = logging.getLevelName(os.getenv('LOG_LEVEL', 'WARNING'))
logging.basicConfig(
    level=log_level,
    format='%(asctime)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    """Parse and return command-line arguments."""
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
    return parser.parse_args()


def _get_persons_config(config) -> list:
    """Return a list of dicts with each person's SSI configuration values."""
    return [
        {
            "name":   config.get("personal_info",   "person1_name",       "Person1"),
            "age":    config.get("social_security",  "person1_ssi_age",    0),
            "amount": config.get("social_security",  "person1_ssi_amount", 0),
        },
        {
            "name":   config.get("personal_info",   "person2_name",       "Person2"),
            "age":    config.get("social_security",  "person2_ssi_age",    0),
            "amount": config.get("social_security",  "person2_ssi_amount", 0),
        },
    ]


def _log_config_settings(config, cola_rate: float) -> None:
    """Log the current SSI configuration for each person and the COLA rate."""
    logger.info("Current SSI Configuration:")
    logger.info("-" * 60)
    for person in _get_persons_config(config):
        logger.info("%s:", person['name'])
        logger.info("  - Claiming Age: %s", person['age'])
        logger.info("  - FRA Benefit (age 67): $%,.2f/month", person['amount'])
    logger.info("COLA Rate: %.1f%%", cola_rate * 100)


def _log_schedule_summary(schedule, start_year: int, end_year: int) -> None:
    """Log summary statistics and key milestone years for the generated schedule."""
    logger.info("Schedule Summary:")
    logger.info("-" * 60)
    logger.info("Total rows: %d", len(schedule))
    logger.info("Years covered: %d - %d", start_year, end_year)
    logger.info("Persons: %s", ', '.join(schedule['person'].unique()))

    logger.info("Sample Data (first 10 rows):\n%s", schedule.head(10).to_string(index=False))

    logger.info("Key Milestone Years:")
    logger.info("-" * 60)

    for person in schedule['person'].unique():
        person_data = schedule[schedule['person'] == person]

        # Find first year with benefits
        first_benefit = person_data[person_data['monthly_benefit'] > 0]
        if not first_benefit.empty:
            first_row = first_benefit.iloc[0]
            logger.info(
                "%s starts receiving benefits: Year %d (Age %d): $%,.2f/month",
                person, first_row['year'], first_row['age'], first_row['monthly_benefit']
            )

            # Show 5 years later
            five_years_later = person_data[
                person_data['year'] == first_row['year'] + 5
            ]
            if not five_years_later.empty:
                later_row = five_years_later.iloc[0]
                logger.info(
                    "  Year %d (Age %d): $%,.2f/month",
                    later_row['year'], later_row['age'], later_row['monthly_benefit']
                )


def main() -> int:
    args = parse_args()

    logger.info("Loading configuration from config.py...")
    config = get_config_manager()

    logger.info("Validating SSI settings...")
    is_valid, errors = validate_config_ssi_settings(config)

    if not is_valid:
        logger.error(
            "Configuration validation failed:\n%s",
            "\n".join(f"  - {e}" for e in errors)
        )
        return 1

    logger.info("Configuration is valid")
    _log_config_settings(config, args.cola)

    if args.validate_only:
        logger.info("Validation complete (--validate-only flag set)")
        return 0

    end_year = args.end_year or args.start_year + 30
    logger.info("Generating schedule from %d to %d...", args.start_year, end_year)

    schedule = generate_ssi_schedule_from_config(
        config_manager=config,
        start_year=args.start_year,
        end_year=end_year,
        cola_rate=args.cola
    )

    if schedule.empty:
        logger.warning("No schedule generated. Check that SSI amounts are set in config.py")
        return 1

    schedule.to_csv(args.output, index=False)
    logger.info("Schedule exported to: %s", args.output)

    _log_schedule_summary(schedule, args.start_year, end_year)

    logger.info("=" * 60)
    logger.info("Schedule generation complete!")
    logger.info("=" * 60)

    return 0


if __name__ == "__main__":
    exit(main())

# Made with Bob
