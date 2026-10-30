"""API tests for the FastAPI service (app/). Skipped where FastAPI is unusable.

Run inside the container image (which has the pinned FastAPI):
    podman run --rm --entrypoint sh -v "$PWD/tests:/app/tests:ro" localhost/retirement-planning:local \
        -c "pip install -q --user pytest httpx && cd /tmp && python -m pytest -q -p no:cacheprovider -o addopts= /app/tests/test_api.py"
"""
import json
import shutil
import sys
from pathlib import Path

import pytest

try:
    from fastapi.testclient import TestClient
    import app.main as main_module
except Exception as exc:  # old/incompatible FastAPI on the host interpreter
    pytest.skip(f"FastAPI not usable here: {exc}", allow_module_level=True)

REPO = Path(__file__).resolve().parent.parent


@pytest.fixture
def client(tmp_path, monkeypatch):
    """Client whose working directory holds its own config file (like /data in the container)."""
    monkeypatch.chdir(tmp_path)
    shutil.copy(REPO / "retirement_config.json.example", tmp_path / "retirement_config.json")
    import config
    config.reload_config()
    with TestClient(main_module.app, base_url="http://localhost") as c:
        yield c


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200 and r.json() == {"status": "ok"}


def test_index_and_vendor_assets_served(client):
    assert "Financial Dashboard" in client.get("/").text
    for name in ("alpine-3.14.9.min.js", "plotly-2.35.2.min.js", "tabulator-6.3.1.min.js"):
        assert client.get(f"/vendor/{name}").status_code == 200
    assert client.get("/static/dashboard.js").status_code == 200


def test_index_references_only_local_assets(client):
    html = client.get("/").text
    assert "http://" not in html and "https://" not in html and "//cdn" not in html


def test_dashboard_no_longer_embeds_strategy(client):
    html = client.get("/").text
    assert "Withdrawal Strategy" not in html and "table-strategy" not in html
    assert "loadStrategy" not in client.get("/static/dashboard.js").text


def test_strategy_page_served_and_in_shared_nav(client):
    html = client.get("/strategy").text
    assert "table-strategy" in html and 'id="main-nav"' in html
    assert "http://" not in html and "https://" not in html
    assert client.get("/static/strategy.js").status_code == 200
    nav = client.get("/static/nav.js").text
    for label in ("Dashboard", "Portfolio", "Strategy", "Advanced Strategy Tools", "Monte Carlo",
                  "Estate Planning", "Settings", "Tax Data Admin"):
        assert f'label: "{label}"' in nav
    for page in ("/", "/settings"):
        assert 'id="main-nav"' in client.get(page).text


def test_get_config_has_all_default_sections(client):
    import config
    body = client.get("/api/config").json()
    assert set(config.DEFAULT_CONFIG) <= set(body)


def test_put_config_updates_file_and_creates_backup(client, tmp_path):
    before = json.loads((tmp_path / "retirement_config.json").read_text())
    key_before = before["financial_assumptions"].get("expected_rate_of_return")
    r = client.put("/api/config", json={"changes": {"financial_assumptions": {"expected_rate_of_return": 7.25}}})
    assert r.status_code == 200
    assert r.json()["config"]["financial_assumptions"]["expected_rate_of_return"] == 7.25

    saved = json.loads((tmp_path / "retirement_config.json").read_text())
    assert saved["financial_assumptions"]["expected_rate_of_return"] == 7.25
    # untouched keys survive the partial update
    other = next(k for k in before["financial_assumptions"] if k != "expected_rate_of_return")
    assert saved["financial_assumptions"][other] == before["financial_assumptions"][other]
    # the previous version was backed up, with the old value
    backups = list((tmp_path / ".backups").glob("retirement_config_*.json"))
    assert len(backups) == 1
    assert json.loads(backups[0].read_text())["financial_assumptions"].get("expected_rate_of_return") == key_before
    # and a follow-up GET sees the new value
    assert client.get("/api/config").json()["financial_assumptions"]["expected_rate_of_return"] == 7.25


@pytest.mark.parametrize("changes", [{"nope": {"a": 1}}, {"metadata": {"last_updated": "x"}}])
def test_put_config_rejects_unknown_and_readonly_sections(client, changes):
    r = client.put("/api/config", json={"changes": changes})
    assert r.status_code == 422


def test_put_config_rejects_empty_body(client):
    assert client.put("/api/config", json={"changes": {}}).status_code == 422


