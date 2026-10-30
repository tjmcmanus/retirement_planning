"""Streamlit-free service for Estate Planning and tax modeling.

Wraps ``estate_tax_calculations.py``, ``beneficiary_optimization.py``,
and ``charitable_giving_advanced.py``, and manages persistence for ``estate_planning_data.json``.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from config import get_config_manager
from beneficiary_optimization import (
    calculate_inherited_ira_10_year_rule,
    calculate_stretch_ira,
    compare_beneficiary_strategies,
    compare_spousal_options,
    calculate_trust_beneficiary,
)
from charitable_giving_advanced import (
    calculate_clt_clat,
    calculate_clt_clut,
    calculate_crt_crat,
    calculate_crt_crut,
    calculate_daf,
    calculate_private_foundation,
    calculate_qcd_benefit,
    compare_foundation_vs_daf,
)
from estate_tax_calculations import (
    FEDERAL_ESTATE_TAX_EXEMPTIONS,
    FEDERAL_ESTATE_TAX_RATE,
    STATE_ESTATE_TAXES,
    STATE_INHERITANCE_TAXES,
    calculate_comprehensive_estate_tax,
    calculate_federal_estate_tax,
    calculate_gstt,
    calculate_inheritance_tax,
    calculate_lifetime_gift_impact,
    calculate_state_estate_tax,
    compare_tcja_sunset_impact,
    get_annual_gift_exclusion,
    get_federal_exemption,
    is_tcja_in_effect,
)
import settings

logger = logging.getLogger(__name__)

FEDERAL_ESTATE_TAX_THRESHOLD_NOTE = "$13M (2024, scheduled to drop ~$7M in 2026 per TCJA sunset)"


def _get_estate_file_path() -> Path:
    return settings.data_path("estate_planning_data.json")


def load_estate_data() -> dict[str, Any]:
    """Load estate planning data from JSON file."""
    path = _get_estate_file_path()
    if path.exists():
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.warning("Could not load estate data from %s: %s", path, e)
    return {}


def save_estate_data(data: dict[str, Any]) -> None:
    """Persist estate planning data to JSON file."""
    path = _get_estate_file_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(".tmp")
    with open(temp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, default=str)
    temp_path.replace(path)


def get_estate_metadata() -> dict[str, Any]:
    """Retrieve config personalization details (names, accounts, properties, children)."""
    config_mgr = get_config_manager()
    p1_name = config_mgr.get("personal_info", "person1_name", "Person 1") or "Person 1"
    p2_name = config_mgr.get("personal_info", "person2_name", "Person 2") or "Person 2"

    accounts_raw = config_mgr.get("portfolio_accounts", "accounts", []) or []
    account_names = [a.get("account_name", "") for a in accounts_raw if a.get("account_name")]

    properties_raw = config_mgr.get("real_estate", "properties", []) or []
    property_names = [p.get("property_name", "") for p in properties_raw if p.get("property_name")]

    children_cfg = config_mgr.get("personal_info", "children", []) or []
    if not isinstance(children_cfg, list):
        children_cfg = []

    has_minor = any(
        config_mgr.calculate_age(c.get("birth_date", "1900-01-01")) < 18
        for c in children_cfg
    )
    has_adult = any(
        config_mgr.calculate_age(c.get("birth_date", "1900-01-01")) >= 18
        for c in children_cfg
    )
    has_special = any(c.get("special_needs", False) for c in children_cfg)

    children_details = []
    for ci, child in enumerate(children_cfg):
        cname = child.get("name", f"Child {ci + 1}")
        cbdate = child.get("birth_date", "")
        cage = config_mgr.calculate_age(cbdate) if cbdate else None
        csn = child.get("special_needs", False)
        children_details.append({
            "name": cname,
            "age": cage,
            "special_needs": csn,
            "birth_date": cbdate,
        })

    return {
        "person1_name": p1_name,
        "person2_name": p2_name,
        "account_names": account_names,
        "property_names": property_names,
        "children": children_details,
        "has_minor_children": has_minor,
        "has_adult_children": has_adult,
        "has_special_needs": has_special,
        "state_estate_tax_states": list(STATE_ESTATE_TAXES.keys()),
        "state_inheritance_tax_states": list(STATE_INHERITANCE_TAXES.keys()),
        "exemption_years": list(FEDERAL_ESTATE_TAX_EXEMPTIONS.keys()),
    }


def compute_recommendations(assess: dict[str, Any], meta: dict[str, Any]) -> list[dict[str, str]]:
    """Generate prioritized actionable recommendations from the assessment."""
    recs = []

    if not assess.get("has_will"):
        recs.append({
            "level": "red",
            "title": "Create a Will",
            "desc": "You do not have a current Will. This is the foundation of any estate plan.",
        })
    if assess.get("has_real_estate") and not assess.get("has_trust"):
        recs.append({
            "level": "red",
            "title": "Consider a Revocable Living Trust",
            "desc": "You own real estate. A trust allows your estate to avoid probate, which can be costly and time-consuming. Real estate must be re-titled into the trust.",
        })
    if assess.get("has_trust") and assess.get("has_real_estate"):
        recs.append({
            "level": "yellow",
            "title": "Fund the Trust — Re-title Real Estate",
            "desc": "You have a trust but need to confirm all real estate is titled in the name of the trust to avoid probate.",
        })
    if assess.get("has_trust") and assess.get("has_retirement_accounts"):
        recs.append({
            "level": "yellow",
            "title": "Fund the Trust — Review Retirement Account Beneficiaries",
            "desc": "Do NOT title retirement accounts in the trust (tax consequences). Instead, name the trust as contingent beneficiary if appropriate, or name individuals directly.",
        })
    if not assess.get("has_poa"):
        recs.append({
            "level": "red",
            "title": "Create a Durable Power of Attorney",
            "desc": "Allows a trusted person to manage finances if you are incapacitated.",
        })
    if not assess.get("has_healthcare_directive"):
        recs.append({
            "level": "red",
            "title": "Create a Healthcare Directive / Living Will",
            "desc": "Documents your medical wishes and names a healthcare proxy.",
        })
    if not assess.get("beneficiaries_current"):
        recs.append({
            "level": "yellow",
            "title": "Update Beneficiary Designations",
            "desc": "Review all retirement accounts, life insurance, and bank accounts.",
        })
    if assess.get("minor_children") and not assess.get("has_will"):
        recs.append({
            "level": "red",
            "title": "Name a Guardian in Your Will",
            "desc": "You have minor children. A Will is the only way to legally name a guardian.",
        })
    if assess.get("special_needs_dependent"):
        sn_names = [c["name"] for c in meta.get("children", []) if c.get("special_needs")]
        sn_label = f" ({', '.join(sn_names)})" if sn_names else ""
        recs.append({
            "level": "red",
            "title": f"Establish a Special Needs Trust (SNT){sn_label}",
            "desc": "Direct inheritance can disqualify special needs dependents from government benefits (SSI, Medicaid). A Third-Party SNT protects eligibility.",
        })
    if assess.get("blended_family"):
        recs.append({
            "level": "yellow",
            "title": "Consider a QTIP or Bloodline Trust",
            "desc": "Blended families require careful trust structuring to provide for the surviving spouse while protecting inheritance for children from prior marriages.",
        })
    if assess.get("has_business"):
        recs.append({
            "level": "yellow",
            "title": "Create a Business Succession Plan",
            "desc": "Ensure a Buy-Sell Agreement, Key Person Insurance, and transfer plan are in place.",
        })
    if assess.get("estate_over_threshold"):
        recs.append({
            "level": "red",
            "title": "Estate Tax Planning Required",
            "desc": f"Your estate exceeds {FEDERAL_ESTATE_TAX_THRESHOLD_NOTE}. Consider ILITs, SLATs, Spousal Portability, and lifetime gifting.",
        })
    if assess.get("has_digital_assets"):
        recs.append({
            "level": "yellow",
            "title": "Document Digital Assets & Passwords",
            "desc": "Create a digital asset inventory with access instructions and appoint a digital executor.",
        })
    if not assess.get("titling_reviewed"):
        recs.append({
            "level": "yellow",
            "title": "Review Account & Property Titling",
            "desc": "Ensure titling (JTWROS, Tenancy by Entirety, Trust) aligns with your estate distribution goals.",
        })

    if not recs:
        recs.append({
            "level": "green",
            "title": "Good Baseline Plan",
            "desc": "Your core documents and titling are in place. Keep review schedules updated annually.",
        })

    return recs


def compute_progress_summary(data: dict[str, Any], meta: dict[str, Any]) -> dict[str, Any]:
    """Calculate progress stats across all checklist categories."""
    categories: list[dict[str, Any]] = []

    # 1. Legal Documents
    legal = data.get("legal", {})
    legal_done = 0
    legal_total = 0
    pending_items = []

    for group_key, group_title in [
        ("core_docs", "Core Legal Documents"),
        ("incapacity_docs", "Incapacity Planning"),
        ("advanced_docs", "Advanced Trusts"),
    ]:
        docs = legal.get(group_key, {})
        for doc_key, doc_val in docs.items():
            legal_total += 1
            if isinstance(doc_val, dict) and doc_val.get("done"):
                legal_done += 1
            else:
                doc_title = doc_key.replace("_", " ").title()
                pending_items.append(f"Legal: {doc_title}")

    legal_pct = (legal_done / legal_total * 100) if legal_total else 0
    categories.append({
        "name": "Legal Documents",
        "done": legal_done,
        "total": legal_total,
        "percent": round(legal_pct, 1),
    })

    # 2. Financial & Beneficiaries
    fin = data.get("financial", {})
    fin_done = 0
    fin_total = 0

    # Beneficiaries
    bens = fin.get("beneficiaries", {})
    for acc_key, acc_val in bens.items():
        fin_total += 1
        if isinstance(acc_val, dict) and acc_val.get("reviewed"):
            fin_done += 1
        else:
            pending_items.append(f"Beneficiary review: {acc_key}")

    # Trust accounts
    trust_accs = fin.get("trust_accounts", {})
    for acc_key, acc_val in trust_accs.items():
        fin_total += 1
        if isinstance(acc_val, dict) and acc_val.get("done"):
            fin_done += 1
        else:
            pending_items.append(f"Trust re-title: {acc_key}")

    # Housekeeping
    hk = fin.get("housekeeping", {})
    for k, v in hk.items():
        fin_total += 1
        if isinstance(v, dict) and v.get("done"):
            fin_done += 1
        else:
            pending_items.append(f"Financial task: {k.replace('_', ' ').title()}")

    fin_pct = (fin_done / fin_total * 100) if fin_total else 0
    categories.append({
        "name": "Financial & Accounts",
        "done": fin_done,
        "total": fin_total,
        "percent": round(fin_pct, 1),
    })

    # 3. Personal & Property
    prop = data.get("property", {})
    prop_done = 0
    prop_total = 0

    re_trust = prop.get("real_estate_trust", {})
    for pk, pv in re_trust.items():
        prop_total += 4
        if isinstance(pv, dict):
            if pv.get("deed_retitled"): prop_done += 1
            if pv.get("deed_recorded"): prop_done += 1
            if pv.get("title_insurance_updated"): prop_done += 1
            if pv.get("lender_notified"): prop_done += 1
            if not pv.get("deed_retitled"):
                pending_items.append(f"Property deed re-title: {pk}")

    for sub_key in ("personal_items", "family_items"):
        sub = prop.get(sub_key, {})
        for item_key, item_val in sub.items():
            prop_total += 1
            if isinstance(item_val, dict) and item_val.get("done"):
                prop_done += 1
            else:
                pending_items.append(f"Personal item: {item_key.replace('_', ' ').title()}")

    prop_pct = (prop_done / prop_total * 100) if prop_total else 0
    categories.append({
        "name": "Personal & Property",
        "done": prop_done,
        "total": prop_total,
        "percent": round(prop_pct, 1),
    })

    # 4. Document Locations
    doc_locs = data.get("document_locations", {})
    loc_done = 0
    loc_total = 0

    for section_k, section_v in doc_locs.items():
        if isinstance(section_v, dict):
            for item_k, item_v in section_v.items():
                loc_total += 1
                if isinstance(item_v, dict) and (item_v.get("location") or item_v.get("has_copy")):
                    loc_done += 1

    loc_pct = (loc_done / loc_total * 100) if loc_total else 0
    categories.append({
        "name": "Document Locations",
        "done": loc_done,
        "total": loc_total,
        "percent": round(loc_pct, 1),
    })

    # Totals
    total_done = legal_done + fin_done + prop_done + loc_done
    total_items = legal_total + fin_total + prop_total + loc_total
    overall_pct = (total_done / total_items * 100) if total_items else 0

    return {
        "categories": categories,
        "total_done": total_done,
        "total_items": total_items,
        "overall_percent": round(overall_pct, 1),
        "pending_items": pending_items[:25],  # top 25 pending tasks
    }


def get_estate_overview() -> dict[str, Any]:
    """Return full estate data, metadata, recommendations, and progress."""
    data = load_estate_data()
    meta = get_estate_metadata()

    # Sync children and property names into data structure if missing
    assess = data.setdefault("assessment", {})
    if meta.get("children"):
        assess["minor_children"] = meta["has_minor_children"]
        assess["adult_children"] = meta["has_adult_children"]
        assess["special_needs_dependent"] = meta["has_special_needs"]

    # Ensure all properties from config are present under real_estate_trust
    re_trust = data.setdefault("property", {}).setdefault("real_estate_trust", {})
    for pname in meta.get("property_names", []):
        pkey = pname.lower().replace(" ", "_").replace("-", "_")
        if pkey not in re_trust:
            re_trust[pkey] = {
                "deed_retitled": False,
                "deed_recorded": False,
                "title_insurance_updated": False,
                "lender_notified": False,
                "notes": "",
            }

    # Ensure accounts are in beneficiaries and trust_accounts
    bens = data.setdefault("financial", {}).setdefault("beneficiaries", {})
    trust_accs = data.setdefault("financial", {}).setdefault("trust_accounts", {})
    for aname in meta.get("account_names", []):
        akey = aname.lower().replace(" ", "_").replace("-", "_")
        if akey not in bens:
            bens[akey] = {"primary": "", "contingent": "", "reviewed": False}
        if akey not in trust_accs:
            trust_accs[akey] = {"action": "Re-title in trust", "done": False, "notes": ""}

    recs = compute_recommendations(assess, meta)
    progress = compute_progress_summary(data, meta)

    return {
        "data": data,
        "meta": meta,
        "recommendations": recs,
        "progress": progress,
    }


def update_estate_section(section: str, patch: dict[str, Any]) -> dict[str, Any]:
    """Partially update a specific section and persist to JSON."""
    data = load_estate_data()

    if section not in data:
        data[section] = {}

    def deep_merge(target: dict[str, Any], source: dict[str, Any]) -> None:
        for k, v in source.items():
            if isinstance(v, dict) and isinstance(target.get(k), dict):
                deep_merge(target[k], v)
            else:
                target[k] = v

    if isinstance(patch, dict):
        deep_merge(data[section], patch)

    save_estate_data(data)
    return get_estate_overview()


# ---------------------------------------------------------------------------
# Calculators
# ---------------------------------------------------------------------------

def calculate_estate_tax(payload: dict[str, Any]) -> dict[str, Any]:
    """Run comprehensive estate and inheritance tax calculations."""
    year = int(payload.get("year", datetime.now().year))
    estate_val = float(payload.get("estate_value", 10_000_000))
    gifts = float(payload.get("prior_taxable_gifts", 0))
    state = str(payload.get("state", "None"))
    state_code = state if state != "None" else None
    portability = float(payload.get("deceased_spousal_unused_exemption", 0))

    # Comprehensive tax calculation
    comp = calculate_comprehensive_estate_tax(
        gross_estate=estate_val,
        year=year,
        state_code=state_code,
        prior_exemption_used=gifts,
        portability_from_spouse=portability,
    )

    # TCJA Sunset Comparison
    tcja_comp = compare_tcja_sunset_impact(
        gross_estate=estate_val,
        prior_exemption_used=gifts,
        state_code=state_code,
    )

    # Gifting impact
    recipients = int(payload.get("gift_recipients", 2))
    years_gifting = int(payload.get("gift_years", 10))
    annual_gift_per_recipient = float(get_annual_gift_exclusion(year))
    gift_impact = calculate_lifetime_gift_impact(
        annual_gifts=annual_gift_per_recipient,
        years=years_gifting,
        num_recipients=recipients,
        year_start=year,
    )

    fed_res = comp.federal_result
    state_res = comp.state_result

    return {
        "comprehensive": {
            "gross_estate": fed_res.gross_estate,
            "federal_exemption": fed_res.exemption_available,
            "taxable_estate": fed_res.taxable_estate,
            "federal_tax": fed_res.estate_tax,
            "state_tax": state_res.estate_tax if state_res else 0.0,
            "total_tax": comp.total_tax_burden,
            "effective_tax_rate": comp.effective_total_rate,
            "net_to_heirs": comp.net_to_heirs,
            "has_tcja_impact": fed_res.tcja_in_effect,
        },
        "tcja_comparison": {
            "current_exemption": tcja_comp.get("year_2025", {}).get("exemption", 0.0),
            "post_sunset_exemption": tcja_comp.get("year_2026", {}).get("exemption", 0.0),
            "current_federal_tax": tcja_comp.get("year_2025", {}).get("total_tax", 0.0),
            "post_sunset_federal_tax": tcja_comp.get("year_2026", {}).get("total_tax", 0.0),
            "additional_tax_due_to_sunset": tcja_comp.get("impact", {}).get("tax_increase", 0.0),
            "percentage_increase": tcja_comp.get("impact", {}).get("tax_increase_pct", 0.0),
        },
        "gifting_impact": {
            "total_gifted": gift_impact.get("total_gifts", 0),
            "tax_free_gifts": gift_impact.get("within_exclusion", 0),
            "taxable_gifts": gift_impact.get("exemption_used", 0),
            "exemption_used": gift_impact.get("exemption_used", 0),
        },
    }


def calculate_beneficiary(strategy_type: str, params: dict[str, Any]) -> dict[str, Any]:
    """Calculate inherited IRA and beneficiary strategies."""
    initial_balance = float(params.get("ira_balance", 500_000))
    tax_rate = float(params.get("beneficiary_tax_rate", 0.24))
    growth = float(params.get("growth_rate", 0.06))
    ben_age = int(params.get("beneficiary_age", 45))

    if strategy_type == "ten_year_rule":
        res = calculate_inherited_ira_10_year_rule(
            initial_balance=initial_balance,
            beneficiary_age=ben_age,
            beneficiary_tax_rate=tax_rate,
            annual_growth_rate=growth,
            account_type=str(params.get("account_type", "Traditional IRA")),
            owner_died_after_rbd=bool(params.get("owner_died_after_rbd", False)),
        )
        return {
            "total_tax_paid": res.total_taxes_paid,
            "total_distributed": res.total_distributions,
            "net_to_beneficiary": res.net_to_beneficiary,
            "effective_tax_rate": res.effective_tax_rate,
            "schedule": res.annual_distributions,
        }

    elif strategy_type == "stretch_ira":
        res = calculate_stretch_ira(
            initial_balance=initial_balance,
            beneficiary_age=ben_age,
            beneficiary_tax_rate=tax_rate,
            annual_growth_rate=growth,
            account_type=str(params.get("account_type", "Traditional IRA")),
        )
        return {
            "total_distributions": res.total_distributions,
            "total_tax": res.total_taxes,
            "net_to_beneficiary": res.net_inherited,
            "schedule": res.annual_rmds,
        }

    elif strategy_type == "spousal_options":
        spouse_age = int(params.get("spouse_age", 60))
        res = compare_spousal_options(
            initial_balance=initial_balance,
            spouse_age=spouse_age,
            annual_growth_rate=growth,
            spouse_tax_rate=tax_rate,
            account_type=str(params.get("account_type", "Traditional IRA")),
        )
        return {
            "rollover_option": {
                "total_distributions": res.rollover_option.total_distributions,
                "total_taxes_paid": res.rollover_option.total_taxes_paid,
                "net_to_beneficiary": res.rollover_option.net_to_beneficiary,
            },
            "inherited_option": {
                "total_distributions": res.inherited_option.total_distributions,
                "total_taxes_paid": res.inherited_option.total_taxes_paid,
                "net_to_beneficiary": res.inherited_option.net_to_beneficiary,
            },
            "recommended_option": res.recommended_option,
            "savings_amount": res.savings_amount,
            "key_factors": res.key_factors,
        }

    elif strategy_type == "trust_beneficiary":
        trust_type = str(params.get("trust_type", "conduit"))
        res = calculate_trust_beneficiary(
            initial_balance=initial_balance,
            trust_type=trust_type,
            oldest_beneficiary_age=ben_age,
            beneficiary_tax_rate=tax_rate,
            annual_growth_rate=growth,
        )
        return {
            "trust_type": res.trust_type,
            "total_trust_taxes": res.total_trust_taxes,
            "total_beneficiary_taxes": res.total_beneficiary_taxes,
            "total_tax_paid": res.total_taxes_paid,
            "net_to_beneficiary": res.net_to_beneficiaries,
            "trust_administration_costs": res.trust_administration_costs,
        }

    elif strategy_type == "compare_all":
        res = compare_beneficiary_strategies(
            initial_balance=initial_balance,
            beneficiary_tax_rate=tax_rate,
            annual_growth_rate=growth,
        )
        return res

    raise ValueError(f"Unknown beneficiary strategy type: {strategy_type}")


def calculate_charitable(tool_type: str, params: dict[str, Any]) -> dict[str, Any]:
    """Calculate charitable trusts (CRT, CLT), DAF vs Foundation, and QCDs."""
    asset_val = float(params.get("asset_value", 1_000_000))
    payout_rate = float(params.get("payout_rate", 0.06))
    term = int(params.get("term_years", 20))
    donor_age = int(params.get("donor_age", 65))
    donor_tax_rate = float(params.get("donor_tax_rate", 0.24))
    growth = float(params.get("growth_rate", 0.07))
    discount = float(params.get("discount_rate", 0.04))

    if tool_type == "crut":
        res = calculate_crt_crut(
            initial_funding=asset_val,
            payout_rate=payout_rate,
            term_years=term,
            donor_age=donor_age,
            donor_tax_rate=donor_tax_rate,
            growth_rate=growth,
        )
        return {
            "charitable_deduction": res.initial_tax_deduction,
            "total_income_to_donor": res.total_income_received,
            "remainder_to_charity": res.charitable_remainder,
            "effective_tax_savings": res.effective_tax_savings,
            "annual_payouts": res.annual_payouts,
        }

    elif tool_type == "crat":
        res = calculate_crt_crat(
            initial_funding=asset_val,
            payout_rate=payout_rate,
            term_years=term,
            donor_age=donor_age,
            donor_tax_rate=donor_tax_rate,
            growth_rate=growth,
            discount_rate=discount,
        )
        return {
            "charitable_deduction": res.initial_tax_deduction,
            "total_income_to_donor": res.total_income_received,
            "remainder_to_charity": res.charitable_remainder,
            "effective_tax_savings": res.effective_tax_savings,
            "annual_payouts": res.annual_payouts,
        }

    elif tool_type == "foundation_vs_daf":
        grant_rate = float(params.get("annual_grant_rate", 0.05))
        res_comp = compare_foundation_vs_daf(
            contribution_amount=asset_val,
            years=term,
            annual_grant_rate=grant_rate,
            growth_rate=growth,
        )
        return {
            "strategies": res_comp.strategies,
            "recommended_strategy": res_comp.recommended_strategy,
            "key_factors": res_comp.key_factors,
            "tax_efficiency_ranking": res_comp.tax_efficiency_ranking,
        }

    elif tool_type == "qcd":
        return calculate_qcd_benefit(
            ira_balance=float(params.get("ira_balance", 500_000)),
            donor_age=int(params.get("donor_age", 72)),
            qcd_amount=float(params.get("qcd_amount", 25_000)),
            marginal_tax_rate=float(params.get("marginal_rate", params.get("donor_tax_rate", 0.24))),
        )

    raise ValueError(f"Unknown charitable tool type: {tool_type}")
