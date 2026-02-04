from typing import Any, Dict, List, Optional
from .model import Model
from .tasks import Task
from .agent_config import AgentConfig
from .core.memory import Memory
from .core.hm import MemoryStream
from .utils import log_info, YogDisplay
from .actions import ActionSpace, UnionActionSpace, ControlActionSpace, ThinkingActionSpace
from .core.agent_core import AgentCore
from .prompts import PromptFactory
from .welcome import start_yoga_system



class YogaAgent(AgentCore):
    def __init__(
        self,
        agent_config: AgentConfig,
        action_spaces: Optional[List[ActionSpace]] = None,
        agent_type: str = "general",
        use_rich_display: bool = True,
        timeout: int = 60
    ):
        self.model = Model(
            api_base=agent_config.api_base_url,
            model_name=agent_config.model_name,
            api_key=agent_config.api_key
        )
        
        self.memory = Memory()
        self.action_spaces = action_spaces or []
        self.use_rich_display = use_rich_display
        self.timeout = timeout
        
        self.thinking_space = ThinkingActionSpace()
        control_space = ControlActionSpace()
        all_spaces = [control_space, self.thinking_space] + self.action_spaces
        self.action_space = UnionActionSpace(all_spaces)
        
        self.agent_type = agent_type
        
        self.system_prompt = PromptFactory.get_system_prompt(
            agent_type=self.agent_type,
            func_signature=self.action_space.get_action_space_description(),
            max_actions=5
        )
        
        self.memory_stream = MemoryStream()
        self.final_result = None
        self.display = YogDisplay() if use_rich_display else None
        
        # log_info("System Prompt:\n" + self.system_prompt)
        # =============== YOGA BANNER ===============

        from rich.console import Console
        from rich.text import Text
        from rich.panel import Panel
        console = Console()
        yoga_text = Text()
        yoga_text.append("Y", style="bold blue")
        yoga_text.append("O", style="bold cyan")
        yoga_text.append("G", style="bold green")
        yoga_text.append("A", style="bold yellow")

        super().__init__(
            model=self.model,
            action_space=self.action_space,
            memory=self.memory,
            memory_stream=self.memory_stream,
            system_prompt=self.system_prompt,
            display=self.display,
            timeout=self.timeout
        )
        start_yoga_system()
