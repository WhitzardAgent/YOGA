import asyncio
from typing import Dict, Any, List
from .base import ActionSpace
from ..environments import RemoteServerEnvironment

class RemoteServerSpace(ActionSpace):
    """
    Action Space for interacting with remote servers via Agent Bridge.
    This space translates high-level agent intents into specific 
    AgentBridge task executions.
    """
    def __init__(self, action_space_name: str, env: RemoteServerEnvironment):
        super().__init__(action_space_name, env)
        # Define capabilities in OpenAI tool-call compatible format
        self.capabilities = {
            "execute_shell": {
                "description": "Execute a shell command on the remote server.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "command": {"type": "string", "description": "The shell command to execute."}
                    },
                    "required": ["command"]
                }
            },
            "execute_python": {
                "description": "Execute Python code on the remote server.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "code": {"type": "string", "description": "The Python code to execute."},
                        "remote_path": {"type": "string", "description": "Destination to store and execute the python code."}
                    },
                    "required": ["code", "remote_path"]
                }
            },
            "sync_to_cloud": {
                "description": "Upload local files to the remote workspace.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "local_path": {"type": "string", "description": "Local file or directory path to upload."},
                        "remote_path": {"type": "string", "description": "Destination path on the remote server."}
                    },
                    "required": ["local_path", "remote_path"]
                }
            },
            "sync_from_cloud": {
                "description": "Download files from the remote server to local storage.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "remote_path": {"type": "string", "description": "Remote file or directory path to download."},
                        "local_path": {"type": "string", "description": "Local destination path for the downloaded content."}
                    },
                    "required": ["remote_path", "local_path"]
                }
            }
        }

    async def execute(self, action_name: str, param_dict: Dict[str, Any]) -> Dict[str, Any]:
        """
        Routes the action to the AgentBridge instance stored in the environment.
        """
        # 1. Ensure the remote connection is active
        try:
            await self.env.setup()
        except Exception as e:
            return {"status": "error", "message": f"Connection failed: {str(e)}"}

        # 2. Map actions to AgentBridge task types
        try:
            if action_name == "execute_shell":
                task = {
                    'type': 'shell',
                    'content': param_dict.get("command", "")
                }
            
            elif action_name == "execute_python":
                task = {
                    'type': 'python',
                    'content': param_dict.get("code", ""),
                    'params': {'remote_path': param_dict.get("remote_path", "/home/ubuntu/sandbox")}
                }
            
            elif action_name == "sync_to_cloud":
                task = {
                    'type': 'sync_to_cloud',
                    'content': param_dict.get("local_path", ""),
                    'params': {'remote_path': param_dict.get("remote_path", "/home/ubuntu/sandbox")}
                }
            
            elif action_name == "sync_from_cloud":
                task = {
                    'type': 'sync_from_cloud',
                    'content': param_dict.get("remote_path", ""),
                    'params': {'local_path': param_dict.get("local_path", "./sandbox")}
                }
            
            else:
                return {"status": "error", "message": f"Action '{action_name}' not supported."}

            # 3. Execute via the bridge (stored in env)
            result = await self.env.bridge.execute_task(task)
            
            # 4. Standardize the response for the Agent's Episodic Memory
            return {
                "status": "success",
                "action": action_name,
                "output": result
            }

        except Exception as e:
            return {
                "status": "error",
                "action": action_name,
                "output": {"error_message": f"Execution failed: {str(e)}"}
            }

    def get_capabilities(self) -> Dict[str, Any]:
        """Returns the available tools for the Agent's system prompt in OpenAI-compatible format."""
        return self.capabilities