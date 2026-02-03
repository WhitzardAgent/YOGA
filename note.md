# 架构分析笔记

## 项目概述

这是一个基于LLM的智能Agent框架，支持多种环境和动作空间的灵活组合。主要用于科学论文编辑、研究分析、LaTeX文档处理等场景。

## 核心模块分析

### 1. Agent模块 (agent.py - 465行)

**职责**：
- 任务执行主循环
- 内存管理
- 动作执行
- 思考空间管理
- 显示渲染

**关键组件**：
- `Agent`类：核心执行器
- `YogDisplay`类：Rich终端显示
- `ThinkingSpace`类：顺序思考支持

**观察到的特点**：
- 单一大型类承担过多职责
- 硬编码的ThinkingSpace依赖
- 动作白名单直接嵌入execute方法
- 大量UI渲染逻辑与核心逻辑耦合

### 2. 配置模块 (agent_config.py - 30行)

**简单配置类**：
- API基础URL
- 模型名称
- API密钥
- YAML加载

**问题**：
- 缺乏环境变量支持
- 配置验证逻辑简单
- 不支持配置继承/覆盖

### 3. 服务模块 (agent_service.py - 505行)

**FastAPI服务**：
- 任务执行端点
- 事件流
- 审批工作流

**观察**：
- 与Agent类紧耦合
- 硬编码的Electron环境和GlimActionSpace
- 审批逻辑嵌入服务层

### 4. 动作空间系统 (actions/)

**基类设计**：
- `ActionSpace`抽象基类
- 动态能力生成
- `UnionActionSpace`组合支持

**现有实现**：
- `ControlActionSpace` - done动作
- `ThinkingActionSpace` - 顺序思考
- `EditActionSpace` - 文件编辑
- `GlimAppActionSpace` - Glim应用集成
- `LocalActionSpace` - 本地环境
- `ResearchActionSpace` - 研究工具
- `LatexEditorActionSpace` - LaTeX编辑
- `RemoteServerSpace` - 远程服务器

**重复代码模式**：
- 每个ActionSpace都有`_get_workspace_root()`方法
- 每个ActionSpace都有`_resolve_path()`方法
- 白名单检查重复实现

### 5. 环境系统 (environments/)

**基类设计**：
- `Environment`抽象基类
- 状态管理
- 观察获取

**现有实现**：
- `LocalCondaEnvironment` - 本地Conda环境
- `ElectronAppEnv` - Electron应用环境
- `RemoteServerEnvironment` - 远程服务器
- `JupyterNotebookEnvironment` - Jupyter环境

**问题**：
- `_BashSession`类嵌入local_env.py
- 路径验证逻辑重复
- 桥接模式实现分散

### 6. 记忆系统 (memory.py, hm.py)

**短期记忆**：
- `Memory`类：消息队列
- 工作内存管理
- 动作历史

**长期记忆**：
- `MemoryChunk`类：记忆块
- `MemoryStream`类：流式存储
- JSONL持久化

### 7. 模型包装器 (model.py - 136行)

**功能**：
- OpenAI客户端封装
- 重试机制(tenacity)
- 简单推理接口

### 8. 提示词管理 (prompts.py - 178行)

**功能**：
- `PromptFactory`类
- 角色定义
- 动态提示组装

### 9. 工具函数 (utils.py - 683行)

**功能**：
- 日志系统
- JSON解析
- 文件操作
- 代码高亮
- Rich显示组件

**问题**：
- YogDisplay类过大
- 混合了UI和业务逻辑
- 大量静态方法

## 架构问题识别

### 1. 职责边界模糊

**Agent类承担过多职责**：
- 核心执行逻辑
- UI渲染
- 思考空间管理
- 动作白名单
- 状态管理

**建议**：
- 拆分Agent类为多个专职类
- 引入执行策略模式
- UI与核心逻辑分离

### 2. 重复代码模式

**路径解析重复**：
- `_get_workspace_root()`在5个ActionSpace中重复
- `_resolve_path()`在5个ActionSpace中重复
- 权限验证逻辑重复

