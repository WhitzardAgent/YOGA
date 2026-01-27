import asyncio
import os
from typing import Optional
from pathlib import Path


class _BashSession:
    """A session of a bash shell."""

    _started: bool
    _timed_out: bool

    command: str = "/bin/bash"
    _output_delay: float = 0.2
    _timeout: float = 120.0
    _sentinel: str = ",,,,bash-command-exit-__ERROR_CODE__-banner,,,,"

    def __init__(self) -> None:
        self._started = False
        self._timed_out = False
        self._process: asyncio.subprocess.Process | None = None

    async def start(self, cwd: Optional[str] = None) -> None:
        """Start the bash shell with optional working directory."""
        if self._started:
            return

        if os.name != "nt":
            self._process = await asyncio.create_subprocess_shell(
                self.command,
                shell=True,
                bufsize=0,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                preexec_fn=os.setsid,
                cwd=cwd,
            )
        else:
            self._process = await asyncio.create_subprocess_shell(
                "cmd.exe /v:on",
                shell=True,
                bufsize=0,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd,
            )

        self._started = True

    async def stop(self) -> None:
        """Terminate the bash shell."""
        if not self._started:
            return
        if self._process is None:
            return
        if self._process.returncode is not None:
            return
        try:
            self._process.terminate()
            stdout, stderr = await asyncio.wait_for(self._process.communicate(), timeout=5.0)
        except asyncio.TimeoutError:
            self._process.kill()
            try:
                stdout, stderr = await asyncio.wait_for(self._process.communicate(), timeout=2.0)
            except asyncio.TimeoutError:
                return None
        except Exception:
            return None

    async def run(self, command: str) -> dict:
        """Execute a command in the bash shell."""
        if not self._started or self._process is None:
            return {"output": "", "error": "Session not started", "error_code": -1}
        if self._process.returncode is not None:
            return {"output": "", "error": f"bash exited with {self._process.returncode}", "error_code": self._process.returncode}
        if self._timed_out:
            return {"output": "", "error": f"timed out after {self._timeout}s", "error_code": -1}

        assert self._process.stdin
        assert self._process.stdout
        assert self._process.stderr

        sentinel_before, pivot, sentinel_after = self._sentinel.partition("__ERROR_CODE__")
        assert pivot == "__ERROR_CODE__"

        errcode_retriever = "!errorlevel!" if os.name == "nt" else "$?"
        command_sep = "&" if os.name == "nt" else ";"

        self._process.stdin.write(
            b"(\n"
            + command.encode()
            + f"\n){command_sep} echo {self._sentinel.replace('__ERROR_CODE__', errcode_retriever)}\n".encode()
        )
        await self._process.stdin.drain()

        error_code = 0
        try:
            async with asyncio.timeout(self._timeout):
                while True:
                    await asyncio.sleep(self._output_delay)
                    output: str = self._process.stdout._buffer.decode()
                    if sentinel_before in output:
                        output, pivot, exit_banner = output.rpartition(sentinel_before)
                        assert pivot
                        error_code_str, pivot, _ = exit_banner.partition(sentinel_after)
                        if not pivot or not error_code_str.isdecimal():
                            continue
                        error_code = int(error_code_str)
                        break
        except asyncio.TimeoutError:
            self._timed_out = True
            return {"output": "", "error": f"timed out after {self._timeout}s", "error_code": -1}

        if output.endswith("\n"):
            output = output[:-1]

        error: str = self._process.stderr._buffer.decode()
        if error.endswith("\n"):
            error = error[:-1]

        self._process.stdout._buffer.clear()
        self._process.stderr._buffer.clear()

        return {"output": output, "error": error, "error_code": error_code}


from .base import Environment
from typing import Dict, Any, Optional
import subprocess
import os
import uuid
import shutil
import asyncio
from pathlib import Path


