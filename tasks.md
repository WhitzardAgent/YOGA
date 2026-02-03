# 重构任务清单

本文档提供详细的重构任务清单，每个任务都包含足够的细节，可以指导程序员准确完成重构工作。每个任务的预期工作量约为1人天。

## 任务总览

| 阶段 | 任务数 | 预计时间 |
|------|--------|----------|
| 阶段1：基础设施 | 5个任务 | 5人天 |
| 阶段2：配置与事件 | 4个任务 | 4人天 |
| 阶段3：Agent重构 | 4个任务 | 4人天 |
| 阶段4：插件系统 | 3个任务 | 3人天 |
| **总计** | **16个任务** | **16人天** |

---

## 阶段1：基础设施

### 任务1.1：创建core目录结构和初始化文件

**原始文件**：无（新建设立）

**新创建文件**：
- `src/yoga_next/core/__init__.py`

**具体步骤**：

1. 在`src/yoga_next/`目录下创建`core`文件夹
2. 在`core`文件夹中创建`__init__.py`文件，内容如下：

```python
"""
核心模块 - 提供Agent框架的基础设施组件

包含：
- path_resolver: 统一路径解析
- action_registry: 动作注册表
- environment_factory: 环境工厂
- config: 配置系统
- event_bus: 事件总线
- agent_core: Agent核心
- agent_executor: 执行策略
- agent_display: 显示接口
- plugin_system: 插件系统
"""

from .path_resolver import PathResolver, PathResolverMixin
from .action_registry import ActionRegistry, WhitelistMiddleware, ActionMetadata
from .environment_factory import EnvironmentFactory, EnvironmentManager
from .config import AgentConfig, ConfigManager
from .event_bus import EventBus, EventRecorder, EventType, Event
from .agent_core import AgentCore
from .agent_executor import AgentExecutor
from .agent_display import AgentDisplay
from .plugin_system import PluginManager, PluginInterface

__all__ = [
    'PathResolver',
    'PathResolverMixin',
    'ActionRegistry',
    'WhitelistMiddleware',
    'ActionMetadata',
    'EnvironmentFactory',
    'EnvironmentManager',
    'AgentConfig',
    'ConfigManager',
    'EventBus',
    'EventRecorder',
    'EventType',
    'Event',
    'AgentCore',
    'AgentExecutor',
    'AgentDisplay',
    'PluginManager',
    'PluginInterface',
]
```

3. 更新`src/yoga_next/__init__.py`，添加对core模块的导入：

```python
# 在现有的导入语句后添加
try:
    from .core import *
except ImportError:
    pass  # 允许在core模块不存在时回退
```

**验收标准**：

1. `src/yoga_next/core/`目录存在
2. `src/yoga_next/core/__init__.py`文件存在且内容正确
3. 运行`python -c "from yoga_next.core import *"`不报错
4. `src/yoga_next/__init__.py`导入不报错

**预期工作量**：0.5人天

---

### 任务1.2：实现PathResolver和PathResolverMixin

**原始文件**：无（新建设立）

**新创建文件**：
- `src/yoga_next/core/path_resolver.py`

**需要参考的现有文件**：
- `src/yoga_next/actions/glim_app_action_space.py`（第45-67行）
- `src/yoga_next/actions/edit_action_space.py`（第30-58行）
- `src/yoga_next/actions/research_action_space.py`（第44-65行）
- `src/yoga_next/actions/latex_action_space.py`（第49-70行）
- `src/yoga_next/environments/local_env.py`（第161-173行）

**具体步骤**：

1. 创建`src/yoga_next/core/path_resolver.py`文件
2. 实现`PathResolver`类：
   - 接收`workspace_root`参数，初始化时调用`Path().resolve()`
   - 实现`resolve(path)`方法，处理相对/绝对路径
   - 实现`_validate_access(abs_path)`方法，验证路径是否在工作区内
   - 实现`get_workspace_root()`方法，返回工作区根目录Path对象

3. 实现`PathResolverMixin`类：
   - 添加`_path_resolver: Optional[PathResolver]`类属性
   - 实现`_init_path_resolver(workspace_root)`方法
   - 实现`_get_workspace_root()`方法，兼容env.config、env.workspace_root等属性
   - 实现`_resolve_path(path)`方法，调用PathResolver.resolve()

4. 编写单元测试，保存到`src/yoga_next/tests/unit/test_path_resolver.py`

**代码模板**：

```python
# src/yoga_next/core/path_resolver.py

from pathlib import Path
from typing import Optional
import os


class PathResolver:
    """统一路径解析器，负责处理路径安全和解析"""

    def __init__(self, workspace_root: str):
        """
        初始化路径解析器
        
        Args:
            workspace_root: 工作区根目录路径
        """
        self.workspace_root = Path(workspace_root).resolve()

    def resolve(self, path: str) -> Path:
        """
        解析相对路径为绝对路径
        
        Args:
            path: 要解析的路径（相对或绝对）
            
        Returns:
            解析后的绝对Path对象
            
        Raises:
            PermissionError: 如果路径超出工作区范围
        """
        p = Path(path)
        if p.is_absolute():
            abs_path = p.resolve()
        else:
            abs_path = (self.workspace_root / p).resolve()
        
        self._validate_access(abs_path)
        return abs_path

    def _validate_access(self, abs_path: Path):
        """
        验证路径是否在工作区内
        
        Args:
            abs_path: 要验证的绝对路径
            
        Raises:
            PermissionError: 如果路径超出工作区范围
        """
        if not str(abs_path).startswith(str(self.workspace_root) + os.sep) \
           and abs_path != self.workspace_root:
            raise PermissionError(
                f"Access denied: {abs_path} is outside workspace {self.workspace_root}"
            )

    def get_workspace_root(self) -> Path:
        """获取工作区根目录"""
        return self.workspace_root

    def __repr__(self):
        return f"PathResolver(workspace_root={self.workspace_root})"


class PathResolverMixin:
    """
    路径解析混入类，可添加到任何需要路径解析的类中
    
    使用方法：
        class MyActionSpace(PathResolverMixin, ActionSpace):
            def __init__(self, action_space_name: str, env=None):
                super().__init__(action_space_name, env)
                self._init_path_resolver(self._get_workspace_root())
    """

    _path_resolver: Optional[PathResolver] = None

    def _init_path_resolver(self, workspace_root: str):
        """
        初始化路径解析器
        
        Args:
            workspace_root: 工作区根目录
        """
        self._path_resolver = PathResolver(workspace_root)

    def _get_workspace_root(self) -> str:
        """
        获取工作区根目录字符串
        
        优先级：
        1. env.config.get("workspace_root")
        2. env.workspace_root
        3. _path_resolver
        4. os.getcwd()
        
        Returns:
            工作区根目录字符串
        """
        # 检查env.config
        if hasattr(self, 'env') and hasattr(self.env, 'config'):
            config = self.env.config
            if isinstance(config, dict):
                ws = config.get("workspace_root")
                if ws:
                    return ws
        
        # 检查env.workspace_root
        if hasattr(self.env, 'workspace_root'):
            return self.env.workspace_root
        
        # 检查_path_resolver
        if self._path_resolver:
            return str(self._path_resolver.get_workspace_root())
        
        # 回退到当前目录
        return os.getcwd()

    def _resolve_path(self, path: str) -> str:
        """
        解析路径字符串
        
        Args:
            path: 要解析的路径
            
        Returns:
            解析后的绝对路径字符串
            
        Raises:
            PermissionError: 如果路径超出工作区范围
        """
        if not self._path_resolver:
            workspace_root = self._get_workspace_root()
            self._init_path_resolver(workspace_root)
        
        return str(self._path_resolver.resolve(path))
```

**验收标准**：

1. `src/yoga_next/core/path_resolver.py`文件存在
2. `PathResolver`类可以正确解析相对路径和绝对路径
3. `PathResolverMixin`类提供`_get_workspace_root()`和`_resolve_path()`方法
4. 路径验证功能正确，拒绝访问工作区外的路径
5. 单元测试覆盖以下场景：
   - 相对路径解析
   - 绝对路径验证
   - 边界情况（工作区根目录本身）
   - 越权访问尝试

**预期工作量**：1人天

---

### 任务1.3：实现ActionRegistry和WhitelistMiddleware

**原始文件**：
- `src/yoga_next/actions/base.py`

**新创建文件**：
- `src/yoga_next/core/action_registry.py`

**具体步骤**：

1. 创建`src/yoga_next/core/action_registry.py`文件
2. 实现`ActionMetadata`类，包含：
   - name: 动作名称
   - description: 动作描述
   - parameters: 参数Schema
   - required: 必需参数列表
   - handler: 处理函数
   - category: 分类

3. 实现`ActionRegistry`类（单例模式）：
   - 实现`register(action_space, category)`方法
   - 实现`_create_metadata(name, method, category)`方法
   - 实现`_python_type_to_json_type(python_type)`方法
   - 实现`get_action(name)`方法
   - 实现`list_actions(category)`方法
   - 实现`get_tool_schema()`方法

