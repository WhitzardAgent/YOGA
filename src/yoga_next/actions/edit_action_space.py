from typing import Dict, Any, List
from .base import ActionSpace
from difflib import unified_diff


class EditActionSpace(ActionSpace):
    """
    Action Space for file editing operations.
    Provides view, create, str_replace, insert, search, and list_tree commands for file manipulation.
    """

    def __init__(self, action_space_name: str = "edit", env=None):
        super().__init__(action_space_name, env)

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

    def _generate_unified_diff(self, old_content: str, new_content: str, path: str) -> str:
        """Generate unified diff between old and new content."""
        old_lines = old_content.splitlines(keepends=True)
        new_lines = new_content.splitlines(keepends=True)

        diff = list(unified_diff(
            old_lines,
            new_lines,
            fromfile=f"a/{path}",
            tofile=f"b/{path}",
            n=3
        ))

        if not diff:
            return ""

        return "```diff\n" + "".join(diff) + "```"

    def _parse_python_error(self, error: SyntaxError, content: str) -> Dict[str, Any]:
        """Parse Python syntax error and provide structured diagnostic feedback."""
        import ast

        lineno = error.lineno if error.lineno else 1
        offset = error.offset if error.offset else 0
        msg = str(error.args[0]) if error.args else "Unknown syntax error"

        lines = content.split("\n")
        error_line = ""
        if 1 <= lineno <= len(lines):
            error_line = lines[lineno - 1].rstrip()
            caret = " " * (offset - 1) + "^"
            error_line += f"\n{caret}"

        suggestions = []
        if "unexpected EOF" in msg:
            suggestions.append("Check for missing closing parenthesis, bracket, or quote")
        elif "invalid syntax" in msg:
            suggestions.append("Check for missing colons after function/class definitions")
        elif "EOL" in msg:
            suggestions.append("Check for unclosed strings or missing line continuation")
        elif "indentation" in msg.lower():
            suggestions.append("Ensure consistent indentation (use spaces, not tabs)")
        elif "unexpected indent" in msg:
            suggestions.append("Check for incorrect indentation level")
        else:
            suggestions.append("Review the code around the error line for syntax issues")

        return {
            "line_number": lineno,
            "error_line": error_line,
            "message": msg,
            "suggestions": suggestions
        }

    def _find_similar_strings(self, target: str, content: str) -> List[str]:
        """Find similar strings in content that might be what user meant."""
        from difflib import SequenceMatcher
        import re

        lines = content.split("\n")
        suggestions = []

        for i, line in enumerate(lines):
            line_normalized = line.strip()
            target_normalized = target.strip()
            if line_normalized and target_normalized:
                ratio = SequenceMatcher(None, line_normalized, target_normalized).ratio()
                if ratio > 0.7 and ratio < 1.0:
                    suggestions.append(f"Line {i + 1}: {line.strip()}")

        return suggestions[:5]

    async def _handle_view(self, path: str, view_range: list = None) -> Dict[str, Any]:
        """View file or directory content.

        :param path: Path relative to the workspace root (e.g., 'src/main.py').
        :param view_range: Optional line range [start, end] to show (1-indexed). Use this to avoid token overflow in large files.

        Returns structured output with markdown code blocks for easy reading.
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

        total_lines = len(file_content.split("\n"))

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

        ext = path.split('.')[-1] if '.' in path else ""
        lang_map = {
            "py": "python", "js": "javascript", "ts": "typescript",
            "json": "json", "md": "markdown", "html": "html",
            "css": "css", "sql": "sql", "sh": "bash", "yaml": "yaml"
        }
        lang = lang_map.get(ext, "text")

        output = f"### 📄 File: {path} ({total_lines} lines total)\n\n```{lang}\n{numbered}\n```"
        return {"status": "success", "stdout": output}

    async def _handle_create(self, path: str, file_text: str = "") -> Dict[str, Any]:
        """Create a new file with the given content.

        :param path: Path relative to the workspace root (e.g., 'new_file.py').
        :param file_text: Content to write to the new file.

        Automatically creates parent directories if they don't exist.
        """
        resolved_path = self._resolve_path(path)

        dir_path = resolved_path.rsplit('/', 1)[0] if '/' in resolved_path else '.'
        if dir_path and dir_path != '.':
            await self.env.run_shell(f"mkdir -p '{dir_path}'")

        await self.env.write_file(resolved_path, file_text)
        return {"status": "success", "stdout": f"File created: {path}"}

    async def _handle_str_replace(self, path: str, old_str: str, new_str: str = "") -> Dict[str, Any]:
        """Replace old_str with new_str in a file. old_str must be unique.

        :param path: Path relative to the workspace root (e.g., 'src/main.py').
        :param old_str: The exact string to replace. Must be unique in the file.
        :param new_str: The new string to replace old_str with.

        Best Practice: Include 1-2 lines of surrounding context in old_str to ensure uniqueness.
        Shows unified diff after successful replacement.
        """
        resolved_path = self._resolve_path(path)

        file_result = await self.env.read_file(resolved_path)
        if file_result.get("status") == "error":
            return file_result
        old_content = file_result.get("content") or file_result.get("stdout") or ""

        occurrences = old_content.count(old_str)
        if occurrences == 0:
            similar = self._find_similar_strings(old_str, old_content)
            error_msg = f"No occurrence of old_str found in {path}."
            if similar:
                error_msg += f"\n\nDid you mean...\n" + "\n".join([f"- {s}" for s in similar])
            raise ValueError(error_msg)
        elif occurrences > 1:
            lines_with_occurrence = []
            for i, line in enumerate(old_content.split("\n")):
                if old_str in line:
                    lines_with_occurrence.append(i + 1)
            raise ValueError(f"Multiple occurrences of old_str in lines {lines_with_occurrence}. Must be unique.")

        new_content = old_content.replace(old_str, new_str)

        if path.endswith(".py"):
            import ast
            try:
                ast.parse(new_content)
            except SyntaxError as e:
                diag = self._parse_python_error(e, new_content)
                return {
                    "status": "error",
                    "message": f"Python syntax error at line {diag['line_number']}: {diag['message']}",
                    "diagnostic": diag
                }

        await self.env.write_file(resolved_path, new_content)

        diff_output = self._generate_unified_diff(old_content, new_content, path)

        output = f"File updated: {path}"
        if diff_output:
            output += f"\n\n### 📝 Applied Changes (Unified Diff):\n{diff_output}"

        return {"status": "success", "stdout": output}

    async def _handle_insert(self, path: str, insert_line: int, new_str: str) -> Dict[str, Any]:
        """Insert new_str after the specified line number.

        :param path: Path relative to the workspace root (e.g., 'src/main.py').
        :param insert_line: Line number AFTER which to insert new_str (1-indexed).
        :param new_str: String to insert.

        Shows unified diff after successful insertion.
        """
        resolved_path = self._resolve_path(path)

        file_result = await self.env.read_file(resolved_path)
        if file_result.get("status") == "error":
            return file_result
        old_content = file_result.get("content") or file_result.get("stdout") or ""

        lines = old_content.split("\n")
        n_lines = len(lines)

        if insert_line < 0 or insert_line > n_lines:
            raise ValueError(f"Invalid insert_line: {insert_line}. File has {n_lines} lines.")

        new_lines = lines[:insert_line] + [new_str] + lines[insert_line:]
        new_content = "\n".join(new_lines)

        if path.endswith(".py"):
            import ast
            try:
                ast.parse(new_content)
            except SyntaxError as e:
                diag = self._parse_python_error(e, new_content)
                return {
                    "status": "error",
                    "message": f"Python syntax error at line {diag['line_number']}: {diag['message']}",
                    "diagnostic": diag
                }

        await self.env.write_file(resolved_path, new_content)

        diff_output = self._generate_unified_diff(old_content, new_content, path)

        output = f"Inserted after line {insert_line} in {path}"
        if diff_output:
            output += f"\n\n### 📝 Applied Changes (Unified Diff):\n{diff_output}"

        return {"status": "success", "stdout": output}

    async def _handle_search(self, path: str, keyword: str) -> Dict[str, Any]:
        """Search for a keyword in files within a directory using grep.

        :param path: Directory path relative to the workspace root (e.g., 'src').
        :param keyword: Keyword to search for.

        Shows first 10 matches with line numbers. Refine keyword if results are too many.
        """
        resolved_path = self._resolve_path(path)
        if not keyword or not keyword.strip():
            return {"status": "error", "message": "Keyword cannot be empty."}
        escaped_keyword = keyword.replace("'", "'\\''")
        cmd = f"grep -rnE --exclude-dir={{.git,.venv,node_modules}} --exclude={{*.pyc,*.egg-info}} '{escaped_keyword}' '{resolved_path}' 2>/dev/null | head -15"
        result = await self.env.run_shell(cmd)
        stdout = result.get("stdout", "")

        if not stdout.strip():
            return {"status": "success", "stdout": f"No matches found for '{keyword}' in {path}"}

        lines = stdout.strip().split("\n")
        total_matches = len(lines)

        display_lines = lines[:10]
        display_output = "\n".join(display_lines)

        output = f"### 🔍 Search Results for '{keyword}' in {path}\n\n{display_output}"

        if total_matches > 10:
            output += f"\n\nShowing first 10 matches, please refine your keyword if needed. (Total: {total_matches} matches)"

        return {"status": "success", "stdout": output}

    async def _handle_list_tree(self, path: str = ".", depth: int = 3) -> Dict[str, Any]:
        """List directory structure in a tree format.

        :param path: Directory path relative to the workspace root (e.g., 'src'). Defaults to current directory.
        :param depth: Maximum depth to traverse. Defaults to 3.

        Returns a tree-like representation of the directory structure.
        """
        resolved_path = self._resolve_path(path)

        if depth < 1:
            depth = 1
        if depth > 10:
            depth = 10

        cmd = f"find '{resolved_path}' -maxdepth {depth} -not -path '*/\\.*' -printf '%p\\n' 2>/dev/null | sort"
        result = await self.env.run_shell(cmd)
        raw_items = result.get("stdout", "").strip().split("\n")

        if not raw_items or raw_items == [""]:
            return {"status": "success", "stdout": f"Directory '{path}' is empty (depth: {depth})"}

        items = [item for item in raw_items if item and item != resolved_path]
        if not items:
            return {"status": "success", "stdout": f"Directory '{path}' is empty (depth: {depth})"}

        prefix = resolved_path.split('/')[-1] or resolved_path
        tree_lines = [f"### 🌳 Directory Tree: {path} (depth: {depth})\n", f"{prefix}/"]

        from collections import defaultdict
        children_map: Dict[str, List[str]] = defaultdict(list)
        all_nodes = set()

        for item in items:
            parent = item.rsplit('/', 1)[0] if '/' in item else resolved_path
            name = item.rsplit('/', 1)[-1] if '/' in item else item
            children_map[parent].append(name)
            all_nodes.add(item)

        def get_connector(is_last: bool) -> str:
            return "└── " if is_last else "├── "

        def build_subtree(parent_path: str, indent: str, is_last: bool):
            lines = []
            siblings = children_map.get(parent_path, [])
            for i, name in enumerate(sorted(siblings)):
                child_is_last = (i == len(siblings) - 1)
                connector = get_connector(child_is_last)
                full_path = f"{parent_path}/{name}" if parent_path != resolved_path else f"{resolved_path}/{name}"

                if full_path in all_nodes:
                    lines.append(f"{indent}{connector}{name}/")
                    extension = "    " if is_last else "│   "
                    lines.extend(build_subtree(full_path, indent + extension, child_is_last))
                else:
                    lines.append(f"{indent}{connector}{name}")
            return lines

        root_children = children_map.get(resolved_path, [])
        for i, name in enumerate(sorted(root_children)):
            child_is_last = (i == len(root_children) - 1)
            connector = get_connector(child_is_last)
            full_path = f"{resolved_path}/{name}"

            if full_path in all_nodes:
                tree_lines.append(f"{connector}{name}/")
                extension = "    " if child_is_last else "│   "
                tree_lines.extend(build_subtree(full_path, extension, child_is_last))
            else:
                tree_lines.append(f"{connector}{name}")

        output = "\n".join(tree_lines)
        return {"status": "success", "stdout": output}

    async def _handle_replace_lines(self, path: str, start_line: int, end_line: int, replacement: str = "") -> Dict[str, Any]:
        """Replace a range of lines with new content.

        Useful when str_replace fails due to whitespace differences.
        Line numbers are 1-indexed (inclusive range).

        :param path: Path relative to the workspace root (e.g., 'src/main.py').
        :param start_line: Starting line number (1-indexed, must be > 0).
        :param end_line: Ending line number (inclusive, must be >= start_line).
        :param replacement: Text to replace the specified lines with.
        :return: Confirmation with unified diff showing changes.
        """
        if start_line <= 0:
            return {"status": "error", "message": f"start_line must be > 0, got {start_line}."}
        if end_line < start_line:
            return {"status": "error", "message": f"end_line ({end_line}) must be >= start_line ({start_line})."}

        resolved_path = self._resolve_path(path)

        file_result = await self.env.read_file(resolved_path)
        if file_result.get("status") == "error":
            return file_result
        old_content = file_result.get("content") or file_result.get("stdout") or ""

        lines = old_content.split("\n")
        n_lines = len(lines)

        if start_line > n_lines:
            return {"status": "error", "message": f"start_line {start_line} exceeds file length ({n_lines} lines)."}
        if end_line > n_lines:
            return {"status": "error", "message": f"end_line {end_line} exceeds file length ({n_lines} lines)."}

        new_lines = lines[:start_line - 1] + [replacement] + lines[end_line:]
        new_content = "\n".join(new_lines)

        await self.env.write_file(resolved_path, new_content)

        diff_output = self._generate_unified_diff(old_content, new_content, path)

        output = f"Lines {start_line}-{end_line} replaced in {path}"
        if diff_output:
            output += f"\n\n### 📝 Applied Changes (Unified Diff):\n{diff_output}"

        return {"status": "success", "stdout": output}
