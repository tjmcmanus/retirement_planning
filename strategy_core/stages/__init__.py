"""
Life Stage Strategy Implementations

Refactored life stage strategies using BaseLifeStageStrategy with
dependency injection and comprehensive type hints.
"""

from .stage1_accumulation import Stage1Accumulation
from .stage2_prep_retirement import Stage2PrepForRetirement
from .stage3_early_retirement import Stage3EarlyRetirement
from .stage4_medicare import Stage4Medicare
from .stage5_social_security import Stage5SocialSecurity
from .stage6_rmd import Stage6RMD
from .stage7_surviving_spouse import Stage7SurvivingSpouse

__all__ = [
    'Stage1Accumulation',
    'Stage2PrepForRetirement',
    'Stage3EarlyRetirement',
    'Stage4Medicare',
    'Stage5SocialSecurity',
    'Stage6RMD',
    'Stage7SurvivingSpouse',
]

# Made with Bob