4. 实现`WhitelistMiddleware`类：
   - 接收`ActionRegistry`和可选的`whitelist`集合
   - 实现`check(action_name)`方法

5. 编写单元测试，保存到`src/yoga_next/tests/unit/test_action_registry.py`

**代码模板**：

```python
# src/yoga_next/core/action_registry.py

from typing import Dict, Any, Callable, Optional, Type, List
from ..actions.base import ActionSpace


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

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters,
            "required": self.required,
            "category": self.category
        }

    def __repr__(self):
        return f"ActionMetadata(name={self.name!r}, category={self.category!r})"


class ActionRegistry:
    """
    动作注册表，管理所有可用动作
    
    单例模式，确保全局只有一个注册表
    """

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
        """
        从ActionSpace类注册所有动作
        
        Args:
            action_space: ActionSpace子类
            category: 动作分类
        """
        for name, method in action_space.__dict__.items():
            if name.startswith("_handle_"):
                action_name = name[len("_handle_"):]
                metadata = self._create_metadata(action_name, method, category)
                self._actions[action_name] = metadata
                
                if category not in self._categories:
                    self._categories[category] = []
                if action_name not in self._categories[category]:
                    self._categories[category].append(action_name)

    def _create_metadata(
        self,
        name: str,
        method: Callable,
        category: str
    ) -> ActionMetadata:
        """从处理方法创建元数据"""
        import inspect
        
        sig = inspect.signature(method)
        doc = inspect.getdoc(method) or "No description provided"
        
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
            parameters={
                "type": "object",
                "properties "required": required": properties,
               
            },
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
        """
        列出动作
        
        Args:
            category: 可选的分类过滤
            
        Returns:
            动作名称列表
        """
        if category:
            return self._categories.get(category, [])
        return list(self._actions.keys())

    def get_tool_schema(self) -> Dict[str, Any]:
        """
        生成OpenAI工具调用Schema
        
        Returns:
            OpenAI格式的工具Schema
        """
        return {
            name: {
                "description": meta.description,
                "parameters": meta.parameters
            }
            for name, meta in self._actions.items()
        }

    def clear(self):
        """清空注册表"""
        self._actions.clear()
        self._categories.clear()


class WhitelistMiddleware:
    """
    动作白名单中间件
    
    用于在执行前检查动作是否在白名单中
    """

    def __init__(self, registry: ActionRegistry, whitelist: set = None):
        """
        初始化白名单中间件
        
        Args:
            registry: 动作注册表
            whitelist: 允许的动作名称集合，为空表示不限制
        """
        self.registry = registry
        self.whitelist = whitelist or set()

    def check(self, action_name: str) -> bool:
        """
        检查动作是否允许执行
        
        Args:
            action_name: 动作名称
            
        Returns:
            True表示允许，False表示不允许
        """
        # 如果设置了白名单，检查是否在白名单中
        if self.whitelist and action_name not in self.whitelist:
            return False
        
        # 检查动作是否已注册
        return action_name in self.registry._actions

    def get_allowed_actions(self) -> list:
        """获取允许的动作列表"""
        if self.whitelist:
            return [a for a in self.whitelist if a in self.registry._actions]
        return self.registry.list_actions()
```

**验收标准**：

1. `src/yoga_next/core/action_registry.py`文件存在
2. `ActionRegistry`是单例模式
3. `register()`方法能正确从ActionSpace注册动作
4. `get_tool_schema()`返回正确的OpenAI格式
5. `WhitelistMiddleware`正确实现白名单检查
6. 单元测试覆盖以下场景：
   - 单例模式验证
   - 从ActionSpace注册动作
   - 白名单检查
   - Schema生成

**预期工作量**：1人天

---

### 任务1.4：实现EnvironmentFactory和EnvironmentManager

**原始文件**：
- `src/yoga_next/environments/__init__.py`
- `src/yoga_next/environments/base.py`
- `src/yoga_next/environments/local_env.py`
- `src/yoga_next/environments/electron_app_env.py`
- `src/yoga_next/environments/remote_server_env.py`
- `src/yoga_next/environments/jupyter_notebook_env.py`

**新创建文件**：
- `src/yoga_next/core/environment_factory.py`

**具体步骤**：

1. 创建`src/yoga_next/core/environment_factory.py`文件
2. 实现`EnvironmentFactory`类：
   - 使用类变量`_environments`存储环境类型映射
   - 实现`register(name, env_class)`类方法
   - 实现`create(env_type, config)`类方法
   - 实现`list_types()`类方法

3. 实现`EnvironmentManager`类：
   - 实现`__init__()`初始化_environment字典和_active_env
   - 实现`register(name, env)`注册环境
   - 实现`activate(name)`激活环境
   - 实现`async setup_active()`设置活动环境
   - 实现`async close_all()`关闭所有环境
   - 实现`active`属性

4. 修改`src/yoga_next/environments/__init__.py`，确保所有环境类可被导入

5. 编写单元测试，保存到`src/yoga_next/tests/unit/test_environment_factory.py`

**代码模板**：

```python
# src/yoga_next/core/environment_factory.py

from typing import Dict, Any, Optional, Type
from ..environments.base import Environment
from ..environments.local_env import LocalCondaEnvironment
from ..environments.electron_app_env import ElectronAppEnv
from ..environments.remote_server_env import RemoteServerEnvironment
from ..environments.jupyter_notebook_env import JupyterNotebookEnvironment


class EnvironmentFactory:
    """
    环境工厂，根据类型创建环境实例
    
    使用方法：
        env = EnvironmentFactory.create("local", {"workspace_root": "/path/to/workspace"})
        env = EnvironmentFactory.create("electron", config)
    """

    _environments: Dict[str, Type[Environment]] = {
        "local": LocalCondaEnvironment,
        "electron": ElectronAppEnv,
        "remote": RemoteServerEnvironment,
        "jupyter": JupyterNotebookEnvironment,
    }

    @classmethod
    def register(cls, name: str, env_class: Type[Environment]):
        """
        注册环境类型
        
        Args:
            name: 环境类型名称（小写）
            env_class: Environment子类
        """
        cls._environments[name.lower()] = env_class

    @classmethod
    def create(
        cls,
        env_type: str,
        config: Optional[Dict[str, Any]] = None
    ) -> Environment:
        """
        创建环境实例
        
        Args:
            env_type: 环境类型名称
            config: 可选的配置字典
            
        Returns:
            环境实例
            
        Raises:
            ValueError: 如果环境类型未知
        """
        env_class = cls._environments.get(env_type.lower())
        if not env_class:
            raise ValueError(
                f"Unknown environment type: {env_type}. "
                f"Available types: {cls.list_types()}"
            )
        return env_class(config or {})

    @classmethod
    def list_types(cls) -> list:
        """
        列出可用的环境类型
        
        Returns:
            环境类型名称列表
        """
        return list(cls._environments.keys())

    @classmethod
    def get_class(cls, env_type: str) -> Optional[Type[Environment]]:
        """
        获取环境类型类
        
        Args:
            env_type: 环境类型名称
            
        Returns:
            Environment子类或None
        """
        return cls._environments.get(env_type.lower())


class EnvironmentManager:
    """
    环境管理器，管理多个环境实例
    
    使用方法：
        manager = EnvironmentManager()
        manager.register("local", local_env)
        manager.activate("local")
        await manager.setup_active()
    """

    def __init__(self):
        self._environments: Dict[str, Environment] = {}
        self._active_env: Optional[str] = None

    def register(self, name: str, env: Environment):
        """
        注册环境实例
        
        Args:
            name: 环境名称
            env: 环境实例
        """
        self._environments[name] = env

    def activate(self, name: str):
        """
        激活环境
        
        Args:
            name: 要激活的环境名称
        """
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
        """
        获取当前活动环境
        
        Returns:
            活动环境实例或None
        """
        if self._active_env:
            return self._environments.get(self._active_env)
        return None

    def get(self, name: str) -> Optional[Environment]:
        """
        获取指定名称的环境
        
        Args:
            name: 环境名称
            
        Returns:
            环境实例或None
        """
        return self._environments.get(name)

    def list_registered(self) -> list:
        """
        列出已注册的环境名称
        
        Returns:
            环境名称列表
        """
        return list(self._environments.keys())
```

**验收标准**：

1. `src/yoga_next/core/environment_factory.py`文件存在
2. `EnvironmentFactory.create()`能创建所有已知环境类型
3. `EnvironmentFactory.register()`能注册新环境类型
4. `EnvironmentManager`正确管理多个环境
5. `active`属性正确返回当前活动环境
6. 单元测试覆盖以下场景：
   - 创建各种环境类型
   - 注册新环境类型
   - 环境切换和激活
   - 异步setup和close

**预期工作量**：1人天

---

### 任务1.5：编写基础设施单元测试

