"""Unit tests for Reports & PDF Export service."""
import time
import pytest
from app.services import reports_service, jobs


def test_reports_service():
    # 1. Templates
    templates = reports_service.list_templates()
    assert len(templates) > 0
    tpl_id = templates[0]["template_id"]

    # 2. Template details
    details = reports_service.get_template_details(tpl_id)
    assert details is not None
    assert "sections" in details
    assert len(details["sections"]) > 0

    # 3. Expense & Healthcare data extraction
    exp_hc = reports_service.get_expense_healthcare_data()
    assert "personal" in exp_hc
    assert "financial" in exp_hc
    assert "living_expenses" in exp_hc
    assert "healthcare" in exp_hc

    # 4. History check & cleanup
    history = reports_service.list_report_history()
    assert isinstance(history, list)