def test_cross_origin_write_is_rejected(client, tmp_path):
    r = client.put(
        "/api/config",
        json={"changes": {"financial_assumptions": {"expected_rate_of_return": 1}}},
        headers={"Origin": "http://evil.example"},
    )
    assert r.status_code == 403
    saved = json.loads((tmp_path / "retirement_config.json").read_text())
    assert saved["financial_assumptions"].get("expected_rate_of_return") != 1


def test_same_origin_write_is_allowed(client):
    r = client.put(
        "/api/config",
        json={"changes": {"financial_assumptions": {"expected_rate_of_return": 5}}},
        headers={"Origin": "http://localhost"},
    )
    assert r.status_code == 200


def test_unexpected_host_header_is_rejected(client):
    assert client.get("/api/health", headers={"Host": "evil.example"}).status_code == 400


def test_strategy_rejects_inverted_years(client):
    assert client.get("/api/strategy", params={"start_year": 2040, "end_year": 2030}).status_code == 422


# ---------------------------------------------------------------------------
# Settings: schema, validation, deep merge, derived fields, reset, export
# ---------------------------------------------------------------------------

def _put(client, changes):
    return client.put("/api/config", json={"changes": changes})


def test_schema_endpoint_and_integrity(client):
    import config
    from app.services import config_schema
    body = client.get("/api/config/schema").json()
    assert [s["id"] for s in body["sections"]][0] == "personal"
    # Every editable field must be a key the config already knows (defaults) or be explicitly default-less.
    known_missing = {"tax_strategy.use_january_bracket_fill_strategy", "tax_strategy.savings_safety_reserve",
                     "tax_strategy.use_60day_rollover_mechanics"}
    for path in config_schema.FIELDS:
        if path in known_missing:
            continue
        assert config_schema.get_path(config.DEFAULT_CONFIG, path, "__missing__") != "__missing__", path
    # show_if conditions only reference known fields
    for spec in config_schema.FIELDS.values():
        for cond in spec["show_if"]:
            assert cond[0] in config_schema.FIELDS, cond


def test_example_config_values_pass_validation(client):
    from app.services import config_schema
    import config
    cfg = client.get("/api/config").json()
    # The shipped example uses "YYYY-MM-DD" placeholders; replace them with real dates first.
    for k in ("person1_birth_date", "person1_retirement_date", "person2_birth_date", "person2_retirement_date"):
        cfg["personal_info"][k] = "1970-01-01"
    cfg["personal_info"]["children"] = [{"name": "Kid", "birth_date": "2015-05-05", "special_needs": False}]
    editable = {p: config_schema.get_path(cfg, p) for p in config_schema.FIELDS}
    changes = {}
    for path, value in editable.items():
        if value is None and config_schema.FIELDS[path]["type"] != "date":
            continue
        cur = changes
        parts = path.split(".")
        for k in parts[:-1]:
            cur = cur.setdefault(k, {})
        cur[parts[-1]] = value
    errs = config_schema.validate_changes(changes, cfg, config.DEFAULT_CONFIG)
    assert errs == [], errs


def test_validation_returns_per_field_errors_and_saves_nothing(client, tmp_path):
    before = (tmp_path / "retirement_config.json").read_text()
    r = _put(client, {"expenses": {"living_expenses": {"property_tax": -5}},
                      "financial_assumptions": {"expected_rate_of_return": "high"},
                      "personal_info": {"person1_birth_date": "1970-02-30"}})
    assert r.status_code == 422
    errors = {e["path"]: e["message"] for e in r.json()["detail"]["errors"]}
    assert set(errors) == {"expenses.living_expenses.property_tax", "financial_assumptions.expected_rate_of_return",
                           "personal_info.person1_birth_date"}
    assert (tmp_path / "retirement_config.json").read_text() == before
    assert not (tmp_path / ".backups").exists()


@pytest.mark.parametrize("changes", [
    {"bucket_strategy": {"bucket_2_years": 7.5}},                      # must be whole
    {"social_security": {"person1_ssi_age": 75}},                       # out of range
    {"healthcare": {"person1_retirement_coverage_type": "Gold"}},      # not an option
    {"personal_info": {"retirement_state": "ZZ"}},
    {"personal_info": {"children": [{"name": "", "birth_date": "2015-05-05"}]}},
    {"real_estate": {"properties": [{"property_name": "A", "address": "B", "purchase_price": 0}]}},
    {"healthcare": {"person1_conditions": ["not_a_condition"]}},
    {"financial_assumptions": {"no_such_key": 1}},
])
def test_invalid_values_are_rejected(client, changes):
    assert _put(client, changes).status_code == 422