**需要测试的文件**：
- `src/yoga_next/core/path_resolver.py`
- `src/yoga_next/core/action_registry.py`
- `src/yoga_next/core/environment_factory.py`

**新创建文件**：
- `src/yoga_next/tests/unit/__init__.py`
- `src/yoga_next/tests/unit/test_path_resolver.py`
- `src/yoga_next/tests/unit/test_action_registry.py`
- `src/yoga_next/tests/unit/test_environment_factory.py`

**具体步骤**：

1. 创建测试目录结构
2. 编写`test_path_resolver.py`，覆盖：
   - 相对路径解析
   - 绝对路径处理
   - 边界情况（工作区根目录）
   - 越权访问拒绝
   - PathResolverMixin方法

3. 编写`test_action_registry.py`，覆盖：
   - 单例模式
   - 从ActionSpace注册
   - 白名单检查
   - Schema生成

4. 编写`test_environment_factory.py`，覆盖：
   - 创建各类型环境
   - 注册新环境
   - EnvironmentManager操作

5. 运行测试确保所有测试通过

**测试代码模板**：

```python
# src/yoga_next/tests/unit/test_path_resolver.py

import pytest
import os
import tempfile
from pathlib import Path
from yoga_next.core.path_resolver import PathResolver, PathResolverMixin


class TestPathResolver:
    """PathResolver测试类"""
    
    @pytest.fixture
    def workspace(self):
        """创建临时工作区"""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir
    
    def test_init(self, workspace):
        """测试初始化"""
        resolver = PathResolver(workspace)
        assert resolver.workspace_root == Path(workspace).resolve()
    
    def test_resolve_relative_path(self, workspace):
        """测试解析相对路径"""
        resolver = PathResolver(workspace)
        
        # 创建测试文件
        test_file = Path(workspace) / "test.txt"
        test_file.write_text("test")
        
        result = resolver.resolve("test.txt")
        assert result == test_file.resolve()
    
    def test_resolve_absolute_path(self, workspace):
        """测试解析绝对路径"""
        resolver = PathResolver(workspace)
        test_file = Path(workspace) / "test.txt"
        test_file.write_text("test")
        
        result = resolver.resolve(str(test_file))
        assert result == test_file.resolve()
    
    def test_validate_access_root(self, workspace):
        """测试访问工作区根目录"""
        resolver = PathResolver(workspace)
        result = resolver.resolve(workspace)
        assert result == Path(workspace).resolve()
    
    def test_validate_access_outside(self, workspace):
        """测试拒绝访问工作区外"""
        resolver = PathResolver(workspace)
        with pytest.raises(PermissionError):
            resolver.resolve("/etc/passwd")
    
    def test_validate_access_sibling(self, workspace):
        """测试拒绝访问兄弟目录"""
        resolver = PathResolver(workspace)
        with tempfile.TemporaryDirectory() as sibling:
            with pytest.raises(PermissionError):
                resolver.resolve(sibling)


class TestPathResolverMixin:
    """PathResolverMixin测试类"""
    
    class MockEnv:
        def __init__(self, workspace_root):
            self.workspace_root = workspace_root
            self.config = {}
    
    @pytest.fixture
    def mixin_instance(self):
        """创建混入类实例"""
        class TestMixin(PathResolverMixin):
            def __init__(self, workspace_root):
                self.env = self.MockEnv(workspace_root)
                self._init_path_resolver(workspace_root)
        
        with tempfile.TemporaryDirectory() as tmpdir:
            yield TestMixin(tmpdir)
    
    def test_get_workspace_root_from_env(self, mixin_instance):
        """测试从env获取工作区"""
        assert mixin_instance._get_workspace_root() == mixin_instance.env.workspace_root
    
    def test_resolve_path(self, mixin_instance):
        """测试路径解析"""
        test_file = Path(mixin_instance.env.workspace_root) / "test.txt"
        test_file.write_text("test")
        
        result = mixin_instance._resolve_path("test.txt")
        assert result == str(test_file.resolve())
```

**验收标准**：

1. 测试文件存在于正确目录
2. 使用pytest框架
3. 每个模块至少80%的测试覆盖率
4. 所有测试通过
5. 包含边界测试和异常测试

**预期工作量**：1人天

---

## 阶段2：配置与事件

### 任务2.1：重构AgentConfig为增强配置系统

**原始文件**：
- `src/yoga_next/agent_config.py`

**新创建文件**：
- `src/yoga_next/core/config.py`

**具体步骤**：

1. 创建`src/yoga_next/core/config.py`文件
2. 实现`AgentConfig`类（使用pydantic）：
   - 保留原有字段：api_base_url, model_name, api_key
   - 添加新字段：max_steps, timeout_seconds, enable_thinking, display_enabled
   - 添加环境配置：workspace_root, environment_type
   - 添加动作空间配置：enabled_action_spaces
   - 实现`from_yaml()`类方法
   - 实现`from_env()`类方法
   - 实现`load()`类方法（智能加载）
   - 添加验证器

3. 实现`ConfigManager`类：
   - 实现`__init__()`初始化_configs字典
   - 实现`register(name, config)`注册配置
   - 实现`activate(name)`激活配置
   - 实现`active`属性
   - 实现`merge(base, overlay)`合并配置

4. 保留`src/yoga_next/agent_config.py`文件，添加对core.config的引用：

```python
# src/yoga_next/agent_config.py

# 保留向后兼容
from .core.config import AgentConfig as NewAgentConfig

class AgentConfig(NewAgentConfig):
    """保留旧类名作为别名"""
    pass
```

5. 创建测试配置文件`configs/config_local.yaml`的示例（如果不存在）

6. 编写单元测试，保存到`src/yoga_next/tests/unit/test_config.py`

**代码模板**：

```python
# src/yoga_next/core/config.py

from typing import Dict, Any, Optional, List
import os
import yaml
from pydantic import BaseModel, Field, validator


class AgentConfig(BaseModel):
    """
    增强的Agent配置类
    
    使用pydantic进行数据验证，支持YAML和环境变量加载
    """

    api_base_url: str = Field(..., description="API基础URL")
    model_name: str = Field(..., description="模型名称")
    api_key: Optional[str] = Field(None, description="API密钥")
    
    # 新增字段
    max_steps: int = Field(100, description="最大执行步数")
    timeout_seconds: int = Field(300, description="超时时间（秒）")
    enable_thinking: bool = Field(True, description="是否启用思考模式")
    display_enabled: bool = Field(True, description="是否启用显示")
    
    # 环境配置
    workspace_root: Optional[str] = Field(None, description="工作区根目录")
    environment_type: str = Field("local", description="环境类型")
    
    # 动作空间配置
    enabled_action_spaces: List[str] = Field(
        default_factory=lambda: ["control", "thinking", "edit"],
        description="启用的动作空间列表"
    )

    @validator('api_base_url', 'model_name')
    def validate_required(cls, v):
        """验证必需字段"""
        if not v or not v.strip():
            raise ValueError('This field is required')
        return v.strip()

    @validator('max_steps', 'timeout_seconds')
    def validate_positive(cls, v):
        """验证正数字段"""
        if v <= 0:
            raise ValueError('Must be positive')
        return v

    @classmethod
    def from_yaml(cls, path: str) -> 'AgentConfig':
        """
        从YAML文件加载配置
        
        Args:
            path: YAML文件路径
            
        Returns:
            AgentConfig实例
            
        Raises:
            FileNotFoundError: 如果文件不存在
            ValueError: 如果必需字段缺失
        """
        with open(path, 'r', encoding='utf-8') as f:
            config_data = yaml.safe_load(f)
        
        if not config_data:
            raise ValueError(f"Empty config file: {path}")
        
        return cls(**config_data)

    @classmethod
    def from_env(cls) -> 'AgentConfig':
        """
        从环境变量加载配置
        
        环境变量：
        - YOGA_API_BASE_URL: API基础URL
        - YOGA_MODEL_NAME: 模型名称
        - YOGA_API_KEY: API密钥
        - YOGA_MAX_STEPS: 最大步数
        - YOGA_TIMEOUT: 超时时间
        - YOGA_WORKSPACE_ROOT: 工作区根目录
        - YOGA_ENV_TYPE: 环境类型
        
        Returns:
            AgentConfig实例
        """
        config_data = {
            'api_base_url': os.environ.get('YOGA_API_BASE_URL', ''),
            'model_name': os.environ.get('YOGA_MODEL_NAME', 'gpt-4'),
            'api_key': os.environ.get('YOGA_API_KEY'),
            'max_steps': int(os.environ.get('YOGA_MAX_STEPS', '100')),
            'timeout_seconds': int(os.environ.get('YOGA_TIMEOUT', '300')),
            'enable_thinking': os.environ.get('YOGA_ENABLE_THINKING', 'True').lower() == 'true',
            'display_enabled': os.environ.get('YOGA_DISPLAY_ENABLED', 'True').lower() == 'true',
            'workspace_root': os.environ.get('YOGA_WORKSPACE_ROOT'),
            'environment_type': os.environ.get('YOGA_ENV_TYPE', 'local'),
        }
        
        # 过滤空值
        config_data = {k: v for k, v in config_data.items() if v is not None and v != ''}
        
        return cls(**config_data)

    @classmethod
    def load(cls, config_path: Optional[str] = None) -> 'AgentConfig':
        """
        智能加载配置
        
        优先使用配置文件，如果文件不存在则使用环境变量
        
        Args:
            config_path: 可选的配置文件路径
            
        Returns:
            AgentConfig实例
        """
        if config_path and os.path.exists(config_path):
            return cls.from_yaml(config_path)
        return cls.from_env()

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return self.dict()

    def to_yaml(self, path: str):
        """保存到YAML文件"""
        with open(path, 'w', encoding='utf-8') as f:
            yaml.safe_dump(self.to_dict(), f, ensure_ascii=False, indent=2)


class ConfigManager:
    """
    配置管理器，支持配置分层和切换
    
    使用方法：
        manager = ConfigManager()
        manager.register("dev", dev_config)
        manager.register("prod", prod_config)
        manager.activate("dev")
        config = manager.active
    """

    def __init__(self):
        self._configs: Dict[str, AgentConfig] = {}
        self._active_config: Optional[str] = None

    def register(self, name: str, config: AgentConfig):
        """
        注册配置
        
        Args:
            name: 配置名称
            config: AgentConfig实例
        """
        self._configs[name] = config

    def activate(self, name: str):
        """
        激活配置
        
        Args:
            name: 要激活的配置名称
        """
        if name in self._configs:
            self._active_config = name

    @property
    def active(self) -> AgentConfig:
        """
        获取当前活动配置
        
        Returns:
            AgentConfig实例
            
        Raises:
            RuntimeError: 如果没有活动配置
        """
        if self._active_config:
            return self._configs.get(self._active_config)
        raise RuntimeError("No active configuration. Call activate() first.")

    def get(self, name: str) -> Optional[AgentConfig]:
        """
        获取指定名称的配置
        
        Args:
            name: 配置名称
            
        Returns:
            AgentConfig实例或None
        """
        return self._configs.get(name)

    def merge(self, base: str, overlay: str) -> AgentConfig:
        """
        合并配置
        
        使用overlay配置覆盖base配置的值
        
        Args:
            base: 基础配置名称
            overlay: 覆盖配置名称
            
        Returns:
            合并后的AgentConfig实例
        """
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
            enable_thinking=overlay_config.enable_thinking or base_config.enable_thinking,
            display_enabled=overlay_config.display_enabled or base_config.display_enabled,
            workspace_root=overlay_config.workspace_root or base_config.workspace_root,
            environment_type=overlay_config.environment_type or base_config.environment_type,
            enabled_action_spaces=overlay_config.enabled_action_spaces or base_config.enabled_action_spaces,
        )

    def list_registered(self) -> list:
        """
        列出已注册的配置名称
        
        Returns:
            配置名称列表
        """
        return list(self._configs.keys())
```

