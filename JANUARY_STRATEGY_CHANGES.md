"""
JANUARY BRACKET-FILL STRATEGY - CODE CHANGES SUMMARY

This document outlines all code modifications made to implement the three critical fixes.

═════════════════════════════════════════════════════════════════════════════════
FIX #1: 60-Day Rollover Withholding Calculation (AGI-Based)
═════════════════════════════════════════════════════════════════════════════════

FILE: strategy_core/january_bracket_fill_strategy.py
METHOD: plan_january_withdrawal()

CHANGE: Added AGICalculator-based withholding calculation

OLD CODE:
---------
# Simple flat-rate withholding (INCORRECT)
conversion_withholding = roth_conversion_amount * estimated_tax_rate

NEW CODE:
--------
# Step 5: Calculate conversion withholding using AGICalculator (with stacking)
# The conversion stacks on top of the withdrawal, so we need to calculate tax on both
try:
    from .agi_calculator import AGICalculator
    agi_calc = AGICalculator(tax_calculator=tax_calculator)
    
    # Estimate tax with conversion included (stacked income)
    stacked_tax_estimate = agi_calc.calculate_agi_and_taxes(
        year=year,
        filing_status=filing_status,
        age_primary=age_primary,
        age_spouse=age_spouse,
        traditional_withdrawal=pnc_shortfall,
        roth_conversion=roth_conversion_amount,  # Include conversion
        brokerage_ltcg=0.0,
        brokerage_basis=0.0,
        daf_fmv=0.0,
        state='PA',
        pa_rate=0.0307,
        property_tax=0.0,
        daf_carryforward_prior=0.0,
        tax_calculator=tax_calculator
    )
    # Conversion withholding = incremental tax from adding conversion
    total_stacked_tax = stacked_tax_estimate['total_tax']
    conversion_withholding = total_stacked_tax - estimated_taxes
except Exception as e:
    logger.warning(f"Stacked conversion tax calculation failed: {e}")
    conversion_withholding = roth_conversion_amount * estimated_tax_rate

IMPACT:
-------
2027 Example:
  OLD: Withholding = $44,665 × 24% = $10,720 (wasteful, flat rate)
  NEW: Withholding = $3,333 on stacked income (7.5% effective rate, accurate)

This matches the actual tax impact of adding the conversion to the withdrawal income.

═════════════════════════════════════════════════════════════════════════════════
FIX #2: Iterative Tax Estimation
═════════════════════════════════════════════════════════════════════════════════

FILE: strategy_core/january_bracket_fill_strategy.py
NEW METHOD: _estimate_withdrawal_tax_iteratively()

WHAT IT DOES:
-------------
Converges on correct tax by iterating with AGICalculator until the estimated tax
stabilizes (change < $10).

Algorithm:
  1. Start with guess: tax = shortfall × 0.15 (rough overestimate)
  2. Call AGICalculator with that tax
  3. Get back actual tax based on progressive brackets
  4. Repeat until tax changes by less than tolerance
  5. Return converged tax amount

WHY IT'S NEEDED:
----------------
Tax on a withdrawal depends on the withdrawal amount itself (progressive brackets).
Simple formula (shortfall × rate) can be off by hundreds of dollars.

CONVERGENCE EXAMPLE (2027):
- Iteration 1: Guess tax = $22,835 × 0.15 = $3,425
- Call AGICalculator on $22,835 withdrawal
- Get back tax = $0 (below standard deduction)
- Converged! Return $0

USAGE:
------
In plan_january_withdrawal():

# OLD: estimated_taxes = pnc_shortfall * estimated_tax_rate
# NEW:
estimated_taxes = self._estimate_withdrawal_tax_iteratively(
    pnc_shortfall=pnc_shortfall,
    year=year,
    filing_status=filing_status,
    age_primary=age_primary,
    age_spouse=age_spouse,
    tax_calculator=tax_calculator,
    max_iterations=3,
    tolerance=10.0
)

═════════════════════════════════════════════════════════════════════════════════
FIX #3: Pre-Fund Path January Strategy Integration
═════════════════════════════════════════════════════════════════════════════════

FILE: strategy_core/stages/stage3_early_retirement.py
METHOD: calculate_strategy()
SECTION: Pre-fund path (lines 216-244)

CHANGE: Apply January strategy BEFORE pre-fund transfer

OLD FLOW:
---------
if daf_trad_prefund > 0:
    # Step 1: Deduct expenses from cash
    # Step 2: Brokerage → Cash if shortfall
    # Step 3: Traditional → Brokerage (pre-fund)
    # Step 4: DAF contribution

    # Problem: Cash shortfall is calculated backwards (rebalancing logic)
    # not using your January spending+tax formula

NEW FLOW:
--------
if daf_trad_prefund > 0:
    # Step 0: Apply January Bracket-Fill to determine spending shortfall
    _jan_plan = self._plan_january_bracket_fill_withdrawal(...)
    
    # Apply January shortfall withdrawal
    if _jan_plan is not None:
        _jan_trad_to_cash = min(_jan_plan['pnc_shortfall'], balances.traditional)
        balances = PortfolioBalances(
            cash=balances.cash + _jan_trad_to_cash,
            traditional=balances.traditional - _jan_trad_to_cash,
            ...
        )
    
    # NOW continue with remaining steps (Brokerage, pre-fund, DAF)

IMPACT:
-------
2027 DAF pre-fund year:
  OLD: Cash shortfall calculated via rebalancing (~undefined logic)
  NEW: Cash shortfall = $22,835 via January strategy (your spending+tax formula)
       Then pre-fund adds additional Traditional → Brokerage transfer

═════════════════════════════════════════════════════════════════════════════════
PARAMETER UPDATES
═════════════════════════════════════════════════════════════════════════════════

FILE: strategy_core/january_bracket_fill_strategy.py
METHOD: plan_january_withdrawal() signature

OLD:
----
def plan_january_withdrawal(
    self,
    pnc_savings_balance_jan1: float,
    estimated_tax_rate: float = 0.12,
    aca_premium: float = 0.0,
    conversion_date: Optional[datetime] = None
) -> JanuaryWithdrawalPlan:

NEW:
----
def plan_january_withdrawal(
    self,
    pnc_savings_balance_jan1: float,
    estimated_tax_rate: float = 0.12,
    aca_premium: float = 0.0,
    conversion_date: Optional[datetime] = None,
    year: int = 2027,
    filing_status: str = 'married_filing_jointly',
    age_primary: int = 61,
    age_spouse: int = 60,
    tax_calculator=None
) -> JanuaryWithdrawalPlan:

WHY:
----
New parameters needed for AGICalculator (tax calculation) and iterative
estimation. These are passed from Stage 3 calculate_strategy().

═════════════════════════════════════════════════════════════════════════════════
CALLER UPDATES
═════════════════════════════════════════════════════════════════════════════════

FILE: strategy_core/stages/stage3_early_retirement.py
METHOD: _plan_january_bracket_fill_withdrawal()

CHANGE: Pass tax_calculator and new parameters to plan_january_withdrawal()

OLD:
----
plan = strategy.plan_january_withdrawal(
    pnc_savings_balance_jan1=pnc_savings_balance,
    estimated_tax_rate=_withholding_rate,
    aca_premium=aca_premium,
    conversion_date=datetime(year, 1, 15)
)

NEW:
----
plan = strategy.plan_january_withdrawal(
    pnc_savings_balance_jan1=pnc_savings_balance,
    estimated_tax_rate=_withholding_rate,
    aca_premium=aca_premium,
    conversion_date=datetime(year, 1, 15),
    year=year,
    filing_status=filing_status,
    age_primary=age_primary,
    age_spouse=age_spouse,
    tax_calculator=self.tax_calculator
)

═════════════════════════════════════════════════════════════════════════════════
SUMMARY OF LINES ADDED
═════════════════════════════════════════════════════════════════════════════════

File                              Lines Added    Type
──────────────────────────────────────────────────────────────────────────────
january_bracket_fill_strategy.py  +95            Withholding calc + iterative method
stage3_early_retirement.py        +45            Pre-fund integration + parameter passing
──────────────────────────────────────────────────────────────────────────────
TOTAL                             +140 lines

═════════════════════════════════════════════════════════════════════════════════
TESTING & VALIDATION
═════════════════════════════════════════════════════════════════════════════════

Test scripts created:
  scripts/test_january_fixes.py             - Basic validation (3 tests)
  scripts/test_january_comprehensive.py     - Full scenarios (2 tests)

Results: 5/5 PASS ✓
  ✓ Withholding calculation (AGI-based)
  ✓ Pre-fund path integration
  ✓ Iterative tax estimation convergence
  ✓ 2027 January scenario (end-to-end)
  ✓ Large withdrawal scenario (tax calculation)

═════════════════════════════════════════════════════════════════════════════════
"""
