# Debug Logging Guide for calculations.py

## Overview

The `calculations.py` file now includes configurable debug level logging for all previously commented-out print statements. This allows you to enable detailed debugging output when needed without modifying the code.

## Logging Configuration

### Default Behavior
By default, logging is set to **WARNING** level, which means debug messages are suppressed and won't appear in the output.

### Enabling Debug Logging

There are three ways to enable debug logging:

#### 1. Environment Variable (Recommended)
Set the `LOG_LEVEL` environment variable before running your application:

```bash
# Linux/Mac
export LOG_LEVEL=DEBUG
python planning_app.py

# Windows (Command Prompt)
set LOG_LEVEL=DEBUG
python planning_app.py

# Windows (PowerShell)
$env:LOG_LEVEL="DEBUG"
python planning_app.py
```

#### 2. Modify the Code Temporarily
In `calculations.py`, change line 18 from:
```python
log_level = logging.getLevelName(os.getenv('LOG_LEVEL', 'WARNING'))
```
to:
```python
log_level = logging.DEBUG
```

#### 3. Programmatic Configuration
In your main application file (e.g., `planning_app.py`), add this at the top:
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## Log Levels

The logging system supports multiple levels:

- **DEBUG**: Detailed information for diagnosing problems (all debug messages)
- **INFO**: Confirmation that things are working as expected
- **WARNING**: Default level - indication that something unexpected happened
- **ERROR**: A serious problem occurred
- **CRITICAL**: A very serious error

## Log Format

Debug messages include:
- Timestamp (YYYY-MM-DD HH:MM:SS)
- Log level (DEBUG, INFO, WARNING, etc.)
- Function name where the log was generated
- Line number
- The actual message

Example output:
```
2026-02-22 09:15:30 - DEBUG - calc_roth_conversions:42 - MaxRate is 0.12 and Headroom is 0.22
2026-02-22 09:15:30 - DEBUG - calc_roth_conversions:43 - Headroom_conv is 15000.0
```

## Functions with Debug Logging

The following functions now include debug logging:

1. **calc_roth_conversions_tax()** - Roth conversion tax calculations
2. **calc_roth_conversions()** - Roth conversion amounts
3. **calc_agi()** - Adjusted Gross Income calculations
4. **calc_daf_value()** - Donor Advised Fund calculations
5. **getUpperIncomeRate()** - Tax bracket queries
6. **calc_atm_phase_out()** - Alternative Minimum Tax phase-out
7. **calculate_atm()** - Alternative Minimum Tax calculations
8. **calculate_atm1()** - Alternative ATM calculations
9. **calculate_std_deduction()** - Standard deduction logic
10. **calculate_irmma_penalty()** - IRMAA penalty calculations
11. **calculate_cap_gains()** - Capital gains tax calculations
12. **calculate_taxable_income()** - Taxable income calculations
13. **get_rmd_value()** - Required Minimum Distribution lookups

## Tips

- Use DEBUG level during development and troubleshooting
- Use WARNING level (default) in production
- Debug messages include variable values, calculation steps, and decision paths
- All monetary values are formatted with thousand separators for readability

## Example Usage

```python
# In your terminal
export LOG_LEVEL=DEBUG

# Run your application
python planning_app.py

# You'll now see detailed debug output like:
# 2026-02-22 09:15:30 - DEBUG - calc_agi:75 - calc_agi inputs: joint_gross_income=100000, div=5000, daf=10000
# 2026-02-22 09:15:30 - DEBUG - calc_agi:78 - AGI (Daf Route): 95000
```

## Disabling Debug Logging

To return to normal operation (no debug messages):

```bash
# Linux/Mac
unset LOG_LEVEL

# Windows (Command Prompt)
set LOG_LEVEL=

# Windows (PowerShell)
Remove-Item Env:LOG_LEVEL
```

Or simply close your terminal and open a new one.