**验收标准**：

1. `src/yoga_next/core/config.py`文件存在
2. `AgentConfig`使用pydantic验证
3. 支持YAML文件加载和保存
4. 支持环境变量加载
5. `ConfigManager`正确管理多个配置
6. 原有`agent_config.py`保持兼容
7. 单元测试覆盖所有功能

**预期工作量**：1人天

---

### 任务2.2：实现EventBus和EventRecorder

**原始文件**：无（新建设立）

**新创建文件**：
- `src/yoga_next/core/event_bus.py`

**具体步骤**：

1. 创建`src/yoga_next/core/event_bus.py`文件
2. 实现`EventType`枚举：
   - TASK_STARTED
   - TASK_COMPLETED
   - TASK_ERROR
   - ACTION_EXECUTED
   - ACTION_COMPLETED
   - ACTION_ERROR
   - THOUGHT_GENERATED
   - STATE_CHANGED
   - MEMORY_UPDATED

3. 实现`Event`数据类：
   - type: EventType
   - payload: Dict[str, Any]
   - timestamp: float
   - source: Optional[str]

4. 实现`EventHandler`类：
   - 接收callback和event_types
   - 实现`handle(event)`方法

5. 实现`EventBus`类：
   - 实现`__init__()`初始化handlers和queue
   - 实现`subscribe(callback, event_types)`订阅事件
   - 实现`unsubscribe(handler)`取消订阅
   - 实现`publish(event)`同步发布
   - 实现`publish_async(event_type, payload, source)`异步发布
   - 实现`start()`和`stop()`方法

6. 实现`EventRecorder`类：
   - 实现`__init__(event_bus)`初始化
   - 实现`start()`和`stop()`控制记录
   - 实现`get_events(event_type)`获取事件
   - 实现`to_json()`导出JSON

7. 编写单元测试，保存到`src/yoga_next/tests/unit/test_event_bus.py`

**代码模板**：

```python
# src/yoga_next/core/event_bus.py

from typing import Callable, Dict, Any, List, Optional
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
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
    timestamp: float = field(default_factory=lambda: datetime.now().timestamp())
    source: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "type": self.type.value,
            "payload": self.payload,
            "timestamp": self.timestamp,
            "source": self.source
        }


class EventHandler:
    """事件处理器"""

    def __init__(self, callback: Callable, event_types: List[EventType] = None):
        """
        初始化事件处理器
        
        Args:
            callback: 事件处理回调函数
            event_types: 关注的事件类型列表，None表示关注所有
        """
        self.callback = callback
        self.event_types = event_types or []

    async def handle(self, event: Event):
        """
        处理事件
        
        Args:
            event: 事件对象
        """
        if not self.event_types or event.type in self.event_types:
            await self.callback(event)


class EventBus:
    """
    事件总线，实现发布/订阅模式
    
    使用方法：
        bus = EventBus()
        
        # 订阅事件
        def on_task_started(event):
            print(f"Task started: {event.payload}")
        
        handler = bus.subscribe(on_task_started, [EventType.TASK_STARTED])
        
        # 发布事件
        await bus.publish(Event(EventType.TASK_STARTED, {"task_id": "123"}))
        
        # 取消订阅
        bus.unsubscribe(handler)
    """

    def __init__(self):
        self._handlers: List[EventHandler] = []
        self._queue: asyncio.Queue = asyncio.Queue()
        self._running: bool = False
        self._task: Optional[asyncio.Task] = None

    def subscribe(
        self,
        callback: Callable,
        event_types: List[EventType] = None
    ) -> EventHandler:
        """
        订阅事件
        
        Args:
            callback: 事件处理回调
            event_types: 关注的事件类型
            
        Returns:
            EventHandler实例，可用于取消订阅
        """
        handler = EventHandler(callback, event_types)
        self._handlers.append(handler)
        return handler

    def unsubscribe(self, handler: EventHandler):
        """
        取消订阅
        
        Args:
            handler: 要取消的EventHandler
        """
        if handler in self._handlers:
            self._handlers.remove(handler)

    async def publish(self, event: Event):
        """
        同步发布事件
        
        Args:
            event: 事件对象
        """
        for handler in self._handlers:
            await handler.handle(event)

    async def publish_async(
        self,
        event_type: EventType,
        payload: Dict[str, Any],
        source: str = None
    ):
        """
        异步发布事件
        
        Args:
            event_type: 事件类型
            payload: 事件数据
            source: 事件源
        """
        event = Event(
            type=event_type,
            payload=payload,
            timestamp=datetime.now().timestamp(),
            source=source
        )
        await self._queue.put(event)

    async def start(self):
        """启动事件处理循环"""
        if not self._running:
            self._running = True
            self._task = asyncio.create_task(self._process_events())

    async def stop(self):
        """停止事件处理循环"""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

    async def _process_events(self):
        """事件处理循环"""
        while self._running:
            try:
                event = await asyncio.wait_for(self._queue.get(), timeout=1.0)
                await self.publish(event)
                self._queue.task_done()
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break

    @property
    def is_running(self) -> bool:
        """检查是否正在运行"""
        return self._running


class EventRecorder:
    """
    事件记录器，用于调试和分析
    
    使用方法：
        recorder = EventRecorder(event_bus)
        recorder.start()
        
        # ... 执行一些操作
        
        events = recorder.get_events(EventType.ACTION_EXECUTED)
        json_output = recorder.to_json()
        
        recorder.stop()
    """

    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus
        self.events: List[Event] = []
        self._subscription: Optional[EventHandler] = None

    def start(self):
        """开始记录事件"""
        self.events.clear()
        self._subscription = self.event_bus.subscribe(self._record)

    def stop(self):
        """停止记录事件"""
        if self._subscription:
            self.event_bus.unsubscribe(self._subscription)
            self._subscription = None

    async def _record(self, event: Event):
        """记录事件"""
        self.events.append(event)

    def get_events(self, event_type: EventType = None) -> List[Event]:
        """
        获取事件
        
        Args:
            event_type: 可选的事件类型过滤
            
        Returns:
            事件列表
        """
        if event_type:
            return [e for e in self.events if e.type == event_type]
        return self.events.copy()

    def get_events_by_source(self, source: str) -> List[Event]:
        """
        按来源获取事件
        
        Args:
            source: 事件来源
            
        Returns:
            事件列表
        """
        return [e for e in self.events if e.source == source]

    def to_json(self) -> str:
        """导出为JSON"""
        import json
        return json.dumps(
            [e.to_dict() for e in self.events],
            indent=2,
            ensure_ascii=False
        )

    def clear(self):
        """清空记录"""
        self.events.clear()
```

