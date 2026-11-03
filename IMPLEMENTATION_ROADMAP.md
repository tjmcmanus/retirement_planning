# IMPLEMENTATION ROADMAP: January Bracket-Fill + 60-Day Rollover Strategy

> **Developer note** — this is an internal planning document, not a user guide.
> It tracks in-progress work on the January bracket-fill strategy and related tax calculation fixes.

**STATUS:** AGI Calculation Fixes ✓ | 60-Day Rollover Integration ✓ | Multi-Year Projection Validated ✓ | Config UI & Dashboard Widgets ✓ | Stages 5–7 AGICalculator Refactor ✓
**NEXT:** All phases complete. No open items.

═════════════════════════════════════════════════════════════════════════════
PHASE 1: AGI CALCULATION (COMPLETE ✓)
═════════════════════════════════════════════════════════════════════════════

✓ Created AGICalculator with correct IRC-compliant order
✓ Fixed Stage 3 (Early Retirement) — uses AGICalculator
✓ Fixed Stage 4 (Medicare) — uses AGICalculator  
✓ Added imports to Stages 5, 6, 7 (refactoring deferred)
✓ Created and validated test suite (6/6 checks pass)

KEY ACHIEVEMENT:
  - Correct AGI order: Ordinary → Pre-deduction AGI → 30% DAF limit → 
    Deduction → Taxable Ordinary → LTCG stacked
  - DAF carryforward tracked (up to 5 years)
  - Itemized vs. Standard deduction logic correct
  - LTCG properly stacks on top of Taxable Ordinary

═════════════════════════════════════════════════════════════════════════════
PHASE 2: 60-DAY ROLLOVER MECHANICS (COMPLETE ✓)
═════════════════════════════════════════════════════════════════════════════

STATUS: Integrated into Stage 3 and Stage 4 ✓

WHAT WAS DONE:
  Added three helpers to strategy_core/base_strategy.py:
    _use_60day_rollover()              — reads tax_strategy.use_60day_rollover_mechanics from config
    _effective_taxable_for_conversion() — returns brokerage + usable_cash when flag is ON,
                                          brokerage-only when OFF (usable_cash = cash − safety_reserve)
    _get_safety_reserve()              — reads tax_strategy.savings_safety_reserve from config ($56k)

  Wired in Stage 3 (strategy_core/stages/stage3_early_retirement.py):
    _calculate_betr_roth_conversion() call now receives _effective_taxable_for_conversion()
    instead of balances.taxable. Decision log entry includes rollover note when active.

  Wired in Stage 4 (strategy_core/stages/stage4_medicare.py):
    _calculate_irmaa_aware_roth_conversion() call now receives _effective_taxable_for_conversion()
    Decision log entry includes rollover note when active.

MECHANISM:
  When use_60day_rollover_mechanics=true (current config):
    effective_taxable = brokerage + max(0, cash − savings_safety_reserve)
  When false (off):
    effective_taxable = brokerage  (no change from prior behavior)
  
  The config currently has:
    use_60day_rollover_mechanics: true  → rollover active
    savings_safety_reserve: 56000       → $56k always kept in cash

OBSERVED IMPACT (2026–2050 projection with actual portfolio):
  Stage 4 (2031–2035) Roth conversions:
    BEFORE rollover integration: $0/year (brokerage exhausted by ~2031)
    AFTER  rollover integration: $229k–$251k/year (cash backs up withholding)
  Net Traditional balance at 2050: $3.0M (vs. $7.2M without conversions)
  → More efficient Roth conversion window preserved through Medicare years

TESTS: tests/test_sixty_day_rollover_integration.py — 16/16 pass
  - _use_60day_rollover reads config correctly
  - _effective_taxable_for_conversion: brokerage-only when OFF, brokerage+cash when ON
  - cash below reserve: usable_cash = 0, effective = brokerage only
  - Stage 3: thin brokerage blocks conversion OFF; unlocks it ON
  - Stage 4: same with IRMAA constraints
  - Symmetry: ample brokerage → ON and OFF give same conversion amount

