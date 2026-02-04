import re
import os
import base64
from typing import Dict, Any, List, Optional
from openai import OpenAI

class MarkdownActionSpace:
    """
    Action Space designed for parsing security write-ups (Markdown) and extracting 
    structured execution trajectories. 
    
    This class integrates local file parsing with local Multimodal AI (OCR) capabilities.
    """

    def __init__(self, workspace_root: str):
        """
        Initialize the action space with a workspace root and OCR client.

        :param workspace_root: The root directory where markdown files and images are located.
        """
        self.workspace_root = workspace_root
        
        # Initialize connection to Local OCR Model (PaddleOCR-VL via OpenAI-compatible API)
        self.ocr_client = OpenAI(
            api_key="EMPTY",
            base_url="http://localhost:8011/v1",
            timeout=3600
        )
        
        # Task prompts for the multimodal model
        self.ocr_tasks = {
            "ocr": "OCR:",
            "table": "Table Recognition:",
            "formula": "Formula Recognition:",
            "chart": "Chart Recognition:",
        }

    async def _read_file_content(self, path: str) -> str:
        """
        Internal helper to read file content safely.

        :param path: Relative path to the file.
        :return: String content of the file.
        :raises FileNotFoundError: If the file does not exist.
        """
        full_path = os.path.join(self.workspace_root, path)
        if not os.path.exists(full_path):
            raise FileNotFoundError(f"File not found: {path}")
        with open(full_path, 'r', encoding='utf-8') as f:
            return f.read()

    def _encode_image_to_base64(self, image_path: str) -> str:
        """
        Internal helper to convert a local image file to a base64 string.

        :param image_path: Absolute path to the image file.
        :return: Base64 encoded string of the image.
        """
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode('utf-8')

    async def _handle_perform_ocr(self, image_relative_path: str, mode: str = "ocr") -> Dict[str, Any]:
        """
        Executes OCR on a local image file using the locally deployed multimodal model.
        This is used to extract text from screenshots (e.g., terminal outputs, web errors).

        :param image_relative_path: The path to the image relative to workspace_root (e.g., "images/nmap_scan.png").
        :param mode: The specific recognition task. Options: "ocr" (default), "table", "formula", "chart".
        :return: A dictionary containing the execution status and the OCR result text in 'stdout'.
        """
        full_path = os.path.join(self.workspace_root, image_relative_path)
        
        if not os.path.exists(full_path):
            return {"status": "error", "stdout": f"Image file not found: {full_path}"}

        try:
            # 1. Prepare Base64 Image
            base64_image = self._encode_image_to_base64(full_path)
            
            # 2. Prepare Prompt based on mode
            task_prompt = self.ocr_tasks.get(mode, "OCR:")
            
            # 3. Construct the request payload
            messages = [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{base64_image}"
                            }
                        },
                        {
                            "type": "text",
                            "text": task_prompt
                        }
                    ]
                }
            ]

            # 4. Call the local model API
            response = self.ocr_client.chat.completions.create(
                model="PaddlePaddle/PaddleOCR-VL", 
                messages=messages,
                temperature=0.0, 
            )

            result_text = response.choices[0].message.content
            
            return {
                "status": "success", 
                "stdout": f"OCR Result for {image_relative_path} (Mode: {mode}):\n\n{result_text}",
                "raw_text": result_text
            }

        except Exception as e:
            return {"status": "error", "stdout": f"OCR API Error: {str(e)}"}

    async def _handle_get_outline(self, path: str) -> Dict[str, Any]:
        """
        Parses the Markdown file to extract headers/sections.
        This helps the agent understand the structure of the attack (e.g., Recon -> Exploit -> Root).

        :param path: Path to the markdown file relative to workspace root.
        :return: A dictionary containing the document outline tree in 'stdout'.
        """
        try:
            content = await self._read_file_content(path)
            lines = content.splitlines()
            outline_md = []
            
            for i, line in enumerate(lines):
                stripped = line.strip()
                if stripped.startswith("#"):
                    # Calculate header level (e.g., ## is level 2)
                    level = len(stripped.split()[0])
                    parts = stripped.split(None, 1)
                    title = parts[1] if len(parts) > 1 else "[Empty Header]"
                    indent = "  " * (level - 1)
                    outline_md.append(f"{indent}- **{title}** (Line {i + 1})")

            output = "### 🗺️ Document Navigation Tree\n\n" + "\n".join(outline_md)
            return {"status": "success", "stdout": output, "raw_data": outline_md}
        except Exception as e:
            return {"status": "error", "stdout": str(e)}

    async def _handle_extract_code_blocks(self, path: str, start_line: int = 0, end_line: int = -1) -> Dict[str, Any]:
        """
        Extracts code blocks (wrapped in triple backticks) from a specified range in the file.
        Used to identify commands (Actions) and terminal outputs (Observations).

        :param path: Path to the markdown file relative to workspace root.
        :param start_line: The line number to start scanning from (0-indexed).
        :param end_line: The line number to stop scanning. If -1, scans to the end of the file.
        :return: A dictionary containing a formatted list of code blocks in 'stdout' and raw block data.
        """
        try:
            content = await self._read_file_content(path)
            lines = content.splitlines()
            
            if end_line == -1:
                end_line = len(lines)

            blocks = []
            in_block = False
            current_block = []
            block_start_line = 0
            lang = ""

            for i, line in enumerate(lines):
                # Only process lines within the requested range
                if i < start_line - 1 or i > end_line - 1:
                    continue

                stripped = line.strip()
                
                # Detect start/end of code block
                if stripped.startswith("```"):
                    if in_block:
                        # End of block
                        blocks.append({
                            "type": "code_block",
                            "language": lang,
                            "content": "\n".join(current_block),
                            "start_line": block_start_line,
                            "end_line": i + 1
                        })
                        current_block = []
                        in_block = False
                        lang = ""
                    else:
                        # Start of block
                        in_block = True
                        block_start_line = i + 1
                        # Extract language if present (e.g., ```bash)
                        lang = stripped.replace("```", "").strip()
                elif in_block:
                    current_block.append(line)

            formatted_output = f"### 💻 Extracted Code Blocks ({len(blocks)} found)\n"
            for b in blocks:
                formatted_output += f"- [Line {b['start_line']}-{b['end_line']}] ({b['language']}):\n{b['content'][:100]}...\n"

            return {"status": "success", "stdout": formatted_output, "blocks": blocks}
        except Exception as e:
            return {"status": "error", "stdout": str(e)}

    async def _handle_extract_images(self, path: str) -> Dict[str, Any]:
        """
        Scans the document for markdown image syntax (![alt](path)) to identify visual assets.
        These assets can be subsequently processed by _handle_perform_ocr.

        :param path: Path to the markdown file relative to workspace root.
        :return: A dictionary containing a list of found images with their line numbers and paths.
        """
        try:
            content = await self._read_file_content(path)
            # Regex for standard markdown images
            pattern = r'!\[(.*?)\]\((.*?)\)'
            matches = []
            
            for i, line in enumerate(content.splitlines()):
                found = re.findall(pattern, line)
                for match in found:
                    matches.append({
                        "line_number": i + 1,
                        "alt_text": match[0],
                        "image_path": match[1]
                    })
            
            output = f"### 🖼️ Found {len(matches)} Images\n"
            for m in matches:
                output += f"- Line {m['line_number']}: {m['image_path']} (Alt: {m['alt_text']})\n"

            return {"status": "success", "stdout": output, "images": matches}
        except Exception as e:
            return {"status": "error", "stdout": str(e)}

    async def _handle_read_section_context(self, path: str, target_line: int, window: int = 5) -> Dict[str, Any]:
        """
        Reads a specific window of text around a target line.
        Crucial for understanding the 'Reasoning' (text) connecting an 'Action' (code block) 
        and an 'Observation' (code block or image).

        :param path: Path to the markdown file relative to workspace root.
        :param target_line: The line number to center the context around.
        :param window: The number of lines to read before and after the target line.
        :return: A dictionary containing the text content surrounding the target line.
        """
        try:
            content = await self._read_file_content(path)
            lines = content.splitlines()
            
            start = max(0, target_line - window - 1)
            end = min(len(lines), target_line + window)
            
            context_lines = []
            for i in range(start, end):
                marker = ">>" if i == (target_line - 1) else "  "
                context_lines.append(f"{marker} {i+1}: {lines[i]}")
            
            return {"status": "success", "stdout": "\n".join(context_lines)}
        except Exception as e:
            return {"status": "error", "stdout": str(e)}