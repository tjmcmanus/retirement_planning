"""Tests for app/services/tax_data.py (Tax Data Admin). Runs on the host: no FastAPI needed."""
import shutil
from datetime import datetime
from pathlib import Path

import pandas as pd
import pytest

import app_cache
from app.services import tax_data

REPO = Path(__file__).resolve().parent.parent
CSVS = [spec["filename"] for spec in tax_data.TABLES.values()]
YEAR = datetime.now().year


@pytest.fixture
def work(tmp_path, monkeypatch):
    """A working directory holding copies of the real tables (like /data in the container)."""
    monkeypatch.chdir(tmp_path)
    for name in CSVS:
        shutil.copy(REPO / name, tmp_path / name)
    return tmp_path


def _rows(key, year=None):
    return tax_data.get_table(key, year)["rows"]


def test_every_shipped_table_validates_and_lists(work):
    for key, spec in tax_data.TABLES.items():
        text = (work / spec["filename"]).read_text()
        report = tax_data.validate_upload(key, text)
        assert report["valid"], (key, report["errors"])
    listing = {t["key"]: t for t in tax_data.list_tables()}
    assert set(listing) == set(tax_data.TABLES)
    assert all(t["exists"] and t["rows"] > 0 for t in listing.values())
    assert listing["standard"]["year_span"][0] <= YEAR <= listing["standard"]["year_span"][1]


def test_spec_columns_match_the_real_files(work):
    for key, spec in tax_data.TABLES.items():
        assert list(spec["columns"]) == list(pd.read_csv(work / spec["filename"]).columns), key


def test_get_table_scopes_to_one_year_and_offers_neighbour_years(work):
    t = tax_data.get_table("standard", YEAR)
    assert t["year"] == YEAR and {r["year"] for r in t["rows"]} == {YEAR}
    assert {YEAR - 1, YEAR, YEAR + 1} <= set(t["years"])
    assert t["total_rows"] > len(t["rows"])
    # a year with no rows is offered but empty
    assert tax_data.get_table("standard", 2099)["rows"] == []
    # tables without a year column return everything
    rmd = tax_data.get_table("rmd")
    assert rmd["has_year"] is False and len(rmd["rows"]) == rmd["total_rows"]


def test_get_table_columns_have_kinds_and_choices(work):
    cols = {c["name"]: c for c in tax_data.get_table("income_rates", YEAR)["columns"]}
    assert cols["filing_status"]["choices"] == tax_data.FILING_STATUSES
    assert cols["rate"]["kind"] == "float" and cols["lower"]["kind"] == "int"


def test_unknown_table_and_missing_file(work):
    with pytest.raises(LookupError):
        tax_data.get_table("nope")
    (work / "atm.csv").unlink()
    with pytest.raises(FileNotFoundError):
        tax_data.get_table("atm", YEAR)
    assert next(t for t in tax_data.list_tables() if t["key"] == "atm")["exists"] is False


def test_save_changes_one_year_only_and_keeps_the_rest(work):
    before = pd.read_csv(work / "standard.csv")
    rows = _rows("standard", YEAR)
    rows[0]["deduction"] = 99999
    out = tax_data.save_rows("standard", YEAR, rows)
    after = pd.read_csv(work / "standard.csv")
    assert len(after) == len(before)
    assert after[after.year != YEAR].equals(before[before.year != YEAR])
    assert int(after[(after.year == YEAR) & (after.filing_status == rows[0]["filing_status"])].deduction.iloc[0]) == 99999
    assert out["rows"][0]["deduction"] == 99999


def test_save_writes_backup_with_old_content(work):
    original = (work / "standard.csv").read_text()
    rows = _rows("standard", YEAR)
    rows[0]["deduction"] = 12345
    out = tax_data.save_rows("standard", YEAR, rows)
    backups = list((work / ".backups").glob("standard_*.csv"))
    assert len(backups) == 1 and out["backup"] == str(Path(".backups") / backups[0].name)
    assert backups[0].read_text() == original


def test_two_saves_in_one_second_keep_both_backups(work):
    rows = _rows("standard", YEAR)
    tax_data.save_rows("standard", YEAR, rows)
    tax_data.save_rows("standard", YEAR, rows)
    assert len(list((work / ".backups").glob("standard_*.csv"))) == 2


def test_save_can_add_a_new_year_in_sorted_position(work):
    new_year = 2099
    rows = [{"year": new_year, "filing_status": "single", "deduction": 20000},
            {"year": new_year, "filing_status": "married_filing_jointly", "deduction": 40000}]
    tax_data.save_rows("standard", new_year, rows)
    df = pd.read_csv(work / "standard.csv")
    assert df.year.is_monotonic_increasing and (df.year == new_year).sum() == 2


def test_save_can_delete_rows_of_the_year(work):
    rows = _rows("standard", YEAR)[:1]
    tax_data.save_rows("standard", YEAR, rows)
    assert len(_rows("standard", YEAR)) == 1


def test_save_keeps_a_file_that_is_not_sorted_in_its_original_order(work):
    before = pd.read_csv(work / "atm.csv")
    assert not before.year.is_monotonic_increasing          # the shipped atm.csv is not sorted
    year = int(before.year.iloc[3])
    rows = _rows("atm", year)
    rows[0]["deduction"] = 1
    tax_data.save_rows("atm", year, rows)
    after = pd.read_csv(work / "atm.csv")
    assert after.year.tolist() == before.year.tolist()      # same row order
    assert int(after[after.year == year].deduction.iloc[0]) == 1