class LocalCondaEnvironment(Environment):
    """
    Environment that creates and manages an isolated local conda environment
    for the agent to interact with.
    """

    def __init__(self, config_dict: Optional[Dict[str, Any]] = None):
        super().__init__()
        self.config = config_dict or {}
        self.conda_path = self.config.get("conda_path", shutil.which("conda") or "conda")
        env_name = self.config.get("env_name", f"yoga_agent_{uuid.uuid4().hex[:8]}")
        self.env_name = env_name
        self.python_version = self.config.get("python_version", "3.10")
        self.workspace_root = self.config.get("workspace_root", os.getcwd())
        self._bash_session: Optional[_BashSession] = None
        self.state["env_name"] = self.env_name
        self.state["python_version"] = self.python_version
        self.state["is_initialized"] = False
        self.state["env_path"] = None
        self.state["packages"] = []
        self.state["workspace_root"] = self.workspace_root

    def _get_abs_path(self, path: str) -> Path:
        """对 Agent 屏蔽根目录，自动处理相对/绝对路径"""
        p = Path(path)
        if p.is_absolute():
            abs_path = p.resolve()
        else:
            abs_path = (Path(self.workspace_root) / p).resolve()

        workspace_resolved = Path(self.workspace_root).resolve()
        if not str(abs_path).startswith(str(workspace_resolved) + os.sep) and abs_path != workspace_resolved:
            raise PermissionError(f"Access denied: {path} is outside workspace")

        return abs_path

    def _validate_path(self, path: str) -> Optional[Path]:
        """验证路径是否在 workspace 内，返回绝对路径或 None"""
        try:
            abs_path = self._get_abs_path(path)
            return abs_path
        except (PermissionError, OSError, ValueError):
            return None

    def _format_result(self, status: str, stdout: str = "", stderr: str = "", error_code: int = 0, message: str = "") -> Dict[str, Any]:
        """统一返回格式"""
        return {
            "status": status,
            "stdout": stdout,
            "stderr": stderr,
            "error_code": error_code,
            "message": message
        }

    async def setup(self):
        """Create and initialize the conda environment."""
        if not self.state["is_initialized"]:
            if not shutil.which("conda") and not shutil.which("mamba"):
                raise RuntimeError("Conda is not installed. Please install Miniconda or Anaconda.")

            env_exists_result = await self._run_conda_command([
                "info", "--envs"
            ], check=False)

            if env_exists_result["status"] == "success" and self.env_name in env_exists_result.get("stdout", ""):
                await self._run_conda_command([
                    "remove", "--name", self.env_name, "--all", "-y"
                ], check=False)

            create_cmd = [
                "create", "--name", self.env_name,
                f"python={self.python_version}", "-y"
            ]

            if "channels" in self.config:
                for channel in self.config["channels"]:
                    create_cmd.extend(["--channel", channel])

            await self._run_conda_command(create_cmd)

            tmp_folder = Path(self.workspace_root) / "tmp"
            tmp_folder.mkdir(parents=True, exist_ok=True)

            self.state["env_path"] = await self._get_env_path()
            self.state["is_initialized"] = True

    async def _ensure_bash_session(self) -> None:
        """Ensure bash session is started with working directory locked to workspace."""
        if self._bash_session is None:
            self._bash_session = _BashSession()
            await self._bash_session.start(cwd=self.workspace_root)

    async def run_shell(self, command: str) -> Dict[str, Any]:
        """统一的 Shell 入口，ActionSpace 只需要传命令（无需 cd）"""
        if not self.state["is_initialized"]:
            return self._format_result("error", message="Environment not initialized. Call setup() first.", error_code=-1)

        try:
            await self._ensure_bash_session()
            result = await self._bash_session.run(command)
            return self._format_result(
                status="success" if result.get("error_code", -1) == 0 else "error",
                stdout=result.get("output", ""),
                stderr=result.get("error", ""),
                error_code=result.get("error_code", -1)
            )
        except Exception as e:
            return self._format_result("error", message=str(e), error_code=-1)

    async def run_python_script(self, code: str) -> Dict[str, Any]:
        """通过临时文件运行 Python，解决转义字符崩溃问题"""
        if not self.state["is_initialized"]:
            return self._format_result("error", message="Environment not initialized. Call setup() first.", error_code=-1)

        try:
            tmp_filename = f"{uuid.uuid4().hex}.py"
            tmp_path = Path(self.workspace_root) / "tmp" / tmp_filename

            await self.write_file(str(tmp_path), code)

            try:
                result = await self.execute_command(f"python tmp/{tmp_filename}")
                return result
            finally:
                if tmp_path.exists():
                    tmp_path.unlink()

        except Exception as e:
            return self._format_result("error", message=str(e), error_code=-1)

    async def execute_command(self, command: str) -> Dict[str, Any]:
        """Execute a command within the conda environment."""
        if not self.state["is_initialized"]:
            return self._format_result("error", message="Environment not initialized. Call setup() first.", error_code=-1)

        full_command = f"conda run -n {self.env_name} {command}"
        return await self._run_shell_command(full_command)

    async def install_packages(self, packages: list) -> Dict[str, Any]:
        """Install packages in the conda environment."""
        if not self.state["is_initialized"]:
            return self._format_result("error", message="Environment not initialized. Call setup() first.", error_code=-1)

        install_cmd = [
            "install", "--name", self.env_name,
            "-y"
        ] + list(packages)

        result = await self._run_conda_command(install_cmd)

        if result.get("returncode", -1) == 0:
            current_packages = self.state["packages"]
            self.state["packages"] = list(set(current_packages + packages))

        return result

    async def run_python(self, code: str) -> Dict[str, Any]:
        """Execute Python code within the environment."""
        return await self.run_python_script(code)

    async def close(self):
        """Remove the conda environment."""
        if self._bash_session:
            await self._bash_session.stop()
            self._bash_session = None

        if self.state["is_initialized"]:
            await self._run_conda_command([
                "remove", "--name", self.env_name, "--all", "-y"
            ], check=False)
            self.state["is_initialized"] = False
            self.state["env_path"] = None
            self.state["packages"] = []

    async def read_file(self, path: str) -> Dict[str, Any]:
        """原生 IO 读取，自动处理相对/绝对路径"""
        try:
            abs_path = self._get_abs_path(path)

            if not abs_path.exists():
                return self._format_result("error", message=f"File not found: {path}", error_code=-1)

            loop = asyncio.get_event_loop()
            content = await loop.run_in_executor(
                None,
                lambda: abs_path.read_text(encoding='utf-8')
            )
            return self._format_result("stdout", stdout=content)
        except PermissionError:
            return self._format_result("error", message=f"Path outside workspace: {path}", error_code=-1)
        except Exception as e:
            return self._format_result("error", message=str(e), error_code=-1)

    async def write_file(self, path: str, content: str) -> Dict[str, Any]:
        """原生 IO 写入，自动处理相对/绝对路径"""
        try:
            abs_path = self._get_abs_path(path)

            abs_path.parent.mkdir(parents=True, exist_ok=True)

            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                lambda: abs_path.write_text(content, encoding='utf-8')
            )
            return self._format_result("success", message=f"File written: {path}")
        except PermissionError:
            return self._format_result("error", message=f"Path outside workspace: {path}", error_code=-1)
        except Exception as e:
            return self._format_result("error", message=str(e), error_code=-1)

    async def list_dir(self, path: str = ".", depth: int = 2) -> Dict[str, Any]:
        """递归列出目录结构，自动处理相对/绝对路径"""
        try:
            abs_path = self._get_abs_path(path)

            if not abs_path.exists():
                return self._format_result("error", message=f"Directory not found: {path}", error_code=-1)
            if not abs_path.is_dir():
                return self._format_result("error", message=f"Not a directory: {path}", error_code=-1)

            def build_tree(p: Path, current_depth: int) -> str:
                if current_depth > depth:
                    return ""
                indent = "  " * current_depth
                result = []
                items = sorted(p.iterdir(), key=lambda x: (x.is_file(), x.name))
                for item in items:
                    if item.is_dir():
                        result.append(f"{indent}{item.name}/")
                        result.append(build_tree(item, current_depth + 1))
                    else:
                        size = item.stat().st_size
                        result.append(f"{indent}{item.name} ({size} bytes)")
                return "\n".join(result)

            loop = asyncio.get_event_loop()
            tree_content = await loop.run_in_executor(
                None,
                lambda: build_tree(abs_path, 0)
            )
            return self._format_result("stdout", stdout=tree_content)
        except PermissionError:
            return self._format_result("error", message=f"Path outside workspace: {path}", error_code=-1)
        except Exception as e:
            return self._format_result("error", message=str(e), error_code=-1)

    async def exists(self, path: str) -> Dict[str, Any]:
        """检查路径是否存在，自动处理相对/绝对路径"""
        try:
            abs_path = self._get_abs_path(path)
            exists = abs_path.exists()
            return self._format_result("stdout", stdout=str(exists))
        except PermissionError:
            return self._format_result("error", message=f"Path outside workspace: {path}", error_code=-1)
        except Exception as e:
            return self._format_result("error", message=str(e), error_code=-1)

    async def _run_conda_command(self, args: list, check: bool = True) -> Dict[str, Any]:
        """Run a conda command."""
        cmd = [self.conda_path] + args
        return await self._run_shell_command(cmd, check=check)

    async def _run_shell_command(self, cmd: str or list, check: bool = True) -> Dict[str, Any]:
        """Run a shell command and return the result."""
        if isinstance(cmd, str):
            shell = True
        else:
            shell = False

        try:
            process = await asyncio.create_subprocess_shell(
                cmd if shell else " ".join(cmd),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()
            stdout_decoded = stdout.decode()
            stderr_decoded = stderr.decode()

            if check and process.returncode != 0:
                return self._format_result(
                    status="error",
                    stderr=stderr_decoded,
                    error_code=process.returncode,
                    message=f"Command failed with return code {process.returncode}"
                )

            return self._format_result(
                status="success",
                stdout=stdout_decoded,
                stderr=stderr_decoded,
                error_code=process.returncode
            )
        except Exception as e:
            return self._format_result("error", message=str(e), error_code=-1)

    async def _get_env_path(self) -> str:
        """Get the path to the conda environment."""
        result = await self._run_conda_command([
            "env", "list"
        ])

        if result["status"] == "success":
            lines = result.get("stdout", "").split("\n")
            for line in lines:
                if self.env_name in line and not line.strip().startswith("#"):
                    parts = line.split()
                    for part in parts:
                        if part.startswith("/"):
                            return part

        return None
