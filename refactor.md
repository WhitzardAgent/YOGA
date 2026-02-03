# 架构重构方案

## 1. 概述

本文档提出了对YOGA Agent框架的架构改进方案，旨在提升模块化程度和可扩展性，同时保持现有功能和实现的完全兼容。改进方案遵循以下核心原则：

- 保持向后兼容，不改变现有API和行为
- 遵循依赖倒置原则，引入抽象层
- 实现关注点分离，降低类职责
- 引入标准设计模式，提升代码可维护性
- 支持插件化扩展，增强生态系统

## 2. 当前架构分析

### 2.1 核心模块结构

当前系统由以下核心模块组成：

```
yoga_next/
├── agent.py (465行)           # 核心Agent类，承担过多职责
├── agent_config.py (30行)     # 简单配置类
├── agent_service.py (505行)   # FastAPI服务，紧耦合
├── planner.py (47行)          # 任务规划器
├── memory.py (114行)          # 短期记忆管理
├── hm.py (50行)               # 长期记忆流
├── model.py (136行)           # LLM模型包装器
├── prompts.py (178行)         # 提示词工厂
├── utils.py (683行)           # 工具函数集合
├── actions/                   # 动作空间模块
│   ├── base.py               # ActionSpace抽象基类
│   ├── control.py            # 控制动作
│   ├── thinking.py           # 思考动作
│   ├── edit_action_space.py  # 编辑动作
│   ├── glim_app_action_space.py
│   ├── local_action_space.py
│   ├── research_action_space.py
│   ├── latex_action_space.py
│   └── remote_server_action_space.py
└── environments/              # 环境模块
    ├── base.py               # Environment抽象基类
    ├── local_env.py          # 本地Conda环境
    ├── electron_app_env.py   # Electron应用环境
    └── ...
```

### 2.2 识别的主要问题

#### 问题1：Agent类职责过重

`Agent`类（465行）当前承担了以下职责：

- 任务执行主循环
- 内存管理与状态追踪
- 动作白名单检查
- UI渲染协调
- 思考空间管理
- 记忆流记录

这种设计违反了单一职责原则，导致：
- 代码难以维护和测试
- 扩展动作类型需要修改Agent类
- UI逻辑与核心逻辑紧密耦合

#### 问题2：路径解析代码重复

在6个ActionSpace实现中发现了重复的路径解析代码：

```python
# 每个ActionSpace中重复的代码模式
def _get_workspace_root(self) -> str:
    if hasattr(self.env, 'config') and isinstance(self.env.config, dict):
        return self.env.config.get("workspace_root", self.env.workspace_root)
    if hasattr(self.env, 'workspace_root'):
        return self.env.workspace_root
    return os.getcwd()

def _resolve_path(self, path: str) -> str:
    from pathlib import Path
    workspace_root = self._get_workspace_root()
    workspace_resolved = Path(workspace_root).resolve()
    # ...相同的安全检查逻辑
```

#### 问题3：硬编码依赖

当前存在多处硬编码依赖：

```python
# agent.py中的硬编码
self.thinking_space = ThinkingActionSpace()

# agent_service.py中的硬编码
self.env = ElectronAppEnv(env_config)
self.glim_space = GlimAppActionSpace("glim_app", self.env)
```

#### 问题4：配置系统薄弱

当前`AgentConfig`类仅支持YAML文件加载：
- 缺乏环境变量支持
- 缺少配置验证
- 不支持配置继承和覆盖

#### 问题5：扩展点不足

系统当前缺乏：
- 标准化的动作注册机制
- 环境工厂模式
- 插件化支持
- 事件总线系统

## 3. 重构方案

### 3.1 总体架构

改进后的架构采用分层设计：

