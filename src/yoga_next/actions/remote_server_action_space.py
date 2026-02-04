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

    async def _handle_execute_shell(self, command: str) -> Dict[str, Any]:
        """Execute a shell command on the remote server.
        
        :param command: The shell command to execute.
        
        Returns the command output including stdout and stderr.
        """
        task = {
            'type': 'shell',
            'content': command
        }
        result = await self.env.bridge.execute_task(task)
        return {
            "status": "success",
            "stdout": result.get("stdout", ""),
            "stderr": result.get("stderr", ""),
            "return_code": result.get("return_code", 0)
        }

    async def _handle_execute_python(self, code: str, remote_path: str = "/home/ubuntu/sandbox") -> Dict[str, Any]:
        """Execute Python code on the remote server.
        
        :param code: The Python code to execute.
        :param remote_path: Destination to store and execute the python code. Defaults to "/home/ubuntu/sandbox".
        
        Returns the execution output including stdout and stderr.
        """
        task = {
            'type': 'python',
            'content': code,
            'params': {'remote_path': remote_path}
        }
        result = await self.env.bridge.execute_task(task)
        return {
            "status": "success",
            "stdout": result.get("stdout", ""),
            "stderr": result.get("stderr", ""),
            "return_code": result.get("return_code", 0)
        }

    async def _handle_sync_to_cloud(self, local_path: str, remote_path: str = "/home/ubuntu/sandbox") -> Dict[str, Any]:
        """Upload local files to the remote workspace.
        
        :param local_path: Local file or directory path to upload.
        :param remote_path: Destination path on the remote server. Defaults to "/home/ubuntu/sandbox".
        
        Returns confirmation of the sync operation.
        """
        task = {
            'type': 'sync_to_cloud',
            'content': local_path,
            'params': {'remote_path': remote_path}
        }
        result = await self.env.bridge.execute_task(task)
        return {
            "status": "success",
            "message": f"Successfully synced {local_path} to {remote_path}",
            "details": result
        }

    async def _handle_sync_from_cloud(self, remote_path: str, local_path: str = "./sandbox") -> Dict[str, Any]:
        """Download files from the remote server to local storage.
        
        :param remote_path: Remote file or directory path to download.
        :param local_path: Local destination path for the downloaded content. Defaults to "./sandbox".
        
        Returns confirmation of the download operation.
        """
        task = {
            'type': 'sync_from_cloud',
            'content': remote_path,
            'params': {'local_path': local_path}
        }
        result = await self.env.bridge.execute_task(task)
        return {
            "status": "success",
            "message": f"Successfully synced {remote_path} to {local_path}",
            "details": result
        }
