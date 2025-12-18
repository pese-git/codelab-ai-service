from typing import List

from app.models.agents import AgentStep


class BaseAgent:
    name: str = ""
    description: str = ""
    tools: List[str] = []

    def __init__(self, llm=None):
        self.llm = llm

    async def decide(self, context: dict) -> AgentStep:
        raise NotImplementedError