```
┌─────────────────────────────────────────────────────┐
│                    Presentation Layer               │
│           (AgentService, API Endpoints)             │
├─────────────────────────────────────────────────────┤
│                   Core Agent Layer                  │
│   AgentCore, AgentExecutor, AgentState, AgentDisplay│
├─────────────────────────────────────────────────────┤
│                  Abstraction Layer                  │
│   ActionRegistry, EnvironmentFactory, EventBus      │
├─────────────────────────────────────────────────────┤
│                  Domain Layer                       │
│     ActionSpaces, Environments, Memory Systems      │
├─────────────────────────────────────────────────────┤
│                  Foundation Layer                   │
│   Config, Logging, Utilities, PathResolver          │
└─────────────────────────────────────────────────────┘
```

### 3.2 核心改进一：拆分Agent类

将大型`Agent`类拆分为多个专职类：

#### 3.2.1 AgentCore - 核心执行逻辑

```python
# src/yoga_next/core/agent_core.py
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from ..tasks import Task
from ..memory import Memory
from ..model import Model
from ..actions import ActionSpace
from ..environments import Environment

class AgentCore(ABC):
    """Agent核心执行引擎，专注于任务执行逻辑"""

    def __init__(
        self,
        model: Model,
        action_spaces: List[ActionSpace],
        environment: Optional[Environment] = None
    ):
        self.model = model
        self.action_space = UnionActionSpace(action_spaces)
        self.environment = environment
        self.memory = Memory(model)
        self.task: Optional[Task] = None
        self.final_result: Optional[Dict[str, Any]] = None

    @abstractmethod
    async def execute_single_task(
        self,
        task: Task,
        task_idx: int,
        max_steps: int
    ) -> str:
        """执行单个任务，由子类实现具体策略"""
        pass

    async def execute(self, task: Task, max_steps: int = 100) -> Dict[str, Any]:
        """任务执行入口"""
        self.task = task
        self.final_result = None
        
        result = await self.execute_single_task(task, task_idx=-1, max_steps=max_steps)
        
        return {"result": result, "final_output": self.final_result}

    def create_state(
        self,
        task: Task,
        prev_action: str,
        obs: str,
        step_num: int
    ) -> str:
        """创建执行状态字符串"""
        thought_trace = self._get_thought_trace()
        return f"""
## Step {step_num}
### Goal
{task.instruction}
### Current Thought Trace
{thought_trace}
### Long-term Memory
{self.memory.get_working_memory()}
### Previous Action
{prev_action}
### Observation
{obs}
### Environment State
{self.environment.get_observation() if self.environment else 'No environment'}
"""

    def _get_thought_trace(self) -> str:
        """获取思考追踪"""
        # 由子类ThinkingSpace实现
        return ""
```

#### 3.2.2 AgentExecutor - 执行策略

```python
# src/yoga_next/core/agent_executor.py
from .agent_core import AgentCore
from ..tasks import Task
from ..utils import extract_json_from_model_markdown_output
from typing import Dict, Any, List

class AgentExecutor:
    """Agent执行策略管理器"""

    def __init__(self, agent_core: AgentCore):
        self.agent = agent_core

    async def run_execution_loop(
        self,
        task: Task,
        task_idx: int,
        max_steps: int
    ) -> str:
        """执行主循环"""
        self.agent.memory.clear_task_related_memory()
        
        initial_state = self.agent.create_state(
            task=task,
            prev_action='(none)',
            obs='(none)',
            step_num=0
        )
        self.agent.memory.add(role='user', content=initial_state)

        for step_num in range(1, max_steps + 1):
            output = self.agent.model.chat_completion(
                self.agent.memory.get_messages()
            )
            self.agent.memory.add(role='assistant', content=output)

            parsed_json = extract_json_from_model_markdown_output(output)
            parsed_json['raw_model_output'] = output
            actions = parsed_json.get('action', [])
            
            if len(actions) == 0:
                continue

            for action in actions:
                result = await self.agent.action_space.execute(
                    action['action_name'],
                    action['action_params']
                )
                
                if action['action_name'] == 'done':
                    self.agent.final_result = result
                    return result.get("message", "Task completed")

            # 更新状态
            state = self.agent.create_state(
                task=task,
                prev_action=parsed_json['current_state']['next_goal'],
                obs='Action completed',
                step_num=step_num
            )
            self.agent.memory.add(role='user', content=state)

        return 'Reach maximal steps'
```