def test_deep_merge_keeps_sibling_nested_keys(client):
    cfg = client.get("/api/config").json()
    siblings = {k: v for k, v in cfg["expenses"]["living_expenses"].items() if k != "property_tax"}
    r = _put(client, {"expenses": {"living_expenses": {"property_tax": 4321}}})
    assert r.status_code == 200
    living = r.json()["config"]["expenses"]["living_expenses"]
    assert living["property_tax"] == 4321
    for k, v in siblings.items():
        assert living[k] == v, k


def test_derives_retirement_age_year_and_expense_total(client):
    r = _put(client, {"personal_info": {"person1_birth_date": "1965-06-15", "person1_retirement_date": "2028-03-01"},
                      "expenses": {"living_expenses": {"property_tax": 1000, "homeowners_insurance": 500,
                                                        "auto_insurance": 0, "food_groceries": 0, "utilities_phone": 0,
                                                        "utilities_internet": 0, "utilities_cable": 0, "utilities_electric": 0,
                                                        "utilities_gas": 0, "utilities_water": 0, "gifts_donations": 0,
                                                        "other_living": 0},
                                   "entertainment_expenses": {"travel_vacations": 2000, "dining_out": 0, "clothing": 0,
                                                              "hobbies": 0, "entertainment_other": 0}}})
    assert r.status_code == 200
    body = r.json()
    pi = body["config"]["personal_info"]
    assert (pi["person1_retirement_age"], pi["person1_retirement_year"]) == (63, 2028)
    assert body["config"]["financial_assumptions"]["expected_annual_expenses"] == 3500
    assert body["derived"]["financial_assumptions.expected_annual_expenses"] == 3500


def test_empty_expense_breakdown_keeps_saved_total(client):
    zero_living = {k: 0 for k in __import__("app.services.config_schema", fromlist=["x"]).LIVING_KEYS}
    zero_ent = {k: 0 for k in __import__("app.services.config_schema", fromlist=["x"]).ENTERTAINMENT_KEYS}
    saved = client.get("/api/config").json()["financial_assumptions"]["expected_annual_expenses"]
    r = _put(client, {"expenses": {"living_expenses": zero_living, "entertainment_expenses": zero_ent}})
    assert r.status_code == 200
    assert r.json()["config"]["financial_assumptions"]["expected_annual_expenses"] == saved
    assert "financial_assumptions.expected_annual_expenses" not in r.json()["derived"]


def test_surviving_spouse_requires_details(client):
    r = _put(client, {"personal_info": {"surviving_spouse_mode": True}})
    assert r.status_code == 422
    paths = {e["path"] for e in r.json()["detail"]["errors"]}
    assert paths == {"personal_info.decedent_person", "personal_info.date_of_death"}
    ok = _put(client, {"personal_info": {"surviving_spouse_mode": True, "decedent_person": "person2",
                                         "date_of_death": "2040-01-01"}})
    assert ok.status_code == 200


def test_table_values_round_trip(client):
    kids = [{"name": "Sam", "birth_date": "2012-04-01", "special_needs": False}]
    props = [{"property_name": "Cabin", "address": "1 Lake Rd", "purchase_price": 250000}]
    r = _put(client, {"personal_info": {"children": kids}, "real_estate": {"properties": props}})
    assert r.status_code == 200
    cfg = client.get("/api/config").json()
    assert cfg["personal_info"]["children"] == kids and cfg["real_estate"]["properties"] == props


def test_ssi_schedule_is_regenerated_on_social_security_change(client, tmp_path):
    # the shipped example has placeholder dates, which the SSI schedule needs to be real
    r = _put(client, {"personal_info": {"person1_birth_date": "1965-01-01", "person2_birth_date": "1966-01-01"},
                      "social_security": {"person1_ssi_amount": 2500, "person1_ssi_age": 67}})
    assert r.status_code == 200 and r.json()["warnings"] == []
    csv = (tmp_path / "ssincome.csv").read_text()
    assert len(csv.splitlines()) > 1


def test_ss_preview_matches_engine(client):
    import ssi_calculator
    r = client.get("/api/social-security/preview", params={"amount": 3000, "age": 70})
    assert r.status_code == 200
    assert r.json()["monthly"] == round(ssi_calculator.calculate_benefit_at_claiming_age(3000, 70), 2)
    assert client.get("/api/social-security/preview", params={"amount": 3000, "age": 40}).status_code == 422


def test_reset_restores_defaults_and_backs_up(client, tmp_path):
    import config
    _put(client, {"financial_assumptions": {"expected_rate_of_return": 9.5}})
    r = client.post("/api/config/reset")
    assert r.status_code == 200
    saved = json.loads((tmp_path / "retirement_config.json").read_text())
    assert saved["financial_assumptions"]["expected_rate_of_return"] == config.DEFAULT_CONFIG["financial_assumptions"]["expected_rate_of_return"]
    assert any(b.read_text().find("9.5") >= 0 for b in (tmp_path / ".backups").glob("retirement_config_*.json"))


