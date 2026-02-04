import re
from typing import Any, Dict

class OutputFormatter:    
    @staticmethod
    def flatten_to_kv_string(result: Dict[str, Any]) -> str:
        if isinstance(result, dict):
            return '\n'.join([f"{k}: {v}" for k, v in result.items()])
        return str(result)
    
    @staticmethod
    def extract_think_tag(content: str) -> str:
        think_pattern = r'<think>(.*?)</think>'
        match = re.search(think_pattern, content, re.DOTALL)
        return match.group(1).strip() if match else ""
    
    @staticmethod
    def truncate_observation(content: str, max_lines: int = 15, keep: int = 7) -> str:
        lines = content.splitlines()
        if len(lines) <= max_lines:
            return content
        return "\n".join(lines[:keep]) + f"\n\n... ({len(lines)-keep*2} lines skipped) ...\n\n" + "\n".join(lines[-keep:])
    
    @staticmethod
    def should_highlight_shell(action_name: str, content: str) -> bool:
        shell_actions = {
            "execute_shell", "run_command", "bash", "shell", "exec",
            "execute_script", "run_bash", "run_shell"
        }
        
        action_lower = action_name.lower().replace("_", "").replace("-", "")
        for shell_action in shell_actions:
            if shell_action in action_lower:
                return True
        
        content_start = content.strip()[:100].lower()
        shell_patterns = [
            "cd ", "ls ", "cat ", "echo ", "grep ", "find ", "sed ", "awk ",
            "pip install", "npm install", "apt ", "git ", "docker ",
            "python", "python3", "node ", "bash ", "sh ",
            "| ", "&& ", "|| ", ">", "<", ">>", "<<"
        ]
        
        for pattern in shell_patterns:
            if content_start.startswith(pattern) or pattern in content_start[:50]:
                return True
        
        return False
