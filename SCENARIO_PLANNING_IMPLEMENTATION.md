# Scenario Planning & What-If Analysis Implementation Plan

## Overview
This document outlines the implementation of comprehensive scenario planning and what-if analysis capabilities for the retirement planning application. This feature enables users to create, compare, and analyze multiple retirement scenarios side-by-side with real-time parameter adjustments.

## Feature Priority: Low (Enhances Planning Flexibility)

## Architecture Overview

### Core Components

1. **Scenario Manager** (`scenario_manager.py`)
   - Scenario data model and storage
   - CRUD operations for scenarios
   - Scenario comparison logic
   - URL parameter encoding/decoding

2. **Life Event Modeler** (`life_event_modeler.py`)
   - Pre-defined life event templates
   - Custom event creation
   - Event impact calculations
   - Timeline integration

3. **Scenario Comparison UI** (`pages/9_scenario_planning.py`)
   - Side-by-side scenario comparison (up to 4)
   - Real-time parameter adjustment
   - Interactive visualizations
   - Scenario management interface

4. **Scenario Storage** (`data/scenarios/`)
   - JSON-based scenario persistence
   - User scenario library
   - Scenario templates

## Data Model

### Scenario Structure
```python
@dataclass
class Scenario:
    """Represents a complete retirement planning scenario."""
    id: str  # UUID
    name: str
    description: str
    created_at: datetime
    modified_at: datetime
    is_baseline: bool
    
    # Financial Parameters
    initial_portfolio: float
    annual_expenses: float
    inflation_rate: float
    portfolio_allocation: dict[str, float]
    
    # Personal Parameters
    person1_age: int
    person2_age: int | None
    retirement_age: int
    plan_to_age: int
    
    # Income Sources
    social_security: SocialSecurityConfig
    pension: PensionConfig | None
    part_time_income: PartTimeIncomeConfig | None
    
    # Life Events
    life_events: list[LifeEvent]
    
    # Tax Strategy
    roth_conversion_strategy: str
    tax_harvesting_enabled: bool
    
    # Results (cached)
    last_run_results: ScenarioResults | None
```

### Life Event Structure
```python
@dataclass
class LifeEvent:
    """Represents a significant life event affecting finances."""
    id: str
    event_type: LifeEventType
    name: str
    start_age: int
    end_age: int | None  # None for one-time events
    
    # Financial Impact
    income_change: float = 0.0  # Annual income change
    expense_change: float = 0.0  # Annual expense change
    one_time_amount: float = 0.0  # One-time windfall/expense
    
    # Tax Impact
    taxable_income_change: float = 0.0
    
    # Portfolio Impact
    portfolio_withdrawal: float = 0.0
    portfolio_contribution: float = 0.0
    
    # Metadata
    notes: str = ""
    color: str = "#3B82F6"  # For visualization

class LifeEventType(Enum):
    """Pre-defined life event types."""
    EARLY_RETIREMENT = "early_retirement"
    PART_TIME_WORK = "part_time_work"
    INHERITANCE = "inheritance"
    HOME_PURCHASE = "home_purchase"
    COLLEGE_FUNDING = "college_funding"
    DIVORCE = "divorce"
    REMARRIAGE = "remarriage"
    DISABILITY = "disability"
    MAJOR_MEDICAL = "major_medical"
    BUSINESS_SALE = "business_sale"
    CUSTOM = "custom"
```

## Implementation Phases

### Phase 1: Core Scenario Management ✅ (Week 1)

#### 1.1 Scenario Manager Module
- [x] Create `scenario_manager.py`
- [x] Implement Scenario data class
- [x] Implement ScenarioManager class
  - [x] Create scenario
  - [x] Update scenario
  - [x] Delete scenario
  - [x] List scenarios
  - [x] Load scenario
  - [x] Clone scenario
- [x] Implement JSON persistence
- [x] Add scenario validation

#### 1.2 Life Event Modeler
- [x] Create `life_event_modeler.py`
- [x] Implement LifeEvent data class
- [x] Create life event templates
- [x] Implement event impact calculator
- [x] Add event timeline integration

### Phase 2: Scenario Comparison UI (Week 2)

