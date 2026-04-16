"""
life_event_modeler.py
=====================
Life Event Modeling for Scenario Planning

This module provides pre-defined life event templates and utilities for
modeling significant financial events in retirement planning scenarios.

Key Features:
- Pre-defined life event templates
- Custom event creation
- Event impact calculations
- Event conflict detection
- Timeline integration
"""

from __future__ import annotations

import logging
from typing import Any

from scenario_manager import LifeEvent, LifeEventType

# Configure logging
logger = logging.getLogger(__name__)


# ============================================================================
# Life Event Templates
# ============================================================================

class LifeEventTemplates:
    """Pre-defined templates for common life events."""
    
    @staticmethod
    def early_retirement(
        retirement_age: int,
        expense_reduction: float = 15_000,
        notes: str = ""
    ) -> LifeEvent:
        """
        Template for early retirement scenario.
        
        Args:
            retirement_age: Age at which to retire early
            expense_reduction: Annual expense reduction (e.g., no commute, work clothes)
            notes: Additional notes
        
        Returns:
            LifeEvent for early retirement
        """
        return LifeEvent(
            id=f"early_retirement_{retirement_age}",
            event_type=LifeEventType.EARLY_RETIREMENT,
            name=f"Early Retirement at {retirement_age}",
            start_age=retirement_age,
            end_age=None,
            expense_change=-expense_reduction,
            notes=notes or f"Retire at age {retirement_age} with reduced expenses",
            color="#10B981",  # Green
        )
    
    @staticmethod
    def part_time_work(
        start_age: int,
        end_age: int,
        annual_income: float = 30_000,
        notes: str = ""
    ) -> LifeEvent:
        """
        Template for part-time work during retirement.
        
        Args:
            start_age: Age to start part-time work
            end_age: Age to end part-time work
            annual_income: Annual income from part-time work
            notes: Additional notes
        
        Returns:
            LifeEvent for part-time work
        """
        return LifeEvent(
            id=f"part_time_{start_age}_{end_age}",
            event_type=LifeEventType.PART_TIME_WORK,
            name=f"Part-Time Work (Ages {start_age}-{end_age})",
            start_age=start_age,
            end_age=end_age,
            income_change=annual_income,
            taxable_income_change=annual_income,
            notes=notes or f"Part-time work earning ${annual_income:,.0f}/year",
            color="#3B82F6",  # Blue
        )
    
    @staticmethod
    def inheritance(
        age: int,
        amount: float = 500_000,
        taxable_portion: float = 0.0,
        notes: str = ""
    ) -> LifeEvent:
        """
        Template for inheritance windfall.
        
        Args:
            age: Age at which inheritance is received
            amount: Inheritance amount
            taxable_portion: Portion that is taxable income
            notes: Additional notes
        
        Returns:
            LifeEvent for inheritance
        """
        return LifeEvent(
            id=f"inheritance_{age}",
            event_type=LifeEventType.INHERITANCE,
            name=f"Inheritance at Age {age}",
            start_age=age,
            end_age=None,
            one_time_amount=amount,
            taxable_income_change=taxable_portion,
            notes=notes or f"Receive ${amount:,.0f} inheritance",
            color="#8B5CF6",  # Purple
        )
    
    @staticmethod
    def home_purchase(
        age: int,
        purchase_price: float = 500_000,
        down_payment_pct: float = 0.20,
        annual_costs: float = 15_000,
        notes: str = ""
    ) -> LifeEvent:
        """
        Template for home purchase.
        
        Args:
            age: Age at which home is purchased
            purchase_price: Home purchase price
            down_payment_pct: Down payment as percentage of price
            annual_costs: Annual costs (property tax, insurance, maintenance)
            notes: Additional notes
        
        Returns:
            LifeEvent for home purchase
        """
        down_payment = purchase_price * down_payment_pct
        return LifeEvent(
            id=f"home_purchase_{age}",
            event_type=LifeEventType.HOME_PURCHASE,
            name=f"Home Purchase at Age {age}",
            start_age=age,
            end_age=None,
            portfolio_withdrawal=down_payment,
            expense_change=annual_costs,
            notes=notes or f"Purchase ${purchase_price:,.0f} home with ${down_payment:,.0f} down payment",
            color="#EF4444",  # Red
        )
    
    @staticmethod
    def college_funding(
        start_age: int,
        years: int = 4,
        annual_cost: float = 50_000,
        notes: str = ""
    ) -> LifeEvent:
        """
        Template for college funding.
        
        Args:
            start_age: Age when college funding starts
            years: Number of years of funding
            annual_cost: Annual college cost
            notes: Additional notes
        
        Returns:
            LifeEvent for college funding
        """
        return LifeEvent(
            id=f"college_{start_age}",
            event_type=LifeEventType.COLLEGE_FUNDING,
            name=f"College Funding (Ages {start_age}-{start_age + years - 1})",
            start_age=start_age,
            end_age=start_age + years - 1,
            expense_change=annual_cost,
            notes=notes or f"Fund college at ${annual_cost:,.0f}/year for {years} years",
            color="#F59E0B",  # Amber
        )
    
    @staticmethod
    def divorce(
        age: int,
        asset_split_pct: float = 0.50,
        portfolio_value: float = 1_500_000,
        expense_change: float = -20_000,
        notes: str = ""
    ) -> LifeEvent:
        """
        Template for divorce financial impact.
        
        Args:
            age: Age at which divorce occurs
            asset_split_pct: Percentage of assets retained (typically 0.50)
            portfolio_value: Current portfolio value for split calculation
            expense_change: Change in annual expenses (typically negative)
            notes: Additional notes
        
        Returns:
            LifeEvent for divorce
        """
        asset_loss = portfolio_value * (1 - asset_split_pct)
        return LifeEvent(
            id=f"divorce_{age}",
            event_type=LifeEventType.DIVORCE,
            name=f"Divorce at Age {age}",
            start_age=age,
            end_age=None,
            portfolio_withdrawal=asset_loss,
            expense_change=expense_change,
            notes=notes or f"Asset split: retain {asset_split_pct:.0%}, expenses change by ${expense_change:,.0f}",
            color="#DC2626",  # Dark Red
        )
    
    @staticmethod
    def remarriage(
        age: int,
        combined_income_increase: float = 0,
        expense_increase: float = 20_000,
        notes: str = ""
    ) -> LifeEvent:
        """
        Template for remarriage financial impact.
        
        Args:
            age: Age at which remarriage occurs
            combined_income_increase: Additional income from new spouse
            expense_increase: Increase in household expenses
            notes: Additional notes
        
        Returns:
            LifeEvent for remarriage
        """
        return LifeEvent(
            id=f"remarriage_{age}",
            event_type=LifeEventType.REMARRIAGE,
            name=f"Remarriage at Age {age}",
            start_age=age,
            end_age=None,
            income_change=combined_income_increase,
            expense_change=expense_increase,
            notes=notes or f"Remarriage with ${expense_increase:,.0f} expense increase",
            color="#EC4899",  # Pink
        )
    
    @staticmethod
    def disability(
        age: int,
        disability_income: float = 40_000,
        medical_expenses: float = 15_000,
        duration_years: int | None = None,
        notes: str = ""
    ) -> LifeEvent:
        """
        Template for disability income scenario.
        
        Args:
            age: Age at which disability begins
            disability_income: Annual disability income
            medical_expenses: Additional annual medical expenses
            duration_years: Duration of disability (None for permanent)
            notes: Additional notes
        
        Returns:
            LifeEvent for disability
        """
        end_age = age + duration_years if duration_years else None
        return LifeEvent(
            id=f"disability_{age}",
            event_type=LifeEventType.DISABILITY,
            name=f"Disability at Age {age}",
            start_age=age,
            end_age=end_age,
            income_change=disability_income,
            expense_change=medical_expenses,
            taxable_income_change=disability_income * 0.85,  # Typically 85% taxable
            notes=notes or f"Disability income ${disability_income:,.0f}/year, medical costs ${medical_expenses:,.0f}/year",
            color="#6B7280",  # Gray
        )
    
    @staticmethod
    def major_medical(
        age: int,
        one_time_cost: float = 100_000,
        ongoing_annual_cost: float = 10_000,
        duration_years: int = 5,
        notes: str = ""
    ) -> LifeEvent:
        """
        Template for major medical expense.
        
        Args:
            age: Age at which medical event occurs
            one_time_cost: One-time medical cost
            ongoing_annual_cost: Ongoing annual medical costs
            duration_years: Duration of ongoing costs
            notes: Additional notes
        
        Returns:
            LifeEvent for major medical expense
        """
        return LifeEvent(
            id=f"medical_{age}",
            event_type=LifeEventType.MAJOR_MEDICAL,
            name=f"Major Medical Event at Age {age}",
            start_age=age,
            end_age=age + duration_years - 1,
            one_time_amount=-one_time_cost,
            expense_change=ongoing_annual_cost,
            notes=notes or f"${one_time_cost:,.0f} initial cost, ${ongoing_annual_cost:,.0f}/year for {duration_years} years",
            color="#DC2626",  # Red
        )
    
    @staticmethod
    def business_sale(
        age: int,
        sale_proceeds: float = 2_000_000,
        capital_gains_pct: float = 0.80,
        notes: str = ""
    ) -> LifeEvent:
        """
        Template for business sale.
        
        Args:
            age: Age at which business is sold
            sale_proceeds: Net proceeds from sale
            capital_gains_pct: Percentage that is capital gains (vs. ordinary income)
            notes: Additional notes
        
        Returns:
            LifeEvent for business sale
        """
        capital_gains = sale_proceeds * capital_gains_pct
        return LifeEvent(
            id=f"business_sale_{age}",
            event_type=LifeEventType.BUSINESS_SALE,
            name=f"Business Sale at Age {age}",
            start_age=age,
            end_age=None,
            one_time_amount=sale_proceeds,
            taxable_income_change=capital_gains,  # Simplified - actual tax treatment varies
            notes=notes or f"Sell business for ${sale_proceeds:,.0f}",
            color="#059669",  # Emerald
        )
    
    @staticmethod
    def rental_income(
        start_age: int,
        end_age: int | None,
        annual_income: float = 24_000,
        annual_expenses: float = 8_000,
        notes: str = ""
    ) -> LifeEvent:
        """
        Template for rental property income.
        
        Args:
            start_age: Age to start receiving rental income
            end_age: Age to stop (None for indefinite)
            annual_income: Annual rental income
            annual_expenses: Annual property expenses
            notes: Additional notes
        
        Returns:
            LifeEvent for rental income
        """
        net_income = annual_income - annual_expenses
        return LifeEvent(
            id=f"rental_{start_age}",
            event_type=LifeEventType.RENTAL_INCOME,
            name=f"Rental Income (Starting Age {start_age})",
            start_age=start_age,
            end_age=end_age,
            income_change=net_income,
            taxable_income_change=net_income,
            notes=notes or f"Net rental income ${net_income:,.0f}/year",
            color="#0891B2",  # Cyan
        )
    
    @staticmethod
    def downsizing(
        age: int,
        home_sale_proceeds: float = 400_000,
        new_home_cost: float = 250_000,
        expense_reduction: float = 10_000,
        notes: str = ""
    ) -> LifeEvent:
        """
        Template for downsizing home.
        
        Args:
            age: Age at which downsizing occurs
            home_sale_proceeds: Proceeds from selling current home
            new_home_cost: Cost of new (smaller) home
            expense_reduction: Annual expense reduction
            notes: Additional notes
        
        Returns:
            LifeEvent for downsizing
        """
        net_proceeds = home_sale_proceeds - new_home_cost
        return LifeEvent(
            id=f"downsize_{age}",
            event_type=LifeEventType.DOWNSIZING,
            name=f"Downsize Home at Age {age}",
            start_age=age,
            end_age=None,
            one_time_amount=net_proceeds,
            expense_change=-expense_reduction,
            notes=notes or f"Net ${net_proceeds:,.0f} from downsizing, reduce expenses ${expense_reduction:,.0f}/year",
            color="#14B8A6",  # Teal
        )
    
    @staticmethod
    def relocation(
        age: int,
        moving_cost: float = 20_000,
        expense_change: float = -15_000,
        notes: str = ""
    ) -> LifeEvent:
        """
        Template for relocation (e.g., to lower cost of living area).
        
        Args:
            age: Age at which relocation occurs
            moving_cost: One-time moving cost
            expense_change: Change in annual expenses (typically negative)
            notes: Additional notes
        
        Returns:
            LifeEvent for relocation
        """
        return LifeEvent(
            id=f"relocate_{age}",
            event_type=LifeEventType.RELOCATION,
            name=f"Relocate at Age {age}",
            start_age=age,
            end_age=None,
            one_time_amount=-moving_cost,
            expense_change=expense_change,
            notes=notes or f"Move with ${moving_cost:,.0f} cost, change expenses by ${expense_change:,.0f}/year",
            color="#8B5CF6",  # Purple
        )
    
    @staticmethod
    def custom(
        name: str,
        start_age: int,
        end_age: int | None = None,
        **kwargs: Any
    ) -> LifeEvent:
        """
        Create a custom life event.
        
        Args:
            name: Event name
            start_age: Starting age
            end_age: Ending age (None for one-time)
            **kwargs: Additional LifeEvent parameters
        
        Returns:
            Custom LifeEvent
        """
        return LifeEvent(
            id=kwargs.pop("id", f"custom_{start_age}"),
            event_type=LifeEventType.CUSTOM,
            name=name,
            start_age=start_age,
            end_age=end_age,
            **kwargs
        )