**验收标准**：

1. `src/yoga_next/core/event_bus.py`文件存在
2. `EventType`包含所有定义的事件类型
3. `EventBus`支持同步和异步发布
4. `EventHandler`正确过滤事件类型
5. `EventRecorder`正确记录和导出事件
6. 单元测试覆盖所有功能

**预期工作量**：1人天

---

### 任务2.3：更新agent_service.py使用新配置

**原始文件**：
- `src/yoga_next/agent_service.py`

**具体步骤**：

1. 阅读`src/yoga_next/agent_service.py`，理解当前配置加载方式（第76-106行）

2. 修改`AgentService.initialize()`方法：
   - 使用`AgentConfig.from_yaml()`加载配置
   - 使用`EnvironmentFactory.create()`创建环境
   - 使用`ConfigManager`管理配置

3. 更新导入语句：
   ```python
   # 新增导入
   from yoga_next.core.config import AgentConfig, ConfigManager
   from yoga_next.core.environment_factory import EnvironmentFactory
   ```

4. 修改环境创建逻辑（第82-90行）：
   ```python
   # 原代码
   env_config = {
       "workspace_root": workspace_root,
       "bridge_type": "stdio"
   }
   self.env = ElectronAppEnv(env_config)
   
   # 新代码
   env_config = {
       "workspace_root": workspace_root,
       "bridge_type": "stdio"
   }
   self.env = EnvironmentFactory.create("electron", env_config)
   ```

5. 修改Agent创建逻辑（第92-106行）：
   ```python
   # 使用ConfigManager管理配置
   self.config_manager = ConfigManager()
   
   try:
       agent_config = AgentConfig.from_yaml(self.config_path)
   except Exception as e:
       log_error(f"Failed to load config from {self.config_path}: {e}")
       agent_config = AgentConfig(
           api_base_url="https://api.openai.com/v1",
           model_name="gpt-4o",
           api_key=""
       )
   
   self.config_manager.register("default", agent_config)
   self.config_manager.activate("default")
   ```

6. 确保更新后的代码保持原有功能不变

7. 运行测试验证功能正常

**修改代码示例**：

```python
# src/yoga_next/agent_service.py (片段)

# 找到AgentService类，修改initialize方法

class AgentService:
    def __init__(self):
        self.agent: Optional[Agent] = None
        self.env: Optional[Environment] = None
        self.glim_space: Optional[GlimAppActionSpace] = None
        self.config_path: str = ""
        self.current_task_id: Optional[str] = None
        self.task_status: Dict[str, TaskStatus] = {}
        self._pending_modifications: Dict[str, PendingModification] = {}
        self._events: asyncio.Queue = asyncio.Queue()
        self._running_tasks: Dict[str, asyncio.Task] = {}
        
        # 新增：配置管理器
        self.config_manager = ConfigManager()

    async def initialize(self, workspace_root: str, config_path: str = ""):
        self.config_path = config_path or os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "configs/config_local.yaml"
        )

        env_config = {
            "workspace_root": workspace_root,
            "bridge_type": "stdio"
        }

        # 使用EnvironmentFactory创建环境
        self.env = EnvironmentFactory.create("electron", env_config)
        await self.env.setup()

        self.glim_space = GlimAppActionSpace("glim_app", self.env)

        # 使用AgentConfig加载配置
        try:
            agent_config = AgentConfig.from_yaml(self.config_path)
        except Exception as e:
            log_error(f"Failed to load config from {self.config_path}: {e}")
            agent_config = AgentConfig(
                api_base_url="https://api.openai.com/v1",
                model_name="gpt-4o",
                api_key=""
            )

        # 注册并激活配置
        self.config_manager.register("default", agent_config)
        self.config_manager.activate("default")

        self.agent = Agent(
            agent_config=self.config_manager.active,
            action_spaces=[self.glim_space],
            use_rich_display=False
        )

        log_info(f"AgentService initialized with workspace: {workspace_root}")
```

**验收标准**：

1. `src/yoga_next/agent_service.py`使用新的AgentConfig
2. `EnvironmentFactory.create()`替代直接环境类实例化
3. `ConfigManager`管理配置
4. API端点功能测试通过
5. 原有配置文件的兼容性

**预期工作量**：1人天

---

### 任务2.4：编写配置和事件系统集成测试

**需要测试的文件**：
- `src/yoga_next/core/config.py`
- `src/yoga_next/core/event_bus.py`
- `src/yoga_next/agent_service.py`

**新创建文件**：
- `src/yoga_next/tests/integration/__init__.py`
- `src/yoga_next/tests/integration/test_config_integration.py`
- `src/yoga_next/tests/integration/test_event_integration.py`
- `src/yoga_next/tests/integration/test_agent_service_integration.py`

**具体步骤**：

1. 创建集成测试目录结构
2. 编写`test_config_integration.py`：
   - 测试从YAML文件加载配置
   - 测试从环境变量加载配置
   - 测试配置合并
   - 测试ConfigManager切换

3. 编写`test_event_integration.py`：
   - 测试事件发布和订阅
   - 测试事件类型过滤
   - 测试EventRecorder记录
   - 测试异步事件处理

4. 编写`test_agent_service_integration.py`：
   - 测试AgentService初始化
   - 测试任务执行流程
   - 测试配置传递

5. 运行集成测试确保所有测试通过

**测试代码模板**：

```python
# src/yoga_next/tests/integration/test_config_integration.py

import pytest
import os
import tempfile
from yoga_next.core.config import AgentConfig, ConfigManager


class TestConfigIntegration:
    """配置集成测试"""
    
    @pytest.fixture
    def yaml_config(self):
        """创建测试YAML配置文件"""
        content = """
api_base_url: https://api.example.com/v1
model_name: gpt-4
api_key: test-key-123
max_steps: 50
timeout_seconds: 600
enable_thinking: true
display_enabled: true
workspace_root: /tmp/test_workspace
environment_type: local
enabled_action_spaces:
  - control
  - thinking
  - edit
"""
        with tempfile.NamedTemporaryFile(
            mode='w', suffix='.yaml', delete=False
        ) as f:
            f.write(content)
            f.flush()
            yield f.name
            os.unlink(f.name)
    
    def test_load_from_yaml(self, yaml_config):
        """测试从YAML加载配置"""
        config = AgentConfig.from_yaml(yaml_config)
        
        assert config.api_base_url == "https://api.example.com/v1"
        assert config.model_name == "gpt-4"
        assert config.api_key == "test-key-123"
        assert config.max_steps == 50
        assert config.timeout_seconds == 600
        assert config.enable_thinking is True
        assert "control" in config.enabled_action_spaces
    
    def test_config_manager_registration(self):
        """测试配置管理器注册"""
        manager = ConfigManager()
        
        config1 = AgentConfig(
            api_base_url="https://api1.com",
            model_name="model1"
        )
        config2 = AgentConfig(
            api_base_url="https://api2.com",
            model_name="model2"
        )
        
        manager.register("dev", config1)
        manager.register("prod", config2)
        
        assert "dev" in manager.list_registered()
        assert "prod" in manager.list_registered()
        assert manager.get("dev") == config1
        assert manager.get("prod") == config2
    
    def test_config_manager_activation(self):
        """测试配置管理器激活"""
        manager = ConfigManager()
        
        config1 = AgentConfig(
            api_base_url="https://api1.com",
            model_name="model1"
        )
        config2 = AgentConfig(
            api_base_url="https://api2.com",
            model_name="model2"
        )
        
        manager.register("dev", config1)
        manager.register("prod", config2)
        
        manager.activate("dev")
        assert manager.active.api_base_url == "https://api1.com"
        
        manager.activate("prod")
        assert manager.active.api_base_url == "https://api2.com"
    
    def test_config_merge(self):
        """测试配置合并"""
        manager = ConfigManager()
        
        base_config = AgentConfig(
            api_base_url="https://base.com",
            model_name="base-model",
            max_steps=100
        )
        overlay_config = AgentConfig(
            api_base_url="https://overlay.com",
            model_name="overlay-model"
        )
        
        manager.register("base", base_config)
        manager.register("overlay", overlay_config)
        
        merged = manager.merge("base", "overlay")
        
        assert merged.api_base_url == "https://overlay.com"
        assert merged.model_name == "overlay-model"
        assert merged.max_steps == 100  # 来自base
```

