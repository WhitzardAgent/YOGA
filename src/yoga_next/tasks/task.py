import yaml

class Task:
    def __init__(self, 
                 task_id, 
                 instruction):
        self.task_id = task_id
        self.instruction = instruction  # Updated from task_description to instruction

    @classmethod
    def from_yaml(cls, yaml_path):
        with open(yaml_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)

        # Validate required fields
        if not data.get('task_id'):
            raise ValueError("Missing required field 'task_id' in YAML.")
        return cls(
            task_id=data['task_id'],
            instruction=data.get('instruction', ''))

    def __repr__(self):
        return (f"Task(task_id={self.task_id!r}, "
                f"instruction={self.instruction!r}")