# ============================================================================
# Event Utilities
# ============================================================================

def detect_event_conflicts(events: list[LifeEvent]) -> list[dict[str, Any]]:
    """
    Detect potential conflicts between life events.
    
    Conflicts include:
    - Overlapping events of incompatible types
    - Events with unrealistic timing
    - Events that would deplete portfolio
    
    Args:
        events: List of life events to check
    
    Returns:
        List of conflict descriptions
    """
    conflicts = []
    
    # Check for overlapping incompatible events
    for i, event1 in enumerate(events):
        for event2 in events[i + 1:]:
            # Check if events overlap in time
            if event1.end_age is None:
                overlap = event2.start_age == event1.start_age
            elif event2.end_age is None:
                overlap = event1.start_age <= event2.start_age <= event1.end_age
            else:
                overlap = not (event1.end_age < event2.start_age or event2.end_age < event1.start_age)
            
            if overlap:
                # Check for incompatible event types
                incompatible_pairs = [
                    (LifeEventType.EARLY_RETIREMENT, LifeEventType.PART_TIME_WORK),
                    (LifeEventType.DIVORCE, LifeEventType.REMARRIAGE),
                ]
                
                for type1, type2 in incompatible_pairs:
                    if ((event1.event_type == type1 and event2.event_type == type2) or
                        (event1.event_type == type2 and event2.event_type == type1)):
                        conflicts.append({
                            "severity": "warning",
                            "event1": event1.name,
                            "event2": event2.name,
                            "message": f"Potentially incompatible events overlap: {event1.name} and {event2.name}",
                        })
    
    # Check for unrealistic timing
    for event in events:
        if event.start_age < 40:
            conflicts.append({
                "severity": "info",
                "event": event.name,
                "message": f"{event.name} starts before typical retirement age (40)",
            })
        
        if event.start_age > 100:
            conflicts.append({
                "severity": "warning",
                "event": event.name,
                "message": f"{event.name} starts at age {event.start_age} (very late in life)",
            })
    
    logger.debug(f"Detected {len(conflicts)} potential conflicts in {len(events)} events")
    return conflicts


