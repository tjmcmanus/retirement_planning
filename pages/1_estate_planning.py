
"""
Estate Planning page for retirement planning application.
Provides a comprehensive estate planning checklist, situation assessment,
document tracker, and review schedule.
"""

import logging
import streamlit as st
import pandas as pd
import json
import os
from datetime import datetime, date
from config import get_config_manager
from components.navbar import navbar
from estate_tax_calculations import (
    calculate_comprehensive_estate_tax,
    compare_tcja_sunset_impact,
    STATE_ESTATE_TAXES,
    STATE_INHERITANCE_TAXES,
    format_currency,
    format_percentage,
)
from beneficiary_optimization import (
    calculate_inherited_ira_10_year_rule,
    calculate_stretch_ira,
    compare_spousal_options,
    calculate_trust_beneficiary,
    compare_beneficiary_strategies,
)
from charitable_giving_advanced import (
    calculate_crt_crut,
    calculate_crt_crat,
    calculate_clt_clut,
    calculate_clt_clat,
    calculate_private_foundation,
    calculate_daf,
    compare_foundation_vs_daf,
    calculate_qcd_benefit,
)

logger = logging.getLogger(__name__)

# Named constant for the federal estate tax threshold note.
# The TCJA sunset in 2026 will reduce this from ~$13M (2024) to ~$7M.
FEDERAL_ESTATE_TAX_THRESHOLD_NOTE = "$13M (2024, scheduled to drop ~$7M in 2026 per TCJA sunset)"

st.set_page_config(page_title="Estate Planning", page_icon="⚖️", layout="wide")

navbar("🏛️ Estate Planning")

# ---------------------------------------------------------------------------
# Configuration & persistence helpers
# ---------------------------------------------------------------------------

ESTATE_DATA_FILE = "estate_planning_data.json"


def _load_estate_data() -> dict:
    """Load estate planning data from JSON file."""
    if os.path.exists(ESTATE_DATA_FILE):
        try:
            with open(ESTATE_DATA_FILE, "r") as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Could not load estate data from {ESTATE_DATA_FILE}: {e}")
    return {}


def _save_estate_data(data: dict) -> bool:
    """Persist estate planning data to JSON file."""
    try:
        with open(ESTATE_DATA_FILE, "w") as f:
            json.dump(data, f, indent=2, default=str)
        return True
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Load config for personalisation (re-read on every page load)
# ---------------------------------------------------------------------------

config_mgr = get_config_manager()
config_mgr.config = config_mgr._load_config()
p1_name: str = config_mgr.get("personal_info", "person1_name", "Person 1") or "Person 1"
p2_name: str = config_mgr.get("personal_info", "person2_name", "Person 2") or "Person 2"
accounts_raw: list = config_mgr.get("portfolio_accounts", "accounts", []) or []
account_names: list[str] = [a.get("account_name", "") for a in accounts_raw if a.get("account_name")]
properties_raw: list = config_mgr.get("real_estate", "properties", []) or []
property_names: list[str] = [p.get("property_name", "") for p in properties_raw if p.get("property_name")]

# Children from configuration page
_children_cfg: list = config_mgr.get("personal_info", "children", []) or []
if not isinstance(_children_cfg, list):
    _children_cfg = []
# Derive summary flags from config data
_cfg_has_minor_children: bool = any(
    config_mgr.calculate_age(c.get("birth_date", "1900-01-01")) < 18
    for c in _children_cfg
    if c.get("birth_date")
)
_cfg_has_adult_children: bool = any(
    config_mgr.calculate_age(c.get("birth_date", "1900-01-01")) >= 18
    for c in _children_cfg
    if c.get("birth_date")
)
_cfg_has_special_needs: bool = any(c.get("special_needs", False) for c in _children_cfg)

# ---------------------------------------------------------------------------
# Session state initialisation
# ---------------------------------------------------------------------------

if "estate_data" not in st.session_state:
    st.session_state["estate_data"] = _load_estate_data()

estate = st.session_state["estate_data"]

# ---------------------------------------------------------------------------
# Page header
# ---------------------------------------------------------------------------

st.title("⚖️ Estate Planning")
st.markdown(
    "A comprehensive guide to assess your current estate situation, build your checklist, "
    "track document locations, and schedule regular reviews."
)

# ---------------------------------------------------------------------------
# Tabs
# ---------------------------------------------------------------------------

(
    tab_assess,
    tab_tax,
    tab_beneficiary,
    tab_charitable,
    tab_legal,
    tab_financial,
    tab_personal,
    tab_docs,
    tab_schedule,
    tab_progress,
) = st.tabs([
    "🔍 Situation Assessment",
    "💰 Estate Tax Calculator",
    "👥 Beneficiary Planning",
    "🎁 Charitable Giving",
    "⚖️ Legal Documents",
    "💰 Financial & Accounts",
    "🏠 Personal & Property",
    "📁 Document Locations",
    "📅 Review Schedule",
    "📊 Overall Progress",
])

# ===========================================================================
# TAB 1 — SITUATION ASSESSMENT
# ===========================================================================

