from typing import List, Dict, Any
import time


class MemoryChunk:
    def __init__(self, task_id: str, step_num: int, message_type: str, content: Dict[str, Any], environment_state: str, timestamp: float):
        self.task_id = task_id
        self.step_num = step_num
        self.message_type = message_type
        self.content = content
        self.environment_state = environment_state
        self.timestamp = timestamp

    def to_dict(self):
        return {
            'task_id': self.task_id,
            'step_num': self.step_num,
            'message_type': self.message_type,
            'content': self.content,
            'environment_state': self.environment_state,
            'timestamp': self.timestamp
        }


class MemoryStream:
    def __init__(self):
        self.chunks: List[MemoryChunk] = []
    
    def add_chunk(self, chunk: MemoryChunk):
        self.chunks.append(chunk)
    
    def get_chunks(self, task_id: str = None, message_type: str = None) -> List[MemoryChunk]:
        if task_id is None and message_type is None:
            return self.chunks
        filtered_chunks = self.chunks
        if task_id:
            filtered_chunks = [chunk for chunk in filtered_chunks if chunk.task_id == task_id]
        if message_type:
            filtered_chunks = [chunk for chunk in filtered_chunks if chunk.message_type == message_type]
        return filtered_chunks
    
    def dump(self, filepath: str):
        """Save all chunks as JSONL (JSON Lines) format to the specified file."""
        import json
        with open(filepath, 'w') as f:
            for chunk in self.chunks:
                f.write(json.dumps(chunk.to_dict()) + '\n')
    
    def clear(self):
        self.chunks.clear()