"""
test_scenario_planning.py
==========================
Comprehensive tests for Scenario Planning & What-If Analysis

Tests cover:
- Scenario CRUD operations
- Life event modeling
- Event impact calculations
- Scenario comparison
- URL encoding/decoding
- Data validation
- Conflict detection
"""

import pytest
import json
from pathlib import Path
from datetime import datetime
import tempfile
import shutil

from scenario_manager import (
    Scenario,
    ScenarioManager,
    LifeEvent,
    LifeEventType,
    SocialSecurityConfig,
    PensionConfig,
    PartTimeIncomeConfig,
    TaxStrategyConfig,
    ScenarioResults,
)
from life_event_modeler import (
    LifeEventTemplates,
    detect_event_conflicts,
    calculate_event_timeline,
    get_template_list,
)


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def temp_storage_dir():
    """Create a temporary directory for test scenarios."""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir)


@pytest.fixture
def scenario_manager(temp_storage_dir):
    """Create a ScenarioManager with temporary storage."""
    return ScenarioManager(storage_dir=temp_storage_dir)


@pytest.fixture
def sample_scenario():
    """Create a sample scenario for testing."""
    return Scenario(
        name="Test Scenario",
        description="A test scenario",
        initial_portfolio=1_500_000,
        annual_expenses=80_000,
        inflation_rate=0.029,
        person1_age=62,
        person2_age=60,
        retirement_age=62,
        plan_to_age=95,
        social_security=SocialSecurityConfig(
            person1_amount=36_000,
            person1_start_age=70,
            person2_amount=24_000,
            person2_start_age=67,
        ),
    )


# ============================================================================
# Scenario Tests
# ============================================================================

class TestScenario:
    """Tests for Scenario data model."""
    
    def test_scenario_creation(self):
        """Test creating a basic scenario."""
        scenario = Scenario(
            name="Basic Test",
            initial_portfolio=1_000_000,
            annual_expenses=50_000,
        )
        
        assert scenario.name == "Basic Test"
        assert scenario.initial_portfolio == 1_000_000
        assert scenario.annual_expenses == 50_000
        assert scenario.id is not None
        assert scenario.created_at is not None
    
    def test_scenario_validation(self):
        """Test scenario validation."""
        # Negative portfolio should raise error
        with pytest.raises(ValueError):
            Scenario(initial_portfolio=-100_000)
        
        # Invalid retirement age should raise error
        with pytest.raises(ValueError):
            Scenario(retirement_age=30)
        
        # Invalid plan_to_age should raise error
        with pytest.raises(ValueError):
            Scenario(retirement_age=65, plan_to_age=60)
    
    def test_scenario_to_dict(self, sample_scenario):
        """Test converting scenario to dictionary."""
        data = sample_scenario.to_dict()
        
        assert data["name"] == "Test Scenario"
        assert data["financial"]["initial_portfolio"] == 1_500_000
        assert data["personal"]["retirement_age"] == 62
        assert "social_security" in data["income_sources"]
    
    def test_scenario_from_dict(self, sample_scenario):
        """Test creating scenario from dictionary."""
        data = sample_scenario.to_dict()
        restored = Scenario.from_dict(data)
        
        assert restored.name == sample_scenario.name
        assert restored.initial_portfolio == sample_scenario.initial_portfolio
        assert restored.retirement_age == sample_scenario.retirement_age
    
    def test_scenario_clone(self, sample_scenario):
        """Test cloning a scenario."""
        cloned = sample_scenario.clone("Cloned Scenario")
        
        assert cloned.name == "Cloned Scenario"
        assert cloned.id != sample_scenario.id
        assert cloned.initial_portfolio == sample_scenario.initial_portfolio
        assert cloned.is_baseline is False
    
    def test_scenario_life_events(self, sample_scenario):
        """Test adding life events to scenario."""
        event = LifeEvent(
            id="test_event",
            event_type=LifeEventType.INHERITANCE,
            name="Test Inheritance",
            start_age=70,
            one_time_amount=500_000,
        )
        
        sample_scenario.life_events.append(event)
        
        assert len(sample_scenario.life_events) == 1
        assert sample_scenario.life_events[0].name == "Test Inheritance"
    
    def test_get_life_events_at_age(self, sample_scenario):
        """Test getting life events at specific age."""
        event1 = LifeEvent(
            id="event1",
            event_type=LifeEventType.PART_TIME_WORK,
            name="Part-Time Work",
            start_age=62,
            end_age=67,
            income_change=30_000,
        )
        event2 = LifeEvent(
            id="event2",
            event_type=LifeEventType.INHERITANCE,
            name="Inheritance",
            start_age=70,
            one_time_amount=500_000,
        )
        
        sample_scenario.life_events.extend([event1, event2])
        
        # At age 65, only part-time work is active
        events_at_65 = sample_scenario.get_life_events_at_age(65)
        assert len(events_at_65) == 1
        assert events_at_65[0].name == "Part-Time Work"
        
        # At age 70, only inheritance is active
        events_at_70 = sample_scenario.get_life_events_at_age(70)
        assert len(events_at_70) == 1
        assert events_at_70[0].name == "Inheritance"
    
    def test_get_total_impact_at_age(self, sample_scenario):
        """Test calculating total impact of all events at age."""
        event1 = LifeEvent(
            id="event1",
            event_type=LifeEventType.PART_TIME_WORK,
            name="Part-Time Work",
            start_age=62,
            end_age=67,
            income_change=30_000,
        )
        event2 = LifeEvent(
            id="event2",
            event_type=LifeEventType.DOWNSIZING,
            name="Downsize",
            start_age=65,
            expense_change=-10_000,
        )
        
        sample_scenario.life_events.extend([event1, event2])
        
        # At age 65, both events are active
        impact = sample_scenario.get_total_impact_at_age(65)
        assert impact["income"] == 30_000
        assert impact["expense"] == -10_000


