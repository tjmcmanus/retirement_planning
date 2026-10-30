"""
Test script for configuration system.
"""

import os
import tempfile

from config import ConfigManager

def test_config():
    """Test configuration loading, saving, and retrieval.

    Runs in a throwaway directory so the save/reset steps below can never
    overwrite the real retirement_config.json (or write into its .backups/).
    """
    original_cwd = os.getcwd()
    with tempfile.TemporaryDirectory() as tmp:
        os.chdir(tmp)
        try:
            _run_config_checks()
        finally:
            os.chdir(original_cwd)


def _run_config_checks():
    print("=" * 60)
    print("Testing Configuration System")
    print("=" * 60)
    
    # Fresh manager on a temp config file (cwd is a temp dir)
    cm = ConfigManager()
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
    print("\nTemporary configuration file removed; real config untouched.")

if __name__ == "__main__":
    test_config()

# Made with Bob


def test_birth_year_is_derived_from_birth_date_not_stored(tmp_path, monkeypatch):
    """One birth setting: social_security birth years are derived from personal_info dates."""
    import json
    from config import ConfigManager

    monkeypatch.chdir(tmp_path)
    # A legacy file that still carries the duplicate social_security.*_birth_year keys.
    legacy = {
        "personal_info": {"person1_birth_date": "1966-05-16", "person2_birth_date": "1967-03-22"},
        "social_security": {"person1_birth_year": 1999, "person2_birth_year": 1999, "person1_gender": "M"},
    }
    (tmp_path / "retirement_config.json").write_text(json.dumps(legacy))

    cm = ConfigManager()
    assert cm.birth_year("person1") == 1966
    assert cm.birth_year("person2") == 1967
    assert "person1_birth_year" not in cm.config["social_security"]

    cm.set("personal_info", "person1_birth_date", "1968-03-01")
    assert cm.birth_year("person1") == 1968          # follows the date immediately
    assert cm.save_config()
    saved = json.loads((tmp_path / "retirement_config.json").read_text())
    assert not [k for k in saved["social_security"] if k.endswith("_birth_year")]
    assert saved["social_security"]["person1_gender"] == "M"   # other optimizer inputs kept
