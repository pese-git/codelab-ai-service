"""
System prompts for all agents in the multi-agent system.
"""
from app.agents.prompts.orchestrator import ORCHESTRATOR_PROMPT
from app.agents.prompts.coder import CODER_PROMPT
from app.agents.prompts.architect import ARCHITECT_PROMPT
from app.agents.prompts.debug import DEBUG_PROMPT
from app.agents.prompts.ask import ASK_PROMPT

__all__ = [
    "ORCHESTRATOR_PROMPT",
    "CODER_PROMPT",
    "ARCHITECT_PROMPT",
    "DEBUG_PROMPT",
    "ASK_PROMPT",
]
