"""
连接管理器测试
"""

import asyncio
import pytest
from unittest.mock import Mock, patch, AsyncMock

from agent_bridge.connection_manager import ConnectionManager
from agent_bridge.exceptions import ConnectionError


class TestConnectionManager:
    """连接管理器测试类"""
    
    def setup_method(self):
        """测试前置方法"""
        self.config = {
            'host': 'test-server.com',
            'username': 'testuser',
            'password': 'testpass',
            'port': 22,
            'timeout': 30,
            'retry_times': 3
        }
        self.manager = ConnectionManager(**self.config)
    
    @pytest.mark.asyncio
    async def test_initialization(self):
        """测试初始化"""
        assert self.manager.host == 'test-server.com'
        assert self.manager.username == 'testuser'
        assert self.manager.password == 'testpass'
        assert self.manager.port == 22
        assert self.manager.timeout == 30
        assert self.manager.retry_times == 3
        assert not self.manager.connected
    
    @pytest.mark.asyncio
    async def test_connect_success(self):
        """测试连接成功"""
        with patch('paramiko.SSHClient') as mock_ssh:
            mock_client = Mock()
            mock_ssh.return_value = mock_client
            mock_transport = Mock()
            mock_transport.is_active.return_value = True
            mock_client.get_transport.return_value = mock_transport
            
            result = await self.manager.connect()
            
            assert result is True
            assert self.manager.connected is True
            mock_client.connect.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_connect_failure(self):
        """测试连接失败"""
        with patch('paramiko.SSHClient') as mock_ssh:
            mock_client = Mock()
            mock_ssh.return_value = mock_client
            mock_client.connect.side_effect = Exception("Connection refused")
            
            with pytest.raises(ConnectionError):
                await self.manager.connect()
    
    @pytest.mark.asyncio
    async def test_execute_command(self):
        """测试执行命令"""
        with patch.object(self.manager, 'client'):
            mock_client = Mock()
            self.manager.client = mock_client
            self.manager.connected = True
            
            mock_stdin = Mock()
            mock_stdout = Mock()
            mock_stderr = Mock()
            
            mock_stdout.read.return_value = b'command output'
            mock_stderr.read.return_value = b''
            mock_stdout.channel.recv_exit_status.return_value = 0
            
            mock_client.exec_command.return_value = (mock_stdin, mock_stdout, mock_stderr)
            
            exit_code, stdout, stderr = await self.manager.execute('ls -la')
            
            assert exit_code == 0
            assert stdout == 'command output'
            assert stderr == ''
    
    @pytest.mark.asyncio
    async def test_stream_shell(self):
        """测试流式shell执行"""
        with patch.object(self.manager, 'client'):
            mock_client = Mock()
            self.manager.client = mock_client
            self.manager.connected = True
            
            mock_channel = Mock()
            mock_channel.recv_ready.side_effect = [True, True, False]
            mock_channel.recv.return_value = b'line 1\nline 2\n'
            mock_channel.exit_status_ready.return_value = True
            mock_channel.recv_exit_status.return_value = 0
            
            mock_client.invoke_shell.return_value = mock_channel
            
            outputs = []
            async for line in self.manager.stream_shell('echo "test"'):
                outputs.append(line)
            
            assert len(outputs) > 0
    
    @pytest.mark.asyncio
    async def test_reconnect(self):
        """测试重连"""
        with patch.object(self.manager, 'connect') as mock_connect, \
             patch.object(self.manager, 'close') as mock_close:
            mock_connect.return_value = True
            
            result = await self.manager.reconnect()
            
            assert result is True
            mock_close.assert_called_once()
            mock_connect.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_close(self):
        """测试关闭连接"""
        mock_client = Mock()
        self.manager.client = mock_client
        self.manager.connected = True
        
        await self.manager.close()
        
        mock_client.close.assert_called_once()
        assert self.manager.connected is False
        assert self.manager.client is None
    
    @pytest.mark.asyncio
    async def test_context_manager(self):
        """测试上下文管理器"""
        with patch.object(self.manager, 'connect') as mock_connect, \
             patch.object(self.manager, 'close') as mock_close:
            mock_connect.return_value = True
            
            async with self.manager as manager:
                assert manager == self.manager
                mock_connect.assert_called_once()
            
            mock_close.assert_called_once()