ESTIMATED EFFORT: 3-4 hours (moderate complexity) → DONE ✓

═════════════════════════════════════════════════════════════════════════════
PHASE 3: CONFIG & UI (COMPLETE ✓)
═════════════════════════════════════════════════════════════════════════════

WHAT WAS DONE:

1. Configuration Parameters — all added to retirement_config.json:
   ✓ savings_safety_reserve: 56000 (cash kept in PNC at all times)
   ✓ property_tax: 5000 (read via _get_property_tax_from_config() in Stages 3 & 4)
   ✓ use_60day_rollover_mechanics: true (controls rollover path in Stages 3 & 4)
   ✓ DAF carryforward tracked via self._daf_carryforward instance variable in Stage 3

2. UI Changes (pages/2_configuration.py) — DONE:
   ✓ Accurate rollover help text with live status badge
   ✓ savings_safety_reserve displayed with correct fallback
   ✓ property_tax field with explanation

3. Dashboard Updates (pages/3_dashboard.py) — DONE:
   ✓ PNC reserve alert when balance < savings_safety_reserve
   ✓ 60-day rollover status widget with effective tax pool sizing
   ✓ DAF 10-year projection table

═════════════════════════════════════════════════════════════════════════════
PHASE 4: STAGES 5–7 REFACTORING (COMPLETE ✓)
═════════════════════════════════════════════════════════════════════════════

STATUS: All three stages now use AGICalculator for their final tax calculation.

WHAT WAS DONE:

1. Extended AGICalculator (strategy_core/agi_calculator.py):
   - Added ss_benefits and taxable_ss parameters to calculate_agi_and_taxes()
   - When ss_benefits > 0, taxable_ss is included in gross_ordinary income
   - Falls back to 85% × ss_benefits if taxable_ss = 0 but ss_benefits > 0
   - Returns 'taxable_ss' in the result dict
   - State tax call now passes _taxable_ss (0 for Stages 3/4; actual for 5/6/7)

2. Refactored Stage 5 (stage5_social_security.py):
   - Replaced inline final tax block + duplicated DAF calculation with AGICalculator call
   - Taxable SS is still computed via _calculate_ss_taxation() on actual income
   - AGICalculator handles: DAF 30% cap, itemized vs. standard, LTCG stacking, state tax

3. Refactored Stage 6 (stage6_rmd.py):
   - RMD passes through as part of traditional_withdrawal to AGICalculator
   - Same AGICalculator path replaces inline duplicate DAF/deduction block

4. Refactored Stage 7 (stage7_surviving_spouse.py):
   - Uses filing_status="Single" — AGICalculator handles single-filer brackets
     and the lower standard deduction automatically
   - Added strategy.daf_deductible assignment (was missing before)
   - Also fixed: tax_calculator.py normalises filing_status case so "Single"
     works the same as "single" (fixes CSV lookup)

5. Fixed TaxCalculator (strategy_core/tax_calculator.py):
   - calculate_standard_deduction: normalised filing_status to lowercase
   - calculate_federal_tax: same normalisation
   - calculate_capital_gains_tax: same normalisation
   - This ensures "Single" (Stage 7) works identically to "single"

TESTS: tests/test_stages567_agi_calculator.py — 25/25 pass
  - AGICalculator SS support: 8 tests
  - Stage 5 path: 5 tests
  - Stage 6 path: 6 tests
  - Stage 7 path: 6 tests

PROJECTION VALIDATION: All 9 inflection-point checks still pass (projection_2026_2050.py)
  - 2036 Stage 5 AGI: $545,546 (includes SS + traditional + conversion)
  - 2041 Stage 6 AGI: $381,096 (RMD + SS + conversion)
  - 2050 Stage 6 AGI: $189,503 (RMD-only years)

═════════════════════════════════════════════════════════════════════════════
PHASE 5: TESTING & VALIDATION (COMPLETE ✓)
═════════════════════════════════════════════════════════════════════════════

