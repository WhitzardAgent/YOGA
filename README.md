# Yoga-Next

一个模块化的 AI Agent 框架，支持多种执行环境和工具集成。

## 快速开始

```python
from yoga_next import YogaAgent, AgentConfig

# 从配置文件加载
config = AgentConfig.from_yaml("config.yaml")

# 创建 Agent
agent = YogaAgent(agent_config=config)

# 执行任务
from yoga_next.tasks import Task
task = Task(task_id="example", instruction="帮我创建一个 Python 文件")
result = await agent.execute(task)
```

## 项目结构

```
src/yoga_next/
├── core/                    # 核心模块
│   ├── agent_core.py        # Agent 核心执行逻辑
│   ├── action_executor.py   # 动作执行器
│   ├── memory_manager.py    # 记忆管理
│   ├── state_builder.py     # 状态构建
│   ├── renderer.py          # UI 渲染
│   └── formatter.py         # 输出格式化
├── actions/                 # Action Spaces（工具集）
│   ├── base.py             # ActionSpace 基类
│   ├── edit_action_space.py    # 文件编辑
│   ├── local_action_space.py   # 本地 shell
│   ├── remote_server_action_space.py  # 远程服务器
│   ├── jupyter_notebook_action_space.py  # Jupyter
│   └── thinking.py         # 思考空间
├── environments/           # 执行环境
│   ├── base.py
│   ├── local_env.py
│   ├── remote_server_env.py
│   └── jupyter_notebook_env.py
├── model.py               # LLM 模型封装
├── prompts.py             # Prompt 工厂
├── tasks.py               # 任务定义
└── yoga_agent.py          # 主入口
```

## 增量开发指南

### 1. 添加新的 Action Space

参考 `edit_action_space.py` 的实现模式：

```python
from yoga_next.actions import ActionSpace
from typing import Dict, Any

class MyActionSpace(ActionSpace):
    def __init__(self, action_space_name: str, env=None):
        super().__init__(action_space_name, env)
    
    async def execute(self, action_name: str, param_dict: Dict[str, Any]) -> Dict[str, Any]:
        """执行动作，通过反射调用 _handle_* 方法"""
        handler = getattr(self, f"_handle_{action_name}", None)
        if not handler:
            return {"status": "error", "message": f"Action '{action_name}' not supported."}
        return await handler(**param_dict)
    
    async def _handle_my_action(self, param1: str, param2: int = 0) -> Dict[str, Any]:
        """动作描述
        
        :param param1: 参数1描述
        :param param2: 参数2描述
        
        Returns:
            执行结果字典
        """
        # 实现逻辑
        return {"status": "success", "output": "..."}
```

**关键约定**：
- 所有可调用动作以 `_handle_` 开头命名
- 使用 docstring 描述参数和返回值
- 返回格式统一为 `{"status": "success|error", ...}`

### 2. 添加新的 Environment

```python
from yoga_next.environments import Environment

class MyEnvironment(Environment):
    def __init__(self, config: dict):
        self.config = config
        self.workspace_root = config.get("workspace_root", ".")
    
    async def setup(self):
        """初始化环境连接"""
        pass
    
    async def run_shell(self, command: str) -> dict:
        """执行 shell 命令"""
        pass
    
    async def read_file(self, path: str) -> dict:
        """读取文件"""
        pass
    
    async def write_file(self, path: str, content: str) -> dict:
        """写入文件"""
        pass
    
    def get_observation(self) -> str:
        """获取环境当前状态描述"""
        return f"Workspace: {self.workspace_root}"
```

### 3. 扩展 Agent 核心功能

继承 `AgentCore` 添加自定义逻辑：

```python
from yoga_next.core import AgentCore

class CustomAgent(AgentCore):
    async def execute_single_task(self, task, task_idx=-1, max_steps=100):
        # 自定义执行逻辑
        # 可以调用父类方法或完全重写
        return await super().execute_single_task(task, task_idx, max_steps)
```

### 4. 添加新的 Prompt 角色

在 `prompts.py` 中添加：

```python
class PromptFactory:
    AGENT_ROLES = {
        "my_role": """
# Role: My Custom Role
...角色描述...
""",
    }
```

使用：
```python
agent = YogaAgent(
    agent_config=config,
    agent_type="my_role"
)
```

## 核心概念

### Action Space

Action Space 是 Agent 可调用的工具集合。每个 Action Space：
- 封装一组相关操作（如文件操作、shell 命令）
- 通过 `execute(action_name, params)` 统一调用
- 使用 `_handle_*` 方法实现具体功能

### Environment

Environment 提供底层执行能力：
- `LocalEnvironment`: 本地 shell 和文件操作
- `RemoteServerEnvironment`: 通过 SSH/AgentBridge 连接远程服务器
- `JupyterNotebookEnvironment`: Jupyter 内核交互

### Memory System

- `Memory`: 短期对话历史
- `MemoryStream`: 长期记忆流，记录所有交互
- `MemoryManager`: 统一管理记忆操作

### State Builder

构建 Agent 的输入状态，包含：
- 任务目标
- 历史思考轨迹
- 长期记忆摘要
- 上一步执行结果
- 环境状态

## 配置示例

```yaml
# config.yaml
api_base_url: "https://api.openai.com/v1"
model_name: "gpt-4"
api_key: "sk-..."
```

## 测试

```bash
# 运行测试
pytest tests/

# 运行特定测试
pytest tests/test_edit_agent.py -v
```

## 依赖安装

```bash
pip install -e .

# 开发依赖
pip install -e ".[dev]"
```

## 架构图

```
┌─────────────────────────────────────────┐
│              YogaAgent                  │
│  (继承 AgentCore, 自动初始化所有模块)    │
└─────────────────────────────────────────┘
                   │
    ┌──────────────┼──────────────┐
    ▼              ▼              ▼
┌─────────┐  ┌──────────┐  ┌──────────┐
│  Model  │  │ Memory   │  │ Action   │
│  (LLM)  │  │ System   │  │ Spaces   │
└─────────┘  └──────────┘  └──────────┘
                                  │
                    ┌─────────────┼─────────────┐
                    ▼             ▼             ▼
              ┌─────────┐  ┌──────────┐  ┌──────────┐
              │  Edit   │  │  Local   │  │ Jupyter  │
              │  Space  │  │  Space   │  │  Space   │
              └─────────┘  └──────────┘  └──────────┘
```

## 贡献指南

1. Fork 仓库
2. 创建功能分支 (`git checkout -b feature/amazing-feature`)
3. 提交更改 (`git commit -m 'Add amazing feature'`)
4. 推送分支 (`git push origin feature/amazing-feature`)
5. 创建 Pull Request

## License

MIT License
