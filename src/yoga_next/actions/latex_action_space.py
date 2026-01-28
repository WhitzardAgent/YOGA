from typing import Dict, Any, List, Optional
from .base import ActionSpace
from difflib import unified_diff
import re
import os


WHITELIST_ACTIONS = {
    "map_project",
    "view_tex_env",
    "edit_tex_env",
    # "check_citations",
    # "compile_and_diagnose",
    "append_edit_rationale"
}


class LatexEditorActionSpace(ActionSpace):
    """
    Action Space for LaTeX Paper Editing.
    Provides structured tools for multi-file project navigation, environment-aware editing,
    citation checking, and compilation diagnostics.

    Tools: map_project, view_tex_env, edit_tex_env, check_citations, compile_and_diagnose, append_edit_rationale
    """

    def __init__(self, action_space_name: str = "latex_editor", env=None):
        super().__init__(action_space_name, env)

    async def execute(self, action_name: str, param_dict: Dict[str, Any]) -> Dict[str, Any]:
        if action_name not in WHITELIST_ACTIONS:
            return {
                "status": "error",
                "message": f"Action '{action_name}' not available. Use append_edit_rationale to record your editing insights."
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
        from os import getcwd
        return getcwd()

    def _resolve_path(self, path: str) -> str:
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
        resolved_path = self._resolve_path(path)
        result = await self.env.read_file(resolved_path)
        if result.get("status") == "error":
            raise FileNotFoundError(result.get("message"))
        return result.get("content") or result.get("stdout") or ""

    def _generate_unified_diff(self, old_content: str, new_content: str, path: str) -> str:
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

    async def _handle_map_project(self, main_tex_path: str = "main.tex") -> Dict[str, Any]:
        """Map the logical structure of a multi-file LaTeX project.

        Recursively scans \\input{} and \\include{} directives to build a tree
        showing the logical organization and corresponding file paths.

        :param main_tex_path: Path to the main .tex file relative to workspace root.
        :return: Markdown-formatted project structure tree.
        """
        resolved_path = self._resolve_path(main_tex_path)
        main_dir = os.path.dirname(resolved_path)

        project_tree = []
        processed_files = set()

        def scan_file(file_path: str, level: int, parent_key: str = "") -> List[str]:
            lines = []
            if file_path in processed_files:
                return [f"{'  ' * level}- **[Circular] {os.path.basename(file_path)}**"]
            processed_files.add(file_path)

            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
            except Exception:
                return [f"{'  ' * level}- **Error reading: {file_path}**"]

            file_name = os.path.basename(file_path)
            lines.append(f"{'  ' * level}- **{file_name}**")

            for i, line in enumerate(content.splitlines()):
                line = line.strip()

                input_match = re.search(r'\\input\{([^}]+)\}', line)
                include_match = re.search(r'\\include\{([^}]+)\}', line)

                if input_match:
                    rel_path = input_match.group(1)
                    if not rel_path.endswith('.tex'):
                        rel_path += '.tex'
                    child_path = os.path.join(main_dir, rel_path)
                    if os.path.exists(child_path):
                        lines.extend(scan_file(child_path, level + 1))

                elif include_match:
                    rel_path = include_match.group(1)
                    if not rel_path.endswith('.tex'):
                        rel_path += '.tex'
                    child_path = os.path.join(main_dir, rel_path)
                    if os.path.exists(child_path):
                        lines.extend(scan_file(child_path, level + 1))

            return lines

        project_tree = scan_file(resolved_path, 0)
        output = "### 📂 LaTeX Project Structure\n\n" + "\n".join(project_tree)
        return {"status": "success", "stdout": output}

    async def _handle_view_tex_env(self, path: str, env_name: str = None, label: str = None) -> Dict[str, Any]:
        """View a specific LaTeX environment by name or label.

        Extracts content between \\begin{env_name} and \\end{env_name},
        or content containing \\label{label}.

        :param path: Path to the .tex file relative to workspace root.
        :param env_name: Environment name (e.g., 'equation', 'figure', 'algorithm').
        :param label: Optional label to search for (e.g., 'eq:main').
        :return: The extracted environment content with context.
        """
        content = await self._read_file_content(path)
        lines = content.splitlines()

        if label:
            pattern = rf'\\label\{{{re.escape(label)}\}}'
            for i, line in enumerate(lines):
                if re.search(pattern, line):
                    start = max(0, i - 5)
                    end = min(len(lines), i + 5)
                    context = "\n".join(lines[start:end])
                    return {
                        "status": "success",
                        "stdout": f"### 🏷️ Label: {label}\n\n**Context:**\n{context}"
                    }
            return {"status": "error", "message": f"Label '{label}' not found."}

        if not env_name:
            return {"status": "error", "message": "Either env_name or label must be provided."}

        env_pattern = re.compile(
            rf'\\begin\{{{re.escape(env_name)}\}}(.*?)\\end\{{{re.escape(env_name)}\}}',
            re.DOTALL
        )

        matches = list(env_pattern.finditer(content))

        if not matches:
            return {"status": "success", "stdout": f"No environment '{env_name}' found."}

        output = f"### 📐 LaTeX Environments: {env_name}\n\n"
        for idx, match in enumerate(matches):
            env_content = match.group(1).strip()
            output += f"**Instance {idx + 1}**\n```latex\n\\begin{{{env_name}}}\n{env_content}\n\\end{{{env_name}}}\n```\n\n"

        return {"status": "success", "stdout": output}

    async def _handle_edit_tex_env(self, path: str, env_name: str, old_str: str, new_str: str = "") -> Dict[str, Any]:
        """Edit content within a specific LaTeX environment.

        Replaces old_str with new_str only within the specified environment,
        preserving LaTeX structure integrity.

        :param path: Path to the .tex file relative to workspace root.
        :param env_name: Environment name (e.g., 'equation', 'figure').
        :param old_str: The exact string to replace within the environment.
        :param new_str: The new string to replace old_str with.
        :return: Unified diff showing changes.
        """
        resolved_path = self._resolve_path(path)
        old_content = await self._read_file_content(path)

        env_pattern = re.compile(
            rf'(\\begin\{{{re.escape(env_name)}\}})(.*?)(\\end\{{{re.escape(env_name)}\}})',
            re.DOTALL
        )

        def replace_in_env(match):
            prefix = match.group(1)
            env_body = match.group(2)
            suffix = match.group(3)

            if old_str in env_body:
                new_body = env_body.replace(old_str, new_str)
                return prefix + new_body + suffix
            return match.group(0)

        new_content = env_pattern.sub(replace_in_env, old_content)

        if new_content == old_content:
            return {"status": "error", "message": f"No occurrence of old_str found in \\begin{{{env_name}}}...\\end{{{env_name}}}."}

        if path.endswith(".tex"):
            import subprocess
            try:
                subprocess.run(
                    ["pdflatex", "-interaction=nonstopmode", "-halt-on-error", resolved_path],
                    capture_output=True,
                    timeout=30
                )
            except Exception:
                pass

        await self.env.write_file(resolved_path, new_content)

        diff_output = self._generate_unified_diff(old_content, new_content, path)
        output = f"Environment updated in {path}"
        if diff_output:
            output += f"\n\n### 📝 Applied Changes:\n{diff_output}"

        return {"status": "success", "stdout": output}

    # async def _handle_check_citations(self, tex_path: str, bib_path: str = None) -> Dict[str, Any]:
    #     """Check citation consistency between .tex and .bib files.

    #     Extracts all \\cite{} keys from the .tex file and compares against
    #     the .bib file to find missing or unused entries.

    #     :param tex_path: Path to the .tex file relative to workspace root.
    #     :param bib_path: Optional path to the .bib file. If not provided, searches for .bib in same directory.
    #     :return: Missing citations and unused bib entries.
    #     """
    #     tex_content = await self._read_file_content(tex_path)

    #     cite_pattern = re.compile(r'\\cite\{([^}]+)\}')
    #     tex_citations = set()
    #     for match in cite_pattern.finditer(tex_content):
    #         keys = match.group(1).split(',')
    #         for key in keys:
    #             tex_citations.add(key.strip())

    #     bib_keys = set()
    #     if bib_path:
    #         bib_content = await self._read_file_content(bib_path)
    #     else:
    #         tex_dir = os.path.dirname(self._resolve_path(tex_path))
    #         bib_files = [f for f in os.listdir(tex_dir) if f.endswith('.bib')]
    #         if bib_files:
    #             bib_content = await self._read_file_content(os.path.join(tex_dir, bib_files[0]))
    #         else:
    #             bib_content = ""

    #     entry_pattern = re.compile(r'@(\w+)\s*\{([^,]+),')
    #     for match in entry_pattern.finditer(bib_content):
    #         bib_keys.add(match.group(2).strip())

    #     missing = tex_citations - bib_keys
    #     unused = bib_keys - tex_citations

    #     output = "### 📚 Citation Check Report\n\n"

    #     if missing:
    #         output += f"**Missing in .bib ({len(missing)}):**\n" + "\n".join([f"- `{k}`" for k in sorted(missing)]) + "\n\n"
    #     else:
    #         output += "**All cited references are present in .bib file.**\n\n"

    #     if unused:
    #         output += f"**Unused in .tex ({len(unused)}):**\n" + "\n".join([f"- `{k}`" for k in sorted(unused)]) + "\n"
    #     else:
    #         output += "**All .bib entries are referenced in .tex file.**\n"

    #     return {"status": "success", "stdout": output}

    # async def _handle_compile_and_diagnose(self, tex_path: str, engine: str = "pdflatex") -> Dict[str, Any]:
    #     """Compile LaTeX and extract diagnostics from .log file.

    #     :param tex_path: Path to the .tex file relative to workspace root.
    #     :param engine: Compiler to use ('pdflatex' or 'latexmk'). Default: pdflatex.
    #     :return: Compilation result with extracted errors and warnings.
    #     """
    #     import subprocess
    #     import time

    #     resolved_path = self._resolve_path(tex_path)
    #     tex_dir = os.path.dirname(resolved_path)
    #     base_name = os.path.splitext(os.path.basename(resolved_path))[0]
    #     log_path = os.path.join(tex_dir, f"{base_name}.log")

    #     cmd = [engine, "-interaction=nonstopmode", "-halt-on-error", resolved_path]
    #     if engine == "latexmk":
    #         cmd = ["latexmk", "-pdf", "-interaction=nonstopmode", resolved_path]

    #     try:
    #         result = subprocess.run(
    #             cmd,
    #             capture_output=True,
    #             text=True,
    #             timeout=120,
    #             cwd=tex_dir
    #         )
    #     except subprocess.TimeoutExpired:
    #         return {"status": "error", "message": "Compilation timed out (120s)."}

    #     output_lines = []
    #     output_lines.append(f"**Compiler:** {engine}")
    #     output_lines.append(f"**Return Code:** {result.returncode}")

    #     if os.path.exists(log_path):
    #         with open(log_path, 'r', encoding='utf-8', errors='ignore') as f:
    #             log_content = f.read()

    #         error_lines = []
    #         warning_count = 0

    #         for line in log_content.splitlines():
    #             if re.search(r'^!|error', line, re.IGNORECASE):
    #                 error_lines.append(line.strip())
    #             elif re.search(r'warning', line, re.IGNORECASE):
    #                 warning_count += 1

    #         output_lines.append(f"**Log File:** {log_path}")

    #         if error_lines:
    #             output_lines.append(f"\n**Errors ({len(error_lines)}):**\n")
    #             for err in error_lines[:20]:
    #                 output_lines.append(f"```\n{err}\n```")
    #             if len(error_lines) > 20:
    #                 output_lines.append(f"\n... and {len(error_lines) - 20} more errors")
    #         else:
    #             output_lines.append("\n**No errors found in log.**")

    #         output_lines.append(f"\n**Warnings:** {warning_count}")

    #     output = "\n".join(output_lines)
    #     return {"status": "success", "stdout": output}

    async def _handle_append_edit_rationale(self, note_entry: str, file_name: str, edit_type: str = "General", notebook_name: str = "editing_log") -> Dict[str, Any]:
        """Append an editing rationale to the editing log.

        Records modification suggestions and academic refinement reasons.

        :param note_entry: The rationale content to save.
        :param file_name: The .tex file being edited.
        :param edit_type: Type of edit (e.g., 'Logic', 'Grammar', 'Math', 'Formatting').
        :param notebook_name: Name of the log file (without .md extension).
        :return: Confirmation of note saved.
        """
        from datetime import datetime
        import os

        workspace_root = self._get_workspace_root()
        if not notebook_name.endswith(".md"):
            notebook_name += ".md"
        log_path = os.path.join(workspace_root, notebook_name)

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        markdown_entry = f"## [{file_name}] - [{edit_type}] - {timestamp}\n\n{note_entry}\n\n---\n\n"

        with open(log_path, "a", encoding="utf-8") as f:
            f.write(markdown_entry)

        return {"status": "success", "stdout": f"Rationale appended to {notebook_name} [{file_name} - {edit_type}]"}