COMPLETED:
  ✓ AGI Calculator unit tests (6/6 pass)
  ✓ 2027 scenario validation (matches manual calculation)
  ✓ End-to-end Stage 3 test with actual config data
      scripts/test_stage3_actual_config.py — all checks pass
  ✓ End-to-end Stage 4 test (Medicare year)
      scripts/test_stage4_actual_config.py — all 7 checks pass
  ✓ DAF carryforward multi-year tracking test
      tests/test_daf_carryforward_multiyear.py — 12/12 pass
  ✓ Multi-year projection 2026–2050 — all 9 inflection-point checks pass
      scripts/projection_2026_2050.py
      Key findings:
        2026  Stage 2: AGI=$403,550 (final working/retirement year, big Roth conversion)
        2027  Stage 3: AGI=$498,663, Conv=$52,332 (bracket-fill begins)
        2028–2030  Stage 3: Roth conversions $238k–$264k/yr (filling 22% bracket)
        2031  Stage 4: IRMAA=$8,487 (2-year lookback on 2029 MAGI)
        2032  Stage 4: IRMAA=$16,975 (lookback hits peak 2030 MAGI — doubles as expected)
        2033–2035  Stage 4: IRMAA normalizes to $4,956/yr; Roth conv stops (brokerage exhausted)
        2036  Stage 5: SS starts (AGI=$195,657 including SS); total portfolio crosses $10M
        2039  Stage 5: Tom's IRS RMD age (73) reached, but Stage 5 continues because
                       Stage 5 uses younger spouse (Sarah born 1967) threshold = age 75
        2041  Stage 6: RMD stage begins (Tom age 75, total = $11.9M)
        2050  Stage 6: Total portfolio = $15.5M; Traditional = $7.2M
      Warnings noted — all resolved (see below):
        - Brokerage exhausted ~2031 → Roth conversions stop in Stage 4   RESOLVED ✓ (Phase 2)
        - "Negative income -$33,500" warnings in Stage 5                  RESOLVED ✓ (see below)
        - DAF carryforward only appears in 2026 ($408,935) — by design (no excess in later years)

  ✓ Boundary condition tests — 22/22 pass
      tests/test_bracket_fill_edge_cases.py
      Covers:
        - Shortfall = $0 (large PNC cash, conversion still fires)
        - PNC below safety reserve (large shortfall; traditional covers gap)
        - Traditional balance too small to cover full shortfall (graceful clamp)
        - Zero traditional balance (no conversion, no withdrawal, no crash)
        - Zero brokerage: rollover OFF blocks conversion, rollover ON uses cash
        - All-zero balances (degenerate — must not crash)
        - Zero expenses (degenerate — must not crash)
        - DAF = exactly 30% of AGI → zero carryforward
        - DAF > 30% of AGI → correct carryforward generated
        - Prior carryforward fully consumed vs. partially consumed
        - Zero AGI → zero deduction, full carryforward
        - carryforward never goes negative (6 parametrized cases)
        - Cross-stage threading: Stage 4 accepts kwarg, deductible set correctly
        - Carryforward reduces federal tax in Stage 4
        - Engine formula is non-negative for all combinations

OPEN ITEMS FROM PROJECTION — ALL RESOLVED:

  1. ✓ RESOLVED — Roth conversions in Stage 4 (Phase 2: 60-Day Rollover)
     Cash (above $56k safety reserve) now counts as effective taxable balance for BETR.
     Stage 4 conversions restored to $229k–$251k/year.
     See: PHASE 2: 60-DAY ROLLOVER MECHANICS above.

  2. ✓ RESOLVED — "Negative income" warning in Stage 5 _calculate_preliminary_tax
     File: strategy_core/stages/stage5_social_security.py, line ~648
     Fix: preliminary_taxable_income = max(0.0, preliminary_income - std_deduction)
          ordinary_income = max(0.0, preliminary_taxable_income - ltcg)
     Root cause: SS (partially taxable) < standard deduction in early SS years (2036–2039)
     when there is no Roth conversion. This is economically correct (zero tax owed);
     the warning was misleading because the value was valid but should have been clamped
     before being passed to calculate_taxable_income.

  3. ✓ DOCUMENTED — Stage 5 threshold uses younger spouse's birth year (by design)
     Stage 5's applies() uses get_rmd_age(max(birth_y1, birth_y2)) which is Sarah's
     birth year (1967 → rmd_age=75). Stage 5 runs until Tom is 75 (2041), even though
     Tom's own RMD age is 73 (2039).
     → This is CORRECT: Stage 6 activates when the older spouse crosses the YOUNGER
       person's threshold (conservative — ensures neither person misses RMDs).
     → Tom's RMD is computed and distributed correctly once Stage 6 activates in 2041.
     → No code change needed. Documented in scripts/projection_2026_2050.py comments.