**验收标准**：

1. 集成测试文件存在于正确目录
2. 每个集成测试至少覆盖一个完整功能流程
3. 测试使用真实配置文件和环境
4. 所有集成测试通过
5. 测试覆盖率不低于60%

**预期工作量**：1人天

---

## 阶段3：Agent重构

### 任务3.1：实现AgentCore

**原始文件**：
- `src/yoga_next/agent.py`（第1-150行）

**新创建文件**：
- `src/yoga_next/core/agent_core.py`

**具体步骤**：

1. 创建`src/yoga_next/core/agent_core.py`文件
2. 实现`AgentCore`抽象类：
   - 接收model、action_spaces、environment参数
   - 实现`execute(task, max_steps)`入口方法
   - 声明`execute_single_task(task, task_idx, max_steps)`抽象方法
   - 实现`create_state(task, prev_action, obs, step_num)`方法
   - 实现`_get_thought_trace()`方法（由子类实现）
   - 实现`_add_to_memory_stream()`方法

3. 保持与原有Agent类的接口兼容：
   - 相同的初始化参数
   - 相同的执行流程
   - 相同的内存管理

4. 编写单元测试，保存到`src/yoga_next/tests/unit/test_agent_core.py`

**代码模板**：

```python
# src/yoga_next/core/agent_core.py

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from ..tasks import Task
from ..memory import Memory
from ..model import Model
from ..actions import ActionSpace, UnionActionSpace
from ..environments import Environment
from ..hm import MemoryStream, MemoryChunk
import time


class AgentCore(ABC):
    """
    Agent核心执行引擎，专注于任务执行逻辑
    
    抽象基类，具体的执行策略由子类实现
    """

    def __init__(
        self,
        model: Model,
        action_spaces: List[ActionSpace],
        environment: Optional[Environment] = None
    ):
        """
        初始化Agent核心
        
        Args:
            model: LLM模型实例
            action_spaces: 动作空间列表
            environment: 可选的环境实例
        """
        self.model = model
        self.action_space = UnionActionSpace(action_spaces)
        self.environment = environment
        self.memory = Memory(model)
        self.memory_stream = MemoryStream()
        
        self.task: Optional[Task] = None
        self.final_result: Optional[Dict[str, Any]] = None

    @abstractmethod
    async def execute_single_task(
        self,
        task: Task,
        task_idx: int,
        max_steps: int
    ) -> str:
        """
        执行单个任务，由子类实现具体策略
        
        Args:
            task: 任务对象
            task_idx: 任务索引
            max_steps: 最大步数
            
        Returns:
            执行结果字符串
        """
        pass

    async def execute(self, task: Task, max_steps: int = 100) -> Dict[str, Any]:
        """
        任务执行入口
        
        Args:
            task: 任务对象
            max_steps: 最大执行步数
            
        Returns:
            包含result和final_output的字典
        """
        self.task = task
        self.final_result = None
        
        result = await self.execute_single_task(task, task_idx=-1, max_steps=max_steps)
        
        return {
            "result": result,
            "final_output": self.final_result
        }

    def create_state(
        self,
        task: Task,
        prev_action: str,
        obs: str,
        step_num: int
    ) -> str:
        """
        创建执行状态字符串
        
        Args:
            task: 任务对象
            prev_action: 上一个动作
            obs: 观察结果
            step_num: 当前步数
            
        Returns:
            格式化的状态字符串
        """
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
        """
        获取思考追踪
        
        子类应重写此方法以提供实际的思考追踪
        """
        return ""

    def _add_to_memory_stream(
        self,
        task_id: str,
        step_num: int,
        message_type: str,
        content: Dict[str, Any]
    ):
        """
        添加到记忆流
        
        Args:
            task_id: 任务ID
            step_num: 步数
            message_type: 消息类型
            content: 消息内容
        """
        env_state = self.environment.get_observation() if self.environment else ""
        timestamp = time.time()
        
        memory_chunk = MemoryChunk(
            task_id=task_id,
            step_num=step_num,
            message_type=message_type,
            content=content,
            environment_state=env_state,
            timestamp=timestamp
        )
        
        self.memory_stream.add_chunk(memory_chunk)

    def dump_memory_stream(self, exp_file_path: str):
        """
        导出记忆流到文件
        
        Args:
            exp_file_path: 输出文件路径
        """
        import os
        os.makedirs(os.path.dirname(exp_file_path), exist_ok=True)
        self.memory_stream.dump(exp_file_path)
```

**验收标准**：

1. `src/yoga_next/core/agent_core.py`文件存在
2. `AgentCore`是抽象类，包含必要的抽象方法
3. `execute()`方法正确调用`execute_single_task()`
4. `create_state()`方法生成正确的状态字符串
5. `_add_to_memory_stream()`正确记录记忆
6. 单元测试覆盖核心功能

**预期工作量**：1人天

---

### 任务3.2：实现AgentExecutor

**原始文件**：
- `src/yoga_next/agent.py`（第298-465行）

**新创建文件**：
- `src/yoga_next/core/agent_executor.py`

**具体步骤**：

1. 创建`src/yoga_next/core/agent_executor.py`文件
2. 实现`AgentExecutor`类：
   - 接收`AgentCore`实例
   - 实现主执行循环逻辑
   - 处理动作执行
   - 管理状态更新

3. 迁移原有`Agent.execute_single_task()`的逻辑：
   - 内存初始化
   - 主循环（for step_num in range(1, max_steps+1)）
   - LLM调用
   - JSON解析
   - 动作执行
   - 状态更新

4. 处理特殊动作（done, sequential_thinking）

5. 编写单元测试，保存到`src/yoga_next/tests/unit/test_agent_executor.py`

**代码模板**：

```python
# src/yoga_next/core/agent_executor.py

from .agent_core import AgentCore
from ..tasks import Task
from ..utils import extract_json_from_model_markdown_output, flatten_to_kv_string
from typing import Dict, Any, List
import logging

logger = logging.getLogger(__name__)


class AgentExecutor:
    """
    Agent执行策略管理器
    
    实现具体的主执行循环逻辑
    """

    def __init__(self, agent_core: AgentCore):
        """
        初始化执行器
        
        Args:
            agent_core: AgentCore实例
        """
        self.agent = agent_core

    async def run_execution_loop(
        self,
        task: Task,
        task_idx: int,
        max_steps: int
    ) -> str:
        """
        执行主循环
        
        Args:
            task: 任务对象
            task_idx: 任务索引
            max_steps: 最大步数
            
        Returns:
            执行结果字符串
        """
        self.agent.memory.clear_task_related_memory()
        
        initial_state = self.agent.create_state(
            task=task,
            prev_action='(none)',
            obs='(none)',
            step_num=0
        )
        
        self.agent.memory.add(role='user', content=initial_state)

        task_status = 'Reach maximal steps. Forwarding to the next task.'

        for step_num in range(1, max_steps + 1):
            # LLM调用
            output = self.agent.model.chat_completion(
                self.agent.memory.get_messages()
            )
            
            self.agent.memory.add(role='assistant', content=output)

            # 解析JSON
            parsed_json = extract_json_from_model_markdown_output(output)
            parsed_json['raw_model_output'] = output
            actions = parsed_json.get('action', [])
            
            # 更新工作内存
            if 'current_state' in parsed_json:
                memory_content = parsed_json['current_state'].get('memory', '')
                self.agent.memory.add_working_memory(task_idx, step_num, memory_content)

            # 无动作处理
            if len(actions) == 0:
                logger.warning("No actions parsed from model output")
                state = self.agent.create_state(
                    task=task,
                    prev_action='No action parsed',
                    obs='Skipping to next step',
                    step_num=step_num
                )
                self.agent.memory.add(role='user', content=state)
                continue

            # 执行动作
            observations = []
            for action in actions:
                action_name = action['action_name']
                action_params = action['action_params']

                result = await self.agent.action_space.execute(
                    action_name,
                    action_params
                )

                if action_name == 'done':
                    self.agent.final_result = result
                    return result.get("message", "Task completed")

                # 格式化结果
                result_str = flatten_to_kv_string(result)
                observations.append(result_str)

            # 更新状态
            state = self.agent.create_state(
                task=task,
                prev_action=parsed_json['current_state'].get('next_goal', ''),
                obs='\n\n'.join(observations),
                step_num=step_num
            )
            self.agent.memory.add(role='user', content=state)

        return task_status
```

**验收标准**：

1. `src/yoga_next/core/agent_executor.py`文件存在
2. `AgentExecutor`正确执行主循环
3. 动作执行流程正确
4. 内存更新逻辑正确
5. 单元测试覆盖核心场景

**预期工作量**：1人天

---

### 任务3.3：实现AgentDisplay

**原始文件**：
- `src/yoga_next/utils.py`（第522-683行）

**新创建文件**：
- `src/yoga_next/core/agent_display.py`

