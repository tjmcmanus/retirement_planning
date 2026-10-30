"""Reports & PDF Export service for retirement planning.

Provides report template management, asynchronous PDF report generation
with background job progress tracking, report history, and printable
expense & healthcare data extraction.
"""
from __future__ import annotations

import logging
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any

import settings
from config import get_config_manager
from components.reporting import ReportBuilder, get_template_manager
from app.services import jobs

logger = logging.getLogger(__name__)


def _get_reports_dir() -> Path:
    """Return directory where PDF reports are stored."""
    rep_dir = Path(settings.data_path("generated_reports"))
    rep_dir.mkdir(parents=True, exist_ok=True)
    return rep_dir


def list_templates() -> list[dict[str, Any]]:
    """List available report templates."""
    try:
        mgr = get_template_manager()
        return mgr.list_templates()
    except Exception as e:
        logger.exception("Error listing report templates: %s", e)
        return []


def get_template_details(template_id: str) -> dict[str, Any] | None:
    """Get full template config with sections."""
    try:
        mgr = get_template_manager()
        tpl = mgr.get_template(template_id)
        if not tpl:
            return None
        return tpl.to_dict()
    except Exception as e:
        logger.exception("Error getting template %s: %s", template_id, e)
        return None


def _sanitize_filename(name: str) -> str:
    """Sanitize string for safe filenames."""
    clean = re.sub(r"[^\w\-.]", "_", name.strip())
    if not clean.lower().endswith(".pdf"):
        clean += ".pdf"
    return clean


def start_report_generation_job(payload: dict[str, Any]) -> str:
    """Start background job to generate PDF report."""
    template_id = payload.get("template_id", "comprehensive_retirement_plan")
    custom_title = payload.get("title")
    prepared_for = payload.get("prepared_for")
    filename = payload.get("filename")
    section_overrides = payload.get("sections", {})  # {section_id: bool}

    if not filename:
        slug = re.sub(r"\W+", "_", (custom_title or template_id).lower()).strip("_")
        filename = f"{slug}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    filename = _sanitize_filename(filename)

    out_dir = _get_reports_dir()
    output_path = out_dir / filename

    def _worker(update_progress):
        update_progress(5, "Initializing template...")
        builder = ReportBuilder(template_id)

        # Apply custom title if provided
        if custom_title:
            builder.data["report_title"] = custom_title

        # Apply section overrides
        if section_overrides:
            for sec in builder.template.sections:
                sec_id = sec.get("section_id")
                if sec_id in section_overrides:
                    sec["enabled"] = bool(section_overrides[sec_id])

        def _progress_cb(msg: str, frac: float):
            # Scale callback between 10% and 95%
            pct = int((0.10 + (frac * 0.85)) * 100)
            update_progress(pct, msg)

        res_path = builder.generate_report(
            output_path=str(output_path),
            prepared_for=prepared_for if prepared_for else None,
            progress_callback=_progress_cb,
        )

        file_size_kb = os.path.getsize(res_path) / 1024
        return {
            "filename": filename,
            "path": str(res_path),
            "size_kb": round(file_size_kb, 1),
            "generated_at": datetime.now().isoformat(),
        }

    job_id = jobs.submit_job("report_generation", _worker)
    return job_id


def list_report_history() -> list[dict[str, Any]]:
    """List all generated PDF reports."""
    rep_dir = _get_reports_dir()
    if not rep_dir.exists():
        return []

    pdf_files = list(rep_dir.glob("*.pdf"))
    pdf_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)

    results = []
    for f in pdf_files:
        try:
            st = f.stat()
            results.append({
                "filename": f.name,
                "size_kb": round(st.st_size / 1024, 1),
                "modified_at": datetime.fromtimestamp(st.st_mtime).strftime("%Y-%m-%d %H:%M"),
                "timestamp": st.st_mtime,
            })
        except Exception as e:
            logger.warning("Could not stat report %s: %s", f, e)

    return results


def get_report_file_path(filename: str) -> Path | None:
    """Get absolute path to a generated report if it exists and is secure."""
    sanitized = _sanitize_filename(filename)
    rep_dir = _get_reports_dir()
    target = (rep_dir / sanitized).resolve()
    if target.is_relative_to(rep_dir.resolve()) and target.is_file():
        return target
    return None


def delete_report(filename: str) -> bool:
    """Delete a generated PDF report."""
    target = get_report_file_path(filename)
    if target and target.exists():
        target.unlink()
        return True
    return False


def clear_all_reports() -> int:
    """Delete all generated PDF reports."""
    rep_dir = _get_reports_dir()
    if not rep_dir.exists():
        return 0
    count = 0
    for f in rep_dir.glob("*.pdf"):
        try:
            f.unlink()
            count += 1
        except Exception as e:
            logger.warning("Failed to delete %s: %s", f, e)
    return count


