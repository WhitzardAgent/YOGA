"""
Agent Bridge 主类：整合所有模块提供统一的接口
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional

from .connection_manager import ConnectionManager
from .action_executor import ActionExecutor
from .data_manager import DataManager
from .app_connector import AppConnector
from .exceptions import AgentBridgeError

logger = logging.getLogger(__name__)


class AgentBridge:
    """
    Agent Bridge 主类，提供统一的云端-本地交互接口
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        初始化Agent Bridge
        
        Args:
            config: 配置字典，包含以下键：
                - ssh_host: SSH主机地址
                - ssh_username: SSH用户名
                - ssh_password: SSH密码
                - ssh_port: SSH端口，默认22
                - remote_workspace: 远程工作目录
                - local_sandbox: 本地下载目录
                - notion_token: Notion API令牌（可选）
                - venv_path: Python虚拟环境路径（可选）
        """
        self.config = config
        
        # 初始化连接管理器
        self.connection_manager = ConnectionManager(
            host=config['ssh_host'],
            username=config['ssh_username'],
            password=config['ssh_password'],
            port=config.get('ssh_port', 22),
            timeout=config.get('timeout', 30),
            retry_times=config.get('retry_times', 3)
        )
        
        # 初始化其他模块
        self.action_executor = ActionExecutor(
            connection_manager=self.connection_manager,
            venv_path=config.get('venv_path', '~/agent_bridge_venv')
        )
        
        self.data_manager = DataManager(
            connection_manager=self.connection_manager
        )
        
        self.app_connector = AppConnector(
            connection_manager=self.connection_manager,
            action_executor=self.action_executor
        )
        
        self.initialized = False
    
    async def initialize(self) -> bool:
        """
        初始化Agent Bridge
        
        Returns:
            bool: 初始化成功返回True
            
        Raises:
            AgentBridgeError: 初始化失败时抛出
        """
        try:
            logger.info("初始化Agent Bridge...")
            
            # 建立SSH连接
            await self.connection_manager.connect()
            
            # 设置虚拟环境
            await self.action_executor.setup_venv()
            
            # 创建远程工作目录
            self.remote_workspace = self.config.get('remote_workspace', '/home/ubuntu/sandbox')
            await self.connection_manager.execute(f"mkdir -p {self.remote_workspace}")
            
            # 创建本地下载目录
            self.local_sandbox = self.config.get('local_sandbox', './sandbox')
            import os
            os.makedirs(self.local_sandbox, exist_ok=True)
            
            self.initialized = True
            logger.info("Agent Bridge 初始化完成")
            return True
            
        except Exception as e:
            raise AgentBridgeError(f"Agent Bridge 初始化失败: {str(e)}")
    
    async def execute_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行任务
        
        Args:
            task: 任务字典，包含以下键：
                - type: 任务类型（shell, python, sync, notion, scrape等）
                - content: 任务内容
                - params: 任务参数（可选）
                
        Returns:
            Dict[str, Any]: 任务执行结果
            
        Raises:
            AgentBridgeError: 任务执行失败时抛出
        """
        if not self.initialized:
            raise AgentBridgeError("Agent Bridge 未初始化，请先调用 initialize() 方法")
        
        task_type = task.get('type')
        content = task.get('content')
        params = task.get('params', {})
        
        try:
            logger.info(f"执行任务: {task_type}")
            
            if task_type == 'shell':
                # 执行shell命令
                exit_code, stdout, stderr = await self.connection_manager.execute(content)
                return {
                    'success': exit_code == 0,
                    'exit_code': exit_code,
                    'stdout': stdout,
                    'stderr': stderr
                }
            
            elif task_type == 'shell_stream':
                # 流式执行shell命令
                output_lines = []
                async for line in self.connection_manager.stream_shell(content):
                    output_lines.append(line)
                return {
                    'success': True,
                    'output': '\n'.join(output_lines)
                }
            
            elif task_type == 'python':
                # 执行Python代码
                remote_path = params.get('remote_path', '/home/ubuntu/sandbox')
                result = await self.action_executor.run_python_script(content, cwd=remote_path)
                return {
                    'success': result['exit_code'] == 0,
                    **result
                }
            
            elif task_type == 'sync_to_cloud':
                # 同步到云端
                local_path = content
                remote_path = params.get('remote_path', '~/agent_bridge_workspace')
                synced_files = await self.data_manager.sync_to_cloud(local_path, remote_path)
                return {
                    'success': True,
                    'synced_files': synced_files
                }
            
            elif task_type == 'sync_from_cloud':
                # 从云端同步
                remote_path = content
                local_path = params.get('local_path', './sandbox')
                synced_files = await self.data_manager.sync_from_cloud(remote_path, local_path)
                return {
                    'success': True,
                    'synced_files': synced_files
                }            
            else:
                raise AgentBridgeError(f"未知的任务类型: {task_type}")
                
        except Exception as e:
            raise AgentBridgeError(f"任务执行失败: {str(e)}")
    
    async def execute_pipeline(self, pipeline: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        执行管道任务（一系列按顺序执行的任务）
        
        Args:
            pipeline: 任务列表
            
        Returns:
            List[Dict[str, Any]]: 每个任务的执行结果
            
        Raises:
            AgentBridgeError: 管道执行失败时抛出
        """
        results = []
        
        try:
            for i, task in enumerate(pipeline):
                logger.info(f"执行管道任务 {i+1}/{len(pipeline)}: {task.get('type')}")
                
                result = await self.execute_task(task)
                results.append(result)
                
                # 如果任务失败，可以选择停止或继续
                if not result.get('success', False) and task.get('stop_on_error', True):
                    logger.warning(f"任务 {i+1} 失败，停止管道执行")
                    break
            
            return results
            
        except Exception as e:
            raise AgentBridgeError(f"管道执行失败: {str(e)}")
    
    async def cleanup(self) -> None:
        """
        清理资源
        """
        try:
            logger.info("清理Agent Bridge资源...")
            await self.connection_manager.close()
            self.initialized = False
            logger.info("Agent Bridge 清理完成")
        except Exception as e:
            logger.error(f"清理失败: {str(e)}")
    
    async def __aenter__(self):
        """异步上下文管理器入口"""
        await self.initialize()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        await self.cleanup()