# ============================================================================
# LifeEvent Tests
# ============================================================================

class TestLifeEvent:
    """Tests for LifeEvent data model."""
    
    def test_life_event_creation(self):
        """Test creating a life event."""
        event = LifeEvent(
            id="test_event",
            event_type=LifeEventType.INHERITANCE,
            name="Test Inheritance",
            start_age=70,
            one_time_amount=500_000,
        )
        
        assert event.name == "Test Inheritance"
        assert event.start_age == 70
        assert event.one_time_amount == 500_000
    
    def test_life_event_validation(self):
        """Test life event validation."""
        # Invalid start age
        with pytest.raises(ValueError):
            LifeEvent(
                id="test",
                event_type=LifeEventType.CUSTOM,
                name="Test",
                start_age=-5,
            )
        
        # End age before start age
        with pytest.raises(ValueError):
            LifeEvent(
                id="test",
                event_type=LifeEventType.CUSTOM,
                name="Test",
                start_age=70,
                end_age=65,
            )
    
    def test_is_active_at_age(self):
        """Test checking if event is active at age."""
        # One-time event
        one_time = LifeEvent(
            id="test",
            event_type=LifeEventType.INHERITANCE,
            name="Inheritance",
            start_age=70,
        )
        
        assert one_time.is_active_at_age(70) is True
        assert one_time.is_active_at_age(71) is False
        assert one_time.is_active_at_age(69) is False
        
        # Recurring event
        recurring = LifeEvent(
            id="test",
            event_type=LifeEventType.PART_TIME_WORK,
            name="Part-Time",
            start_age=62,
            end_age=67,
        )
        
        assert recurring.is_active_at_age(61) is False
        assert recurring.is_active_at_age(62) is True
        assert recurring.is_active_at_age(65) is True
        assert recurring.is_active_at_age(67) is True
        assert recurring.is_active_at_age(68) is False
    
    def test_get_annual_impact(self):
        """Test calculating annual impact."""
        event = LifeEvent(
            id="test",
            event_type=LifeEventType.PART_TIME_WORK,
            name="Part-Time",
            start_age=62,
            end_age=67,
            income_change=30_000,
            expense_change=-5_000,
            one_time_amount=10_000,  # Bonus at start
        )
        
        # At start age, includes one-time amount
        impact_62 = event.get_annual_impact(62)
        assert impact_62["income"] == 30_000
        assert impact_62["expense"] == -5_000
        assert impact_62["portfolio_change"] == 10_000
        
        # After start age, no one-time amount
        impact_65 = event.get_annual_impact(65)
        assert impact_65["income"] == 30_000
        assert impact_65["expense"] == -5_000
        assert impact_65["portfolio_change"] == 0
        
        # Outside active range
        impact_70 = event.get_annual_impact(70)
        assert impact_70["income"] == 0
        assert impact_70["expense"] == 0


# ============================================================================
# ScenarioManager Tests
# ============================================================================

