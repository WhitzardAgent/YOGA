"""
动作执行器测试
"""

import asyncio
import pytest
from unittest.mock import Mock, patch, AsyncMock

from agent_bridge.action_executor import ActionExecutor
from agent_bridge.connection_manager import ConnectionManager
from agent_bridge.exceptions import ExecutionError


class TestActionExecutor:
    """动作执行器测试类"""
    
    def setup_method(self):
        """测试前置方法"""
        self.mock_connection = Mock(spec=ConnectionManager)
        self.executor = ActionExecutor(
            connection_manager=self.mock_connection,
            venv_path='~/test_venv'
        )
    
    @pytest.mark.asyncio
    async def test_initialization(self):
        """测试初始化"""
        assert self.executor.connection_manager == self.mock_connection
        assert self.executor.venv_path == '~/test_venv'
        assert self.executor.venv_python == '~/test_venv/bin/python'
        assert self.executor.venv_pip == '~/test_venv/bin/pip'
        assert not self.executor._venv_initialized
    
    @pytest.mark.asyncio
    async def test_setup_venv_exists(self):
        """测试虚拟环境已存在"""
        self.mock_connection.execute.return_value = (0, '', '')
        
        result = await self.executor.setup_venv()
        
        assert result is True
        assert self.executor._venv_initialized is True
        self.mock_connection.execute.assert_called_with('test -d ~/test_venv')
    
    @pytest.mark.asyncio
    async def test_setup_venv_not_exists(self):
        """测试虚拟环境不存在，需要创建"""
        self.mock_connection.execute.side_effect = [
            (1, '', ''),  # test -d 失败
            (0, '', ''),  # python3 -m venv 成功
            (0, '', ''),  # pip upgrade 成功
        ]
        
        result = await self.executor.setup_venv()
        
        assert result is True
        assert self.executor._venv_initialized is True
        assert self.mock_connection.execute.call_count == 3
    
    @pytest.mark.asyncio
    async def test_install_requirements(self):
        """测试安装依赖包"""
        self.executor._venv_initialized = True
        self.mock_connection.execute.return_value = (0, '', '')
        
        requirements = ['numpy', 'pandas', 'requests']
        result = await self.executor.install_requirements(requirements)
        
        assert result is True
        assert self.mock_connection.execute.call_count == 3
    
    @pytest.mark.asyncio
    async def test_run_python_script(self):
        """测试运行Python脚本"""
        self.executor._venv_initialized = True
        
        # 模拟执行结果
        self.mock_connection.execute.return_value = (0, 'JSON_OUTPUT:{"success": true}', '')
        
        code = '''
import json
print("Hello from Python!")
print('JSON_OUTPUT:{"result": "success"}')
'''
        
        result = await self.executor.run_python_script(code)
        
        assert result['exit_code'] == 0
        assert 'stdout' in result
        assert 'json_output' in result
        
        # 验证临时文件已清理
        cleanup_call = self.mock_connection.execute.call_args_list[-1]
        assert 'rm -f' in cleanup_call[0][0]
    
    @pytest.mark.asyncio
    async def test_run_python_script_with_error(self):
        """测试运行有错误的Python脚本"""
        self.executor._venv_initialized = True
        
        self.mock_connection.execute.return_value = (1, '', 'SyntaxError: invalid syntax')
        
        code = 'invalid python code'
        
        with pytest.raises(ExecutionError):
            await self.executor.run_python_script(code)
    
    @pytest.mark.asyncio
    async def test_create_remote_directory(self):
        """测试创建远程目录"""
        self.mock_connection.execute.return_value = (0, '', '')
        
        result = await self.executor.create_remote_directory('/tmp/test_dir')
        
        assert result is True
        self.mock_connection.execute.assert_called_with('mkdir -p /tmp/test_dir')
    
    @pytest.mark.asyncio
    async def test_check_remote_file_exists(self):
        """测试检查远程文件是否存在"""
        self.mock_connection.execute.return_value = (0, '', '')
        
        result = await self.executor.check_remote_file_exists('/tmp/test.py')
        
        assert result is True
        self.mock_connection.execute.assert_called_with('test -f /tmp/test.py')


class TestCodeWrapping:
    """代码包装测试"""
    
    def test_wrap_code_with_json_capture(self):
        """测试代码包装"""
        executor = ActionExecutor(Mock())
        
        user_code = '''
print("Hello World")
x = 1 + 1
print(f"Result: {x}")
'''
        
        wrapped_code = executor._wrap_code_with_json_capture(user_code)
        
        assert 'import json' in wrapped_code
        assert 'import sys' in wrapped_code
        assert 'try:' in wrapped_code
        assert 'except Exception as e:' in wrapped_code
        assert 'JSON_OUTPUT' in wrapped_code
        assert user_code.strip() in wrapped_code
    
    @pytest.mark.asyncio
    async def test_write_remote_file(self):
        """测试写入远程文件"""
        executor = ActionExecutor(Mock())
        executor.connection_manager.execute.return_value = (0, '', '')
        
        content = 'print("Hello from remote file!")'
        await executor._write_remote_file('/tmp/test.py', content)
        
        # 验证使用了base64编码
        call_args = executor.connection_manager.execute.call_args
        command = call_args[0][0]
        assert 'base64 -d' in command
        assert '/tmp/test.py' in command