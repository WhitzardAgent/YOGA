from typing import Dict, Any
from .base import ActionSpace
from ..environments import LocalCondaEnvironment


class LocalActionSpace(ActionSpace):
    """
    Action Space for executing commands in the local environment.
    Delegates to LocalCondaEnvironment for all operations.
    """

    def __init__(self, action_space_name: str, env: LocalCondaEnvironment):
        super().__init__(action_space_name, env)

    async def execute(self, action_name: str, param_dict: Dict[str, Any]) -> Dict[str, Any]:
        try:
            await self.env.setup()
            handler = getattr(self, f"_handle_{action_name}", None)
            if not handler:
                return {"status": "error", "message": f"Action '{action_name}' not supported."}
            result = await handler(**param_dict)
            return {
                "status": "success" if result.get("status") != "error" else "error",
                "action": action_name,
                "output": result
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}

    async def _handle_execute_shell(self, command: str) -> Dict[str, Any]:
        """Execute a shell command in the local environment.

        :param command: The shell command to execute.
        """
        return await self.env.run_shell(command)

    # async def _handle_execute_python(self, code: str) -> Dict[str, Any]:
    #     """Execute Python code in the local conda environment.

    #     :param code: The Python code to execute.
    #     """
    #     return await self.env.run_python(code)

    # async def _handle_install_packages(self, packages: list) -> Dict[str, Any]:
    #     """Install Python packages in the local conda environment.

    #     :param packages: List of package names to install.
    #     """
    #     return await self.env.install_packages(packages)

    async def _handle_run_in_conda_env(self, command: str) -> Dict[str, Any]:
        """Execute a command within the conda environment.

        :param command: The command to run in the conda environment.
        """
        return await self.env.execute_command(command)

    async def _handle_read_file(self, path: str) -> Dict[str, Any]:
        """Read the contents of a file.

        :param path: Path to the file to read.
        """
        return await self.env.read_file(path)

    async def _handle_write_file(self, path: str, content: str) -> Dict[str, Any]:
        """Write content to a file.

        :param path: Path to the file to write.
        :param content: Content to write to the file.
        """
        return await self.env.write_file(path, content)

    async def _handle_list_directory(self, path: str, depth: int = 2) -> Dict[str, Any]:
        """List contents of a directory recursively.

        :param path: Path to the directory.
        :param depth: Depth of recursion (default: 2).
        """
        return await self.env.list_dir(path, depth)

    async def _handle_exists(self, path: str) -> Dict[str, Any]:
        """Check if a path exists.

        :param path: Path to check.
        """
        return await self.env.exists(path)

    async def close(self):
        await self.env.close()