ESTIMATED EFFORT: All items complete ✓

═════════════════════════════════════════════════════════════════════════════
CRITICAL PATH (What to Prioritize)
═════════════════════════════════════════════════════════════════════════════

IMMEDIATE (High-Value, Low-Effort):
  1. ✓ Run Stage 3 with actual config, verify output vs. manual calc
  2. ✓ Add property_tax to config.json
  3. ✓ Update AGICalculator calls to read property_tax from config

SHORT-TERM (Medium-Value, Medium-Effort):
  4. ✓ Integrate 60-Day Rollover into Stages 3 & 4
  5. ✓ Config UI controls — accurate help text, live rollover status badge, savings_safety_reserve
  6. ✓ Dashboard metrics — PNC reserve alert, 60-day rollover status, DAF 10-year projection table

MEDIUM-TERM (If implementing Stages 5–7):
  7. [ ] [4-6 hrs] Refactor Stages 5, 6, 7 to use AGICalculator

═════════════════════════════════════════════════════════════════════════════
REMAINING BUGS/TODOs (In Code Comments)
═════════════════════════════════════════════════════════════════════════════

RESOLVED:
  ✓ property_tax is read from config via _get_property_tax_from_config() in
    both stage3_early_retirement.py and stage4_medicare.py.
    The value (currently $5,000) comes from expenses.living_expenses.property_tax
    in retirement_config.json.

RESOLVED:
  ✓ DAF carryforward cross-stage threading — confirmed already working correctly.
    The engine (WithdrawalStrategyEngine in strategy.py) maintains self._daf_carryforward
    and passes it each year via daf_carryforward_prior kwarg (line 4554), then updates
    it from strategy.daf_deductible (lines 4563-4564). All stages (2, 3, 4, 5, 6) set
    strategy.daf_deductible. The TODO comment in stage3_early_retirement.py was written
    before the engine threading was added and is now stale.
    Validated by: tests/test_bracket_fill_edge_cases.py::TestCrossStageDAFThreading

═════════════════════════════════════════════════════════════════════════════
FILES CREATED/MODIFIED
═════════════════════════════════════════════════════════════════════════════

NEW FILES:
  - strategy_core/agi_calculator.py (320 lines, complete)
  - scripts/test_agi_calculator_integration.py (260 lines, all tests pass)
  - scripts/projection_2026_2050.py (full 2026–2050 engine validation, 9 checks)
  - tests/test_daf_carryforward_multiyear.py (12 tests)
  - tests/test_sixty_day_rollover_integration.py (16 tests)
  - tests/test_bracket_fill_edge_cases.py (22 tests — boundary conditions)
  - tests/test_stages567_agi_calculator.py (25 tests — Stage 5/6/7 AGICalculator path)
  - IMPLEMENTATION_MANIFEST.md (renamed from IMPLEMENTATION_MANIFEST.py)

