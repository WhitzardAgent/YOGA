from typing import Dict, Any, List
from .base import ActionSpace
import os


WHITELIST_ACTIONS = {
    "list_file_tree",
    "view",
    "search",
    "insert",
    "replace"
}


class GlimAppActionSpace(ActionSpace):
    """
    Action Space for Glim Electron App Integration.
    Provides file tree listing, viewing, searching, and safe editing with user approval.

    Tools: list_file_tree, view, search, insert, replace
    """

    def __init__(self, action_space_name: str = "glim_app", env=None):
        super().__init__(action_space_name, env)

    async def execute(self, action_name: str, param_dict: Dict[str, Any]) -> Dict[str, Any]:
        if action_name not in WHITELIST_ACTIONS:
            return {
                "status": "error",
                "message": f"Action '{action_name}' not available. Available tools: list_file_tree, view, search, insert, replace."
            }

        try:
            await self.env.setup()
            handler = getattr(self, f"_handle_{action_name}", None)
            result = await handler(**param_dict)
            return {
                "status": "success" if result.get("status") != "error" else "error",
                "action": action_name,
                "output": result
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def _get_workspace_root(self) -> str:
        if hasattr(self.env, 'config') and isinstance(self.env.config, dict):
            return self.env.config.get("workspace_root", self.env.workspace_root)
        if hasattr(self.env, 'workspace_root'):
            return self.env.workspace_root
        return os.getcwd()

    def _resolve_path(self, path: str) -> str:
        from pathlib import Path
        workspace_root = self._get_workspace_root()
        workspace_resolved = Path(workspace_root).resolve()

        if path.startswith("/"):
            relative_path = path.lstrip("/")
        else:
            relative_path = path

        abs_path = (workspace_resolved / relative_path).resolve()

        if not str(abs_path).startswith(str(workspace_resolved) + os.sep) and abs_path != workspace_resolved:
            raise PermissionError(f"Access denied: '{path}' outside workspace.")

        return str(abs_path)

    async def _handle_list_file_tree(self, path: str = None, recursive: bool = True) -> Dict[str, Any]:
        """List the project file tree structure.

        :param path: Starting path (defaults to project root).
        :param recursive: Whether to list subdirectories recursively.
        :return: File tree in JSON format.
        """
        workspace_root = self._get_workspace_root()
        start_path = path if path else workspace_root
        resolved_path = self._resolve_path(start_path)

        payload = {
            "tool": "list_file_tree",
            "params": {
                "path": resolved_path,
                "recursive": recursive
            }
        }

        try:
            response = await self.env.bridge.send_request(payload)
            return {
                "status": "success",
                "stdout": response.get("result", response)
            }
        except Exception as e:
            return {"status": "error", "message": f"Failed to list file tree: {str(e)}"}

    async def _handle_view(self, path: str, start_line: int = None, end_line: int = None) -> Dict[str, Any]:
        """View source code with line numbers.

        :param path: File path to read.
        :param start_line: Starting line number (1-indexed).
        :param end_line: Ending line number.
        :return: Code snippet with line numbers.
        """
        resolved_path = self._resolve_path(path)

        payload = {
            "tool": "view",
            "params": {
                "path": resolved_path,
                "start_line": start_line,
                "end_line": end_line
            }
        }

        try:
            response = await self.env.bridge.send_request(payload)
            return {
                "status": "success",
                "stdout": response.get("result", response)
            }
        except Exception as e:
            return {"status": "error", "message": f"Failed to view file: {str(e)}"}

    async def _handle_search(self, query: str, include: str = None) -> Dict[str, Any]:
        """Search for content in the project.

        :param query: Keyword or regex pattern to search.
        :param include: File types to include (e.g., "*.tex,*.bib").
        :return: List of matches with file, line number, and context.
        """
        payload = {
            "tool": "search",
            "params": {
                "query": query,
                "include": include
            }
        }

        try:
            response = await self.env.bridge.send_request(payload)
            return {
                "status": "success",
                "stdout": response.get("result", response)
            }
        except Exception as e:
            return {"status": "error", "message": f"Search failed: {str(e)}"}

    async def _handle_insert(self, path: str, at_line: int, content: str, description: str = "") -> Dict[str, Any]:
        """Insert new content after a specific line (non-destructive).

        :param path: Target file path.
        :param at_line: Line number after which to insert.
        :param content: LaTeX code to insert.
        :param description: Reason for adding this content.
        :return: Result with user approval status.
        """
        resolved_path = self._resolve_path(path)

        payload = {
            "tool": "insert",
            "params": {
                "path": resolved_path,
                "at_line": at_line,
                "content": content,
                "description": description
            }
        }

        try:
            response = await self.env.bridge.wait_for_user_approval(payload)

            if response.get("status") == "accepted":
                return {
                    "status": "success",
                    "observation": f"User ACCEPTED the insertion at line {at_line}. Content added to {path}."
                }
            else:
                return {
                    "status": "success",
                    "observation": "User REJECTED the insertion. The file remains unchanged. Consider an alternative approach."
                }
        except Exception as e:
            return {"status": "error", "message": f"Insert operation failed: {str(e)}"}

    async def _handle_replace(self, path: str, from_line: int, to_line: int, new_content: str,
                              original_code_snippet: str = "", description: str = "") -> Dict[str, Any]:
        """Replace a range of lines with new content (destructive, requires approval).

        :param path: Target file path.
        :param from_line: Starting line number (1-indexed).
        :param to_line: Ending line number.
        :param new_content: New code to replace the range.
        :param original_code_snippet: Agent's memory of old code (for consistency verification).
        :param description: Reason for this modification.
        :return: Result with user approval status.
        """
        resolved_path = self._resolve_path(path)

        payload = {
            "tool": "replace",
            "params": {
                "path": resolved_path,
                "from_line": from_line,
                "to_line": to_line,
                "new_content": new_content,
                "original_code_snippet": original_code_snippet,
                "description": description
            }
        }

        try:
            response = await self.env.bridge.wait_for_user_approval(payload)

            if response.get("status") == "accepted":
                return {
                    "status": "success",
                    "observation": f"User ACCEPTED the replacement at lines {from_line}-{to_line}. File updated successfully."
                }
            else:
                return {
                    "status": "success",
                    "observation": "User REJECTED the modification. The file remains unchanged. Please try an alternative fix."
                }
        except Exception as e:
            return {"status": "error", "message": f"Replace operation failed: {str(e)}"}
