from typing import Dict, Any, List
from .base import ActionSpace


class ResearchActionSpace(ActionSpace):
    """
    Minimalist Action Space for AI Scientist Agent.
    Provides basic navigation tools - logic analysis is delegated to the LLM.

    Tools: get_outline, read_section, append_to_notebook
    """

    def __init__(self, action_space_name: str = "research", env=None):
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
        """Get workspace_root from environment config."""
        if hasattr(self.env, 'config') and isinstance(self.env.config, dict):
            return self.env.config.get("workspace_root", self.env.workspace_root)
        if hasattr(self.env, 'workspace_root'):
            return self.env.workspace_root
        from os import getcwd
        return getcwd()

    def _resolve_path(self, path: str) -> str:
        """Resolve path relative to workspace_root with security check."""
        from pathlib import Path
        import os

        workspace_root = self._get_workspace_root()
        workspace_resolved = Path(workspace_root).resolve()

        relative_path = path.lstrip("/")
        abs_path = (workspace_resolved / relative_path).resolve()

        if not str(abs_path).startswith(str(workspace_resolved) + os.sep) and abs_path != workspace_resolved:
            raise PermissionError(f"Access denied: '{path}' outside workspace.")

        return str(abs_path)

    async def _read_file_content(self, path: str) -> str:
        """Read file content safely."""
        resolved_path = self._resolve_path(path)
        result = await self.env.read_file(resolved_path)
        if result.get("status") == "error":
            raise FileNotFoundError(result.get("message"))
        return result.get("content") or result.get("stdout") or ""

    async def _handle_get_outline(self, path: str) -> Dict[str, Any]:
        """Extract markdown header structure as a navigation map.

        :param path: Path to the markdown paper relative to workspace root.
        :return: List of headers with their line numbers.
        """
        content = await self._read_file_content(path)
        lines = content.splitlines()

        outline = []
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith("#"):
                level = len(stripped.split()[0])
                title = stripped.split(None, 1)[1] if " " in stripped else stripped
                outline.append({
                    "line": i + 1,
                    "level": level,
                    "title": title
                })

        return {
            "status": "success",
            "stdout": outline
        }

    async def _handle_read_section(self, path: str, section_title: str) -> Dict[str, Any]:
        """Read content from a specific section by title.

        :param path: Path to the markdown paper relative to workspace root.
        :param section_title: The exact header title to find.
        :return: Full section content including all subsections.
        """
        content = await self._read_file_content(path)
        lines = content.splitlines()

        start_index = -1
        target_level = 0

        for i, line in enumerate(lines):
            if section_title in line and line.strip().startswith("#"):
                start_index = i
                target_level = len(line.split()[0])
                break

        if start_index == -1:
            return {"status": "error", "message": f"Section '{section_title}' not found."}

        end_index = len(lines)
        for i in range(start_index + 1, len(lines)):
            line = lines[i].strip()
            if line.startswith("#"):
                level = len(line.split()[0])
                if level <= target_level:
                    end_index = i
                    break

        section_content = "\n".join(lines[start_index:end_index])
        return {
            "status": "success",
            "stdout": section_content
        }

    async def _handle_append_to_notebook(self, note_entry: str, category: str = "general") -> Dict[str, Any]:
        """Save a structured note to the research notebook.

        :param note_entry: The note content to save.
        :param category: Category tag (e.g., 'hypothesis', 'evidence', 'todo').
        :return: Confirmation of note saved.
        """
        import json
        import time

        workspace_root = self._get_workspace_root()
        notebook_path = f"{workspace_root}/research_notebook.jsonl"

        entry = {
            "timestamp": time.time(),
            "category": category,
            "content": note_entry
        }

        json_str = json.dumps(entry, ensure_ascii=False)
        await self.env.run_shell(f"echo '{json_str}' >> '{notebook_path}'")

        return {"status": "success", "stdout": f"Note saved [category: {category}]"}

    async def _handle_search_keyword(self, path: str, query: str, context_lines: int = 2) -> Dict[str, Any]:
        """Search for keyword in the document with surrounding context.

        :param path: Path to the markdown paper relative to workspace root.
        :param query: Keyword to search for (case-insensitive).
        :param context_lines: Number of context lines before/after each match (default: 2).
        :return: Matches with context, max 10 results.
        """
        content = await self._read_file_content(path)
        lines = content.splitlines()
        matches = []

        for i, line in enumerate(lines):
            if query.lower() in line.lower():
                start = max(0, i - context_lines)
                end = min(len(lines), i + context_lines + 1)
                context = lines[start:end]
                matches.append({
                    "line": i + 1,
                    "context": "\n".join(context)
                })

        if not matches:
            return {"status": "success", "stdout": f"No matches found for '{query}'."}

        output = f"### 🔍 Search Results for '{query}'\n\n"
        for idx, m in enumerate(matches[:10]):
            output += f"**Match {idx+1}** (Line {m['line']}):\n{m['context']}\n\n"
            if len(matches) > 10:
                output += f"... and {len(matches) - 10} more matches"

        return {"status": "success", "stdout": output}

    async def _handle_extract_all_tables(self, path: str) -> Dict[str, Any]:
        """Extract all markdown tables from the document.

        :param path: Path to the markdown paper relative to workspace root.
        :return: All tables in original markdown format with table numbers.
        """
        content = await self._read_file_content(path)
        lines = content.splitlines()

        tables = []
        current_table = []
        in_table = False

        for line in lines:
            stripped = line.strip()
            if stripped.startswith("|") and stripped.endswith("|"):
                current_table.append(stripped)
                in_table = True
            else:
                if in_table and len(current_table) >= 2:
                    tables.append("\n".join(current_table))
                current_table = []
                in_table = False

        if in_table and len(current_table) >= 2:
            tables.append("\n".join(current_table))

        if not tables:
            return {"status": "success", "stdout": "No tables found."}

        output = "### 📊 Extracted Tables\n\n"
        for idx, table in enumerate(tables):
            output += f"**Table {idx+1}**\n{table}\n\n"

        return {"status": "success", "stdout": output}
