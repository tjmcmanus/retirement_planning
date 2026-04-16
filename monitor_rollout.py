#!/usr/bin/env python3
"""
Monitor Rollout Script

Analyzes logs for rollout issues and provides status report.
"""

import re
import sys
from datetime import datetime
from typing import List, Tuple


def analyze_logs(log_file: str) -> Tuple[bool, dict]:
    """
    Analyze logs for rollout issues.
    
    Args:
        log_file: Path to log file
        
    Returns:
        Tuple of (success, stats_dict)
    """
    errors = []
    warnings = []
    refactored_active = False
    stage_mentions = []
    
    try:
        with open(log_file, 'r') as f:
            for line_num, line in enumerate(f, 1):
                # Check if refactored stages are active
                if 'refactored life stages' in line.lower():
                    refactored_active = True
                    stage_mentions.append((line_num, line.strip()))
                
                # Collect errors
                if 'ERROR' in line:
                    errors.append((line_num, line.strip()))
                
                # Collect warnings related to refactoring
                if 'WARNING' in line and 'refactor' in line.lower():
                    warnings.append((line_num, line.strip()))
    
    except FileNotFoundError:
        print(f"Error: Log file '{log_file}' not found")
        return False, {}
    
    stats = {
        'refactored_active': refactored_active,
        'errors': errors,
        'warnings': warnings,
        'stage_mentions': stage_mentions
    }
    
    return len(errors) == 0, stats


def print_report(success: bool, stats: dict):
    """Print analysis report"""
    print("=" * 70)
    print("ROLLOUT MONITORING REPORT")
    print("=" * 70)
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # Status
    status = "✓ SUCCESS" if success else "✗ ISSUES FOUND"
    print(f"Status: {status}")
    print()
    
    # Refactored stages status
    if stats['refactored_active']:
        print("✓ Refactored stages are ACTIVE")
    else:
        print("⚠ Refactored stages are NOT active (using original implementation)")
    print()
    
    # Stage mentions
    if stats['stage_mentions']:
        print(f"Stage initialization messages: {len(stats['stage_mentions'])}")
        for line_num, msg in stats['stage_mentions'][:3]:
            print(f"  Line {line_num}: {msg[:80]}...")
        print()
    
    # Errors
    print(f"Errors found: {len(stats['errors'])}")
    if stats['errors']:
        print("\nERRORS:")
        for line_num, error in stats['errors'][:5]:
            print(f"  Line {line_num}: {error[:100]}")
        if len(stats['errors']) > 5:
            print(f"  ... and {len(stats['errors']) - 5} more")
        print()
    
    # Warnings
    print(f"Refactoring warnings: {len(stats['warnings'])}")
    if stats['warnings']:
        print("\nWARNINGS:")
        for line_num, warning in stats['warnings'][:5]:
            print(f"  Line {line_num}: {warning[:100]}")
        if len(stats['warnings']) > 5:
            print(f"  ... and {len(stats['warnings']) - 5} more")
        print()
    
    # Recommendations
    print("=" * 70)
    print("RECOMMENDATIONS")
    print("=" * 70)
    
    if success and stats['refactored_active']:
        print("✓ Rollout appears successful")
        print("✓ Continue monitoring for 24-48 hours")
        print("✓ Proceed to Phase 5 (Cleanup) when stable")
    elif not stats['refactored_active']:
        print("⚠ Refactored stages not active")
        print("  - Check USE_REFACTORED_STAGES environment variable")
        print("  - Verify: export USE_REFACTORED_STAGES=true")
    elif not success:
        print("✗ Issues detected - consider rollback")
        print("  - Review errors above")
        print("  - Rollback: export USE_REFACTORED_STAGES=false")
        print("  - Investigate and fix issues")
    
    print("=" * 70)


def main():
    """Main entry point"""
    if len(sys.argv) < 2:
        print("Usage: python3 monitor_rollout.py <log_file>")
        print()
        print("Example:")
        print("  python3 monitor_rollout.py app.log")
        print("  python3 monitor_rollout.py /var/log/retirement_planning.log")
        sys.exit(1)
    
    log_file = sys.argv[1]
    success, stats = analyze_logs(log_file)
    print_report(success, stats)
    
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()

# Made with Bob
