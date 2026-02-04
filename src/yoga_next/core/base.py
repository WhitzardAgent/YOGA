from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from dataclasses import dataclass

@dataclass
class ActionResult:
    success: bool
    message: str
    data: Optional[Dict[str, Any]] = None

class IFormatter(ABC):
    @staticmethod
    @abstractmethod
    def extract_json_from_model_markdown_output(output: str) -> Dict[str, Any]:
        pass
    
    @staticmethod
    @abstractmethod
    def flatten_to_kv_string(result: Dict[str, Any]) -> str:
        pass
    
    @staticmethod
    @abstractmethod
    def extract_think_tag(content: str) -> str:
        pass

class IActionExecutor(ABC):
    @abstractmethod
    async def execute(
        self,
        action_name: str,
        action_params: Dict[str, Any]
    ) -> ActionResult:
        pass

class IAgentCore(ABC):
    @abstractmethod
    async def execute(self, task: Any, max_steps: int = 100) -> Any:
        pass
    
    @abstractmethod
    async def execute_single_task(
        self,
        task: Any,
        task_idx: int = -1,
        max_steps: int = 100
    ) -> str:
        pass