**具体步骤**：

1. 创建`src/yoga_next/core/agent_display.py`文件
2. 实现`AgentDisplay`类：
   - 封装YogDisplay的使用
   - 实现`render_step_header(step_num)`方法
   - 实现`render_agent_plan(step_num, parsed_json, actions)`方法
   - 实现`_extract_think_tag(content)`方法
   - 实现`render_action_result(action_name, result)`方法
   - 实现`render_done(success, message)`方法

3. 提取UI渲染逻辑，移除与核心逻辑的耦合

4. 编写单元测试，保存到`src/yoga_next/tests/unit/test_agent_display.py`

**代码模板**：

```python
# src/yoga_next/core/agent_display.py

from typing import Dict, Any, Optional, List
from ..utils import YogDisplay
from rich.panel import Panel
from rich.text import Text
from rich.rule import Rule
from rich.table import Table
from rich import box
import re


class AgentDisplay:
    """
    Agent显示渲染接口
    
    封装所有UI渲染逻辑，与核心逻辑解耦
    """

    def __init__(self, display: Optional[YogDisplay] = None):
        """
        初始化显示接口
        
        Args:
            display: 可选的YogDisplay实例
        """
        self.display = display or YogDisplay()

    def render_step_header(self, step_num: int):
        """
        渲染步骤头部
        
        Args:
            step_num: 当前步数
        """
        self.display.console.print("\n")
        self.display.console.print(Rule(
            title=f"[bold white] STEP {step_num} [/bold white]",
            style="on blue",
            characters=" "
        ))

    def render_agent_plan(
        self,
        step_num: int,
        parsed_json: Dict[str, Any],
        actions: List[Dict[str, Any]]
    ):
        """
        渲染Agent执行计划
        
        Args:
            step_num: 当前步数
            parsed_json: 解析的JSON
            actions: 动作列表
        """
        # 提取思考内容
        raw_output = parsed_json.get('raw_model_output', '')
        think_content = self._extract_think_tag(raw_output)

        if think_content:
            self.display.console.print(Panel(
                Text(think_content, style="italic cyan"),
                title="[bold cyan]🧠 Internal Thought[/bold cyan]",
                border_style="cyan",
                subtitle="Mental Sandbox",
                expand=True
            ))

        # 渲染状态表格
        status_table = Table.grid(expand=True)
        status_table.add_column(ratio=1)
        status_table.add_column(ratio=1)

        memory = self.agent.memory.get_working_memory() if hasattr(self.agent, 'memory') else ""
        
        memory_panel = Panel(
            Text(str(memory), style="grey70"),
            title="[bold magenta]💾 Working Memory[/bold magenta]",
            border_style="magenta",
            expand=True
        )

        curr_state = parsed_json.get('current_state', {})
        next_goal = curr_state.get('next_goal', '...')
        
        goal_panel = Panel(
            Text(str(next_goal), style="bold white"),
            title="[bold blue]🎯 Next Goal[/bold blue]",
            border_style="blue",
            expand=True
        )

        status_table.add_row(memory_panel, goal_panel)
        self.display.console.print(status_table)

        # 渲染动作表格
        action_table = Table(
            box=box.ROUNDED,
            expand=True,
            show_header=True,
            header_style="bold yellow"
        )
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
                str(i + 1),
                act['action_name'],
                params_str
            )

        self.display.console.print(Panel(
            action_table,
            title="[bold green]🚀 Execution Plan[/bold green]",
            border_style="green"
        ))

    def _extract_think_tag(self, content: str) -> str:
        """
        提取思考标签内容
        
        Args:
            content: 原始内容
            
        Returns:
            思考内容或空字符串
        """
        match = re.search(r'<think>(.*?)</think>', content, re.DOTALL)
        return match.group(1).strip() if match else ""

    def render_action_result(
        self,
        action_name: str,
        result: Dict[str, Any]
    ):
        """
        渲染动作结果
        
        Args:
            action_name: 动作名称
            result: 执行结果
        """
        if hasattr(self.display, 'render_observation'):
            result_for_render = result.copy()
            result_for_render['action'] = action_name
            self.display.render_observation(result_for_render)

    def render_done(self, success: bool, message: str):
        """
        渲染完成状态
        
        Args:
            success: 是否成功
            message: 完成消息
        """
        title = "✅ Mission Accomplished" if success else "❌ Mission Failed"
        style = "bold green" if success else "bold red"
        self.display.console.print("\n")
        self.display.console.print(Panel(
            message,
            title=title,
            border_style=style,
            padding=(1, 4)
        ))

    def render_planning(self, task_description: str):
        """
        渲染规划阶段
        
        Args:
            task_description: 任务描述
        """
        self.display.console.print(Panel(
            task_description,
            title="📋 Planning",
            border_style="cyan",
            expand=False
        ))
```

**验收标准**：

1. `src/yoga_next/core/agent_display.py`文件存在
2. `AgentDisplay`类封装所有UI渲染
3. 与原有YogDisplay兼容
4. 单元测试覆盖主要渲染方法

**预期工作量**：1人天

---

### 任务3.4：创建适配器并更新agent.py

**原始文件**：
- `src/yoga_next/agent.py`

**新创建文件**：
- `src/yoga_next/adapters/__init__.py`
- `src/yoga_next/adapters/agent_adapter.py`

**具体步骤**：

1. 创建`adapters`目录和`__init__.py`
2. 创建`src/yoga_next/adapters/agent_adapter.py`：
   - 实现`AgentAdapter`类，继承`AgentCore`
   - 接收原有`Agent`实例
   - 实现`execute_single_task()`方法委托给旧Agent

3. 修改`src/yoga_next/agent.py`：
   - 添加对新core模块的导入
   - 保持原有API不变
   - 在文档字符串中注明已支持新架构

4. 更新`src/yoga_next/__init__.py`：
   - 添加对adapters的导入

5. 运行测试确保兼容

**适配器代码模板**：

```python
# src/yoga_next/adapters/agent_adapter.py

from ..core.agent_core import AgentCore
from ..tasks import Task
from typing import Dict, Any


class AgentAdapter(AgentCore):
    """
    适配器：使新架构兼容旧Agent类
    
    通过委托模式，将新架构的调用转发给原有的Agent实现
    """

    def __init__(self, legacy_agent: 'LegacyAgent'):
        """
        初始化适配器
        
        Args:
            legacy_agent: 原有Agent实例
        """
        # 提取旧Agent的核心属性
        super().__init__(
            model=legacy_agent.model,
            action_spaces=[legacy_agent.action_space],
            environment=legacy_agent.action_space.env if hasattr(legacy_agent.action_space, 'env') else None
        )
        self._legacy_agent = legacy_agent
        self._display = legacy_agent.display
        self._thinking_space = legacy_agent.thinking_space

    async def execute_single_task(
        self,
        task: Task,
        task_idx: int,
        max_steps: int
    ) -> str:
        """
        执行单个任务，委托给旧Agent
        
        Args:
            task: 任务对象
            task_idx: 任务索引
            max_steps: 最大步数
            
        Returns:
            执行结果
        """
        return await self._legacy_agent.execute_single_task(
            task,
            task_idx,
            max_steps
        )

    def _get_thought_trace(self) -> str:
        """获取思考追踪"""
        if hasattr(self._thinking_space, 'get_thought_trace'):
            return self._thinking_space.get_thought_trace()
        return ""
```

**更新agent.py示例**：

```python
# src/yoga_next/agent.py

# 在文件开头添加
try:
    from .core.agent_core import AgentCore
    from .core.agent_executor import AgentExecutor
    from .core.agent_display import AgentDisplay
    from .adapters.agent_adapter import AgentAdapter
    _NEW_ARCHITECTURE_AVAILABLE = True
except ImportError:
    _NEW_ARCHITECTURE_AVAILABLE = False

# 修改Agent类，支持新架构
class Agent:
    # ... 现有代码保持不变 ...
    
    def __init__(
        self,
        agent_config=None,  # 修改为可选参数
        action_spaces=None,
        use_rich_display=True
    ):
        # 现有初始化逻辑...
        
        # 如果传入了新配置，初始化新架构
        if _NEW_ARCHITECTURE_AVAILABLE and agent_config is not None:
            # 使用新架构的初始化逻辑
            pass
    
    def create_new_arch_instance(self, config, action_spaces):
        """
        使用新架构创建实例
        
        用于迁移到新架构的工厂方法
        """
        adapter = AgentAdapter(self)
        # ... 配置新架构组件 ...
        return adapter
```

**验收标准**：

1. `adapters`目录存在
2. `AgentAdapter`正确继承`AgentCore`
3. `execute_single_task()`正确委托
4. `agent.py`保持原有API不变
5. 所有测试通过

**预期工作量**：1人天

---

## 阶段4：插件系统

### 任务4.1：实现PluginInterface和PluginManager

**原始文件**：无（新建设立）

**新创建文件**：
- `src/yoga_next/core/plugin_system.py`

