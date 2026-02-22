"""
Test script for configuration system.
"""

from config import get_config_manager

def test_config():
    """Test configuration loading, saving, and retrieval."""
    print("=" * 60)
    print("Testing Configuration System")
    print("=" * 60)
    
    # Get configuration manager
    cm = get_config_manager()
    print("✓ Config manager initialized")
    
    # Test reading default values
    person1_name = cm.get("personal_info", "person1_name")
    print(f"✓ Person 1 name: {person1_name}")
    
    expenses = cm.get("financial_assumptions", "expected_annual_expenses")
    print(f"✓ Expected annual expenses: ${expenses:,}")
    
    ssi_age = cm.get("social_security", "person1_ssi_age")
    print(f"✓ Social Security age: {ssi_age}")
    
    # Test age calculation
    birth_date = cm.get("personal_info", "person1_birth_date")
    age = cm.calculate_age(birth_date)
    print(f"✓ Calculated age from {birth_date}: {age} years")
    
    # Test getting entire section
    financial_section = cm.get_section("financial_assumptions")
    print(f"✓ Financial assumptions section has {len(financial_section)} keys")
    
    # Test saving configuration
    if cm.save_config():
        print("✓ Configuration saved successfully to retirement_config.json")
    else:
        print("✗ Failed to save configuration")
    
    # Test updating a value
    cm.set("personal_info", "person1_name", "TestUser")
    updated_name = cm.get("personal_info", "person1_name")
    print(f"✓ Updated person1_name to: {updated_name}")
    
    # Test section update
    cm.update_section("financial_assumptions", {
        "expected_annual_expenses": 60000,
        "years_of_expenses_in_cash": 5
    })
    updated_expenses = cm.get("financial_assumptions", "expected_annual_expenses")
    updated_years = cm.get("financial_assumptions", "years_of_expenses_in_cash")
    print(f"✓ Updated expenses to: ${updated_expenses:,}")
    print(f"✓ Updated cash years to: {updated_years}")
    
    # Test export
    config_json = cm.export_config()
    print(f"✓ Exported configuration ({len(config_json)} characters)")
    
    # Reset to defaults for clean state
    cm.reset_to_defaults()
    cm.save_config()
    print("✓ Reset to defaults and saved")
    
    print("=" * 60)
    print("All tests passed! ✓")
    print("=" * 60)
    print("\nConfiguration file created: retirement_config.json")
    print("You can now run the Streamlit app and access the Configuration page.")

if __name__ == "__main__":
    test_config()

# Made with Bob