class TestScenarioManager:
    """Tests for ScenarioManager."""
    
    def test_create_scenario(self, scenario_manager, sample_scenario):
        """Test creating a scenario."""
        created = scenario_manager.create_scenario(sample_scenario)
        
        assert created.id == sample_scenario.id
        assert created.name == sample_scenario.name
        
        # Verify file was created
        file_path = Path(scenario_manager.storage_dir) / f"{sample_scenario.id}.json"
        assert file_path.exists()
    
    def test_get_scenario(self, scenario_manager, sample_scenario):
        """Test retrieving a scenario."""
        scenario_manager.create_scenario(sample_scenario)
        
        retrieved = scenario_manager.get_scenario(sample_scenario.id)
        
        assert retrieved is not None
        assert retrieved.id == sample_scenario.id
        assert retrieved.name == sample_scenario.name
    
    def test_update_scenario(self, scenario_manager, sample_scenario):
        """Test updating a scenario."""
        scenario_manager.create_scenario(sample_scenario)
        
        sample_scenario.name = "Updated Name"
        sample_scenario.annual_expenses = 90_000
        
        updated = scenario_manager.update_scenario(sample_scenario)
        
        assert updated.name == "Updated Name"
        assert updated.annual_expenses == 90_000
        
        # Verify changes persisted
        retrieved = scenario_manager.get_scenario(sample_scenario.id)
        assert retrieved.name == "Updated Name"
    
    def test_delete_scenario(self, scenario_manager, sample_scenario):
        """Test deleting a scenario."""
        scenario_manager.create_scenario(sample_scenario)
        
        deleted = scenario_manager.delete_scenario(sample_scenario.id)
        
        assert deleted is True
        
        # Verify file was deleted
        file_path = Path(scenario_manager.storage_dir) / f"{sample_scenario.id}.json"
        assert not file_path.exists()
        
        # Verify scenario cannot be retrieved
        retrieved = scenario_manager.get_scenario(sample_scenario.id)
        assert retrieved is None
    
    def test_list_scenarios(self, scenario_manager, sample_scenario):
        """Test listing scenarios."""
        scenario_manager.create_scenario(sample_scenario)
        
        scenario2 = sample_scenario.clone("Second Scenario")
        scenario_manager.create_scenario(scenario2)
        
        scenarios = scenario_manager.list_scenarios()
        
        assert len(scenarios) == 2
        assert any(s["name"] == "Test Scenario" for s in scenarios)
        assert any(s["name"] == "Second Scenario" for s in scenarios)
    
    def test_baseline_scenario(self, scenario_manager, sample_scenario):
        """Test baseline scenario management."""
        sample_scenario.is_baseline = True
        scenario_manager.create_scenario(sample_scenario)
        
        baseline = scenario_manager.get_baseline_scenario()
        
        assert baseline is not None
        assert baseline.id == sample_scenario.id
        assert baseline.is_baseline is True
    
    def test_set_baseline(self, scenario_manager, sample_scenario):
        """Test setting a scenario as baseline."""
        scenario_manager.create_scenario(sample_scenario)
        
        success = scenario_manager.set_baseline(sample_scenario.id)
        
        assert success is True
        
        retrieved = scenario_manager.get_scenario(sample_scenario.id)
        assert retrieved.is_baseline is True
    
    def test_compare_scenarios(self, scenario_manager, sample_scenario):
        """Test comparing scenarios."""
        scenario_manager.create_scenario(sample_scenario)
        
        scenario2 = sample_scenario.clone("Scenario 2")
        scenario2.annual_expenses = 100_000
        scenario_manager.create_scenario(scenario2)
        
        comparison = scenario_manager.compare_scenarios([sample_scenario.id, scenario2.id])
        
        assert len(comparison) == 2
        assert "Scenario" in comparison.columns
    
    def test_encode_decode_url(self, scenario_manager, sample_scenario):
        """Test URL encoding and decoding."""
        scenario_manager.create_scenario(sample_scenario)
        
        scenario2 = sample_scenario.clone("Scenario 2")
        scenario_manager.create_scenario(scenario2)
        
        # Encode
        encoded = scenario_manager.encode_scenario_url([sample_scenario.id, scenario2.id])
        
        assert isinstance(encoded, str)
        assert len(encoded) > 0
        
        # Decode
        decoded = scenario_manager.decode_scenario_url(encoded)
        
        assert len(decoded) == 2
        assert sample_scenario.id in decoded
        assert scenario2.id in decoded


# ============================================================================
# LifeEventTemplates Tests
# ============================================================================

class TestLifeEventTemplates:
    """Tests for life event templates."""
    
    def test_early_retirement_template(self):
        """Test early retirement template."""
        event = LifeEventTemplates.early_retirement(60, expense_reduction=15_000)
        
        assert event.event_type == LifeEventType.EARLY_RETIREMENT
        assert event.start_age == 60
        assert event.expense_change == -15_000
    
    def test_part_time_work_template(self):
        """Test part-time work template."""
        event = LifeEventTemplates.part_time_work(62, 67, annual_income=30_000)
        
        assert event.event_type == LifeEventType.PART_TIME_WORK
        assert event.start_age == 62
        assert event.end_age == 67
        assert event.income_change == 30_000
    
    def test_inheritance_template(self):
        """Test inheritance template."""
        event = LifeEventTemplates.inheritance(70, amount=500_000)
        
        assert event.event_type == LifeEventType.INHERITANCE
        assert event.start_age == 70
        assert event.one_time_amount == 500_000
    
    def test_home_purchase_template(self):
        """Test home purchase template."""
        event = LifeEventTemplates.home_purchase(
            65, purchase_price=500_000, down_payment_pct=0.20
        )
        
        assert event.event_type == LifeEventType.HOME_PURCHASE
        assert event.start_age == 65
        assert event.portfolio_withdrawal == 100_000  # 20% of 500k
    
    def test_custom_template(self):
        """Test custom event template."""
        event = LifeEventTemplates.custom(
            "Custom Event",
            start_age=65,
            income_change=10_000,
        )
        
        assert event.event_type == LifeEventType.CUSTOM
        assert event.name == "Custom Event"
        assert event.income_change == 10_000


