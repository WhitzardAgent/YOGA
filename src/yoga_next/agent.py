from .actions import ActionSpace, UnionActionSpace, ControlActionSpace, ThinkingActionSpace
from .memory import Memory
from .planner import Planner
from .model import Model
from .tasks import Task
from .agent_config import AgentConfig
from .prompts import SYSTEM_PROMPT
from .utils import log_info, log_warn, log_error, extract_json_from_model_markdown_output, flatten_to_kv_string, YogDisplay
from .hm import MemoryChunk, MemoryStream
import asyncio
import time
from typing import List, Dict, Any, Optional
from rich.live import Live
from rich.status import Status


class Agent:
    def __init__(self, 
                 agent_config: AgentConfig,
                 action_spaces: List[ActionSpace],
                 use_rich_display: bool = True):
        self.model = Model(
            api_base=agent_config.api_base_url, 
            model_name=agent_config.model_name, 
            api_key=agent_config.api_key
        )
        self.memory = Memory(model=self.model)
        self.planner = Planner(model=self.model)
        self.action_spaces = action_spaces
        self.use_rich_display = use_rich_display
        
        self.thinking_space = ThinkingActionSpace()
        control_space = ControlActionSpace()
        all_spaces = [control_space, self.thinking_space] + action_spaces
        self.action_space = UnionActionSpace(all_spaces)
        
        self.system_prompt = SYSTEM_PROMPT.format(
                func_signature=self.action_space.get_action_space_description(), 
                max_actions=5
        )
        self.memory_stream = MemoryStream()
        self.final_result = None
        self.display = YogDisplay() if use_rich_display else None
        log_info("System Prompt:\n"+self.system_prompt)
        
    def _get_thought_trace(self, max_thoughts: int = 5) -> str:
        """获取最近的思维摘要列表"""
        if not hasattr(self, 'thinking_space') or not self.thinking_space.thought_history:
            return "(No thoughts yet)"
        
        thoughts = self.thinking_space.thought_history[-max_thoughts:]
        lines = []
        for td in thoughts:
            prefix = "🔄" if td.is_revision else ("🌿" if td.branch_from_thought else "💭")
            summary = td.thought[:80] + "..." if len(td.thought) > 80 else td.thought
            lines.append(f"{prefix} Step #{td.thought_number}: {summary}")
        return "\n".join(lines)

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
            if(task_idx < 0):
                log_info('='*10 + f' Step {step_num}/{max_steps} ' + '='*10)
            else:
                log_info('='*10 + f' Task {task_idx} Step {step_num}/{max_steps} ' + '='*10)
            
            if self.display:
                self.display.render_step_start(step_num, task_idx if task_idx > 0 else None)
                
            if live:
                live.update(Status("Thinking...", spinner="dots"))
            
            output = self.model.chat_completion(self.memory.messages)
            log_info('+'*10 + f' Agent Output ' + '+'*10)
            log_info(f'{output}')
            
            self._add_to_memory_stream(task.task_id, step_num, "thinking", {"output": output})
            self.memory.add(role='assistant', content=output)
            
            parsed_json = extract_json_from_model_markdown_output(output)
            parsed_json['raw_model_output'] = output
            actions = parsed_json['action']
            self.memory.add_working_memory(task_idx, step_num, parsed_json['current_state']['memory'])

            current_state = parsed_json.get('current_state', {})
            thought_content = current_state.get('memory', '')
            if self.display and thought_content:
                self.display.render_thought(thought_content)

            if(len(actions) == 0):
                log_warn("No actions parsed from model output, skipping to next step.")
                self._add_to_memory_stream(task.task_id, step_num, "warning", {"message": "No actions parsed from model output."})
                continue

            if(len(actions) == 1 and actions[0]['action_name'] == 'done'):
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
                
                result = await self.action_space.execute(action['action_name'], 
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
                    if self.display:
                        live.update(Status("Processing thought...", spinner="dots"))
                    
                    result = await self.action_space.execute(action_name, action_params)
                    
                    if self.display and self.thinking_space.thought_history:
                        thinking_data = self.thinking_space.thought_history[-1]
                        formatted_thought = self.thinking_space._format_thought(thinking_data)
                        self.display.console.print(formatted_thought)
                    
                    prefix = "[Plan Revision]" if action_params.get('is_revision') else "[Thought]"
                    self.memory.add_working_memory(
                        task_idx, step_num, 
                        f"{prefix} {action_params.get('thought', '')}"
                    )
                    
                    observations.append(f"Thought #{action_params.get('thought_number')}: {action_params.get('thought', '')[:100]}...")
                    
                    next_needed = action_params.get('next_thought_needed', True)
                    observations.append(f"Thought #{action_params.get('thought_number')}/{action_params.get('total_thoughts')}: {action_params.get('thought', '')[:100]}...")
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
                
                if self.display:
                    action_code = str(action_params)
                    self.display.render_action(action_code, action_name)
                
                if live:
                    live.update(Status(f"Executing {action_name}...", spinner="earth"))
                
                result = await self.action_space.execute(action_name, action_params)
                
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
                    self.display.render_observation(result)
                
            state = self.create_state(task=task,
                                      prev_action=parsed_json['current_state']['next_goal'],
                                      obs='\n\n'.join(observations),
                                      step_num=step_num)
                                      
            self._add_to_memory_stream(task.task_id, step_num, "observation", {"observations": '\n\n'.join(observations)})

            log_info('+'*10 + f' Observation ' + '+'*10)
            log_info(f'{state}')
            self.memory.add(role='user', content=state)
            
        if live:
            live.stop()
            live = None
            
        return task_status
