# Yoga-Next 开发规范 (PRD)

## 项目概述

Yoga-Next 是一个模块化的 AI Agent 框架，支持多种执行环境和工具集成。

### 核心特性

- **模块化设计**：Model、Memory、Action Spaces、Environments 独立可替换
- **多环境支持**：本地环境、远程服务器、Jupyter Notebook、Electron 应用
- **动作执行**：统一的 ActionSpace 接口，支持异步执行
- **记忆系统**：短期对话历史 + 长期记忆流

## 代码结构

```
src/yoga_next/
├── core/                    # 核心模块
│   ├── agent_core.py        # Agent 执行主循环
│   ├── action_executor.py   # 动作执行器
│   ├── memory_manager.py    # 记忆管理
│   ├── state_builder.py     # 状态构建
│   ├── renderer.py          # UI 渲染
│   ├── formatter.py         # 输出格式化
│   └── base.py             # 抽象基类
├── actions/                 # Action Spaces
│   ├── base.py             # ActionSpace 基类
│   ├── edit_action_space.py    # 文件编辑
│   ├── local_action_space.py   # 本地 shell
│   ├── remote_server_action_space.py  # 远程服务器
│   ├── jupyter_notebook_action_space.py  # Jupyter
│   ├── thinking.py         # 思考空间
│   └── latex_action_space.py  # LaTeX 编辑
├── environments/           # 执行环境
│   ├── base.py             # Environment 基类
│   ├── local_env.py        # 本地环境
│   ├── remote_server_env.py # 远程服务器
│   ├── jupyter_notebook_env.py  # Jupyter
│   └── electron_app_env.py # Electron 应用
├── model.py               # LLM 模型封装
├── prompts.py             # Prompt 工厂
├── tasks.py               # 任务定义
└── yoga_agent.py          # 主入口
```

## 开发规范

### 1. 命名规范

| 类型 | 规范 | 示例 |
|------|------|------|
| 类名 | PascalCase | `YogaAgent`, `ActionSpace` |
| 函数/方法 | snake_case | `get_observation()`, `execute()` |
| 变量 | snake_case | `action_space`, `memory_stream` |
| 常量 | UPPER_SNAKE_CASE | `DEFAULT_TIMEOUT` |
| Action Handler | `_handle_<action_name>` | `_handle_execute_shell()` |
| 私有属性 | `_prefix` | `_action_space`, `_memory` |

### 2. Action Space 规范

所有 Action Space 必须继承 `ActionSpace`，并遵循以下模式：

```python
from yoga_next.actions import ActionSpace
from typing import Dict, Any

class MyActionSpace(ActionSpace):
    def __init__(self, action_space_name: str, env=None):
        super().__init__(action_space_name, env)
    
    async def execute(self, action_name: str, param_dict: Dict[str, Any]) -> Dict[str, Any]:
        """统一入口：通过反射调用 _handle_* 方法"""
        handler = getattr(self, f"_handle_{action_name}", None)
        if not handler:
            return {"status": "error", "message": f"Action '{action_name}' not supported."}
        return await handler(**param_dict)
    
    async def _handle_my_action(self, param1: str, param2: int = 0) -> Dict[str, Any]:
        """动作描述（会显示给 Agent）
        
        :param param1: 参数1描述
        :param param2: 参数2描述
        
        Returns:
            执行结果字典
        """
        # 实现逻辑
        return {"status": "success", "output": "..."}
```

**关键约定**：

1. 所有可调用动作必须以 `_handle_` 开头
2. docstring 必须描述参数和返回值
3. 返回格式统一为 `{"status": "success|error", ...}`
4. 使用 `self.env` 访问底层 Environment

### 3. Environment 规范

所有 Environment 必须继承 `Environment`：

```python
from yoga_next.environments import Environment
from typing import Any, Dict

class MyEnvironment(Environment):
    def __init__(self, config: Dict[str, Any]):
        super().__init__()
        self.config = config
        self.state["connected"] = False
    
    async def setup(self):
        """初始化资源（可选）"""
        self.state["connected"] = True
    
    async def close(self):
        """清理资源（可选）"""
        pass
    
    def get_observation(self) -> str:
        """返回环境当前状态描述"""
        return f"Connected: {self.state.get('connected', False)}"
```

### 4. Action Space 与 Environment 绑定规则

| Action Space | 可绑定的 Environment |
|--------------|---------------------|
| `EditActionSpace` | `LocalEnv` |
| `LocalActionSpace` | `LocalEnv` |
| `RemoteServerSpace` | `RemoteServerEnv` |
| `JupyterNotebookActionSpace` | `JupyterNotebookEnv` |
| `ThinkingActionSpace` | 无（通用） |

**约束**：Action Space 只能绑定到特定类型的 Environment，不能跨环境绑定。

### 5. 返回值规范

所有 `_handle_*` 方法必须返回字典：