**白名单检查重复**：
- 每个ActionSpace的execute方法都有白名单检查
- 应该在基类或装饰器中统一处理

**建议**：
- 提取公共路径处理模块
- 创建路径处理mixin或基类
- 使用装饰器统一白名单处理

### 3. 依赖关系混乱

**硬编码依赖**：
- Agent中硬编码ThinkingSpace
- AgentService中硬编码ElectronAppEnv和GlimAppActionSpace
- RemoteServerSpace中硬编码AgentBridge

**建议**：
- 使用依赖注入
- 创建工厂模式
- 引入配置驱动

### 4. 配置系统薄弱

**当前问题**：
- 配置类过于简单
- 环境变量支持不足
- 缺少配置验证

**建议**：
- 增强配置验证
- 添加环境变量支持
- 实现配置分层

### 5. 扩展点不足

**当前缺少**：
- 动作注册机制
- 环境工厂
- 插件系统
- 事件系统

**建议**：
- 添加注册表模式
- 实现工厂模式
- 添加生命周期钩子

### 6. 测试困难

**问题**：
- Agent类过大导致单元测试困难
- UI逻辑与核心逻辑耦合
- 缺少接口抽象

**建议**：
- 拆分Agent类
- 引入接口隔离
- 添加测试基础设施

## 关键改进建议

### 优先级1：高内聚低耦合

1. 拆分Agent类为：
   - `AgentCore`：核心执行逻辑
   - `AgentExecutor`：执行策略
   - `AgentDisplay`：UI渲染
   - `AgentState`：状态管理

2. 创建路径处理模块：
   - `PathResolver`类
   - `WorkspaceManager`类

3. 统一白名单处理：
   - `ActionRegistry`类
   - `WhitelistMiddleware`类

### 优先级2：可扩展性

1. 实现插件系统：
   - `PluginInterface`
   - `PluginManager`
   - 钩子机制

2. 添加工厂模式：
   - `ActionSpaceFactory`
   - `EnvironmentFactory`
   - `AgentFactory`

3. 实现事件系统：
   - `EventBus`
   - 事件类型定义
   - 订阅/发布机制

### 优先级3：配置增强

1. 增强配置验证
2. 添加环境变量支持
3. 实现配置分层

### 优先级4：测试友好

1. 添加接口抽象
2. 依赖注入容器
3. Mock基础设施

## 重要代码片段

### Agent.execute主循环 (agent.py:281-296)

```python
async def execute(self, task: Task, max_steps=100):
    self.task = task
    self.final_result = None
    
    if self.display:
        self.display.render_planning(task.instruction)
    
    thought_guidance = (
        "Since this is a new task, please start by using sequential_thinking "
        "to analyze the requirements and plan your approach."
    )
    self._add_to_memory_stream(task.task_id, 0, "guidance", {"message": thought_guidance})
    
    result = await self.execute_single_task(task, task_idx=-1, max_steps=max_steps)
    
    return self.final_result
```

### ActionSpace基类 (base.py:86-110)

```python
class ActionSpace(ABC):
    def __init__(self, action_space_name: str, env: Environment):
        self.env = env
        self.action_space_name = action_space_name
        self._capabilities: Dict[str, Any] = {}
        self._generated = False

    def _generate_capabilities(self) -> Dict[str, Any]:
        """Dynamically generate capabilities from _handle_* methods."""
        capabilities = {}
        for name, method in inspect.getmembers(self, predicate=inspect.ismethod):
            if name.startswith("_handle_"):
                action_name = name[len("_handle_"):]
                capabilities[action_name] = _generate_tool_schema(method)
        return capabilities
```

### 路径解析重复代码 (glim_app_action_space.py:45-67)

```python
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
    # ...路径处理逻辑
```

## 下一步行动

1. 完善note.md记录所有发现
2. 编写refactor.md详细改进方案
3. 制定实施优先级和时间表
4. 创建原型验证关键改进点
