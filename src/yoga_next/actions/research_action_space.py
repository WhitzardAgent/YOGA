from typing import Dict, Any, List
from .base import ActionSpace


class ResearchActionSpace(ActionSpace):
    """
    Action Space for AI Scientist Agent.
    Enables structured reading, multi-modal extraction (tables/formulas), and insight mining
    from Markdown-formatted research papers. Supports "thought skeleton" extraction for
    understanding research logic, formulas, and ablation studies.
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

    async def _read_file_content(self, path: str) -> str:
        """Helper to read file content safely."""
        resolved_path = self._resolve_path(path)
        result = await self.env.read_file(resolved_path)
        if result.get("status") == "error":
            raise FileNotFoundError(result.get("message"))
        return result.get("content") or result.get("stdout") or ""

    async def _handle_get_outline(self, path: str) -> Dict[str, Any]:
        """Extract the header structure (TOC) of the paper.

        :param path: Path to the markdown paper relative to workspace root.
        :return: Formatted outline with line numbers.
        """
        content = await self._read_file_content(path)
        lines = content.splitlines()
        outline = []
        for i, line in enumerate(lines):
            if line.strip().startswith("#"):
                outline.append(f"Line {i+1}: {line.strip()}")

        if not outline:
            return {"status": "success", "stdout": "No headers found in the paper."}

        return {
            "status": "success",
            "stdout": f"### 📑 Paper Outline: {path}\n\n" + "\n".join(outline)
        }

    async def _handle_read_section(self, path: str, section_title: str) -> Dict[str, Any]:
        """Read a specific section based on its exact title from the outline.

        :param path: Path to the markdown paper relative to workspace root.
        :param section_title: The exact header title to find (e.g., '## 3. Methodology').
        :return: The full section content including headers.
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
            return {"status": "error", "message": f"Section '{section_title}' not found. Use get_outline to see available sections."}

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
            "stdout": f"### 📖 Section: {section_title}\n\n{section_content}"
        }

    async def _handle_extract_tables(self, path: str) -> Dict[str, Any]:
        """Extract all markdown tables and convert them to structured format.

        Useful for extracting SOTA results, dataset statistics, and comparison data.
        Tables are identified by | separators and must have at least header and divider.

        :param path: Path to the markdown paper relative to workspace root.
        :return: Extracted tables in original markdown format.
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
                if in_table:
                    if len(current_table) >= 2:
                        tables.append("\n".join(current_table))
                    current_table = []
                    in_table = False

        if in_table and len(current_table) >= 2:
            tables.append("\n".join(current_table))

        if not tables:
            return {"status": "success", "stdout": "No structured tables found in the paper."}

        output = "### 📊 Extracted Tables:\n\n"
        for idx, table in enumerate(tables):
            output += f"**Table {idx+1}**\n{table}\n\n"

        return {"status": "success", "stdout": output}

    async def _handle_extract_formulas(self, path: str) -> Dict[str, Any]:
        """Extract LaTeX display math formulas ($$ ... $$) with surrounding context.

        For each formula, extracts: the LaTeX, definition description (2 lines before),
        and parameter meanings (2 lines after). This helps understand formulas as
        logical primitives with physical meaning.

        :param path: Path to the markdown paper relative to workspace root.
        :return: Formulas with rich context including definitions and parameters.
        """
        import re

        content = await self._read_file_content(path)
        lines = content.splitlines()

        formula_pattern = re.compile(r'\$\$(.*?)\$\$', re.DOTALL)
        matches = list(formula_pattern.finditer(content))

        if not matches:
            return {"status": "success", "stdout": "No display math formulas ($$ ... $$) found."}

        output = "### 🧮 Formulas with Context:\n\n"

        for idx, match in enumerate(matches):
            clean_math = match.group(1).strip()
            formula_start_pos = match.start()
            formula_line_num = content[:formula_start_pos].count('\n') + 1

            context_before = []
            context_after = []

            start_line = max(0, formula_line_num - 3)
            end_line = min(len(lines), formula_line_num + 2)

            for i in range(start_line, formula_line_num - 1):
                if lines[i].strip() and not lines[i].strip().startswith('#'):
                    context_before.append(lines[i].strip())
                elif lines[i].strip().startswith('#'):
                    break

            for i in range(formula_line_num, min(len(lines), formula_line_num + 3)):
                if lines[i].strip() and not lines[i].strip().startswith('#'):
                    context_after.append(lines[i].strip())
                elif lines[i].strip().startswith('#'):
                    break

            output += f"**Formula {idx+1}** (Line {formula_line_num})\n\n"
            output += f"```latex\n{clean_math}\n```\n\n"

            if context_before:
                output += f"*📝 Definition Context (2 lines before):*\n"
                output += f"> {' '.join(context_before[-2:])}\n\n"

            if context_after:
                output += f"*🔢 Parameter Meanings (2 lines after):*\n"
                output += f"> {' '.join(context_after[:2])}\n\n"

            output += "---\n\n"

        return {"status": "success", "stdout": output}

    async def _handle_extract_logic_chains(self, path: str) -> Dict[str, Any]:
        """Extract causal logic chains from the paper.

        Scans for trigger words indicating causal relationships: "therefore", "to address",
        "consequently", "by introducing", "instead of". Returns full paragraphs with line
        numbers to help extract [Problem -> Mechanism -> Effect] chains.

        :param path: Path to the markdown paper relative to workspace root.
        :return: Causal logic chains with trigger words and context.
        """
        content = await self._read_file_content(path)
        lines = content.splitlines()

        trigger_keywords = [
            "therefore", "thus", "hence", "consequently",
            "to address", "in order to", "for the purpose of",
            "by introducing", "by proposing", "by leveraging",
            "instead of", "rather than", "in contrast to",
            "as a result", "which leads to", "this enables"
        ]

        chains = []
        current_paragraph = []
        current_start_line = 0

        for i, line in enumerate(lines):
            line_lower = line.lower().strip()
            current_paragraph.append(line)

            if not line.strip() or i == len(lines) - 1:
                paragraph_text = " ".join(current_paragraph)
                paragraph_lower = paragraph_text.lower()

                for keyword in trigger_keywords:
                    if keyword in paragraph_lower:
                        chains.append({
                            "line_number": current_start_line + 1,
                            "trigger_word": keyword,
                            "context": paragraph_text.strip()[:500]
                        })
                        break

                current_paragraph = []
                current_start_line = i + 1

        if not chains:
            return {"status": "success", "stdout": "No causal logic chains found."}

        output = "### 🔗 Causal Logic Chains:\n\n"
        output += "_Extracted [Problem -> Mechanism -> Effect] patterns_\n\n"

        for idx, chain in enumerate(chains):
            output += f"**Chain {idx+1}** (Line {chain['line_number']})\n"
            output += f"*Trigger: \"{chain['trigger_word']}\"*\n\n"
            output += f"{chain['context']}\n\n"
            output += "---\n\n"

        return {"status": "success", "stdout": output}

    async def _handle_analyze_ablation_logic(self, path: str) -> Dict[str, Any]:
        """Analyze ablation study logic and component contributions.

        Locates paragraphs discussing ablation experiments with keywords like:
        "ablation", "component-wise", "without the", "remove", "w/o".
        Extracts insights about which model components are most critical.

        :param path: Path to the markdown paper relative to workspace root.
        :return: Ablation study analysis with component importance insights.
        """
        content = await self._read_file_content(path)
        lines = content.splitlines()

        ablation_keywords = [
            "ablation", "ablate", "component-wise", "component wise",
            "without the", "without our", "remove the", "removing",
            "w/o the", "drop the", "leave out", "excluding"
        ]

        ablation_sections = []
        current_section = []
        start_line = 0
        in_ablation = False

        for i, line in enumerate(lines):
            line_lower = line.lower().strip()
            is_ablation = any(kw in line_lower for kw in ablation_keywords)

            if is_ablation:
                if not in_ablation:
                    start_line = i
                    current_section = []
                    in_ablation = True
                current_section.append(line)
            else:
                if in_ablation and current_section:
                    context_start = max(0, start_line - 1)
                    context_end = min(len(lines), i + 2)
                    full_context = "\n".join(lines[context_start:context_end])
                    ablation_sections.append({
                        "start_line": start_line + 1,
                        "content": full_context.strip()
                    })
                in_ablation = False
                current_section = []

        if current_section:
            context_start = max(0, start_line - 1)
            context_end = min(len(lines), len(lines))
            full_context = "\n".join(lines[context_start:context_end])
            ablation_sections.append({
                "start_line": start_line + 1,
                "content": full_context.strip()
            })

        if not ablation_sections:
            return {"status": "success", "stdout": "No ablation study sections found."}

        output = "### 🔬 Ablation Study Analysis:\n\n"
        output += "_Component importance insights from ablation experiments_\n\n"

        for idx, section in enumerate(ablation_sections):
            output += f"**Ablation Section {idx+1}** (Line {section['start_line']})\n\n"
            output += f"{section['content']}\n\n"
            output += "---\n\n"

        return {"status": "success", "stdout": output}

    async def _handle_scan_insights(self, path: str) -> Dict[str, Any]:
        """Scan for research gaps, limitations, and suboptimal patterns.

        Searches for keywords indicating research boundaries, technical limitations,
        and areas for improvement. These are critical for generating hypotheses.

        :param path: Path to the markdown paper relative to workspace root.
        :return: Formatted insights with research gaps and limitations.
        """
        content = await self._read_file_content(path)
        lines = content.splitlines()

        keywords = [
            "however", "although", "limitation", "drawback", "limitation",
            "surprisingly", "future work", "remain", "challenge",
            "potential", "we leave", "addressed in", "not yet",
            "suboptimal", "bottleneck", "trade-off", "tradeoff",
            "computationally expensive", "high computational",
            "not significantly", "no significant", "marginal",
            "missing", "ignored", "assumes", "assuming"
        ]

        hits = []
        for i, line in enumerate(lines):
            lower_line = line.lower()
            if any(k in lower_line for k in keywords):
                start = max(0, i - 1)
                end = min(len(lines), i + 2)
                context = "\n".join(lines[start:end])
                matched_kw = [k for k in keywords if k in lower_line][0]
                hits.append({
                    "line": i + 1,
                    "keyword": matched_kw,
                    "context": context.strip()
                })

        if not hits:
            return {"status": "success", "stdout": "No obvious research gaps or limitations found."}

        output = "### 💡 Research Gaps & Limitations:\n\n"
        output += "_Key patterns for hypothesis generation_\n\n"

        for idx, hit in enumerate(hits):
            output += f"**Insight {idx+1}** (Line {hit['line']}, keyword: \"{hit['keyword']}\")\n\n"
            output += f">>> {hit['context']}\n\n"
            output += "---\n\n"

        return {"status": "success", "stdout": output}

    async def _handle_find_citations(self, path: str, query: str) -> Dict[str, Any]:
        """Find all contexts where a specific paper, author, or topic is cited.

        Useful for understanding relationships to baseline methods and related work.

        :param path: Path to the markdown paper relative to workspace root.
        :param query: Keyword or paper title to search for in citations.
        :return: Line-by-line citation contexts (max 10).
        """
        content = await self._read_file_content(path)
        lines = content.splitlines()

        hits = []
        for i, line in enumerate(lines):
            if query.lower() in line.lower():
                hits.append(f"**Line {i+1}**: {line.strip()}")

        if not hits:
            return {"status": "success", "stdout": f"No citations found for '{query}'."}

        output = f"### 🔗 Citations for '{query}':\n\n" + "\n".join(hits[:10])
        if len(hits) > 10:
            output += f"\n\n... and {len(hits) - 10} more matches (refine query to see all)"
        return {"status": "success", "stdout": output}

    async def _handle_append_to_notebook(self, note_entry: str, category: str = "general") -> Dict[str, Any]:
        """Save a structured note to the agent's research notebook.

        Acts as short-term memory for hypothesis generation and evidence tracking.
        Notes are appended to research_notebook.jsonl in the workspace root.

        :param note_entry: The note content to save.
        :param category: Category tag (e.g., 'hypothesis', 'evidence', 'baseline_metric', 'todo').
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

        return {"status": "success", "stdout": f"Note saved to research_notebook.jsonl [category: {category}]"}

    async def _handle_read_paper_summary(self, path: str) -> Dict[str, Any]:
        """Generate a structured summary of the paper including key sections.

        Extracts: Title, Abstract, Introduction, Methodology, Results, and Conclusion.

        :param path: Path to the markdown paper relative to workspace root.
        :return: Structured summary in markdown format.
        """
        content = await self._read_file_content(path)
        lines = content.splitlines()

        summary_sections = {}

        section_patterns = {
            "abstract": ["# Abstract", "## Abstract", "### Abstract"],
            "introduction": ["# Introduction", "## Introduction", "### Introduction"],
            "methodology": ["# Methodology", "## Methodology", "### Methodology", "# Method", "## Method"],
            "results": ["# Results", "## Results", "### Results", "# Experiments", "## Experiments"],
            "conclusion": ["# Conclusion", "## Conclusion", "### Conclusion"],
        }

        def extract_section(start_idx: int, end_idx: int) -> str:
            return "\n".join(lines[start_idx:end_idx]).strip()

        for i, line in enumerate(lines):
            line_stripped = line.strip().lower()
            for section_name, patterns in section_patterns.items():
                for pattern in patterns:
                    if pattern.lower() in line_stripped and line.startswith("#"):
                        target_level = len(line.split()[0])
                        end_idx = len(lines)
                        for j in range(i + 1, len(lines)):
                            if lines[j].strip().startswith("#"):
                                level = len(lines[j].split()[0])
                                if level <= target_level:
                                    end_idx = j
                                    break
                        section_content = extract_section(i, end_idx)
                        if section_content:
                            summary_sections[section_name] = section_content[:500]
                        break

        output = "### 📋 Paper Summary\n\n"

        title = lines[0] if lines else "Untitled"
        output += f"**Title**: {title}\n\n"

        for section_name, content in summary_sections.items():
            output += f"**{section_name.title()}**\n{content[:300]}...\n\n"

        if not summary_sections:
            output += "_No structured sections found. Use read_section to explore specific parts._"

        return {"status": "success", "stdout": output}

    async def _handle_find_figures(self, path: str) -> Dict[str, Any]:
        """Locate all figure and table captions in the paper.

        Useful for quickly understanding visual materials and their descriptions.

        :param path: Path to the markdown paper relative to workspace root.
        :return: List of figure/table captions with their line numbers.
        """
        content = await self._read_file_content(path)
        lines = content.splitlines()

        figures = []
        for i, line in enumerate(lines):
            line_lower = line.lower()
            if ("figure" in line_lower or "fig." in line_lower or "fig " in line_lower) and line.strip().startswith("|"):
                figures.append(f"**Line {i+1}**: {line.strip()}")
            elif ("table" in line_lower or "tab." in line_lower) and line.strip().startswith("|"):
                figures.append(f"**Line {i+1}**: {line.strip()}")

        if not figures:
            return {"status": "success", "stdout": "No figure/table captions found."}

        return {
            "status": "success",
            "stdout": "### 🖼️ Figures & Tables\n\n" + "\n".join(figures)
        }

    async def _handle_get_research_context(self, path: str) -> Dict[str, Any]:
        """Extract the "worldview" of the paper.

        Captures: First 3 paragraphs of Introduction, all of Conclusion, and
        sentences containing "assume", "presuppose", "observation".
        This reveals the paper's foundational assumptions and high-level claims.

        :param path: Path to the markdown paper relative to workspace root.
        :return: Research worldview with assumptions and key observations.
        """
        content = await self._read_file_content(path)
        lines = content.splitlines()

        output = "### 🌍 Research Worldview\n\n"

        intro_start = -1
        intro_end = -1
        conclusion_start = -1
        conclusion_end = -1

        for i, line in enumerate(lines):
            line_lower = line.strip().lower()
            if line.startswith("#"):
                level = len(line.split()[0])

                if intro_start == -1 and "introduction" in line_lower:
                    intro_start = i + 1
                    for j in range(i + 1, len(lines)):
                        if lines[j].strip().startswith("#"):
                            intro_end = j
                            break
                    if intro_end == -1:
                        intro_end = min(i + 15, len(lines))

                elif "conclusion" in line_lower or "conclusions" in line_lower:
                    conclusion_start = i + 1
                    conclusion_end = len(lines)
                    break

        if intro_start != -1 and intro_start < len(lines):
            intro_lines = lines[intro_start:intro_end]
            non_empty_lines = [l for l in intro_lines if l.strip() and not l.strip().startswith('#')]
            first_3_paragraphs = []
            current_para = []

            for line in non_empty_lines:
                if line.strip():
                    current_para.append(line.strip())
                if len(current_para) >= 3:
                    first_3_paragraphs.append(" ".join(current_para[:3]))
                    break
                elif not line.strip() and current_para:
                    first_3_paragraphs.append(" ".join(current_paragraphs))
                    current_para = []

            output += "**Introduction (First 3 paragraphs)**\n\n"
            for para in first_3_paragraphs[:3]:
                output += f"> {para[:300]}...\n\n"

        if conclusion_start != -1:
            conclusion_lines = lines[conclusion_start:conclusion_end]
            conclusion_text = " ".join([l.strip() for l in conclusion_lines if l.strip()])
            if conclusion_text:
                output += "**Conclusion**\n\n"
                output += f"> {conclusion_text[:500]}...\n\n"

        assumption_keywords = ["assume", "presuppose", "suppose", "observation", "observe"]
        assumptions = []

        for i, line in enumerate(lines):
            line_lower = line.lower().strip()
            if any(kw in line_lower for kw in assumption_keywords) and len(line) > 20:
                assumptions.append(f"**Line {i+1}**: {line.strip()}")

        if assumptions:
            output += "**Assumptions & Observations**\n\n"
            for assump in assumptions[:10]:
                output += f"{assump}\n"
            if len(assumptions) > 10:
                output += f"\n... and {len(assumptions) - 10} more\n"

        return {"status": "success", "stdout": output}