```python
# 成功
return {"status": "success", "output": "...", "key": "value"}

# 失败
return {"status": "error", "message": "Error description"}
```

### 6. 文件结构规范

每个模块文件应该：

```python
"""
Module docstring - 描述模块功能
"""

from typing import Dict, Any, List
# ... imports ...

# 公共类/函数
class MyClass:
    """类 docstring"""
    pass

# 私有函数（如果需要）
def _private_helper():
    pass
```

## 模块间关系

```
YogaAgent (主入口)
    │
    ├── Model (LLM)
    │
    ├── Memory (对话历史)
    │
    ├── MemoryStream (长期记忆)
    │
    ├── Action Space 1 ──┐
    ├── Action Space 2 ──┼──► Environment (共享)
    └── Action Space 3 ──┘
```

### 依赖方向

- `YogaAgent` → `AgentCore` → 各核心模块
- `ActionSpace` → `Environment`（通过 `self.env`）
- `AgentCore` → `ActionSpace.execute()` → `_handle_*()`

## 添加新功能指南

### 1. 添加新的 Action Space

步骤：
1. 在 `actions/` 目录下创建新文件
2. 继承 `ActionSpace` 基类
3. 实现 `execute()` 方法（反射模式）
4. 实现 `_handle_*` 方法
5. 在 `actions/__init__.py` 中导出

### 2. 添加新的 Environment

步骤：
1. 在 `environments/` 目录下创建新文件
2. 继承 `Environment` 基类
3. 实现必要方法（`setup()`, `get_observation()` 等）
4. 在 `environments/__init__.py` 中导出

### 3. 添加新的 Prompt 角色

在 `prompts.py` 中的 `PromptFactory.AGENT_ROLES` 添加：

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
agent = YogaAgent(agent_config=config, agent_type="my_role")
```

## 测试规范

### 测试文件位置

```
tests/
├── test_edit_agent.py     # EditActionSpace 测试
└── ...                   # 其他测试
```

### 测试模式

```python
import asyncio
from yoga_next import YogaAgent
from yoga_next.environments import LocalCondaEnvironment
from yoga_next.actions import EditActionSpace, LocalActionSpace

async def test_my_feature():
    # 1. 初始化配置
    agent_config = AgentConfig.from_yaml("config.yaml")
    
    # 2. 创建环境和 Action Space
    env = LocalCondaEnvironment(config)
    my_space = MyActionSpace("my", env)
    
    # 3. 创建 Agent
    agent = YogaAgent(
        agent_config=agent_config,
        action_spaces=[my_space]
    )
    
    # 4. 执行任务
    task = Task(task_id="test_001", instruction="...")
    result = await agent.execute(task)
    
    # 5. 验证结果
    assert result is not None

if __name__ == "__main__":
    asyncio.run(test_my_feature())
```

## 常见问题

### Q1: 如何让 Agent 调用新的 action？

确保：
1. Action Space 已添加到 Agent
2. `_handle_*` 方法已正确定义
3. docstring 描述清晰

### Q2: 如何调试 Agent 执行？

```python
# 启用详细日志
import logging
logging.basicConfig(level=logging.DEBUG)

# 或查看 memory stream
agent.memory_stream.dump("debug.jsonl")
```

### Q3: 如何添加异步 Environment？

```python
class AsyncEnv(Environment):
    async def setup(self):
        await self._connect_async()
    
    async def close(self):
        await self._disconnect_async()
```

## API 参考

### YogaAgent

```python
agent = YogaAgent(
    agent_config: AgentConfig,
    action_spaces: List[ActionSpace] = None,
    agent_type: str = "general",
    use_rich_display: bool = False,
    timeout: int = 60
)

result = await agent.execute(task: Task) -> Dict
```

### ActionSpace

```python
space = MyActionSpace("name", env)

# Agent 调用入口
result = await space.execute(action_name: str, param_dict: Dict) -> Dict
```

### Environment

```python
env = MyEnvironment(config)

await env.setup()           # 初始化
await env.close()           # 清理
obs = env.get_observation()  # 获取状态
```

## 配置

```yaml
# config.yaml
api_base_url: "https://api.openai.com/v1"
model_name: "gpt-4"
api_key: "sk-..."
```

## 快速参考

| 操作 | 代码 |
|------|------|
| 创建 Agent | `agent = YogaAgent(agent_config=config)` |
| 添加 Action Space | `YogaAgent(..., action_spaces=[space])` |
| 执行任务 | `result = await agent.execute(task)` |
| 绑定 Environment | `MyActionSpace("name", env)` |
| 内存导出 | `agent.dump("path.jsonl")` |

## 贡献指南

1. Fork 仓库
2. 创建功能分支 (`git checkout -b feature/name`)
3. 遵循代码规范
4. 添加测试
5. 提交 PR

## 版本历史

- v0.1.0: 初始版本，支持基本 Agent 执行
