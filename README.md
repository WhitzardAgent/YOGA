# Yoga-Next

Yoga-Next is an AI agent system designed to perform complex tasks using a combination of planning, memory, and action execution capabilities.

## Project Structure

```
yoga-next/
├── src/
│   └── yoga_next/          # Core package source code
│       ├── __init__.py
│       ├── agent.py        # Main agent implementation
│       ├── memory.py       # Memory management system
│       ├── model.py        # Model interface
│       ├── planner.py      # Task planning system
│       ├── prompts.py      # System prompts
│       ├── utils.py        # Utility functions
│       ├── agent_config.py # Agent configuration
│       ├── hm.py           # Memory chunk definitions
│       ├── actions/        # Action space definitions
│       ├── environments/   # Environment implementations
│       └── tasks/          # Task definitions
├── tests/
│   └── test_shell_agent.py # Main test file
├── task_examples/          # Example tasks
├── configs/                # Configuration files
├── setup.py               # Package setup
├── pyproject.toml         # Modern Python project configuration
└── README.md
```

## Installation

To install the package in development mode:

```bash
pip install -e .
```

## Usage

The main entry point for the agent system is in [src/yoga_next/agent.py](file:///Users/morinop/coding/yoga-next/src/yoga_next/agent.py). You can run the test to see an example of how the system works:

```bash
python -m pytest tests/ -v
```

Or run the main test file directly:

```bash
cd tests
python test_shell_agent.py
```

## Testing

Tests are located in the [tests](file:///Users/morinop/coding/yoga-next/actions/remote_server_action_space.py#L1-L15) directory. Run them using:

```bash
python -m pytest tests/
```

## Development

To set up the development environment:

1. Clone the repository
2. Install in editable mode: `pip install -e .`
3. Run tests to verify the installation: `python -m pytest tests/`