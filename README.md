# Yoga-Next

A modular AI Agent framework supporting multiple execution environments and tool integrations.

[中文文档](README.zh.md) | English Documentation

## Quick Start

```python
from yoga_next import YogaAgent, AgentConfig

# Load from config file
config = AgentConfig.from_yaml("config.yaml")

# Create Agent
agent = YogaAgent(agent_config=config)

# Execute task
from yoga_next.tasks import Task
task = Task(task_id="example", instruction="Create a Python file for me")
result = await agent.execute(task)
```

## Project Structure

```
src/yoga_next/
├── core/                    # Core modules
│   ├── agent_core.py        # Agent core execution logic
│   ├── action_executor.py   # Action executor
│   ├── memory_manager.py    # Memory management
│   ├── state_builder.py     # State building
│   ├── renderer.py          # UI rendering
│   └── formatter.py         # Output formatting
├── actions/                 # Action Spaces (tool sets)
│   ├── base.py             # ActionSpace base class
│   ├── edit_action_space.py    # File editing
│   ├── local_action_space.py   # Local shell
│   ├── remote_server_action_space.py  # Remote servers
│   ├── jupyter_notebook_action_space.py  # Jupyter
│   └── thinking.py         # Thinking space
├── environments/           # Execution environments
│   ├── base.py            # Environment abstract base class
│   ├── local_env.py       # Local environment
│   ├── remote_server_env.py  # Remote server environment
│   ├── jupyter_notebook_env.py  # Jupyter environment
│   └── electron_app_env.py # Electron app environment
├── model.py               # LLM model wrapper
├── prompts.py             # Prompt factory
├── tasks.py               # Task definitions
└── yoga_agent.py          # Main entry point
```

## Core Concepts

### Environment

Environment is the underlying execution environment for Agent actions, encapsulating resource connections and operation interfaces.

**Core Methods**:

| Method | Description | Required |
|--------|-------------|----------|
| `get_observation()` | Get current environment state description | No (defaults to empty string) |
| `setup()` | Initialize resources (connections, etc.) | No |
| `close()` | Clean up resources | No |
| `update_state()` | Update internal state | No |

**Available Environments**:

1. **LocalEnvironment** (`local_env.py`) - Local development environment
2. **RemoteServerEnvironment** (`remote_server_env.py`) - Remote server (SSH)
3. **JupyterNotebookEnvironment** (`jupyter_notebook_env.py`) - Jupyter notebook
4. **ElectronAppEnvironment** (`electron_app_env.py`) - Electron application

## Incremental Development Guide

### 1. Adding a New Action Space

Follow the pattern from `edit_action_space.py`:

```python
from yoga_next.actions import ActionSpace
from typing import Dict, Any

class MyActionSpace(ActionSpace):
    def __init__(self, action_space_name: str, env=None):
        super().__init__(action_space_name, env)
    
    async def execute(self, action_name: str, param_dict: Dict[str, Any]) -> Dict[str, Any]:
        """Execute action by dispatching to _handle_* methods via reflection"""
        handler = getattr(self, f"_handle_{action_name}", None)
        if not handler:
            return {"status": "error", "message": f"Action '{action_name}' not supported."}
        return await handler(**param_dict)
    
    async def _handle_my_action(self, param1: str, param2: int = 0) -> Dict[str, Any]:
        """Action description
        
        :param param1: Description of parameter 1
        :param param2: Description of parameter 2
        
        Returns:
            Result dictionary
        """
        # Implementation logic
        return {"status": "success", "output": "..."}
```

**Key Conventions**:
- All callable actions are named with `_handle_` prefix
- Use docstrings to describe parameters and return values
- Return format standardized to `{"status": "success|error", ...}`

### 2. Adding a New Environment

Implement the `Environment` abstract base class:

```python
from yoga_next.environments import Environment
from typing import Any, Dict

class MyEnvironment(Environment):
    """My custom environment"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__()
        self.config = config
        self.workspace_root = config.get("workspace_root", ".")
        # Initialize other state
        self.state["workspace"] = self.workspace_root
    
    async def setup(self):
        """Initialize environment resources (connections, etc.)"""
        pass
    
    async def close(self):
        """Clean up resources"""
        pass
    
    def get_observation(self) -> str:
        """Get current environment state description"""
        return f"Workspace: {self.workspace_root}\nState: {dict(self.state)}"
```

**Using Environment in Action Space**:

```python
from yoga_next.actions import ActionSpace
from typing import Dict, Any

class MyActionSpace(ActionSpace):
    def __init__(self, action_space_name: str, env: MyEnvironment):
        super().__init__(action_space_name, env)
    
    async def _handle_my_action(self, param: str) -> Dict[str, Any]:
        """Perform operation using environment"""
        # Access Environment via self.env
        result = await self.env.run_my_operation(param)
        return {"status": "success", "result": result}
```

### 3. Extending Agent Core Functionality

Inherit from `AgentCore` to add custom logic:

```python
from yoga_next.core import AgentCore

class CustomAgent(AgentCore):
    async def execute_single_task(self, task, task_idx=-1, max_steps=100):
        # Custom execution logic
        # Can call parent methods or completely override
        return await super().execute_single_task(task, task_idx, max_steps)
```