#### 3.2.3 AgentDisplay - 显示接口

```python
# src/yoga_next/core/agent_display.py
from typing import Dict, Any, Optional, List
from ..utils import YogDisplay

class AgentDisplay:
    """Agent显示渲染接口"""

    def __init__(self, display: Optional[YogDisplay] = None):
        self.display = display or YogDisplay()

    def render_step_header(self, step_num: int):
        """渲染步骤头部"""
        if self.display:
            self.display.console.print("\n")
            from rich.rule import Rule
            from rich.panel import Panel
            from rich.text import Text
            self.display.console.print(Panel(
                Text(f" STEP {step_num} ", style="bold white"),
                style="on blue"
            ))

    def render_agent_plan(
        self,
        step_num: int,
        parsed_json: Dict[str, Any],
        actions: List[Dict[str, Any]]
    ):
        """渲染Agent执行计划"""
        if not self.display:
            return

        from ..utils import (
            Panel, Text, Table, box,
            extract_json_from_model_markdown_output
        )
        
        # 渲染思考内容
        raw_output = parsed_json.get('raw_model_output', '')
        think_content = self._extract_think_tag(raw_output)
        
        if think_content:
            self.display.console.print(Panel(
                Text(think_content, style="italic cyan"),
                title="🧠 Internal Thought",
                border_style="cyan"
            ))

        # 渲染状态表格
        status_table = Table.grid(expand=True)
        status_table.add_column(ratio=1)
        status_table.add_column(ratio=1)

        memory = self.agent.memory.get_working_memory() if hasattr(self.agent, 'memory') else ""
        
        memory_panel = Panel(
            Text(str(memory), style="grey70"),
            title="💾 Working Memory",
            border_style="magenta",
            expand=True
        )

        curr_state = parsed_json.get('current_state', {})
        next_goal = curr_state.get('next_goal', '...')
        
        goal_panel = Panel(
            Text(str(next_goal), style="bold white"),
            title="🎯 Next Goal",
            border_style="blue",
            expand=True
        )

        status_table.add_row(memory_panel, goal_panel)
        self.display.console.print(status_table)

    def _extract_think_tag(self, content: str) -> str:
        """提取思考标签内容"""
        import re
        match = re.search(r'<think>(.*?)</think>', content, re.DOTALL)
        return match.group(1).strip() if match else ""
```

### 3.3 核心改进二：路径解析模块

创建统一的路径解析模块，消除重复代码：

```python
# src/yoga_next/core/path_resolver.py
from pathlib import Path
from typing import Optional
import os

class PathResolver:
    """统一路径解析器"""

    def __init__(self, workspace_root: str):
        self.workspace_root = Path(workspace_root).resolve()

    def resolve(self, path: str) -> Path:
        """解析相对路径为绝对路径"""
        p = Path(path)
        if p.is_absolute():
            abs_path = p.resolve()
        else:
            abs_path = (self.workspace_root / p).resolve()
        
        self._validate_access(abs_path)
        return abs_path

    def _validate_access(self, abs_path: Path):
        """验证路径是否在工作区内"""
        if not str(abs_path).startswith(str(self.workspace_root) + os.sep) \
           and abs_path != self.workspace_root:
            raise PermissionError(f"Access denied: {abs_path} is outside workspace")

    def get_workspace_root(self) -> Path:
        """获取工作区根目录"""
        return self.workspace_root


class PathResolverMixin:
    """路径解析混入类，可添加到任何需要路径解析的类中"""

    _path_resolver: Optional[PathResolver] = None

    def _init_path_resolver(self, workspace_root: str):
        """初始化路径解析器"""
        self._path_resolver = PathResolver(workspace_root)

    def _get_workspace_root(self) -> str:
        """获取工作区根目录字符串"""
        if hasattr(self, 'env') and hasattr(self.env, 'config'):
            config = self.env.config
            if isinstance(config, dict):
                return config.get("workspace_root", str(self._path_resolver.get_workspace_root()))
        
        if hasattr(self.env, 'workspace_root'):
            return self.env.workspace_root
        
        if self._path_resolver:
            return str(self._path_resolver.get_workspace_root())
        
        return os.getcwd()

    def _resolve_path(self, path: str) -> str:
        """解析路径"""
        if not self._path_resolver:
            workspace_root = self._get_workspace_root()
            self._init_path_resolver(workspace_root)
        
        return str(self._path_resolver.resolve(path))
```