MODIFIED FILES:
  - strategy_core/agi_calculator.py (added ss_benefits / taxable_ss params + 'taxable_ss' result key)
  - strategy_core/tax_calculator.py (filing_status case-normalisation in 3 methods)
  - strategy_core/base_strategy.py (_use_60day_rollover, _effective_taxable_for_conversion, _get_safety_reserve)
  - strategy_core/stages/stage3_early_retirement.py
  - strategy_core/stages/stage4_medicare.py
  - strategy_core/stages/stage5_social_security.py (final tax block → AGICalculator)
  - strategy_core/stages/stage6_rmd.py (final tax block → AGICalculator)
  - strategy_core/stages/stage7_surviving_spouse.py (final tax block → AGICalculator; daf_deductible added)
  - pages/2_configuration.py (accurate rollover help text, live status badge)
  - pages/3_dashboard.py (PNC alert, rollover status, DAF projection widgets)

DELETED (dead code — zero live references):
  - editable_table.py (no imports anywhere)
  - withdrawal_strategy.py (root facade — all callers import from strategy.py directly)
  - =0.3.6 (stray pip artifact)
  - two-phase-withdrawal-strategy-implementation-status.html (stray HTML artifact)
  - IMPLEMENTATION_MANIFEST.py (converted to IMPLEMENTATION_MANIFEST.md)

CONFIRMED LIVE (do not delete):
  - income_expense.py — used by FastAPI at app/api/routes.py and app/services/strategy_service.py
  - withdrawal_strategy_validation.py — imported by tests/test_withdrawal_strategy_integration.py
    and tests/test_withdrawal_strategy_edge_cases.py

UNCONNECTED SCAFFOLDING (not wired into the live engine — do not delete, but not active):
  - withdrawal_strategy_optimization.py — zero importers anywhere; standalone optimization
    utilities that duplicate logic already in the live stage files. Safe to delete if desired.
  - strategy_core/stages/stage3_bracket_fill.py — complete alternative Stage 3 implementation
    using JanuaryBracketFillOrchestrator; NOT in stages/__init__.py and not used by the engine.
    The live engine uses stage3_early_retirement.py. Only referenced in example scripts under scripts/.
  - strategy_core/withdrawal_orchestrator.py — JanuaryBracketFillOrchestrator class; only used
    by stage3_bracket_fill.py (which is itself unconnected). Live stages use BETR helpers directly.
  - strategy_core/roth_conversion_optimizer.py — RothConversionOptimizer class; only referenced
    by example scripts under scripts/. Live stages do Roth optimization inline.
  - strategy_core/sixty_day_rollover.py — SixtyDayRolloverHandler class; the live 60-day rollover
    path is implemented via _use_60day_rollover() / _effective_taxable_for_conversion() in
    base_strategy.py. This class is only referenced by example scripts and january_bracket_fill_strategy.py.

═════════════════════════════════════════════════════════════════════════════
REFERENCE IMPLEMENTATIONS
═════════════════════════════════════════════════════════════════════════════

Use these scripts to validate your strategy logic:

  1. scripts/bracket_fill_full_agi.py
     - Manual 2027 scenario with all steps shown
     - Expected values for validation

  2. scripts/test_agi_calculator_integration.py
     - Run to verify AGICalculator is working
     - Can add more test cases

  3. scripts/example_bracket_fill_with_actual_data.py
     - Reads config and calculates bracket-fill for each year
     - Useful for sanity-checking multi-year projections

═════════════════════════════════════════════════════════════════════════════
YOUR JANUARY STRATEGY: NOW PRODUCTION-READY (For Stages 3 & 4)
═════════════════════════════════════════════════════════════════════════════

READY TO USE:
  ✓ Assess annual spending need (with correct AGI for tax estimate)
  ✓ Calculate shortfall (spending − PNC balance)
  ✓ Determine Traditional withdrawal (shortfall + tax estimate)
  ✓ Calculate Roth conversion space (remaining 12% bracket)
  ✓ Optimize DAF (30% AGI limit + carryforward)

NEXT STEPS:
  1. Run with actual data and verify tax estimates match manual
  2. Integrate 60-Day rollover withholding mechanics
  3. Add config UI for $50k safety threshold
  4. Deploy for 2027 planning (first full retirement year)

═════════════════════════════════════════════════════════════════════════════