def test_export_bundle_contents(client, tmp_path):
    import io, zipfile
    (tmp_path / "portfolio_data_truth.csv").write_text("a,b\n1,2\n")
    r = client.get("/api/config/export")
    assert r.status_code == 200 and r.headers["content-type"] == "application/zip"
    assert "attachment" in r.headers["content-disposition"]
    with zipfile.ZipFile(io.BytesIO(r.content)) as zf:
        assert set(zf.namelist()) == {"retirement_config.json", "portfolio_data_truth.csv"}
        raw = zf.read("retirement_config.json").decode()
    assert raw.startswith("// Primary person:")
    json.loads("\n".join(ln for ln in raw.splitlines() if not ln.startswith("//")))  # still importable


def test_settings_page_served_and_local_only(client):
    html = client.get("/settings").text
    assert "Settings" in html and "http://" not in html and "https://" not in html
    assert client.get("/static/settings.js").status_code == 200


# ---------------------------------------------------------------------------
# Dashboard: forecast, stress, statement, mixes, readiness
# ---------------------------------------------------------------------------

def test_dashboard_page_has_all_streamlit_sections_and_stays_local(client):
    html = client.get("/").text
    for text in ("Market Forecast", "Net Worth Overview", "Financial Plan Readiness Indicator", "chart-gauge",
                 "chart-trend", "'chart-' + k"):
        assert text in html, text
    js = client.get("/static/dashboard.js").text
    for label in ("Long-Term", "Intermediate-Term", "Short-Term", "Market Stress", "Net Worth Statement",
                  "Account Mix", "Portfolio Mix"):
        assert label in js, label
    assert "http://" not in html and "https://" not in html
    assert "http://" not in js and "https://" not in js


def test_treemap_nodes_match_plotly_express(client):
    from app.services import dashboard
    out = dashboard.treemap_nodes([(("A", "x"), 30.0), (("A", "y"), 10.0), (("B", "z"), 60.0)])
    by_id = {n["id"]: n for n in out["nodes"]}
    assert by_id["A"]["value"] == 40 and by_id["A"]["parent"] == "" and by_id["A"]["label"] == "A"
    assert by_id["A/x"]["parent"] == "A" and by_id["A/x"]["color"] == 30
    assert by_id["A"]["color"] == pytest.approx((30 * 30 + 10 * 10) / 40)       # value-weighted mean colour
    assert out["midpoint"] == pytest.approx((900 + 100 + 3600) / 100)           # np.average(v, weights=v)
    assert dashboard.treemap_nodes([])["midpoint"] == 0


@pytest.mark.parametrize("path,attr", [
    ("/api/dashboard/stress", "market_stress"),
    ("/api/dashboard/statement", "net_worth_statement"),
    ("/api/dashboard/account-mix", "account_mix"),
    ("/api/dashboard/portfolio-mix", "portfolio_mix"),
    ("/api/dashboard/readiness", "readiness"),
])
def test_dashboard_routes_return_service_result_and_report_failures(client, monkeypatch, path, attr):
    from app.services import dashboard
    monkeypatch.setattr(dashboard, attr, lambda: {"ready": True, "marker": attr})
    assert client.get(path).json() == {"ready": True, "marker": attr}

    def boom():
        raise RuntimeError("engine down")
    monkeypatch.setattr(dashboard, attr, boom)
    r = client.get(path)
    assert r.status_code == 500 and "engine down" in r.json()["detail"]


def test_dashboard_forecast_route_validates_timeframe(client, monkeypatch):
    from app.services import dashboard
    seen = []
    monkeypatch.setattr(dashboard, "market_forecast", lambda tf: seen.append(tf) or {"timeframe": tf})
    for tf in ("longterm", "intermediate", "shortterm"):
        assert client.get(f"/api/dashboard/forecast/{tf}").json() == {"timeframe": tf}
    assert seen == ["longterm", "intermediate", "shortterm"]
    assert client.get("/api/dashboard/forecast/weekly").status_code == 422