with tab_assess:
    st.header("🔍 Situation Assessment")
    st.markdown(
        "Answer the questions below to help determine which estate planning tools are "
        "recommended for your situation. Your answers drive the checklist recommendations."
    )

    assess = estate.setdefault("assessment", {})

    # Auto-populate flags from config children data (config is authoritative source)
    if _children_cfg:
        assess["minor_children"] = _cfg_has_minor_children
        assess["adult_children"] = _cfg_has_adult_children
        assess["special_needs_dependent"] = _cfg_has_special_needs

    st.subheader("Family & Beneficiaries")

    # -----------------------------------------------------------------------
    # Children summary panel (read from configuration)
    # -----------------------------------------------------------------------
    if _children_cfg:
        st.info(
            f"👶 **{len(_children_cfg)} child(ren) configured** in Personal Info. "
            "The checkboxes below are automatically set from that data. "
            "To add or edit children, go to ⚙️ Configuration → Personal Info."
        )
        _child_cols = st.columns(min(len(_children_cfg), 4))
        for _ci, _child in enumerate(_children_cfg):
            _cname = _child.get("name", f"Child {_ci + 1}")
            _cbdate = _child.get("birth_date", "")
            _cage = config_mgr.calculate_age(_cbdate) if _cbdate else "?"
            _csn = _child.get("special_needs", False)
            with _child_cols[_ci % len(_child_cols)]:
                st.markdown(
                    f"**{_cname}**  \n"
                    f"Age: {_cage}  \n"
                    + ("🔹 Special Needs" if _csn else "")
                )
    else:
        st.caption(
            "💡 No children configured. Add children in ⚙️ Configuration → Personal Info "
            "to auto-populate the checkboxes below."
        )

    col_a1, col_a2 = st.columns(2)
    with col_a1:
        assess["married"] = st.checkbox(
            "Are you married / in a domestic partnership?",
            value=assess.get("married", True),
            key="assess_married",
        )
        assess["minor_children"] = st.checkbox(
            "Do you have minor children (under 18)?",
            value=assess.get("minor_children", _cfg_has_minor_children),
            key="assess_minor_children",
            disabled=bool(_children_cfg),  # locked when config data is present
        )
        assess["adult_children"] = st.checkbox(
            "Do you have adult children?",
            value=assess.get("adult_children", _cfg_has_adult_children),
            key="assess_adult_children",
            disabled=bool(_children_cfg),
        )
    with col_a2:
        assess["special_needs_dependent"] = st.checkbox(
            "Do you have a dependent with special needs?",
            value=assess.get("special_needs_dependent", _cfg_has_special_needs),
            key="assess_special_needs",
            disabled=bool(_children_cfg),
        )
        assess["blended_family"] = st.checkbox(
            "Is this a blended family (step-children, prior marriages)?",
            value=assess.get("blended_family", False),
            key="assess_blended",
        )
        assess["elderly_parents"] = st.checkbox(
            "Are you caring for or supporting elderly parents?",
            value=assess.get("elderly_parents", False),
            key="assess_elderly_parents",
        )

    st.subheader("Assets & Estate Size")
    col_b1, col_b2 = st.columns(2)
    with col_b1:
        assess["has_real_estate"] = st.checkbox(
            "Do you own real estate (primary home, rental, vacation)?",
            value=assess.get("has_real_estate", len(property_names) > 0),
            key="assess_real_estate",
        )
        assess["has_business"] = st.checkbox(
            "Do you own a business or have business interests?",
            value=assess.get("has_business", False),
            key="assess_business",
        )
        assess["has_retirement_accounts"] = st.checkbox(
            "Do you have retirement accounts (IRA, 401k, Roth)?",
            value=assess.get("has_retirement_accounts", len(account_names) > 0),
            key="assess_retirement_accts",
        )
    with col_b2:
        assess["estate_over_threshold"] = st.checkbox(
            f"Is your estimated estate value over {FEDERAL_ESTATE_TAX_THRESHOLD_NOTE}?",
            value=assess.get("estate_over_threshold", False),
            key="assess_estate_threshold",
        )
        assess["has_life_insurance"] = st.checkbox(
            "Do you have life insurance policies?",
            value=assess.get("has_life_insurance", False),
            key="assess_life_insurance",
        )
        assess["has_digital_assets"] = st.checkbox(
            "Do you have significant digital assets (crypto, online accounts)?",
            value=assess.get("has_digital_assets", False),
            key="assess_digital_assets",
        )

    st.subheader("Existing Documents")
    col_c1, col_c2 = st.columns(2)
    with col_c1:
        assess["has_will"] = st.checkbox(
            "Do you have a current Will?",
            value=assess.get("has_will", False),
            key="assess_has_will",
        )
        assess["has_trust"] = st.checkbox(
            "Do you have a Revocable Living Trust?",
            value=assess.get("has_trust", False),
            key="assess_has_trust",
        )
        assess["has_poa"] = st.checkbox(
            "Do you have a Durable Power of Attorney?",
            value=assess.get("has_poa", False),
            key="assess_has_poa",
        )
    with col_c2:
        assess["has_healthcare_directive"] = st.checkbox(
            "Do you have a Healthcare Directive / Living Will?",
            value=assess.get("has_healthcare_directive", False),
            key="assess_has_hcd",
        )
        assess["beneficiaries_current"] = st.checkbox(
            "Are all account beneficiary designations current?",
            value=assess.get("beneficiaries_current", False),
            key="assess_beneficiaries",
        )
        assess["titling_reviewed"] = st.checkbox(
            "Has property titling been reviewed recently?",
            value=assess.get("titling_reviewed", False),
            key="assess_titling",
        )

    # ---------------------------------------------------------------------------
    # Recommendations panel
    # ---------------------------------------------------------------------------
    st.markdown("---")
    st.subheader("📋 Recommendations Based on Your Situation")

    recs: list[str] = []

    if not assess.get("has_will"):
        recs.append("🔴 **Create a Will** — You do not have a current Will. This is the foundation of any estate plan.")
    if assess.get("has_real_estate") and not assess.get("has_trust"):
        recs.append(
            "🔴 **Consider a Revocable Living Trust** — You own real estate. A trust allows your estate to "
            "avoid probate, which can be costly and time-consuming. Real estate must be re-titled into the trust."
        )
    if assess.get("has_trust") and assess.get("has_real_estate"):
        recs.append(
            "🟡 **Fund the Trust — Re-title Real Estate** — You have a trust but need to confirm all real estate "
            "is titled in the name of the trust to avoid probate."
        )
    if assess.get("has_trust") and assess.get("has_retirement_accounts"):
        recs.append(
            "🟡 **Fund the Trust — Review Retirement Account Beneficiaries** — Do NOT title retirement accounts "
            "in the trust (tax consequences). Instead, name the trust as contingent beneficiary if appropriate, "
            "or name individuals directly."
        )
    if not assess.get("has_poa"):
        recs.append("🔴 **Create a Durable Power of Attorney** — Allows a trusted person to manage finances if you are incapacitated.")
    if not assess.get("has_healthcare_directive"):
        recs.append("🔴 **Create a Healthcare Directive / Living Will** — Documents your medical wishes and names a healthcare proxy.")
    if not assess.get("beneficiaries_current"):
        recs.append("🟡 **Update Beneficiary Designations** — Review all retirement accounts, life insurance, and bank accounts.")
    if assess.get("minor_children") and not assess.get("has_will"):
        recs.append("🔴 **Name a Guardian in Your Will** — You have minor children. A Will is the only way to legally name a guardian.")
    if assess.get("special_needs_dependent"):
        # Personalise with child name(s) if available
        _sn_names = [c.get("name", "") for c in _children_cfg if c.get("special_needs", False)]
        _sn_label = f" ({', '.join(n for n in _sn_names if n)})" if _sn_names else ""
        recs.append(
            f"🔴 **Consider a Special Needs Trust{_sn_label}** — "
            "Protects a disabled dependent's eligibility for government benefits (SSI, Medicaid). "
            "Assets held in a properly drafted SNT do not count against benefit eligibility limits."
        )
    if _children_cfg and any(
        18 <= config_mgr.calculate_age(c.get("birth_date", "1900-01-01")) <= 22
        for c in _children_cfg if c.get("birth_date")
    ):
        recs.append(
            "🟡 **College Funding** — You have children approaching or in college age. "
            "Consider 529 plan contributions, financial aid implications, and whether "
            "your withdrawal strategy accounts for college expenses."
        )
    if assess.get("has_business"):
        recs.append("🟡 **Create a Business Succession Plan** — Document what happens to your business interest at death or incapacity.")
    if assess.get("estate_over_threshold"):
        recs.append("🔴 **Consult an Estate Attorney re: Estate Tax Planning** — Your estate may be subject to federal estate tax.")
    if assess.get("has_life_insurance"):
        recs.append("🟡 **Review Life Insurance Beneficiaries & Consider an ILIT** — An Irrevocable Life Insurance Trust can remove proceeds from your taxable estate.")
    if assess.get("has_digital_assets"):
        recs.append("🟡 **Create a Digital Asset Inventory** — Document crypto wallets, passwords, and online accounts for your executor.")
    if not assess.get("titling_reviewed"):
        recs.append("🟡 **Review Property Titling** — Ensure real estate, vehicles, and bank accounts are titled correctly (joint tenancy, TOD, trust).")
    if assess.get("blended_family"):
        recs.append("🟡 **Consider a QTIP Trust or Separate Property Agreement** — Blended families benefit from careful trust structuring to protect all children.")

    if not recs:
        st.success("✅ Your estate plan appears to be in good shape! Continue to review annually.")
    else:
        for r in recs:
            st.markdown(r)

    if st.button("💾 Save Assessment", key="save_assessment"):
        if _save_estate_data(estate):
            st.success("✅ Assessment saved!")
        else:
            st.error("❌ Error saving assessment.")


# ===========================================================================
# TAB 2 — ESTATE TAX CALCULATOR
# ===========================================================================

