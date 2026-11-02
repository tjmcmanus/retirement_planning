"""Settings schema: the single source for the Settings page form and for server-side validation.

Field bounds, options and labels mirror the widgets in ``pages/2_configuration.py``.
A field's ``path`` is ``section.key`` (or ``section.group.key`` for nested settings).

Not in the schema (still Streamlit-only): LTC/HSA analyzers, the Social Security optimizer and its
inputs (``person*_gender``, ``*_life_expectancy``, ``*_current_earnings``; the birth year is derived from
``personal_info.person*_birth_date`` via ``ConfigManager.birth_year``), the Medicare
and SS guides, and the Portfolio Data editor.
"""
from __future__ import annotations

import copy
import datetime as dt
import math
import re
from typing import Any

US_STATES = [
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA", "HI", "ID", "IL", "IN", "IA", "KS", "KY",
    "LA", "ME", "MD", "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ", "NM", "NY", "NC", "ND",
    "OH", "OK", "OR", "PA", "RI", "SC", "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY",
]

CONDITIONS = [
    ("high_blood_pressure", "High Blood Pressure"), ("high_cholesterol", "High Cholesterol"),
    ("type2_diabetes", "Type 2 Diabetes"), ("type1_diabetes", "Type 1 Diabetes"),
    ("atherosclerosis", "Atherosclerosis"), ("copd", "COPD"), ("cancer", "Cancer"),
    ("parkinsons", "Parkinson's Disease"), ("alzheimers", "Alzheimer's Disease"),
]

NOT_SINGLE = [["personal_info.is_single_person", "falsy", None]]


def num(path, label, lo, hi, step=1, *, integer=False, help="", show_if=None, prefix="", suffix="", default=None):
    return {"type": "number", "path": path, "label": label, "min": lo, "max": hi, "step": step,
            "int": integer, "help": help, "show_if": show_if or [], "prefix": prefix, "suffix": suffix,
            "default": default}


def text(path, label, *, help="", max_len=120, show_if=None):
    return {"type": "text", "path": path, "label": label, "help": help, "max_len": max_len, "show_if": show_if or []}


def date(path, label, *, help="", show_if=None, nullable=False):
    return {"type": "date", "path": path, "label": label, "help": help, "show_if": show_if or [], "nullable": nullable}


def boolean(path, label, *, help="", show_if=None, default=False):
    return {"type": "bool", "path": path, "label": label, "help": help, "show_if": show_if or [],
            "default": default}


def select(path, label, options, *, help="", show_if=None, nullable=False):
    return {"type": "select", "path": path, "label": label, "options": options, "help": help,
            "show_if": show_if or [], "nullable": nullable}


def computed(cid, show_if=None):
    return {"type": "computed", "id": cid, "show_if": show_if or []}


# Mirrors portfolio_data_entry.VALID_ACCOUNT_TYPES (tests keep the two in step).
ACCOUNT_TYPES = ["Checking", "Savings", "Brokerage", "Traditional", "Roth"]


def table(path, label, columns, required, *, help="", show_if=None):
    return {"type": "table", "path": path, "label": label, "columns": columns, "required": required,
            "help": help, "show_if": show_if or []}


def _per_person(builder):
    return [builder(1), builder(2)]


def _healthcare(n: int):
    p = f"healthcare.person{n}_"
    show = [] if n == 1 else NOT_SINGLE
    return {
        "title": "{p%d}'s Healthcare" % n,
        "fields": [
            select(p + "preretirement_coverage_type", "Pre-Retirement Coverage Type",
                   ["None", "Employer", "ACA Marketplace"], show_if=show),
            num(p + "preretirement_insurance_monthly", "Monthly Pre-Retirement Premium", 0, 5000, 50, integer=True,
                prefix="$", show_if=show + [[p + "preretirement_coverage_type", "ne", "None"]]),
            select(p + "retirement_coverage_type", "Retirement Coverage Type (post-retirement, pre-Medicare)",
                   ["None", "Employer Retiree", "ACA Marketplace"], show_if=show),
            num(p + "aca_insurance_monthly", "Monthly Retirement Premium (before subsidies if ACA)", 0, 5000, 50,
                integer=True, prefix="$", show_if=show + [[p + "retirement_coverage_type", "ne", "None"]]),
            num(p + "aca_start_age", "ACA Coverage Start Age", 50, 65, integer=True, show_if=show),
            num(p + "aca_end_age", "ACA Coverage End Age", 60, 70, integer=True, show_if=show),
            num(p + "medicare_start_age", "Medicare Start Age", 60, 70, integer=True, show_if=show),
            {"type": "multi", "path": f"healthcare.person{n}_conditions", "label": "Chronic conditions (adjust out-of-pocket tier)",
             "options": CONDITIONS, "help": "Checked conditions raise the out-of-pocket tier used for healthcare projections.",
             "show_if": show},
            computed(f"health_cost_{n}", show_if=show),
        ],
    }