# ============================================================================
# Event Utilities Tests
# ============================================================================

class TestEventUtilities:
    """Tests for event utility functions."""
    
    def test_detect_event_conflicts(self):
        """Test conflict detection."""
        event1 = LifeEventTemplates.early_retirement(60)
        event2 = LifeEventTemplates.part_time_work(60, 65)
        
        conflicts = detect_event_conflicts([event1, event2])
        
        # Should detect overlap between early retirement and part-time work
        assert len(conflicts) > 0
    
    def test_calculate_event_timeline(self):
        """Test timeline calculation."""
        event1 = LifeEventTemplates.part_time_work(62, 67, annual_income=30_000)
        event2 = LifeEventTemplates.inheritance(70, amount=500_000)
        
        timeline = calculate_event_timeline([event1, event2], 60, 75)
        
        # Check timeline has entries for all ages
        assert len(timeline) == 16  # Ages 60-75 inclusive
        
        # Check part-time work impact at age 65
        assert timeline[65]["income"] == 30_000
        
        # Check inheritance impact at age 70
        assert timeline[70]["portfolio_change"] == 500_000
    
    def test_get_template_list(self):
        """Test getting template list."""
        templates = get_template_list()
        
        assert len(templates) > 0
        assert all("name" in t for t in templates)
        assert all("type" in t for t in templates)
        assert all("description" in t for t in templates)


# ============================================================================
# Integration Tests
# ============================================================================

class TestIntegration:
    """Integration tests for complete workflows."""
    
    def test_complete_scenario_workflow(self, scenario_manager):
        """Test complete scenario creation and analysis workflow."""
        # Create baseline scenario
        baseline = Scenario(
            name="Baseline",
            description="Current plan",
            is_baseline=True,
            initial_portfolio=1_500_000,
            annual_expenses=80_000,
            retirement_age=65,
            plan_to_age=95,
        )
        scenario_manager.create_scenario(baseline)
        
        # Create early retirement scenario
        early_retire = baseline.clone("Early Retirement")
        early_retire.retirement_age = 60
        early_retire.life_events.append(
            LifeEventTemplates.early_retirement(60, expense_reduction=15_000)
        )
        scenario_manager.create_scenario(early_retire)
        
        # Create part-time scenario
        part_time = baseline.clone("Part-Time Retirement")
        part_time.life_events.append(
            LifeEventTemplates.part_time_work(65, 70, annual_income=30_000)
        )
        scenario_manager.create_scenario(part_time)
        
        # List all scenarios
        scenarios = scenario_manager.list_scenarios()
        assert len(scenarios) == 3
        
        # Compare scenarios
        comparison = scenario_manager.compare_scenarios([
            baseline.id, early_retire.id, part_time.id
        ])
        assert len(comparison) == 3
        
        # Test URL sharing
        url_param = scenario_manager.encode_scenario_url([baseline.id, early_retire.id])
        decoded_ids = scenario_manager.decode_scenario_url(url_param)
        assert len(decoded_ids) == 2
    
    def test_life_event_impact_workflow(self):
        """Test complete life event impact calculation."""
        scenario = Scenario(
            name="Test",
            retirement_age=62,
            plan_to_age=95,
        )
        
        # Add multiple life events
        scenario.life_events.extend([
            LifeEventTemplates.part_time_work(62, 67, annual_income=30_000),
            LifeEventTemplates.inheritance(70, amount=500_000),
            LifeEventTemplates.downsizing(75, home_sale_proceeds=400_000, new_home_cost=250_000),
        ])
        
        # Calculate impacts at different ages
        impact_65 = scenario.get_total_impact_at_age(65)
        assert impact_65["income"] == 30_000  # Part-time work
        
        impact_70 = scenario.get_total_impact_at_age(70)
        assert impact_70["portfolio_change"] == 500_000  # Inheritance
        
        impact_75 = scenario.get_total_impact_at_age(75)
        assert impact_75["portfolio_change"] == 150_000  # Net from downsizing


# ============================================================================
# Run Tests
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])

# Made with Bob
