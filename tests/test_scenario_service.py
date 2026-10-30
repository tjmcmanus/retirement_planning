"""Unit tests for Scenario Planning service."""
import pytest
from app.services import scenario_service


def test_scenario_lifecycle():
    # 1. List scenarios
    scenarios = scenario_service.list_scenarios()
    assert len(scenarios) >= 1

    # 2. Get scenario
    first_id = scenarios[0]["id"]
    sc = scenario_service.get_scenario(first_id)
    assert sc is not None
    assert sc["id"] == first_id

    # 3. Clone scenario
    cloned = scenario_service.clone_scenario(first_id, new_name="Test Cloned Scenario")
    assert cloned is not None
    assert cloned["name"] == "Test Cloned Scenario"
    cloned_id = cloned["id"]

    # 4. Update cloned scenario
    updated = scenario_service.update_scenario(cloned_id, {
        "name": "Updated Cloned Scenario",
        "annual_expenses": 95_000,
        "retirement_age": 60,
    })
    assert updated["name"] == "Updated Cloned Scenario"
    assert updated["financial"]["annual_expenses"] == 95_000
    assert updated["personal"]["retirement_age"] == 60

    # 5. Templates
    templates = scenario_service.get_templates()
    assert len(templates) > 0
    assert any(t["name"] == "Part-Time Work" for t in templates)

    # 6. Add life event
    ev_updated = scenario_service.add_life_event(cloned_id, {
        "name": "Consulting Income",
        "event_type": "part_time_work",
        "start_age": 60,
        "end_age": 65,
        "income_change": 30_000,
    })
    assert len(ev_updated["life_events"]) >= 1
    event_id = ev_updated["life_events"][0]["id"]

    # 7. Analyze scenario
    res = scenario_service.analyze_scenario(cloned_id, n_simulations=100)
    assert res["success"] is True
    assert "success_probability" in res
    assert "median_path" in res
    assert len(res["cash_flows"]) > 0

    # 8. Delete life event
    del_ev = scenario_service.delete_life_event(cloned_id, event_id)
    assert len(del_ev["life_events"]) == 0

    # 9. Delete scenario
    del_res = scenario_service.delete_scenario(cloned_id)
    assert del_res is True
