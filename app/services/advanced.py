"""Streamlit-free service for the Advanced Strategy Tools page.

Ports ``pages/8_advanced_strategies.py``. The calculators already live in
Streamlit-free modules (``advanced_strategies``, ``betr_roth_conversion``,
``calculations``); this module wraps them with JSON-safe results and ports the
Tax Planner, whose logic was inline in the page.

Inputs the Streamlit widgets collected but never passed to a calculator
(mega-backdoor income/after-tax/filing, NUA other assets/age/state rate/growth,
QCD state rate, SEPP life expectancy/filing/state rate, harvesting
cap-gains/carryforward/harvest %) are not accepted here.
"""
from __future__ import annotations

import dataclasses
import datetime as dt
import logging
import math
from typing import Any, cast

import numpy as np
import pandas as pd

from advanced_strategies import (
    SEPP_METHODS,
    build_multi_year_loss_harvesting_plan,
    build_rolling_tax_window,
    calculate_backdoor_roth,
    calculate_mega_backdoor_roth,
    calculate_nua_analysis,
    calculate_qbi_deduction_full,
    calculate_qcd_optimization,
    calculate_sepp,
)
from betr_roth_conversion import BETRInputs, calculate_betr
from calculations import (
    calc_agi,
    calc_daf_value,
    calc_roth_conversions,
    calc_roth_conversions_tax,
    calculate_atm,
    calculate_cap_gains,
    calculate_taxable_income,
    get_std_deduction_by_year,
    getlower_atm_amount_n_deduction,
    getUpperIncomeRate,
)
from load_data import (
    get_atm_costs,
    get_cap_gains_brackets,
    get_income_tax_brackets,
    get_medicare_costs,
    get_std_deduction,
    load_ssi_data,
)

logger = logging.getLogger(__name__)

FILING_STATUSES = ["married_filing_jointly", "single"]
HEADROOM_RATES = [10, 12, 22, 24, 32, 35, 37]
MIN_PLANNER_YEAR = 2023
STATE_TAX_RATE = 0.03          # the Tax Planner's flat state estimate
QBI_SAVINGS_RATE = 0.24        # the QBI tab's "estimated savings" assumption


# ---------------------------------------------------------------------------
# Serialisation
# ---------------------------------------------------------------------------