def _social_security(n: int):
    p = f"social_security.person{n}_"
    show = [] if n == 1 else NOT_SINGLE
    return {
        "title": "{p%d}'s Social Security" % n,
        "fields": [
            num(p + "ssi_age", "Age to Start Benefits", 62, 70, integer=True, show_if=show,
                help="Age when you plan to start collecting Social Security (62-70)."),
            num(p + "ssi_amount", "Monthly Benefit at Age 67", 0, 10000, 100, integer=True, prefix="$", show_if=show,
                help="Estimated MONTHLY benefit at Full Retirement Age (67). Adjusted for the claiming age."),
            computed(f"ss_preview_{n}", show_if=show),
        ],
    }


_LIVING = [
    ("property_tax", "Property Tax (Annual)", 100000, 100), ("homeowners_insurance", "Homeowners Insurance (Annual)", 50000, 100),
    ("auto_insurance", "Auto Insurance (Annual)", 20000, 100), ("food_groceries", "Food & Groceries (Annual)", 100000, 500),
    ("utilities_phone", "Phone (Annual)", 10000, 50), ("utilities_internet", "Internet (Annual)", 10000, 50),
    ("utilities_cable", "Cable/Streaming (Annual)", 10000, 50), ("utilities_electric", "Electric (Annual)", 20000, 100),
    ("utilities_gas", "Gas/Heating (Annual)", 20000, 100), ("utilities_water", "Water/Sewer (Annual)", 10000, 50),
    ("gifts_donations", "Gifts & Donations (Annual)", 100000, 100), ("other_living", "Other Living Expenses (Annual)", 100000, 100),
]
LIVING_KEYS = [k for k, *_ in _LIVING]
_ENT = [
    ("travel_vacations", "Travel & Vacations (Annual)", 200000), ("dining_out", "Dining Out (Annual)", 100000),
    ("clothing", "Clothing & Personal Care (Annual)", 100000), ("hobbies", "Hobbies & Recreation (Annual)", 100000),
    ("entertainment_other", "Other Entertainment (Annual)", 100000),
]
ENTERTAINMENT_KEYS = [k for k, *_ in _ENT]

_STAGES = [
    (1, "Stage 1: Accumulation (%)", "Employed, earning wages, building retirement accounts"),
    (2, "Stage 2: Prep for Retirement (%)", "Employed, within 10 years of retirement, optimizing Roth/Traditional balance"),
    (3, "Stage 3: Early Retirement (%)", "Pre-Medicare, pre-SS, pre-RMD: prime conversion years with low income"),
    (4, "Stage 4: Medicare Stage (%)", "IRMAA optimization with Medicare, pre-SS, pre-RMD"),
    (5, "Stage 5: Social Security Stage (%)", "SS benefits + Medicare, pre-RMD"),
    (6, "Stage 6: RMD Stage (%)", "Required Minimum Distributions: limited conversion capacity"),
    (7, "Stage 7: Surviving Spouse (%)", "Single filer with survivor benefits: conservative conversions"),
]