with tab_tax:
    st.header("💰 Estate Tax Calculator")
    st.markdown(
        "Calculate federal and state estate taxes, including TCJA sunset impact analysis. "
        "This tool helps you understand potential estate tax liability and plan accordingly."
    )
    
    # Initialize tax calculation data
    tax_calc = estate.setdefault("tax_calculator", {})
    
    # Input Section
    st.subheader("📊 Estate Information")
    
    col1, col2 = st.columns(2)
    
    with col1:
        gross_estate = st.number_input(
            "Gross Estate Value ($)",
            min_value=0,
            value=tax_calc.get("gross_estate", 10_000_000),
            step=100_000,
            help="Total value of all assets including real estate, investments, life insurance, business interests, etc.",
            key="tax_gross_estate"
        )
        tax_calc["gross_estate"] = gross_estate
        
        death_year = st.selectbox(
            "Year of Death (for projections)",
            options=list(range(2024, 2036)),
            index=0,
            help="Select the year to calculate estate taxes. Future years show TCJA sunset impact.",
            key="tax_death_year"
        )
        tax_calc["death_year"] = death_year
        
        prior_gifts = st.number_input(
            "Prior Lifetime Gifts Using Exemption ($)",
            min_value=0,
            value=tax_calc.get("prior_gifts", 0),
            step=100_000,
            help="Amount of federal estate tax exemption already used for lifetime gifts above annual exclusion",
            key="tax_prior_gifts"
        )
        tax_calc["prior_gifts"] = prior_gifts
    
    with col2:
        # State selection
        state_options = ["None"] + sorted(list(STATE_ESTATE_TAXES.keys()) + list(STATE_INHERITANCE_TAXES.keys()))
        state_code = st.selectbox(
            "State of Residence",
            options=state_options,
            index=0,
            help="Select your state to include state estate or inheritance taxes",
            key="tax_state"
        )
        tax_calc["state"] = state_code if state_code != "None" else None
        
        portability = st.number_input(
            "Portability from Deceased Spouse ($)",
            min_value=0,
            value=tax_calc.get("portability", 0),
            step=100_000,
            help="Unused federal exemption from deceased spouse (portability election)",
            key="tax_portability"
        )
        tax_calc["portability"] = portability
        
        skip_transfers = st.number_input(
            "Transfers to Skip Persons ($)",
            min_value=0,
            value=tax_calc.get("skip_transfers", 0),
            step=100_000,
            help="Amount going to grandchildren or other skip persons (for GSTT calculation)",
            key="tax_skip_transfers"
        )
        tax_calc["skip_transfers"] = skip_transfers
    
    # Beneficiaries Section
    st.subheader("👥 Beneficiaries (for Inheritance Tax)")
    
    if tax_calc["state"] and tax_calc["state"] in STATE_INHERITANCE_TAXES:
        st.info(f"💡 {STATE_INHERITANCE_TAXES[tax_calc['state']]['name']} has inheritance taxes. Add beneficiaries below to calculate their tax liability.")
        
        # Initialize beneficiaries list
        if "beneficiaries" not in tax_calc:
            tax_calc["beneficiaries"] = []
        
        # Add beneficiary form
        with st.expander("➕ Add Beneficiary", expanded=len(tax_calc["beneficiaries"]) == 0):
            ben_col1, ben_col2, ben_col3 = st.columns(3)
            
            with ben_col1:
                ben_name = st.text_input("Beneficiary Name", key="new_ben_name")
            
            with ben_col2:
                ben_relationship = st.selectbox(
                    "Relationship",
                    options=["spouse", "child", "parent", "sibling", "other"],
                    key="new_ben_relationship"
                )
            
            with ben_col3:
                ben_amount = st.number_input(
                    "Inheritance Amount ($)",
                    min_value=0,
                    step=10_000,
                    key="new_ben_amount"
                )
            
            if st.button("Add Beneficiary", key="add_beneficiary"):
                if ben_name and ben_amount > 0:
                    tax_calc["beneficiaries"].append({
                        "name": ben_name,
                        "relationship": ben_relationship,
                        "amount": ben_amount
                    })
                    st.success(f"Added {ben_name}")
                    st.rerun()
        
        # Display existing beneficiaries
        if tax_calc["beneficiaries"]:
            st.write("**Current Beneficiaries:**")
            for i, ben in enumerate(tax_calc["beneficiaries"]):
                col_name, col_rel, col_amt, col_del = st.columns([3, 2, 2, 1])
                
                with col_name:
                    st.write(ben["name"])
                with col_rel:
                    st.write(ben["relationship"].title())
                with col_amt:
                    st.write(f"${ben['amount']:,.0f}")
                with col_del:
                    if st.button("🗑️", key=f"del_ben_{i}", help="Delete beneficiary"):
                        tax_calc["beneficiaries"].pop(i)
                        st.rerun()
    
    # Calculate Button
    st.markdown("---")
    
    if st.button("🧮 Calculate Estate Taxes", type="primary", key="calculate_estate_tax"):
        try:
            # Perform comprehensive estate tax calculation
            result = calculate_comprehensive_estate_tax(
                gross_estate=gross_estate,
                year=death_year,
                state_code=tax_calc["state"],
                beneficiaries=tax_calc.get("beneficiaries", []),
                skip_person_transfers=skip_transfers,
                prior_exemption_used=prior_gifts,
                portability_from_spouse=portability,
            )
            
            # Store results
            tax_calc["last_calculation"] = {
                "result": result._asdict(),
                "timestamp": datetime.now().isoformat(),
            }
            
            # Display Results
            st.markdown("---")
            st.subheader("📊 Estate Tax Calculation Results")
            
            # Summary Cards
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric(
                    "Gross Estate",
                    format_currency(result.federal_result.gross_estate),
                )
            
            with col2:
                st.metric(
                    "Total Tax Burden",
                    format_currency(result.total_tax_burden),
                    delta=f"-{format_percentage(result.effective_total_rate)}",
                    delta_color="inverse"
                )
            
            with col3:
                st.metric(
                    "Net to Heirs",
                    format_currency(result.net_to_heirs),
                )
            
            with col4:
                st.metric(
                    "Effective Tax Rate",
                    format_percentage(result.effective_total_rate),
                )
            
            # Detailed Breakdown
            st.subheader("🔍 Detailed Tax Breakdown")
            
            # Federal Estate Tax
            st.write("**Federal Estate Tax:**")
            fed_col1, fed_col2 = st.columns(2)
            
            with fed_col1:
                st.write(f"• Exemption Available: {format_currency(result.federal_result.exemption_available)}")
                st.write(f"• Taxable Estate: {format_currency(result.federal_result.taxable_estate)}")
                st.write(f"• Federal Estate Tax: {format_currency(result.federal_result.estate_tax)}")
            
            with fed_col2:
                st.write(f"• TCJA in Effect: {'Yes' if result.federal_result.tcja_in_effect else 'No'}")
                st.write(f"• Portability Available: {format_currency(result.federal_result.portability_available)}")
                st.write(f"• Effective Rate: {format_percentage(result.federal_result.effective_rate)}")
            
            # State Estate Tax
            if result.state_result:
                st.write("**State Estate Tax:**")
                st.write(f"• State: {result.state_result.state_name}")
                st.write(f"• State Exemption: {format_currency(result.state_result.exemption)}")
                st.write(f"• State Estate Tax: {format_currency(result.state_result.estate_tax)}")
                st.write(f"• Notes: {result.state_result.notes}")
            
            # Inheritance Tax
            if result.inheritance_results:
                st.write("**Inheritance Tax by Beneficiary:**")
                for inh in result.inheritance_results:
                    st.write(f"• {inh.beneficiary_name} ({inh.relationship}): {format_currency(inh.inheritance_tax)} on {format_currency(inh.inheritance_amount)}")
            
            # GSTT
            if result.gstt_result:
                st.write("**Generation-Skipping Transfer Tax:**")
                st.write(f"• Skip Person Transfers: {format_currency(result.gstt_result.transfer_amount)}")
                st.write(f"• GSTT Tax: {format_currency(result.gstt_result.gstt_tax)}")
            
        except Exception as e:
            st.error(f"Error calculating estate taxes: {str(e)}")
    
    # TCJA Sunset Analysis
    st.markdown("---")
    st.subheader("⚖️ TCJA Sunset Impact Analysis")
    st.markdown(
        "The Tax Cuts and Jobs Act (TCJA) doubled the federal estate tax exemption through 2025. "
        "Starting in 2026, the exemption will revert to approximately half the current level. "
        "This analysis shows the impact on your estate."
    )
    
    if st.button("📈 Analyze TCJA Sunset Impact", key="tcja_analysis"):
        try:
            comparison = compare_tcja_sunset_impact(
                gross_estate=gross_estate,
                state_code=tax_calc["state"],
                prior_exemption_used=prior_gifts,
            )
            
            st.subheader("📊 TCJA Sunset Comparison")
            
            # Comparison Table
            comp_col1, comp_col2, comp_col3 = st.columns(3)
            
            with comp_col1:
                st.write("**2025 (TCJA in Effect)**")
                st.write(f"Exemption: {format_currency(comparison['year_2025']['exemption'])}")
                st.write(f"Total Tax: {format_currency(comparison['year_2025']['total_tax'])}")
                st.write(f"Net to Heirs: {format_currency(comparison['year_2025']['net_to_heirs'])}")
            
            with comp_col2:
                st.write("**2026 (TCJA Sunset)**")
                st.write(f"Exemption: {format_currency(comparison['year_2026']['exemption'])}")
                st.write(f"Total Tax: {format_currency(comparison['year_2026']['total_tax'])}")
                st.write(f"Net to Heirs: {format_currency(comparison['year_2026']['net_to_heirs'])}")
            
            with comp_col3:
                st.write("**Impact**")
                st.write(f"Exemption Reduction: {format_currency(comparison['impact']['exemption_reduction'])}")
                st.write(f"Tax Increase: {format_currency(comparison['impact']['tax_increase'])}")
                st.write(f"Net Reduction: {format_currency(comparison['impact']['net_reduction'])}")
            
            # Visual Impact
            if comparison['impact']['tax_increase'] > 0:
                st.error(
                    f"⚠️ **TCJA Sunset Impact**: Your estate tax would increase by "
                    f"{format_currency(comparison['impact']['tax_increase'])} in 2026, "
                    f"reducing the net amount to heirs by the same amount."
                )
                
                st.info(
                    "💡 **Planning Strategies to Consider:**\n"
                    "• Make lifetime gifts to use exemption before 2026\n"
                    "• Consider grantor trusts (GRATs, CLATs)\n"
                    "• Review life insurance planning\n"
                    "• Consult with an estate planning attorney"
                )
            else:
                st.success("✅ Your estate is not significantly impacted by the TCJA sunset.")
        
        except Exception as e:
            st.error(f"Error analyzing TCJA impact: {str(e)}")
    
    # Save calculation data
    if st.button("💾 Save Tax Calculation", key="save_tax_calc"):
        if _save_estate_data(estate):
            st.success("✅ Tax calculation data saved!")
        else:
            st.error("❌ Error saving tax calculation data.")

# ===========================================================================
# TAB 3 — BENEFICIARY PLANNING
# ===========================================================================

