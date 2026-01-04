"""
连接管理器：处理SSH连接和流式命令执行
"""

import asyncio
import logging
import time
from typing import AsyncGenerator, Optional, Tuple

import paramiko
from paramiko import SSHClient, AutoAddPolicy

from .exceptions import ConnectionError

logger = logging.getLogger(__name__)


class ConnectionManager:
    """
    管理持久化SSH连接，提供流式命令执行能力和SFTP支持
    """
    def __init__(self, host: str, username: str, password: str, port: int = 22, 
                 timeout: int = 30, retry_times: int = 3):
        """
        初始化连接管理器
        
        Args:
            host: 远程主机地址
            username: SSH用户名
            password: SSH密码
            port: SSH端口，默认22
            timeout: 连接超时时间，默认30秒
            retry_times: 重试次数，默认3次
        """
        self.host = host
        self.username = username
        self.password = password
        self.port = port
        self.timeout = timeout
        self.retry_times = retry_times
        
        self._client: Optional[SSHClient] = None
        self._sftp = None  # 缓存 SFTP 客户端
        self.connected = False
        
    async def connect(self) -> bool:
        """
        建立SSH连接
        
        Returns:
            bool: 连接成功返回True
            
        Raises:
            ConnectionError: 连接失败时抛出
        """
        if self.connected and self._client:
            return True
            
        for attempt in range(self.retry_times):
            try:
                logger.info(f"尝试连接 {self.host}:{self.port} (第{attempt + 1}次)")
                
                client = SSHClient()
                client.set_missing_host_key_policy(AutoAddPolicy())
                
                # 使用asyncio线程池执行阻塞的SSH连接
                await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: client.connect(
                        hostname=self.host,
                        port=self.port,
                        username=self.username,
                        password=self.password,
                        timeout=self.timeout,
                        look_for_keys=False,
                        allow_agent=False
                    )
                )
                
                self._client = client
                self._sftp = None  # 重置 SFTP（旧连接已失效）
                self.connected = True
                
                logger.info(f"成功连接到 {self.host}:{self.port}")
                return True
                
            except Exception as e:
                logger.error(f"连接失败 (第{attempt + 1}次): {str(e)}")
                if attempt < self.retry_times - 1:
                    await asyncio.sleep(2 ** attempt)  # 指数退避
                else:
                    raise ConnectionError(f"连接失败: {str(e)}")
        
        return False
    
    def get_sftp(self):
        """
        获取 SFTP 客户端（懒加载，线程不安全但 asyncio 单线程下安全）
        
        Returns:
            paramiko.SFTPClient: SFTP 客户端实例
        """
        if not self.connected or not self._client:
            raise ConnectionError("未建立SSH连接，无法获取SFTP客户端")
        
        if self._sftp is None:
            # 在主线程中调用（因 asyncio 单线程运行，安全）
            self._sftp = self._client.open_sftp()
            logger.debug("SFTP 客户端已创建")
        
        return self._sftp

    async def stream_shell(self, cmd: str) -> AsyncGenerator[str, None]:
        """
        流式执行shell命令，实时获取输出
        
        Args:
            cmd: 要执行的命令
            
        Yields:
            str: 命令输出的每一行
            
        Raises:
            ConnectionError: 连接问题时抛出
        """
        if not self.connected or not self._client:
            raise ConnectionError("未建立SSH连接")
        
        start_time = time.time()
        channel = None
        
        try:
            channel = self._client.invoke_shell()
            channel.settimeout(1.0)
            
            logger.info(f"执行命令: {cmd}")
            channel.send(cmd + '\n')
            
            buffer = ""
            while True:
                if channel.recv_ready():
                    data = channel.recv(4096).decode('utf-8', errors='ignore')
                    buffer += data
                    
                    while '\n' in buffer:
                        line, buffer = buffer.split('\n', 1)
                        line = line.strip()
                        if line and not line.startswith('$') and not line.endswith(cmd.strip()):
                            yield line
                
                if channel.exit_status_ready():
                    remaining = channel.recv(4096).decode('utf-8', errors='ignore')
                    if remaining:
                        buffer += remaining
                        for line in buffer.split('\n'):
                            line = line.strip()
                            if line and not line.startswith('$'):
                                yield line
                    break
                
                await asyncio.sleep(0.01)
            
            exit_code = channel.recv_exit_status()
            execution_time = time.time() - start_time
            logger.info(f"命令执行完成: 耗时={execution_time:.2f}s, 返回码={exit_code}")
            
            if exit_code != 0:
                logger.warning(f"命令返回非零状态码: {exit_code}")
                
        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"命令执行失败: {str(e)}, 耗时={execution_time:.2f}s")
            raise ConnectionError(f"流式命令执行失败: {str(e)}")
        finally:
            if channel:
                channel.close()
    
    async def execute(self, cmd: str) -> Tuple[int, str, str]:
        """
        执行命令并返回完整输出
        
        Args:
            cmd: 要执行的命令
            
        Returns:
            Tuple[int, str, str]: (返回码, stdout, stderr)
            
        Raises:
            ConnectionError: 连接问题时抛出
        """
        if not self.connected or not self._client:
            raise ConnectionError("未建立SSH连接")
        
        start_time = time.time()
        
        try:
            logger.info(f"执行命令: {cmd}")
            
            stdin, stdout, stderr = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self._client.exec_command(cmd, timeout=self.timeout)
            )
            
            stdout_data = await asyncio.get_event_loop().run_in_executor(None, stdout.read)
            stderr_data = await asyncio.get_event_loop().run_in_executor(None, stderr.read)
            exit_code = stdout.channel.recv_exit_status()
            
            stdout_str = stdout_data.decode('utf-8', errors='ignore')
            stderr_str = stderr_data.decode('utf-8', errors='ignore')
            
            execution_time = time.time() - start_time
            logger.info(f"命令执行完成: 耗时={execution_time:.2f}s, 返回码={exit_code}")
            
            return exit_code, stdout_str, stderr_str
            
        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"命令执行失败: {str(e)}, 耗时={execution_time:.2f}s")
            raise ConnectionError(f"命令执行失败: {str(e)}")
    
    async def reconnect(self) -> bool:
        """重新连接SSH"""
        logger.info("重新连接SSH...")
        await self.close()
        return await self.connect()
    
    async def close(self) -> None:
        """关闭SSH连接及SFTP"""
        if self._sftp:
            try:
                self._sftp.close()
                logger.debug("SFTP 连接已关闭")
            except Exception as e:
                logger.error(f"关闭SFTP时出错: {str(e)}")
            finally:
                self._sftp = None
        
        if self._client:
            try:
                self._client.close()
                logger.info("SSH连接已关闭")
            except Exception as e:
                logger.error(f"关闭SSH连接时出错: {str(e)}")
            finally:
                self._client = None
                self.connected = False
    
    def is_connected(self) -> bool:
        """检查连接状态"""
        return (
            self.connected 
            and self._client is not None 
            and self._client.get_transport() is not None 
            and self._client.get_transport().is_active()
        )
    
    async def __aenter__(self):
        await self.connect()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()