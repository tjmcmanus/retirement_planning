"""Unit tests for estate planning service."""
from __future__ import annotations

import json
from pathlib import Path
import pytest

from app.services import estate


def test_estate_metadata():
    meta = estate.get_estate_metadata()
    assert "person1_name" in meta
    assert "account_names" in meta
    assert "property_names" in meta
    assert "state_estate_tax_states" in meta
    assert "MA" in meta["state_estate_tax_states"]
    assert "PA" in meta["state_inheritance_tax_states"]


def test_compute_recommendations():
    assess = {
        "has_will": False,
        "has_trust": False,
        "has_real_estate": True,
        "has_poa": False,
        "has_healthcare_directive": False,
        "beneficiaries_current": False,
        "minor_children": True,
    }
    recs = estate.compute_recommendations(assess, {"children": []})
    assert len(recs) >= 4
    titles = [r["title"] for r in recs]
    assert "Create a Will" in titles
    assert "Consider a Revocable Living Trust" in titles
    assert "Create a Durable Power of Attorney" in titles
    assert "Name a Guardian in Your Will" in titles


def test_compute_progress_summary():
    data = {
        "legal": {
            "core_docs": {"will": {"done": True}, "trust": {"done": False}},
            "incapacity_docs": {"poa": {"done": True}},
        },
        "financial": {
            "beneficiaries": {"acc1": {"reviewed": True}, "acc2": {"reviewed": False}},
            "trust_accounts": {},
            "housekeeping": {},
        },
        "property": {
            "real_estate_trust": {},
            "personal_items": {"car": {"done": True}},
            "family_items": {},
        },
        "document_locations": {},
    }
    summary = estate.compute_progress_summary(data, {})
    assert summary["total_items"] > 0
    assert summary["total_done"] >= 3
    assert 0 <= summary["overall_percent"] <= 100


def test_calculate_estate_tax():
    payload = {
        "year": 2026,
        "estate_value": 15_000_000,
        "prior_taxable_gifts": 0,
        "state": "MA",
        "gift_recipients": 2,
        "gift_years": 10,
        "estate_growth_rate": 0.05,
    }
    res = estate.calculate_estate_tax(payload)
    assert "comprehensive" in res
    assert res["comprehensive"]["federal_tax"] > 0
    assert res["comprehensive"]["net_to_heirs"] > 0
    assert "tcja_comparison" in res
    assert res["tcja_comparison"]["additional_tax_due_to_sunset"] > 0
    assert "gifting_impact" in res
    assert res["gifting_impact"]["total_gifted"] > 0


def test_calculate_beneficiary():
    # 10-year rule
    ten_yr = estate.calculate_beneficiary("ten_year_rule", {
        "ira_balance": 500_000,
        "beneficiary_age": 45,
        "beneficiary_tax_rate": 0.24,
        "growth_rate": 0.06,
        "strategy": "equal_annual",
    })
    assert "total_tax_paid" in ten_yr
    assert "schedule" in ten_yr
    assert len(ten_yr["schedule"]) == 10

    # Spousal options
    spousal = estate.calculate_beneficiary("spousal_options", {
        "ira_balance": 500_000,
        "spouse_age": 60,
    })
    assert "rollover_option" in spousal
    assert "inherited_option" in spousal

    # Trust beneficiary
    trust_ben = estate.calculate_beneficiary("trust_beneficiary", {
        "ira_balance": 500_000,
        "trust_type": "conduit",
        "beneficiary_age": 45,
    })
    assert trust_ben["trust_type"] == "conduit"
    assert "net_to_beneficiary" in trust_ben


def test_calculate_charitable():
    # CRUT
    crut = estate.calculate_charitable("crut", {
        "asset_value": 1_000_000,
        "payout_rate": 0.06,
        "term_years": 20,
        "donor_age": 65,
    })
    assert crut["charitable_deduction"] > 0
    assert crut["total_income_to_donor"] > 0

    # Foundation vs DAF
    fnd = estate.calculate_charitable("foundation_vs_daf", {
        "asset_value": 1_000_000,
        "term_years": 20,
        "annual_grant_rate": 0.05,
    })
    assert "strategies" in fnd
    assert "Private Foundation" in fnd["strategies"]
    assert "Donor Advised Fund" in fnd["strategies"]

    # QCD
    qcd = estate.calculate_charitable("qcd", {
        "qcd_amount": 25_000,
        "taxable_dist": 50_000,
        "marginal_rate": 0.24,
    })
    assert qcd["tax_savings"] > 0
