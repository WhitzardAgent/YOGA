from .base import Environment
from ..actions.agent_bridge.agent_bridge import AgentBridge # Correct path to AgentBridge class
from ..utils import log_info

class RemoteServerEnvironment(Environment):
    def __init__(self, config_dict):
        super().__init__()
        # The environment owns the connection resource
        self.bridge = AgentBridge(config_dict)
        self.state["is_initialized"] = False
        self.state["cwd"] = None

    async def setup(self, local_path=None):
        if not self.state["is_initialized"]:
            await self.bridge.initialize()
            self.state['is_initialized'] = True
            self.state["cwd"] = "/home/ubuntu/sandbox"
            if(local_path is not None):
                log_info(local_path)
                success = await self.bridge.execute_task(task={
                    "type": "shell",
                    "content": f'rm -rf {self.state["cwd"]}',
                    "params": {
                    }
                })
                log_info(success)
                success = await self.bridge.execute_task(task={
                    "type": "sync_to_cloud",
                    "content": local_path,
                    "params": {
                        "remote_path": self.state["cwd"]
                    }
                })
                log_info(success)
            
    async def close(self):
        if self.state["is_initialized"]:
            await self.bridge.cleanup()
            self.state["is_initialized"] = False