from abc import ABC, abstractmethod
from typing import Any, Dict
from collections import OrderedDict

class Environment(ABC):
    """
    Abstract base class for all Environments.
    The Environment is the 'Source of Truth' and owns the stateful resources.
    """
    def __init__(self):
        self.state: OrderedDict[str, Any] = OrderedDict()

    def get_observation(self) -> str:
        """Returns the current observable state of the environment."""
        s = ''
        for k, v in self.state.items():
            s += f'{k}:{v}\n'
        return s

    def update_state(self, key: str, value: Any):
        """Updates internal state variables."""
        self.state[key] = value

    async def setup(self):
        """Optional: Initialize resources (connections, files, etc.)."""
        pass

    async def close(self):
        """Optional: Clean up resources."""
        pass