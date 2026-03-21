"""
Estate Tax Calculations Module

Provides comprehensive estate tax calculations including:
- Federal estate tax with TCJA sunset modeling
- State estate and inheritance taxes
- Generation-Skipping Transfer Tax (GSTT) analysis
- Portability calculations for married couples
- Annual exclusion gift tracking

References:
- IRC §2001-2210 (Estate Tax)
- IRC §2601-2664 (Generation-Skipping Transfer Tax)
- TCJA (Tax Cuts and Jobs Act) sunset provisions
"""

import pandas as pd
import numpy as np
import logging
import os
from typing import Dict, List, Tuple, Optional, NamedTuple, Any
from datetime import datetime

# Configure logging
log_level = logging.getLevelName(os.getenv('LOG_LEVEL', 'WARNING'))
logging.basicConfig(
    level=log_level,
    format='%(asctime)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


# ==============================================================================
# FEDERAL ESTATE TAX CONSTANTS
# ==============================================================================

# TCJA (Tax Cuts and Jobs Act) doubled the estate tax exemption from 2018-2025
# After 2025, it reverts to pre-TCJA levels (adjusted for inflation)

# Historical and projected federal estate tax exemptions
FEDERAL_ESTATE_TAX_EXEMPTIONS = {
    2023: 12_920_000,   # Actual
    2024: 13_610_000,   # Actual
    2025: 13_990_000,   # Projected (TCJA still in effect)
    2026: 7_110_000,    # Projected (TCJA sunset - reverts to ~50% of 2025 level)
    2027: 7_320_000,    # Projected with inflation
    2028: 7_540_000,    # Projected with inflation
    2029: 7_770_000,    # Projected with inflation
    2030: 8_000_000,    # Projected with inflation
    2031: 8_240_000,    # Projected with inflation
    2032: 8_490_000,    # Projected with inflation
    2033: 8_740_000,    # Projected with inflation
    2034: 9_000_000,    # Projected with inflation
    2035: 9_270_000,    # Projected with inflation
}

# Federal estate tax rate (flat rate above exemption)
FEDERAL_ESTATE_TAX_RATE = 0.40  # 40%

# Annual gift tax exclusion (per recipient)
ANNUAL_GIFT_EXCLUSION = {
    2023: 17_000,
    2024: 18_000,
    2025: 18_000,
    2026: 19_000,  # Projected
    2027: 19_000,
    2028: 20_000,
    2029: 20_000,
    2030: 21_000,
}

# Generation-Skipping Transfer Tax (GSTT) exemption (same as estate tax exemption)
GSTT_EXEMPTIONS = FEDERAL_ESTATE_TAX_EXEMPTIONS.copy()
GSTT_TAX_RATE = 0.40  # 40% flat rate


# ==============================================================================
# STATE ESTATE AND INHERITANCE TAX DATA
# ==============================================================================

# States with estate taxes (as of 2024)
# Format: state_code: (exemption_amount, rates_dict, notes)
STATE_ESTATE_TAXES = {
    'CT': {
        'name': 'Connecticut',
        'exemption': 13_610_000,  # Matches federal (2024)
        'rates': [
            (0, 10_100_000, 0.10),
            (10_100_000, 10_600_000, 0.11),
            (10_600_000, 11_100_000, 0.115),
            (11_100_000, float('inf'), 0.12),
        ],
        'notes': 'Matches federal exemption since 2023'
    },
    'DC': {
        'name': 'District of Columbia',
        'exemption': 4_528_800,  # 2024
        'rates': [
            (0, 1_000_000, 0.12),
            (1_000_000, float('inf'), 0.16),
        ],
        'notes': 'Progressive rates from 11.2% to 16%'
    },
    'HI': {
        'name': 'Hawaii',
        'exemption': 5_490_000,  # 2024
        'rates': [
            (0, 2_000_000, 0.10),
            (2_000_000, 4_000_000, 0.15),
            (4_000_000, float('inf'), 0.20),
        ],
        'notes': 'Progressive rates from 10% to 20%'
    },
    'IL': {
        'name': 'Illinois',
        'exemption': 4_000_000,  # 2024
        'rates': [
            (0, 4_000_000, 0.00),
            (4_000_000, float('inf'), 0.16),
        ],
        'notes': 'Flat 16% rate above exemption'
    },
    'ME': {
        'name': 'Maine',
        'exemption': 6_410_000,  # 2024
        'rates': [
            (0, 6_410_000, 0.08),
            (6_410_000, 9_410_000, 0.10),
            (9_410_000, float('inf'), 0.12),
        ],
        'notes': 'Progressive rates from 8% to 12%'
    },
    'MD': {
        'name': 'Maryland',
        'exemption': 5_000_000,  # 2024
        'rates': [
            (0, 5_000_000, 0.00),
            (5_000_000, float('inf'), 0.16),
        ],
        'notes': 'Flat 16% rate above exemption; also has inheritance tax'
    },
    'MA': {
        'name': 'Massachusetts',
        'exemption': 2_000_000,  # 2024 (lowest in nation)
        'rates': [
            (0, 1_000_000, 0.08),
            (1_000_000, float('inf'), 0.16),
        ],
        'notes': 'Progressive rates from 0.8% to 16%; cliff tax (no exemption if over threshold)'
    },
    'MN': {
        'name': 'Minnesota',
        'exemption': 3_000_000,  # 2024
        'rates': [
            (0, 3_000_000, 0.13),
            (3_000_000, 4_000_000, 0.14),
            (4_000_000, 6_000_000, 0.15),
            (6_000_000, float('inf'), 0.16),
        ],
        'notes': 'Progressive rates from 13% to 16%'
    },
    'NY': {
        'name': 'New York',
        'exemption': 6_940_000,  # 2024
        'rates': [
            (0, 6_940_000, 0.034),
            (6_940_000, 10_940_000, 0.10),
            (10_940_000, float('inf'), 0.16),
        ],
        'notes': 'Progressive rates from 3.06% to 16%; cliff tax if estate exceeds 105% of exemption'
    },
    'OR': {
        'name': 'Oregon',
        'exemption': 1_000_000,  # 2024 (lowest in nation)
        'rates': [
            (0, 1_000_000, 0.10),
            (1_000_000, 2_500_000, 0.12),
            (2_500_000, 5_000_000, 0.14),
            (5_000_000, float('inf'), 0.16),
        ],
        'notes': 'Progressive rates from 10% to 16%'
    },
    'RI': {
        'name': 'Rhode Island',
        'exemption': 1_733_264,  # 2024
        'rates': [
            (0, 1_733_264, 0.00),
            (1_733_264, float('inf'), 0.16),
        ],
        'notes': 'Flat 16% rate above exemption'
    },
    'VT': {
        'name': 'Vermont',
        'exemption': 5_000_000,  # 2024
        'rates': [
            (0, 5_000_000, 0.00),
            (5_000_000, float('inf'), 0.16),
        ],
        'notes': 'Flat 16% rate above exemption'
    },
    'WA': {
        'name': 'Washington',
        'exemption': 2_193_000,  # 2024
        'rates': [
            (0, 1_000_000, 0.10),
            (1_000_000, 2_000_000, 0.14),
            (2_000_000, 3_000_000, 0.15),
            (3_000_000, 4_000_000, 0.16),
            (4_000_000, 6_000_000, 0.18),
            (6_000_000, 7_000_000, 0.19),
            (7_000_000, 9_000_000, 0.195),
            (9_000_000, float('inf'), 0.20),
        ],
        'notes': 'Progressive rates from 10% to 20%'
    },
}

# States with inheritance taxes (tax paid by beneficiaries, not estate)
# Format: state_code: (rates_by_relationship, exemptions_by_relationship)
STATE_INHERITANCE_TAXES = {
    'IA': {
        'name': 'Iowa',
        'rates': {
            'spouse': 0.00,  # Exempt
            'parent': 0.00,  # Exempt
            'child': 0.00,   # Exempt (as of 2021)
            'sibling': 0.05,  # 5%
            'other': 0.10,    # 10%
        },
        'exemptions': {
            'spouse': float('inf'),
            'parent': float('inf'),
            'child': float('inf'),
            'sibling': 0,
            'other': 0,
        },
        'notes': 'Being phased out; eliminated for lineal descendants'
    },
    'KY': {
        'name': 'Kentucky',
        'rates': {
            'spouse': 0.00,  # Exempt
            'parent': 0.00,  # Exempt
            'child': 0.00,   # Exempt
            'sibling': 0.04,  # 4% to 16%
            'other': 0.06,    # 6% to 16%
        },
        'exemptions': {
            'spouse': float('inf'),
            'parent': float('inf'),
            'child': float('inf'),
            'sibling': 1_000,
            'other': 500,
        },
        'notes': 'Progressive rates based on relationship and amount'
    },
    'MD': {
        'name': 'Maryland',
        'rates': {
            'spouse': 0.00,  # Exempt
            'parent': 0.00,  # Exempt
            'child': 0.00,   # Exempt
            'sibling': 0.10,  # 10%
            'other': 0.10,    # 10%
        },
        'exemptions': {
            'spouse': float('inf'),
            'parent': float('inf'),
            'child': float('inf'),
            'sibling': 0,
            'other': 0,
        },
        'notes': 'Also has estate tax; 10% flat rate for non-lineal heirs'
    },
    'NE': {
        'name': 'Nebraska',
        'rates': {
            'spouse': 0.00,  # Exempt
            'parent': 0.01,  # 1%
            'child': 0.01,   # 1%
            'sibling': 0.13,  # 13%
            'other': 0.18,    # 18%
        },
        'exemptions': {
            'spouse': float('inf'),
            'parent': 40_000,
            'child': 40_000,
            'sibling': 15_000,
            'other': 10_000,
        },
        'notes': 'Rates vary by relationship: 1% (immediate family) to 18% (distant relatives)'
    },
    'NJ': {
        'name': 'New Jersey',
        'rates': {
            'spouse': 0.00,  # Exempt
            'parent': 0.00,  # Exempt
            'child': 0.00,   # Exempt
            'sibling': 0.11,  # 11% to 16%
            'other': 0.15,    # 15% to 16%
        },
        'exemptions': {
            'spouse': float('inf'),
            'parent': float('inf'),
            'child': float('inf'),
            'sibling': 25_000,
            'other': 500,
        },
        'notes': 'Progressive rates from 11% to 16% for non-lineal heirs'
    },
    'PA': {
        'name': 'Pennsylvania',
        'rates': {
            'spouse': 0.00,  # Exempt
            'parent': 0.00,  # Exempt (as of 2012)
            'child': 0.045,  # 4.5%
            'sibling': 0.12,  # 12%
            'other': 0.15,    # 15%
        },
        'exemptions': {
            'spouse': float('inf'),
            'parent': float('inf'),
            'child': 0,
            'sibling': 0,
            'other': 0,
        },
        'notes': 'Flat rates by relationship; no exemption amounts'
    },
}


# ==============================================================================
# RESULT CLASSES
# ==============================================================================

class FederalEstateTaxResult(NamedTuple):
    """Result of federal estate tax calculation."""
    gross_estate: float
    exemption_used: float
    exemption_available: float
    taxable_estate: float
    estate_tax: float
    effective_rate: float
    portability_available: float  # For surviving spouse
    year: int
    tcja_in_effect: bool


class StateEstateTaxResult(NamedTuple):
    """Result of state estate tax calculation."""
    state: str
    state_name: str
    gross_estate: float
    exemption: float
    taxable_estate: float
    estate_tax: float
    effective_rate: float
    notes: str


class InheritanceTaxResult(NamedTuple):
    """Result of inheritance tax calculation for a beneficiary."""
    state: str
    state_name: str
    beneficiary_name: str
    relationship: str
    inheritance_amount: float
    exemption: float
    taxable_amount: float
    inheritance_tax: float
    effective_rate: float


class GSTTResult(NamedTuple):
    """Result of Generation-Skipping Transfer Tax calculation."""
    transfer_amount: float
    exemption_used: float
    exemption_available: float
    taxable_amount: float
    gstt_tax: float
    effective_rate: float
    year: int


class ComprehensiveEstateTaxResult(NamedTuple):
    """Comprehensive estate tax analysis result."""
    federal_result: FederalEstateTaxResult
    state_result: Optional[StateEstateTaxResult]
    inheritance_results: List[InheritanceTaxResult]
    gstt_result: Optional[GSTTResult]
    total_estate_tax: float
    total_inheritance_tax: float
    total_gstt_tax: float
    total_tax_burden: float
    net_to_heirs: float
    effective_total_rate: float


# ==============================================================================
# FEDERAL ESTATE TAX CALCULATIONS
# ==============================================================================

def get_federal_exemption(year: int) -> float:
    """
    Get federal estate tax exemption for a given year.
    
    Args:
        year: Tax year
        
    Returns:
        Federal estate tax exemption amount
    """
    if year in FEDERAL_ESTATE_TAX_EXEMPTIONS:
        return FEDERAL_ESTATE_TAX_EXEMPTIONS[year]
    
    # For years beyond our data, use inflation-adjusted projection
    last_year = max(FEDERAL_ESTATE_TAX_EXEMPTIONS.keys())
    last_exemption = FEDERAL_ESTATE_TAX_EXEMPTIONS[last_year]
    years_diff = year - last_year
    
    # Assume 3% annual inflation
    inflation_rate = 0.03
    projected_exemption = last_exemption * ((1 + inflation_rate) ** years_diff)
    
    logger.info(f"Projected exemption for {year}: ${projected_exemption:,.0f} (based on {last_year})")
    return projected_exemption


def is_tcja_in_effect(year: int) -> bool:
    """
    Determine if TCJA (Tax Cuts and Jobs Act) is still in effect.
    
    TCJA doubled the estate tax exemption from 2018-2025.
    After 2025, it sunsets and reverts to pre-TCJA levels.
    
    Args:
        year: Tax year
        
    Returns:
        True if TCJA is in effect, False otherwise
    """
    return year <= 2025


def calculate_federal_estate_tax(
    gross_estate: float,
    year: int,
    prior_exemption_used: float = 0.0,
    portability_from_spouse: float = 0.0,
) -> FederalEstateTaxResult:
    """
    Calculate federal estate tax with TCJA sunset modeling.
    
    Args:
        gross_estate: Total value of the estate
        year: Year of death
        prior_exemption_used: Amount of exemption already used (lifetime gifts)
        portability_from_spouse: Unused exemption from deceased spouse
        
    Returns:
        FederalEstateTaxResult with detailed tax calculation
    """
    # Get base exemption for the year
    base_exemption = get_federal_exemption(year)
    
    # Total available exemption includes portability
    total_exemption = base_exemption + portability_from_spouse
    
    # Reduce by prior exemption used (lifetime gifts)
    available_exemption = max(0, total_exemption - prior_exemption_used)
    
    # Calculate taxable estate
    taxable_estate = max(0, gross_estate - available_exemption)
    
    # Calculate estate tax (flat 40% rate above exemption)
    estate_tax = taxable_estate * FEDERAL_ESTATE_TAX_RATE
    
    # Calculate effective rate
    effective_rate = estate_tax / gross_estate if gross_estate > 0 else 0.0
    
    # Calculate portability available for surviving spouse
    exemption_used = min(gross_estate, available_exemption)
    portability_available = max(0, base_exemption - exemption_used)
    
    tcja_in_effect = is_tcja_in_effect(year)
    
    logger.info(
        f"Federal Estate Tax ({year}): "
        f"Gross=${gross_estate:,.0f}, "
        f"Exemption=${available_exemption:,.0f}, "
        f"Tax=${estate_tax:,.0f}, "
        f"TCJA={'Yes' if tcja_in_effect else 'No'}"
    )
    
    return FederalEstateTaxResult(
        gross_estate=gross_estate,
        exemption_used=exemption_used,
        exemption_available=available_exemption,
        taxable_estate=taxable_estate,
        estate_tax=estate_tax,
        effective_rate=effective_rate,
        portability_available=portability_available,
        year=year,
        tcja_in_effect=tcja_in_effect,
    )


# ==============================================================================
# STATE ESTATE TAX CALCULATIONS
# ==============================================================================

def calculate_state_estate_tax(
    gross_estate: float,
    state_code: str,
    year: int = 2024,
) -> Optional[StateEstateTaxResult]:
    """
    Calculate state estate tax.
    
    Args:
        gross_estate: Total value of the estate
        state_code: Two-letter state code (e.g., 'NY', 'MA')
        year: Tax year (for future inflation adjustments)
        
    Returns:
        StateEstateTaxResult or None if state has no estate tax
    """
    state_code = state_code.upper()
    
    if state_code not in STATE_ESTATE_TAXES:
        logger.info(f"No estate tax for state: {state_code}")
        return None
    
    state_data = STATE_ESTATE_TAXES[state_code]
    exemption = state_data['exemption']
    rates = state_data['rates']
    
    # Calculate taxable estate
    taxable_estate = max(0, gross_estate - exemption)
    
    # Calculate tax using progressive rates
    estate_tax = 0.0
    remaining = taxable_estate
    
    for lower, upper, rate in rates:
        if remaining <= 0:
            break
        
        bracket_amount = min(remaining, upper - lower)
        estate_tax += bracket_amount * rate
        remaining -= bracket_amount
    
    # Special handling for cliff taxes (MA, NY)
    if state_code == 'MA' and gross_estate > exemption:
        # Massachusetts has a cliff tax - no exemption if over threshold
        estate_tax = gross_estate * 0.08  # Minimum rate
        for lower, upper, rate in rates:
            if gross_estate > lower:
                estate_tax = max(estate_tax, (gross_estate - lower) * rate)
    
    elif state_code == 'NY' and gross_estate > exemption * 1.05:
        # New York cliff tax if estate exceeds 105% of exemption
        estate_tax = gross_estate * 0.16  # Maximum rate applies to entire estate
    
    effective_rate = estate_tax / gross_estate if gross_estate > 0 else 0.0
    
    logger.info(
        f"State Estate Tax ({state_code}): "
        f"Gross=${gross_estate:,.0f}, "
        f"Exemption=${exemption:,.0f}, "
        f"Tax=${estate_tax:,.0f}"
    )
    
    return StateEstateTaxResult(
        state=state_code,
        state_name=state_data['name'],
        gross_estate=gross_estate,
        exemption=exemption,
        taxable_estate=taxable_estate,
        estate_tax=estate_tax,
        effective_rate=effective_rate,
        notes=state_data['notes'],
    )


# ==============================================================================
# INHERITANCE TAX CALCULATIONS
# ==============================================================================

def calculate_inheritance_tax(
    inheritance_amount: float,
    relationship: str,
    state_code: str,
    beneficiary_name: str = "Beneficiary",
) -> Optional[InheritanceTaxResult]:
    """
    Calculate inheritance tax for a specific beneficiary.
    
    Args:
        inheritance_amount: Amount inherited by beneficiary
        relationship: Relationship to deceased ('spouse', 'child', 'sibling', 'other')
        state_code: Two-letter state code
        beneficiary_name: Name of beneficiary (for reporting)
        
    Returns:
        InheritanceTaxResult or None if state has no inheritance tax
    """
    state_code = state_code.upper()
    
    if state_code not in STATE_INHERITANCE_TAXES:
        logger.info(f"No inheritance tax for state: {state_code}")
        return None
    
    state_data = STATE_INHERITANCE_TAXES[state_code]
    
    # Normalize relationship
    relationship = relationship.lower()
    if relationship not in state_data['rates']:
        relationship = 'other'
    
    rate = state_data['rates'][relationship]
    exemption = state_data['exemptions'][relationship]
    
    # Calculate taxable amount
    taxable_amount = max(0, inheritance_amount - exemption)
    
    # Calculate inheritance tax
    inheritance_tax = taxable_amount * rate
    
    effective_rate = inheritance_tax / inheritance_amount if inheritance_amount > 0 else 0.0
    
    logger.info(
        f"Inheritance Tax ({state_code}): "
        f"Beneficiary={beneficiary_name}, "
        f"Relationship={relationship}, "
        f"Amount=${inheritance_amount:,.0f}, "
        f"Tax=${inheritance_tax:,.0f}"
    )
    
    return InheritanceTaxResult(
        state=state_code,
        state_name=state_data['name'],
        beneficiary_name=beneficiary_name,
        relationship=relationship,
        inheritance_amount=inheritance_amount,
        exemption=exemption,
        taxable_amount=taxable_amount,
        inheritance_tax=inheritance_tax,
        effective_rate=effective_rate,
    )


# ==============================================================================
# GENERATION-SKIPPING TRANSFER TAX (GSTT)
# ==============================================================================

def calculate_gstt(
    transfer_amount: float,
    year: int,
    prior_exemption_used: float = 0.0,
) -> GSTTResult:
    """
    Calculate Generation-Skipping Transfer Tax (GSTT).
    
    GSTT applies to transfers to beneficiaries who are two or more generations
    below the transferor (e.g., grandchildren, great-grandchildren).
    
    Args:
        transfer_amount: Amount transferred to skip persons
        year: Year of transfer
        prior_exemption_used: Amount of GSTT exemption already used
        
    Returns:
        GSTTResult with detailed GSTT calculation
    """
    # GSTT exemption is the same as estate tax exemption
    base_exemption = get_federal_exemption(year)
    
    # Calculate available exemption
    available_exemption = max(0, base_exemption - prior_exemption_used)
    
    # Calculate taxable amount
    taxable_amount = max(0, transfer_amount - available_exemption)
    
    # Calculate GSTT (flat 40% rate)
    gstt_tax = taxable_amount * GSTT_TAX_RATE
    
    # Calculate effective rate
    effective_rate = gstt_tax / transfer_amount if transfer_amount > 0 else 0.0
    
    # Calculate exemption used
    exemption_used = min(transfer_amount, available_exemption)
    
    logger.info(
        f"GSTT ({year}): "
        f"Transfer=${transfer_amount:,.0f}, "
        f"Exemption=${available_exemption:,.0f}, "
        f"Tax=${gstt_tax:,.0f}"
    )
    
    return GSTTResult(
        transfer_amount=transfer_amount,
        exemption_used=exemption_used,
        exemption_available=available_exemption,
        taxable_amount=taxable_amount,
        gstt_tax=gstt_tax,
        effective_rate=effective_rate,
        year=year,
    )


# ==============================================================================
# COMPREHENSIVE ESTATE TAX ANALYSIS
# ==============================================================================

def calculate_comprehensive_estate_tax(
    gross_estate: float,
    year: int,
    state_code: Optional[str] = None,
    beneficiaries: Optional[List[Dict[str, Any]]] = None,
    skip_person_transfers: float = 0.0,
    prior_exemption_used: float = 0.0,
    prior_gstt_exemption_used: float = 0.0,
    portability_from_spouse: float = 0.0,
) -> ComprehensiveEstateTaxResult:
    """
    Calculate comprehensive estate tax analysis including federal, state, inheritance, and GSTT.
    
    Args:
        gross_estate: Total value of the estate
        year: Year of death
        state_code: Two-letter state code (optional)
        beneficiaries: List of beneficiary dicts with 'name', 'relationship', 'amount'
        skip_person_transfers: Total amount going to skip persons (for GSTT)
        prior_exemption_used: Federal exemption already used (lifetime gifts)
        prior_gstt_exemption_used: GSTT exemption already used
        portability_from_spouse: Unused exemption from deceased spouse
        
    Returns:
        ComprehensiveEstateTaxResult with complete analysis
    """
    # Calculate federal estate tax
    federal_result = calculate_federal_estate_tax(
        gross_estate=gross_estate,
        year=year,
        prior_exemption_used=prior_exemption_used,
        portability_from_spouse=portability_from_spouse,
    )
    
    # Calculate state estate tax
    state_result = None
    if state_code:
        state_result = calculate_state_estate_tax(
            gross_estate=gross_estate,
            state_code=state_code,
            year=year,
        )
    
    # Calculate inheritance taxes for each beneficiary
    inheritance_results = []
    if beneficiaries and state_code:
        for beneficiary in beneficiaries:
            inh_result = calculate_inheritance_tax(
                inheritance_amount=beneficiary.get('amount', 0),
                relationship=beneficiary.get('relationship', 'other'),
                state_code=state_code,
                beneficiary_name=beneficiary.get('name', 'Beneficiary'),
            )
            if inh_result:
                inheritance_results.append(inh_result)
    
    # Calculate GSTT
    gstt_result = None
    if skip_person_transfers > 0:
        gstt_result = calculate_gstt(
            transfer_amount=skip_person_transfers,
            year=year,
            prior_exemption_used=prior_gstt_exemption_used,
        )
    
    # Calculate totals
    total_estate_tax = federal_result.estate_tax + (state_result.estate_tax if state_result else 0)
    total_inheritance_tax = sum(r.inheritance_tax for r in inheritance_results)
    total_gstt_tax = gstt_result.gstt_tax if gstt_result else 0
    total_tax_burden = total_estate_tax + total_inheritance_tax + total_gstt_tax
    
    net_to_heirs = gross_estate - total_tax_burden
    effective_total_rate = total_tax_burden / gross_estate if gross_estate > 0 else 0.0
    
    logger.info(
        f"Comprehensive Estate Tax Analysis: "
        f"Gross=${gross_estate:,.0f}, "
        f"Total Tax=${total_tax_burden:,.0f}, "
        f"Net to Heirs=${net_to_heirs:,.0f}, "
        f"Effective Rate={effective_total_rate:.2%}"
    )
    
    return ComprehensiveEstateTaxResult(
        federal_result=federal_result,
        state_result=state_result,
        inheritance_results=inheritance_results,
        gstt_result=gstt_result,
        total_estate_tax=total_estate_tax,
        total_inheritance_tax=total_inheritance_tax,
        total_gstt_tax=total_gstt_tax,
        total_tax_burden=total_tax_burden,
        net_to_heirs=net_to_heirs,
        effective_total_rate=effective_total_rate,
    )


# ==============================================================================
# TCJA SUNSET COMPARISON
# ==============================================================================

def compare_tcja_sunset_impact(
    gross_estate: float,
    state_code: Optional[str] = None,
    prior_exemption_used: float = 0.0,
) -> Dict[str, Any]:
    """
    Compare estate tax impact before and after TCJA sunset.
    
    Args:
        gross_estate: Total value of the estate
        state_code: Two-letter state code (optional)
        prior_exemption_used: Federal exemption already used
        
    Returns:
        Dictionary with comparison data
    """
    # Calculate for 2025 (TCJA in effect)
    result_2025 = calculate_comprehensive_estate_tax(
        gross_estate=gross_estate,
        year=2025,
        state_code=state_code,
        prior_exemption_used=prior_exemption_used,
    )
    
    # Calculate for 2026 (TCJA sunset)
    result_2026 = calculate_comprehensive_estate_tax(
        gross_estate=gross_estate,
        year=2026,
        state_code=state_code,
        prior_exemption_used=prior_exemption_used,
    )
    
    # Calculate differences
    exemption_reduction = result_2025.federal_result.exemption_available - result_2026.federal_result.exemption_available
    tax_increase = result_2026.total_tax_burden - result_2025.total_tax_burden
    
    comparison = {
        'gross_estate': gross_estate,
        'state': state_code,
        'year_2025': {
            'exemption': result_2025.federal_result.exemption_available,
            'total_tax': result_2025.total_tax_burden,
            'effective_rate': result_2025.effective_total_rate,
            'net_to_heirs': result_2025.net_to_heirs,
        },
        'year_2026': {
            'exemption': result_2026.federal_result.exemption_available,
            'total_tax': result_2026.total_tax_burden,
            'effective_rate': result_2026.effective_total_rate,
            'net_to_heirs': result_2026.net_to_heirs,
        },
        'impact': {
            'exemption_reduction': exemption_reduction,
            'tax_increase': tax_increase,
            'tax_increase_pct': (tax_increase / result_2025.total_tax_burden * 100) if result_2025.total_tax_burden > 0 else 0,
            'net_reduction': result_2025.net_to_heirs - result_2026.net_to_heirs,
        }
    }
    
    logger.info(
        f"TCJA Sunset Impact: "
        f"Exemption reduction=${exemption_reduction:,.0f}, "
        f"Tax increase=${tax_increase:,.0f}"
    )
    
    return comparison


# ==============================================================================
# UTILITY FUNCTIONS
# ==============================================================================

def get_annual_gift_exclusion(year: int) -> int:
    """Get annual gift tax exclusion for a given year."""
    if year in ANNUAL_GIFT_EXCLUSION:
        return ANNUAL_GIFT_EXCLUSION[year]
    
    # For future years, use last known value with inflation
    last_year = max(ANNUAL_GIFT_EXCLUSION.keys())
    last_exclusion = ANNUAL_GIFT_EXCLUSION[last_year]
    years_diff = year - last_year
    
    # Round to nearest $1,000
    projected = last_exclusion * ((1.03) ** years_diff)
    return int(round(projected / 1000) * 1000)


def calculate_lifetime_gift_impact(
    annual_gifts: float,
    years: int,
    num_recipients: int,
    year_start: int,
) -> Dict[str, float]:
    """
    Calculate the impact of annual exclusion gifts on estate tax exemption.
    
    Args:
        annual_gifts: Total annual gifts per recipient
        years: Number of years of gifting
        num_recipients: Number of gift recipients
        year_start: Starting year
        
    Returns:
        Dictionary with gift analysis
    """
    total_gifts = 0
    exemption_used = 0
    
    for i in range(years):
        year = year_start + i
        exclusion = get_annual_gift_exclusion(year)
        
        # Gifts per recipient
        per_recipient = annual_gifts
        
        # Amount over exclusion (uses exemption)
        over_exclusion = max(0, per_recipient - exclusion)
        
        # Total for all recipients
        total_gifts += per_recipient * num_recipients
        exemption_used += over_exclusion * num_recipients
    
    return {
        'total_gifts': total_gifts,
        'exemption_used': exemption_used,
        'within_exclusion': total_gifts - exemption_used,
        'years': years,
        'recipients': num_recipients,
    }


def format_currency(amount: float) -> str:
    """Format amount as currency string."""
    return f"${amount:,.0f}"


def format_percentage(rate: float) -> str:
    """Format rate as percentage string."""
    return f"{rate * 100:.2f}%"

# Made with Bob
