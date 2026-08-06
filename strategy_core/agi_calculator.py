"""
AGI Calculator with Correct Order

Implements the correct IRC-compliant AGI calculation order:
  1. Gross Ordinary Income = Traditional + Roth Conversion + Brokerage Basis
  2. Pre-deduction AGI = Gross Ordinary + LTCG
  3. DAF 30% limit = 30% × Pre-deduction AGI
  4. Deduction = max(Itemized, Standard) where Itemized = DAF (capped) + SALT (capped $10k)
  5. Taxable Ordinary = Gross Ordinary − Deduction
  6. LTCG stacks on top of Taxable Ordinary for LTCG bracket calculation

DAF key points:
  - Source: appreciated Brokerage stock (no income event, embedded gain eliminated)
  - Deductible: up to 30% of AGI in year of contribution (IRC §170)
  - Carryforward: excess carries forward up to 5 years
  - This module tracks carryforward state if needed for multi-year analysis

LTCG key points:
  - LTCG is included in AGI for DAF limit calculation
  - But LTCG brackets stack on top of taxable ORDINARY income
  - PA does not tax LTCG (state calculation separate)
"""

import logging
from typing import Dict, Tuple, Optional

logger = logging.getLogger(__name__)


class DAFCarryforwardTracker:
    """
    Tracks DAF carryforward amounts across years.
    
    Per IRC §170, excess DAF deduction carries forward up to 5 years.
    This is useful for multi-year planning but each year's calculation
    is independent (current year uses available carryforward + current year amount).
    """
    
    def __init__(self):
        """Initialize carryforward tracker with no prior balance."""
        self.carryforward_balance = 0.0
        self.carryforward_history = []
    
    def add_carryforward(self, amount: float, year: int):
        """Add to carryforward balance (from prior year or current year excess)."""
        if amount > 0:
            self.carryforward_balance += amount
            self.carryforward_history.append({
                'year': year,
                'added': amount,
                'balance': self.carryforward_balance
            })
            logger.debug(f"DAF carryforward: +${amount:,.0f} (balance now ${self.carryforward_balance:,.0f})")
    
    def use_carryforward(self, amount: float, year: int) -> float:
        """Use carryforward; return amount actually used (clamped to balance)."""
        used = min(amount, self.carryforward_balance)
        self.carryforward_balance -= used
        if used > 0:
            self.carryforward_history.append({
                'year': year,
                'used': -used,
                'balance': self.carryforward_balance
            })
            logger.debug(f"DAF carryforward: -${used:,.0f} (balance now ${self.carryforward_balance:,.0f})")
        return used
    
    def get_balance(self) -> float:
        """Return current carryforward balance."""
        return self.carryforward_balance


