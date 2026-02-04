import asyncio
from typing import Any, Dict, Optional
from .base import ActionResult

class ActionExecutor:
    def __init__(self, action_space: Any, timeout: int = 60):
        self.action_space = action_space
        self.timeout = timeout
    
    def _get_timeout_for_action(self, action_name: str) -> int:
        return self.timeout
    
    async def execute(
        self,
        action_name: str,
        action_params: Dict[str, Any]
    ) -> ActionResult:
        timeout = self._get_timeout_for_action(action_name)
        
        try:
            result = await asyncio.wait_for(
                self.action_space.execute(action_name, action_params),
                timeout=timeout
            )
            output = result.get("output")
            
            return ActionResult(
                success=True,
                message=output,
                data=output
            )
            
        except asyncio.TimeoutError:
            from .utils import log_warn
            log_warn(f"Action '{action_name}' timed out after {timeout}s")
            return ActionResult(
                success=False,
                message=f"Action '{action_name}' timed out after {timeout}s. Please try a different approach or reduce the scope of this operation.",
                data={
                    "status": "error",
                    "message": f"Action '{action_name}' timed out after {timeout}s. Please try a different approach or reduce the scope of this operation.",
                    "error_code": 124,
                    "timeout": timeout,
                    "action": action_name
                }
            )
        except Exception as e:
            return ActionResult(
                success=False,
                message=f"Action {action_name} failed: {str(e)}"
            )
    
    def set_timeout(self, timeout: int) -> None:
        self.timeout = timeout