### 3.4 核心改进三：动作注册表

实现标准化的动作注册机制：

```python
# src/yoga_next/core/action_registry.py
from typing import Dict, Any, Callable, Optional, Type
from ..actions.base import ActionSpace
from ..environments.base import Environment

class ActionMetadata:
    """动作元数据"""

    def __init__(
        self,
        name: str,
        description: str,
        parameters: Dict[str, Any],
        required: List[str],
        handler: Callable,
        category: str = "default"
    ):
        self.name = name
        self.description = description
        self.parameters = parameters
        self.required = required
        self.handler = handler
        self.category = category


class ActionRegistry:
    """动作注册表，管理所有可用动作"""

    _instance: Optional['ActionRegistry'] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._actions: Dict[str, ActionMetadata] = {}
            cls._instance._categories: Dict[str, list] = {}
        return cls._instance

    def register(
        self,
        action_space: Type[ActionSpace],
        category: str = "default"
    ):
        """从ActionSpace类注册动作"""
        for name, method in action_space.__dict__.items():
            if name.startswith("_handle_"):
                action_name = name[len("_handle_"):]
                metadata = self._create_metadata(action_name, method, category)
                self._actions[action_name] = metadata
                
                if category not in self._categories:
                    self._categories[category] = []
                self._categories[category].append(action_name)

    def _create_metadata(
        self,
        name: str,
        method: Callable,
        category: str
    ) -> ActionMetadata:
        """从方法创建元数据"""
        import inspect
        
        sig = inspect.signature(method)
        doc = inspect.getdoc(method) or "No description"
        
        # 解析参数
        properties = {}
        required = []
        
        for param_name, param in sig.parameters.items():
            if param_name == "self":
                continue
            
            # 类型推断
            ptype = str
            if param.annotation is not inspect.Parameter.empty:
                ptype = param.annotation
            
            properties[param_name] = {
                "type": self._python_type_to_json_type(ptype),
                "description": doc
            }
            
            if param.default is inspect.Parameter.empty:
                required.append(param_name)

        return ActionMetadata(
            name=name,
            description=doc,
            parameters={"properties": properties, "required": required},
            required=required,
            handler=method,
            category=category
        )

    def _python_type_to_json_type(self, python_type) -> str:
        """Python类型转JSON Schema类型"""
        type_str = str(python_type)
        if python_type is int or "int" in type_str.lower():
            return "integer"
        elif python_type is bool or "bool" in type_str.lower():
            return "boolean"
        elif python_type is list or "List" in type_str or "list" in type_str.lower():
            return "array"
        elif python_type is dict or "Dict" in type_str or "dict" in type_str.lower():
            return "object"
        return "string"

    def get_action(self, name: str) -> Optional[ActionMetadata]:
        """获取动作元数据"""
        return self._actions.get(name)

    def list_actions(self, category: Optional[str] = None) -> list:
        """列出动作"""
        if category:
            return self._categories.get(category, [])
        return list(self._actions.keys())

    def get_tool_schema(self) -> Dict[str, Any]:
        """生成OpenAI工具调用Schema"""
        return {
            name: {
                "description": meta.description,
                "parameters": {
                    "type": "object",
                    "properties": meta.parameters.get("properties", {}),
                    "required": meta.parameters.get("required", [])
                }
            }
            for name, meta in self._actions.items()
        }


class WhitelistMiddleware:
    """动作白名单中间件"""

    def __init__(self, registry: ActionRegistry, whitelist: set = None):
        self.registry = registry
        self.whitelist = whitelist or set()

    def check(self, action_name: str) -> bool:
        """检查动作是否在白名单中"""
        if self.whitelist and action_name not in self.whitelist:
            return False
        return action_name in self.registry._actions
```

