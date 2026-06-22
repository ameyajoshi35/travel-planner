from abc import ABC, abstractmethod
from ..models import TripContext


class BaseAgent(ABC):
    @abstractmethod
    def run(self, ctx: TripContext) -> dict:
        """Execute the agent and return a structured result dict."""
        ...
