# YOGA - Next Generation AI Agent Framework

<p align="center">
  <strong>🚀 An Intelligent Agent Framework with Dynamic Planning, Rich UI, and Self-Healing Capabilities</strong>
</p>

<p align="center">
  <a href="#-features">Features</a> •
  <a href="#-architecture">Architecture</a> •
  <a href="#-quick-start">Quick Start</a> •
  <a href="#-developer-guide">Developer Guide</a> •
  <a href="#-action-spaces">Action Spaces</a>
</p>

---

## ✨ Features

### 🔮 Dynamic Sequential Thinking
- **Mandatory first-step analysis**: Every task begins with `sequential_thinking` for structured reasoning
- **Dynamic replanning**: When errors occur, use `is_revision=True` to update your plan
- **Chain-of-thought exploration**: Explore hypotheses and verify them before executing actions

### 🎨 Rich Interactive Display
- **Live progress tracking**: Real-time step-by-step visualization with Rich library
- **Color-coded output**: Syntax highlighting for shell commands, code blocks, and diffs
- **Structured observations**: Markdown-formatted output with language-aware code blocks
- **Tree visualization**: Directory structure with Git-style tree display

### 🛡️ Enterprise-Grade Reliability
- **Timeout protection**: Configurable per-action timeouts (default 60s, long operations up to 300s)
- **Self-healing**: Fuzzy string matching suggests corrections for failed operations
- **Syntax validation**: Python files validated with `ast.parse()` before writing
- **Path security**: Workspace-anchored path resolution prevents escape attempts

### 📊 Memory & Trajectory
- **Long-term memory**: Persistent working memory across task steps
- **Trajectory logging**: JSONL-formatted execution history for debugging and replay
- **Thought trace**: Visual indicator of reasoning progress with revision tracking

### 🔌 Modular Architecture
- **ActionSpace pattern**: Composable action spaces via `UnionActionSpace`
- **Environment abstraction**: Support for Local, Jupyter, and Remote Server environments
- **Auto-generated schemas**: Tool descriptions from docstrings via `inspect`

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         YOGA Agent                               │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐ │
│  │   Planner   │  │   Memory    │  │      Model (LLM)        │ │
│  └─────────────┘  └─────────────┘  └─────────────────────────┘ │
├─────────────────────────────────────────────────────────────────┤
│                    Unified Action Space                          │
│  ┌───────────┐ ┌───────────┐ ┌───────────┐ ┌───────────────┐  │
│  │  Control  │ │ Thinking  │ │   Edit    │ │   Local/Remote │ │
│  │  Space    │ │  Space    │ │  Space    │ │    Spaces     │ │
│  └───────────┘ └───────────┘ └───────────┘ └───────────────┘  │
├─────────────────────────────────────────────────────────────────┤
│                    Environment Layer                             │
│  ┌───────────────┐  ┌─────────────────┐  ┌─────────────────┐   │
│  │ LocalCondaEnv │  │ JupyterNotebook │  │ RemoteServerEnv │   │
│  └───────────────┘  └─────────────────┘  └─────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

### Core Components

| Component | Purpose |
|-----------|---------|
| `Agent` | Main orchestrator with timeout protection and UI rendering |
| `ActionSpace` | Base class for action implementations |
| `UnionActionSpace` | Combines multiple action spaces dynamically |
| `Environment` | Abstraction for file system, shell, and notebook operations |
| `Memory` | Working memory for conversation context |
| `MemoryStream` | Trajectory logging for debugging |

---

## 🚀 Quick Start

### Installation

```bash
git clone https://github.com/your-org/yoga-next.git
cd yoga-next
pip install -e .
```

### Basic Usage

```python
from yoga_next import Agent, AgentConfig, LocalActionSpace
from yoga_next.environments import LocalCondaEnvironment

# Configure the agent
config = AgentConfig(
    api_base_url="https://api.openai.com/v1",
    model_name="gpt-4o",
    api_key="your-api-key"
)

# Create environment and action space
env = LocalCondaEnvironment({"workspace_root": "/path/to/workspace"})
action_space = LocalActionSpace("local", env)

# Initialize agent
agent = Agent(
    agent_config=config,
    action_spaces=[action_space],
    use_rich_display=True
)

# Execute a task
from yoga_next import Task
task = Task(task_id="example", instruction="Analyze the codebase structure")
result = await agent.execute(task)
```

---

## 💻 Developer Guide

### Creating Custom Action Spaces