### 3.5 核心改进四：环境工厂

实现环境工厂模式，解耦环境创建：

```python
# src/yoga_next/core/environment_factory.py
from typing import Dict, Any, Optional, Type
from ..environments.base import Environment
from ..environments.local_env import LocalCondaEnvironment
from ..environments.electron_app_env import ElectronAppEnv
from ..environments.remote_server_env import RemoteServerEnvironment
from ..environments.jupyter_notebook_env import JupyterNotebookEnvironment

class EnvironmentFactory:
    """环境工厂"""

    _environments: Dict[str, Type[Environment]] = {
        "local": LocalCondaEnvironment,
        "electron": ElectronAppEnv,
        "remote": RemoteServerEnvironment,
        "jupyter": JupyterNotebookEnvironment,
    }

    @classmethod
    def register(cls, name: str, env_class: Type[Environment]):
        """注册环境类型"""
        cls._environments[name.lower()] = env_class

    @classmethod
    def create(
        cls,
        env_type: str,
        config: Optional[Dict[str, Any]] = None
    ) -> Environment:
        """创建环境实例"""
        env_class = cls._environments.get(env_type.lower())
        if not env_class:
            raise ValueError(f"Unknown environment type: {env_type}")
        return env_class(config or {})

    @classmethod
    def list_types(cls) -> list:
        """列出可用的环境类型"""
        return list(cls._environments.keys())


class EnvironmentManager:
    """环境管理器"""

    def __init__(self):
        self._environments: Dict[str, Environment] = {}
        self._active_env: Optional[str] = None

    def register(self, name: str, env: Environment):
        """注册环境"""
        self._environments[name] = env

    def activate(self, name: str):
        """激活环境"""
        if name in self._environments:
            self._active_env = name

    async def setup_active(self):
        """设置活动环境"""
        if self._active_env and self._active_env in self._environments:
            await self._environments[self._active_env].setup()

    async def close_all(self):
        """关闭所有环境"""
        for env in self._environments.values():
            await env.close()

    @property
    def active(self) -> Optional[Environment]:
        """获取当前活动环境"""
        if self._active_env:
            return self._environments.get(self._active_env)
        return None
```

### 3.6 核心改进五：配置系统增强

增强配置系统，支持环境变量和验证：

