"""
advanced_strategies.py

Multi-Year Tax Planning and Advanced Retirement Strategies

Implements:
  Multi-Year Tax Planning:
    - 5-year rolling tax optimization window
    - Bracket management across multiple years
    - Capital loss harvesting strategies (multi-year)
    - Qualified Business Income (QBI) deduction planning

  Advanced Strategies:
    - Backdoor Roth IRA contribution tracking
    - Mega backdoor Roth strategies
    - Net Unrealized Appreciation (NUA) for company stock
    - Qualified Charitable Distributions (QCD) optimization
    - 72(t) SEPP (Substantially Equal Periodic Payments) calculations
"""

from __future__ import annotations

import logging
import math
import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from load_data import get_income_tax_brackets, get_cap_gains_brackets, get_std_deduction, get_ira_limits
from calculations import calculate_taxable_income, getUpperIncomeRate, get_std_deduction_by_year

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
log_level = logging.getLevelName(os.getenv("LOG_LEVEL", "WARNING"))
logging.basicConfig(
    level=log_level,
    format="%(asctime)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

IRA_CONTRIBUTION_LIMIT_BASE: int = 7_000
IRA_CATCH_UP_CONTRIBUTION: int = 1_000

K401_EMPLOYEE_LIMIT: int = 23_500
K401_TOTAL_LIMIT: int = 70_000
K401_CATCH_UP_50: int = 7_500
K401_CATCH_UP_60_63: int = 11_250

QCD_ANNUAL_LIMIT: int = 105_000
QCD_ELIGIBLE_AGE: int = 70

RMD_START_AGE: int = 73
NUA_MINIMUM_GAIN_PCT: float = 0.20

SEPP_METHODS: List[str] = [
    "Required Minimum Distribution (RMD)",
    "Fixed Amortization",
    "Fixed Annuitization",
]

EARLY_WITHDRAWAL_PENALTY_AGE: float = 59.5
EARLY_WITHDRAWAL_PENALTY_RATE: float = 0.10

QBI_DEDUCTION_RATE: float = 0.20
QBI_PHASE_OUT_MFJ_START: int = 394_600
QBI_PHASE_OUT_MFJ_END: int = 494_600
QBI_PHASE_OUT_SINGLE_START: int = 197_300
QBI_PHASE_OUT_SINGLE_END: int = 247_300
QBI_W2_LIMIT_RATE: float = 0.50
QBI_W2_UBIA_RATE: float = 0.25

# IRS single-life annuity factors by age (simplified, for SEPP Fixed Annuitization)
_SEPP_ANNUITY_FACTORS: Dict[int, float] = {
    40: 23.8, 45: 20.0, 50: 16.4, 51: 15.9, 52: 15.4, 53: 14.9, 54: 14.4,
    55: 13.9, 56: 13.4, 57: 12.9, 58: 12.4, 59: 11.9, 60: 11.4, 61: 10.9,
    62: 10.4, 63: 9.9, 64: 9.4, 65: 8.9, 66: 8.4, 67: 7.9, 68: 7.4,
    69: 6.9, 70: 6.4,
}

_SEPP_DEFAULT_AFR: float = 0.055  # 120% of mid-term AFR (approximate 2024)


# ===========================================================================
# DATA CLASSES
# ===========================================================================

@dataclass
class YearlyTaxProjection:
    """Single-year tax projection for the rolling window."""
    year: int
    ordinary_income: float = 0.0
    capital_gains_lt: float = 0.0
    capital_gains_st: float = 0.0
    roth_conversion: float = 0.0
    qbi_income: float = 0.0
    charitable_contributions: float = 0.0
    capital_loss_carryforward: float = 0.0
    agi: float = 0.0
    federal_tax: float = 0.0
    effective_rate: float = 0.0
    marginal_rate: float = 0.0
    bracket_headroom: float = 0.0
    qbi_deduction: float = 0.0
    net_capital_loss_used: float = 0.0
    notes: List[str] = field(default_factory=list)


@dataclass
class RollingTaxWindow:
    """5-year rolling tax optimization analysis."""
    years: List[YearlyTaxProjection] = field(default_factory=list)
    total_tax_5yr: float = 0.0
    avg_effective_rate: float = 0.0
    total_bracket_headroom: float = 0.0
    optimization_opportunities: List[str] = field(default_factory=list)
    recommended_conversions: Dict[int, float] = field(default_factory=dict)
    recommended_harvesting: Dict[int, float] = field(default_factory=dict)


@dataclass
class BackdoorRothResult:
    """Result of backdoor Roth IRA contribution analysis."""
    year: int
    contribution_amount: float
    conversion_amount: float
    pro_rata_tax: float
    net_benefit: float
    eligible: bool
    ineligible_reason: str = ""
    steps: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


@dataclass
class MegaBackdoorRothResult:
    """Result of mega backdoor Roth analysis."""
    year: int
    after_tax_contribution: float
    in_plan_conversion: float
    rollover_to_roth_ira: float
    tax_on_earnings: float
    net_benefit: float
    eligible: bool
    ineligible_reason: str = ""
    steps: List[str] = field(default_factory=list)


@dataclass
class NUAAnalysis:
    """Net Unrealized Appreciation analysis for company stock."""
    ticker: str
    shares: float
    cost_basis_per_share: float
    current_price_per_share: float
    total_cost_basis: float
    current_value: float
    nua_amount: float
    nua_pct: float
    ordinary_income_tax_on_basis: float
    ltcg_tax_on_nua: float
    total_nua_tax: float
    tax_if_distributed_as_cash: float
    tax_savings: float
    strategy_recommended: bool
    notes: List[str] = field(default_factory=list)


@dataclass
class QCDAnalysis:
    """Qualified Charitable Distribution optimization."""
    year: int
    age: int
    rmd_amount: float
    qcd_amount: float
    qcd_limit: float
    agi_reduction: float
    tax_savings: float
    irmaa_impact: float
    ss_torpedo_reduction: float
    cash_donation_deduction: float
    qcd_advantage: float
    eligible: bool
    notes: List[str] = field(default_factory=list)


@dataclass
class SEPPCalculation:
    """72(t) Substantially Equal Periodic Payments calculation."""
    account_balance: float
    age: int
    method: str
    annual_payment: float
    monthly_payment: float
    years_required: int
    total_distributions: float
    estimated_annual_tax: float
    early_withdrawal_penalty_avoided: float
    notes: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


@dataclass
class MultiYearHarvestingPlan:
    """Multi-year capital loss harvesting plan."""
    years: List[int] = field(default_factory=list)
    harvest_amounts: Dict[int, float] = field(default_factory=dict)
    carryforward_by_year: Dict[int, float] = field(default_factory=dict)
    tax_savings_by_year: Dict[int, float] = field(default_factory=dict)
    total_tax_savings: float = 0.0
    notes: List[str] = field(default_factory=list)

# Made with Bob


# ===========================================================================
# MULTI-YEAR TAX PLANNING
# ===========================================================================

def project_single_year_tax(
    year: int,
    ordinary_income: float,
    capital_gains_lt: float = 0.0,
    capital_gains_st: float = 0.0,
    roth_conversion: float = 0.0,
    qbi_income: float = 0.0,
    charitable_contributions: float = 0.0,
    capital_loss_carryforward: float = 0.0,
    filing_status: str = "married_filing_jointly",
) -> YearlyTaxProjection:
    """
    Project taxes for a single year including all income sources.

    Handles capital loss netting, QBI deduction, and bracket headroom.

    Args:
        year: Tax year
        ordinary_income: Wages + IRA distributions + other ordinary income
        capital_gains_lt: Long-term capital gains
        capital_gains_st: Short-term capital gains (taxed as ordinary income)
        roth_conversion: Roth conversion amount (taxed as ordinary income)
        qbi_income: Qualified Business Income (for QBI deduction)
        charitable_contributions: Charitable contributions (for itemizing)
        capital_loss_carryforward: Capital loss carryforward from prior years
        filing_status: Filing status for bracket lookup

    Returns:
        YearlyTaxProjection with computed tax fields
    """
    proj = YearlyTaxProjection(
        year=year,
        ordinary_income=ordinary_income,
        capital_gains_lt=capital_gains_lt,
        capital_gains_st=capital_gains_st,
        roth_conversion=roth_conversion,
        qbi_income=qbi_income,
        charitable_contributions=charitable_contributions,
        capital_loss_carryforward=capital_loss_carryforward,
    )

    try:
        # get_income_tax_brackets / get_cap_gains_brackets return rows already
        # filtered to the requested year; calculate_taxable_income accepts the
        # full filtered DataFrame directly.  Cast to pd.DataFrame to satisfy
        # the type checker (the cached functions return DataFrame but pyright
        # infers a broader type from the cache decorator).
        tax_brackets: pd.DataFrame = pd.DataFrame(get_income_tax_brackets(year, filing_status))
        cg_brackets: pd.DataFrame = pd.DataFrame(get_cap_gains_brackets(year, filing_status))

        # standard.csv has columns: year, filing_status, deduction
        # get_std_deduction_by_year returns a plain float
        try:
            std_deduction = get_std_deduction_by_year(year)
        except (ValueError, KeyError):
            std_deduction = 30_000.0  # MFJ fallback

        # Capital loss netting: net losses offset gains first, then up to
        # $3,000 of ordinary income per year (IRC §1211(b))
        net_cg = capital_gains_lt + capital_gains_st - capital_loss_carryforward
        if net_cg < 0:
            ordinary_income_offset = min(abs(net_cg), 3_000.0)
            proj.net_capital_loss_used = ordinary_income_offset
            net_cg_for_tax = 0.0
            ordinary_income_after_loss = max(0.0, ordinary_income - ordinary_income_offset)
            proj.notes.append(
                f"Capital loss carryforward of ${capital_loss_carryforward:,.0f} offsets "
                f"${ordinary_income_offset:,.0f} of ordinary income."
            )
        else:
            net_cg_for_tax = net_cg
            ordinary_income_after_loss = ordinary_income

        # QBI deduction (IRC §199A)
        qbi_ded = _calculate_qbi_deduction(
            qbi_income=qbi_income,
            total_income=ordinary_income_after_loss + roth_conversion + capital_gains_st,
            filing_status=filing_status,
        )
        proj.qbi_deduction = qbi_ded

        # Total ordinary income for bracket purposes
        total_ordinary = (
            ordinary_income_after_loss
            + capital_gains_st
            + roth_conversion
            - qbi_ded
        )

        # AGI (before standard deduction)
        agi = total_ordinary + max(0.0, net_cg_for_tax)
        proj.agi = agi

        # Taxable income after standard deduction
        taxable_ordinary = max(0.0, total_ordinary - std_deduction)

        # Federal income tax on ordinary income using progressive brackets
        # calculate_taxable_income returns TaxCalculation named tuple
        result = calculate_taxable_income(taxable_ordinary, tax_brackets)
        federal_tax = result.total_tax
        proj.marginal_rate = float(result.max_rate)
        proj.bracket_headroom = max(0.0, float(result.upper_max) - taxable_ordinary)

        # Capital gains tax: ordinary income fills lower brackets first
        cg_tax = 0.0
        if net_cg_for_tax > 0 and not cg_brackets.empty:
            total_income_for_cg = taxable_ordinary + net_cg_for_tax
            matched = False
            for _, row in cg_brackets.iterrows():
                if float(row["lower"]) <= total_income_for_cg <= float(row["upper"]):
                    cg_tax = net_cg_for_tax * float(row["rate"])
                    matched = True
                    break
            if not matched:
                cg_tax = net_cg_for_tax * 0.20  # top LTCG rate fallback

        proj.federal_tax = federal_tax + cg_tax
        proj.effective_rate = proj.federal_tax / agi if agi > 0 else 0.0

    except Exception as e:
        logger.warning(f"Tax projection failed for year {year}: {e}")
        proj.notes.append(f"Projection error: {e}")

    return proj


def build_rolling_tax_window(
    start_year: int,
    income_by_year: Dict[int, float],
    cg_lt_by_year: Optional[Dict[int, float]] = None,
    cg_st_by_year: Optional[Dict[int, float]] = None,
    conversion_by_year: Optional[Dict[int, float]] = None,
    qbi_by_year: Optional[Dict[int, float]] = None,
    loss_carryforward: float = 0.0,
    filing_status: str = "married_filing_jointly",
    window: int = 5,
) -> RollingTaxWindow:
    """
    Build a rolling tax optimization window.

    Projects taxes for each year in the window, identifies bracket headroom,
    and recommends optimal Roth conversion and harvesting amounts.

    Args:
        start_year: First year of the window
        income_by_year: Ordinary income for each year {year: amount}
        cg_lt_by_year: Long-term capital gains by year (optional)
        cg_st_by_year: Short-term capital gains by year (optional)
        conversion_by_year: Planned Roth conversions by year (optional)
        qbi_by_year: QBI income by year (optional)
        loss_carryforward: Starting capital loss carryforward
        filing_status: Filing status
        window: Number of years in the rolling window (default 5)

    Returns:
        RollingTaxWindow with projections and optimization recommendations
    """
    result = RollingTaxWindow()
    remaining_loss_cf = loss_carryforward

    for i in range(window):
        yr = start_year + i
        income = income_by_year.get(yr, income_by_year.get(start_year, 0.0))
        cg_lt = (cg_lt_by_year or {}).get(yr, 0.0)
        cg_st = (cg_st_by_year or {}).get(yr, 0.0)
        conv = (conversion_by_year or {}).get(yr, 0.0)
        qbi = (qbi_by_year or {}).get(yr, 0.0)

        proj = project_single_year_tax(
            year=yr,
            ordinary_income=income,
            capital_gains_lt=cg_lt,
            capital_gains_st=cg_st,
            roth_conversion=conv,
            qbi_income=qbi,
            capital_loss_carryforward=remaining_loss_cf,
            filing_status=filing_status,
        )
        result.years.append(proj)

        # Roll forward unused capital loss
        net_cg = cg_lt + cg_st - remaining_loss_cf
        if net_cg < 0:
            remaining_loss_cf = abs(net_cg) - proj.net_capital_loss_used
        else:
            remaining_loss_cf = 0.0

    # Aggregate metrics
    result.total_tax_5yr = sum(p.federal_tax for p in result.years)
    result.avg_effective_rate = (
        sum(p.effective_rate for p in result.years) / len(result.years)
        if result.years else 0.0
    )
    result.total_bracket_headroom = sum(p.bracket_headroom for p in result.years)

    _identify_optimization_opportunities(result)
    return result


def _identify_optimization_opportunities(window: RollingTaxWindow) -> None:
    """Populate optimization_opportunities, recommended_conversions, and recommended_harvesting."""
    for proj in window.years:
        if proj.bracket_headroom > 5_000:
            window.optimization_opportunities.append(
                f"📈 {proj.year}: ${proj.bracket_headroom:,.0f} headroom in "
                f"{proj.marginal_rate:.0%} bracket — consider Roth conversion."
            )
            window.recommended_conversions[proj.year] = proj.bracket_headroom

        if proj.effective_rate < 0.15 and proj.agi > 0:
            window.optimization_opportunities.append(
                f"🌾 {proj.year}: Effective rate {proj.effective_rate:.1%} — "
                f"consider harvesting long-term gains at 0% LTCG rate."
            )
            window.recommended_harvesting[proj.year] = proj.bracket_headroom

        if proj.qbi_deduction > 0:
            window.optimization_opportunities.append(
                f"🏢 {proj.year}: QBI deduction of ${proj.qbi_deduction:,.0f} available."
            )

        if proj.capital_loss_carryforward > 0:
            window.optimization_opportunities.append(
                f"📉 {proj.year}: ${proj.capital_loss_carryforward:,.0f} capital loss "
                f"carryforward — use to offset gains."
            )


# ===========================================================================
# QBI DEDUCTION
# ===========================================================================

def _calculate_qbi_deduction(
    qbi_income: float,
    total_income: float,
    filing_status: str = "married_filing_jointly",
    w2_wages: float = 0.0,
    ubia_qualified_property: float = 0.0,
    is_sstb: bool = False,
) -> float:
    """Internal QBI deduction helper (no breakdown)."""
    if qbi_income <= 0:
        return 0.0

    if filing_status == "married_filing_jointly":
        ps, pe = QBI_PHASE_OUT_MFJ_START, QBI_PHASE_OUT_MFJ_END
    else:
        ps, pe = QBI_PHASE_OUT_SINGLE_START, QBI_PHASE_OUT_SINGLE_END

    base = qbi_income * QBI_DEDUCTION_RATE

    if total_income <= ps:
        return min(base, total_income * QBI_DEDUCTION_RATE)

    if is_sstb and total_income >= pe:
        return 0.0

    if w2_wages > 0 or ubia_qualified_property > 0:
        w2_limit = max(
            w2_wages * QBI_W2_LIMIT_RATE,
            w2_wages * QBI_W2_UBIA_RATE + ubia_qualified_property * 0.025,
        )
        phase_ratio = min(1.0, (total_income - ps) / (pe - ps))
        return max(0.0, base - phase_ratio * max(0.0, base - w2_limit))

    if total_income >= pe:
        return 0.0
    phase_ratio = (total_income - ps) / (pe - ps)
    return max(0.0, base * (1 - phase_ratio))


def calculate_qbi_deduction_full(
    qbi_income: float,
    total_taxable_income: float,
    w2_wages: float = 0.0,
    ubia_qualified_property: float = 0.0,
    is_sstb: bool = False,
    filing_status: str = "married_filing_jointly",
) -> Dict:
    """
    Full QBI deduction calculation (IRC §199A) with detailed breakdown.

    Args:
        qbi_income: Qualified business income from pass-through entity
        total_taxable_income: Total taxable income (for phase-out)
        w2_wages: W-2 wages paid by the business
        ubia_qualified_property: Unadjusted basis of qualified property
        is_sstb: Whether the business is a Specified Service Trade or Business
        filing_status: Filing status

    Returns:
        Dict with keys: deduction, base_deduction, w2_limit, phase_out_pct, notes
    """
    notes: List[str] = []

    if qbi_income <= 0:
        return {"deduction": 0.0, "base_deduction": 0.0, "w2_limit": 0.0,
                "phase_out_pct": 0.0, "notes": ["No QBI income — deduction is $0."]}

    base = qbi_income * QBI_DEDUCTION_RATE
    notes.append(f"Base QBI deduction: ${qbi_income:,.0f} × 20% = ${base:,.0f}")

    if filing_status == "married_filing_jointly":
        ps, pe = QBI_PHASE_OUT_MFJ_START, QBI_PHASE_OUT_MFJ_END
    else:
        ps, pe = QBI_PHASE_OUT_SINGLE_START, QBI_PHASE_OUT_SINGLE_END

    if total_taxable_income <= ps:
        notes.append(
            f"Income ${total_taxable_income:,.0f} is below phase-out threshold "
            f"${ps:,.0f} — full deduction."
        )
        return {"deduction": base, "base_deduction": base, "w2_limit": 0.0,
                "phase_out_pct": 0.0, "notes": notes}

    if is_sstb and total_taxable_income >= pe:
        notes.append(f"SSTB fully phased out above ${pe:,.0f}.")
        return {"deduction": 0.0, "base_deduction": base, "w2_limit": 0.0,
                "phase_out_pct": 1.0, "notes": notes}

    phase_ratio = min(1.0, (total_taxable_income - ps) / (pe - ps))
    notes.append(f"Phase-out: {phase_ratio:.1%} through the phase-out range.")

    w2_limit = 0.0
    if w2_wages > 0 or ubia_qualified_property > 0:
        w2_limit = max(
            w2_wages * QBI_W2_LIMIT_RATE,
            w2_wages * QBI_W2_UBIA_RATE + ubia_qualified_property * 0.025,
        )
        notes.append(f"W-2 wage limitation: ${w2_limit:,.0f}")
        limited = base - phase_ratio * max(0.0, base - w2_limit)
        deduction = max(0.0, limited)
    else:
        notes.append("No W-2 wages — deduction phases out linearly.")
        deduction = max(0.0, base * (1 - phase_ratio)) if not is_sstb else 0.0

    notes.append(f"Final QBI deduction: ${deduction:,.0f}")
    return {"deduction": deduction, "base_deduction": base, "w2_limit": w2_limit,
            "phase_out_pct": phase_ratio, "notes": notes}


# ===========================================================================
# BACKDOOR ROTH IRA
# ===========================================================================

def calculate_backdoor_roth(
    year: int,
    age: int,
    magi: float,
    traditional_ira_balance: float,
    after_tax_ira_basis: float = 0.0,
    contribution_amount: Optional[float] = None,
    filing_status: str = "married_filing_jointly",
) -> BackdoorRothResult:
    """
    Calculate backdoor Roth IRA contribution and conversion.

    The backdoor Roth strategy:
    1. Make a non-deductible contribution to a Traditional IRA
    2. Immediately convert the Traditional IRA to Roth
    3. Pro-rata rule applies if you have other pre-tax IRA balances

    Args:
        year: Tax year
        age: Taxpayer age
        magi: Modified Adjusted Gross Income
        traditional_ira_balance: Pre-tax Traditional IRA balance (triggers pro-rata)
        after_tax_ira_basis: Existing after-tax (non-deductible) basis in Traditional IRA
        contribution_amount: Contribution amount (None = use annual limit)
        filing_status: Filing status

    Returns:
        BackdoorRothResult with eligibility, tax impact, and steps
    """
    # Get IRA limits from lookup table
    try:
        limits_df = get_ira_limits(year)
        if limits_df.empty:
            # Fallback to constants if year not found
            logger.warning(f"IRA limits not found for year {year}, using default constants")
            ira_base = IRA_CONTRIBUTION_LIMIT_BASE
            ira_catchup = IRA_CATCH_UP_CONTRIBUTION
            roth_phase_out_start = 236_000 if filing_status == "married_filing_jointly" else 150_000
        else:
            ira_base = int(limits_df.iloc[0]['ira_contribution_base'])
            ira_catchup = int(limits_df.iloc[0]['ira_catchup_50plus'])
            if filing_status == "married_filing_jointly":
                roth_phase_out_start = int(limits_df.iloc[0]['roth_phaseout_start_mfj'])
            else:
                roth_phase_out_start = int(limits_df.iloc[0]['roth_phaseout_start_single'])
    except Exception as e:
        logger.error(f"Error loading IRA limits for year {year}: {e}")
        # Fallback to constants
        ira_base = IRA_CONTRIBUTION_LIMIT_BASE
        ira_catchup = IRA_CATCH_UP_CONTRIBUTION
        roth_phase_out_start = 236_000 if filing_status == "married_filing_jointly" else 150_000
    
    catch_up = ira_catchup if age >= 50 else 0
    annual_limit = ira_base + catch_up
    contrib = min(
        contribution_amount if contribution_amount is not None else float(annual_limit),
        float(annual_limit),
    )

    result = BackdoorRothResult(
        year=year,
        contribution_amount=contrib,
        conversion_amount=contrib,
        pro_rata_tax=0.0,
        net_benefit=0.0,
        eligible=True,
    )

    # Check if direct Roth contribution is available (no backdoor needed)

    if magi <= roth_phase_out_start:
        result.eligible = False
        result.ineligible_reason = (
            f"MAGI ${magi:,.0f} is below the Roth phase-out threshold "
            f"${roth_phase_out_start:,.0f}. "
            "You can contribute directly to a Roth IRA — backdoor strategy not needed."
        )
        result.steps.append(
            "✅ Direct Roth IRA contribution is available — no backdoor needed."
        )
        return result

    result.steps.append(
        f"Step 1: Make a non-deductible Traditional IRA contribution of ${contrib:,.0f} "
        f"(annual limit: ${annual_limit:,.0f})."
    )
    result.steps.append(
        "Step 2: File IRS Form 8606 to record the non-deductible contribution as "
        "after-tax basis."
    )

    # Pro-rata rule: if pre-tax IRA balances exist, a portion of the conversion is taxable
    total_ira_balance = traditional_ira_balance + after_tax_ira_basis + contrib
    if traditional_ira_balance > 0:
        taxable_pct = traditional_ira_balance / total_ira_balance
        taxable_amount = contrib * taxable_pct
        estimated_tax_rate = 0.22
        result.pro_rata_tax = taxable_amount * estimated_tax_rate
        result.warnings.append(
            f"⚠️ Pro-Rata Rule: You have ${traditional_ira_balance:,.0f} in pre-tax IRA "
            f"balances. {taxable_pct:.1%} of your conversion (${taxable_amount:,.0f}) will "
            f"be taxable. Estimated tax: ${result.pro_rata_tax:,.0f}. "
            "Consider rolling pre-tax IRA into a 401(k) to eliminate pro-rata exposure."
        )
        result.steps.append(
            f"Step 3: Convert ${contrib:,.0f} to Roth IRA. "
            f"⚠️ Pro-rata rule applies — ${taxable_amount:,.0f} is taxable."
        )
    else:
        result.steps.append(
            f"Step 3: Convert ${contrib:,.0f} to Roth IRA immediately. "
            "No pre-tax IRA balance — conversion is 100% tax-free."
        )

    result.steps.append(
        "Step 4: File IRS Form 8606 Part II to report the Roth conversion."
    )
    result.steps.append(
        "Step 5: Ensure the conversion is complete before December 31 of the tax year."
    )

    future_value = contrib * (1.07 ** 20)
    result.net_benefit = future_value - result.pro_rata_tax
    result.conversion_amount = contrib
    return result


# ===========================================================================
# MEGA BACKDOOR ROTH
# ===========================================================================

def calculate_mega_backdoor_roth(
    year: int,
    age: int,
    employee_elective_deferral: float,
    employer_match: float,
    plan_allows_after_tax: bool = True,
    plan_allows_in_plan_conversion: bool = True,
) -> MegaBackdoorRothResult:
    """
    Calculate mega backdoor Roth strategy via 401(k) after-tax contributions.

    The mega backdoor Roth strategy:
    1. Max out employee elective deferrals (pre-tax or Roth)
    2. Make additional after-tax contributions up to the 415(c) limit
    3. Convert after-tax contributions to Roth (in-plan or rollover to Roth IRA)

    Args:
        year: Tax year
        age: Taxpayer age
        employee_elective_deferral: Employee elective deferral amount
        employer_match: Employer matching contribution
        plan_allows_after_tax: Whether the plan allows after-tax contributions
        plan_allows_in_plan_conversion: Whether the plan allows in-plan Roth conversion

    Returns:
        MegaBackdoorRothResult with eligibility and amounts
    """
    result = MegaBackdoorRothResult(
        year=year,
        after_tax_contribution=0.0,
        in_plan_conversion=0.0,
        rollover_to_roth_ira=0.0,
        tax_on_earnings=0.0,
        net_benefit=0.0,
        eligible=True,
    )

    if not plan_allows_after_tax:
        result.eligible = False
        result.ineligible_reason = (
            "Your 401(k) plan does not allow after-tax contributions. "
            "Contact your plan administrator to confirm plan features."
        )
        return result

    # Get 401(k) limits from lookup table
    try:
        limits_df = get_ira_limits(year)
        if limits_df.empty:
            logger.warning(f"401(k) limits not found for year {year}, using default constants")
            k401_total = K401_TOTAL_LIMIT
            k401_catchup_50 = K401_CATCH_UP_50
            k401_catchup_60_63 = K401_CATCH_UP_60_63
        else:
            k401_total = int(limits_df.iloc[0]['k401_total_limit'])
            k401_catchup_50 = int(limits_df.iloc[0]['k401_catchup_50'])
            k401_catchup_60_63 = int(limits_df.iloc[0]['k401_catchup_60_63'])
    except Exception as e:
        logger.error(f"Error loading 401(k) limits for year {year}: {e}")
        k401_total = K401_TOTAL_LIMIT
        k401_catchup_50 = K401_CATCH_UP_50
        k401_catchup_60_63 = K401_CATCH_UP_60_63
    
    # Age-based catch-up: SECURE 2.0 special catch-up for ages 60-63
    catch_up = k401_catchup_60_63 if 60 <= age <= 63 else (k401_catchup_50 if age >= 50 else 0)
    total_limit = k401_total + catch_up

    after_tax_room = max(0.0, total_limit - employee_elective_deferral - employer_match)
    result.after_tax_contribution = after_tax_room

    if after_tax_room <= 0:
        result.eligible = False
        result.ineligible_reason = (
            f"No room for after-tax contributions: "
            f"Employee deferral (${employee_elective_deferral:,.0f}) + "
            f"Employer match (${employer_match:,.0f}) = "
            f"${employee_elective_deferral + employer_match:,.0f} "
            f"already at or above the ${total_limit:,.0f} 415(c) limit."
        )
        return result

    result.steps.append(
        f"Step 1: Confirm your 401(k) plan allows after-tax contributions and "
        f"{'in-plan Roth conversions' if plan_allows_in_plan_conversion else 'in-service withdrawals'}."
    )
    result.steps.append(
        f"Step 2: Contribute ${after_tax_room:,.0f} in after-tax (non-Roth) contributions "
        f"to your 401(k). This fills the remaining room under the ${total_limit:,.0f} 415(c) limit."
    )

    if plan_allows_in_plan_conversion:
        result.in_plan_conversion = after_tax_room
        result.steps.append(
            f"Step 3: Immediately convert the ${after_tax_room:,.0f} after-tax balance "
            "to Roth within the plan (in-plan Roth conversion). "
            "Converting immediately minimizes taxable earnings."
        )
    else:
        result.rollover_to_roth_ira = after_tax_room
        result.steps.append(
            f"Step 3: Request an in-service withdrawal of the ${after_tax_room:,.0f} "
            "after-tax balance and roll it over to a Roth IRA within 60 days."
        )
        result.steps.append(
            "Step 4: Roll the basis to Roth IRA and any earnings to a Traditional IRA."
        )

    result.steps.append("Step 5: File IRS Form 8606 to track the after-tax basis.")
    result.net_benefit = after_tax_room * (1.07 ** 20) - after_tax_room
    return result


# ===========================================================================
# NET UNREALIZED APPRECIATION (NUA)
# ===========================================================================

def calculate_nua_analysis(
    ticker: str,
    shares: float,
    cost_basis_per_share: float,
    current_price_per_share: float,
    ordinary_income_tax_rate: float,
    ltcg_tax_rate: float,
    future_tax_rate: float = 0.24,
    years_to_sale: int = 10,
) -> NUAAnalysis:
    """
    Analyze Net Unrealized Appreciation (NUA) strategy for company stock in a 401(k).

    NUA strategy: Instead of rolling company stock to an IRA, take a lump-sum
    distribution. Pay ordinary income tax only on the cost basis; the NUA
    (appreciation) is taxed at the lower long-term capital gains rate when sold.

    Args:
        ticker: Stock ticker symbol
        shares: Number of shares of company stock in the plan
        cost_basis_per_share: Cost basis per share (what the plan paid)
        current_price_per_share: Current market price per share
        ordinary_income_tax_rate: Ordinary income tax rate (for basis taxation)
        ltcg_tax_rate: Long-term capital gains rate (for NUA taxation)
        future_tax_rate: Expected future ordinary income tax rate (for IRA comparison)
        years_to_sale: Years until stock is sold (for IRA comparison growth)

    Returns:
        NUAAnalysis with tax comparison and recommendation
    """
    total_cost_basis = shares * cost_basis_per_share
    current_value = shares * current_price_per_share
    nua_amount = current_value - total_cost_basis
    nua_pct = nua_amount / total_cost_basis if total_cost_basis > 0 else 0.0

    ordinary_income_tax_on_basis = total_cost_basis * ordinary_income_tax_rate
    ltcg_tax_on_nua = nua_amount * ltcg_tax_rate
    total_nua_tax = ordinary_income_tax_on_basis + ltcg_tax_on_nua

    # Alternative: roll to IRA, grow, withdraw later at ordinary income rates
    future_value_in_ira = current_value * (1.05 ** years_to_sale)
    tax_if_distributed_as_cash = future_value_in_ira * future_tax_rate

    tax_savings = tax_if_distributed_as_cash - total_nua_tax

    notes: List[str] = []
    notes.append(
        f"Cost basis: ${total_cost_basis:,.0f} taxed at {ordinary_income_tax_rate:.0%} "
        f"ordinary income rate = ${ordinary_income_tax_on_basis:,.0f}"
    )
    notes.append(
        f"NUA of ${nua_amount:,.0f} taxed at {ltcg_tax_rate:.0%} LTCG rate "
        f"= ${ltcg_tax_on_nua:,.0f}"
    )
    notes.append(
        f"Total NUA strategy tax: ${total_nua_tax:,.0f} vs. "
        f"IRA rollover estimated tax: ${tax_if_distributed_as_cash:,.0f}"
    )

    strategy_recommended = nua_pct >= NUA_MINIMUM_GAIN_PCT and tax_savings > 0

    if strategy_recommended:
        notes.append(
            f"✅ NUA strategy recommended: saves approximately ${tax_savings:,.0f} in taxes."
        )
    else:
        if nua_pct < NUA_MINIMUM_GAIN_PCT:
            notes.append(
                f"⚠️ NUA gain ({nua_pct:.1%}) is below the {NUA_MINIMUM_GAIN_PCT:.0%} "
                "threshold. IRA rollover may be preferable."
            )
        else:
            notes.append("⚠️ NUA strategy does not provide tax savings in this scenario.")

    notes.append(
        "⚠️ NUA requires a qualifying lump-sum distribution (triggering event: "
        "separation from service, age 59½, death, or disability)."
    )
    notes.append(
        "⚠️ The 10% early withdrawal penalty applies to the cost basis if under age 59½."
    )

    return NUAAnalysis(
        ticker=ticker,
        shares=shares,
        cost_basis_per_share=cost_basis_per_share,
        current_price_per_share=current_price_per_share,
        total_cost_basis=total_cost_basis,
        current_value=current_value,
        nua_amount=nua_amount,
        nua_pct=nua_pct,
        ordinary_income_tax_on_basis=ordinary_income_tax_on_basis,
        ltcg_tax_on_nua=ltcg_tax_on_nua,
        total_nua_tax=total_nua_tax,
        tax_if_distributed_as_cash=tax_if_distributed_as_cash,
        tax_savings=tax_savings,
        strategy_recommended=strategy_recommended,
        notes=notes,
    )


# ===========================================================================
# QUALIFIED CHARITABLE DISTRIBUTIONS (QCD)
# ===========================================================================

def calculate_qcd_optimization(
    year: int,
    age: int,
    rmd_amount: float,
    ira_balance: float,
    planned_charitable_giving: float,
    agi_before_rmd: float,
    marginal_tax_rate: float,
    filing_status: str = "married_filing_jointly",
    irmaa_magi_threshold: float = 206_000.0,
    ss_benefits: float = 0.0,
) -> QCDAnalysis:
    """
    Optimize Qualified Charitable Distributions (QCD) from IRA.

    QCDs allow taxpayers age 70½+ to donate up to $105,000/year directly
    from an IRA to a qualified charity. The distribution counts toward the
    RMD but is excluded from AGI.

    Args:
        year: Tax year
        age: Taxpayer age
        rmd_amount: Required Minimum Distribution for the year
        ira_balance: IRA balance
        planned_charitable_giving: Annual charitable giving amount
        agi_before_rmd: AGI before RMD is included
        marginal_tax_rate: Marginal federal income tax rate
        filing_status: Filing status
        irmaa_magi_threshold: IRMAA threshold (to check if QCD avoids surcharge)
        ss_benefits: Annual Social Security benefits (for SS torpedo calculation)

    Returns:
        QCDAnalysis with tax savings and recommendation
    """
    result = QCDAnalysis(
        year=year,
        age=age,
        rmd_amount=rmd_amount,
        qcd_amount=0.0,
        qcd_limit=float(QCD_ANNUAL_LIMIT),
        agi_reduction=0.0,
        tax_savings=0.0,
        irmaa_impact=0.0,
        ss_torpedo_reduction=0.0,
        cash_donation_deduction=0.0,
        qcd_advantage=0.0,
        eligible=False,
        notes=[],
    )

    if age < QCD_ELIGIBLE_AGE:
        result.eligible = False
        result.notes.append(
            f"QCD requires age {QCD_ELIGIBLE_AGE}+. Current age: {age}. "
            f"Eligible in {QCD_ELIGIBLE_AGE - age} year(s)."
        )
        return result

    result.eligible = True

    # QCD amount: lesser of planned giving, RMD, and annual limit
    qcd_amount = min(planned_charitable_giving, rmd_amount, float(QCD_ANNUAL_LIMIT))
    result.qcd_amount = qcd_amount

    # AGI reduction: QCD reduces AGI by the full amount (vs. cash donation which only
    # reduces taxable income if itemizing above standard deduction)
    result.agi_reduction = qcd_amount

    # Direct tax savings from AGI reduction
    result.tax_savings = qcd_amount * marginal_tax_rate

    # IRMAA impact: check if QCD keeps MAGI below IRMAA threshold
    agi_with_rmd = agi_before_rmd + rmd_amount
    agi_with_qcd = agi_before_rmd + (rmd_amount - qcd_amount)
    if agi_with_rmd > irmaa_magi_threshold >= agi_with_qcd:
        result.irmaa_impact = 2_000.0  # Approximate IRMAA surcharge avoided (per person)
        result.notes.append(
            f"✅ QCD keeps MAGI (${agi_with_qcd:,.0f}) below IRMAA threshold "
            f"(${irmaa_magi_threshold:,.0f}), potentially saving ~$2,000+ in Medicare surcharges."
        )

    # Social Security torpedo: QCD reduces AGI, which reduces taxable SS benefits
    # Up to 85% of SS benefits are taxable; each $1 of AGI reduction saves ~$0.85 × marginal rate
    if ss_benefits > 0:
        ss_torpedo_reduction = qcd_amount * 0.85 * marginal_tax_rate
        result.ss_torpedo_reduction = ss_torpedo_reduction
        result.notes.append(
            f"SS torpedo reduction: ${ss_torpedo_reduction:,.0f} in additional tax savings "
            f"from reduced taxable Social Security benefits."
        )

    # Cash donation comparison: cash donation only saves taxes if itemizing
    std_ded = 30_000.0 if filing_status == "married_filing_jointly" else 15_000.0
    if agi_with_rmd - qcd_amount > std_ded:
        result.cash_donation_deduction = qcd_amount * marginal_tax_rate
    else:
        result.cash_donation_deduction = 0.0
        result.notes.append(
            "Cash donation would not provide additional tax benefit "
            "(below standard deduction threshold)."
        )

    # QCD advantage over cash donation
    result.qcd_advantage = (
        result.tax_savings
        - result.cash_donation_deduction
        + result.irmaa_impact
        + result.ss_torpedo_reduction
    )

    result.notes.append(
        f"QCD of ${qcd_amount:,.0f} reduces AGI from ${agi_with_rmd:,.0f} "
        f"to ${agi_with_qcd:,.0f}."
    )
    result.notes.append(
        f"Direct tax savings: ${result.tax_savings:,.0f} at "
        f"{marginal_tax_rate:.0%} marginal rate."
    )
    result.notes.append(
        f"Total QCD advantage over cash donation: ${result.qcd_advantage:,.0f}."
    )

    return result


# ===========================================================================
# 72(t) SEPP CALCULATIONS
# ===========================================================================

def calculate_sepp(
    account_balance: float,
    age: int,
    method: str = "Fixed Amortization",
    afr: float = _SEPP_DEFAULT_AFR,
    marginal_tax_rate: float = 0.22,
) -> SEPPCalculation:
    """
    Calculate 72(t) Substantially Equal Periodic Payments (SEPP).

    SEPP allows penalty-free withdrawals from an IRA before age 59½ under
    IRC §72(t)(2)(A)(iv). Payments must continue for the longer of 5 years
    or until age 59½.

    Three IRS-approved methods:
    1. Required Minimum Distribution (RMD): Variable annual payment
    2. Fixed Amortization: Fixed annual payment (typically highest amount)
    3. Fixed Annuitization: Fixed annual payment using IRS annuity factor

    Args:
        account_balance: IRA account balance at start of SEPP
        age: Taxpayer age at start of SEPP
        method: SEPP calculation method (see SEPP_METHODS)
        afr: Applicable Federal Rate (120% of mid-term AFR, max 5% per IRS Notice 2022-6)
        marginal_tax_rate: Marginal tax rate for estimating annual tax

    Returns:
        SEPPCalculation with annual payment, duration, and tax impact
    """
    result = SEPPCalculation(
        account_balance=account_balance,
        age=age,
        method=method,
        annual_payment=0.0,
        monthly_payment=0.0,
        years_required=0,
        total_distributions=0.0,
        estimated_annual_tax=0.0,
        early_withdrawal_penalty_avoided=0.0,
    )

    if age >= EARLY_WITHDRAWAL_PENALTY_AGE:
        result.warnings.append(
            f"Age {age} is at or above {EARLY_WITHDRAWAL_PENALTY_AGE}. "
            "SEPP is not needed — you can withdraw penalty-free."
        )
        return result

    # Duration: longer of 5 years or until age 59½
    years_to_59_5 = math.ceil(EARLY_WITHDRAWAL_PENALTY_AGE - age)
    years_required = max(5, years_to_59_5)
    result.years_required = years_required

    annual_payment = 0.0

    if method == "Required Minimum Distribution (RMD)":
        # RMD method: account_balance / life_expectancy_factor
        # Use IRS Single Life Expectancy table (simplified)
        life_expectancy = _get_life_expectancy(age)
        annual_payment = account_balance / life_expectancy
        result.notes.append(
            f"RMD method: ${account_balance:,.0f} ÷ {life_expectancy:.1f} "
            f"(life expectancy factor) = ${annual_payment:,.0f}/year."
        )
        result.notes.append(
            "⚠️ RMD method produces a variable payment that changes each year "
            "as the account balance changes. This is the lowest of the three methods."
        )

    elif method == "Fixed Amortization":
        # Fixed Amortization: amortize balance over life expectancy at the AFR
        life_expectancy = _get_life_expectancy(age)
        if afr > 0:
            # Present value annuity factor: (1 - (1+r)^-n) / r
            n = life_expectancy
            r = afr
            annuity_factor = (1 - (1 + r) ** (-n)) / r
            annual_payment = account_balance / annuity_factor
        else:
            annual_payment = account_balance / life_expectancy
        result.notes.append(
            f"Fixed Amortization: ${account_balance:,.0f} amortized over "
            f"{life_expectancy:.1f} years at {afr:.2%} AFR = ${annual_payment:,.0f}/year."
        )
        result.notes.append(
            "Fixed Amortization typically produces the highest annual payment of the three methods."
        )

    elif method == "Fixed Annuitization":
        # Fixed Annuitization: account_balance / annuity_factor from IRS table
        annuity_factor = _get_sepp_annuity_factor(age)
        if annuity_factor > 0:
            annual_payment = account_balance / annuity_factor
        else:
            annual_payment = 0.0
        result.notes.append(
            f"Fixed Annuitization: ${account_balance:,.0f} ÷ {annuity_factor:.1f} "
            f"(IRS annuity factor for age {age}) = ${annual_payment:,.0f}/year."
        )

    else:
        result.warnings.append(
            f"Unknown SEPP method: '{method}'. "
            f"Valid methods: {', '.join(SEPP_METHODS)}"
        )
        return result

    result.annual_payment = annual_payment
    result.monthly_payment = annual_payment / 12.0
    result.total_distributions = annual_payment * years_required
    result.estimated_annual_tax = annual_payment * marginal_tax_rate
    result.early_withdrawal_penalty_avoided = annual_payment * years_required * EARLY_WITHDRAWAL_PENALTY_RATE

    result.notes.append(
        f"SEPP must continue for {years_required} years "
        f"(longer of 5 years or until age 59½)."
    )
    result.notes.append(
        f"Total distributions over {years_required} years: "
        f"${result.total_distributions:,.0f}."
    )
    result.notes.append(
        f"Early withdrawal penalty avoided: "
        f"${result.early_withdrawal_penalty_avoided:,.0f}."
    )
    result.warnings.append(
        "⚠️ Modifying or stopping SEPP before the required period ends triggers "
        "the 10% penalty PLUS interest on ALL prior distributions."
    )
    result.warnings.append(
        "⚠️ Consult a tax professional before starting a SEPP program. "
        "IRS Notice 2022-6 governs current SEPP rules."
    )

    return result


def _get_life_expectancy(age: int) -> float:
    """
    Get IRS Single Life Expectancy factor for SEPP calculations.
    Simplified table based on IRS Publication 590-B.
    """
    # IRS Single Life Expectancy Table (Appendix B, Pub 590-B)
    table = {
        40: 43.6, 45: 38.8, 50: 34.2, 51: 33.3, 52: 32.3, 53: 31.4, 54: 30.5,
        55: 29.6, 56: 28.7, 57: 27.9, 58: 27.0, 59: 26.1, 60: 25.2, 61: 24.4,
        62: 23.5, 63: 22.7, 64: 21.8, 65: 21.0, 66: 20.2, 67: 19.4, 68: 18.6,
        69: 17.8, 70: 17.0,
    }
    # Interpolate for ages not in table
    if age in table:
        return table[age]
    ages = sorted(table.keys())
    if age < ages[0]:
        return table[ages[0]] + (ages[0] - age) * 1.0
    if age > ages[-1]:
        return max(1.0, table[ages[-1]] - (age - ages[-1]) * 0.8)
    # Linear interpolation
    for i in range(len(ages) - 1):
        if ages[i] <= age <= ages[i + 1]:
            t = (age - ages[i]) / (ages[i + 1] - ages[i])
            return table[ages[i]] + t * (table[ages[i + 1]] - table[ages[i]])
    return 20.0


def _get_sepp_annuity_factor(age: int) -> float:
    """Get IRS annuity factor for Fixed Annuitization SEPP method."""
    if age in _SEPP_ANNUITY_FACTORS:
        return _SEPP_ANNUITY_FACTORS[age]
    ages = sorted(_SEPP_ANNUITY_FACTORS.keys())
    if age < ages[0]:
        return _SEPP_ANNUITY_FACTORS[ages[0]] + (ages[0] - age) * 0.5
    if age > ages[-1]:
        return max(1.0, _SEPP_ANNUITY_FACTORS[ages[-1]] - (age - ages[-1]) * 0.5)
    for i in range(len(ages) - 1):
        if ages[i] <= age <= ages[i + 1]:
            t = (age - ages[i]) / (ages[i + 1] - ages[i])
            return (
                _SEPP_ANNUITY_FACTORS[ages[i]]
                + t * (_SEPP_ANNUITY_FACTORS[ages[i + 1]] - _SEPP_ANNUITY_FACTORS[ages[i]])
            )
    return 15.0


# ===========================================================================
# MULTI-YEAR CAPITAL LOSS HARVESTING PLAN
# ===========================================================================

def build_multi_year_loss_harvesting_plan(
    start_year: int,
    portfolio_positions: List[Dict],
    income_by_year: Dict[int, float],
    filing_status: str = "married_filing_jointly",
    window: int = 5,
) -> MultiYearHarvestingPlan:
    """
    Build a multi-year capital loss harvesting plan.

    Identifies positions with unrealized losses, plans harvesting across years
    to maximize tax benefit, and tracks carryforward balances.

    Args:
        start_year: First year of the plan
        portfolio_positions: List of dicts with keys:
            ticker, shares, cost_basis, current_price, holding_period_days
        income_by_year: Ordinary income by year (for bracket context)
        filing_status: Filing status
        window: Number of years to plan (default 5)

    Returns:
        MultiYearHarvestingPlan with harvest schedule and tax savings
    """
    plan = MultiYearHarvestingPlan()
    plan.years = list(range(start_year, start_year + window))

    # Identify positions with unrealized losses
    loss_positions = []
    for pos in portfolio_positions:
        cost = float(pos.get("cost_basis", 0.0))
        price = float(pos.get("current_price", 0.0))
        shares = float(pos.get("shares", 0.0))
        unrealized = (price - cost) * shares
        if unrealized < 0:
            loss_positions.append({
                **pos,
                "unrealized_loss": abs(unrealized),
                "is_long_term": int(pos.get("holding_period_days", 0)) >= 365,
            })

    # Sort by loss size (largest first)
    loss_positions.sort(key=lambda x: x["unrealized_loss"], reverse=True)

    remaining_losses = sum(p["unrealized_loss"] for p in loss_positions)
    carryforward = 0.0

    for yr in plan.years:
        income = income_by_year.get(yr, income_by_year.get(start_year, 0.0))

        # Harvest up to $3,000 ordinary income offset + any gains to offset
        harvest_this_year = min(remaining_losses + carryforward, 50_000.0)
        plan.harvest_amounts[yr] = harvest_this_year

        # Tax savings: $3,000 at ordinary rate + remainder at LTCG rate
        ordinary_offset = min(harvest_this_year + carryforward, 3_000.0)
        ltcg_offset = max(0.0, harvest_this_year - ordinary_offset)

        # Estimate tax rates from income
        ordinary_rate = 0.22 if income > 89_075 else 0.12
        ltcg_rate = 0.15 if income > 44_625 else 0.0

        tax_savings = ordinary_offset * ordinary_rate + ltcg_offset * ltcg_rate
        plan.tax_savings_by_year[yr] = tax_savings

        # Update carryforward
        used = ordinary_offset + ltcg_offset
        carryforward = max(0.0, carryforward + harvest_this_year - used)
        plan.carryforward_by_year[yr] = carryforward
        remaining_losses = max(0.0, remaining_losses - harvest_this_year)

    plan.total_tax_savings = sum(plan.tax_savings_by_year.values())

    if loss_positions:
        plan.notes.append(
            f"Found {len(loss_positions)} position(s) with unrealized losses totaling "
            f"${sum(p['unrealized_loss'] for p in loss_positions):,.0f}."
        )
    else:
        plan.notes.append("No positions with unrealized losses found.")

    plan.notes.append(
        "⚠️ Wash-sale rule (IRC §1091): Do not repurchase substantially identical "
        "securities within 30 days before or after the sale."
    )
    plan.notes.append(
        "⚠️ Capital loss carryforward has no expiration — unused losses carry forward indefinitely."
    )

    return plan
