from .actions import ActionSpace, UnionActionSpace, ControlActionSpace, ThinkingActionSpace, EditActionSpace
from .memory import Memory
from .planner import Planner
from .model import Model
from .tasks import Task
from .agent_config import AgentConfig
from .prompts import PromptFactory
from .utils import log_info, log_warn, log_error, extract_json_from_model_markdown_output, flatten_to_kv_string, YogDisplay
from .hm import MemoryChunk, MemoryStream
import asyncio
import time
from typing import List, Dict, Any, Optional
from rich.live import Live
from rich.status import Status
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.rule import Rule
from rich.syntax import Syntax
from rich import box


DEFAULT_TIMEOUT = 60.0
LONG_ACTION_TIMEOUT = 300.0

ACTION_TIMEOUTS = {
    "pip_install": 180.0,
    "pip_uninstall": 120.0,
    "conda_install": 180.0,
    "conda_create": 180.0,
    "conda_remove": 120.0,
    "download_file": 120.0,
    "clone_repo": 120.0,
}


class Agent:
    def __init__(self, 
                 agent_config: AgentConfig,
                 action_spaces: List[ActionSpace],
                 use_rich_display: bool = True,
                 timeout: float = DEFAULT_TIMEOUT):
        self.model = Model(
            api_base=agent_config.api_base_url, 
            model_name=agent_config.model_name, 
            api_key=agent_config.api_key
        )
        self.memory = Memory(model=self.model)
        self.planner = Planner(model=self.model)
        self.action_spaces = action_spaces
        self.use_rich_display = use_rich_display
        self.timeout = timeout
        
        self.thinking_space = ThinkingActionSpace()
        control_space = ControlActionSpace()
        all_spaces = [control_space, self.thinking_space] + action_spaces
        self.action_space = UnionActionSpace(all_spaces)
        
        self.agent_type = "latex_editor"
        
        # 动态生成
        self.system_prompt = PromptFactory.get_system_prompt(
            agent_type=self.agent_type,
            func_signature=self.action_space.get_action_space_description(), 
            max_actions=5
        )
        self.memory_stream = MemoryStream()
        self.final_result = None
        self.display = YogDisplay() if use_rich_display else None
        log_info("System Prompt:\n"+self.system_prompt)
        
    def _get_timeout_for_action(self, action_name: str) -> float:
        """根据动作名称获取特定的超时时间"""
        for key, timeout in ACTION_TIMEOUTS.items():
            if key in action_name.lower():
                return timeout
        return self.timeout
    
    async def _execute_with_timeout(self, action_name: str, action_params: Dict[str, Any]) -> Dict[str, Any]:
        """带超时的动作执行"""
        timeout = self._get_timeout_for_action(action_name)
        
        try:
            result = await asyncio.wait_for(
                self.action_space.execute(action_name, action_params),
                timeout=timeout
            )
            output = result.get("output")
            if output is not None:
                return output
            return result
        except asyncio.TimeoutError:
            log_warn(f"Action '{action_name}' timed out after {timeout}s")
            return {
                "status": "error",
                "message": f"Action '{action_name}' timed out after {timeout}s. Please try a different approach or reduce the scope of this operation.",
                "error_code": 124,
                "timeout": timeout,
                "action": action_name
            }
        
    def _get_thought_trace(self, max_thoughts: int = 5) -> str:
        """获取最近的思维摘要列表（紧凑格式）"""
        if not hasattr(self, 'thinking_space') or not self.thinking_space.thought_history:
            return "[grey50](No reasoning history)[/grey50]"
        
        thoughts = self.thinking_space.thought_history[-max_thoughts:]
        lines = []
        for td in thoughts:
            icon = "[bold green]✓[/bold green]" if not td.is_revision else "[bold yellow]⚠[/bold yellow]"
            summary = td.thought[:60].replace("\n", " ") + "..."
            lines.append(f"{icon} [grey70]T#{td.thought_number}:[/grey70] {summary}")
        return "\n".join(lines)

    def _truncate_observation(self, content: str, max_lines: int = 15, keep: int = 7) -> str:
        """自动截断过长的 Observation"""
        lines = content.splitlines()
        if len(lines) <= max_lines:
            return content
        return "\n".join(lines[:keep]) + f"\n\n[bold yellow]... (Skipped {len(lines)-keep*2} lines) ...[/bold yellow]\n\n" + "\n".join(lines[-keep:])
    
    def _should_highlight_shell(self, action_name: str, content: str) -> bool:
        """判断是否应该对内容进行 shell 语法高亮"""
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

    def _print_step_header(self, step_num: int):
        """使用带背景颜色的 Rule，产生强烈的视觉分割"""
        if not self.display:
            return
        self.display.console.print("\n")
        self.display.console.print(Rule(
            title=f"[bold white] STEP {step_num} [/bold white]",
            style="on blue",
            characters=" "
        ))

    def _render_agent_plan(self, step_num: int, parsed_json: Dict[str, Any], actions: List[Dict[str, Any]]):
        """使用 Columns/Table 布局展示 Reasoning 和 Execution Plan"""
        if not self.display:
            return
        
        curr_state = parsed_json.get('current_state', {})
        memory = curr_state.get('memory', '...')
        next_goal = curr_state.get('next_goal', '...')
        
        logic_panel = Panel(
            Text(f"{next_goal}\n\n{memory}", style="italic grey70"),
            title="[bold magenta]🤔 Reasoning[/bold magenta]",
            border_style="magenta",
            expand=True
        )
        
        action_table = Table(box=box.SIMPLE_HEAD, expand=True)
        action_table.add_column("#", style="dim", width=2)
        action_table.add_column("Action", style="bold yellow")
        action_table.add_column("Parameters", style="green", overflow="fold")
        
        for i, act in enumerate(actions):
            params = str(act['action_params'])
            action_table.add_row(
                str(i+1),
                act['action_name'],
                params
            )
        
        combined_content = Table.grid(expand=True)
        combined_content.add_row(logic_panel)
        combined_content.add_row(Panel(action_table, title="[bold green]🚀 Execution Plan[/bold green]", border_style="green"))
        
        self.display.console.print(combined_content)

    def create_state(self, 
                     task: Task, 
                     prev_action: str, 
                     obs: str, 
                     step_num: int,
                     ):
        thought_trace = self._get_thought_trace()
        return f"""
## Step {step_num}

### Goal
{task.instruction}

### Current Thought Trace
{thought_trace}

### Long-term Memory
{self.memory.get_working_memory()}

### Previous Action
{prev_action}

### Observation
{obs}

### Environment State
{self.action_space.env.get_observation() if self.action_space.env else 'No environment'}
"""

    def dump(self, exp_file_path: str):
        """Dump the memory stream to a JSONL file with the given path"""
        import os
        os.makedirs(os.path.dirname(exp_file_path), exist_ok=True)
        self.memory_stream.dump(exp_file_path)
        log_info(f"Memory stream dumped to {exp_file_path}")

    def _add_to_memory_stream(self, task_id: str, step_num: int, message_type: str, content: Dict[str, Any]):
        env_state = self.action_space.env.get_observation() if self.action_space.env else ""
        timestamp = time.time()
        memory_chunk = MemoryChunk(
            task_id=task_id,
            step_num=step_num,
            message_type=message_type,
            content=content,
            environment_state=env_state,
            timestamp=timestamp
        )
        self.memory_stream.add_chunk(memory_chunk)

    async def execute(self, task: Task, max_steps=100):
        self.task = task
        self.final_result = None
        
        if self.display:
            self.display.render_planning(task.instruction)
        
        thought_guidance = (
            "Since this is a new task, please start by using sequential_thinking "
            "to analyze the requirements and plan your approach."
        )
        self._add_to_memory_stream(task.task_id, 0, "guidance", {"message": thought_guidance})
        
        result = await self.execute_single_task(task, task_idx=-1, max_steps=max_steps)
        
        return self.final_result
    
    async def execute_single_task(self, task, task_idx=-1, max_steps=100):
        self.memory.clear_task_related_memory()
        self.memory.add(role='system', content=self.system_prompt)
        
        initial_state = self.create_state(task=task,
                                          prev_action='(none)', 
                                          obs='(none)', 
                                          step_num=0)
        self._add_to_memory_stream(task.task_id, 0, "initial_state", {"state": initial_state})
        self.memory.add(role='user', content=initial_state)
        
        log_info(f"⚠️ {task}")
        env_obs = self.action_space.env.get_observation() if self.action_space.env else "No environment"
        log_info(f'Environment State:\n {env_obs}')
        task_status = 'Reach maximal steps. Forwarding to the next task.'
        
        live = None
        if self.display:
            live = Live(Status("Waiting for LLM...", spinner="dots"), refresh_per_second=10)
            live.start()
        
        for step_num in range(1, max_steps+1):
            self._print_step_header(step_num)
            
            if live:
                live.update(Status("LLM is thinking...", spinner="bouncingBall"))
            
            output = self.model.chat_completion(self.memory.messages)
            
            self._add_to_memory_stream(task.task_id, step_num, "thinking", {"output": output})
            self.memory.add(role='assistant', content=output)
            
            parsed_json = extract_json_from_model_markdown_output(output)
            parsed_json['raw_model_output'] = output
            actions = parsed_json.get('action', [])
            self.memory.add_working_memory(task_idx, step_num, parsed_json['current_state']['memory'])

            if len(actions) == 0:
                log_warn("No actions parsed from model output, skipping to next step.")
                self._add_to_memory_stream(task.task_id, step_num, "warning", {"message": "No actions parsed from model output."})
                if live:
                    live.update(Status("No actions parsed. Retrying...", spinner="dots"))
                continue

            self._render_agent_plan(step_num, parsed_json, actions)

            if len(actions) == 1 and actions[0]['action_name'] == 'done':
                action = actions[0]
                self._add_to_memory_stream(task.task_id, step_num, "action", {
                    "action_index": 0,
                    "action_name": action['action_name'], 
                    "action_params": action['action_params']
                })
                
                if self.display:
                    self.display.render_action(str(action['action_params']), "done")
                
                if live:
                    live.update(Status("Task completing...", spinner="dots"))
                
                result = await self._execute_with_timeout(action['action_name'], 
                                                          action['action_params'])
                
                self.final_result = result
                self._add_to_memory_stream(task.task_id, step_num, "final_status", {"status": result})
                
                if self.display:
                    self.display.render_observation(result)
                    success = result.get("success", True)
                    message = result.get("message", "Task completed")
                    self.display.render_done(success, message)
                
                if live:
                    live.stop()
                    live = None
                break
        
            observations = []
            physical_action_executed = False
            
            for i, action in enumerate(actions):
                action_name = action['action_name']
                action_params = action['action_params']
                
                self._add_to_memory_stream(task.task_id, step_num, "action", {
                    "action_index": i,
                    "action_name": action_name, 
                    "action_params": action_params
                })
                
                if action_name == 'sequential_thinking':
                    if live:
                        live.update(Status(f"Processing thought #{action_params.get('thought_number', '?')}...", spinner="dots"))
                    
                    result = await self._execute_with_timeout(action_name, action_params)
                    
                    if self.display and self.thinking_space.thought_history:
                        thinking_data = self.thinking_space.thought_history[-1]
                        formatted_thought = self.thinking_space._format_thought(thinking_data)
                        self.display.console.print(formatted_thought)
                    
                    prefix = "[Plan Revision]" if action_params.get('is_revision') else "[Thought]"
                    self.memory.add_working_memory(
                        task_idx, step_num, 
                        f"{prefix} {action_params.get('thought', '')}"
                    )
                    
                    observations.append(f"Thought #{action_params.get('thought_number')}/{action_params.get('total_thoughts')}: {action_params.get('thought', '')[:100]}...")
                    
                    next_needed = action_params.get('next_thought_needed', True)
                    summary = result.get('current_thought_summary', '')
                    advice = result.get('advice', '')
                    if summary or advice:
                        observations.append(f"[Thought Summary] {summary} | {advice}")
                    
                    if not next_needed and not physical_action_executed and len(actions) == 1:
                        completion_prompt = (
                            "You indicated no more thoughts are needed and no physical actions were performed. "
                            "Have you completed all required operations? If so, please call done()."
                        )
                        self.memory.add(role='user', content=completion_prompt)
                    
                    continue
                
                if live:
                    live.update(Status(f"Running: [bold cyan]{action_name}[/bold cyan]...", spinner="earth"))
                
                result = await self._execute_with_timeout(action_name, action_params)
                
                if action_name not in ['sequential_thinking', 'done']:
                    physical_action_executed = True
                
                if action_name == 'done':
                    self.final_result = result
                    self._add_to_memory_stream(task.task_id, step_num, "final_status", {"status": result})
                    
                    if self.display:
                        self.display.render_observation(result)
                        success = result.get("success", True)
                        message = result.get("message", "Task completed")
                        self.display.render_done(success, message)
                    
                    if live:
                        live.stop()
                        live = None
                    return result.get("message", "Task completed")

                result_str = flatten_to_kv_string(result)
                observations.append(result_str)
                
                if self.display:
                    result_for_render = result.copy()
                    result_for_render['action'] = action_name
                    self.display.render_observation(result_for_render)
                
            state = self.create_state(task=task,
                                      prev_action=parsed_json['current_state']['next_goal'],
                                      obs='\n\n'.join(observations),
                                      step_num=step_num)
                                      
            self._add_to_memory_stream(task.task_id, step_num, "observation", {"observations": '\n\n'.join(observations)})
            self.memory.add(role='user', content=state)
            
        if live:
            live.stop()
            live = None
            
        return task_status