with tab_beneficiary:
    st.header("👥 Beneficiary Planning & Optimization")
    st.markdown(
        "Analyze inherited IRA strategies, compare spousal options, and model trust beneficiaries. "
        "SECURE Act 2.0 compliant with 10-year rule and stretch IRA calculations."
    )
    
    # Initialize beneficiary data
    ben_data = estate.setdefault("beneficiary_planning", {})
    
    # Strategy Selection
    st.subheader("📊 Select Analysis Type")
    
    analysis_type = st.selectbox(
        "Choose Beneficiary Analysis",
        options=[
            "Inherited IRA (10-Year Rule)",
            "Stretch IRA (Eligible Designated Beneficiary)",
            "Spousal Options Comparison",
            "Trust as Beneficiary",
            "Compare Multiple Strategies",
        ],
        key="ben_analysis_type"
    )
    
    if analysis_type == "Inherited IRA (10-Year Rule)":
        st.subheader("📉 10-Year Rule Analysis (SECURE Act)")
        st.info("Non-spouse beneficiaries must withdraw entire IRA balance within 10 years of owner's death.")
        
        col1, col2 = st.columns(2)
        
        with col1:
            ira_balance = st.number_input(
                "IRA Balance ($)",
                min_value=0,
                value=ben_data.get("ira_balance", 500_000),
                step=10_000,
                key="ben_ira_balance"
            )
            
            beneficiary_age = st.number_input(
                "Beneficiary Age",
                min_value=0,
                max_value=120,
                value=ben_data.get("beneficiary_age", 45),
                key="ben_age"
            )
        
        with col2:
            tax_rate = st.slider(
                "Beneficiary Tax Rate",
                min_value=0.0,
                max_value=0.50,
                value=ben_data.get("tax_rate", 0.24),
                step=0.01,
                format="%.0f%%",
                key="ben_tax_rate"
            )
            
            growth_rate = st.slider(
                "Expected Annual Return",
                min_value=0.0,
                max_value=0.15,
                value=0.07,
                step=0.01,
                format="%.0f%%",
                key="ben_growth"
            )
        
        if st.button("Calculate 10-Year Rule", key="calc_10year"):
            try:
                result = calculate_inherited_ira_10_year_rule(
                    initial_balance=ira_balance,
                    beneficiary_age=beneficiary_age,
                    beneficiary_tax_rate=tax_rate,
                    annual_growth_rate=growth_rate,
                )
                
                # Display results
                st.success("✅ Calculation Complete")
                
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Total Distributions", format_currency(result.total_distributions))
                with col2:
                    st.metric("Total Taxes", format_currency(result.total_taxes_paid))
                with col3:
                    st.metric("Net to Beneficiary", format_currency(result.net_to_beneficiary))
                
                # Year-by-year breakdown
                st.subheader("📅 Year-by-Year Distributions")
                df = pd.DataFrame(result.annual_distributions)
                df['year'] = df['year'].astype(int)
                df['distribution'] = df['distribution'].apply(lambda x: f"${x:,.0f}")
                df['tax'] = df['tax'].apply(lambda x: f"${x:,.0f}")
                df['after_tax_distribution'] = df['after_tax_distribution'].apply(lambda x: f"${x:,.0f}")
                st.dataframe(df[['year', 'distribution', 'tax', 'after_tax_distribution']], use_container_width=True)
                
            except Exception as e:
                st.error(f"Error: {str(e)}")
    
    elif analysis_type == "Spousal Options Comparison":
        st.subheader("💑 Spousal Beneficiary Options")
        st.info("Surviving spouses can rollover to own IRA or remain as beneficiary. Compare both options.")
        
        col1, col2 = st.columns(2)
        
        with col1:
            ira_balance = st.number_input(
                "IRA Balance ($)",
                min_value=0,
                value=800_000,
                step=10_000,
                key="spouse_ira_balance"
            )
            
            spouse_age = st.number_input(
                "Spouse Age",
                min_value=0,
                max_value=120,
                value=62,
                key="spouse_age"
            )
        
        with col2:
            spouse_tax_rate = st.slider(
                "Spouse Tax Rate",
                min_value=0.0,
                max_value=0.50,
                value=0.24,
                step=0.01,
                format="%.0f%%",
                key="spouse_tax_rate"
            )
        
        if st.button("Compare Spousal Options", key="calc_spouse"):
            try:
                result = compare_spousal_options(
                    initial_balance=ira_balance,
                    spouse_age=spouse_age,
                    spouse_tax_rate=spouse_tax_rate,
                )
                
                st.success("✅ Comparison Complete")
                
                # Recommendation
                st.subheader("🎯 Recommendation")
                if result.recommended_option == 'rollover':
                    st.success(f"**Recommended: Rollover to Own IRA**")
                else:
                    st.success(f"**Recommended: Remain as Beneficiary**")
                
                st.write("**Key Factors:**")
                for factor in result.key_factors:
                    st.write(f"• {factor}")
                
                # Side-by-side comparison
                col1, col2 = st.columns(2)
                
                with col1:
                    st.write("**Rollover Option:**")
                    st.metric("Net to Spouse", format_currency(result.rollover_option.net_to_beneficiary))
                    st.metric("Effective Tax Rate", format_percentage(result.rollover_option.effective_tax_rate))
                
                with col2:
                    st.write("**Inherited IRA Option:**")
                    st.metric("Net to Spouse", format_currency(result.inherited_option.net_to_beneficiary))
                    st.metric("Effective Tax Rate", format_percentage(result.inherited_option.effective_tax_rate))
                
                st.metric("Savings with Recommended Option", format_currency(result.savings_amount))
                
            except Exception as e:
                st.error(f"Error: {str(e)}")
    
    elif analysis_type == "Trust as Beneficiary":
        st.subheader("🏛️ Trust Beneficiary Analysis")
        st.info("Analyze tax implications when a trust is named as IRA beneficiary.")
        
        col1, col2 = st.columns(2)
        
        with col1:
            ira_balance = st.number_input(
                "IRA Balance ($)",
                min_value=0,
                value=1_000_000,
                step=10_000,
                key="trust_ira_balance"
            )
            
            trust_type = st.selectbox(
                "Trust Type",
                options=["conduit", "accumulation", "see-through"],
                key="trust_type"
            )
        
        with col2:
            oldest_ben_age = st.number_input(
                "Oldest Beneficiary Age",
                min_value=0,
                max_value=120,
                value=40,
                key="oldest_ben_age"
            )
            
            admin_cost = st.number_input(
                "Annual Admin Cost ($)",
                min_value=0,
                value=5000,
                step=1000,
                key="trust_admin"
            )
        
        if st.button("Analyze Trust Beneficiary", key="calc_trust"):
            try:
                result = calculate_trust_beneficiary(
                    initial_balance=ira_balance,
                    trust_type=trust_type,
                    oldest_beneficiary_age=oldest_ben_age,
                    annual_admin_cost=admin_cost,
                )
                
                st.success("✅ Analysis Complete")
                
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Net to Beneficiaries", format_currency(result.net_to_beneficiaries))
                with col2:
                    st.metric("Total Taxes", format_currency(result.total_taxes_paid))
                with col3:
                    st.metric("Admin Costs", format_currency(result.trust_administration_costs))
                
                st.write(f"**Trust Type:** {result.trust_type.title()}")
                st.write(f"**Qualifies as Designated Beneficiary:** {'Yes' if result.qualifies_as_designated_beneficiary else 'No'}")
                st.write(f"**Distribution Method:** {result.distribution_method}")
                
            except Exception as e:
                st.error(f"Error: {str(e)}")


# ===========================================================================
# TAB 4 — CHARITABLE GIVING
# ===========================================================================