def test_charitable_giving_section_saves_and_validates(client):
    ids = [s["id"] for s in client.get("/api/config/schema").json()["sections"]]
    assert "charitable" in ids
    ok = _put(client, {"charitable_giving": {
        "annual_charitable_giving": 30000, "has_daf": True, "daf_provider": "Schwab Charitable",
        "daf_contribution_start_year": 2026, "daf_contribution_end_year": 2040}})
    assert ok.status_code == 200
    cg = ok.json()["config"]["charitable_giving"]
    assert cg["annual_charitable_giving"] == 30000 and cg["daf_provider"] == "Schwab Charitable"
    assert cg["charitable_giving_end_age"]  # sibling keys survive the merge

    bad = _put(client, {"charitable_giving": {"charitable_giving_start_age": 80, "charitable_giving_end_age": 70,
                                              "daf_contribution_start_year": 2040,
                                              "daf_contribution_end_year": 2030}})
    assert bad.status_code == 422
    paths = {e["path"] for e in bad.json()["detail"]["errors"]}
    assert paths == {"charitable_giving.charitable_giving_end_age", "charitable_giving.daf_contribution_end_year"}
    assert _put(client, {"charitable_giving": {"annual_charitable_giving": -1}}).status_code == 422


def test_trad_prefund_schedule_saves_validates_and_drives_engine(client):
    rows = [{"year": 2027, "amount": 200000}, {"year": 2028, "amount": 50000}]
    ok = _put(client, {"tax_strategy": {"trad_prefund_schedule": rows}})
    assert ok.status_code == 200
    assert ok.json()["config"]["tax_strategy"]["trad_prefund_schedule"] == rows

    dup = _put(client, {"tax_strategy": {"trad_prefund_schedule": [
        {"year": 2027, "amount": 1}, {"year": 2027, "amount": 2}]}})
    assert dup.status_code == 422
    assert {e["path"] for e in dup.json()["detail"]["errors"]} == {"tax_strategy.trad_prefund_schedule"}
    assert _put(client, {"tax_strategy": {"trad_prefund_schedule": [{"year": 2027, "amount": -5}]}}).status_code == 422

    # The Stage 3 engine reads the saved schedule (no DAF required) and caps it at available Traditional.
    from config import get_config_manager
    from strategy_core.stages.stage3_early_retirement import Stage3EarlyRetirement
    stage = Stage3EarlyRetirement.__new__(Stage3EarlyRetirement)
    stage._log_decision = lambda *a, **k: None
    get_config_manager().config["tax_strategy"]["trad_prefund_schedule"] = rows
    calc = stage._calculate_daf_trad_prefund
    assert calc(None, 61, 2027, 1_000_000, 0) == 200000
    assert calc(None, 62, 2028, 1_000_000, 0) == 50000
    assert calc(None, 62, 2029, 1_000_000, 0) == 0
    assert calc(None, 61, 2027, 150_000, 100_000) == 50000  # capped by Traditional minus reserved


def test_strategy_decisions_endpoint_returns_reasons_and_strategy_stays_plain_json(client, monkeypatch):
    import pandas as pd
    from app.services import strategy_service
    from strategy_core.models import DecisionLog

    log = DecisionLog()
    log.add("roth_conversion", "BETR Conversion (Stage 3)", "Convert $404,606", "Low-income window.", betr=0.257)
    log.add("tax_strategy", "DAF", "Gift $300,000", "Bundling.", amount=300000)
    df = pd.DataFrame([{"Year": 2027, "Stage": "Stage 3", "Trad→\nCash": 36005.0, "Trad→\nRoth": 404606.0,
                        "Brok→\nCash": 0.0, "DAF Contribution": 0.0, "AGI": 1.0, "Federal Tax": 2.0,
                        "Decision Log": log}])
    monkeypatch.setattr(strategy_service, "_build_strategy",
                        lambda s, e: (df, df[["Year"]], {"start_year": 2027, "rate": 0.06}))

    body = client.get("/api/strategy/decisions?year=2027").json()
    assert body["summary"]["trad_to_roth"] == 404606.0
    cats = {g["category"]: g["decisions"] for g in body["groups"]}
    assert cats["roth_conversion"][0]["reason"] == "Low-income window."
    assert cats["roth_conversion"][0]["values"] == {"betr": 0.257}
    assert client.get("/api/strategy/decisions?year=1999").status_code == 404

    main = client.get("/api/strategy").json()  # the log must not leak into the table payload
    assert "Decision Log" not in main["columns"] and "Decision Log" not in main["strategy"][0]


# ---------------------------------------------------------------------------
# Tax Data Admin
# ---------------------------------------------------------------------------

@pytest.fixture
def tax_client(client, tmp_path):
    """The shared client with copies of the real reference tables in its working directory."""
    for name in ("standard.csv", "income_rates.csv", "cap_gains.csv", "ira_limits.csv", "irmaa.csv",
                 "rmd.csv", "ssincome.csv", "atm.csv"):
        shutil.copy(REPO / name, tmp_path / name)
    return client


