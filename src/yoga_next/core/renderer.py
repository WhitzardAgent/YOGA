from typing import Any, Dict, List
from rich.table import Table, box
from rich.panel import Panel
from rich.text import Text
from rich.rule import Rule

class AgentPlanRenderer:
    def __init__(self, console: Any = None, display: Any = None):
        self.console = console
        self.display = display
    
    def render_step_header(self, step_num: int) -> None:
        if not self.console:
            return
        self.console.print("\n")
        self.console.print(Rule(
            title=f" STEP {step_num} ",
            style="on blue",
            characters=" "
        ))
    
    def render_agent_plan(
        self,
        step_num: int,
        parsed_json: Dict[str, Any],
        actions: List[Dict[str, Any]],
        memory: Any,
        think_content: str = ""
    ) -> None:
        if not self.console:
            return
        
        raw_output = parsed_json.get('raw_model_output', '')
        curr_state = parsed_json.get('current_state', {})
        next_goal = curr_state.get('next_goal', '...')
        
        if think_content:
            think_panel = Panel(
                Text(think_content, style="italic cyan"),
                title="🧠 Internal Thought",
                border_style="cyan",
                subtitle="Mental Sandbox",
                expand=True
            )
            self.console.print(think_panel)
        
        status_table = Table.grid(expand=True)
        status_table.add_column(ratio=1)
        status_table.add_column(ratio=1)
        
        memory_panel = Panel(
            Text(str(memory), style="grey70"),
            title="💾 Working Memory",
            border_style="magenta",
            expand=True
        )
        
        goal_panel = Panel(
            Text(str(next_goal), style="bold white"),
            title="🎯 Next Goal",
            border_style="blue",
            expand=True
        )
        
        status_table.add_row(memory_panel, goal_panel)
        self.console.print(status_table)
        
        action_table = Table(box=box.ROUNDED, expand=True, show_header=True, header_style="bold yellow")
        action_table.add_column("#", style="dim", width=3, justify="center")
        action_table.add_column("Action", style="bold yellow", width=20)
        action_table.add_column("Parameters", style="green", overflow="fold")
        
        import json
        for i, act in enumerate(actions):
            params = act['action_params']
            if isinstance(params, dict) and len(params) > 1:
                params_str = json.dumps(params, indent=2, ensure_ascii=False)
            else:
                params_str = str(params)
            
            action_table.add_row(
                str(i+1),
                act['action_name'],
                params_str
            )
        
        self.console.print(Panel(
            action_table,
            title="🚀 Execution Plan",
            border_style="green"
        ))