_BUCKET_ON = [["bucket_strategy.enabled", "truthy", None]]
_TREND_ON = _BUCKET_ON + [["bucket_strategy.market_trend_adjustment.enabled", "truthy", None]]
_DECLINE_ON = [["expenses.entertainment_expenses.retirement_decline_enabled", "truthy", None]]
_SURVIVING = NOT_SINGLE + [["personal_info.surviving_spouse_mode", "truthy", None]]
_DAF_ON = [["charitable_giving.has_daf", "truthy", None]]
SECTIONS: list[dict[str, Any]] = [
    {"id": "personal", "label": "Personal Info", "groups": [
        {"title": "Planning mode", "fields": [
            boolean("personal_info.is_single_person", "Planning for a single person (not a couple)",
                    help="Hides spouse/partner fields and uses single filing status."),
        ]},
        {"title": "Primary person", "fields": [
            text("personal_info.person1_name", "Name", max_len=60),
            date("personal_info.person1_birth_date", "Birth Date"),
            date("personal_info.person1_retirement_date", "Planned Retirement Date"),
            computed("ages_1"),
        ]},
        {"title": "Spouse / partner", "fields": [
            text("personal_info.person2_name", "Name", max_len=60, show_if=NOT_SINGLE),
            date("personal_info.person2_birth_date", "Birth Date", show_if=NOT_SINGLE),
            date("personal_info.person2_retirement_date", "Planned Retirement Date", show_if=NOT_SINGLE),
            computed("ages_2", show_if=NOT_SINGLE),
        ]},
        {"title": "Retirement location", "fields": [
            select("personal_info.retirement_state", "Retirement State", US_STATES,
                   help="Affects state tax calculations."),
        ]},
        {"title": "Stage 7: surviving spouse planning", "fields": [
            boolean("personal_info.surviving_spouse_mode", "Planning for a surviving spouse scenario (Stage 7)",
                    help="Single filer tax status and survivor benefits from the year after death.", show_if=NOT_SINGLE),
            select("personal_info.decedent_person", "Decedent (deceased person)", [["person1", "Primary"], ["person2", "Spouse / partner"]],
                   show_if=_SURVIVING, nullable=True),
            date("personal_info.date_of_death", "Date of Death", show_if=_SURVIVING, nullable=True),
        ]},
        {"title": "Children", "fields": [
            table("personal_info.children", "Children", [
                {"key": "name", "label": "Child's Name", "type": "text", "max_len": 60},
                {"key": "birth_date", "label": "Birth Date", "type": "date"},
                {"key": "special_needs", "label": "Special Needs", "type": "bool"},
            ], ["name", "birth_date"],
                help="Used for estate planning suggestions, dependent tax calculations and college funding strategies."),
        ]},
    ]},
    {"id": "assumptions", "label": "Financial Assumptions", "groups": [
        {"title": "Expected annual expenses", "fields": [computed("expense_totals")]},
        {"title": "Assumptions", "fields": [
            num("financial_assumptions.expense_inflation_rate", "Expense Inflation Rate", 0, 10, 0.1, suffix="%",
                help="Expected annual increase in expenses."),
            num("financial_assumptions.expected_rate_of_return", "Expected Rate of Return", 0, 20, 0.1, suffix="%",
                help="Expected annual investment return."),
            num("financial_assumptions.years_of_expenses_in_cash", "Years of Expenses in Cash", 1, 10, integer=True,
                help="Years of expenses to keep in cash/safe assets (retirement phase)."),
            num("financial_assumptions.brokerage_rebalance_trigger_multiplier", "Taxable Account Buffer Multiplier", 0.5, 5, 0.5,
                help="Base target is 1 year of expenses. 2.0 = keep 2 years in the taxable account."),
            num("financial_assumptions.accumulation_cash_buffer_months", "Accumulation Phase: Cash Buffer (months of wages)",
                3, 24, integer=True, help="Working years: target this many months of gross wages in cash."),
        ]},
        {"title": "Income (pre-retirement)", "fields": [
            num("income.person1_annual_wages", "{p1}: Annual Wages/Salary", 0, 1000000, 5000, integer=True, prefix="$"),
            num("income.person2_annual_wages", "{p2}: Annual Wages/Salary", 0, 1000000, 5000, integer=True, prefix="$",
                show_if=NOT_SINGLE),
            num("income.wage_inflation_rate", "Wage Inflation Rate", 0, 10, 0.1, suffix="%"),
        ]},
        {"title": "Retirement contributions (pre-retirement)", "fields": [
            num("income.contribution_401k_percent", "401k Contribution (% of wages)", 0, 100, 0.5, suffix="%",
                help="Pre-tax (Traditional) 401k deferral as a percent of wages."),
            num("income.contribution_roth_percent", "Roth Contribution (% of wages)", 0, 100, 0.5, suffix="%",
                help="After-tax Roth contribution as a percent of wages."),
            num("income.contribution_brokerage_percent", "Brokerage Contribution (% of wages)", 0, 100, 0.5, suffix="%",
                help="Taxable brokerage savings as a percent of wages."),
            num("income.employer_match_percent", "Employer Match (% of wages)", 0, 25, 0.5, suffix="%",
                help="Employer matches your 401k/Roth deferral dollar-for-dollar up to this percent of wages. "
                     "The match always goes in pre-tax (Traditional)."),
            boolean("income.contribution_auto_split", "Auto-split Roth vs Traditional by tax rate (accumulation years)",
                    help="Accumulation years only: send the deferral to Traditional when today's marginal rate is "
                         "higher than your expected retirement rate, and to Roth when it is lower. Off keeps the "
                         "percentages above. Prep-for-retirement years always use this rate comparison."),
            num("income.expected_retirement_tax_rate", "Expected Retirement Marginal Rate", 0, 37, 1, suffix="%",
                integer=True,
                help="Your expected federal marginal rate in retirement (many retirees land in 12-22%)."),
        ]},
        {"title": "Other income sources (today's dollars)", "fields": [
            num("income.pension_annual", "Pension / Annuity ($/yr)", 0, 500000, 1000, integer=True, prefix="$"),
            num("income.interest_annual", "Interest Income ($/yr)", 0, 200000, 500, integer=True, prefix="$"),
            num("income.rental_annual", "Net Rental Income ($/yr)", 0, 500000, 1000, integer=True, prefix="$"),
            num("income.dividend_annual", "Dividend Income ($/yr)", 0, 200000, 500, integer=True, prefix="$"),
        ]},
    ]},
    {"id": "expenses", "label": "Expenses", "groups": [
        {"title": "Living expenses (do not go away in retirement)",
         "fields": [num(f"expenses.living_expenses.{k}", lbl, 0, hi, st, integer=True, prefix="$") for k, lbl, hi, st in _LIVING]
         + [computed("living_total")]},
        {"title": "Entertainment & lifestyle", "fields": [
            *[num(f"expenses.entertainment_expenses.{k}", lbl, 0, hi, 500, integer=True, prefix="$") for k, lbl, hi in _ENT],
            boolean("expenses.entertainment_expenses.retirement_decline_enabled", "Enable retirement decline",
                    help="Reduce entertainment expenses in retirement."),
            num("expenses.entertainment_expenses.retirement_decline_percent", "Retirement Decline (%)", 0, 100, 5, integer=True,
                suffix="%", show_if=_DECLINE_ON),
            num("expenses.entertainment_expenses.retirement_decline_start_age", "Decline Start Age", 50, 80, integer=True,
                show_if=_DECLINE_ON),
        ]},
        {"title": "Big ticket items", "fields": [
            table("expenses.big_ticket_items", "Big ticket items", [
                {"key": "name", "label": "Item Name", "type": "text", "max_len": 100},
                {"key": "amount", "label": "Amount ($)", "type": "number", "min": 0, "max": 1000000, "step": 1000},
                {"key": "frequency_years", "label": "Every (years)", "type": "number", "min": 1, "max": 50, "int": True},
                {"key": "start_year", "label": "Start Year", "type": "number", "min": 2020, "max": 2100, "int": True},
                {"key": "end_year", "label": "End Year", "type": "number", "min": 2020, "max": 2100, "int": True},
            ], ["name", "amount"], help="Major purchases that occur periodically: a car every 10-15 years, weddings, a roof."),
        ]},
    ]},
    {"id": "healthcare", "label": "Healthcare", "groups": _per_person(_healthcare)},
    {"id": "social_security", "label": "Social Security", "groups": _per_person(_social_security)},
    {"id": "tax", "label": "Tax Strategy", "groups": [
        {"title": "Strategy Selectors", "fields": [
            select("tax_strategy.withdrawal_sequence", "Withdrawal Account Sequence", [
                ["taxable_deferred_free", "Taxable, Tax-Deferred, Tax-Free (Standard)"],
                ["pro_rata", "Pro-Rata (Proportional across all accounts)"],
                ["taxable_free_deferred", "Taxable, Tax-Free, Tax-Deferred"],
                ["deferred_taxable_free", "Tax-Deferred, Taxable, Tax-Free"],
                ["deferred_free_taxable", "Tax-Deferred, Tax-Free, Taxable"],
                ["free_deferred_taxable", "Tax-Free, Tax-Deferred, Taxable"],
                ["free_taxable_deferred", "Tax-Free, Taxable, Tax-Deferred"],
            ], help="Priority order of accounts from which living expenses and cash buffer deficits are sourced."),
            select("tax_strategy.roth_conversion_target", "Roth Conversion Fill Target", [
                ["none", "No Conversions (0%)"],
                ["fill_0", "Roth Conversions to fill 0% Brkt"],
                ["fill_10", "Roth Conversions to fill 10% Brkt"],
                ["fill_12", "Roth Conversions to fill 12% Brkt"],
                ["irmaa_1", "Roth Conversions below IRMAA Brkt 1"],
                ["fill_22", "Roth Conversions to fill 22% Brkt"],
                ["irmaa_2", "Roth Conversions below IRMAA Brkt 2"],
                ["irmaa_3", "Roth Conversions below IRMAA Brkt 3"],
                ["irmaa_4", "Roth Conversions below IRMAA Brkt 4"],
                ["fill_24", "Roth Conversions to fill 24% Brkt"],
                ["fill_32", "Roth Conversions to fill 32% Brkt"],
                ["irmaa_5", "Roth Conversions below IRMAA Brkt 5"],
                ["fill_35", "Roth Conversions to fill 35% Brkt"],
                ["max", "Maximum Roth Conversion"],
            ], help="Target tax bracket ceiling or IRMAA threshold up to which Traditional IRA/401(k) balances are converted to Roth."),
        ]},
        {"title": "Roth conversions", "fields": [
            num("tax_strategy.max_roth_conversion_tax_rate", "Global Maximum Tax Rate for Conversions (legacy)", 0, 37, integer=True,
                suffix="%", help="Used if stage-specific rates are not configured."),
        ]},
        {"title": "Stage-specific conversion rate limits", "fields": [
            num(f"tax_strategy.stage_{i}_max_conversion_rate", lbl, 0, 37, integer=True, suffix="%", help=h)
            for i, lbl, h in _STAGES
        ]},
        {"title": "January bracket-fill strategy", "fields": [
            boolean("tax_strategy.use_january_bracket_fill_strategy", "Enable January Bracket-Fill Strategy",
                    help="Single January withdrawal instead of continuous BETR optimization."),
            num("tax_strategy.savings_safety_reserve", "Savings Safety Reserve", 0, 500000, 1000, integer=True, prefix="$",
                help="Minimum savings balance before mid-year brokerage supplementation triggers. "
                     "When never saved, defaults to 5 months of expected expenses."),
            boolean("tax_strategy.use_60day_rollover_mechanics", "Use 60-Day Rollover for Roth Conversions",
                    help="Withhold conversion taxes from Traditional, redeposit within 60 days.", default=True),
        ]},
        {"title": "Traditional → Brokerage pre-fund by year (optional)", "fields": [
            table("tax_strategy.trad_prefund_schedule", "Pre-fund amounts", [
                {"key": "year", "label": "Year", "type": "number", "min": 2020, "max": 2100, "int": True},
                {"key": "amount", "label": "Amount ($)", "type": "number", "min": 0, "max": 5_000_000, "step": 5000,
                 "int": True},
            ], ["year", "amount"],
                help="Move $X from Traditional to Brokerage in a given year, e.g. to seed a Direct Indexing portfolio. "
                     "Taxed as ordinary income; Roth conversion is skipped that year. Applies in any stage "
                     "(1 through 7). Pair it with a DAF gift that year to offset the income."),
        ]},
    ]},
    {"id": "charitable", "label": "Charitable Giving", "groups": [
        {"title": "Annual charitable contributions", "fields": [
            num("charitable_giving.annual_charitable_giving", "Annual Charitable Giving Goal", 0, 1_000_000, 1000,
                integer=True, prefix="$", help="Your target annual charitable giving amount."),
            num("charitable_giving.charitable_giving_start_age", "Start Age for Charitable Giving", 50, 100, integer=True,
                help="Age when you plan to start regular charitable giving."),
            num("charitable_giving.charitable_giving_end_age", "End Age for Charitable Giving", 50, 110, integer=True,
                help="Age when you plan to stop charitable giving."),
            num("charitable_giving.charitable_giving_inflation_rate", "Charitable Giving Inflation Rate", 0, 10, 0.1,
                suffix="%", help="Expected annual increase in charitable giving."),
        ]},
        {"title": "Donor Advised Fund (DAF)", "fields": [
            boolean("charitable_giving.has_daf", "I already have a Donor Advised Fund set up",
                    help="Check this once you have opened a DAF (e.g. Fidelity, Schwab or Vanguard Charitable)."),
            text("charitable_giving.daf_provider", "DAF Provider", show_if=_DAF_ON,
                 help="Sponsoring organization, e.g. Fidelity Charitable, Schwab Charitable, Vanguard Charitable."),
            num("charitable_giving.daf_initial_contribution", "Initial DAF Contribution", 0, 10_000_000, 5000,
                integer=True, prefix="$", show_if=_DAF_ON, help="One-time initial contribution to establish your DAF."),
            num("charitable_giving.daf_annual_contribution", "Bundled DAF Contribution", 0, 10_000_000, 5000,
                integer=True, prefix="$", show_if=_DAF_ON,
                help="Amount contributed in each bundling year. The Streamlit page recalculates this from your giving "
                     "goal when it saves; see the suggestion below."),
            num("charitable_giving.daf_contribution_start_year", "DAF Contribution Start Year", 2020, 2100,
                integer=True, show_if=_DAF_ON, help="First tax year to make a DAF contribution."),
            num("charitable_giving.daf_contribution_end_year", "DAF Contribution End Year", 2020, 2100,
                integer=True, show_if=_DAF_ON,
                help="Last tax year to make a DAF contribution (inclusive). Stop before QCDs become more efficient."),
            computed("daf_bundle_suggestion", show_if=_DAF_ON),
        ]},
    ]},
    {"id": "rebalancing", "label": "Rebalancing", "groups": [
        {"title": "Preferred funds for rebalancing recommendations", "fields": [
            text("rebalancing_preferences.cash_symbol", "Cash Symbol", help="Symbol for cash/money market positions."),
            text("rebalancing_preferences.bonds_traditional", "Bonds: Traditional IRA"),
            text("rebalancing_preferences.bonds_roth", "Bonds: Roth IRA"),
            text("rebalancing_preferences.bonds_brokerage", "Bonds: Brokerage", help="Prefer Treasuries/munis for tax efficiency."),
            text("rebalancing_preferences.stocks_traditional", "Stocks: Traditional IRA"),
            text("rebalancing_preferences.stocks_roth", "Stocks: Roth IRA"),
            text("rebalancing_preferences.stocks_brokerage", "Stocks: Brokerage"),
        ]},
    ]},
    {"id": "bucket", "label": "Bucket Strategy", "groups": [
        {"title": "Bucket strategy", "fields": [
            boolean("bucket_strategy.enabled", "Enable Bucket Strategy",
                    help="Divides assets into buckets by when the money is needed, to manage sequence-of-returns risk."),
        ]},
        {"title": "Bucket sizing", "fields": [
            num("bucket_strategy.bucket_1_years", "Bucket 1: Years of Expenses (Safety)", 1, 5, 0.5, show_if=_BUCKET_ON,
                help="Cash/money market, typically 1-3 years."),
            num("bucket_strategy.bucket_2_years", "Bucket 2: Years of Expenses (Transition)", 5, 15, integer=True,
                show_if=_BUCKET_ON, help="Graduated allocation, typically 5-10 years."),
            num("bucket_strategy.bucket_2_start_stock_pct", "Starting Stock % (Year 1 of Bucket 2)", 0, 50, 5, integer=True,
                suffix="%", show_if=_BUCKET_ON),
            num("bucket_strategy.bucket_2_end_stock_pct", "Ending Stock % (final year of Bucket 2)", 50, 100, 5, integer=True,
                suffix="%", show_if=_BUCKET_ON),
            computed("bucket_progression", show_if=_BUCKET_ON),
        ]},
        {"title": "Market trend adjustments", "fields": [
            boolean("bucket_strategy.market_trend_adjustment.enabled", "Enable Market Trend-Based Adjustments",
                    help="Adjust stock allocations using SPY moving averages.", show_if=_BUCKET_ON),
            num("bucket_strategy.market_trend_adjustment.short_ma_weeks", "Short-term Moving Average (weeks)", 5, 20,
                integer=True, show_if=_TREND_ON),
            num("bucket_strategy.market_trend_adjustment.long_ma_weeks", "Long-term Moving Average (weeks)", 30, 100,
                integer=True, show_if=_TREND_ON),
            num("bucket_strategy.market_trend_adjustment.bull_adjustment", "Bull Market Adjustment (%)", -10, 10, 1,
                show_if=_TREND_ON),
            num("bucket_strategy.market_trend_adjustment.warning_adjustment", "Warning Market Adjustment (%)", -30, 0, 1,
                show_if=_TREND_ON),
            num("bucket_strategy.market_trend_adjustment.bear_adjustment", "Bear Market Adjustment (%)", -50, 0, 1,
                show_if=_TREND_ON),
        ]},
    ]},
    {"id": "accounts", "label": "Accounts", "groups": [
        {"title": "Account mapping", "fields": [
            table("portfolio_accounts.accounts", "Your Accounts", [
                {"key": "account_name", "label": "Account Name", "type": "text", "max_len": 100},
                {"key": "account_type", "label": "Account Type", "type": "select", "options": ACCOUNT_TYPES},
                {"key": "owner", "label": "Owner", "type": "text", "max_len": 60, "choices": "owners"},
            ], ["account_name", "account_type", "owner"],
                help="Brokerage syncs (Connections) look each account up here by name to set its type and owner; "
                     "an account that is not listed is stored as Brokerage / Joint. Names must match what the sync "
                     "produces: the SnapTrade account name, or Schwab-<last 4 digits> for Schwab. Saving also "
                     "updates the type and owner of holdings already in the portfolio."),
        ]},
    ]},
    {"id": "real_estate", "label": "Real Estate", "groups": [
        {"title": "Properties", "fields": [
            table("real_estate.properties", "Properties", [
                {"key": "property_name", "label": "Property Name", "type": "text", "max_len": 100},
                {"key": "address", "label": "Address", "type": "text", "max_len": 200},
                {"key": "purchase_price", "label": "Purchase Price ($)", "type": "number", "min": 0.01, "max": 1e10, "step": 1000},
            ], ["property_name", "address", "purchase_price"],
                help="Purchase prices appear in the Net Worth statement under Real Estate."),
            computed("re_total"),
        ]},
    ]},
]