#### 2.1 Main Scenario Planning Page
- [ ] Create `pages/9_scenario_planning.py`
- [ ] Implement scenario selector (up to 4)
- [ ] Add scenario creation wizard
- [ ] Implement parameter adjustment panel
- [ ] Add real-time recalculation

#### 2.2 Comparison Visualizations
- [ ] Side-by-side metrics comparison
- [ ] Portfolio trajectory comparison chart
- [ ] Success probability comparison
- [ ] Tax impact comparison
- [ ] Cash flow comparison timeline

#### 2.3 Life Event Integration
- [ ] Life event timeline editor
- [ ] Event impact visualization
- [ ] Event library browser
- [ ] Custom event creator

### Phase 3: Advanced Features (Week 3)

#### 3.1 Scenario Sharing
- [ ] URL parameter encoding
- [ ] URL parameter decoding
- [ ] Share link generation
- [ ] Import from URL

#### 3.2 Scenario Templates
- [ ] Pre-built scenario templates
  - [ ] Conservative retirement
  - [ ] Aggressive early retirement
  - [ ] Part-time phased retirement
  - [ ] Inheritance windfall
  - [ ] Major expense planning
- [ ] Template customization
- [ ] Template library

#### 3.3 Sensitivity Analysis
- [ ] Parameter sensitivity charts
- [ ] Monte Carlo integration
- [ ] Risk factor identification
- [ ] Optimization suggestions

### Phase 4: Testing & Documentation (Week 4)

#### 4.1 Testing
- [ ] Unit tests for scenario manager
- [ ] Unit tests for life event modeler
- [ ] Integration tests for UI
- [ ] End-to-end scenario workflows
- [ ] Performance testing (4 scenarios)

#### 4.2 Documentation
- [ ] User guide for scenario planning
- [ ] Life event modeling guide
- [ ] API documentation
- [ ] Example scenarios

## Technical Specifications

### Scenario Storage Format (JSON)
```json
{
  "id": "uuid-here",
  "name": "Early Retirement at 55",
  "description": "Retire 7 years early with reduced expenses",
  "created_at": "2026-04-08T14:00:00Z",
  "modified_at": "2026-04-08T14:00:00Z",
  "is_baseline": false,
  "financial": {
    "initial_portfolio": 1500000,
    "annual_expenses": 60000,
    "inflation_rate": 0.029,
    "portfolio_allocation": {
      "stocks": 0.70,
      "bonds": 0.25,
      "cash": 0.05
    }
  },
  "personal": {
    "person1_age": 55,
    "person2_age": 53,
    "retirement_age": 55,
    "plan_to_age": 95
  },
  "income_sources": {
    "social_security": {
      "person1_amount": 36000,
      "person1_start_age": 70,
      "person2_amount": 24000,
      "person2_start_age": 67
    },
    "pension": null,
    "part_time_income": {
      "annual_amount": 20000,
      "start_age": 55,
      "end_age": 62,
      "growth_rate": 0.02
    }
  },
  "life_events": [
    {
      "id": "event-1",
      "event_type": "early_retirement",
      "name": "Early Retirement",
      "start_age": 55,
      "end_age": null,
      "expense_change": -15000,
      "notes": "Reduced expenses due to no commute"
    },
    {
      "id": "event-2",
      "event_type": "part_time_work",
      "name": "Consulting Work",
      "start_age": 55,
      "end_age": 62,
      "income_change": 20000,
      "notes": "Part-time consulting 2 days/week"
    }
  ],
  "tax_strategy": {
    "roth_conversion_strategy": "fill_bracket",
    "tax_harvesting_enabled": true
  }
}
```

### URL Parameter Format
```
?scenarios=base64_encoded_json
```

Example:
```
https://app.example.com/scenario-planning?scenarios=eyJzY2VuYXJpb3MiOlt7ImlkIjoiYmFzZWxpbmUi...
```

## UI/UX Design