with tab_charitable:
    st.header("🎁 Advanced Charitable Giving Strategies")
    st.markdown(
        "Model Charitable Remainder Trusts (CRT), Charitable Lead Trusts (CLT), "
        "and compare Private Foundations vs. Donor Advised Funds (DAF)."
    )
    
    # Initialize charitable data
    char_data = estate.setdefault("charitable_giving", {})
    
    # Strategy Selection
    st.subheader("📊 Select Charitable Strategy")
    
    char_strategy = st.selectbox(
        "Choose Strategy to Analyze",
        options=[
            "Charitable Remainder Trust (CRUT)",
            "Charitable Remainder Trust (CRAT)",
            "Charitable Lead Trust (CLUT)",
            "Charitable Lead Trust (CLAT)",
            "Private Foundation vs. DAF",
            "Qualified Charitable Distribution (QCD)",
        ],
        key="char_strategy"
    )
    
    if char_strategy == "Charitable Remainder Trust (CRUT)":
        st.subheader("💰 CRUT Analysis (Unitrust)")
        st.info("CRUT pays a fixed percentage of trust value each year (revalued annually). Provides inflation protection.")
        
        col1, col2 = st.columns(2)
        
        with col1:
            funding = st.number_input(
                "Initial Funding ($)",
                min_value=0,
                value=1_000_000,
                step=50_000,
                key="crut_funding"
            )
            
            payout_rate = st.slider(
                "Annual Payout Rate",
                min_value=0.05,
                max_value=0.50,
                value=0.05,
                step=0.01,
                format="%.0f%%",
                key="crut_payout"
            )
        
        with col2:
            term_years = st.number_input(
                "Term (Years)",
                min_value=1,
                max_value=50,
                value=20,
                key="crut_term"
            )
            
            donor_age = st.number_input(
                "Donor Age",
                min_value=0,
                max_value=120,
                value=65,
                key="crut_age"
            )
        
        if st.button("Calculate CRUT", key="calc_crut"):
            try:
                result = calculate_crt_crut(
                    initial_funding=funding,
                    payout_rate=payout_rate,
                    term_years=term_years,
                    donor_age=donor_age,
                )
                
                st.success("✅ CRUT Analysis Complete")
                
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("Total Income", format_currency(result.total_income_received))
                with col2:
                    st.metric("Net Income", format_currency(result.net_income_to_donor))
                with col3:
                    st.metric("To Charity", format_currency(result.charitable_remainder))
                with col4:
                    st.metric("Tax Savings", format_currency(result.effective_tax_savings))
                
                st.write(f"**Initial Tax Deduction:** {format_currency(result.initial_tax_deduction)}")
                st.write(f"**Present Value of Remainder:** {format_currency(result.present_value_remainder)}")
                
            except Exception as e:
                st.error(f"Error: {str(e)}")
    
    elif char_strategy == "Private Foundation vs. DAF":
        st.subheader("🏛️ Private Foundation vs. Donor Advised Fund")
        st.info("Compare costs, control, and grant efficiency between private foundations and DAFs.")
        
        col1, col2 = st.columns(2)
        
        with col1:
            contribution = st.number_input(
                "Initial Contribution ($)",
                min_value=0,
                value=5_000_000,
                step=100_000,
                key="pf_contribution"
            )
        
        with col2:
            years = st.number_input(
                "Years to Project",
                min_value=1,
                max_value=50,
                value=20,
                key="pf_years"
            )
        
        if st.button("Compare Foundation vs. DAF", key="calc_pf_daf"):
            try:
                result = compare_foundation_vs_daf(
                    contribution_amount=contribution,
                    years=years,
                )
                
                st.success("✅ Comparison Complete")
                
                # Recommendation
                st.subheader("🎯 Recommendation")
                st.success(f"**Recommended: {result.recommended_strategy}**")
                
                st.write("**Key Factors:**")
                for factor in result.key_factors:
                    st.write(f"• {factor}")
                
                # Side-by-side comparison
                col1, col2 = st.columns(2)
                
                with col1:
                    st.write("**Private Foundation:**")
                    pf_data = result.strategies['Private Foundation']
                    st.metric("Total Grants", format_currency(pf_data['Total Grants']))
                    st.metric("Total Costs", format_currency(pf_data['Total Costs']))
                    st.metric("Ending Balance", format_currency(pf_data['Ending Balance']))
                    st.write(f"Control Level: {pf_data['Control Level']}/100")
                    st.write(f"Complexity: {pf_data['Complexity']}/100")
                
                with col2:
                    st.write("**Donor Advised Fund:**")
                    daf_data = result.strategies['Donor Advised Fund']
                    st.metric("Total Grants", format_currency(daf_data['Total Grants']))
                    st.metric("Total Costs", format_currency(daf_data['Total Costs']))
                    st.metric("Ending Balance", format_currency(daf_data['Ending Balance']))
                    st.write(f"Control Level: {daf_data['Control Level']}/100")
                    st.write(f"Complexity: {daf_data['Complexity']}/100")
                
                # Tax efficiency ranking
                st.subheader("📊 Tax Efficiency Ranking")
                for i, (strategy, efficiency) in enumerate(result.tax_efficiency_ranking, 1):
                    st.write(f"{i}. {strategy}: {format_percentage(efficiency)}")
                
            except Exception as e:
                st.error(f"Error: {str(e)}")
    
    elif char_strategy == "Qualified Charitable Distribution (QCD)":
        st.subheader("💝 QCD Benefit Analysis")
        st.info("QCDs allow direct IRA-to-charity transfers (up to $105,000/year) that satisfy RMDs without increasing taxable income.")
        
        col1, col2 = st.columns(2)
        
        with col1:
            ira_balance = st.number_input(
                "IRA Balance ($)",
                min_value=0,
                value=500_000,
                step=10_000,
                key="qcd_balance"
            )
            
            donor_age = st.number_input(
                "Donor Age",
                min_value=0,
                max_value=120,
                value=72,
                key="qcd_age"
            )
        
        with col2:
            qcd_amount = st.number_input(
                "QCD Amount ($)",
                min_value=0,
                max_value=105_000,
                value=50_000,
                step=5_000,
                key="qcd_amount"
            )
            
            tax_rate = st.slider(
                "Marginal Tax Rate",
                min_value=0.0,
                max_value=0.50,
                value=0.24,
                step=0.01,
                format="%.0f%%",
                key="qcd_tax_rate"
            )
        
        if st.button("Calculate QCD Benefit", key="calc_qcd"):
            try:
                result = calculate_qcd_benefit(
                    ira_balance=ira_balance,
                    donor_age=donor_age,
                    qcd_amount=qcd_amount,
                    marginal_tax_rate=tax_rate,
                )
                
                if result.get('eligible'):
                    st.success("✅ QCD Analysis Complete")
                    
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("QCD Amount", format_currency(result['qcd_amount']))
                    with col2:
                        st.metric("Tax Savings", format_currency(result['tax_savings']))
                    with col3:
                        st.metric("Total Benefit", format_currency(result['total_benefit']))
                    
                    st.write(f"**IRMAA Savings:** {format_currency(result['irmaa_savings'])}")
                    st.write(f"**Effective Benefit Rate:** {format_percentage(result['effective_benefit_rate'])}")
                else:
                    st.warning(f"❌ Not Eligible: {result.get('reason')}")
                
            except Exception as e:
                st.error(f"Error: {str(e)}")



# ===========================================================================
# TAB 2 — LEGAL DOCUMENTS CHECKLIST
# ===========================================================================