def test_tax_data_page_served_and_in_shared_nav(client):
    html = client.get("/tax-data").text
    assert "grid-tax" in html and 'id="main-nav"' in html
    assert client.get("/static/tax_data.js").status_code == 200
    assert 'label: "Tax Data Admin", href: "/tax-data"' in client.get("/static/nav.js").text


def test_tax_data_page_loads_no_external_scripts_or_styles(client):
    import re
    html = client.get("/tax-data").text
    for tag in re.findall(r"<(?:script|link)[^>]+>", html):
        assert "http://" not in tag and "https://" not in tag, tag


def test_tax_data_list_and_get(tax_client):
    tables = tax_client.get("/api/tax-data").json()
    assert [t["key"] for t in tables] == ["standard", "income_rates", "cap_gains", "ira_limits",
                                          "irmaa", "rmd", "ssincome", "atm"]
    assert all(t["exists"] for t in tables)
    body = tax_client.get("/api/tax-data/standard?year=2026").json()
    assert body["year"] == 2026 and {r["year"] for r in body["rows"]} == {2026}
    assert tax_client.get("/api/tax-data/nope").status_code == 404
    assert tax_client.get("/api/tax-data/standard?year=1500").status_code == 422


def test_tax_data_save_roundtrip_backup_and_validation(tax_client, tmp_path):
    rows = tax_client.get("/api/tax-data/standard?year=2026").json()["rows"]
    original = (tmp_path / "standard.csv").read_text()
    rows[0]["deduction"] = 31111
    r = tax_client.put("/api/tax-data/standard", json={"year": 2026, "rows": rows})
    assert r.status_code == 200 and r.json()["rows"][0]["deduction"] == 31111
    assert "31111" in (tmp_path / "standard.csv").read_text()
    assert next((tmp_path / ".backups").glob("standard_*.csv")).read_text() == original

    rows[0]["filing_status"] = "bogus"
    saved = (tmp_path / "standard.csv").read_text()
    bad = tax_client.put("/api/tax-data/standard", json={"year": 2026, "rows": rows})
    assert bad.status_code == 422
    assert bad.json()["detail"]["errors"][0]["column"] == "filing_status"
    assert (tmp_path / "standard.csv").read_text() == saved

    # a year is required for tables that have a year column
    assert tax_client.put("/api/tax-data/standard", json={"rows": rows}).status_code == 422


def test_tax_data_save_is_seen_by_the_engine(tax_client):
    import load_data
    rows = tax_client.get("/api/tax-data/standard?year=2026").json()["rows"]
    single = next(r for r in rows if r["filing_status"] == "single")
    before = float(load_data.get_std_deduction(2026, "single").deduction.iloc[0])
    single["deduction"] = int(before) + 500
    assert tax_client.put("/api/tax-data/standard", json={"year": 2026, "rows": rows}).status_code == 200
    assert float(load_data.get_std_deduction(2026, "single").deduction.iloc[0]) == before + 500


def test_tax_data_download_and_upload(tax_client, tmp_path):
    d = tax_client.get("/api/tax-data/irmaa/download")
    assert d.status_code == 200 and d.headers["content-type"].startswith("text/csv")
    assert 'filename="irmaa_' in d.headers["content-disposition"]
    csv = d.text

    ok = tax_client.post("/api/tax-data/irmaa/validate-upload", json={"csv": csv}).json()
    assert ok["valid"] and ok["rows"] > 0 and len(ok["preview"]) == 10

    bad = tax_client.post("/api/tax-data/standard/validate-upload", json={"csv": "year,filing_status\n2026,single\n"}).json()
    assert not bad["valid"] and "deduction" in bad["errors"][0]
    assert tax_client.post("/api/tax-data/standard/validate-upload", json={"csv": ""}).status_code == 422

    rejected = tax_client.put("/api/tax-data/standard/upload", json={"csv": "year,filing_status\n2026,single\n"})
    assert rejected.status_code == 422 and not (tmp_path / ".backups").exists()

    new = "year,filing_status,deduction\n2030,single,20000\n2030,married_filing_jointly,40000\n"
    done = tax_client.put("/api/tax-data/standard/upload", json={"csv": new})
    assert done.status_code == 200 and done.json()["total_rows"] == 2 and done.json()["backup"]
    assert len(list((tmp_path / ".backups").glob("standard_*.csv"))) == 1


def test_tax_data_rejects_cross_origin_writes(tax_client):
    r = tax_client.put("/api/tax-data/standard", headers={"Origin": "http://evil.example"},
                       json={"year": 2026, "rows": []})
    assert r.status_code == 403


# ---------------------------------------------------------------------------
# Advanced Strategy Tools
# ---------------------------------------------------------------------------

