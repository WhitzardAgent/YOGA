from typing import Any, Dict, List

class StateBuilder:
    def __init__(
        self,
        memory: Any,
        action_space: Any,
        thought_trace: List[Dict[str, Any]] = None
    ):
        self.memory = memory
        self.action_space = action_space
        self.thought_trace = thought_trace or []
    
    def build_state(
        self,
        task: Any,
        prev_action: str,
        obs: str,
        step_num: int
    ) -> str:
        thought_trace = self._get_thought_trace()
        env_obs = self.action_space.env.get_observation() if self.action_space.env else "No environment"
        
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
{env_obs}
"""
    
    def _get_thought_trace(self) -> str:
        if not self.thought_trace:
            return "(none)"
        
        trace_parts = []
        for i, thought in enumerate(self.thought_trace):
            thought_text = thought.get('thought', '')
            is_revision = thought.get('is_revision', False)
            prefix = "[Plan Revision]" if is_revision else "[Thought]"
            trace_parts.append(f"{prefix} {thought_text}")
        
        return '\n'.join(trace_parts)