### 4. Adding a New Prompt Role

Add in `prompts.py`:

```python
class PromptFactory:
    AGENT_ROLES = {
        "my_role": """
# Role: My Custom Role
...role description...
""",
    }
```

Usage:
```python
agent = YogaAgent(
    agent_config=config,
    agent_type="my_role"
)
```

## Complete Example

### 1. Create Custom Environment

```python
# my_env.py
from yoga_next.environments import Environment
import asyncio

class DatabaseEnvironment(Environment):
    """Database operation environment"""
    
    def __init__(self, config: dict):
        super().__init__()
        self.connection = None
        self.config = config
    
    async def setup(self):
        """Establish database connection"""
        # Implement database connection logic
        self.connection = await self._connect()
        self.state["connected"] = True
    
    async def close(self):
        """Close database connection"""
        if self.connection:
            await self.connection.close()
    
    async def _connect(self):
        """Actual connection logic"""
        pass
    
    def get_observation(self) -> str:
        return f"Database: {self.config.get('host')}\nConnected: {self.state.get('connected', False)}"
```

### 2. Create Action Space Correspondingly

```python
# my_actions.py
from yoga_next.actions import ActionSpace
from typing import Dict, Any

class DatabaseActionSpace(ActionSpace):
    """Database operation toolset"""
    
    def __init__(self, action_space_name: str, env):
        super().__init__(action_space_name, env)
    
    async def execute(self, action_name: str, param_dict: Dict[str, Any]) -> Dict[str, Any]:
        handler = getattr(self, f"_handle_{action_name}", None)
        if not handler:
            return {"status": "error", "message": f"Action '{action_name}' not supported."}
        return await handler(**param_dict)
    
    async def _handle_query(self, sql: str) -> Dict[str, Any]:
        """Execute SQL query
        
        :param sql: SQL query statement
        
        Returns:
            Query results
        """
        results = await self.env.connection.execute(sql)
        return {"status": "success", "results": results}
    
    async def _handle_insert(self, table: str, data: dict) -> Dict[str, Any]:
        """Insert data
        
        :param table: Table name
        :param data: Data dictionary to insert
        """
        await self.env.connection.insert(table, data)
        return {"status": "success", "message": "Data inserted"}
```

### 3. Compose and Use

```python
# main.py
from yoga_next import YogaAgent, AgentConfig
from my_env import DatabaseEnvironment
from my_actions import DatabaseActionSpace

config = AgentConfig.from_yaml("config.yaml")

# Create environment and Action Space
db_env = DatabaseEnvironment({"host": "localhost", "port": 5432})
db_actions = DatabaseActionSpace("db", db_env)

# Create Agent
agent = YogaAgent(
    agent_config=config,
    action_spaces=[db_actions]
)

# Execute task
task = Task(
    task_id="db_task",
    instruction="Insert a new user record into the users table"
)
result = await agent.execute(task)
```

## Configuration Example

```yaml
# config.yaml
api_base_url: "https://api.openai.com/v1"
model_name: "gpt-4"
api_key: "sk-..."
```


# Run specific test
pytest tests/test_edit_agent.py -v
```

## Installation

```bash
pip install -e .

# Development dependencies
pip install -e ".[dev]"
```

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                        YogaAgent                             │
│            (Inherits AgentCore, auto-initializes            │
│             all modules)                                    │
└─────────────────────────────────────────────────────────────┘
                              │
           ┌──────────────────┼──────────────────┐
           ▼                  ▼                  ▼
    ┌─────────────┐   ┌─────────────┐   ┌─────────────┐
    │    Model     │   │   Memory    │   │   Action    │
    │   (LLM)      │   │   System    │   │   Spaces    │
    └─────────────┘   └─────────────┘   └─────────────┘
                                              │
    ┌─────────────────────────────────────────────────────────────┐
    │                                                             │
    ▼                                                             ▼
┌───────────────────┐                                   ┌───────────────────┐
│   LocalEnv        │                                   │ JupyterNotebookEnv │
│                   │                                   │                   │
│  ◄─────────────── │                                   │  ◄─────────────── │
│  │                │                                   │  │                │
│  ▼                │                                   │  ▼                │
│ EditActionSpace  │                                   │ JupyterActionSpace│
│ LocalActionSpace  │                                   │                   │
└───────────────────┘                                   └───────────────────┘
```

**Relationship Legend**:
| Environment | Available Action Spaces |
|-------------|----------------------|
| `LocalEnv` | `EditActionSpace`, `LocalActionSpace` |
| `JupyterNotebookEnv` | `JupyterActionSpace` |

**Constraints**:
- Each Action Space can only bind to specific Environment types
- Multiple Action Spaces can share the same Environment (e.g., both `EditActionSpace` and `LocalActionSpace` bind to `LocalEnv`)
- Cross-environment binding is NOT allowed (e.g., `EditActionSpace` cannot bind to `JupyterNotebookEnv`)

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Create a Pull Request

## License

MIT License
