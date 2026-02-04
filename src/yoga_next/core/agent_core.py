import asyncio
import time
from typing import Any, Dict, List
from rich.live import Live
from rich.status import Status
from .base import IAgentCore, ActionResult
from .formatter import OutputFormatter
from .renderer import AgentPlanRenderer
from .memory_manager import MemoryManager
from .state_builder import StateBuilder
from .action_executor import ActionExecutor
from ..utils import log_info, log_warn, parse_model_response
from .formatter import OutputFormatter

class AgentCore(IAgentCore):
    def __init__(
        self,
        model: Any,
        action_space: Any,
        memory: Any,
        memory_stream: Any,
        system_prompt: str,
        display: Any = None,
        timeout: int = 60
    ):
        self.model = model
        self.action_space = action_space
        self.display = display
        self.timeout = timeout
        
        self.memory = memory
        self.memory_stream = memory_stream
        self.memory_manager = MemoryManager(memory, memory_stream)
        self.action_executor = ActionExecutor(action_space, timeout)
        self.state_builder = StateBuilder(memory, action_space)
        self.renderer = AgentPlanRenderer(
            console=display.console if display else None,
            display=display
        )
        
        self.task = None
        self.final_result = None
        self.system_prompt = system_prompt
        self.thinking_space = getattr(action_space, 'thinking_space', None)
    
    
    def _add_to_memory_stream(
        self,
        task_id: str,
        step_num: int,
        message_type: str,
        content: Dict[str, Any],
        env_state: str = ""
    ):
        self.memory_manager.add_to_memory_stream(task_id, step_num, message_type, content, env_state)
    
    async def execute(self, task: Any, max_steps: int = 100) -> Any:
        self.task = task
        self.final_result = None
        
        if self.display:
            self.display.render_planning(task.instruction)
        
        thought_guidance = (
            "Since this is a new task, please start by using sequential_thinking "
            "to analyze the requirements and plan your approach."
        )
        env_state = self.action_space.env.get_observation() if self.action_space.env else ""
        self.memory_manager.add_to_memory_stream(
            task.task_id, 0, "guidance", {"message": thought_guidance}, env_state
        )
        
        result = await self.execute_single_task(task, task_idx=-1, max_steps=max_steps)
        
        return self.final_result
    
    async def execute_single_task(
        self,
        task: Any,
        task_idx: int = -1,
        max_steps: int = 100
    ) -> str:
        self.memory.clear_task_related_memory()
        self.memory.add(role='system', content=self.system_prompt)
        
        initial_state = self.state_builder.build_state(
            task=task,
            prev_action='(none)',
            obs='(none)',
            step_num=0
        )

        self.memory_manager.add_to_memory_stream(task.task_id, 0, "initial_state", {"state": initial_state})
    
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
            self.renderer.render_step_header(step_num)
            
            if live:
                live.update(Status("LLM is thinking...", spinner="bouncingBall"))
            
            output = self.model.chat_completion(self.memory.get_messages())
            self.memory_manager.add_to_memory_stream(task.task_id, step_num, "thinking", {"output": output})
            self.memory.add(role='assistant', content=output)
            
            parsed_json = parse_model_response(output)
            parsed_json['raw_model_output'] = output
            actions = parsed_json.get('action', [])
            self.memory.add_working_memory(task_idx, step_num, parsed_json['current_state']['memory'])

            if len(actions) == 0:
                log_warn("No actions parsed from model output, skipping to next step.")
                self.memory_manager.add_to_memory_stream(task.task_id, step_num, "warning", {"message": "No actions parsed from model output."})
                if live:
                    live.update(Status("No actions parsed. Retrying...", spinner="dots"))
                continue

            think_content = OutputFormatter.extract_think_tag(parsed_json.get('raw_model_output', ''))
            self.renderer.render_agent_plan(
                step_num, parsed_json, actions,
                self.memory.get_working_memory(),
                think_content
            )
    

            if len(actions) == 1 and actions[0]['action_name'] == 'done':
                action = actions[0]
                self.memory_manager.add_to_memory_stream(task.task_id, step_num, "action", {
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
                self.memory_manager.add_to_memory_stream(task.task_id, step_num, "final_status", {"status": result})
                
                if self.display:
                    self.display.render_observation(result)
                    success = result.get("success", True)
                    message = result.get("message", "Task completed")
                
                if live:
                    live.stop()
                    live = None
                break
        
            observations = []
            physical_action_executed = False
            
            for i, action in enumerate(actions):
                action_name = action['action_name']
                action_params = action['action_params']
                
                self.memory_manager.add_to_memory_stream(task.task_id, step_num, "action", {
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
                    self.memory_manager.add_to_memory_stream(task.task_id, step_num, "final_status", {"status": result})
                    
                    if self.display:
                        self.display.render_observation(result)
                        success = result.get("success", True)
                        message = result.get("message", "Task completed")
                        self.display.render_done(success, message)
                    
                    if live:
                        live.stop()
                        live = None
                    return result.get("message", "Task completed")

                result_str = OutputFormatter.flatten_to_kv_string(result)
                observations.append(result_str)
                
                if self.display:
                    result_for_render = result.copy()
                    result_for_render['action'] = action_name
                    self.display.render_observation(result_for_render)
                
            state = self.state_builder.build_state(
                task=task,
                prev_action=parsed_json['current_state']['next_goal'],
                obs='\n\n'.join(observations),
                step_num=step_num
            )
                                    
            self.memory_manager.add_to_memory_stream(task.task_id, step_num, "observation", {"observations": '\n\n'.join(observations)})
            self.memory.add(role='user', content=state)
            
        if live:
            live.stop()
            live = None
            
        return task_status
    
    async def _execute_with_timeout(
        self,
        action_name: str,
        action_params: Dict[str, Any]
    ) -> Dict[str, Any]:
        result = await self.action_executor.execute(action_name, action_params)
        return {
            'success': result.success,
            'message': result.message,
            **(result.data or {})
        }
    
    def dump(self, exp_file_path: str) -> None:
        """Dump the memory stream to a JSONL file with the given path"""
        import os
        os.makedirs(os.path.dirname(exp_file_path), exist_ok=True)
        self.memory_stream.dump(exp_file_path)
        log_info(f"Memory stream dumped to {exp_file_path}")