def get_expense_healthcare_data() -> dict[str, Any]:
    """Extract live configuration for the Expense & Healthcare printable summary."""
    cfg = get_config_manager()

    p1_name = cfg.get("personal_info", "person1_name", "Person 1")
    p2_name = cfg.get("personal_info", "person2_name", "Person 2")
    p1_bd = cfg.get("personal_info", "person1_birth_date", "1966-01-01")
    p2_bd = cfg.get("personal_info", "person2_birth_date", "1967-01-01")
    p1_ret = cfg.get("personal_info", "person1_retirement_date", "2026-01-01")
    p2_ret = cfg.get("personal_info", "person2_retirement_date", "2027-01-01")
    state = cfg.get("personal_info", "retirement_state", "")
    is_single = cfg.get("personal_info", "is_single_person", False)

    living = cfg.get_section("expenses").get("living_expenses", {})
    entertain = cfg.get_section("expenses").get("entertainment_expenses", {})
    fin = cfg.get_section("financial_assumptions")
    hc = cfg.get_section("healthcare")
    char = cfg.get_section("charitable_giving")
    ss = cfg.get_section("social_security")

    def _calc_age_yr(ret_date: str, birth_date: str):
        try:
            by = int(birth_date.split("-")[0])
            ry = int(ret_date.split("-")[0])
            return ry - by, ry
        except Exception:
            return 65, 2031

    p1_ret_age, p1_ret_yr = _calc_age_yr(p1_ret, p1_bd)
    p2_ret_age, p2_ret_yr = _calc_age_yr(p2_ret, p2_bd)

    p1_med_age = hc.get("person1_medicare_start_age", 65)
    p2_med_age = hc.get("person2_medicare_start_age", 65)
    p1_birth_yr = int(p1_bd.split("-")[0]) if "-" in str(p1_bd) else 1966
    p2_birth_yr = int(p2_bd.split("-")[0]) if "-" in str(p2_bd) else 1967
    p1_med_yr = p1_birth_yr + p1_med_age
    p2_med_yr = p2_birth_yr + p2_med_age

    living_items = [
        {"category": k.replace("_", " ").title(), "amount": float(v)}
        for k, v in living.items()
        if isinstance(v, (int, float)) and v > 0
    ]
    entertain_items = [
        {"category": k.replace("_", " ").title(), "amount": float(v)}
        for k, v in entertain.items()
        if isinstance(v, (int, float)) and v > 0
    ]

    total_living = sum(item["amount"] for item in living_items)
    total_entertain = sum(item["amount"] for item in entertain_items)

    return {
        "personal": {
            "p1_name": p1_name,
            "p2_name": p2_name,
            "is_single": is_single,
            "state": state,
            "p1_ret_age": p1_ret_age,
            "p1_ret_yr": p1_ret_yr,
            "p2_ret_age": p2_ret_age,
            "p2_ret_yr": p2_ret_yr,
            "p1_med_age": p1_med_age,
            "p1_med_yr": p1_med_yr,
            "p2_med_age": p2_med_age,
            "p2_med_yr": p2_med_yr,
        },
        "financial": {
            "expected_annual_expenses": float(fin.get("expected_annual_expenses", 80_000)),
            "expense_inflation_rate": float(fin.get("expense_inflation_rate", 3.0)),
            "expected_rate_of_return": float(fin.get("expected_rate_of_return", 6.0)),
            "years_of_expenses_in_cash": float(fin.get("years_of_expenses_in_cash", 2)),
            "accumulation_cash_buffer_months": int(fin.get("accumulation_cash_buffer_months", 6)),
        },
        "living_expenses": living_items,
        "total_living": total_living,
        "entertainment_expenses": entertain_items,
        "total_entertainment": total_entertain,
        "healthcare": {
            "p1_pre_medicare_annual": float(hc.get("person1_pre_medicare_annual", 0)),
            "p2_pre_medicare_annual": float(hc.get("person2_pre_medicare_annual", 0)),
            "p1_medicare_supplement_annual": float(hc.get("person1_medicare_supplement_annual", 0)),
            "p2_medicare_supplement_annual": float(hc.get("person2_medicare_supplement_annual", 0)),
            "p1_out_of_pocket_annual": float(hc.get("person1_out_of_pocket_annual", 0)),
            "p2_out_of_pocket_annual": float(hc.get("person2_out_of_pocket_annual", 0)),
            "annual_inflation": float(hc.get("healthcare_inflation_rate", 5.0)),
        },
        "charitable": {
            "annual_giving": float(char.get("annual_giving_amount", 0)),
            "qcd_eligible": char.get("use_qcd", False),
        },
        "social_security": {
            "p1_amount": float(ss.get("person1_expected_benefit", 0)),
            "p1_age": int(ss.get("person1_start_age", 67)),
            "p2_amount": float(ss.get("person2_expected_benefit", 0)),
            "p2_age": int(ss.get("person2_start_age", 67)),
        },
    }