# ---------------------------------------------------------------------------
# Lookup and validation
# ---------------------------------------------------------------------------

def _all_fields() -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for sec in SECTIONS:
        for grp in sec["groups"]:
            for f in grp["fields"]:
                if "path" in f:
                    out[f["path"]] = f
    return out


FIELDS = _all_fields()


def schema_payload() -> dict[str, Any]:
    return {"sections": SECTIONS}


def get_path(tree: dict, path: str, default: Any = None) -> Any:
    cur: Any = tree
    for part in path.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return default
        cur = cur[part]
    return cur


def _exists(tree: dict, path: str) -> bool:
    sentinel = object()
    return get_path(tree, path, sentinel) is not sentinel


def flatten(changes: dict[str, Any]) -> dict[str, Any]:
    """``{"a": {"b": {"c": 1}}}`` -> ``{"a.b.c": 1}``. Lists and scalars are leaves."""
    out: dict[str, Any] = {}

    def walk(prefix: str, value: Any) -> None:
        if isinstance(value, dict):
            for k, v in value.items():
                walk(f"{prefix}.{k}" if prefix else str(k), v)
        else:
            out[prefix] = value

    walk("", changes)
    return out


_ISO = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _is_number(v: Any) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def _valid_date(v: Any) -> bool:
    if not isinstance(v, str) or not _ISO.match(v):
        return False
    try:
        dt.datetime.strptime(v, "%Y-%m-%d")
        return True
    except ValueError:
        return False


