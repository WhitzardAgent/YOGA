### TODO: Implement more complex architectures

class Memory():
    def __init__(self):
        self.messages = list()
        self.working_memory = list()
        self.action_history = list()

    def add(self, role, content):
        self.messages.append({
            "role": role,
            "content": content
        })
        
    def clear_task_related_memory(self):
        self.messages = list()
        
    def add_working_memory(self, task_idx, step_num, memory_content):
        self.working_memory.append([task_idx, step_num, memory_content])

    def add_action(self, task_idx, step_num, action_idx, action_name, action_args):
        self.action_history.append([task_idx, step_num, action_idx, action_name, action_args])

    def get_action_history(self):
        """
        Format the action history into a user-friendly indented string,
        showing the hierarchy: Task → Step → Action.

        Returns:
            str: Formatted history as a single string with indentation.
        """
        if not self.action_history:
            return "No actions recorded."

        formatted_lines = []
        current_task = None
        current_step = None

        for record in self.action_history:
            task_idx, step_num, action_idx, action_name, action_args = record

            # Add task header if new task
            if task_idx != current_task:
                formatted_lines.append(f"Task {task_idx}")
                current_task = task_idx
                current_step = None  # Reset step when task changes

            # Add step header if new step
            if step_num != current_step:
                formatted_lines.append(f"  Step {step_num}")
                current_step = step_num

            # Format args
            if action_args:
                args_str = ", ".join(f"{k}={v!r}" for k, v in action_args.items())
            else:
                args_str = ""

            # Add indented action
            action_line = f"    Action {action_idx}: {action_name}({args_str})"
            formatted_lines.append(action_line)

        return "\n".join(formatted_lines)
    
    def get_working_memory(self):
        mem_str = ''
        seen_lines = set()
        
        for entry in (self.working_memory):  # Make sure steps are in order
            lines = entry[2].split('\n')
            
            # Filter the lines that haven't been seen in previous steps
            new_lines = [line for line in lines if line not in seen_lines]
            
            if new_lines:
                if(entry[0] < 0):
                    mem_str += f'- Step {entry[1]}\n' # No subtasks
                else:
                    mem_str += f'- Task {entry[0]} Step {entry[1]}\n'
                for line in new_lines:
                    mem_str += f'\t{line}\n'
            
            # Add all lines from current step to seen lines set
            for line in lines:
                seen_lines.add(line)
        
        return mem_str
            
    def get_messages(self, max_round=2):
        short_memory = []
        # Always include the first slot (system message)
        short_memory.append(self.messages[0])
        
        num_after_system = len(self.messages) - 1
        take = min(num_after_system, 2 * max_round - 1)
        
        if take > 0:
            short_memory.extend(self.messages[-take:])
        
        return short_memory


    def get_full_messages(self):
        return self.messages



