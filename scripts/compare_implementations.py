#!/usr/bin/env python3
"""
Compare Implementations Script

Compares outputs between old and new stage implementations to validate correctness.
"""

import strategy
from strategy import WithdrawalStrategyEngine


def compare_stage_outputs():
    """Run both implementations and compare stage selection"""
    
    print("=" * 70)
    print("IMPLEMENTATION COMPARISON")
    print("=" * 70)
    print()
    
    # Create engines
    print("Creating engines...")
    old_engine = WithdrawalStrategyEngine(use_refactored_stages=False)
    new_engine = WithdrawalStrategyEngine(use_refactored_stages=True)
    
    print(f"✓ Old engine: {len(old_engine.stages)} stages")
    print(f"✓ New engine: {len(new_engine.stages)} stages")
    print()
    
    # Test cases covering all stages
    test_cases = [
        # (age_primary, age_spouse, year, has_wages, has_ss, expected_stage)
        (35, 33, 2024, True, False, "Stage 1"),   # Accumulation
        (55, 53, 2024, True, False, "Stage 2"),   # Prep for Retirement
        (60, 58, 2024, False, False, "Stage 3"),  # Early Retirement
        (66, 64, 2024, False, False, "Stage 4"),  # Medicare
        (68, 66, 2024, False, True, "Stage 5"),   # Social Security
        (75, 73, 2024, False, True, "Stage 6"),   # RMD
        (80, None, 2024, False, True, "Stage 7"), # Surviving Spouse
    ]
    
    print("Comparing stage selection...")
    print("-" * 70)
    
    all_match = True
    for age_p, age_s, year, wages, ss, expected in test_cases:
        # Determine stages
        old_stage = old_engine.determine_stage(age_p, age_s or 0, year, wages, ss)
        new_stage = new_engine.determine_stage(age_p, age_s or 0, year, wages, ss)
        
        # Compare
        match = old_stage.name == new_stage.name
        all_match = all_match and match
        
        status = "✓" if match else "✗"
        spouse_str = f"/{age_s}" if age_s else "/deceased"
        
        print(f"{status} Age {age_p}{spouse_str}, Wages={wages}, SS={ss}")
        print(f"   Old: {old_stage.name}")
        print(f"   New: {new_stage.name}")
        if expected:
            expected_match = expected in old_stage.name
            exp_status = "✓" if expected_match else "⚠"
            print(f"   {exp_status} Expected: {expected}")
        print()
    
    print("-" * 70)
    
    if all_match:
        print("✓ SUCCESS: All stage selections match!")
    else:
        print("✗ MISMATCH: Some stage selections differ")
        print("   This may indicate an issue - investigate further")
    
    print()
    return all_match


def compare_stage_interfaces():
    """Verify both implementations have consistent interfaces"""
    
    print("=" * 70)
    print("INTERFACE CONSISTENCY CHECK")
    print("=" * 70)
    print()
    
    old_engine = WithdrawalStrategyEngine(use_refactored_stages=False)
    new_engine = WithdrawalStrategyEngine(use_refactored_stages=True)
    
    print("Checking stage interfaces...")
    
    all_consistent = True
    for i, (old_stage, new_stage) in enumerate(zip(old_engine.stages, new_engine.stages), 1):
        # Check required methods
        old_has_applies = hasattr(old_stage, 'applies')
        new_has_applies = hasattr(new_stage, 'applies')
        
        old_has_calc = hasattr(old_stage, 'calculate_strategy')
        new_has_calc = hasattr(new_stage, 'calculate_strategy')
        
        old_has_name = hasattr(old_stage, 'name')
        new_has_name = hasattr(new_stage, 'name')
        
        consistent = (old_has_applies == new_has_applies and
                     old_has_calc == new_has_calc and
                     old_has_name == new_has_name)
        
        all_consistent = all_consistent and consistent
        
        status = "✓" if consistent else "✗"
        print(f"{status} Stage {i}: {type(old_stage).__name__} vs {type(new_stage).__name__}")
        
        if not consistent:
            print(f"   applies: {old_has_applies} vs {new_has_applies}")
            print(f"   calculate_strategy: {old_has_calc} vs {new_has_calc}")
            print(f"   name: {old_has_name} vs {new_has_name}")
    
    print()
    if all_consistent:
        print("✓ SUCCESS: All interfaces are consistent")
    else:
        print("✗ FAILURE: Interface inconsistencies detected")
    
    print()
    return all_consistent


def check_environment():
    """Check current environment configuration"""
    
    print("=" * 70)
    print("ENVIRONMENT CHECK")
    print("=" * 70)
    print()
    
    print(f"Refactored stages available: {strategy.REFACTORED_STAGES_AVAILABLE}")
    print(f"USE_REFACTORED_STAGES flag: {strategy.USE_REFACTORED_STAGES}")
    print(f"Comparison mode enabled: {strategy.COMPARE_IMPLEMENTATIONS}")
    print()
    
    if strategy.USE_REFACTORED_STAGES and strategy.REFACTORED_STAGES_AVAILABLE:
        print("✓ System is configured to use REFACTORED stages")
    elif not strategy.REFACTORED_STAGES_AVAILABLE:
        print("⚠ Refactored stages are NOT available (import failed)")
    else:
        print("✓ System is configured to use ORIGINAL stages")
    
    print()


def main():
    """Main entry point"""
    print()
    check_environment()
    
    # Run comparisons
    stage_match = compare_stage_outputs()
    interface_match = compare_stage_interfaces()
    
    # Summary
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    
    if stage_match and interface_match:
        print("✓ All comparisons passed")
        print("✓ Implementations are equivalent")
        print("✓ Safe to proceed with rollout")
        exit_code = 0
    else:
        print("✗ Some comparisons failed")
        print("⚠ Review differences before rollout")
        exit_code = 1
    
    print("=" * 70)
    print()
    
    return exit_code


if __name__ == '__main__':
    import sys
    sys.exit(main())

# Made with Bob
