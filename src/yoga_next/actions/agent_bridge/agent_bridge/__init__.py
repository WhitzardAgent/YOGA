"""
Agent Bridge: Cloud-Local Bridge Framework
支持流式输出与环境隔离的 Agent 混合云交互层
"""

from .connection_manager import ConnectionManager
from .action_executor import ActionExecutor
from .data_manager import DataManager
from .app_connector import AppConnector
from .agent_bridge import AgentBridge
from .exceptions import AgentBridgeError, ConnectionError, ExecutionError

__version__ = "1.0.0"
__author__ = "Agent Bridge Team"

__all__ = [
    "ConnectionManager",
    "ActionExecutor", 
    "DataManager",
    "AppConnector",
    "AgentBridge",
    "AgentBridgeError",
    "ConnectionError",
    "ExecutionError"
]