def test_save_rejects_bad_cells_and_writes_nothing(work):
    original = (work / "standard.csv").read_text()
    rows = _rows("standard", YEAR)
    rows[0]["deduction"] = "abc"
    rows[1]["filing_status"] = "head_of_household"
    rows.append({"year": YEAR, "filing_status": "single", "deduction": None})
    with pytest.raises(tax_data.TableValidationError) as exc:
        tax_data.save_rows("standard", YEAR, rows)
    found = {(e["row"], e["column"]) for e in exc.value.errors}
    assert {(0, "deduction"), (1, "filing_status"), (len(rows) - 1, "deduction")} <= found
    assert (work / "standard.csv").read_text() == original
    assert not (work / ".backups").exists()


def test_save_rejects_wrong_year_non_integers_and_empty_result(work):
    rows = _rows("standard", YEAR)
    rows[0]["year"] = YEAR + 1
    with pytest.raises(tax_data.TableValidationError) as exc:
        tax_data.save_rows("standard", YEAR, rows)
    assert any(e["column"] == "year" for e in exc.value.errors)

    rows = _rows("standard", YEAR)
    rows[0]["deduction"] = 123.5
    with pytest.raises(tax_data.TableValidationError) as exc:
        tax_data.save_rows("standard", YEAR, rows)
    assert "whole number" in exc.value.errors[0]["message"]

    rmd = _rows("rmd")
    with pytest.raises(tax_data.TableValidationError):
        tax_data.save_rows("rmd", None, [])
    assert len(_rows("rmd")) == len(rmd)

    with pytest.raises(ValueError):
        tax_data.save_rows("standard", None, rows)          # year is required for a table with a year column


def test_save_rejects_nan_inf_and_year_range(work):
    rows = _rows("income_rates", YEAR)
    rows[0]["rate"] = float("nan")
    rows[1]["upper"] = "inf"
    with pytest.raises(tax_data.TableValidationError) as exc:
        tax_data.save_rows("income_rates", YEAR, rows)
    assert {e["column"] for e in exc.value.errors} == {"rate", "upper"}
    with pytest.raises(tax_data.TableValidationError) as exc:
        tax_data.save_rows("standard", 1999, [{"year": 1999, "filing_status": "single", "deduction": 1}])
    assert any("between" in e["message"] for e in exc.value.errors)


def test_float_values_round_trip_without_noise(work):
    rows = _rows("income_rates", YEAR)
    rows[0]["rate"] = 0.235
    tax_data.save_rows("income_rates", YEAR, rows)
    assert "0.235" in (work / "income_rates.csv").read_text()


def test_save_table_without_year_replaces_everything(work):
    rows = _rows("rmd")
    rows[0]["Distribution"] = 1.5
    tax_data.save_rows("rmd", None, rows)
    assert pd.read_csv(work / "rmd.csv").Distribution.iloc[0] == 1.5


def test_save_clears_memoised_results(work):
    import load_data
    first = float(load_data.get_std_deduction(YEAR, "single").deduction.iloc[0])
    rows = _rows("standard", YEAR)
    for r in rows:
        if r["filing_status"] == "single":
            r["deduction"] = int(first) + 777
    tax_data.save_rows("standard", YEAR, rows)
    assert float(load_data.get_std_deduction(YEAR, "single").deduction.iloc[0]) == first + 777
    app_cache.clear_all()


def test_upload_validation_accepts_real_files_and_downloaded_copies(work):
    for key in ("irmaa", "atm", "rmd"):         # the Streamlit page rejected these three
        name, data = tax_data.download(key)
        assert name.startswith(key) and name.endswith(".csv")
        assert tax_data.validate_upload(key, data.decode())["valid"]


def test_upload_validation_reports_problems(work):
    r = tax_data.validate_upload("standard", "year,filing_status\n2024,single\n")
    assert not r["valid"] and "deduction" in r["errors"][0]
    r = tax_data.validate_upload("standard", "year,filing_status,deduction\n2024,alien,100\nabc,single,5\n")
    assert not r["valid"] and any("alien" in e for e in r["errors"]) and any("not a number" in e for e in r["errors"])
    r = tax_data.validate_upload("standard", "year,filing_status,deduction\n1999,single,100\n")
    assert any("between" in e for e in r["errors"])
    assert not tax_data.validate_upload("standard", "year,filing_status,deduction\n")["valid"]      # no data rows
    with pytest.raises(tax_data.TableValidationError):
        tax_data.validate_upload("standard", "")                                                      # empty file


def test_upload_warns_about_extra_columns_and_caps_error_list(work):
    r = tax_data.validate_upload("standard", "year,filing_status,deduction,note\n2024,single,1,x\n")
    assert r["valid"] and "note" in r["warnings"][0]
    big = "year,filing_status,deduction\n" + "abc,single,1\n" * 200
    r = tax_data.validate_upload("standard", big)
    assert len(r["errors"]) == tax_data.MAX_REPORTED_ERRORS + 1 and r["errors"][-1].startswith("...and")


def test_replace_table_backs_up_and_replaces(work):
    original = (work / "standard.csv").read_text()
    csv = "year,filing_status,deduction\n2030,single,20000\n2030,married_filing_jointly,40000\n"
    out = tax_data.replace_table("standard", csv)
    assert out["total_rows"] == 2
    assert pd.read_csv(work / "standard.csv").deduction.tolist() == [20000, 40000]
    assert next((work / ".backups").glob("standard_*.csv")).read_text() == original


def test_replace_table_rejects_invalid_and_leaves_file(work):
    original = (work / "standard.csv").read_text()
    with pytest.raises(tax_data.TableValidationError):
        tax_data.replace_table("standard", "year,filing_status,deduction\n2030,alien,1\n")
    assert (work / "standard.csv").read_text() == original and not (work / ".backups").exists()


def test_no_temp_file_left_behind(work):
    tax_data.save_rows("standard", YEAR, _rows("standard", YEAR))
    assert not list(work.glob("*.tmp"))