@pytest.fixture
def adv_client(client, tmp_path, monkeypatch):
    """The shared client with the reference tables, and fixed account balances."""
    for name in ("standard.csv", "income_rates.csv", "cap_gains.csv", "ira_limits.csv", "irmaa.csv",
                 "atm.csv", "qbi_limits.csv"):
        shutil.copy(REPO / name, tmp_path / name)
    from app.services import advanced
    monkeypatch.setattr(advanced, "_balances",
                        lambda: {"cash": 100_000.0, "traditional": 500_000.0, "roth": 200_000.0, "taxable": 300_000.0})
    return client


PLANNER_BODY = dict(wages=100_000, year=2026, roth_amount=10_000)


def test_advanced_page_served_and_in_shared_nav(client):
    html = client.get("/advanced").text
    assert "Advanced Strategy Tools" in html and 'id="main-nav"' in html
    assert client.get("/static/advanced.js").status_code == 200
    assert 'label: "Advanced Strategy Tools", href: "/advanced"' in client.get("/static/nav.js").text


def test_advanced_page_loads_no_external_scripts_or_styles(client):
    import re
    html = client.get("/advanced").text
    for tag in re.findall(r"<(?:script|link)[^>]+>", html):
        assert "http://" not in tag and "https://" not in tag, tag


def test_advanced_guides_are_served_and_static(client):
    for key in ("tax_planner", "multi_year", "qbi", "backdoor", "nua", "qcd", "sepp", "harvest"):
        r = client.get(f"/static/guides/{key}.html")
        assert r.status_code == 200 and "<script" not in r.text.lower() and "http://" not in r.text


def test_advanced_meta(adv_client):
    m = adv_client.get("/api/advanced/meta").json()
    assert m["planner_years"][0] == 2023 and m["filing_status"] == "married_filing_jointly"
    assert m["balances"]["traditional"] == 500_000 and "Fixed Amortization" in m["sepp_methods"]


def test_advanced_tax_planner_roundtrip(adv_client):
    r = adv_client.post("/api/advanced/tax-planner", json=PLANNER_BODY)
    assert r.status_code == 200, r.text
    cols = {c["title"]: {m["label"]: m["value"] for m in c["metrics"]} for c in r.json()["columns"]}
    assert cols["Ordinary Income"]["AGI"] == 75_800 and cols["Taxes Owed"]["Income Tax"] == 8_600


def test_advanced_tax_planner_unknown_year_is_422(adv_client):
    r = adv_client.post("/api/advanced/tax-planner", json={**PLANNER_BODY, "year": 2099})
    assert r.status_code == 422 and "tax data" in str(r.json()["detail"]).lower()


@pytest.mark.parametrize("path,body", [
    ("tax-planner", {**PLANNER_BODY, "medicare": 3}),
    ("tax-planner", {**PLANNER_BODY, "headroom_pct": 25}),
    ("tax-planner", {**PLANNER_BODY, "daf_type": "gold"}),
    ("tax-planner", {**PLANNER_BODY, "surprise": 1}),
    ("multi-year", dict(start_year=2026, window=2)),
    ("multi-year", dict(start_year=2026, window=11)),
    ("multi-year", dict(start_year=2026, income=-1)),
    ("backdoor", dict(year=2026, age=17)),
    ("backdoor", dict(year=2026, age=81)),
    ("betr", dict(conversion_amount=999)),
    ("betr", dict(current_rate=0.09)),
    ("betr", dict(annual_return=0.13)),
    ("betr", dict(years=41)),
    ("mega-backdoor", dict(year=2026, age=17)),
    ("nua", dict(ltcg_rate=0.21)),
    ("nua", dict(years=31)),
    ("qcd", dict(year=2026, age=69)),
    ("sepp", dict(age=59)),
    ("sepp", dict(balance=999)),
    ("sepp", dict(rate=0.11)),
    ("harvest", dict(start_year=2026, window=0)),
    ("qbi", dict(qbi_income=-5)),
    ("qbi", dict(filing_status="head_of_household")),
])
def test_advanced_rejects_out_of_range_inputs(adv_client, path, body):
    r = adv_client.post(f"/api/advanced/{path}", json=body)
    assert r.status_code == 422, (path, body, r.text)


def test_advanced_sepp_unknown_method_is_422(adv_client):
    r = adv_client.post("/api/advanced/sepp", json=dict(method="Made Up"))
    assert r.status_code == 422 and "Unknown SEPP method" in r.json()["detail"]