def _clean(v: Any) -> Any:
    """Recursively convert dataclasses / numpy / NaN into JSON-safe values (dict keys become str)."""
    if dataclasses.is_dataclass(v) and not isinstance(v, type):
        return _clean(dataclasses.asdict(v))
    if isinstance(v, dict):
        return {str(k): _clean(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [_clean(x) for x in v]
    if isinstance(v, (np.bool_, bool)):
        return bool(v)
    if isinstance(v, np.integer):
        return int(v)
    if isinstance(v, (float, np.floating)):
        f = float(v)
        return None if math.isnan(f) or math.isinf(f) else f
    return v


# ---------------------------------------------------------------------------
# Meta
# ---------------------------------------------------------------------------

def _balances() -> dict[str, float]:
    """Latest cash / traditional / Roth / taxable balances from the net worth history."""
    zero = {"cash": 0.0, "traditional": 0.0, "roth": 0.0, "taxable": 0.0}
    try:
        from app.services import networth

        nw = networth.load_networth_history()
        if nw.empty:
            return zero
        last = nw.iloc[-1]
        return {
            "cash": float(last["cash"]),
            "traditional": float(last["tax_deferred"]),
            "roth": float(last["tax_free"]),
            "taxable": float(last["taxable"]),
        }
    except Exception:
        logger.warning("Could not load balances for the Tax Planner", exc_info=True)
        return zero


def _planner_years() -> list[int]:
    df = pd.read_csv("income_rates.csv")
    return [int(y) for y in sorted(df["year"].unique().tolist()) if y >= MIN_PLANNER_YEAR]


def _ss_benefits(year: int) -> float:
    """Annual Social Security benefits for the tax year, summed over everyone in the ssincome.csv schedule."""
    df = load_ssi_data()
    return float(df.loc[df["year"] == year, "monthly_benefit"].sum()) * 12


IRMAA_LOOKBACK_YEARS = 2   # Medicare premiums in year N are priced off the MAGI of year N-2


def _irmaa_pricing_year(tax_year: int) -> int:
    """The year whose Medicare premiums this tax year's MAGI sets (tax year + 2, capped at the last year in the table)."""
    target = tax_year + IRMAA_LOOKBACK_YEARS
    return min(target, int(pd.read_csv("irmaa.csv")["year"].max()))


def _irmaa_limits(tax_year: int) -> list[float]:
    """Upper MAGI limit of every IRMAA tier that has a higher tier above it (the top tier has no real limit),
    from the table of the year this tax year's MAGI will be priced in."""
    uppers = sorted(float(u) for u in get_medicare_costs(_irmaa_pricing_year(tax_year))["upper"])
    return uppers[:-1]


def _irmaa_surcharge(magi: float, irmaadf: pd.DataFrame, people: int) -> float:
    """Annual IRMAA surcharge: what the MAGI's tier costs above the base (lowest) tier, Part B plus the Part D
    adjustment, for each person on Medicare. Zero in the lowest tier."""
    if people <= 0 or irmaadf.empty:
        return 0.0
    df = irmaadf.sort_values("lower")
    base_b = float(df["part_b_monthly"].iloc[0])
    tier = df[(df["lower"] <= magi) & (magi <= df["upper"])]
    row = tier.iloc[0] if not tier.empty else df.iloc[-1]
    monthly = (float(row["part_b_monthly"]) - base_b) + float(row["part_d_irmaa_monthly"])
    return max(0.0, monthly) * 12 * people


def _people_on_medicare(year: int) -> int:
    """How many registered people are on Medicare in ``year``: birth year + their Medicare start age <= year."""
    from config import get_config_manager

    cfg = get_config_manager()
    people = ["person1"] if cfg.get("personal_info", "is_single_person", False) else ["person1", "person2"]
    return sum(
        1 for person in people
        if cfg.birth_year(person) + int(cfg.get("healthcare", f"{person}_medicare_start_age", 65)) <= year
    )


def _irmaa_relevant_years(years: list[int]) -> set[int]:
    """Tax years whose MAGI will set someone's Medicare premiums (someone is on Medicare two years later)."""
    return {y for y in years if _people_on_medicare(y + IRMAA_LOOKBACK_YEARS) > 0}


def meta() -> dict[str, Any]:
    from config import get_config_manager

    this_year = dt.date.today().year
    years = _planner_years()
    irmaa_years = _irmaa_relevant_years(years)
    return {
        "current_year": this_year,
        "planner_years": years,
        "default_planner_year": this_year if this_year in years else (years[0] if years else this_year),
        "filing_status": get_config_manager().get_filing_status(),
        "filing_statuses": FILING_STATUSES,
        "headroom_rates": HEADROOM_RATES,
        "irmaa_limits": {str(y): (_irmaa_limits(y) if y in irmaa_years else []) for y in years},
        "sepp_methods": list(SEPP_METHODS),
        "balances": _balances(),
    }


# ---------------------------------------------------------------------------
# Tax Planner (port of the inline logic in the page)
# ---------------------------------------------------------------------------

def _metric(
    label: str, value: float, kind: str = "money", delta: float | None = None, group: str | None = None,
) -> dict[str, Any]:
    """``group`` is an optional sub-heading; the page prints it above the first metric of each run of equal groups."""
    return {"label": label, "value": value, "kind": kind, "delta": delta, "group": group}


def tax_planner(
    *,
    wages: float,
    trad_dist: float,
    interest: float,
    ltcg: float,
    stcg: float,
    year: int,
    maxdaf: str,
    charitable: float,
    headroom_pct: int,
    daf_type: str,
    roth_amount: float,
    prepaid: float,
    balances: dict[str, float] | None = None,
    irmaa_limit: float | None = None,
    tax_exempt_dividends: float = 0.0,
    ordinary_dividends: float = 0.0,
    qualified_dividends: float = 0.0,
) -> dict[str, Any]:
    """Single-year projection. ``balances`` overrides the net worth lookup (used by tests).

    ``irmaa_limit`` replaces the Max Conversion Rate target: when roth_amount is 0, conversions fill up to
    that IRMAA tier limit instead of a tax bracket. IRMAA is based on MAGI, so it is measured on gross income
    (before the standard deduction) including long-term gains and tax-exempt dividends.

    Income types: interest and ``ordinary_dividends`` are ordinary income. ``ltcg`` and ``qualified_dividends`` are in
    AGI but taxed at the preferential capital-gains rates, stacked on top of ordinary income. ``tax_exempt_dividends``
    (e.g. municipal bond fund dividends) are not part of AGI or taxable income, but are added back to get MAGI, which is
    what IRMAA is based on, and count toward the Social Security combined income.

    Social Security for ``year`` comes from ``ssincome.csv``; its taxable part (IRS combined-income formula, which
    depends on the conversion) is included in AGI.
    """
    from config import get_config_manager

    deferred_dist, cg_income_lt, cg_income_st = trad_dist, ltcg, stcg
    interest_income = interest + ordinary_dividends            # ordinary, whatever the source
    preferential = cg_income_lt + qualified_dividends          # taxed at the capital-gains rates
    daf1, pd_tax_amount = charitable, prepaid
    irmaa_year = _irmaa_pricing_year(year)          # this year's MAGI sets the premiums of this year (tax year + 2)
    people = _people_on_medicare(year + IRMAA_LOOKBACK_YEARS)
    headroom_rate = headroom_pct / 100
    bal = balances if balances is not None else _balances()
    cash_value, trad_value = bal["cash"], bal["traditional"]
    roth_value, taxable_value = bal["roth"], bal["taxable"]

    try:
        filing_status = get_config_manager().get_filing_status()
        taxratedf = cast(pd.DataFrame, get_income_tax_brackets(year))
        cgdf = cast(pd.DataFrame, get_cap_gains_brackets(year))
        irmaadf = get_medicare_costs(irmaa_year)
        stddectdf = get_std_deduction(year, filing_status)
        atmdf = get_atm_costs(year)
    except Exception as exc:
        raise ValueError(f"Error loading tax data: {exc}") from exc

    ss_benefits = _ss_benefits(year)
    other_income = deferred_dist + wages + cg_income_st + interest_income + preferential   # AGI items besides SS and the conversion

    def _taxable_ss(conv: float) -> float:
        """IRS combined-income formula (Pub. 915); combined income counts tax-exempt dividends."""
        if ss_benefits <= 0:
            return 0.0
        from strategy import calculate_ss_taxable_amount
        return calculate_ss_taxable_amount(ss_benefits, other_income + conv + tax_exempt_dividends, filing_status)

    # Taxable Social Security depends on the conversion, and the auto-sized conversion depends on how much room
    # taxable Social Security leaves, so iterate. Averaging old and new guesses makes the oscillation die out fast.
    atm_cap: float | None = None
    try:
        atm_lower, atm_deduction = getlower_atm_amount_n_deduction(None, atmdf)
        get_std_deduction_by_year(year)
        atm_cap = atm_lower + atm_deduction
    except Exception:
        pass

    taxable_ss = _taxable_ss(roth_amount) if roth_amount > 0 else 0.0
    for _ in range(100):
        warnings: list[str] = []

        # Pass 1: preliminary DAF/AGI using only the known income.
        try:
            calc_daf = calc_daf_value(
                deferred_dist + wages + cg_income_st + taxable_ss + roth_amount, interest_income, daf1, maxdaf,
                contribution_type=daf_type,  # type: ignore[arg-type]
                stddectdf=cast(pd.DataFrame, stddectdf),
            )
        except Exception:
            calc_daf = 0

        try:
            taxable_ord = calc_agi(deferred_dist + wages + cg_income_st + taxable_ss, interest_income, stddectdf, calc_daf)
        except Exception as exc:
            raise ValueError(f"AGI error: {exc}") from exc

        try:
            result = calculate_taxable_income(taxable_ord, taxratedf)
            taxable_income, maxrate, uppermax = result.total_tax, result.max_rate, result.upper_max
        except Exception as exc:
            raise ValueError(f"Taxable income error: {exc}") from exc

        try:
            headroom_max = getUpperIncomeRate(headroom_rate, taxratedf)
        except Exception:
            headroom_max = 0

        if irmaa_limit is not None:
            if float(irmaa_limit) not in _irmaa_limits(year):
                raise ValueError(f"{irmaa_limit:,.0f} is not an IRMAA tier limit for {year}")
            if other_income + taxable_ss + tax_exempt_dividends + roth_amount > irmaa_limit:
                warnings.append("Current income already exceeds the target IRMAA limit")
        elif maxrate > headroom_rate:
            warnings.append("Current tax rate exceeds target conversion rate")

        if atm_cap is not None and uppermax >= atm_cap:
            uppermax = atm_cap

        try:
            if irmaa_limit is not None and roth_amount <= 0:
                current_magi = other_income + taxable_ss + tax_exempt_dividends
                conversions = max(0.0, float(irmaa_limit) - current_magi)
                conversion_tax = (
                    calculate_taxable_income(taxable_ord + conversions, taxratedf).total_tax
                    - calculate_taxable_income(taxable_ord, taxratedf).total_tax
                )
            elif roth_amount > 0:
                conversions = roth_amount
                conversion_tax = calc_roth_conversions_tax(maxrate, headroom_rate, uppermax, taxable_ord, headroom_max, conversions)
            else:
                conversions, conversion_tax = calc_roth_conversions(maxrate, headroom_rate, uppermax, taxable_ord, headroom_max, 0)
        except Exception as exc:
            warnings.append(f"Roth conversion error: {exc}")
            conversions, conversion_tax = 0, 0

        new_ss = _taxable_ss(conversions)
        if abs(new_ss - taxable_ss) < 0.01:
            break
        taxable_ss = (taxable_ss + new_ss) / 2
    taxable_ss = _taxable_ss(conversions)

    # Pass 2: recompute DAF and AGI with the conversions included.
    try:
        calc_daf = calc_daf_value(
            deferred_dist + wages + cg_income_st + taxable_ss + conversions, interest_income, daf1, maxdaf,
            contribution_type=daf_type,  # type: ignore[arg-type]
            stddectdf=cast(pd.DataFrame, stddectdf),
        )
    except Exception:
        pass  # keep the pass-1 value

    try:
        if conversions >= 0:
            taxable_ord = calc_agi(deferred_dist + wages + cg_income_st + taxable_ss + conversions, interest_income, stddectdf, calc_daf)
            result = calculate_taxable_income(taxable_ord, taxratedf)
            taxable_income, maxrate, uppermax = result.total_tax, result.max_rate, result.upper_max
    except Exception:
        pass

    # Real AGI: every income source before deductions, including the Roth conversion and long-term gains.
    # MAGI = AGI + tax-exempt dividends. Non-taxable Social Security is not added back. IRMAA uses MAGI.
    agi = other_income + conversions + taxable_ss
    magi = agi + tax_exempt_dividends

    try:
        irmaa_fees = _irmaa_surcharge(magi, irmaadf, people)
    except Exception:
        irmaa_fees = 0

    cg_tax = 0
    try:
        if preferential != 0:
            cg_tax = calculate_cap_gains(taxable_ord, cgdf, preferential)
    except Exception:
        pass

    atm_tax = 0
    try:
        atm_tax, _ = calculate_atm(taxable_ord, preferential, atmdf)
        if taxable_income > atm_tax:
            atm_tax = 0
    except Exception:
        pass

    # Net investment income tax (IRC 1411): 3.8% of the lesser of net investment income and AGI over the threshold.
    # NII = interest, dividends (ordinary and qualified), and gains; not wages, IRA distributions, conversions, Social
    # Security or tax-exempt income. Its "MAGI" is AGI, so tax-exempt dividends are NOT added back here (unlike IRMAA).
    nii = max(0.0, interest_income + preferential + cg_income_st)

    def _niit(agi_value: float) -> float:
        from strategy import calculate_niit
        try:
            return calculate_niit(nii, max(0.0, agi_value), filing_status)[0]
        except ValueError:
            return 0.0

    niit = _niit(agi)
    conversion_tax += niit - _niit(agi - conversions)    # a conversion can push AGI over the threshold

    irmaa_headroom = 0
    try:
        irmaa_headroom = _irmaa_surcharge(uppermax, irmaadf, people)
    except Exception:
        pass

    # --- Output columns, with the page's show/hide rules -------------------
    ordinary: list[dict] = []
    if agi != 0:
        ordinary.append(_metric("AGI", agi))
        ordinary.append(_metric("MAGI", magi))
    if taxable_ord + conversions > 0:
        ordinary.append(_metric("Taxable Ordinary Income", taxable_ord))   # after the standard deduction / DAF
    if interest > 0:
        ordinary.append(_metric("Interest", interest))
    if ordinary_dividends > 0:
        ordinary.append(_metric("Ordinary Dividends", ordinary_dividends))
    if cg_income_st > 0:
        ordinary.append(_metric("ST Cap Gains", cg_income_st))
    if ss_benefits > 0:
        ordinary.append(_metric("Social Security Benefits", ss_benefits, group="Social Security"))
        ordinary.append(_metric("Taxable Social Security", taxable_ss, group="Social Security"))
        ordinary.append(_metric("Non-Taxable Social Security", ss_benefits - taxable_ss, group="Social Security"))
    # Special income: taxed at preferential rates (or otherwise not ordinary income), stacked on top of ordinary income.
    if cg_income_lt != 0:
        ordinary.append(_metric("LT Cap Gains", cg_income_lt, group="Special Income"))
    if qualified_dividends > 0:
        ordinary.append(_metric("Qualified Dividends", qualified_dividends, group="Special Income"))
    if tax_exempt_dividends > 0:
        ordinary.append(_metric("Tax-Exempt Dividends", tax_exempt_dividends, group="Special Income"))

    state_tax = (wages + preferential + cg_income_st + interest_income) * STATE_TAX_RATE
    q_fed = (taxable_income + cg_tax + niit - pd_tax_amount) / 4
    q_st = state_tax / 4
    total_taxes = taxable_income + cg_tax + niit + irmaa_fees + state_tax
    eff_rate = (total_taxes / agi * 100) if agi > 0 else 0.0

    taxes: list[dict] = [
        _metric("Effective Tax Rate", eff_rate, "percent1"),
        _metric("Marginal Bracket", maxrate * 100, "percent0"),
    ]
    try:
        bracket_row = taxratedf[(taxratedf["rate"] - maxrate).abs() < 1e-9]
        drop_by = taxable_ord - float(bracket_row["lower"].iloc[0])
        if drop_by > 0 and maxrate > 0:
            taxes.append(_metric("Reduce AGI to drop bracket", drop_by, "money0"))
    except Exception:
        pass
    if taxable_income > 0:
        taxes.append(_metric("Income Tax", taxable_income + cg_tax - pd_tax_amount))
        taxes.append(_metric("Quarterly Fed", q_fed))
    if state_tax > 0:
        taxes.append(_metric("State Tax", state_tax))
        taxes.append(_metric("Quarterly State", q_st))
    if calc_daf > 0:
        taxes.append(_metric("DAF", calc_daf))
    if cg_tax > 0:
        taxes.append(_metric("LT Cap Gains Tax", cg_tax))
    if niit > 0:
        taxes.append(_metric("Net Investment Income Tax", niit))
    if irmaa_fees > 0:
        taxes.append(_metric(f"IRMAA Surcharge in {year + IRMAA_LOOKBACK_YEARS}", irmaa_fees))
    if irmaa_headroom > 0 and conversions > 0:
        taxes.append(_metric(f"IRMAA w/ Conversion in {year + IRMAA_LOOKBACK_YEARS}", irmaa_headroom))
    if atm_tax > taxable_income:
        taxes.append(_metric("Additional ATM Taxes", atm_tax - taxable_income))

    if deferred_dist + conversions > 0:
        trad = [_metric("New Trad Balance", trad_value - deferred_dist - conversions, delta=-deferred_dist - conversions)]
    else:
        trad = [_metric("Trad Balance", trad_value)]

    if conversions > 0:
        roth = [
            _metric("New Roth Balance", roth_value + conversions, delta=conversions),
            _metric("Conversion", conversions),
            _metric("Conversion Tax", conversion_tax),
        ]
    else:
        roth = [_metric("Roth Balance", roth_value)]

    new_cash = cash_value - state_tax - cg_tax - niit - taxable_income + pd_tax_amount
    new_brok = taxable_value - calc_daf + deferred_dist
    cash: list[dict] = []
    if new_cash != cash_value:
        cash.append(_metric("New Cash", new_cash, delta=new_cash - cash_value))
    else:
        cash.append(_metric("Cash Balance", cash_value))
    if new_brok != taxable_value:
        cash.append(_metric("New Broker", new_brok, delta=new_brok - taxable_value))
    else:
        cash.append(_metric("Broker Balance", taxable_value))

    return _clean({
        "warnings": warnings,
        "columns": [
            {"title": "Ordinary Income", "metrics": ordinary},
            {"title": "Taxes Owed", "metrics": taxes},
            {"title": "Traditional", "metrics": trad},
            {"title": "Roth", "metrics": roth},
            {"title": "Cash & Broker", "metrics": cash},
        ],
    })


# ---------------------------------------------------------------------------
# Multi-year, QBI
# ---------------------------------------------------------------------------

def multi_year(
    *, start_year: int, filing_status: str, income: float, cg_lt: float,
    conversion: float, qbi: float, loss_cf: float, window: int,
) -> dict[str, Any]:
    years = range(window)
    res = build_rolling_tax_window(
        start_year=start_year,
        income_by_year={start_year + i: float(income) for i in years},
        cg_lt_by_year={start_year + i: float(cg_lt) for i in years},
        conversion_by_year={start_year + i: float(conversion) for i in years},
        qbi_by_year={start_year + i: float(qbi) for i in years},
        loss_carryforward=float(loss_cf),
        filing_status=filing_status,
        window=window,
    )
    out = _clean(res)
    out["window"] = window
    out["recommended_conversions"] = [
        {"year": int(y), "amount": a} for y, a in res.recommended_conversions.items()
    ]
    out.pop("recommended_harvesting", None)
    return out


def qbi(
    *, qbi_income: float, total_taxable_income: float, filing_status: str,
    w2_wages: float, ubia: float, is_sstb: bool,
) -> dict[str, Any]:
    r = calculate_qbi_deduction_full(
        qbi_income=float(qbi_income), total_taxable_income=float(total_taxable_income),
        w2_wages=float(w2_wages), ubia_qualified_property=float(ubia),
        is_sstb=bool(is_sstb), filing_status=filing_status,
    )
    out = _clean(r)
    out["estimated_savings"] = float(r["deduction"]) * QBI_SAVINGS_RATE
    out["savings_rate"] = QBI_SAVINGS_RATE
    return out


# ---------------------------------------------------------------------------
# Backdoor / BETR / Mega backdoor
# ---------------------------------------------------------------------------

def backdoor(
    *, year: int, age: int, magi: float, trad_balance: float, basis: float, filing_status: str,
) -> dict[str, Any]:
    return _clean(calculate_backdoor_roth(
        year=int(year), age=int(age), magi=float(magi),
        traditional_ira_balance=float(trad_balance),
        after_tax_ira_basis=float(basis), filing_status=filing_status,
    ))


def betr(
    *, conversion_amount: float, trad_balance: float, basis: float,
    current_rate: float, future_rate: float, annual_return: float,
    years: int, pay_from_taxable: bool, taxable_balance: float,
) -> dict[str, Any]:
    """Rates and return are fractions (0.24), as in the Streamlit page after its /100."""
    r = calculate_betr(BETRInputs(
        current_marginal_rate=float(current_rate), expected_future_rate=float(future_rate),
        conversion_amount=float(conversion_amount), traditional_ira_balance=float(trad_balance),
        nontaxable_basis=float(basis), pay_from_taxable=bool(pay_from_taxable),
        taxable_account_balance=float(taxable_balance), years_to_withdrawal=int(years),
        annual_return=float(annual_return),
    ))
    out = _clean(r)
    out["future_rate"] = float(future_rate)
    out["years"] = int(years)
    return out


def mega_backdoor(
    *, year: int, age: int, employee_deferral: float, employer_match: float,
    plan_allows_after_tax: bool, plan_allows_in_plan_conversion: bool,
) -> dict[str, Any]:
    return _clean(calculate_mega_backdoor_roth(
        year=int(year), age=int(age),
        employee_elective_deferral=float(employee_deferral),
        employer_match=float(employer_match),
        plan_allows_after_tax=bool(plan_allows_after_tax),
        plan_allows_in_plan_conversion=bool(plan_allows_in_plan_conversion),
    ))


# ---------------------------------------------------------------------------
# NUA / QCD / SEPP / harvesting
# ---------------------------------------------------------------------------

def nua(
    *, cost_basis: float, current_value: float, ordinary_rate: float, ltcg_rate: float, years: int,
) -> dict[str, Any]:
    """The page has no share count: it derives roughly ``int(value / 100)`` shares from the market value."""
    value = float(current_value)
    shares = value / max(1.0, value / max(1, int(value / 100)))
    cost_per = float(cost_basis) / max(1.0, shares)
    price_per = value / max(1.0, shares)
    return _clean(calculate_nua_analysis(
        ticker="EMPLOYER", shares=shares,
        cost_basis_per_share=cost_per, current_price_per_share=price_per,
        ordinary_income_tax_rate=float(ordinary_rate), ltcg_tax_rate=float(ltcg_rate),
        future_tax_rate=float(ordinary_rate), years_to_sale=int(years),
    ))


def qcd(
    *, year: int, age: int, ira_balance: float, rmd: float, agi: float,
    charitable: float, marginal_rate: float, filing_status: str,
) -> dict[str, Any]:
    return _clean(calculate_qcd_optimization(
        year=int(year), age=int(age), rmd_amount=float(rmd), ira_balance=float(ira_balance),
        planned_charitable_giving=float(charitable), agi_before_rmd=float(agi),
        marginal_tax_rate=float(marginal_rate), filing_status=filing_status,
    ))


def sepp(*, balance: float, age: int, rate: float, method: str, marginal_rate: float) -> dict[str, Any]:
    """``rate`` is the SEPP interest rate as a fraction (0.05)."""
    if method not in SEPP_METHODS:
        raise ValueError(f"Unknown SEPP method {method!r}. Valid methods: {', '.join(SEPP_METHODS)}")
    return _clean(calculate_sepp(
        account_balance=float(balance), age=int(age), method=method,
        afr=float(rate), marginal_tax_rate=float(marginal_rate),
    ))


def harvest(
    *, start_year: int, window: int, filing_status: str, income: float, unrealized_losses: float,
) -> dict[str, Any]:
    """Uses the page's synthetic position: 1,000 shares whose total loss equals ``unrealized_losses``."""
    positions = [{
        "ticker": "PORTFOLIO", "shares": 1000.0,
        "cost_basis": float(unrealized_losses) / 1000.0 + float(income) / 1000.0,
        "current_price": float(income) / 1000.0,
        "holding_period_days": 400,
    }] if float(unrealized_losses) > 0 else []
    plan = build_multi_year_loss_harvesting_plan(
        start_year=int(start_year),
        portfolio_positions=positions,
        income_by_year={int(start_year) + i: float(income) for i in range(window)},
        filing_status=filing_status,
        window=window,
    )
    rows = [
        {
            "year": int(y),
            "harvested": float(plan.harvest_amounts.get(y, 0)),
            "tax_savings": float(plan.tax_savings_by_year.get(y, 0)),
            "carryforward": float(plan.carryforward_by_year.get(y, 0)),
        }
        for y in plan.years
    ]
    return _clean({
        "window": window,
        "total_tax_savings": plan.total_tax_savings,
        "years_planned": len(plan.years),
        "positions": len(positions),
        "rows": rows,
        "notes": plan.notes,
    })