```python
# src/yoga_next/core/config.py
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
import os
import yaml
from pydantic import BaseModel, Field, validator


class AgentConfig(BaseModel):
    """增强的Agent配置"""

    api_base_url: str = Field(..., description="API基础URL")
    model_name: str = Field(..., description="模型名称")
    api_key: Optional[str] = Field(None, description="API密钥")
    
    # 新增字段
    max_steps: int = Field(100, description="最大执行步数")
    timeout_seconds: int = Field(300, description="超时时间")
    enable_thinking: bool = Field(True, description="启用思考模式")
    display_enabled: bool = Field(True, description="启用显示")
    
    # 环境配置
    workspace_root: Optional[str] = Field(None, description="工作区根目录")
    environment_type: str = Field("local", description="环境类型")
    
    # 动作空间配置
    enabled_action_spaces: List[str] = Field(
        default_factory=lambda: ["control", "thinking", "edit"]
    )

    @validator('api_base_url', 'model_name')
    def validate_required(cls, v):
        if not v or not v.strip():
            raise ValueError('This field is required')
        return v.strip()

    @classmethod
    def from_yaml(cls, path: str) -> 'AgentConfig':
        """从YAML文件加载配置"""
        with open(path, 'r', encoding='utf-8') as f:
            config_data = yaml.safe_load(f)
        return cls(**config_data)

    @classmethod
    def from_env(cls) -> 'AgentConfig':
        """从环境变量加载配置"""
        config_data = {
            'api_base_url': os.environ.get('YOGA_API_BASE_URL', ''),
            'model_name': os.environ.get('YOGA_MODEL_NAME', 'gpt-4'),
            'api_key': os.environ.get('YOGA_API_KEY', ''),
            'max_steps': int(os.environ.get('YOGA_MAX_STEPS', '100')),
            'timeout_seconds': int(os.environ.get('YOGA_TIMEOUT', '300')),
            'workspace_root': os.environ.get('YOGA_WORKSPACE_ROOT', ''),
            'environment_type': os.environ.get('YOGA_ENV_TYPE', 'local'),
        }
        return cls(**config_data)

    @classmethod
    def load(cls, config_path: Optional[str] = None) -> 'AgentConfig':
        """智能加载配置，优先使用配置文件"""
        if config_path and os.path.exists(config_path):
            return cls.from_yaml(config_path)
        return cls.from_env()


class ConfigManager:
    """配置管理器，支持配置分层"""

    def __init__(self):
        self._configs: Dict[str, AgentConfig] = {}
        self._active_config: Optional[str] = None

    def register(self, name: str, config: AgentConfig):
        """注册配置"""
        self._configs[name] = config

    def activate(self, name: str):
        """激活配置"""
        if name in self._configs:
            self._active_config = name

    @property
    def active(self) -> AgentConfig:
        """获取当前活动配置"""
        if self._active_config:
            return self._configs.get(self._active_config)
        raise RuntimeError("No active configuration")

    def merge(self, base: str, overlay: str) -> AgentConfig:
        """合并配置"""
        base_config = self._configs.get(base, AgentConfig(
            api_base_url="", model_name=""
        ))
        overlay_config = self._configs.get(overlay, AgentConfig(
            api_base_url="", model_name=""
        ))
        
        # 简单合并策略
        return AgentConfig(
            api_base_url=overlay_config.api_base_url or base_config.api_base_url,
            model_name=overlay_config.model_name or base_config.model_name,
            api_key=overlay_config.api_key or base_config.api_key,
            max_steps=overlay_config.max_steps or base_config.max_steps,
            timeout_seconds=overlay_config.timeout_seconds or base_config.timeout_seconds,
            workspace_root=overlay_config.workspace_root or base_config.workspace_root,
            environment_type=overlay_config.environment_type or base_config.environment_type,
        )
```

### 3.7 核心改进六：事件总线

引入事件系统，实现松耦合的组件通信：

```python
# src/yoga_next/core/event_bus.py
from typing import Callable, Dict, Any, List, Optional
from dataclasses import dataclass
from enum import Enum
import asyncio


class EventType(Enum):
    """事件类型枚举"""
    TASK_STARTED = "task_started"
    TASK_COMPLETED = "task_completed"
    TASK_ERROR = "task_error"
    ACTION_EXECUTED = "action_executed"
    ACTION_COMPLETED = "action_completed"
    ACTION_ERROR = "action_error"
    THOUGHT_GENERATED = "thought_generated"
    STATE_CHANGED = "state_changed"
    MEMORY_UPDATED = "memory_updated"


@dataclass
class Event:
    """事件数据类"""
    type: EventType
    payload: Dict[str, Any]
    timestamp: float
    source: Optional[str] = None


class EventHandler:
    """事件处理器"""

    def __init__(self, callback: Callable, event_types: List[EventType] = None):
        self.callback = callback
        self.event_types = event_types or []

    async def handle(self, event: Event):
        """处理事件"""
        if not self.event_types or event.type in self.event_types:
            await self.callback(event)


class EventBus:
    """事件总线"""

    def __init__(self):
        self._handlers: List[EventHandler] = []
        self._queue: asyncio.Queue = asyncio.Queue()

    def subscribe(
        self,
        callback: Callable,
        event_types: List[EventType] = None
    ) -> EventHandler:
        """订阅事件"""
        handler = EventHandler(callback, event_types)
        self._handlers.append(handler)
        return handler

    def unsubscribe(self, handler: EventHandler):
        """取消订阅"""
        if handler in self._handlers:
            self._handlers.remove(handler)

    async def publish(self, event: Event):
        """发布事件"""
        for handler in self._handlers:
            await handler.handle(event)

    async def publish_async(self, event_type: EventType, payload: Dict[str, Any], source: str = None):
        """异步发布事件"""
        event = Event(
            type=event_type,
            payload=payload,
            timestamp=0,  # 将在消费时设置
            source=source
        )
        await self._queue.put(event)

    async def start(self):
        """启动事件处理循环"""
        while True:
            event = await self._queue.get()
            event.timestamp = __import__('time').time()
            await self.publish(event)

    def stop(self):
        """停止事件处理"""
        # 实际实现需要更复杂的停止逻辑
        pass


class EventRecorder:
    """事件记录器，用于调试和分析"""

    def __init__(self, event_bus: EventBus):
        self.events: List[Event] = []
        self.event_bus = event_bus
        self._subscription = None

    def start(self):
        """开始记录事件"""
        self.events.clear()
        self._subscription = self.event_bus.subscribe(self._record)

    def stop(self):
        """停止记录事件"""
        if self._subscription:
            self.event_bus.unsubscribe(self._subscription)

    async def _record(self, event: Event):
        """记录事件"""
        self.events.append(event)

    def get_events(self, event_type: EventType = None) -> List[Event]:
        """获取事件"""
        if event_type:
            return [e for e in self.events if e.type == event_type]
        return self.events

    def to_json(self) -> str:
        """导出为JSON"""
        import json
        return json.dumps([
            {"type": e.type.value, "payload": e.payload, "timestamp": e.timestamp}
            for e in self.events
        ], indent=2)
```