def test_advanced_calculators_return_json(adv_client):
    calls = {
        "multi-year": dict(start_year=2026, filing_status="single", income=100_000, window=3),
        "qbi": dict(qbi_income=100_000, total_taxable_income=200_000),
        "backdoor": dict(year=2026, magi=250_000),
        "betr": {},
        "mega-backdoor": dict(year=2026, employee_deferral=23_500, employer_match=5_000),
        "nua": dict(cost_basis=50_000, current_value=200_000),
        "qcd": dict(year=2026, ira_balance=500_000, rmd=20_000, agi=100_000, charitable=10_000),
        "sepp": {},
        "harvest": dict(start_year=2026, window=3, income=100_000, unrealized_losses=50_000),
    }
    for path, body in calls.items():
        r = adv_client.post(f"/api/advanced/{path}", json=body)
        assert r.status_code == 200, (path, r.text)
        assert isinstance(r.json(), dict)
    assert adv_client.post("/api/advanced/nua", json=calls["nua"]).json()["nua_amount"] == 150_000
    assert adv_client.post("/api/advanced/harvest", json=calls["harvest"]).json()["rows"][0]["harvested"] == 50_000


def test_advanced_post_requires_same_origin(adv_client):
    r = adv_client.post("/api/advanced/qbi", json=dict(qbi_income=1), headers={"Origin": "http://evil.example"})
    assert r.status_code == 403


# ---------------------------------------------------------------------------
# Monte Carlo API Tests
# ---------------------------------------------------------------------------

def test_monte_carlo_page_and_meta(client):
    page_r = client.get("/monte-carlo")
    assert page_r.status_code == 200
    assert "Monte Carlo Simulation" in page_r.text

    meta_r = client.get("/api/monte-carlo/meta")
    assert meta_r.status_code == 200
    meta = meta_r.json()
    assert "portfolio_presets" in meta
    assert "stress_scenarios" in meta
    assert "longevity_scenarios" in meta

    defs_r = client.get("/api/monte-carlo/defaults")
    assert defs_r.status_code == 200
    defs = defs_r.json()
    assert "portfolio" in defs
    assert "withdrawal" in defs


def test_monte_carlo_run_and_job_polling(client):
    import time
    payload = {
        "portfolio": 1_000_000,
        "withdrawal": 50_000,
        "start_age": 62,
        "end_age": 85,
        "ss_annual": 20_000,
        "ss_start_age": 70,
        "inflation_pct": 2.5,
        "allocation": "Moderate (70/30)",
        "n_simulations": 200,
    }

    submit_r = client.post("/api/monte-carlo/run", json=payload)
    assert submit_r.status_code == 200
    job_id = submit_r.json()["job_id"]

    for _ in range(30):
        poll_r = client.get(f"/api/jobs/{job_id}")
        assert poll_r.status_code == 200
        job_data = poll_r.json()
        if job_data["status"] == "completed":
            break
        time.sleep(0.05)

    assert job_data["status"] == "completed"
    res = job_data["result"]
    assert "success_probability" in res
    assert "median_final_portfolio" in res
    assert "fan_chart" in res


def test_monte_carlo_stress_tests_job_endpoint(client):
    import time
    payload = {
        "inputs": {
            "portfolio": 1_000_000,
            "withdrawal": 50_000,
            "start_age": 62,
            "end_age": 85,
            "ss_annual": 20_000,
            "ss_start_age": 70,
            "inflation_pct": 2.5,
            "allocation": "Moderate (70/30)",
            "n_simulations": 200,
        },
        "scenarios": ["2008 Financial Crisis"],
    }
    submit_r = client.post("/api/monte-carlo/stress-tests", json=payload)
    assert submit_r.status_code == 200
    job_id = submit_r.json()["job_id"]

    for _ in range(30):
        poll_r = client.get(f"/api/jobs/{job_id}")
        assert poll_r.status_code == 200
        job_data = poll_r.json()
        if job_data["status"] == "completed":
            break
        time.sleep(0.05)

    assert job_data["status"] == "completed"
    res = job_data["result"]
    assert "results" in res
    assert len(res["results"]) == 1


def test_monte_carlo_export_csv_endpoint(client):
    payload = {
        "inputs": {
            "portfolio": 1_000_000,
            "withdrawal": 50_000,
            "start_age": 62,
            "end_age": 85,
            "ss_annual": 20_000,
            "ss_start_age": 70,
            "inflation_pct": 2.5,
            "allocation": "Moderate (70/30)",
            "n_simulations": 100,
        },
        "include_stress": True,
        "include_longevity": True,
    }
    r = client.post("/api/monte-carlo/export-csv", json=payload)
    assert r.status_code == 200
    assert r.headers["content-type"] == "text/csv; charset=utf-8"
    assert "MONTE CARLO SIMULATION REPORT" in r.text
