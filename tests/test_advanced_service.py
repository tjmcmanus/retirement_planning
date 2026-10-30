"""Advanced Strategy Tools service tests (app/services/advanced.py).

No FastAPI needed, so these run on the host as well as in the container image. Each test runs in its own
directory holding copies of the reference tables, because the loaders read CSVs from the working directory.
Tax Planner expectations were worked out by hand from the 2026 MFJ tables:
standard deduction 34,200; brackets 10% to 24,800, 12% to 100,800, 22% to 211,400, 24% to 403,550.
"""
import json
import shutil
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
TABLES = ("income_rates", "cap_gains", "standard", "irmaa", "atm", "ira_limits", "qbi_limits")
BAL = {"cash": 100_000.0, "traditional": 500_000.0, "roth": 200_000.0, "taxable": 300_000.0}

PLANNER = dict(wages=100_000, trad_dist=0, interest=0, ltcg=0, stcg=0, medicare=0, year=2026, maxdaf="N",
               charitable=0, headroom_pct=24, daf_type="securities", roth_amount=0, prepaid=0)


@pytest.fixture
def adv(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    for t in TABLES:
        shutil.copy(REPO / f"{t}.csv", tmp_path / f"{t}.csv")
    shutil.copy(REPO / "retirement_config.json.example", tmp_path / "retirement_config.json")
    import app_cache
    import config
    app_cache.clear_all()
    config.reload_config()
    from app.services import advanced
    yield advanced
    app_cache.clear_all()


def _planner(adv, **kw):
    out = adv.tax_planner(**{**PLANNER, **kw}, balances=BAL)
    cols = {c["title"]: {m["label"]: m for m in c["metrics"]} for c in out["columns"]}
    return out, cols


# ── Tax Planner ────────────────────────────────────────────────────────────

def test_planner_explicit_conversion_matches_hand_calculation(adv):
    out, c = _planner(adv, roth_amount=10_000)
    assert out["warnings"] == []
    assert c["Ordinary Income"]["AGI"]["value"] == 75_800          # 100k + 10k - 34.2k standard deduction
    assert c["Taxes Owed"]["Income Tax"]["value"] == 8_600         # 10% * 24,800 + 12% * 51,000
    assert c["Taxes Owed"]["Quarterly Fed"]["value"] == 2_150
    assert c["Taxes Owed"]["State Tax"]["value"] == 3_000          # flat 3% of wages
    assert c["Taxes Owed"]["Marginal Bracket"]["value"] == 12
    assert c["Roth"]["Conversion Tax"]["value"] == 1_200           # 12% * 10,000
    assert c["Roth"]["New Roth Balance"]["value"] == 210_000
    assert c["Roth"]["New Roth Balance"]["delta"] == 10_000
    assert c["Traditional"]["New Trad Balance"]["value"] == 490_000
    assert c["Cash & Broker"]["New Cash"]["value"] == 88_400       # 100k - 3,000 state - 8,600 federal
    assert "New Broker" not in c["Cash & Broker"] and c["Cash & Broker"]["Broker Balance"]["value"] == 300_000


def test_planner_auto_conversion_fills_to_target_bracket(adv):
    out, c = _planner(adv)                                          # roth_amount 0 -> fill the 24% bracket
    assert c["Ordinary Income"]["AGI"]["value"] == 403_550          # top of the 24% bracket
    assert c["Taxes Owed"]["Marginal Bracket"]["value"] == 24
    assert c["Roth"]["Conversion"]["value"] == 337_750              # 403,550 - (100,000 - 34,200)


def test_planner_all_income_types_prepaid_and_balances(adv):
    out, c = _planner(adv, roth_amount=10_000, prepaid=1_000, interest=500, ltcg=5_000, stcg=1_000, trad_dist=2_000)
    assert c["Ordinary Income"]["AGI"]["value"] == 79_300
    assert [m for m in c["Ordinary Income"]] == ["AGI", "Interest", "ST Cap Gains", "LT Cap Gains"]
    assert c["Taxes Owed"]["Income Tax"]["value"] == 8_020          # 9,020 tax + 0 cap gains (0% bracket) - 1,000 prepaid
    assert c["Taxes Owed"]["State Tax"]["value"] == pytest.approx(3_195)   # 3% of 106,500
    assert c["Cash & Broker"]["New Cash"]["value"] == pytest.approx(88_785)
    assert c["Cash & Broker"]["New Broker"]["value"] == 302_000     # +2,000 distribution
    assert c["Traditional"]["New Trad Balance"]["value"] == 488_000  # -2,000 distribution -10,000 conversion


def test_planner_capital_gains_tax_prepaid_and_cash(adv):
    out, c = _planner(adv, roth_amount=300_000, ltcg=50_000, prepaid=2_000)
    assert c["Ordinary Income"]["AGI"]["value"] == 365_800                  # 100k + 300k - 34.2k
    # 2,480 + 12% * 76,000 + 22% * 110,600 + 24% * 154,400 = 72,988
    assert c["Taxes Owed"]["LT Cap Gains Tax"]["value"] == 7_500            # 15% of 50,000 (AGI above 98,900)
    assert c["Taxes Owed"]["Income Tax"]["value"] == 78_488                 # 72,988 + 7,500 - 2,000 prepaid
    assert c["Taxes Owed"]["Quarterly Fed"]["value"] == 19_622              # 78,488 / 4
    assert c["Taxes Owed"]["State Tax"]["value"] == 4_500                   # 3% of 150,000
    assert c["Cash & Broker"]["New Cash"]["value"] == 17_012                # 100k - 4,500 - 7,500 - 72,988 + 2,000


def test_planner_short_term_gains_listed_only_when_positive(adv):
    _, c = _planner(adv, roth_amount=10_000, stcg=1)
    assert "ST Cap Gains" in c["Ordinary Income"]
    _, c = _planner(adv, roth_amount=10_000, stcg=0)
    assert "ST Cap Gains" not in c["Ordinary Income"]


def test_planner_max_daf_cash_uses_sixty_percent_of_income(adv):
    out, c = _planner(adv, roth_amount=10_000, maxdaf="Y", daf_type="cash", wages=200_000)
    assert c["Taxes Owed"]["DAF"]["value"] == 126_000                       # 60% of 210,000
    assert c["Ordinary Income"]["AGI"]["value"] == 84_000                   # itemising: the DAF replaces the standard deduction
    assert c["Taxes Owed"]["Income Tax"]["value"] == 9_584                  # 2,480 + 12% * 59,200
    assert c["Cash & Broker"]["New Broker"]["value"] == 174_000             # 300k - 126k


def test_planner_securities_daf_uses_thirty_percent(adv):
    _, c = _planner(adv, roth_amount=10_000, maxdaf="Y", daf_type="securities", wages=200_000)
    assert c["Taxes Owed"]["DAF"]["value"] == 63_000                        # 30% of 210,000


def test_planner_medicare_surcharge_only_when_enrolled(adv):
    _, none = _planner(adv, roth_amount=10_000, wages=250_000, medicare=0)
    _, two = _planner(adv, roth_amount=10_000, wages=250_000, medicare=2)
    assert "Medicare Surcharge" not in none["Taxes Owed"]
    assert two["Taxes Owed"]["Medicare Surcharge"]["value"] > 0
    assert "Medicare w/ Conversion" in two["Taxes Owed"]


def test_planner_no_conversion_when_over_target_bracket_hides_conversion_medicare(adv):
    out, c = _planner(adv, wages=250_000, headroom_pct=22, medicare=2)     # already in the 24% bracket: nothing to convert
    assert out["warnings"] and "Conversion" not in c["Roth"]
    assert "Medicare Surcharge" in c["Taxes Owed"] and "Medicare w/ Conversion" not in c["Taxes Owed"]


def test_planner_warns_when_current_rate_exceeds_target(adv):
    out, _ = _planner(adv, wages=300_000, headroom_pct=12, roth_amount=0)
    assert out["warnings"] == ["Current tax rate exceeds target conversion rate"]


def test_planner_unknown_year_is_a_value_error(adv):
    with pytest.raises(ValueError):
        adv.tax_planner(**{**PLANNER, "year": 1999}, balances=BAL)


def test_planner_result_is_json_serialisable(adv):
    json.dumps(adv.tax_planner(**PLANNER, balances=BAL), allow_nan=False)


# ── Calculators: the service must return exactly what the calculators return ───

def test_multi_year_matches_calculator_and_converts_year_keys(adv):
    import advanced_strategies as A
    kw = dict(start_year=2026, filing_status="single", income=100_000, cg_lt=5_000, conversion=10_000, qbi=0, loss_cf=0, window=4)
    out = adv.multi_year(**kw)
    yrs = range(4)
    direct = A.build_rolling_tax_window(
        start_year=2026, income_by_year={2026 + i: 100_000.0 for i in yrs}, cg_lt_by_year={2026 + i: 5_000.0 for i in yrs},
        conversion_by_year={2026 + i: 10_000.0 for i in yrs}, qbi_by_year={2026 + i: 0.0 for i in yrs},
        loss_carryforward=0.0, filing_status="single", window=4)
    assert out["total_tax_5yr"] == direct.total_tax_5yr and out["window"] == 4
    assert [y["federal_tax"] for y in out["years"]] == [y.federal_tax for y in direct.years]
    assert len(out["years"]) == 4
    assert out["recommended_conversions"] == [{"year": y, "amount": a} for y, a in direct.recommended_conversions.items()]
    json.dumps(out, allow_nan=False)


def test_qbi_adds_savings_estimate(adv):
    import advanced_strategies as A
    out = adv.qbi(qbi_income=100_000, total_taxable_income=200_000, filing_status="married_filing_jointly",
                  w2_wages=0, ubia=0, is_sstb=False)
    direct = A.calculate_qbi_deduction_full(qbi_income=100_000.0, total_taxable_income=200_000.0, filing_status="married_filing_jointly")
    assert out["deduction"] == direct["deduction"] == 20_000        # 20% of QBI, below the phase-out
    assert out["estimated_savings"] == pytest.approx(20_000 * 0.24)


def test_backdoor_result_has_the_fields_the_page_reads(adv):
    out = adv.backdoor(year=2026, age=45, magi=250_000, trad_balance=0, basis=0, filing_status="married_filing_jointly")
    assert set(out) >= {"contribution_amount", "pro_rata_tax", "net_benefit", "eligible", "ineligible_reason", "steps", "warnings"}


def test_backdoor_pro_rata_with_pretax_balance(adv):
    clean = adv.backdoor(year=2026, age=45, magi=250_000, trad_balance=0, basis=0, filing_status="married_filing_jointly")
    dirty = adv.backdoor(year=2026, age=45, magi=250_000, trad_balance=500_000, basis=0, filing_status="married_filing_jointly")
    assert clean["pro_rata_tax"] == 0 and dirty["pro_rata_tax"] > 0


def test_betr_percent_inputs_are_fractions_and_future_rate_echoed(adv):
    out = adv.betr(conversion_amount=50_000, trad_balance=500_000, basis=0, current_rate=0.24, future_rate=0.22,
                   annual_return=0.07, years=20, pay_from_taxable=True, taxable_balance=200_000)
    assert out["future_rate"] == 0.22 and out["years"] == 20
    assert out["conversion_tax"] == pytest.approx(12_000)           # 24% of 50,000
    assert out["conversion_recommended"] == (0.22 > out["betr"])   # convert when the future rate beats the break-even rate


def test_mega_backdoor_not_allowed_by_plan(adv):
    out = adv.mega_backdoor(year=2026, age=45, employee_deferral=23_500, employer_match=5_000,
                            plan_allows_after_tax=False, plan_allows_in_plan_conversion=True)
    assert out["eligible"] is False and out["ineligible_reason"]


def test_mega_backdoor_after_tax_room(adv):
    out = adv.mega_backdoor(year=2026, age=45, employee_deferral=23_500, employer_match=5_000,
                            plan_allows_after_tax=True, plan_allows_in_plan_conversion=True)
    assert out["eligible"] and out["after_tax_contribution"] > 0


def test_nua_derives_shares_like_the_page(adv):
    out = adv.nua(cost_basis=50_000, current_value=200_000, ordinary_rate=0.24, ltcg_rate=0.15, years=5)
    assert out["shares"] == pytest.approx(2_000)                    # int(200,000 / 100)
    assert out["nua_amount"] == pytest.approx(150_000)
    assert out["total_cost_basis"] == pytest.approx(50_000)
    assert out["current_value"] == pytest.approx(200_000)


def test_nua_zero_value_does_not_divide_by_zero(adv):
    out = adv.nua(cost_basis=0, current_value=0, ordinary_rate=0.24, ltcg_rate=0.15, years=0)
    assert out["nua_amount"] == 0


def test_qcd_limited_to_rmd_and_goal(adv):
    out = adv.qcd(year=2026, age=73, ira_balance=500_000, rmd=20_000, agi=100_000, charitable=10_000,
                  marginal_rate=0.22, filing_status="married_filing_jointly")
    assert out["qcd_amount"] == 10_000 and out["eligible"]
    assert out["agi_reduction"] == 10_000


def test_sepp_methods_validated(adv):
    with pytest.raises(ValueError, match="Unknown SEPP method"):
        adv.sepp(balance=500_000, age=50, rate=0.05, method="Made Up", marginal_rate=0.22)
    for m in adv.SEPP_METHODS:
        out = adv.sepp(balance=500_000, age=50, rate=0.05, method=m, marginal_rate=0.22)
        assert out["annual_payment"] > 0 and out["monthly_payment"] == pytest.approx(out["annual_payment"] / 12)


def test_harvest_uses_synthetic_position_and_string_free_rows(adv):
    out = adv.harvest(start_year=2026, window=3, filing_status="single", income=100_000, unrealized_losses=50_000)
    assert out["positions"] == 1 and out["years_planned"] == 3 and len(out["rows"]) == 3
    assert out["rows"][0]["harvested"] == 50_000
    assert out["total_tax_savings"] == pytest.approx(sum(r["tax_savings"] for r in out["rows"]))
    assert all(isinstance(r["year"], int) for r in out["rows"])
    json.dumps(out, allow_nan=False)


def test_harvest_without_losses_has_no_positions(adv):
    out = adv.harvest(start_year=2026, window=2, filing_status="single", income=100_000, unrealized_losses=0)
    assert out["positions"] == 0 and out["total_tax_savings"] == 0


# ── Meta ───────────────────────────────────────────────────────────────────

def test_meta_lists_years_from_2023_and_filing_status(adv, monkeypatch):
    monkeypatch.setattr(adv, "_balances", lambda: BAL)
    m = adv.meta()
    assert m["planner_years"][0] == 2023 and m["default_planner_year"] in m["planner_years"]
    assert m["filing_status"] == "married_filing_jointly"
    assert m["sepp_methods"] == list(adv.SEPP_METHODS) and m["balances"] == BAL


def test_balances_fall_back_to_zero_when_net_worth_unavailable(adv, monkeypatch):
    from app.services import networth

    def boom():
        raise RuntimeError("no data")
    monkeypatch.setattr(networth, "load_networth_history", boom)
    assert adv._balances() == {"cash": 0.0, "traditional": 0.0, "roth": 0.0, "taxable": 0.0}


def test_balances_read_the_latest_row(adv, monkeypatch):
    import pandas as pd
    from app.services import networth
    df = pd.DataFrame({"cash": [1.0, 2.0], "taxable": [3.0, 4.0], "tax_deferred": [5.0, 6.0], "tax_free": [7.0, 8.0], "total": [16.0, 20.0]})
    monkeypatch.setattr(networth, "load_networth_history", lambda: df)
    assert adv._balances() == {"cash": 2.0, "traditional": 6.0, "roth": 8.0, "taxable": 4.0}