def _check_scalar(spec: dict[str, Any], v: Any) -> str | None:
    t = spec["type"]
    if t == "number":
        if not _is_number(v):
            return "Must be a number"
        if spec.get("int") and v != int(v):
            return "Must be a whole number"
        if v < spec["min"] or v > spec["max"]:
            return f"Must be between {spec['min']:g} and {spec['max']:g}"
    elif t == "text":
        if not isinstance(v, str):
            return "Must be text"
        if len(v) > spec.get("max_len", 120):
            return f"Must be at most {spec.get('max_len', 120)} characters"
    elif t == "date":
        if v is None and spec.get("nullable"):
            return None
        if not _valid_date(v):
            return "Must be a valid date (YYYY-MM-DD)"
    elif t == "bool":
        if not isinstance(v, bool):
            return "Must be true or false"
    elif t == "select":
        if v is None and spec.get("nullable"):
            return None
        allowed = [o[0] if isinstance(o, list) else o for o in spec["options"]]
        if v not in allowed:
            return "Must be one of: " + ", ".join(map(str, allowed))
    elif t == "multi":
        allowed = [o[0] for o in spec["options"]]
        if not isinstance(v, list) or any(x not in allowed for x in v) or len(set(v)) != len(v):
            return "Invalid selection"
    return None