with tab_legal:
    st.header("⚖️ Legal Documents Checklist")
    st.markdown("Track the status of each legal document. Check off items as they are completed.")

    legal = estate.setdefault("legal", {})

    def _legal_section(key: str, title: str, items: list[tuple[str, str, list[str]]]) -> None:
        """Render a legal checklist section.

        Args:
            key: Unique key prefix for session state.
            title: Section heading.
            items: List of (item_key, label, sub_steps) tuples.
        """
        st.subheader(title)
        section = legal.setdefault(key, {})
        for item_key, label, sub_steps in items:
            item = section.setdefault(item_key, {"done": False, "notes": "", "steps": {}})
            col1, col2 = st.columns([3, 1])
            with col1:
                item["done"] = st.checkbox(label, value=item.get("done", False), key=f"legal_{key}_{item_key}")
            with col2:
                if item["done"]:
                    st.markdown("✅ Complete")
                else:
                    st.markdown("⬜ Pending")
            if sub_steps:
                with st.expander(f"📋 Steps to complete: {label}", expanded=False):
                    steps = item.setdefault("steps", {})
                    for i, step in enumerate(sub_steps):
                        step_key = f"step_{i}"
                        steps[step_key] = st.checkbox(
                            step, value=steps.get(step_key, False),
                            key=f"legal_{key}_{item_key}_step_{i}"
                        )
            item["notes"] = st.text_input(
                "Notes", value=item.get("notes", ""),
                key=f"legal_{key}_{item_key}_notes",
                placeholder="Attorney name, date completed, location of document…",
                label_visibility="collapsed",
            )
        st.markdown("---")

    _legal_section("core_docs", "📄 Core Documents", [
        ("will", f"Last Will & Testament — {p1_name}", [
            "Choose an estate planning attorney",
            "Gather list of assets and beneficiaries",
            "Name executor / personal representative",
            "Name guardian for minor children (if applicable)",
            "Review and sign with witnesses and notary",
            "Store original in fireproof safe or with attorney",
            "Provide copies to executor",
        ]),
        ("will_p2", f"Last Will & Testament — {p2_name}", [
            "Choose an estate planning attorney",
            "Gather list of assets and beneficiaries",
            "Name executor / personal representative",
            "Name guardian for minor children (if applicable)",
            "Review and sign with witnesses and notary",
            "Store original in fireproof safe or with attorney",
        ]),
        ("trust", "Revocable Living Trust", [
            "Consult estate attorney to draft trust document",
            "Name trustee and successor trustee(s)",
            "Name beneficiaries",
            "Sign and notarize trust document",
            "Obtain EIN if required (usually not for revocable trust)",
            "Fund the trust — re-title real estate (see Financial tab)",
            "Fund the trust — transfer bank/brokerage accounts",
            "Fund the trust — update beneficiary designations",
            "Store original trust document securely",
            "Provide copies to successor trustee",
        ]),
        ("pour_over_will", "Pour-Over Will (companion to trust)", [
            "Draft with estate attorney alongside trust",
            "Sign with witnesses and notary",
            "Store with trust documents",
        ]),
    ])

    _legal_section("incapacity_docs", "🏥 Incapacity Documents", [
        ("poa_p1", f"Durable Power of Attorney — {p1_name}", [
            "Choose a trusted agent (spouse, adult child, trusted friend)",
            "Decide scope: general vs. limited powers",
            "Draft with attorney or use state-approved form",
            "Sign with witnesses and notary",
            "Provide copies to agent, financial institutions, and attorney",
        ]),
        ("poa_p2", f"Durable Power of Attorney — {p2_name}", [
            "Choose a trusted agent",
            "Draft with attorney or use state-approved form",
            "Sign with witnesses and notary",
            "Provide copies to agent and financial institutions",
        ]),
        ("hcd_p1", f"Healthcare Directive / Living Will — {p1_name}", [
            "Decide on life-sustaining treatment preferences",
            "Name a healthcare proxy / agent",
            "Draft using state-specific form",
            "Sign with witnesses and notary",
            "Provide copies to healthcare proxy, primary physician, and hospital",
            "Store copy in medical records",
        ]),
        ("hcd_p2", f"Healthcare Directive / Living Will — {p2_name}", [
            "Decide on life-sustaining treatment preferences",
            "Name a healthcare proxy / agent",
            "Draft using state-specific form",
            "Sign with witnesses and notary",
            "Provide copies to healthcare proxy and physician",
        ]),
        ("hipaa_p1", f"HIPAA Authorization — {p1_name}", [
            "List individuals authorized to receive medical information",
            "Sign and date the form",
            "Provide to primary physician and hospital",
        ]),
        ("hipaa_p2", f"HIPAA Authorization — {p2_name}", [
            "List individuals authorized to receive medical information",
            "Sign and date the form",
            "Provide to primary physician and hospital",
        ]),
    ])

    _legal_section("advanced_docs", "🏛️ Advanced / Optional Documents", [
        ("special_needs_trust", "Special Needs Trust (if applicable)", [
            "Consult a special needs attorney",
            "Identify trustee and successor trustee",
            "Draft and execute trust",
            "Fund trust appropriately (avoid disqualifying government benefits)",
        ]),
        ("ilit", "Irrevocable Life Insurance Trust (ILIT) — if estate tax concern", [
            "Consult estate attorney",
            "Create trust and name trustee",
            "Transfer life insurance policy to trust",
            "Ensure Crummey notices are sent annually",
        ]),
        ("business_succession", "Business Succession Plan (if applicable)", [
            "Identify successor(s)",
            "Value the business",
            "Draft buy-sell agreement",
            "Fund buy-sell with life insurance if appropriate",
            "Update operating agreement / shareholder agreement",
        ]),
    ])

    if st.button("💾 Save Legal Checklist", key="save_legal"):
        if _save_estate_data(estate):
            st.success("✅ Legal checklist saved!")
        else:
            st.error("❌ Error saving.")


# ===========================================================================
# TAB 3 — FINANCIAL & ACCOUNTS CHECKLIST
# ===========================================================================

with tab_financial:
    st.header("💰 Financial & Accounts Checklist")
    st.markdown(
        "Ensure all financial accounts are properly titled, beneficiaries are current, "
        "and trust funding is complete."
    )

    fin = estate.setdefault("financial", {})

    st.subheader("🏦 Beneficiary Designations")
    st.info(
        "Beneficiary designations **override** your Will. Review every account. "
        "Retirement accounts (IRA, 401k, Roth) should generally name individuals, not the trust, "
        "to preserve stretch IRA / tax-deferral benefits."
    )

    bene = fin.setdefault("beneficiaries", {})

    # Dynamic account list from config
    all_accounts = account_names if account_names else ["Account 1", "Account 2"]
    for idx, acct in enumerate(all_accounts):
        safe_key = acct.replace(" ", "_").lower()
        acct_data = bene.setdefault(safe_key, {"primary": "", "contingent": "", "reviewed": False})
        with st.expander(f"📋 {acct}", expanded=False):
            c1, c2, c3 = st.columns([2, 2, 1])
            with c1:
                acct_data["primary"] = st.text_input(
                    "Primary Beneficiary",
                    value=acct_data.get("primary", ""),
                    key=f"bene_{safe_key}_{idx}_primary",
                )
            with c2:
                acct_data["contingent"] = st.text_input(
                    "Contingent Beneficiary",
                    value=acct_data.get("contingent", ""),
                    key=f"bene_{safe_key}_{idx}_contingent",
                )
            with c3:
                acct_data["reviewed"] = st.checkbox(
                    "Reviewed ✅",
                    value=acct_data.get("reviewed", False),
                    key=f"bene_{safe_key}_{idx}_reviewed",
                )

    st.markdown("---")
    st.subheader("🏛️ Trust Funding — Accounts")
    st.markdown(
        "If you have a Revocable Living Trust, the following accounts should be re-titled "
        "in the name of the trust (or have the trust named as beneficiary where appropriate)."
    )

    trust_accts = fin.setdefault("trust_accounts", {})
    for idx, acct in enumerate(all_accounts):
        safe_key = acct.replace(" ", "_").lower()
        acct_trust = trust_accts.setdefault(safe_key, {"action": "Re-title in trust", "done": False, "notes": ""})
        col1, col2, col3 = st.columns([2, 1, 2])
        with col1:
            st.markdown(f"**{acct}**")
        with col2:
            acct_trust["done"] = st.checkbox(
                "Done", value=acct_trust.get("done", False),
                key=f"trust_acct_{safe_key}_{idx}_done"
            )
        with col3:
            acct_trust["notes"] = st.text_input(
                "Notes", value=acct_trust.get("notes", ""),
                key=f"trust_acct_{safe_key}_{idx}_notes",
                label_visibility="collapsed",
                placeholder="e.g. Named trust as contingent beneficiary",
            )

    st.markdown("---")
    st.subheader("📋 General Financial Housekeeping")

    fin_items = fin.setdefault("housekeeping", {})
    housekeeping_checklist = [
        ("joint_accounts", "Review joint account titling (JTWROS vs. tenants in common)"),
        ("tod_accounts", "Add Transfer-on-Death (TOD) designations to brokerage accounts"),
        ("pod_accounts", "Add Payable-on-Death (POD) designations to bank accounts"),
        ("life_insurance_review", "Review life insurance coverage amounts and beneficiaries"),
        ("annuity_review", "Review annuity contracts and beneficiaries"),
        ("pension_review", "Review pension survivor benefit elections"),
        ("safe_deposit", "Inventory safe deposit box contents and add authorized signer"),
        ("digital_assets", "Create digital asset inventory (crypto, online accounts, passwords)"),
        ("debt_inventory", "Create inventory of all debts (mortgage, loans, credit cards)"),
        ("credit_freeze", "Consider credit freeze to prevent identity theft"),
    ]
    for item_key, label in housekeeping_checklist:
        item = fin_items.setdefault(item_key, {"done": False, "notes": ""})
        col1, col2 = st.columns([4, 1])
        with col1:
            item["done"] = st.checkbox(label, value=item.get("done", False), key=f"fin_{item_key}")
        with col2:
            if item["done"]:
                st.markdown("✅")

    if st.button("💾 Save Financial Checklist", key="save_financial"):
        if _save_estate_data(estate):
            st.success("✅ Financial checklist saved!")
        else:
            st.error("❌ Error saving.")


# ===========================================================================
# TAB 4 — PERSONAL & PROPERTY CHECKLIST
# ===========================================================================