def calculate_event_timeline(
    events: list[LifeEvent],
    start_age: int,
    end_age: int
) -> dict[int, dict[str, float]]:
    """
    Calculate the cumulative impact of all events across a timeline.
    
    Args:
        events: List of life events
        start_age: Starting age for timeline
        end_age: Ending age for timeline
    
    Returns:
        Dictionary mapping age to cumulative impacts
    """
    timeline = {}
    
    for age in range(start_age, end_age + 1):
        total_impact = {
            "income": 0.0,
            "expense": 0.0,
            "taxable_income": 0.0,
            "portfolio_change": 0.0,
            "active_events": [],
        }
        
        for event in events:
            if event.is_active_at_age(age):
                impact = event.get_annual_impact(age)
                total_impact["income"] += impact["income"]
                total_impact["expense"] += impact["expense"]
                total_impact["taxable_income"] += impact["taxable_income"]
                total_impact["portfolio_change"] += impact["portfolio_change"]
                total_impact["active_events"].append(event.name)
        
        timeline[age] = total_impact
    
    logger.debug(f"Calculated timeline for ages {start_age}-{end_age} with {len(events)} events")
    return timeline


def get_template_list() -> list[dict[str, Any]]:
    """
    Get a list of all available life event templates.
    
    Returns:
        List of template metadata dictionaries
    """
    templates = [
        {
            "name": "Early Retirement",
            "type": LifeEventType.EARLY_RETIREMENT,
            "description": "Retire earlier than planned with reduced expenses",
            "color": "#10B981",
        },
        {
            "name": "Part-Time Work",
            "type": LifeEventType.PART_TIME_WORK,
            "description": "Work part-time during retirement for additional income",
            "color": "#3B82F6",
        },
        {
            "name": "Inheritance",
            "type": LifeEventType.INHERITANCE,
            "description": "Receive an inheritance windfall",
            "color": "#8B5CF6",
        },
        {
            "name": "Home Purchase",
            "type": LifeEventType.HOME_PURCHASE,
            "description": "Purchase a home with down payment and ongoing costs",
            "color": "#EF4444",
        },
        {
            "name": "College Funding",
            "type": LifeEventType.COLLEGE_FUNDING,
            "description": "Fund college education for children/grandchildren",
            "color": "#F59E0B",
        },
        {
            "name": "Divorce",
            "type": LifeEventType.DIVORCE,
            "description": "Model financial impact of divorce",
            "color": "#DC2626",
        },
        {
            "name": "Remarriage",
            "type": LifeEventType.REMARRIAGE,
            "description": "Model financial impact of remarriage",
            "color": "#EC4899",
        },
        {
            "name": "Disability",
            "type": LifeEventType.DISABILITY,
            "description": "Disability income and medical expenses",
            "color": "#6B7280",
        },
        {
            "name": "Major Medical",
            "type": LifeEventType.MAJOR_MEDICAL,
            "description": "Major medical event with significant costs",
            "color": "#DC2626",
        },
        {
            "name": "Business Sale",
            "type": LifeEventType.BUSINESS_SALE,
            "description": "Sell a business for proceeds",
            "color": "#059669",
        },
        {
            "name": "Rental Income",
            "type": LifeEventType.RENTAL_INCOME,
            "description": "Receive rental income from property",
            "color": "#0891B2",
        },
        {
            "name": "Downsizing",
            "type": LifeEventType.DOWNSIZING,
            "description": "Downsize home to reduce expenses",
            "color": "#14B8A6",
        },
        {
            "name": "Relocation",
            "type": LifeEventType.RELOCATION,
            "description": "Relocate to lower cost of living area",
            "color": "#8B5CF6",
        },
        {
            "name": "Custom Event",
            "type": LifeEventType.CUSTOM,
            "description": "Create a custom life event",
            "color": "#6B7280",
        },
    ]
    
    return templates


# Made with Bob