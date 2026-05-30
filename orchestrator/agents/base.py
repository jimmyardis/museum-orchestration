from abc import ABC, abstractmethod
import logging


class BaseAgent(ABC):
    name: str
    description: str
    dependencies: list[str] = []

    def __init__(self):
        self.logger = logging.getLogger(self.name)

    @abstractmethod
    def run(self, persona_id: str, context: dict) -> dict:
        """Execute agent logic. Return {"status", "message", "data"}."""
        pass

    def validate_context(self, context: dict, required_keys: list[str]):
        missing = [k for k in required_keys if k not in context]
        if missing:
            raise ValueError(f"{self.name}: missing context keys: {missing}")