with tab_personal:
    st.header("🏠 Personal & Property Checklist")

    prop = estate.setdefault("property", {})

    st.subheader("🏡 Real Estate — Trust Funding & Titling")
    st.info(
        "Real estate must be **re-titled** (via a new deed) into the name of your Revocable Living Trust "
        "to avoid probate. Each property requires a separate deed recorded with the county."
    )

    re_trust = prop.setdefault("real_estate_trust", {})
    display_properties = property_names if property_names else ["Primary Residence"]
    for prop_name in display_properties:
        safe_key = prop_name.replace(" ", "_").lower()
        prop_data = re_trust.setdefault(safe_key, {
            "deed_retitled": False,
            "deed_recorded": False,
            "title_insurance_updated": False,
            "lender_notified": False,
            "notes": "",
        })
        with st.expander(f"🏠 {prop_name}", expanded=False):
            c1, c2 = st.columns(2)
            with c1:
                prop_data["deed_retitled"] = st.checkbox(
                    "New deed drafted naming trust as owner",
                    value=prop_data.get("deed_retitled", False),
                    key=f"re_{safe_key}_deed_retitled",
                )
                prop_data["deed_recorded"] = st.checkbox(
                    "Deed recorded with county recorder",
                    value=prop_data.get("deed_recorded", False),
                    key=f"re_{safe_key}_deed_recorded",
                )
            with c2:
                prop_data["title_insurance_updated"] = st.checkbox(
                    "Title insurance updated / endorsement obtained",
                    value=prop_data.get("title_insurance_updated", False),
                    key=f"re_{safe_key}_title_ins",
                )
                prop_data["lender_notified"] = st.checkbox(
                    "Mortgage lender notified (due-on-sale clause review)",
                    value=prop_data.get("lender_notified", False),
                    key=f"re_{safe_key}_lender",
                )
            prop_data["notes"] = st.text_area(
                "Notes",
                value=prop_data.get("notes", ""),
                key=f"re_{safe_key}_notes",
                height=60,
                placeholder="Attorney, date recorded, deed book/page number…",
            )

    st.markdown("---")
    st.subheader("🚗 Personal Property & Vehicles")

    personal_items = prop.setdefault("personal_items", {})
    personal_checklist = [
        ("vehicles_titled", "Review vehicle titles (add TOD or transfer to trust if allowed by state)"),
        ("valuable_items", "Create inventory of valuable personal property (jewelry, art, collectibles)"),
        ("valuable_appraisals", "Obtain appraisals for high-value items"),
        ("valuable_photos", "Photograph / video valuable items for insurance and estate purposes"),
        ("storage_units", "Document any storage unit locations and access information"),
        ("firearms", "Review firearms ownership and transfer rules (NFA items require special handling)"),
    ]
    for item_key, label in personal_checklist:
        item = personal_items.setdefault(item_key, {"done": False})
        item["done"] = st.checkbox(label, value=item.get("done", False), key=f"personal_{item_key}")

    st.markdown("---")
    st.subheader("👨‍👩‍👧 Family & Personal Housekeeping")

    family_items = prop.setdefault("family_items", {})
    family_checklist = [
        ("letter_of_instruction", "Write a Letter of Instruction (non-legal guide for executor/family)"),
        ("funeral_wishes", "Document funeral / burial / cremation wishes"),
        ("obituary_draft", "Draft an obituary or key biographical notes"),
        ("family_history", "Record family history and important stories"),
        ("pet_care", "Document pet care instructions and name a caretaker"),
        ("social_media", "Document social media account instructions (memorialization or deletion)"),
        ("email_accounts", "Document email account access and instructions"),
        ("subscriptions", "List recurring subscriptions to cancel"),
        ("employer_benefits", "Review employer death benefits, pension, and group life insurance"),
        ("military_benefits", "Review VA / military benefits if applicable"),
    ]
    for item_key, label in family_checklist:
        item = family_items.setdefault(item_key, {"done": False})
        item["done"] = st.checkbox(label, value=item.get("done", False), key=f"family_{item_key}")

    if st.button("💾 Save Personal & Property Checklist", key="save_personal"):
        if _save_estate_data(estate):
            st.success("✅ Personal & property checklist saved!")
        else:
            st.error("❌ Error saving.")


# ===========================================================================
# TAB 5 — DOCUMENT LOCATIONS
# ===========================================================================

with tab_docs:
    st.header("📁 Document Locations")
    st.markdown(
        "Record where each important document is stored. This information is critical for your "
        "executor, trustee, and family members."
    )

    doc_locs = estate.setdefault("document_locations", {})

    doc_categories = {
        "Legal Documents": [
            ("will_p1", f"Will — {p1_name}"),
            ("will_p2", f"Will — {p2_name}"),
            ("trust_doc", "Revocable Living Trust"),
            ("pour_over_will", "Pour-Over Will"),
            ("poa_p1", f"Power of Attorney — {p1_name}"),
            ("poa_p2", f"Power of Attorney — {p2_name}"),
            ("hcd_p1", f"Healthcare Directive — {p1_name}"),
            ("hcd_p2", f"Healthcare Directive — {p2_name}"),
            ("hipaa_p1", f"HIPAA Authorization — {p1_name}"),
            ("hipaa_p2", f"HIPAA Authorization — {p2_name}"),
        ],
        "Financial Documents": [
            ("tax_returns", "Tax Returns (last 7 years)"),
            ("investment_statements", "Investment Account Statements"),
            ("retirement_statements", "Retirement Account Statements"),
            ("life_insurance_policies", "Life Insurance Policies"),
            ("annuity_contracts", "Annuity Contracts"),
            ("pension_documents", "Pension / Retirement Plan Documents"),
            ("bank_statements", "Bank Account Statements"),
            ("safe_deposit_key", "Safe Deposit Box Key & Location"),
        ],
        "Real Estate Documents": [
            ("property_deeds", "Property Deeds"),
            ("mortgage_documents", "Mortgage / Loan Documents"),
            ("title_insurance", "Title Insurance Policies"),
            ("property_tax_records", "Property Tax Records"),
            ("hoa_documents", "HOA Documents"),
        ],
        "Personal Documents": [
            ("birth_certificates", "Birth Certificates"),
            ("marriage_certificate", "Marriage Certificate"),
            ("divorce_decree", "Divorce Decree (if applicable)"),
            ("passports", "Passports"),
            ("social_security_cards", "Social Security Cards"),
            ("military_records", "Military Records (if applicable)"),
            ("vehicle_titles", "Vehicle Titles"),
            ("digital_asset_inventory", "Digital Asset Inventory / Password Manager"),
        ],
    }

    for category, items in doc_categories.items():
        st.subheader(f"📂 {category}")
        cat_data = doc_locs.setdefault(category.replace(" ", "_").lower(), {})
        for item_key, label in items:
            item = cat_data.setdefault(item_key, {"location": "", "notes": "", "has_copy": False})
            with st.expander(f"📄 {label}", expanded=False):
                col1, col2, col3 = st.columns([3, 3, 1])
                with col1:
                    item["location"] = st.text_input(
                        "Location / Storage",
                        value=item.get("location", ""),
                        key=f"doc_{category}_{item_key}_loc",
                        placeholder="e.g. Fireproof safe at home, Attorney's office, Safe deposit box…",
                    )
                with col2:
                    item["notes"] = st.text_input(
                        "Notes / Contact",
                        value=item.get("notes", ""),
                        key=f"doc_{category}_{item_key}_notes",
                        placeholder="e.g. Attorney: John Smith, 555-1234",
                    )
                with col3:
                    item["has_copy"] = st.checkbox(
                        "Copy exists",
                        value=item.get("has_copy", False),
                        key=f"doc_{category}_{item_key}_copy",
                    )
        st.markdown("---")

    if st.button("💾 Save Document Locations", key="save_docs"):
        if _save_estate_data(estate):
            st.success("✅ Document locations saved!")
        else:
            st.error("❌ Error saving.")


# ===========================================================================
# TAB 6 — REVIEW SCHEDULE
# ===========================================================================