def _check_table(spec: dict[str, Any], rows: Any) -> list[str]:
    if not isinstance(rows, list):
        return ["Must be a list of rows"]
    errs: list[str] = []
    for i, row in enumerate(rows, start=1):
        if not isinstance(row, dict):
            errs.append(f"Row {i}: must be an object")
            continue
        for col in spec["columns"]:
            key = col["key"]
            if key not in row:
                if key in spec["required"]:
                    errs.append(f"Row {i}: {col['label']} is required")
                continue
            v = row[key]
            if key in spec["required"] and (v is None or (isinstance(v, str) and not v.strip())):
                errs.append(f"Row {i}: {col['label']} is required")
                continue
            msg = _check_scalar(col, v)
            if msg:
                errs.append(f"Row {i}: {col['label']}: {msg}")
        extra = set(row) - {c["key"] for c in spec["columns"]}
        if extra:
            errs.append(f"Row {i}: unknown column(s): {', '.join(sorted(extra))}")
    return errs


def validate_changes(changes: dict[str, Any], current: dict[str, Any], defaults: dict[str, Any]) -> list[dict[str, str]]:
    """Return ``[{"path", "message"}]``; empty means valid. ``current`` is the saved config."""
    errors: list[dict[str, str]] = []
    for path, value in flatten(changes).items():
        spec = FIELDS.get(path)
        if spec is None:
            # Not editable in the form. Allow only keys that already exist (default or saved) with the same JSON type.
            if not (_exists(defaults, path) or _exists(current, path)):
                errors.append({"path": path, "message": "Unknown setting"})
                continue
            old = get_path(current, path, get_path(defaults, path))
            if old is not None and type(old) is not type(value) and not (_is_number(old) and _is_number(value)):
                errors.append({"path": path, "message": f"Expected {type(old).__name__}"})
            continue
        if spec["type"] == "table":
            errors += [{"path": path, "message": m} for m in _check_table(spec, value)]
            continue
        msg = _check_scalar(spec, value)
        if msg:
            errors.append({"path": path, "message": msg})
    return errors


