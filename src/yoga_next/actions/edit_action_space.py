from typing import Dict, Any
from .base import ActionSpace


class EditActionSpace(ActionSpace):
    """
    Action Space for file editing operations.
    Provides view, create, str_replace, insert, and search commands for file manipulation.
    """

    def __init__(self, action_space_name: str = "edit", env=None):
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

    def _get_workspace_root(self) -> str:
        """Get workspace_root from environment config, defaulting to current working directory."""
        if hasattr(self.env, 'config') and isinstance(self.env.config, dict):
            return self.env.config.get("workspace_root", self.env.workspace_root)
        if hasattr(self.env, 'workspace_root'):
            return self.env.workspace_root
        from os import getcwd
        return getcwd()

    def _resolve_path(self, path: str) -> str:
        """Resolve path relative to workspace_root with security check.

        All input paths are treated as relative to workspace_root.
        Uses .resolve() to get absolute path and verifies it's within workspace_root.
        Raises PermissionError if path attempts to escape workspace.
        """
        from pathlib import Path
        import os

        workspace_root = self._get_workspace_root()
        workspace_resolved = Path(workspace_root).resolve()

        relative_path = path.lstrip("/")
        abs_path = (workspace_resolved / relative_path).resolve()

        if not str(abs_path).startswith(str(workspace_resolved) + os.sep) and abs_path != workspace_resolved:
            raise PermissionError(f"Access denied: '{path}' resolves to '{abs_path}' which is outside workspace '{workspace_root}'")

        return str(abs_path)

    async def _handle_view(self, path: str, view_range: list = None) -> Dict[str, Any]:
        """View file or directory content.

        :param path: Path relative to the workspace root (e.g., 'src/main.py').
        :param view_range: Optional line range [start, end] to show (1-indexed).
        """
        resolved_path = self._resolve_path(path)

        is_dir_result = await self.env.run_shell(f"test -d '{resolved_path}' && echo 'dir' || echo 'file'")
        is_dir = "dir" in is_dir_result.get("stdout", "")

        if is_dir:
            cmd = f"find '{resolved_path}' -maxdepth 2 -not -path '*/\\.*' -printf '%p\\n' 2>/dev/null | head -50"
            result = await self.env.run_shell(cmd)
            output = f"Files in {path}:\n{result.get('stdout', '')}"
            return {"status": "success", "stdout": output}

        file_result = await self.env.read_file(resolved_path)
        if file_result.get("status") == "error":
            return file_result
        file_content = file_result.get("content") or file_result.get("stdout") or ""

        if view_range and isinstance(view_range, list) and len(view_range) == 2:
            start, end = view_range
            lines = file_content.split("\n")
            n_lines = len(lines)
            if start < 1 or start > n_lines:
                raise ValueError(f"Invalid view_range start: {start}. File has {n_lines} lines.")
            if end > n_lines:
                end = n_lines
            if end != -1 and end < start:
                raise ValueError(f"Invalid view_range: end {end} < start {start}.")
            if end == -1:
                file_content = "\n".join(lines[start - 1:])
            else:
                file_content = "\n".join(lines[start - 1:end])

        lines = file_content.split("\n")
        numbered = "\n".join([f"{i + 1}\t{line}" for i, line in enumerate(lines)])
        return {"status": "success", "stdout": f"Content of {path}:\n{numbered}"}

    async def _handle_create(self, path: str, file_text: str = "") -> Dict[str, Any]:
        """Create a new file with the given content.

        :param path: Path relative to the workspace root (e.g., 'new_file.py').
        :param file_text: Content to write to the new file.
        """
        resolved_path = self._resolve_path(path)
        await self.env.write_file(resolved_path, file_text)
        return {"status": "success", "stdout": f"File created: {path}"}

    async def _handle_str_replace(self, path: str, old_str: str, new_str: str = "") -> Dict[str, Any]:
        """Replace old_str with new_str in a file. old_str must be unique.

        :param path: Path relative to the workspace root (e.g., 'src/main.py').
        :param old_str: The exact string to replace. Must be unique in the file.
        :param new_str: The new string to replace old_str with.
        """
        resolved_path = self._resolve_path(path)

        file_result = await self.env.read_file(resolved_path)
        if file_result.get("status") == "error":
            return file_result
        file_content = file_result.get("content") or file_result.get("stdout") or ""

        occurrences = file_content.count(old_str)
        if occurrences == 0:
            raise ValueError(f"No occurrence of old_str found in {path}.")
        elif occurrences > 1:
            lines_with_occurrence = []
            for i, line in enumerate(file_content.split("\n")):
                if old_str in line:
                    lines_with_occurrence.append(i + 1)
            raise ValueError(f"Multiple occurrences of old_str in lines {lines_with_occurrence}. Must be unique.")

        new_file_content = file_content.replace(old_str, new_str)

        if path.endswith(".py"):
            import ast
            try:
                ast.parse(new_file_content)
            except SyntaxError as e:
                return {"status": "error", "message": f"Python syntax error: {e}"}

        await self.env.write_file(resolved_path, new_file_content)
        return {"status": "success", "stdout": f"File updated: {path}"}

    async def _handle_insert(self, path: str, insert_line: int, new_str: str) -> Dict[str, Any]:
        """Insert new_str after the specified line number.

        :param path: Path relative to the workspace root (e.g., 'src/main.py').
        :param insert_line: Line number AFTER which to insert (1-indexed).
        :param new_str: String to insert.
        """
        resolved_path = self._resolve_path(path)

        file_result = await self.env.read_file(resolved_path)
        if file_result.get("status") == "error":
            return file_result
        file_content = file_result.get("content") or file_result.get("stdout") or ""

        lines = file_content.split("\n")
        n_lines = len(lines)

        if insert_line < 0 or insert_line > n_lines:
            raise ValueError(f"Invalid insert_line: {insert_line}. File has {n_lines} lines.")

        new_lines = lines[:insert_line] + [new_str] + lines[insert_line:]
        new_file_content = "\n".join(new_lines)

        if path.endswith(".py"):
            import ast
            try:
                ast.parse(new_file_content)
            except SyntaxError as e:
                return {"status": "error", "message": f"Python syntax error: {e}"}

        await self.env.write_file(resolved_path, new_file_content)
        return {"status": "success", "stdout": f"Inserted after line {insert_line} in {path}"}

    async def _handle_search(self, path: str, keyword: str) -> Dict[str, Any]:
        """Search for a keyword in files within a directory using grep.

        :param path: Directory path relative to the workspace root (e.g., 'src').
        :param keyword: Keyword to search for.
        """
        resolved_path = self._resolve_path(path)
        if not keyword or not keyword.strip():
            return {"status": "error", "message": "Keyword cannot be empty."}
        escaped_keyword = keyword.replace("'", "'\\''")
        cmd = f"grep -rnE --exclude-dir={{.git,.venv,node_modules}} --exclude={{*.pyc,*.egg-info}} '{escaped_keyword}' '{resolved_path}' 2>/dev/null | head -100"
        result = await self.env.run_shell(cmd)
        stdout = result.get("stdout", "")

        if not stdout.strip():
            return {"status": "success", "stdout": f"No matches found for '{keyword}' in {path}"}

        return {"status": "success", "stdout": stdout}
