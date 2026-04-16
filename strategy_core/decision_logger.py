"""
Decision Logger Implementation

Provides structured logging of strategy decisions for audit trails
and user transparency.
"""

import logging
from typing import List, Any

from .interfaces import IDecisionLogger
from .models import DecisionLog, DecisionReason

logger = logging.getLogger(__name__)


class DecisionLogger(IDecisionLogger):
    """
    Concrete implementation of decision logging.
    
    Maintains a structured log of all strategy decisions with
    supporting data for transparency and debugging.
    
    Attributes:
        _log: Internal DecisionLog instance
    """
    
    def __init__(self):
        """Initialize decision logger with empty log."""
        self._log = DecisionLog()
        logger.debug("Initialized DecisionLogger")
    
    def log_decision(
        self,
        category: str,
        decision: str,
        action: str,
        reason: str,
        **values: Any
    ) -> None:
        """
        Log a strategy decision.
        
        Args:
            category: Decision category (e.g., 'roth_conversion')
            decision: Short decision label
            action: What was decided
            reason: Human-readable explanation
            **values: Supporting numerical values
        """
        self._log.add(category, decision, action, reason, **values)
        
        logger.debug(
            f"Decision logged: [{category}] {decision}: {action} - {reason}"
        )
    
    def get_all_decisions(self) -> List[DecisionReason]:
        """
        Get all logged decisions.
        
        Returns:
            List of all DecisionReason objects
        """
        return self._log.all_decisions()
    
    def get_summary(self) -> List[str]:
        """
        Get human-readable summary of all decisions.
        
        Returns:
            List of formatted decision strings
        """
        return self._log.summary_lines()
    
    def get_decisions_by_category(self, category: str) -> List[DecisionReason]:
        """
        Get decisions for a specific category.
        
        Args:
            category: Category name
            
        Returns:
            List of decisions in that category
        """
        if not hasattr(self._log, category):
            logger.warning(f"Unknown category: {category}")
            return []
        
        return getattr(self._log, category)
    
    def clear(self) -> None:
        """Clear all logged decisions."""
        self._log = DecisionLog()
        logger.debug("Decision log cleared")
    
    def get_log(self) -> DecisionLog:
        """
        Get the underlying DecisionLog object.
        
        Returns:
            DecisionLog instance
        """
        return self._log
    
    def merge_log(self, other_log: DecisionLog) -> None:
        """
        Merge another DecisionLog into this logger.
        
        Useful for combining decisions from sub-calculations.
        
        Args:
            other_log: DecisionLog to merge
        """
        for decision in other_log.all_decisions():
            # Determine category based on decision content
            category = self._categorize_decision(decision)
            
            self._log.add(
                category,
                decision.decision,
                decision.action,
                decision.reason,
                **decision.values
            )
        
        logger.debug(f"Merged {len(other_log.all_decisions())} decisions")
    
    def _categorize_decision(self, decision: DecisionReason) -> str:
        """
        Determine the appropriate category for a decision.
        
        Args:
            decision: DecisionReason to categorize
            
        Returns:
            Category name
        """
        label = decision.decision.lower()
        
        if "cash" in label:
            return "cash_replenishment"
        if "brokerage" in label or "taxable" in label:
            return "brokerage_replenishment"
        if "roth" in label and "conversion" not in label:
            return "roth_conversion"
        if "conversion" in label:
            return "roth_conversion"
        if "irmaa" in label:
            return "irmaa_decisions"
        if "aca" in label or "healthcare" in label:
            return "aca_decisions"
        if "rmd" in label:
            return "rmd_decisions"
        if "ltcg" in label or "capital gain" in label:
            return "ltcg_decisions"
        if "social security" in label or "ss " in label:
            return "ss_decisions"
        if "contribution" in label or "401k" in label or "ira" in label:
            return "contribution_decisions"
        
        # Default bucket
        return "tax_strategy"
    
    def export_to_dict(self) -> dict:
        """
        Export all decisions to a dictionary for serialization.
        
        Returns:
            Dictionary with categorized decisions
        """
        return {
            'tax_strategy': [d.to_dict() for d in self._log.tax_strategy],
            'roth_conversion': [d.to_dict() for d in self._log.roth_conversion],
            'aca_decisions': [d.to_dict() for d in self._log.aca_decisions],
            'irmaa_decisions': [d.to_dict() for d in self._log.irmaa_decisions],
            'cash_replenishment': [d.to_dict() for d in self._log.cash_replenishment],
            'brokerage_replenishment': [d.to_dict() for d in self._log.brokerage_replenishment],
            'contribution_decisions': [d.to_dict() for d in self._log.contribution_decisions],
            'rmd_decisions': [d.to_dict() for d in self._log.rmd_decisions],
            'ltcg_decisions': [d.to_dict() for d in self._log.ltcg_decisions],
            'ss_decisions': [d.to_dict() for d in self._log.ss_decisions],
        }
    
    def __repr__(self) -> str:
        """String representation for debugging."""
        num_decisions = len(self._log.all_decisions())
        return f"DecisionLogger(decisions={num_decisions})"

# Made with Bob
