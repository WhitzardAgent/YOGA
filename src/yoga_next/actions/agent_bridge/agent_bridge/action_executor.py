"""
动作执行器：在云端虚拟环境中执行Python代码
"""

import json
import logging
import tempfile
import uuid
from typing import Any, Dict, List, Optional

from .connection_manager import ConnectionManager
from .exceptions import ExecutionError

logger = logging.getLogger(__name__)


class ActionExecutor:
    """
    在云端虚拟环境中执行Python代码
    """
    
    def __init__(self, connection_manager: ConnectionManager, 
                 venv_path: str = "~/agent_bridge_venv"):
        """
        初始化动作执行器
        
        Args:
            connection_manager: SSH连接管理器
            venv_path: 虚拟环境路径，默认~/agent_bridge_venv
        """
        self.connection_manager = connection_manager
        self.venv_path = venv_path
        self.venv_python = f"{venv_path}/bin/python"
        self.venv_pip = f"{venv_path}/bin/pip"
        self._venv_initialized = False
    
    async def setup_venv(self) -> bool:
        """
        设置Python虚拟环境
        
        Returns:
            bool: 设置成功返回True
            
        Raises:
            ExecutionError: 虚拟环境创建失败时抛出
        """
        try:
            logger.info(f"检查虚拟环境: {self.venv_path}")
            
            # 检查虚拟环境是否已存在
            exit_code, _, _ = await self.connection_manager.execute(
                f"test -d {self.venv_path}"
            )
            
            if exit_code == 0:
                logger.info("虚拟环境已存在")
                self._venv_initialized = True
                return True
            
            # 创建虚拟环境
            logger.info("创建Python虚拟环境...")
            exit_code, stdout, stderr = await self.connection_manager.execute(
                f"python3 -m venv {self.venv_path}"
            )
            
            if exit_code != 0:
                raise ExecutionError(f"虚拟环境创建失败: {stderr}")
            
            # 升级pip
            logger.info("升级pip...")
            exit_code, _, stderr = await self.connection_manager.execute(
                f"{self.venv_pip} install --upgrade pip"
            )
            
            if exit_code != 0:
                logger.warning(f"pip升级失败: {stderr}")
            
            self._venv_initialized = True
            logger.info("虚拟环境设置完成")
            return True
            
        except Exception as e:
            raise ExecutionError(f"虚拟环境设置失败: {str(e)}")
    
    async def install_requirements(self, requirements: List[str]) -> bool:
        """
        安装Python依赖包
        
        Args:
            requirements: 依赖包列表
            
        Returns:
            bool: 安装成功返回True
            
        Raises:
            ExecutionError: 安装失败时抛出
        """
        if not self._venv_initialized:
            await self.setup_venv()
        
        if not requirements:
            return True
        
        try:
            # 构建安装命令
            packages = " ".join(requirements)
            logger.info(f"安装依赖包: {packages}")
            
            # 逐个安装以避免某个包失败导致全部失败
            for package in requirements:
                exit_code, stdout, stderr = await self.connection_manager.execute(
                    f"{self.venv_pip} install {package}"
                )
                
                if exit_code != 0:
                    logger.warning(f"包 {package} 安装失败: {stderr}")
                else:
                    logger.info(f"包 {package} 安装成功")
            
            return True
            
        except Exception as e:
            raise ExecutionError(f"依赖包安装失败: {str(e)}")
    
    async def run_python_script(self, code: str, timeout: int = 300, cwd: str='') -> Dict[str, Any]:
        """
        在云端虚拟环境中运行Python代码
        
        Args:
            code: Python代码字符串
            timeout: 执行超时时间（秒），默认300秒
            
        Returns:
            Dict[str, Any]: 包含执行结果的字典
                - exit_code: 返回码
                - stdout: 标准输出
                - stderr: 标准错误
                - json_output: 解析的JSON输出（如果有）
                - execution_time: 执行时间
                
        Raises:
            ExecutionError: 代码执行失败时抛出
        """
        if not self._venv_initialized:
            await self.setup_venv()
        
        # 生成唯一的脚本文件名
        script_id = str(uuid.uuid4())[:8]
        script_name = f"script_{script_id}.py"
        remote_script_path = f"{cwd}{script_name}"
        
        try:
            # 包装代码以捕获JSON输出
            wrapped_code = self._wrap_code_with_json_capture(code)
            
            # 将代码写入远程文件
            await self._write_remote_file(remote_script_path, wrapped_code)
            
            # 在虚拟环境中执行脚本
            logger.info(f"执行Python脚本: {script_name}")
            exit_code, stdout, stderr = await self.connection_manager.execute(
                f"{self.venv_python} {script_name}"
            )
            
            # 清理脚本文件
            await self.connection_manager.execute(f"rm -f {remote_script_path}")
            
            # 解析JSON输出
            json_output = None
            if stdout:
                try:
                    # 尝试从输出中提取JSON
                    lines = stdout.strip().split('\n')
                    for line in reversed(lines):
                        if line.strip().startswith('JSON_OUTPUT:') or line.strip().startswith('{"'):
                            json_str = line.replace('JSON_OUTPUT:', '').strip()
                            json_output = json.loads(json_str)
                            break
                except (json.JSONDecodeError, Exception) as e:
                    logger.debug(f"JSON解析失败（这可能不是错误）: {str(e)}")
            
            return {
                'exit_code': exit_code,
                'stdout': stdout,
                'stderr': stderr,
                'json_output': json_output,
                'script_path': remote_script_path
            }
            
        except Exception as e:
            # 清理临时文件
            try:
                await self.connection_manager.execute(f"rm -f {remote_script_path}")
            except:
                pass
            
            raise ExecutionError(f"Python脚本执行失败: {str(e)}")
    
    def _wrap_code_with_json_capture(self, code: str) -> str:
        """
        包装代码以捕获JSON输出
        
        Args:
            code: 原始Python代码
            
        Returns:
            str: 包装后的代码
        """
        # 确保用户代码每行都有正确的缩进
        indented_code = '\n'.join(f'        {line}' for line in code.splitlines()) if code.strip() else '        pass'
        
        wrapper_template = """
import json
import sys
import traceback

try:
    # 创建输出捕获
    from io import StringIO
    import contextlib
    
    @contextlib.contextmanager
    def capture_output():
        stdout_capture = StringIO()
        stderr_capture = StringIO()
        with contextlib.redirect_stdout(stdout_capture), contextlib.redirect_stderr(stderr_capture):
            yield stdout_capture, stderr_capture
    
    # 执行用户代码
    with capture_output() as (stdout_capture, stderr_capture):
        # 用户代码开始
{code}
        # 用户代码结束
    
    # 获取输出
    stdout_output = stdout_capture.getvalue()
    stderr_output = stderr_capture.getvalue()
    
    # 尝试解析最后的表达式作为JSON输出
    json_output = None
    if stdout_output:
        lines = stdout_output.strip().split('\\n')
        for line in reversed(lines):
            line = line.strip()
            if line:
                try:
                    json_output = json.loads(line)
                    break
                except:
                    pass
    
    # 输出结果
    result = {{
        'success': True,
        'stdout': stdout_output,
        'stderr': stderr_output,
        'json_output': json_output
    }}
    
    print("JSON_OUTPUT:" + json.dumps(result, ensure_ascii=False, indent=2))
    
except Exception as e:
    error_result = {{
        'success': False,
        'error': str(e),
        'traceback': traceback.format_exc()
    }}
    print("JSON_OUTPUT:" + json.dumps(error_result, ensure_ascii=False, indent=2))
    sys.exit(1)
"""
        return wrapper_template.format(code=indented_code)
    
    async def _write_remote_file(self, remote_path: str, content: str) -> None:
        """
        使用 heredoc 高效、安全地将内容写入远程文件
        
        Args:
            remote_path: 远程文件路径
            content: 文件内容（UTF-8 字符串）
        """
        # 生成唯一结束标记，避免与内容冲突
        end_marker = f"AGENT_BRIDGE_EOF_{uuid.uuid4().hex}"
        
        # 构建 heredoc 命令（单引号防止 shell 展开）
        heredoc_cmd = f"cat > {remote_path} << '{end_marker}'\n{content}\n{end_marker}"
        
        exit_code, _, stderr = await self.connection_manager.execute(heredoc_cmd)
        
        if exit_code != 0:
            raise ExecutionError(f"写入远程文件失败: {stderr}")
        
        logger.debug(f"远程文件已创建: {remote_path}")
        
    async def create_remote_directory(self, remote_path: str) -> bool:
        """
        创建远程目录
        
        Args:
            remote_path: 远程目录路径
            
        Returns:
            bool: 创建成功返回True
        """
        try:
            exit_code, _, _ = await self.connection_manager.execute(
                f"mkdir -p {remote_path}"
            )
            return exit_code == 0
        except Exception as e:
            logger.error(f"创建远程目录失败: {str(e)}")
            return False
    
    async def check_remote_file_exists(self, remote_path: str) -> bool:
        """
        检查远程文件是否存在
        
        Args:
            remote_path: 远程文件路径
            
        Returns:
            bool: 文件存在返回True
        """
        try:
            exit_code, _, _ = await self.connection_manager.execute(
                f"test -f {remote_path}"
            )
            return exit_code == 0
        except Exception as e:
            logger.error(f"检查文件失败: {str(e)}")
            return False