def validate_merged(merged: dict[str, Any]) -> list[dict[str, str]]:
    """Cross-field rules that need the final configuration."""
    errors: list[dict[str, str]] = []
    pi = merged.get("personal_info", {})
    if pi.get("surviving_spouse_mode") and not pi.get("is_single_person"):
        if pi.get("decedent_person") not in ("person1", "person2"):
            errors.append({"path": "personal_info.decedent_person", "message": "Required when planning for a surviving spouse"})
        if not _valid_date(pi.get("date_of_death")):
            errors.append({"path": "personal_info.date_of_death", "message": "Required when planning for a surviving spouse"})

    names = [str(a.get("account_name", "")).strip() for a in merged.get("portfolio_accounts", {}).get("accounts", []) or []]
    if len(names) != len(set(names)):
        errors.append({"path": "portfolio_accounts.accounts", "message": "Each account name may appear only once"})

    cg = merged.get("charitable_giving", {})
    if cg.get("charitable_giving_end_age", 0) < cg.get("charitable_giving_start_age", 0):
        errors.append({"path": "charitable_giving.charitable_giving_end_age",
                       "message": "End age must be at least the start age"})
    years = [r.get("year") for r in merged.get("tax_strategy", {}).get("trad_prefund_schedule", []) or []]
    if len(years) != len(set(years)):
        errors.append({"path": "tax_strategy.trad_prefund_schedule", "message": "Each year may appear only once"})
    if cg.get("has_daf"):
        if cg.get("daf_contribution_end_year", 0) < cg.get("daf_contribution_start_year", 0):
            errors.append({"path": "charitable_giving.daf_contribution_end_year",
                           "message": "End year must be at least the start year"})
    return errors


def deep_copy(v: Any) -> Any:
    return copy.deepcopy(v)