with tab_schedule:
    st.header("📅 Review Schedule")
    st.markdown(
        "Estate plans should be reviewed regularly and after major life events. "
        "Set your review dates and track completion."
    )

    sched = estate.setdefault("schedule", {})

    st.subheader("📆 Annual Review")
    st.markdown(
        "**Recommended:** Review your estate plan every year, ideally in Q1 or after tax season."
    )

    annual = sched.setdefault("annual_reviews", [])

    # Add a new review entry
    with st.expander("➕ Add Annual Review Entry", expanded=False):
        col_r1, col_r2, col_r3 = st.columns(3)
        with col_r1:
            new_review_year = st.number_input(
                "Year", min_value=2020, max_value=2050,
                value=datetime.now().year, key="new_review_year"
            )
        with col_r2:
            new_review_date = st.date_input("Review Date", value=date.today(), key="new_review_date")
        with col_r3:
            new_review_notes = st.text_input("Notes / Changes Made", key="new_review_notes")
        if st.button("Add Review", key="add_review_btn"):
            annual.append({
                "year": int(new_review_year),
                "date": str(new_review_date),
                "notes": new_review_notes,
                "completed": True,
            })
            if _save_estate_data(estate):
                st.success("✅ Review entry added!")
                st.rerun()

    if annual:
        st.markdown("**Review History:**")
        for i, rev in enumerate(sorted(annual, key=lambda x: x.get("year", 0), reverse=True)):
            st.markdown(f"- **{rev.get('year')}** — {rev.get('date', '')} — {rev.get('notes', 'No notes')}")
    else:
        st.info("No annual reviews recorded yet.")

    st.markdown("---")
    st.subheader("⚡ Trigger Events — Review Immediately After:")

    trigger_events = [
        ("marriage", "Marriage or divorce"),
        ("new_child", "Birth or adoption of a child"),
        ("death_beneficiary", "Death of a beneficiary, executor, or trustee"),
        ("major_asset", "Acquisition or sale of major asset (real estate, business)"),
        ("move_state", "Moving to a new state"),
        ("tax_law_change", "Significant change in tax law"),
        ("health_change", "Major health diagnosis"),
        ("inheritance", "Receiving a large inheritance"),
        ("business_change", "Starting, buying, or selling a business"),
        ("retirement", "Retirement"),
    ]

    triggers = sched.setdefault("triggers", {})
    for t_key, t_label in trigger_events:
        t_data = triggers.setdefault(t_key, {"occurred": False, "reviewed": False, "date": ""})
        col1, col2, col3 = st.columns([3, 1, 2])
        with col1:
            st.markdown(f"**{t_label}**")
        with col2:
            t_data["occurred"] = st.checkbox(
                "Occurred", value=t_data.get("occurred", False),
                key=f"trigger_{t_key}_occurred"
            )
        with col3:
            if t_data.get("occurred"):
                t_data["reviewed"] = st.checkbox(
                    "Plan reviewed after event",
                    value=t_data.get("reviewed", False),
                    key=f"trigger_{t_key}_reviewed"
                )

    st.markdown("---")
    st.subheader("📋 Recommended Review Checklist (Annual)")

    annual_checklist = [
        ("review_will", "Review Will for accuracy and current wishes"),
        ("review_trust", "Review Trust document and confirm all assets are funded"),
        ("review_beneficiaries", "Verify all beneficiary designations are current"),
        ("review_poa", "Confirm Power of Attorney agents are still appropriate"),
        ("review_hcd", "Confirm Healthcare Directive agents and wishes are current"),
        ("review_titling", "Review property titling (real estate, vehicles, accounts)"),
        ("review_life_insurance", "Review life insurance coverage and beneficiaries"),
        ("review_digital_assets", "Update digital asset inventory and passwords"),
        ("review_letter_of_instruction", "Update Letter of Instruction"),
        ("review_tax_law", "Review for any new tax law changes affecting estate plan"),
        ("review_attorney", "Schedule meeting with estate attorney if changes needed"),
    ]

    annual_review_items = sched.setdefault("annual_checklist", {})
    for item_key, label in annual_checklist:
        item = annual_review_items.setdefault(item_key, {"done": False})
        item["done"] = st.checkbox(label, value=item.get("done", False), key=f"annual_{item_key}")

    if st.button("💾 Save Review Schedule", key="save_schedule"):
        if _save_estate_data(estate):
            st.success("✅ Review schedule saved!")
        else:
            st.error("❌ Error saving.")


# ===========================================================================
# TAB 7 — OVERALL PROGRESS
# ===========================================================================

with tab_progress:
    st.header("📊 Overall Estate Planning Progress")
    st.markdown("A summary of your estate planning completion across all categories.")

    # ---------------------------------------------------------------------------
    # Compute completion metrics
    # ---------------------------------------------------------------------------

    def _count_items(data: dict, done_key: str = "done") -> tuple[int, int]:
        """Recursively count completed vs total checkbox items."""
        total = 0
        done = 0
        for v in data.values():
            if isinstance(v, dict):
                if done_key in v:
                    total += 1
                    if v[done_key]:
                        done += 1
                else:
                    sub_done, sub_total = _count_items(v, done_key)
                    done += sub_done
                    total += sub_total
        return done, total

    legal_done, legal_total = _count_items(estate.get("legal", {}))
    fin_done, fin_total = _count_items(estate.get("financial", {}))
    prop_done, prop_total = _count_items(estate.get("property", {}))
    sched_done, sched_total = _count_items(estate.get("schedule", {}).get("annual_checklist", {}))

    # Document locations — count items with a location filled in
    doc_loc_data = estate.get("document_locations", {})
    doc_total = 0
    doc_done = 0
    for cat_data in doc_loc_data.values():
        if isinstance(cat_data, dict):
            for item in cat_data.values():
                if isinstance(item, dict):
                    doc_total += 1
                    if item.get("location", "").strip():
                        doc_done += 1

    # Assessment completion
    assess_data = estate.get("assessment", {})
    assess_answered = sum(1 for v in assess_data.values() if isinstance(v, bool))
    assess_total_q = len([v for v in assess_data.values() if isinstance(v, bool)])

    # Overall
    overall_done = legal_done + fin_done + prop_done + sched_done + doc_done
    overall_total = legal_total + fin_total + prop_total + sched_total + doc_total

    # ---------------------------------------------------------------------------
    # Display metrics
    # ---------------------------------------------------------------------------

    st.subheader("📈 Completion Summary")

    m1, m2, m3, m4, m5, m6 = st.columns(6)
    with m1:
        pct = int(legal_done / legal_total * 100) if legal_total else 0
        st.metric("⚖️ Legal", f"{pct}%", f"{legal_done}/{legal_total} items")
    with m2:
        pct = int(fin_done / fin_total * 100) if fin_total else 0
        st.metric("💰 Financial", f"{pct}%", f"{fin_done}/{fin_total} items")
    with m3:
        pct = int(prop_done / prop_total * 100) if prop_total else 0
        st.metric("🏠 Property", f"{pct}%", f"{prop_done}/{prop_total} items")
    with m4:
        pct = int(doc_done / doc_total * 100) if doc_total else 0
        st.metric("📁 Documents", f"{pct}%", f"{doc_done}/{doc_total} located")
    with m5:
        pct = int(sched_done / sched_total * 100) if sched_total else 0
        st.metric("📅 Annual Review", f"{pct}%", f"{sched_done}/{sched_total} items")
    with m6:
        pct = int(overall_done / overall_total * 100) if overall_total else 0
        st.metric("🎯 Overall", f"{pct}%", f"{overall_done}/{overall_total} total")

    # Progress bars
    st.markdown("---")
    st.subheader("📊 Progress by Category")

    categories = [
        ("⚖️ Legal Documents", legal_done, legal_total),
        ("💰 Financial & Accounts", fin_done, fin_total),
        ("🏠 Personal & Property", prop_done, prop_total),
        ("📁 Document Locations", doc_done, doc_total),
        ("📅 Annual Review Checklist", sched_done, sched_total),
    ]

    for cat_label, done, total in categories:
        pct = done / total if total else 0
        col_label, col_bar = st.columns([2, 5])
        with col_label:
            st.markdown(f"**{cat_label}**")
            st.caption(f"{done} of {total} complete")
        with col_bar:
            st.progress(pct)

    # ---------------------------------------------------------------------------
    # Recommendations summary
    # ---------------------------------------------------------------------------
    st.markdown("---")
    st.subheader("🔴 Open Recommendations")

    assess_data = estate.get("assessment", {})
    open_recs: list[str] = []

    if not assess_data.get("has_will"):
        open_recs.append("Create a Will")
    if assess_data.get("has_real_estate") and not assess_data.get("has_trust"):
        open_recs.append("Consider a Revocable Living Trust to avoid probate on real estate")
    if assess_data.get("has_trust") and assess_data.get("has_real_estate"):
        open_recs.append("Fund the Trust — re-title real estate into trust name")
    if not assess_data.get("has_poa"):
        open_recs.append("Create a Durable Power of Attorney")
    if not assess_data.get("has_healthcare_directive"):
        open_recs.append("Create a Healthcare Directive / Living Will")
    if not assess_data.get("beneficiaries_current"):
        open_recs.append("Update beneficiary designations on all accounts")
    if not assess_data.get("titling_reviewed"):
        open_recs.append("Review property titling")

    if open_recs:
        for rec in open_recs:
            st.markdown(f"- 🔴 {rec}")
    else:
        st.success("✅ No open recommendations! Keep reviewing annually.")

    # ---------------------------------------------------------------------------
    # Next review date
    # ---------------------------------------------------------------------------
    st.markdown("---")
    st.subheader("📅 Next Scheduled Review")

    next_review = sched.get("next_review_date", "")
    col_nr1, col_nr2 = st.columns([2, 3])
    with col_nr1:
        new_next = st.date_input(
            "Set Next Review Date",
            value=date.fromisoformat(next_review) if next_review else date(datetime.now().year + 1, 1, 15),
            key="next_review_date_input",
        )
        sched["next_review_date"] = str(new_next)
    with col_nr2:
        days_until = (new_next - date.today()).days
        if days_until < 0:
            st.warning(f"⚠️ Review is **overdue** by {abs(days_until)} days!")
        elif days_until == 0:
            st.success("✅ Review is scheduled for **today**!")
        elif days_until <= 30:
            st.info(f"📅 Review is in **{days_until} days** ({new_next.strftime('%B %d, %Y')})")
        else:
            st.success(f"✅ Next review: **{new_next.strftime('%B %d, %Y')}** ({days_until} days away)")