```python
from yoga_next.actions import ActionSpace
from typing import Dict, Any

class MyActionSpace(ActionSpace):
    def __init__(self, env=None):
        super().__init__("my_actions", env)

    async def execute(self, action_name: str, param_dict: Dict[str, Any]) -> Dict[str, Any]:
        handler = getattr(self, f"_handle_{action_name}", None)
        if not handler:
            return {"status": "error", "message": f"Unknown action: {action_name}"}
        result = await handler(**param_dict)
        return {"status": "success", "output": result}

    async def _handle_my_action(self, param: str) -> Dict[str, Any]:
        """Execute custom action.

        :param param: Description of the parameter.
        """
        # Your implementation here
        return {"result": "done"}
```

### Registering with Agent

```python
from yoga_next import Agent, AgentConfig

agent = Agent(
    agent_config=config,
    action_spaces=[MyActionSpace(env), LocalActionSpace(env)],
    use_rich_display=True
)
```

### Path Safety

All file paths are automatically:
- Resolved relative to workspace_root
- Validated to prevent escape attempts
- Converted to absolute paths before I/O

```python
# In EditActionSpace handlers:
resolved_path = self._resolve_path(path)  # Safe path handling
await self.env.read_file(resolved_path)
```

### Memory Stream Usage

```python
# Enable trajectory logging
agent.dump("/path/to/trajectory.jsonl")

# Replay execution
from yoga_next import MemoryStream
stream = MemoryStream.load("/path/to/trajectory.jsonl")
```

---

## 🔧 Action Spaces

### EditActionSpace - Advanced File Editing

| Action | Description |
|--------|-------------|
| `view(path, view_range)` | View file/directory with line numbers and syntax highlighting |
| `create(path, file_text)` | Create files with auto parent directory creation |
| `str_replace(path, old_str, new_str)` | Replace content with uniqueness checking and diff output |
| `insert(path, insert_line, new_str)` | Insert lines with Python syntax validation |
| `search(path, keyword)` | Grep-based search with result limits |
| `list_tree(path, depth)` | Recursive directory tree visualization |

### LocalActionSpace - Shell Operations

| Action | Description |
|--------|-------------|
| `execute_shell(command)` | Execute bash commands in conda environment |
| `run_in_conda_env(command)` | Run commands in specific conda environment |
| `read_file(path)` | Read file contents |
| `write_file(path, content)` | Write file contents |
| `list_directory(path, depth)` | Recursive directory listing |
| `exists(path)` | Check path existence |

### ThinkingActionSpace - Dynamic Planning

| Action | Description |
|--------|-------------|
| `sequential_thinking(...)` | Structured reasoning with plan revision support |

---

## 🎯 Thinking Protocol

Every task **must** start with `sequential_thinking`:

```markdown
sequential_thinking(
    thought="Analyze the requirements and break down the task",
    thought_number=1,
    total_thoughts=3,
    next_thought_needed=True,
    is_revision=False
)
```

**Protocol Rules:**
1. First action for any new task = `sequential_thinking`
2. On error: use `is_revision=True` to update plan
3. Only set `next_thought_needed=False` when plan is solid
4. Maximum 5 consecutive failed attempts → drop subtask

---

## 📁 Project Structure

```
yoga-next/
├── src/yoga_next/
│   ├── agent.py              # Main Agent implementation
│   ├── memory.py             # Working memory management
│   ├── model.py              # LLM interface with retry logic
│   ├── planner.py            # Task planning
│   ├── prompts.py            # System prompts & Thinking Protocol
│   ├── utils.py              # Logging, extraction, UI utilities
│   ├── hm.py                 # Memory chunk definitions
│   ├── agent_config.py       # Configuration dataclass
│   ├── actions/
│   │   ├── base.py           # ActionSpace base & schema generation
│   │   ├── edit_action_space.py  # Advanced file editing
│   │   ├── local_action_space.py # Shell & file operations
│   │   ├── thinking.py       # Sequential thinking handler
│   │   ├── control.py        # Task completion signaling
│   │   └── ...               # Other action spaces
│   ├── environments/
│   │   ├── base.py           # Environment abstract base
│   │   ├── local_env.py      # Local conda environment
│   │   ├── jupyter_notebook_env.py
│   │   └── remote_server_env.py
│   └── tasks/
│       └── task.py           # Task definitions
├── tests/                    # Test suite
├── configs/                  # Configuration files
├── task_examples/            # Example challenges
├── setup.py                  # Package setup
└── README.md                 # This file
```

---

## 🧪 Testing

```bash
# Run all tests
python -m pytest tests/ -v

# Run specific test
python tests/test_local_agent.py

# Run fuzzy self-healing tests
python tests/run_fuzzy_self_healing_test.py
```

---

## 📝 License

MIT License

---

<p align="center">
  Built with ❤️ by the YOGA Team
</p>
