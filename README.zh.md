# Yoga-Next

一个模块化的 AI Agent 框架，支持多种执行环境和工具集成。

[English](README.md) | 中文文档

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
│   ├── base.py            # Environment 抽象基类
│   ├── local_env.py       # 本地环境
│   ├── remote_server_env.py  # 远程服务器环境
│   ├── jupyter_notebook_env.py  # Jupyter 环境
│   └── electron_app_env.py # Electron 应用环境
├── model.py               # LLM 模型封装
├── prompts.py             # Prompt 工厂
├── tasks.py               # 任务定义
└── yoga_agent.py          # 主入口
```

## 核心概念

### Environment

Environment 是 Agent 执行动作的底层环境，封装了资源连接和操作接口。

**核心方法**：

| 方法 | 说明 | 是否必须实现 |
|------|------|-------------|
| `get_observation()` | 获取环境当前状态描述 | 否（默认返回空字符串） |
| `setup()` | 初始化资源（连接等） | 否 |
| `close()` | 清理资源 | 否 |
| `update_state()` | 更新内部状态 | 否 |

### 可用 Environment

1. **LocalEnvironment** (`local_env.py`) - 本地开发环境
2. **RemoteServerEnvironment** (`remote_server_env.py`) - 远程服务器（SSH）
3. **JupyterNotebookEnvironment** (`jupyter_notebook_env.py`) - Jupyter 笔记本
4. **ElectronAppEnvironment** (`electron_app_env.py`) - Electron 应用

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

实现 `Environment` 抽象基类：

```python
from yoga_next.environments import Environment
from typing import Any, Dict

class MyEnvironment(Environment):
    """我的自定义环境"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__()
        self.config = config
        self.workspace_root = config.get("workspace_root", ".")
        # 初始化其他状态
        self.state["workspace"] = self.workspace_root
    
    async def setup(self):
        """初始化环境连接等资源"""
        pass
    
    async def close(self):
        """清理资源"""
        pass
    
    def get_observation(self) -> str:
        """获取环境当前状态描述"""
        return f"Workspace: {self.workspace_root}\nState: {dict(self.state)}"
```

**在 Action Space 中使用 Environment**：

```python
from yoga_next.actions import ActionSpace
from typing import Dict, Any

class MyActionSpace(ActionSpace):
    def __init__(self, action_space_name: str, env: MyEnvironment):
        super().__init__(action_space_name, env)
    
    async def _handle_my_action(self, param: str) -> Dict[str, Any]:
        """使用环境执行操作"""
        # 通过 self.env 访问 Environment
        result = await self.env.run_my_operation(param)
        return {"status": "success", "result": result}
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

## 完整示例

### 1. 创建自定义 Environment

```python
# my_env.py
from yoga_next.environments import Environment
import asyncio

class DatabaseEnvironment(Environment):
    """数据库操作环境"""
    
    def __init__(self, config: dict):
        super().__init__()
        self.connection = None
        self.config = config
    
    async def setup(self):
        """建立数据库连接"""
        # 实现数据库连接逻辑
        self.connection = await self._connect()
        self.state["connected"] = True
    
    async def close(self):
        """关闭数据库连接"""
        if self.connection:
            await self.connection.close()
    
    async def _connect(self):
        """实际连接逻辑"""
        pass
    
    def get_observation(self) -> str:
        return f"Database: {self.config.get('host')}\nConnected: {self.state.get('connected', False)}"
```

### 2. 创建配套的 Action Space

```python
# my_actions.py
from yoga_next.actions import ActionSpace
from typing import Dict, Any

class DatabaseActionSpace(ActionSpace):
    """数据库操作工具集"""
    
    def __init__(self, action_space_name: str, env):
        super().__init__(action_space_name, env)
    
    async def execute(self, action_name: str, param_dict: Dict[str, Any]) -> Dict[str, Any]:
        handler = getattr(self, f"_handle_{action_name}", None)
        if not handler:
            return {"status": "error", "message": f"Action '{action_name}' not supported."}
        return await handler(**param_dict)
    
    async def _handle_query(self, sql: str) -> Dict[str, Any]:
        """执行 SQL 查询
        
        :param sql: SQL 查询语句
        
        Returns:
            查询结果
        """
        results = await self.env.connection.execute(sql)
        return {"status": "success", "results": results}
    
    async def _handle_insert(self, table: str, data: dict) -> Dict[str, Any]:
        """插入数据
        
        :param table: 表名
        :param data: 要插入的数据字典
        """
        await self.env.connection.insert(table, data)
        return {"status": "success", "message": "Data inserted"}
```

### 3. 组合使用

```python
# main.py
from yoga_next import YogaAgent, AgentConfig
from my_env import DatabaseEnvironment
from my_actions import DatabaseActionSpace

config = AgentConfig.from_yaml("config.yaml")

# 创建环境和 Action Space
db_env = DatabaseEnvironment({"host": "localhost", "port": 5432})
db_actions = DatabaseActionSpace("db", db_env)

# 创建 Agent
agent = YogaAgent(
    agent_config=config,
    action_spaces=[db_actions]
)

# 执行任务
task = Task(
    task_id="db_task",
    instruction="在 users 表中插入一条新用户数据"
)
result = await agent.execute(task)
```

## 配置示例

```yaml
# config.yaml
api_base_url: "https://api.openai.com/v1"
model_name: "gpt-4"
api_key: "sk-..."
```

## 试试看

```bash
python tests/test_edit_agent.py
```

## 依赖安装

```bash
pip install -e .

# 开发依赖
pip install -e ".[dev]"
```

## 架构图

```
┌─────────────────────────────────────────────────────────────┐
│                        YogaAgent                             │
│            (继承 AgentCore，自动初始化所有模块)                 │
└─────────────────────────────────────────────────────────────┘
                              │
           ┌──────────────────┼──────────────────┐
           ▼                  ▼                  ▼
    ┌─────────────┐   ┌─────────────┐   ┌─────────────┐
    │    Model    │   │   Memory    │   │   Action    │
    │   (LLM)     │   │   System    │   │   Spaces    │
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

**关系说明**：
| Environment | 可绑定的 Action Space |
|-------------|---------------------|
| `LocalEnv` | `EditActionSpace`, `LocalActionSpace` |
| `JupyterNotebookEnv` | `JupyterActionSpace` |

**约束规则**：
- 每个 Action Space 只能绑定到特定类型的 Environment
- 多个 Action Space 可以共享同一个 Environment（如 `EditActionSpace` 和 `LocalActionSpace` 都绑定到 `LocalEnv`）
- 不能跨环境绑定（如 `EditActionSpace` 不能绑定到 `JupyterNotebookEnv`）

## 贡献指南

1. Fork 仓库
2. 创建功能分支 (`git checkout -b feature/amazing-feature`)
3. 提交更改 (`git commit -m 'Add amazing feature'`)
4. 推送分支 (`git push origin feature/amazing-feature`)
5. 创建 Pull Request

## License

MIT License