**具体步骤**：

1. 创建`src/yoga_next/core/plugin_system.py`文件
2. 实现`PluginInterface`抽象类：
   - `name`属性
   - `version`属性
   - `description`属性
   - `register_actions()`方法
   - `register_environments()`方法
   - `on_load()`方法
   - `on_unload()`方法

3. 实现`PluginManager`类：
   - 实现`__init__()`初始化_plugin、_action_spaces、_environments字典
   - 实现`load_plugin(plugin)`加载插件
   - 实现`unload_plugin(name)`卸载插件
   - 实现`list_plugins()`列出插件
   - 实现`get_action_space(name)`获取动作
   - 实现`get_environment(name)`获取环境

4. 编写单元测试，保存到`src/yoga_next/tests/unit/test_plugin_system.py`

**代码模板**：

```python
# src/yoga_next/core/plugin_system.py

from typing import Dict, Any, Type, Optional
from abc import ABC, abstractmethod
from ..actions.base import ActionSpace
from ..environments.base import Environment


class PluginInterface(ABC):
    """
    插件接口
    
    所有插件必须实现此接口
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """插件名称"""
        pass

    @property
    @abstractmethod
    def version(self) -> str:
        """插件版本"""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """插件描述"""
        pass

    @abstractmethod
    def register_actions(self) -> Dict[str, Type[ActionSpace]]:
        """
        注册动作空间
        
        Returns:
            动作空间名称到类的映射
        """
        pass

    @abstractmethod
    def register_environments(self) -> Dict[str, Type[Environment]]:
        """
        注册环境
        
        Returns:
            环境名称到类的映射
        """
        pass

    @abstractmethod
    def on_load(self):
        """插件加载时调用"""
        pass

    @abstractmethod
    def on_unload(self):
        """插件卸载时调用"""
        pass


class PluginManager:
    """
    插件管理器
    
    负责插件的加载、卸载和查询
    """

    def __init__(self):
        self._plugins: Dict[str, PluginInterface] = {}
        self._action_spaces: Dict[str, Type[ActionSpace]] = {}
        self._environments: Dict[str, Type[Environment]] = {}

    def load_plugin(self, plugin: PluginInterface):
        """
        加载插件
        
        Args:
            plugin: 插件实例
        """
        # 调用on_load生命周期钩子
        plugin.on_load()
        
        # 存储插件
        self._plugins[plugin.name] = plugin
        
        # 注册动作
        for name, action_space in plugin.register_actions().items():
            self._action_spaces[name] = action_space
        
        # 注册环境
        for name, env_class in plugin.register_environments().items():
            self._environments[name] = env_class

    def unload_plugin(self, name: str):
        """
        卸载插件
        
        Args:
            name: 插件名称
        """
        if name in self._plugins:
            # 调用on_unload生命周期钩子
            self._plugins[name].on_unload()
            del self._plugins[name]

    def list_plugins(self) -> list:
        """
        列出已加载的插件
        
        Returns:
            插件信息列表
        """
        return [
            {
                "name": p.name,
                "version": p.version,
                "description": p.description
            }
            for p in self._plugins.values()
        ]

    def get_action_space(self, name: str) -> Optional[Type[ActionSpace]]:
        """
        获取动作空间类
        
        Args:
            name: 动作空间名称
            
        Returns:
            ActionSpace子类或None
        """
        return self._action_spaces.get(name)

    def get_environment(self, name: str) -> Optional[Type[Environment]]:
        """
        获取环境类
        
        Args:
            name: 环境名称
            
        Returns:
            Environment子类或None
        """
        return self._environments.get(name)

    def get_plugin(self, name: str) -> Optional[PluginInterface]:
        """
        获取插件实例
        
        Args:
            name: 插件名称
            
        Returns:
            PluginInterface实例或None
        """
        return self._plugins.get(name)
```

**验收标准**：

1. `src/yoga_next/core/plugin_system.py`文件存在
2. `PluginInterface`包含所有必需方法
3. `PluginManager`正确管理插件
4. 单元测试覆盖核心功能

**预期工作量**：1人天

---

### 任务4.2：创建示例插件

**原始文件**：
- `src/yoga_next/actions/control.py`

**新创建文件**：
- `src/yoga_next/plugins/__init__.py`
- `src/yoga_next/plugins/example_plugin.py`

**具体步骤**：

1. 创建`plugins`目录和`__init__.py`
2. 创建`src/yoga_next/plugins/example_plugin.py`：
   - 实现`ExamplePlugin`类
   - 继承`PluginInterface`
   - 实现所有必需方法
   - 注册一个示例动作空间

3. 创建简单的测试插件，演示插件开发流程

4. 编写插件文档注释

**示例插件代码模板**：

```python
# src/yoga_next/plugins/example_plugin.py

from typing import Dict, Type
from ..core.plugin_system import PluginInterface
from ..actions.base import ActionSpace
from ..environments.base import Environment
from ..actions.control import ControlActionSpace


class ExamplePlugin(PluginInterface):
    """
    示例插件
    
    演示如何开发YOGA Agent插件
    """

    @property
    def name(self) -> str:
        return "example-plugin"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def description(self) -> str:
        return "示例插件，提供基本的控制功能"

    def register_actions(self) -> Dict[str, Type[ActionSpace]]:
        """
        注册动作空间
        
        Returns:
            动作空间名称到类的映射
        """
        return {
            "control": ControlActionSpace,
        }

    def register_environments(self) -> Dict[str, Type[Environment]]:
        """
        注册环境
        
        Returns:
            空字典（此插件不注册环境）
        """
        return {}

    def on_load(self):
        """插件加载时调用"""
        print(f"Plugin {self.name} v{self.version} loaded")

    def on_unload(self):
        """插件卸载时调用"""
        print(f"Plugin {self.name} unloaded")


# 注册插件实例
example_plugin = ExamplePlugin()
```

**验收标准**：

1. `plugins`目录存在
2. `ExamplePlugin`实现`PluginInterface`
3. 插件可以正确加载和卸载
4. 示例代码可运行

**预期工作量**：0.5人天

---

### 任务4.3：更新文档和最终测试

**需要更新的文件**：
- `README.md`（如果存在）
- `src/yoga_next/core/__init__.py`

**具体步骤**：

1. 更新`src/yoga_next/core/__init__.py`，添加新模块导出：
   ```python
   # 添加
   from .plugin_system import PluginManager, PluginInterface
   
   __all__.extend(['PluginManager', 'PluginInterface'])
   ```

2. 创建插件开发文档`docs/plugin_development.md`：
   - 插件接口说明
   - 开发示例
   - 注册流程

3. 运行所有测试确保系统正常

4. 创建最终测试报告

**最终测试清单**：

- [ ] 运行单元测试：`pytest src/yoga_next/tests/unit/ -v`
- [ ] 运行集成测试：`pytest src/yoga_next/tests/integration/ -v`
- [ ] 测试导入：`python -c "from yoga_next.core import *"`
- [ ] 测试配置加载
- [ ] 测试事件总线
- [ ] 测试Agent执行

**验收标准**：

1. 所有单元测试通过
2. 所有集成测试通过
3. 文档更新完成
4. 系统可正常运行

**预期工作量**：0.5人天

---

## 总体检查清单

在开始每个任务前，请确认：

- [ ] 理解任务目标和验收标准
- [ ] 已阅读相关原始文件
- [ ] 已查看refactor.md中的代码模板
- [ ] 已准备测试环境

在完成每个任务后，请确认：

- [ ] 代码文件已创建/修改
- [ ] 单元测试已编写并通过
- [ ] 代码符合项目规范
- [ ] 已更新相关导入

## 依赖关系

```
任务1.1 (创建core目录)
    │
    ├── 任务1.2 (PathResolver)
    │       └── 任务1.5 (单元测试)
    │
    ├── 任务1.3 (ActionRegistry)
    │       └── 任务1.5 (单元测试)
    │
    ├── 任务1.4 (EnvironmentFactory)
    │       └── 任务1.5 (单元测试)
    │
    └── 任务2.1 (Config)
            │
            ├── 任务2.2 (EventBus)
            │       └── 任务2.4 (集成测试)
            │
            └── 任务2.3 (更新agent_service)
                    └── 任务2.4 (集成测试)

任务3.1 (AgentCore)
    │
    ├── 任务3.2 (AgentExecutor)
    │       └── 任务3.4 (适配器)
    │
    └── 任务3.3 (AgentDisplay)
            └── 任务3.4 (适配器)

任务4.1 (PluginSystem)
    │
    ├── 任务4.2 (示例插件)
    │
    └── 任务4.3 (最终测试)
```

---

## 注意事项

1. **向后兼容**：所有修改必须保持原有API不变
2. **渐进式迁移**：每个任务完成后系统应该仍能正常运行
3. **测试驱动**：先写测试，再实现功能
4. **文档更新**：代码即文档，确保注释完整
5. **代码风格**：遵循项目现有风格