class AGICalculator:
    """
    Correct AGI calculation with proper order and DAF/LTCG handling.
    """
    
    def __init__(self, tax_calculator=None):
        """
        Initialize AGI calculator.
        
        Args:
            tax_calculator: TaxCalculator instance for standard deduction lookup
        """
        self.tax_calculator = tax_calculator
    
    def calculate_agi_and_taxes(
        self,
        year: int,
        filing_status: str,
        age_primary: int,
        age_spouse: int,
        traditional_withdrawal: float,
        roth_conversion: float,
        brokerage_ltcg: float,
        brokerage_basis: float = 0.0,
        daf_fmv: float = 0.0,
        state: str = 'PA',
        pa_rate: float = 0.0307,
        property_tax: float = 0.0,
        daf_carryforward_prior: float = 0.0,
        tax_calculator=None
    ) -> Dict:
        """
        Calculate AGI and taxes with correct order.
        
        STEP 1: Gross Ordinary Income
          = Traditional + Roth Conversion
          (NOT including Brokerage basis — basis is return of capital, not income)
        
        STEP 2: Pre-deduction AGI
          = Gross Ordinary + LTCG
          (used for 30% DAF limit calculation)
        
        STEP 3: DAF Deduction
          - DAF FMV available this year
          - 30% AGI limit
          - Use carryforward if available
          - Excess carries forward
        
        STEP 4: Itemized vs. Standard Deduction
          - Itemized = DAF deductible + SALT (capped $10k)
          - Standard = age-adjusted per IRS tables
          - Use max of two
        
        STEP 5: Taxable Ordinary Income
          = Gross Ordinary - Deduction
        
        STEP 6: Federal Ordinary Tax
          - Tax calculator on Taxable Ordinary
          - Max rate and bracket tracking
        
        STEP 7: LTCG Tax
          - LTCG stacks on top of Taxable Ordinary
          - Use LTCG-specific brackets
        
        STEP 8: State Tax
          - On Taxable Ordinary only (PA doesn't tax LTCG)
        
        Args:
            year: Tax year
            filing_status: 'married_filing_jointly', 'single', etc.
            age_primary: Primary taxpayer age
            age_spouse: Spouse age
            traditional_withdrawal: Traditional IRA/401k withdrawal (before conversions/withholding)
            roth_conversion: Roth conversion amount (ordinary income)
            brokerage_ltcg: Long-term capital gain realized (ONLY the gain, not basis)
            brokerage_basis: Basis portion of brokerage sale (NOT taxable income; used for cash flow only)
            daf_fmv: DAF stock transfer FMV this year (no income event)
            state: State code for state tax
            pa_rate: PA state tax rate
            property_tax: Property tax for SALT calculation
            daf_carryforward_prior: DAF carryforward from prior years (if any)
            tax_calculator: Optional tax calculator (uses self.tax_calculator if not provided)
        
        Returns:
            Dict with complete AGI and tax breakdown:
              {
                'gross_ordinary': float,
                'agi_pre_deduction': float,
                'daf_30pct_limit': float,
                'daf_deductible_this_year': float,
                'daf_carryforward_new': float,
                'salt': float,
                'itemized_deduction': float,
                'std_deduction': float,
                'deduction': float,
                'deduction_type': str,  # 'ITEMIZED' or 'STANDARD'
                'taxable_ordinary': float,
                'federal_ordinary_tax': float,
                'ltcg_tax': float,
                'state_tax': float,
                'total_tax': float,
                'max_federal_rate': float,
                'upper_bracket': float,
              }
        """
        calc = tax_calculator or self.tax_calculator
        if not calc:
            raise ValueError("tax_calculator required but not provided")
        
        logger.debug(
            f"AGI calculation for year {year}: "
            f"trad=${traditional_withdrawal:,.0f}, "
            f"roth=${roth_conversion:,.0f}, "
            f"ltcg=${brokerage_ltcg:,.0f}, "
            f"basis=${brokerage_basis:,.0f}, "
            f"daf=${daf_fmv:,.0f}"
        )
        
        # ─────────────────────────────────────────────────────────────────────────
        # STEP 1: Gross Ordinary Income
        # NOTE: Brokerage BASIS is NOT included. Basis is return of capital (already-taxed money).
        # Only GAINS are taxable income. Basis is used for cash flow but not AGI.
        # ─────────────────────────────────────────────────────────────────────────
        gross_ordinary = traditional_withdrawal + roth_conversion
        logger.debug(f"Gross ordinary: {traditional_withdrawal} + {roth_conversion} = {gross_ordinary}")
        
        # ─────────────────────────────────────────────────────────────────────────
        # STEP 2: Pre-deduction AGI (used for 30% DAF limit)
        # ─────────────────────────────────────────────────────────────────────────
        agi_pre_deduction = gross_ordinary + brokerage_ltcg
        logger.debug(f"AGI pre-deduction: {gross_ordinary} + {brokerage_ltcg} = {agi_pre_deduction}")
        
        # ─────────────────────────────────────────────────────────────────────────
        # STEP 3: DAF Deduction (with 30% AGI limit and carryforward)
        # ─────────────────────────────────────────────────────────────────────────
        daf_30pct_limit = agi_pre_deduction * 0.30
        
        # Available DAF = current year + carryforward (up to limit)
        available_daf = daf_fmv + daf_carryforward_prior
        
        # Deductible this year (up to 30% limit)
        daf_deductible_this_year = min(available_daf, daf_30pct_limit)
        
        # Carryforward (any excess, not deductible this year)
        daf_carryforward_new = available_daf - daf_deductible_this_year
        
        logger.debug(
            f"DAF deduction: FMV={daf_fmv:,.0f}, "
            f"carryforward_prior={daf_carryforward_prior:,.0f}, "
            f"available={available_daf:,.0f}, "
            f"30%_limit={daf_30pct_limit:,.0f}, "
            f"deductible={daf_deductible_this_year:,.0f}, "
            f"carryforward_new={daf_carryforward_new:,.0f}"
        )
        
        # ─────────────────────────────────────────────────────────────────────────
        # STEP 4: Itemized vs. Standard Deduction
        # ─────────────────────────────────────────────────────────────────────────
        
        # Get standard deduction (age-adjusted)
        std_deduction = calc.calculate_standard_deduction(
            filing_status, year, age_primary, age_spouse
        )
        
        # Calculate state income tax estimate for SALT
        state_income_estimate = gross_ordinary * pa_rate
        salt = min(state_income_estimate + property_tax, 10000)  # SALT capped at $10k
        
        # Itemized deduction = DAF (capped) + SALT (capped)
        itemized_deduction = daf_deductible_this_year + salt
        
        # Use itemized if greater than standard
        use_itemized = itemized_deduction > std_deduction
        deduction = itemized_deduction if use_itemized else std_deduction
        deduction_type = "ITEMIZED" if use_itemized else "STANDARD"
        
        logger.debug(
            f"Deduction: std={std_deduction:,.0f}, "
            f"itemized={itemized_deduction:,.0f} (DAF {daf_deductible_this_year:,.0f} + SALT {salt:,.0f}), "
            f"using {deduction_type}=${deduction:,.0f}"
        )
        
        # ─────────────────────────────────────────────────────────────────────────
        # STEP 5: Taxable Ordinary Income
        # ─────────────────────────────────────────────────────────────────────────
        taxable_ordinary = max(0, gross_ordinary - deduction)
        logger.debug(f"Taxable ordinary: {gross_ordinary} - {deduction} = {taxable_ordinary}")
        
        # ─────────────────────────────────────────────────────────────────────────
        # STEP 6: Federal Ordinary Income Tax
        # ─────────────────────────────────────────────────────────────────────────
        federal_ordinary_tax, max_federal_rate, upper_bracket = calc.calculate_federal_tax(
            taxable_ordinary, filing_status, year
        )
        logger.debug(
            f"Federal ordinary tax: ${federal_ordinary_tax:,.0f} "
            f"(taxable=${taxable_ordinary:,.0f}, max_rate={max_federal_rate:.1%})"
        )
        
        # ─────────────────────────────────────────────────────────────────────────
        # STEP 7: LTCG Tax (stacked on top of taxable ordinary)
        # ─────────────────────────────────────────────────────────────────────────
        ltcg_tax = calc.calculate_capital_gains_tax(
            brokerage_ltcg, taxable_ordinary, filing_status, year
        )
        logger.debug(
            f"LTCG tax: ${ltcg_tax:,.0f} "
            f"(ltcg=${brokerage_ltcg:,.0f}, stacked on ordinary=${taxable_ordinary:,.0f})"
        )
        
        # ─────────────────────────────────────────────────────────────────────────
        # STEP 8: State Tax (PA: ordinary only, no LTCG)
        # ─────────────────────────────────────────────────────────────────────────
        state_tax = calc.calculate_state_tax(
            agi=agi_pre_deduction,
            state=state,
            year=year,
            filing_status=filing_status,
            retirement_income=traditional_withdrawal,
            ss_benefits=0.0,  # Stage 3 (pre-SS) use case; override if SS present
            roth_conversion=roth_conversion
        )
        logger.debug(f"State tax ({state}): ${state_tax:,.0f}")
        
        # ─────────────────────────────────────────────────────────────────────────
        # TOTALS
        # ─────────────────────────────────────────────────────────────────────────
        total_tax = federal_ordinary_tax + ltcg_tax + state_tax
        logger.debug(
            f"Total tax: ${federal_ordinary_tax:,.0f} (fed ordinary) + "
            f"${ltcg_tax:,.0f} (LTCG) + ${state_tax:,.0f} ({state}) = ${total_tax:,.0f}"
        )
        
        return {
            'gross_ordinary': gross_ordinary,
            'agi_pre_deduction': agi_pre_deduction,
            'daf_30pct_limit': daf_30pct_limit,
            'daf_deductible_this_year': daf_deductible_this_year,
            'daf_carryforward_new': daf_carryforward_new,
            'salt': salt,
            'itemized_deduction': itemized_deduction,
            'std_deduction': std_deduction,
            'deduction': deduction,
            'deduction_type': deduction_type,
            'taxable_ordinary': taxable_ordinary,
            'federal_ordinary_tax': federal_ordinary_tax,
            'ltcg_tax': ltcg_tax,
            'state_tax': state_tax,
            'total_tax': total_tax,
            'max_federal_rate': max_federal_rate,
            'upper_bracket': upper_bracket,
        }
