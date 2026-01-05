"""
HITL Policy Service for determining which tool calls require user approval.

Provides:
- Policy evaluation for tool calls
- Default policy configuration
- Wildcard pattern matching for tool names
"""
import fnmatch
import logging
from typing import Optional, Tuple

from app.models.hitl_models import HITLPolicy, HITLPolicyRule

logger = logging.getLogger("agent-runtime.hitl_policy")


class HITLPolicyService:
    """
    Service for evaluating HITL policies and determining if tool calls require approval.
    
    Supports:
    - Rule-based policy evaluation
    - Wildcard pattern matching (e.g., "write_*", "*_file")
    - Default fallback behavior
    """
    
    def __init__(self, policy: Optional[HITLPolicy] = None):
        """
        Initialize policy service with optional custom policy.
        
        Args:
            policy: Custom HITL policy. If None, uses default policy.
        """
        self._policy = policy or self._get_default_policy()
        logger.info(
            f"HITLPolicyService initialized: enabled={self._policy.enabled}, "
            f"rules={len(self._policy.rules)}"
        )
    
    def _get_default_policy(self) -> HITLPolicy:
        """
        Get default HITL policy with common dangerous operations.
        
        Returns:
            Default HITLPolicy configuration
        """
        return HITLPolicy(
            enabled=True,
            rules=[
                HITLPolicyRule(
                    tool_name="write_file",
                    requires_approval=True,
                    reason="File modification requires user approval"
                ),
                HITLPolicyRule(
                    tool_name="delete_file",
                    requires_approval=True,
                    reason="File deletion requires user approval"
                ),
                HITLPolicyRule(
                    tool_name="execute_command",
                    requires_approval=True,
                    reason="Command execution requires user approval"
                ),
                HITLPolicyRule(
                    tool_name="create_directory",
                    requires_approval=True,
                    reason="Directory creation requires user approval"
                ),
                HITLPolicyRule(
                    tool_name="move_file",
                    requires_approval=True,
                    reason="File move requires user approval"
                ),
                # Safe operations - explicitly marked as not requiring approval
                HITLPolicyRule(
                    tool_name="read_file",
                    requires_approval=False,
                    reason="Read operations are safe"
                ),
                HITLPolicyRule(
                    tool_name="list_files",
                    requires_approval=False,
                    reason="List operations are safe"
                ),
                HITLPolicyRule(
                    tool_name="search_files",
                    requires_approval=False,
                    reason="Search operations are safe"
                ),
            ],
            default_requires_approval=False
        )
    
    def requires_approval(self, tool_name: str) -> Tuple[bool, Optional[str]]:
        """
        Check if a tool call requires user approval based on policy.
        
        Args:
            tool_name: Name of the tool to check
            
        Returns:
            Tuple of (requires_approval: bool, reason: Optional[str])
        """
        # If HITL is disabled globally, no approval required
        if not self._policy.enabled:
            logger.debug(f"HITL disabled globally, tool '{tool_name}' does not require approval")
            return False, None
        
        # Check each rule for a match
        for rule in self._policy.rules:
            if self._matches_pattern(tool_name, rule.tool_name):
                logger.debug(
                    f"Tool '{tool_name}' matched rule '{rule.tool_name}': "
                    f"requires_approval={rule.requires_approval}"
                )
                return rule.requires_approval, rule.reason
        
        # No rule matched, use default behavior
        logger.debug(
            f"Tool '{tool_name}' did not match any rule, "
            f"using default: requires_approval={self._policy.default_requires_approval}"
        )
        return self._policy.default_requires_approval, None
    
    def _matches_pattern(self, tool_name: str, pattern: str) -> bool:
        """
        Check if tool name matches pattern (supports wildcards).
        
        Args:
            tool_name: Actual tool name
            pattern: Pattern to match (supports * and ? wildcards)
            
        Returns:
            True if tool name matches pattern
        """
        return fnmatch.fnmatch(tool_name, pattern)
    
    def update_policy(self, policy: HITLPolicy) -> None:
        """
        Update the current policy configuration.
        
        Args:
            policy: New HITL policy
        """
        self._policy = policy
        logger.info(
            f"Policy updated: enabled={policy.enabled}, "
            f"rules={len(policy.rules)}"
        )
    
    def get_policy(self) -> HITLPolicy:
        """
        Get current policy configuration.
        
        Returns:
            Current HITLPolicy
        """
        return self._policy
    
    def is_enabled(self) -> bool:
        """
        Check if HITL is globally enabled.
        
        Returns:
            True if HITL is enabled
        """
        return self._policy.enabled
    
    def enable(self) -> None:
        """Enable HITL globally"""
        self._policy.enabled = True
        logger.info("HITL enabled globally")
    
    def disable(self) -> None:
        """Disable HITL globally"""
        self._policy.enabled = False
        logger.info("HITL disabled globally")


# Singleton instance for global use
hitl_policy_service = HITLPolicyService()
