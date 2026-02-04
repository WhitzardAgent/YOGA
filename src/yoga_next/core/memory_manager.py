import time
from typing import Any, Dict, Optional
from .hm import MemoryChunk

class MemoryManager:
    def __init__(self, memory: Any, memory_stream: Any):
        self.memory = memory
        self.memory_stream = memory_stream
    
    def add_working_memory(
        self,
        task_idx: int,
        step_num: int,
        memory_content: str
    ) -> None:
        self.memory.add_working_memory(task_idx, step_num, memory_content)
    
    def add_to_memory_stream(
        self,
        task_id: str,
        step_num: int,
        message_type: str,
        content: Dict[str, Any],
        env_state: str = ""
    ) -> MemoryChunk:
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
        return memory_chunk
    
    def clear_task_memory(self) -> None:
        self.memory.clear_task_related_memory()
    
    def get_working_memory(self) -> str:
        return self.memory.get_working_memory()
    
    def add_message(self, role: str, content: str) -> None:
        self.memory.add(role=role, content=content)
    
    def get_messages(self) -> Any:
        return self.memory.get_messages()