### Layout Structure
```
┌─────────────────────────────────────────────────────────────┐
│ 🎯 Scenario Planning & What-If Analysis                     │
├─────────────────────────────────────────────────────────────┤
│ [Scenario 1 ▼] [Scenario 2 ▼] [Scenario 3 ▼] [Scenario 4 ▼]│
│ [+ New] [Clone] [Edit] [Delete] [Share Link] [Import]      │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│ ┌──────────────┬──────────────┬──────────────┬────────────┐│
│ │ Scenario 1   │ Scenario 2   │ Scenario 3   │ Scenario 4 ││
│ ├──────────────┼──────────────┼──────────────┼────────────┤│
│ │ Success: 92% │ Success: 85% │ Success: 78% │ Success: 95││
│ │ Final: $2.1M │ Final: $1.2M │ Final: $800K │ Final: $3M ││
│ │ Age: 95      │ Age: 95      │ Age: 90      │ Age: 100   ││
│ └──────────────┴──────────────┴──────────────┴────────────┘│
│                                                              │
│ 📊 Portfolio Trajectory Comparison                          │
│ [Interactive Chart with 4 lines]                            │
│                                                              │
│ 📅 Life Events Timeline                                     │
│ [Timeline visualization with events]                        │
│                                                              │
│ 💰 Cash Flow Comparison                                     │
│ [Stacked area chart]                                        │
│                                                              │
│ 📈 Key Metrics Comparison                                   │
│ [Table with side-by-side metrics]                           │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### Scenario Editor Modal
```
┌─────────────────────────────────────────────┐
│ ✏️ Edit Scenario: "Early Retirement"        │
├─────────────────────────────────────────────┤
│ Tabs: [Basic] [Income] [Events] [Strategy] │
│                                             │
│ Basic Information:                          │
│ Name: [Early Retirement at 55_________]     │
│ Description: [________________________]     │
│                                             │
│ Financial Parameters:                       │
│ Portfolio: [$1,500,000]                     │
│ Expenses: [$60,000]                         │
│ Inflation: [2.9%]                           │
│                                             │
│ Personal:                                   │
│ Retirement Age: [55]                        │
│ Plan To Age: [95]                           │
│                                             │
│ [Cancel] [Save] [Save & Run]                │
└─────────────────────────────────────────────┘
```

## Integration Points

### 1. Monte Carlo Integration
- Run Monte Carlo for each scenario
- Compare success probabilities
- Visualize outcome distributions
- Stress test scenarios

### 2. Strategy Module Integration
- Apply withdrawal strategies to scenarios
- Compare strategy effectiveness
- Optimize strategy per scenario

### 3. Tax Planning Integration
- Calculate tax impact per scenario
- Compare Roth conversion strategies
- Optimize tax efficiency

### 4. Portfolio Integration
- Use current portfolio as baseline
- Model portfolio changes
- Track allocation drift

## Performance Considerations

### Optimization Strategies
1. **Lazy Loading**: Only calculate results when scenario is viewed
2. **Caching**: Cache scenario results until parameters change
3. **Parallel Processing**: Run multiple scenarios in parallel
4. **Progressive Enhancement**: Show basic comparison first, detailed analysis on demand
5. **Debouncing**: Delay recalculation during rapid parameter changes

### Performance Targets
- Scenario creation: < 100ms
- Parameter update: < 50ms
- Comparison view load: < 500ms
- 4-scenario Monte Carlo: < 10 seconds
- URL encoding/decoding: < 100ms

## Security & Privacy

### Data Protection
- Scenarios stored locally only
- No server-side storage
- URL parameters use base64 encoding (not encryption)
- Warning when sharing URLs with financial data

### Validation
- Input validation for all parameters
- Scenario integrity checks
- Life event conflict detection
- Portfolio balance validation

## User Workflows

### Workflow 1: Compare Retirement Ages
1. User loads baseline scenario (current plan)
2. Clones baseline to create "Early Retirement" scenario
3. Adjusts retirement age to 60 (from 65)
4. Clones baseline to create "Late Retirement" scenario
5. Adjusts retirement age to 70
6. Views side-by-side comparison
7. Analyzes success probability and final portfolio values
8. Makes decision based on comparison

### Workflow 2: Model Inheritance Windfall
1. User creates new scenario "With Inheritance"
2. Adds life event: Inheritance at age 70
3. Sets one-time amount: $500,000
4. Compares with baseline
5. Sees improved success probability
6. Explores different uses (pay off mortgage, increase spending)

### Workflow 3: Plan for Part-Time Retirement
1. User creates "Phased Retirement" scenario
2. Adds part-time work event: ages 62-67
3. Sets annual income: $30,000
4. Reduces expenses during part-time period
5. Compares with full retirement at 62
6. Sees extended portfolio longevity

## Success Metrics

### User Engagement
- Number of scenarios created per user
- Scenario comparison frequency
- Life events added per scenario
- Scenario sharing rate

### Feature Adoption
- % of users creating multiple scenarios
- Average scenarios per user
- Most popular life event types
- Most compared parameters

### User Satisfaction
- Feature usage retention
- User feedback ratings
- Support ticket reduction
- Feature request alignment

## Future Enhancements (Post-MVP)

### Advanced Features
1. **Scenario Optimization**
   - AI-powered scenario suggestions
   - Automatic parameter optimization
   - Goal-based scenario generation

2. **Collaborative Planning**
   - Share scenarios with financial advisor
   - Multi-user scenario editing
   - Advisor comments and recommendations

3. **Advanced Life Events**
   - Healthcare cost modeling
   - Long-term care scenarios
   - Estate planning integration
   - Business succession planning

4. **Enhanced Visualizations**
   - 3D scenario space exploration
   - Interactive sensitivity analysis
   - Animated scenario transitions
   - VR/AR scenario visualization

5. **Machine Learning**
   - Predict likely scenarios based on user profile
   - Learn from user preferences
   - Suggest optimal parameter ranges
   - Anomaly detection in scenarios

## Dependencies

### Required Packages
- `streamlit` >= 1.28.0 (UI framework)
- `pandas` >= 2.0.0 (data manipulation)
- `plotly` >= 5.17.0 (visualizations)
- `pydantic` >= 2.0.0 (data validation)
- `uuid` (scenario IDs)
- `base64` (URL encoding)
- `json` (persistence)

### Internal Dependencies
- `monte_carlo.py` (simulation engine)
- `calculations.py` (tax calculations)
- `config.py` (configuration management)
- `load_data.py` (data loading)

## Testing Strategy

### Unit Tests
- Scenario CRUD operations
- Life event calculations
- URL encoding/decoding
- Data validation
- Event conflict detection

### Integration Tests
- Scenario comparison workflow
- Monte Carlo integration
- Strategy application
- Tax calculation integration

### UI Tests
- Scenario creation flow
- Parameter adjustment
- Comparison view rendering
- Life event editor

### Performance Tests
- 4-scenario comparison load time
- Monte Carlo execution time
- Large scenario library handling
- URL parameter size limits

## Documentation Deliverables

1. **User Guide**: `SCENARIO_PLANNING_USER_GUIDE.md`
2. **API Documentation**: `SCENARIO_PLANNING_API.md`
3. **Life Event Guide**: `LIFE_EVENT_MODELING_GUIDE.md`
4. **Example Scenarios**: `SCENARIO_EXAMPLES.md`
5. **Developer Guide**: `SCENARIO_PLANNING_DEVELOPER_GUIDE.md`

## Timeline

### Week 1: Core Infrastructure
- Days 1-2: Scenario manager implementation
- Days 3-4: Life event modeler implementation
- Day 5: Testing and refinement

### Week 2: UI Development
- Days 1-2: Main scenario planning page
- Days 3-4: Comparison visualizations
- Day 5: Life event integration

### Week 3: Advanced Features
- Days 1-2: URL sharing implementation
- Days 3-4: Scenario templates
- Day 5: Sensitivity analysis

### Week 4: Polish & Documentation
- Days 1-2: Comprehensive testing
- Days 3-4: Documentation
- Day 5: Final review and deployment

## Conclusion

This implementation plan provides a comprehensive roadmap for building a robust scenario planning and what-if analysis feature. The phased approach ensures incremental delivery of value while maintaining code quality and user experience standards.

The feature will significantly enhance the retirement planning application by enabling users to explore multiple futures, understand trade-offs, and make more informed decisions about their retirement strategy.

---

**Status**: Ready for Implementation  
**Priority**: Low (Enhances Planning Flexibility)  
**Estimated Effort**: 4 weeks  
**Dependencies**: Monte Carlo module, Tax calculations, Configuration system  
**Risk Level**: Low (isolated feature, no breaking changes)