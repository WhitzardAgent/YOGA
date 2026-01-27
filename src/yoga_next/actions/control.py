from typing import Dict, Any
from .base import ActionSpace


class ControlActionSpace(ActionSpace):
    """
    Action Space for controlling agent execution flow.
    Provides the 'done' action to signal task completion.
    """

    def __init__(self, action_space_name: str = "control", env = None):
        super().__init__(action_space_name, env)

    async def execute(self, action_name: str, param_dict: Dict[str, Any]) -> Dict[str, Any]:
        handler = getattr(self, f"_handle_{action_name}", None)
        if not handler:
            return {"status": "error", "message": f"Action '{action_name}' not supported."}
        return await handler(**param_dict)

    async def _handle_done(self, success: bool = True, message: str = "Task completed successfully.") -> Dict[str, Any]:
        """Signal that the task is done and agent should stop execution.

        :param success: Whether the task completed successfully.
        :param message: A message describing the completion status.
        """
        return {
            "status": "completed",
            "success": success,
            "message": message
        }