## 4. 实施路线图

### 阶段1：基础设施（第1-2周）

1. 创建`src/yoga_next/core/`目录结构
2. 实现`PathResolver`和`PathResolverMixin`
3. 实现`ActionRegistry`和`WhitelistMiddleware`
4. 实现`EnvironmentFactory`和`EnvironmentManager`
5. 编写单元测试

### 阶段2：配置与事件（第3-4周）

1. 重构`AgentConfig`为`Config`系统
2. 实现`EventBus`和`EventRecorder`
3. 更新`agent_service.py`使用新配置
4. 编写集成测试

### 阶段3：Agent重构（第5-6周）

1. 实现`AgentCore`、`AgentExecutor`、`AgentDisplay`
2. 创建适配器保持向后兼容
3. 更新`agent.py`使用新架构
4. 编写端到端测试

## 8. 附录

### 8.1 新目录结构

```
src/yoga_next/
├── core/                    # 新增核心模块
│   ├── __init__.py
│   ├── agent_core.py       # Agent核心
│   ├── agent_executor.py   # 执行策略
│   ├── agent_display.py    # 显示接口
│   ├── path_resolver.py    # 路径解析
│   ├── action_registry.py  # 动作注册
│   ├── environment_factory.py  # 环境工厂
│   ├── config.py           # 配置系统
│   ├── event_bus.py        # 事件总线
├── adapters/                # 适配器
│   └── agent_adapter.py
├── agent.py                # 保留，兼容入口
├── agent_config.py         # 保留，别名到config
├── ...
```

### 8.2 迁移检查清单

- [ ] 创建`core/`目录
- [ ] 实现`PathResolver`
- [ ] 实现`ActionRegistry`
- [ ] 实现`EnvironmentFactory`
- [ ] 重构`AgentConfig`
- [ ] 实现`EventBus`
- [ ] 实现`AgentCore`
- [ ] 实现`AgentExecutor`
- [ ] 实现`AgentDisplay`
- [ ] 创建适配器
- [ ] 更新`agent.py`
- [ ] 编写单元测试
- [ ] 编写集成测试
- [ ] 编写端到端测试
- [ ] 更新文档

## 9. 总结

本重构方案通过以下方式提升架构质量：

1. **模块化**：拆分大型类，引入专职组件
2. **可扩展**：插件系统、事件总线、工厂模式
3. **可测试**：依赖注入、接口抽象
4. **可维护**：关注点分离、单一职责
5. **向后兼容**：适配器模式、渐进迁移

实施本方案将显著提升框架的可维护性、可扩展性和可测试性，同时保持完全的功能兼容性。
