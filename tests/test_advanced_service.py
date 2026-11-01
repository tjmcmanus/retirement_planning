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
TABLES = ("income_rates", "cap_gains", "standard", "irmaa", "atm", "ira_limits", "qbi_limits", "ssincome")
BAL = {"cash": 100_000.0, "traditional": 500_000.0, "roth": 200_000.0, "taxable": 300_000.0}

PLANNER = dict(wages=100_000, trad_dist=0, interest=0, ltcg=0, stcg=0, year=2026, maxdaf="N",
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


def _medicare(births, ages=(65, 65), single=False):
    """Register people (birth dates) and Medicare start ages in the config the planner reads."""
    import config
    cfg = config.get_config_manager()
    cfg.set("personal_info", "is_single_person", single)
    cfg.set("personal_info", "person1_birth_date", births[0])
    cfg.set("personal_info", "person2_birth_date", births[-1])
    cfg.set("healthcare", "person1_medicare_start_age", ages[0])
    cfg.set("healthcare", "person2_medicare_start_age", ages[-1])


def _planner(adv, **kw):
    out = adv.tax_planner(**{**PLANNER, **kw}, balances=BAL)
    cols = {c["title"]: {m["label"]: m for m in c["metrics"]} for c in out["columns"]}
    return out, cols


# ── Tax Planner ────────────────────────────────────────────────────────────

def test_planner_explicit_conversion_matches_hand_calculation(adv):
    out, c = _planner(adv, roth_amount=10_000)
    assert out["warnings"] == []
    assert c["Ordinary Income"]["AGI"]["value"] == 110_000         # 100k wages + 10k conversion
    assert c["Ordinary Income"]["MAGI"]["value"] == 110_000
    assert c["Ordinary Income"]["Taxable Ordinary Income"]["value"] == 75_800   # less the 34.2k standard deduction
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
    assert c["Ordinary Income"]["Taxable Ordinary Income"]["value"] == 403_550   # top of the 24% bracket
    assert c["Ordinary Income"]["AGI"]["value"] == 437_750          # + 34.2k standard deduction
    assert c["Taxes Owed"]["Marginal Bracket"]["value"] == 24
    assert c["Roth"]["Conversion"]["value"] == 337_750              # 403,550 - (100,000 - 34,200)


def test_planner_all_income_types_prepaid_and_balances(adv):
    out, c = _planner(adv, roth_amount=10_000, prepaid=1_000, interest=500, ltcg=5_000, stcg=1_000, trad_dist=2_000)
    assert c["Ordinary Income"]["Taxable Ordinary Income"]["value"] == 79_300
    assert c["Ordinary Income"]["AGI"]["value"] == 118_500          # incl. 5k long-term gains
    assert [m for m in c["Ordinary Income"]] == ["AGI", "MAGI", "Taxable Ordinary Income", "Interest", "ST Cap Gains", "LT Cap Gains"]
    assert c["Ordinary Income"]["LT Cap Gains"]["group"] == "Special Income"
    assert all(m["group"] is None for k, m in c["Ordinary Income"].items() if k != "LT Cap Gains")
    assert c["Taxes Owed"]["Income Tax"]["value"] == 8_020          # 9,020 tax + 0 cap gains (0% bracket) - 1,000 prepaid
    assert c["Taxes Owed"]["State Tax"]["value"] == pytest.approx(3_195)   # 3% of 106,500
    assert c["Cash & Broker"]["New Cash"]["value"] == pytest.approx(88_785)
    assert c["Cash & Broker"]["New Broker"]["value"] == 302_000     # +2,000 distribution
    assert c["Traditional"]["New Trad Balance"]["value"] == 488_000  # -2,000 distribution -10,000 conversion


def test_planner_capital_gains_tax_prepaid_and_cash(adv):
    out, c = _planner(adv, roth_amount=300_000, ltcg=50_000, prepaid=2_000)
    assert c["Ordinary Income"]["Taxable Ordinary Income"]["value"] == 365_800   # 100k + 300k - 34.2k
    assert c["Ordinary Income"]["AGI"]["value"] == 450_000                  # + 50k long-term gains
    # 2,480 + 12% * 76,000 + 22% * 110,600 + 24% * 154,400 = 72,988
    assert c["Taxes Owed"]["LT Cap Gains Tax"]["value"] == 7_500            # 15% of 50,000 (AGI above 98,900)
    assert c["Taxes Owed"]["Income Tax"]["value"] == 78_488                 # 72,988 + 7,500 - 2,000 prepaid
    assert c["Taxes Owed"]["Net Investment Income Tax"]["value"] == 1_900  # 3.8% of the 50k gain: AGI 450,000 is over 250,000
    assert c["Taxes Owed"]["Quarterly Fed"]["value"] == 20_097              # (78,488 + 1,900) / 4
    assert c["Taxes Owed"]["State Tax"]["value"] == 4_500                   # 3% of 150,000
    assert c["Cash & Broker"]["New Cash"]["value"] == 15_112                # 100k - 4,500 - 7,500 - 1,900 - 72,988 + 2,000


def test_planner_short_term_gains_listed_only_when_positive(adv):
    _, c = _planner(adv, roth_amount=10_000, stcg=1)
    assert "ST Cap Gains" in c["Ordinary Income"]
    _, c = _planner(adv, roth_amount=10_000, stcg=0)
    assert "ST Cap Gains" not in c["Ordinary Income"]


def test_planner_max_daf_cash_uses_sixty_percent_of_income(adv):
    out, c = _planner(adv, roth_amount=10_000, maxdaf="Y", daf_type="cash", wages=200_000)
    assert c["Taxes Owed"]["DAF"]["value"] == 126_000                       # 60% of 210,000
    assert c["Ordinary Income"]["Taxable Ordinary Income"]["value"] == 84_000   # itemising: the DAF replaces the standard deduction
    assert c["Ordinary Income"]["AGI"]["value"] == 210_000
    assert c["Taxes Owed"]["Income Tax"]["value"] == 9_584                  # 2,480 + 12% * 59,200
    assert c["Cash & Broker"]["New Broker"]["value"] == 174_000             # 300k - 126k


def test_planner_securities_daf_uses_thirty_percent(adv):
    _, c = _planner(adv, roth_amount=10_000, maxdaf="Y", daf_type="securities", wages=200_000)
    assert c["Taxes Owed"]["DAF"]["value"] == 63_000                        # 30% of 210,000


def test_planner_irmaa_surcharge_only_when_someone_is_on_medicare_in_tax_year_plus_two(adv):
    _medicare(("1990-01-01", "1990-01-01"))                       # nobody on Medicare in 2028
    _, none = _planner(adv, roth_amount=10_000, wages=250_000)
    _medicare(("1960-01-01", "1990-01-01"))                       # one person is
    _, one = _planner(adv, roth_amount=10_000, wages=250_000)
    _medicare(("1960-01-01", "1960-01-01"))                       # both are
    _, two = _planner(adv, roth_amount=10_000, wages=250_000)
    assert not [k for k in none["Taxes Owed"] if "IRMAA" in k]
    assert one["Taxes Owed"]["IRMAA Surcharge in 2028"]["value"] > 0
    assert two["Taxes Owed"]["IRMAA Surcharge in 2028"]["value"] == pytest.approx(2 * one["Taxes Owed"]["IRMAA Surcharge in 2028"]["value"])
    assert "IRMAA w/ Conversion in 2028" in two["Taxes Owed"]


def test_planner_irmaa_surcharge_is_priced_in_the_tax_year_plus_two_table(adv):
    _medicare(("1960-01-01", "1960-01-01"))
    # MAGI 222,000: over the 2026 tier-1 limit (218,000) but under the 2028 one (223,000), the table that applies.
    _, c = _planner(adv, roth_amount=1, wages=221_999)
    assert c["Ordinary Income"]["MAGI"]["value"] == 222_000
    assert not [k for k in c["Taxes Owed"] if k.startswith("IRMAA Surcharge")]      # lowest tier: no surcharge
    _, c = _planner(adv, roth_amount=1, wages=223_001)
    # tier 2 of 2028: Part B 309.48 - 206.50 base, plus Part D 14.70, per person per month, two people
    assert c["Taxes Owed"]["IRMAA Surcharge in 2028"]["value"] == pytest.approx((309.48 - 206.50 + 14.70) * 12 * 2)


def test_planner_no_conversion_when_over_target_bracket_hides_conversion_medicare(adv):
    _medicare(("1960-01-01", "1960-01-01"))
    out, c = _planner(adv, wages=250_000, headroom_pct=22)     # already in the 24% bracket: nothing to convert
    assert out["warnings"] and "Conversion" not in c["Roth"]
    assert "IRMAA Surcharge in 2028" in c["Taxes Owed"] and "IRMAA w/ Conversion in 2028" not in c["Taxes Owed"]


def test_planner_warns_when_current_rate_exceeds_target(adv):
    out, _ = _planner(adv, wages=300_000, headroom_pct=12, roth_amount=0)
    assert out["warnings"] == ["Current tax rate exceeds target conversion rate"]


def test_planner_unknown_year_is_a_value_error(adv):
    with pytest.raises(ValueError):
        adv.tax_planner(**{**PLANNER, "year": 1999}, balances=BAL)


def test_planner_result_is_json_serialisable(adv):
    json.dumps(adv.tax_planner(**PLANNER, balances=BAL), allow_nan=False)


def test_planner_irmaa_limit_fills_conversion_to_tier_limit(adv):
    _medicare(("1960-01-01", "1960-01-01"))
    out, c = _planner(adv, irmaa_limit=223_000)                             # tier 1 limit of the 2028 table (2026 + 2)
    assert out["warnings"] == []
    assert c["Roth"]["Conversion"]["value"] == 123_000                       # 223,000 - 100,000 wages
    assert c["Ordinary Income"]["Taxable Ordinary Income"]["value"] == 188_800   # 223,000 - 34,200
    assert c["Ordinary Income"]["MAGI"]["value"] == 223_000
    assert "IRMAA Surcharge in 2028" not in c["Taxes Owed"]                  # exactly at the tier-1 limit: no surcharge


def test_planner_magi_drives_medicare_surcharge_not_taxable_income(adv):
    # Taxable income 215,800 is under the 218,000 tier-1 limit, but MAGI 250,000 is not.
    _medicare(("1960-01-01", "1960-01-01"))
    _, c = _planner(adv, roth_amount=10_000, wages=240_000)
    assert c["Ordinary Income"]["MAGI"]["value"] == 250_000
    assert c["Taxes Owed"]["IRMAA Surcharge in 2028"]["value"] == pytest.approx((309.48 - 206.50 + 14.70) * 12 * 2)   # tier 2       # tier 2 Part B: 309.48 * 12 * 2


def _write_ss(monthly_by_person, year=2026):
    rows = ["year,age,person,monthly_benefit"] + [f"{year},70,{n},{m}" for n, m in monthly_by_person.items()]
    Path("ssincome.csv").write_text("\n".join(rows) + "\n")


def test_planner_derives_taxable_and_non_taxable_social_security(adv):
    _write_ss({"Alex": 3_000, "Jamie": 2_000})                                # 60,000 / year
    out, c = _planner(adv, wages=40_000, roth_amount=10_000)
    oi = c["Ordinary Income"]
    # combined income 50,000 + 30,000 = 80,000 (MFJ): 85% * (80,000 - 44,000) + 6,000 = 36,600
    assert oi["Social Security Benefits"]["value"] == 60_000
    assert oi["Taxable Social Security"]["value"] == pytest.approx(36_600)
    assert oi["Non-Taxable Social Security"]["value"] == pytest.approx(23_400)
    assert oi["AGI"]["value"] == pytest.approx(86_600)                       # 40,000 + 10,000 + 36,600
    assert oi["MAGI"]["value"] == pytest.approx(86_600)                      # non-taxable SS is not added back
    assert oi["Taxable Social Security"]["group"] == "Social Security"
    assert oi["Taxable Ordinary Income"]["value"] == pytest.approx(52_400)   # less the 34,200 standard deduction


def test_planner_tax_exempt_dividends_increases_taxable_social_security(adv):
    _write_ss({"Alex": 3_000, "Jamie": 2_000})
    _, base = _planner(adv, wages=0, roth_amount=1)
    _, muni = _planner(adv, wages=0, roth_amount=1, tax_exempt_dividends=20_000)
    assert muni["Ordinary Income"]["Taxable Social Security"]["value"] > base["Ordinary Income"]["Taxable Social Security"]["value"]
    assert muni["Ordinary Income"]["AGI"]["value"] > base["Ordinary Income"]["AGI"]["value"]


def test_planner_auto_conversion_with_social_security_still_fills_bracket(adv):
    from strategy import calculate_ss_taxable_amount
    _write_ss({"Alex": 3_000, "Jamie": 2_000})
    _, c = _planner(adv, wages=40_000)                                       # roth_amount 0 -> fill the 24% bracket
    conv = c["Roth"]["Conversion"]["value"]
    taxable_ss = c["Ordinary Income"]["Taxable Social Security"]["value"]
    assert taxable_ss == pytest.approx(calculate_ss_taxable_amount(60_000, 40_000 + conv, "married_filing_jointly"), abs=0.05)
    assert c["Ordinary Income"]["Taxable Ordinary Income"]["value"] == pytest.approx(403_550, abs=1)
    assert c["Ordinary Income"]["AGI"]["value"] == pytest.approx(40_000 + conv + taxable_ss)


def test_planner_without_social_security_has_no_social_security_cards(adv):
    _, c = _planner(adv, roth_amount=10_000)
    assert not [k for k in c["Ordinary Income"] if "Social Security" in k]


def test_planner_ordinary_dividends_are_taxed_like_interest(adv):
    _, via_interest = _planner(adv, roth_amount=10_000, interest=5_000)
    _, via_div = _planner(adv, roth_amount=10_000, ordinary_dividends=5_000)
    oi = via_div["Ordinary Income"]
    assert oi["AGI"]["value"] == via_interest["Ordinary Income"]["AGI"]["value"] == 115_000
    assert oi["Taxable Ordinary Income"]["value"] == via_interest["Ordinary Income"]["Taxable Ordinary Income"]["value"]
    assert oi["Ordinary Dividends"]["value"] == 5_000 and oi["Ordinary Dividends"]["group"] is None
    assert via_div["Taxes Owed"]["Income Tax"] == via_interest["Taxes Owed"]["Income Tax"]
    assert "LT Cap Gains Tax" not in via_div["Taxes Owed"]


def test_planner_qualified_dividends_are_taxed_like_long_term_gains(adv):
    _, via_ltcg = _planner(adv, roth_amount=300_000, ltcg=50_000)
    _, via_qd = _planner(adv, roth_amount=300_000, qualified_dividends=50_000)
    oi = via_qd["Ordinary Income"]
    assert oi["AGI"]["value"] == via_ltcg["Ordinary Income"]["AGI"]["value"] == 450_000
    assert oi["Taxable Ordinary Income"]["value"] == via_ltcg["Ordinary Income"]["Taxable Ordinary Income"]["value"]
    assert via_qd["Taxes Owed"]["LT Cap Gains Tax"]["value"] == via_ltcg["Taxes Owed"]["LT Cap Gains Tax"]["value"] == 7_500
    assert oi["Qualified Dividends"]["group"] == "Special Income"


def test_planner_qualified_and_long_term_gains_stack_together(adv):
    _, both = _planner(adv, roth_amount=300_000, ltcg=20_000, qualified_dividends=30_000)
    _, one = _planner(adv, roth_amount=300_000, ltcg=50_000)
    assert both["Taxes Owed"]["LT Cap Gains Tax"] == one["Taxes Owed"]["LT Cap Gains Tax"]


def test_planner_dividend_types_in_agi_and_magi(adv):
    _, c = _planner(adv, roth_amount=10_000, ordinary_dividends=1_000, qualified_dividends=2_000, tax_exempt_dividends=3_000)
    oi = c["Ordinary Income"]
    assert oi["AGI"]["value"] == 113_000                    # 100k + 10k + 1k + 2k; the muni dividends stay out
    assert oi["MAGI"]["value"] == 116_000                   # ...and come back for MAGI
    assert oi["Taxable Ordinary Income"]["value"] == 76_800  # 110k + 1k ordinary - 34.2k standard deduction


def test_planner_niit_is_3_8_percent_of_the_lesser_of_nii_and_agi_over_threshold(adv):
    # MFJ threshold 250,000.
    _, c = _planner(adv, wages=200_000, roth_amount=70_000, interest=10_000, ltcg=20_000)
    assert c["Ordinary Income"]["AGI"]["value"] == 300_000
    # NII = 10k interest + 20k LTCG = 30k; AGI over the threshold = 50k -> the lesser, 30k, is taxed
    assert c["Taxes Owed"]["Net Investment Income Tax"]["value"] == pytest.approx(30_000 * 0.038)
    _, c = _planner(adv, wages=200_000, roth_amount=30_000, interest=10_000, ltcg=20_000)
    assert c["Ordinary Income"]["AGI"]["value"] == 260_000
    assert c["Taxes Owed"]["Net Investment Income Tax"]["value"] == pytest.approx(10_000 * 0.038)   # only 10k over


def test_planner_no_niit_below_threshold_or_without_investment_income(adv):
    _, below = _planner(adv, wages=100_000, roth_amount=10_000, interest=5_000)
    _, no_nii = _planner(adv, wages=400_000, roth_amount=10_000)
    assert "Net Investment Income Tax" not in below["Taxes Owed"]
    assert "Net Investment Income Tax" not in no_nii["Taxes Owed"]          # wages and the conversion are not NII


def test_planner_niit_covers_every_taxable_investment_income_type(adv):
    _, c = _planner(adv, wages=300_000, roth_amount=1, interest=1_000, ordinary_dividends=2_000,
                    qualified_dividends=3_000, ltcg=4_000, stcg=5_000, tax_exempt_dividends=50_000)
    assert c["Taxes Owed"]["Net Investment Income Tax"]["value"] == pytest.approx(15_000 * 0.038)   # muni excluded


def test_planner_niit_uses_agi_not_irmaa_magi(adv):
    # AGI 245,000 is under the 250,000 threshold; muni dividends lift MAGI to 275,000 but NIIT ignores them.
    _, c = _planner(adv, wages=225_000, roth_amount=1, interest=19_999, tax_exempt_dividends=30_000)
    assert c["Ordinary Income"]["AGI"]["value"] == 245_000 and c["Ordinary Income"]["MAGI"]["value"] == 275_000
    assert "Net Investment Income Tax" not in c["Taxes Owed"]


def test_planner_conversion_tax_includes_the_niit_it_triggers(adv):
    # Without the conversion AGI is 230,000 (under 250,000): no NIIT. Converting 70,000 takes AGI to 300,000.
    _, c = _planner(adv, wages=200_000, roth_amount=70_000, interest=10_000, ltcg=20_000)
    _, plain = _planner(adv, wages=200_000, roth_amount=70_000)                  # same conversion, no investment income
    niit = c["Taxes Owed"]["Net Investment Income Tax"]["value"]
    assert niit == pytest.approx(1_140)
    # the investment income also moves the bracket stacking, so compare against the bracket-only tax on the conversion
    assert c["Roth"]["Conversion Tax"]["value"] >= plain["Roth"]["Conversion Tax"]["value"] + niit - 1e-6


def test_planner_niit_flows_into_cash_and_conversion_tax(adv):
    _, base = _planner(adv, wages=200_000, roth_amount=1, interest=10_000, ltcg=20_000)
    _, big = _planner(adv, wages=200_000, roth_amount=70_000, interest=10_000, ltcg=20_000)
    niit = big["Taxes Owed"]["Net Investment Income Tax"]["value"]
    assert niit == pytest.approx(1_140)
    # the conversion lifted AGI over the threshold, so part of the NIIT is a cost of converting
    no_niit_cash = 100_000 - 0.03 * 230_000 - big["Taxes Owed"]["Income Tax"]["value"]
    assert big["Cash & Broker"]["New Cash"]["value"] == pytest.approx(no_niit_cash - niit)


def test_planner_tax_exempt_dividends_raises_magi_only(adv):
    base_out, base = _planner(adv, roth_amount=10_000)
    _, c = _planner(adv, roth_amount=10_000, tax_exempt_dividends=6_000)
    oi = c["Ordinary Income"]
    assert oi["AGI"]["value"] == base["Ordinary Income"]["AGI"]["value"] == 110_000      # muni interest is not in AGI
    assert oi["MAGI"]["value"] == 116_000
    assert oi["Taxable Ordinary Income"]["value"] == base["Ordinary Income"]["Taxable Ordinary Income"]["value"]
    assert oi["Tax-Exempt Dividends"]["value"] == 6_000 and oi["Tax-Exempt Dividends"]["group"] == "Special Income"
    assert "Tax-Exempt Dividends" not in base["Ordinary Income"]
    assert c["Taxes Owed"]["Income Tax"] == base["Taxes Owed"]["Income Tax"]


def test_planner_tax_exempt_dividends_can_push_magi_over_an_irmaa_tier(adv):
    _medicare(("1960-01-01", "1960-01-01"))
    _, without = _planner(adv, roth_amount=10_000, wages=210_000)
    _, c = _planner(adv, roth_amount=10_000, wages=200_000, tax_exempt_dividends=15_000)
    assert not [k for k in without["Taxes Owed"] if k.startswith("IRMAA Surcharge")]   # MAGI 220,000: under 223,000
    assert c["Ordinary Income"]["MAGI"]["value"] == 225_000                              # muni interest tips it over
    assert c["Taxes Owed"]["IRMAA Surcharge in 2028"]["value"] == pytest.approx((309.48 - 206.50 + 14.70) * 12 * 2)


def test_planner_irmaa_limit_counts_tax_exempt_dividends_in_magi(adv):
    _, c = _planner(adv, irmaa_limit=223_000, tax_exempt_dividends=6_000)
    assert c["Roth"]["Conversion"]["value"] == 117_000                       # 223,000 - 100,000 - 6,000


def test_planner_irmaa_limit_counts_long_term_gains_in_magi(adv):
    _, c = _planner(adv, irmaa_limit=223_000, ltcg=21_000)
    assert c["Roth"]["Conversion"]["value"] == 102_000                       # 223,000 - 100,000 - 21,000


def test_planner_irmaa_limit_already_exceeded_warns_and_converts_nothing(adv):
    out, c = _planner(adv, irmaa_limit=223_000, wages=250_000)
    assert out["warnings"] == ["Current income already exceeds the target IRMAA limit"]
    assert "Conversion" not in c["Roth"]


def test_planner_irmaa_limit_must_be_a_tier_limit(adv):
    with pytest.raises(ValueError):
        adv.tax_planner(**{**PLANNER, "irmaa_limit": 123_456}, balances=BAL)


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
    # Example config: born 1965 / 1966, Medicare at 65 -> the 2028 MAGI is the first to price someone's Medicare.
    assert m["irmaa_limits"]["2026"] == m["irmaa_limits"]["2027"] == []
    assert len(m["irmaa_limits"]["2028"]) == 5 and m["irmaa_limits"]["2028"] == adv._irmaa_limits(2028)


@pytest.mark.parametrize("birth,year,expected", [
    ("1963-06-01", 2026, True),     # 63 in 2026: on Medicare in 2028, which looks back at 2026
    ("1964-06-01", 2026, False),    # 62 in 2026: not yet germane...
    ("1964-06-01", 2027, True),     # ...but it is in 2027
    ("1964-06-01", 2028, True),
])
def test_irmaa_levels_only_listed_for_germane_tax_years(adv, monkeypatch, birth, year, expected):
    import config
    cfg = config.get_config_manager()
    cfg.set("personal_info", "person1_birth_date", birth)
    cfg.set("personal_info", "is_single_person", True)
    monkeypatch.setattr(adv, "_balances", lambda: BAL)
    assert bool(adv.meta()["irmaa_limits"][str(year)]) is expected


def test_irmaa_germane_year_uses_the_oldest_person_and_their_medicare_age(adv, monkeypatch):
    import config
    cfg = config.get_config_manager()
    cfg.set("personal_info", "is_single_person", False)
    cfg.set("personal_info", "person1_birth_date", "1970-01-01")      # young
    cfg.set("personal_info", "person2_birth_date", "1963-01-01")      # oldest: 63 in 2026
    cfg.set("healthcare", "person2_medicare_start_age", 65)
    monkeypatch.setattr(adv, "_balances", lambda: BAL)
    assert adv.meta()["irmaa_limits"]["2026"]
    cfg.set("healthcare", "person2_medicare_start_age", 67)             # later Medicare start pushes it out
    assert adv.meta()["irmaa_limits"]["2026"] == [] and adv.meta()["irmaa_limits"]["2028"]


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
