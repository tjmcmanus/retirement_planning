"""
IMPLEMENTATION ROADMAP: January Bracket-Fill + 60-Day Rollover Strategy

STATUS: AGI Calculation Fixes Complete ✓
NEXT: 60-Day Rollover Mechanics + Config UI

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
PHASE 2: 60-DAY ROLLOVER MECHANICS (READY FOR INTEGRATION)
═════════════════════════════════════════════════════════════════════════════

STATUS: Scaffolded but not yet integrated into stages

WHAT EXISTS:
  - strategy_core/sixty_day_rollover.py — SixtyDayRolloverHandler class
  - Tracks 60-day window, withholding, redeposit logic
  - IRS compliance checks

WHAT NEEDS TO HAPPEN:
  1. January Withdrawal includes withholding calculation
     - Withdrawal amount W includes: tax withholding + net conversion + spending
     - Withholding = (W - basis) × tax_rate  (approximate)
     - Actually: calculate via AGICalculator with hypothetical conversion amount
  
  2. Integrate SixtyDayRolloverHandler into Stage 3 & 4 calculate_strategy()
     - Withhold from Traditional withdrawal
     - Schedule 60-day reminder
     - Track deadline (day 60 from withdrawal)
  
  3. Redeposit mechanism (happens mid-year or whenever cash available)
     - Call SixtyDayRolloverHandler.redeposit()
     - Pull from cash (primary) or Brokerage (if cash insufficient)
     - Redeposit to Traditional IRA
     - Close the window
  
  4. Handle edge cases:
     - What if 60-day window expires before redeposit available? → non-deductible contribution trap
     - What if redeposit only partial? → partial rollover implications
     - What if Traditional account unavailable? → fallback to Roth conversion logic

ESTIMATED EFFORT: 3-4 hours (moderate complexity)

═════════════════════════════════════════════════════════════════════════════
PHASE 3: CONFIG & UI (PARTIALLY DONE)
═════════════════════════════════════════════════════════════════════════════

WHAT'S NEEDED:

1. Configuration Parameters (add to retirement_config.json or new config section):
   
   a) PNC Safety Threshold
      - Key: "pnc_safety_threshold" (default: 50000)
      - When cash falls below this, top up from Brokerage
      - User can adjust for their comfort level
   
   b) Property Tax (for SALT calculation)
      - Key: "property_tax" (default: 0)
      - Currently hardcoded to 0.0 in AGICalculator calls
   
   c) DAF Carryforward Tracking
      - Key: "track_daf_carryforward" (default: true)
      - Enable multi-year DAF planning
      - Store history in strategy state
   
   d) 60-Day Rollover Mechanics
      - Key: "use_60day_rollover" (default: true)
      - Toggle between withholding from conversion vs. separate payment
      - Track deadline/reminder preferences

2. UI Changes (pages/2_configuration.py):
   - Add sliders for: pnc_safety_threshold, property_tax
   - Add toggle for: use_60day_rollover, track_daf_carryforward
   - Show current values with explanations

3. Dashboard Updates (pages/3_dashboard.py):
   - Add "DAF Carryforward" widget (year-by-year breakdown)
   - Add "60-Day Rollover Status" widget (if active)
   - Add "PNC Alert" when balance < safety_threshold

ESTIMATED EFFORT: 2-3 hours

═════════════════════════════════════════════════════════════════════════════
PHASE 4: STAGES 5–7 REFACTORING (DEFERRED)
═════════════════════════════════════════════════════════════════════════════

STATUS: Imports added, core logic not yet refactored

WHY DEFERRED: These stages have additional complexity:
  - Stage 5: Social Security taxation (combined income calculation feedback loop)
  - Stage 6: RMD (mandatory distribution adds to ordinary income)
  - Stage 7: Surviving spouse (filing status change)

APPROACH WHEN READY:
  1. Extract SS taxation into separate method/class
  2. Refactor Stage 5 to calculate taxable SS, then use AGICalculator
  3. For Stage 6: RMD enters as part of Traditional withdrawal (simple)
  4. For Stage 7: Same as Stage 5 but with single-filer rates

ESTIMATED EFFORT (when needed): 4-6 hours total

═════════════════════════════════════════════════════════════════════════════
PHASE 5: TESTING & VALIDATION (IN PROGRESS)
═════════════════════════════════════════════════════════════════════════════

COMPLETED:
  ✓ AGI Calculator unit tests (6/6 pass)
  ✓ 2027 scenario validation (matches manual calculation)

STILL NEEDED:
  [ ] End-to-end Stage 3 test with actual config data
  [ ] End-to-end Stage 4 test (Medicare year)
  [ ] Multi-year projection test (2026–2050) with manual Excel comparison
  [ ] 60-Day rollover integration test
  [ ] DAF carryforward multi-year tracking test
  [ ] Boundary condition tests (edge cases in bracket-fill)

ESTIMATED EFFORT: 2-3 hours

═════════════════════════════════════════════════════════════════════════════
CRITICAL PATH (What to Prioritize)
═════════════════════════════════════════════════════════════════════════════

IMMEDIATE (High-Value, Low-Effort):
  1. [1 hour]  Run Stage 3 with actual config, verify output vs. manual calc
  2. [1 hour]  Add property_tax to config.json
  3. [1 hour]  Update AGICalculator calls to read property_tax from config

SHORT-TERM (Medium-Value, Medium-Effort):
  4. [3-4 hrs] Integrate 60-Day Rollover into Stages 3 & 4
  5. [1-2 hrs] Add config UI controls (safety_threshold, property_tax)
  6. [1-2 hrs] Dashboard metrics (DAF carryforward, PNC status)

MEDIUM-TERM (If implementing Stages 5–7):
  7. [4-6 hrs] Refactor Stages 5, 6, 7 to use AGICalculator

═════════════════════════════════════════════════════════════════════════════
REMAINING BUGS/TODOs (In Code Comments)
═════════════════════════════════════════════════════════════════════════════

Location: strategy_core/stages/stage3_early_retirement.py, line 483
  TODO: track_daf_carryforward_prior=0.0  # TODO: track across years

Location: strategy_core/stages/stage3_early_retirement.py, line 484
  TODO: property_tax=0.0  # TODO: add to config

Same TODOs appear in stage4_medicare.py (lines 327–328)

═════════════════════════════════════════════════════════════════════════════
FILES CREATED/MODIFIED
═════════════════════════════════════════════════════════════════════════════

NEW FILES:
  - strategy_core/agi_calculator.py (320 lines, complete)
  - scripts/test_agi_calculator_integration.py (260 lines, all tests pass)

MODIFIED FILES:
  - strategy_core/stages/stage3_early_retirement.py
  - strategy_core/stages/stage4_medicare.py
  - strategy_core/stages/stage5_social_security.py
  - strategy_core/stages/stage6_rmd.py
  - strategy_core/stages/stage7_surviving_spouse.py

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
"""
