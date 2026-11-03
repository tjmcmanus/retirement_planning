# Implementation Manifest: January Bracket-Fill Strategy

> **Developer note** — quick-start guide and file manifest.

---

## LIVE ENGINE FILES (Active — wired into `strategy.py`)

The live withdrawal engine imports from `strategy_core/stages/__init__.py`, which exports:

| File | Class | Status |
|---|---|---|
| `strategy_core/stages/stage1_accumulation.py` | `Stage1Accumulation` | Live ✓ |
| `strategy_core/stages/stage2_prep_retirement.py` | `Stage2PrepForRetirement` | Live ✓ |
| `strategy_core/stages/stage3_early_retirement.py` | `Stage3EarlyRetirement` | Live ✓ |
| `strategy_core/stages/stage4_medicare.py` | `Stage4Medicare` | Live ✓ |
| `strategy_core/stages/stage5_social_security.py` | `Stage5SocialSecurity` | Live ✓ |
| `strategy_core/stages/stage6_rmd.py` | `Stage6RMD` | Live ✓ |
| `strategy_core/stages/stage7_surviving_spouse.py` | `Stage7SurvivingSpouse` | Live ✓ |

Supporting live files:

| File | Purpose | Status |
|---|---|---|
| `strategy_core/base_strategy.py` | `BaseLifeStageStrategy` + rollover/DAF helpers | Live ✓ |
| `strategy_core/agi_calculator.py` | `AGICalculator` (IRC-compliant AGI/tax calc) | Live ✓ |
| `strategy_core/tax_calculator.py` | `TaxCalculator` | Live ✓ |
| `strategy_core/account_manager.py` | `AccountManager` | Live ✓ |
| `strategy_core/decision_logger.py` | `DecisionLogger` | Live ✓ |
| `strategy_core/models.py` | Dataclasses (`YearlyStrategy`, `PortfolioBalances`, …) | Live ✓ |
| `strategy_core/interfaces.py` | Abstract interfaces | Live ✓ |
| `strategy_core/january_bracket_fill_strategy.py` | `JanuaryBracketFillStrategy` (used in Stage 3) | Live ✓ |
| `strategy_core/savings_account_tracker.py` | Used by `january_bracket_fill_strategy.py` | Live ✓ |

---

## UNCONNECTED SCAFFOLDING (Not wired into the live engine)

These files are complete implementations but are **not imported by the live engine**. They are
referenced only by example/validation scripts under `scripts/`. Do not delete without reading
`IMPLEMENTATION_ROADMAP.md` first.

**`strategy_core/stages/stage3_bracket_fill.py`**
- **class**: `Stage3EarlyRetirementBracketFill`
- **purpose**: Alternative Stage 3 using `JanuaryBracketFillOrchestrator` with ACA optimization
- **status**: ⚠️ NOT in `stages/__init__.py` — engine uses `stage3_early_retirement.py` instead
- **note**: Would replace the live Stage 3 if wired in. Depends on `withdrawal_orchestrator.py`.

**`strategy_core/withdrawal_orchestrator.py`**
- **class**: `JanuaryBracketFillOrchestrator`
- **purpose**: Bracket-fill withdrawal calculation engine
- **status**: ⚠️ Only used by `stage3_bracket_fill.py` (which is itself unconnected)
- **note**: Live stages do equivalent calculations inline with BETR helpers.

**`strategy_core/roth_conversion_optimizer.py`**
- **class**: `RothConversionOptimizer`
- **purpose**: DAF → RMD → BETR Roth conversion priority optimizer
- **status**: ⚠️ Only referenced by example scripts under `scripts/`
- **note**: Live stages do Roth optimization inline.

**`strategy_core/sixty_day_rollover.py`**
- **class**: `SixtyDayRolloverHandler`
- **purpose**: IRS 60-day rollover rule for Roth conversion withholding
- **status**: ⚠️ Only referenced by example scripts and `january_bracket_fill_strategy.py`
- **note**: Live rollover path uses `_use_60day_rollover()` / `_effective_taxable_for_conversion()`
  in `base_strategy.py` directly — this class is not called at runtime.



## EXAMPLE & TESTING FILES


**`scripts/example_bracket_fill_strategy.py`**
- **type**: `Runnable Example`
- **lines**: 280
- **purpose**: `End-to-end example showing how to use all three modules`
- **how_to_run**: `python scripts/example_bracket_fill_strategy.py`
- **customization**: `Edit values in example_january_bracket_fill() function with your data`
- **status**: `Ready to run`



## CONFIGURATION REQUIREMENTS






## QUICK START GUIDE







## MODULE DEPENDENCIES






## TESTING CHECKLIST







## USAGE EXAMPLES


## Simple usage: Calculate your 2026 withdrawal plan





## With Roth conversion optimization




## With 60-day rollover planning





## DOCUMENTATION ARTIFACTS (HTML — no longer present)

The following HTML artifacts were generated during early design and have been removed:

- `withdrawal_strategy_review.html` — early BETR vs. bracket-fill comparison (deleted)
- `pnc_cash_strategy.html` — PNC cash/rebalancing distinction (deleted)
- `january_bracket_fill_strategy.html` — original 7-step workflow spec (deleted)
- `bracket_fill_implementation.html` — early implementation guide (deleted)
- `bracket_fill_summary.html` — early complete summary (deleted)
- `bracket_fill_quick_ref.html` — quick reference (deleted)
- `bracket_fill_project_complete.html` — project complete summary (deleted)

Current documentation is in `IMPLEMENTATION_ROADMAP.md` and `JANUARY_STRATEGY_CHANGES.md`.



## SUPPORT & TROUBLESHOOTING











