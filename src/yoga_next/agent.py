from .actions import ActionSpace, UnionActionSpace, ControlActionSpace
from .memory import Memory
from .planner import Planner
from .model import Model
from .tasks import Task
from .agent_config import AgentConfig
from .prompts import SYSTEM_PROMPT
from .utils import log_info, log_warn, log_error, extract_json_from_model_markdown_output, flatten_to_kv_string
from .hm import MemoryChunk, MemoryStream
import asyncio
import time
from typing import List, Dict, Any


class Agent:
    def __init__(self, 
                 agent_config: AgentConfig,
                 action_spaces: List[ActionSpace]):
        self.model = Model(
            api_base=agent_config.api_base_url, 
            model_name=agent_config.model_name, 
            api_key=agent_config.api_key
        )
        self.memory = Memory(model=self.model)
        self.planner = Planner(model=self.model)
        self.action_spaces = action_spaces
        
        control_space = ControlActionSpace()
        all_spaces = [control_space] + action_spaces
        self.action_space = UnionActionSpace(all_spaces)
        
        self.system_prompt = SYSTEM_PROMPT.format(
                func_signature=self.action_space.get_action_space_description(), 
                max_actions=5
        )
        self.memory_stream = MemoryStream()
        self.final_result = None
        log_info("System Prompt:\n"+self.system_prompt)
        

    def create_state(self, 
                     task: Task, 
                     prev_action: str, 
                     obs: str, 
                     step_num: int,
                     ):
        return f"""
## Step {step_num}

### Goal
{task.instruction}

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
        log_info('Decompose into procedures ...')
        self._add_to_memory_stream(task.task_id, 0, "planning", {"message": f"Decomposing task: {task.instruction}"})
        
        self.subtasks = self.planner.plan(task, action_space=self.action_space)
        log_info(f'Goal: {task}')
        self._add_to_memory_stream(task.task_id, 0, "goal", {"task": str(task)})
        
        for idx, subtask in enumerate(self.subtasks):
            log_info(f"#{idx}: {subtask}")
            self._add_to_memory_stream(task.task_id, 0, "subtask", {"subtask_number": idx+1, "content": subtask})
            
        for task_idx, subtask in enumerate(self.subtasks):
            log_info(f'Executing Subtask #{task_idx+1}: {subtask}...')
            goal = f"### Current Task\nGoal: {task.instruction}\nSubtask: {subtask}\n"
            sub_task = Task(task_id=f"{task.task_id}_subtask_{task_idx+1}", 
                instruction=goal)
            status = await self.execute_single_task(sub_task, task_idx=(task_idx+1), max_steps=max_steps//5)
            log_info(f'Subtask #{task_idx+1} Final Status: {status}...')   
            self._add_to_memory_stream(sub_task.task_id, -1, "subtask_status", {"subtask_number": task_idx+1, "status": f"Subtask #{task_idx+1} Final Status: {status}"})
        
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
        
        for step_num in range(1, max_steps+1):
            if(task_idx < 0):
                log_info('='*10 + f' Step {step_num}/{max_steps} ' + '='*10)
            else:
                log_info('='*10 + f' Task {task_idx} Step {step_num}/{max_steps} ' + '='*10)
                
            output = self.model.chat_completion(self.memory.messages)
            log_info('+'*10 + f' Agent Output ' + '+'*10)
            log_info(f'{output}')
            
            self._add_to_memory_stream(task.task_id, step_num, "thinking", {"output": output})
            self.memory.add(role='assistant', content=output)
            
            parsed_json = extract_json_from_model_markdown_output(output)
            parsed_json['raw_model_output'] = output
            actions = parsed_json['action']
            self.memory.add_working_memory(task_idx, step_num, parsed_json['current_state']['memory'])

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
                
                result = await self.action_space.execute(action['action_name'], 
                                                        action['action_params'])
                
                self.final_result = result
                self._add_to_memory_stream(task.task_id, step_num, "final_status", {"status": result})
                break
        
            observations = []
            for i, action in enumerate(actions):
                self._add_to_memory_stream(task.task_id, step_num, "action", {
                    "action_index": i,
                    "action_name": action['action_name'], 
                    "action_params": action['action_params']
                })
                
                result = await self.action_space.execute(action['action_name'], 
                                                        action['action_params'])
                
                if action['action_name'] == 'done':
                    self.final_result = result
                    self._add_to_memory_stream(task.task_id, step_num, "final_status", {"status": result})
                    observations.append(flatten_to_kv_string(result))
                    state = self.create_state(task=task,
                                              prev_action=parsed_json['current_state']['next_goal'],
                                              obs='\n\n'.join(observations),
                                              step_num=step_num)
                    self._add_to_memory_stream(task.task_id, step_num, "observation", {"observations": '\n\n'.join(observations)})
                    self.memory.add(role='user', content=state)
                    return result.get("message", "Task completed")

                result_str = flatten_to_kv_string(result)
                observations.append(result_str)
                
            state = self.create_state(task=task,
                                      prev_action=parsed_json['current_state']['next_goal'],
                                      obs='\n\n'.join(observations),
                                      step_num=step_num)
                                      
            self._add_to_memory_stream(task.task_id, step_num, "observation", {"observations": '\n\n'.join(observations)})

            log_info('+'*10 + f' Observation ' + '+'*10)
            log_info(f'{state}')
            self.memory.add(role='user', content=state)
            
        return task_status
