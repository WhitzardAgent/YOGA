
from typing import Dict, Any, List
from .tasks import Task
from .model import Model
from .actions import ActionSpace
from .utils import extract_bullets


class Planner:
    def __init__(self,
                 model: Model) -> None:
        self.model = model
        self.prompt_template = """You are an autonomous task planner powered by a large language model. Your role is to receive a high-level task and independently generate a clear, executable plan by decomposing it into well-structured subtasks. You operate without human involvement—your plan must enable full execution from start to finish with no external guidance.

        ### Available Tools
        {tool_description}

        Guidelines for planning:

        1.  **Understand the Objective Fully:** Infer the final goal, required outputs, constraints, and success criteria. Fill in reasonable assumptions if information is missing.
        2.  **Decompose into Atomic Steps:** Break the task into small, concrete subtasks. Each should represent a single, achievable action.
        3.  **Be Action-Oriented and Specific:** Use imperative verbs (e.g., "Search", "Draft", "Verify", "Calculate", "Generate") to ensure clarity and executability. Avoid vague or abstract phrasing.
        4.  **Respect Logical Flow:** Sequence subtasks in a coherent order, accounting for dependencies. Identify steps that can be performed in parallel when possible.
        5.  **Leverage Tool Awareness Implicitly:** Design subtasks with an understanding of what can be achieved using the available tools. While you must **not mention or invoke tools directly**, ensure each subtask is feasible given the toolset (e.g., a subtask like 'Find recent studies on climate change impacts' implies search capability).
        6.  **Ensure Completeness:** Include all necessary stages—research, creation, validation, refinement, and delivery. Anticipate potential issues and include checks or fallback logic where appropriate.
        7.  **Output Format:** Return only a clean bulleted list of subtasks. Do not include explanations, headers, or commentary.

        **Output Structure:**
        -   Subtask 1: Actionable step (tool-aware but no explicit tool reference)
        -   Subtask 2: Next logical action
        -   Subtask 3: Follow-up step with clear intent
        -   ... (Continue until the task is fully resolved)

        Your plan should serve as a self-contained, executable roadmap. You are fully responsible for its success.

        Task:
        {task}
    """
        
    def plan(self, task:Task, action_space: ActionSpace)->List[str]:
        messages = [
            {"role":"system", "content": "You are a helpful assistant good at decomposing complex tasks into practical steps. No more than 5 subtasks."},
            {"role":"user", "content": self.prompt_template.format(task=task.instruction, tool_description=action_space.get_action_space_description())}
        ]
        plan_str = self.model.chat_completion(messages)
        subtasks = extract_bullets(plan_str)
        return subtasks