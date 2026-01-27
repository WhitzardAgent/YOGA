# YOGA - 新一代 AI Agent 框架

<p align="center">
  <strong>🚀 具备动态规划、丰富 UI 和自愈能力的智能 Agent 框架</strong>
</p>

<p align="center">
  <a href="#-特性">特性</a> •
  <a href="#-架构设计">架构设计</a> •
  <a href="#-快速开始">快速开始</a> •
  <a href="#-开发者指南">开发者指南</a> •
  <a href="#-动作空间">动作空间</a>
</p>

---

## ✨ 核心特性

### 🔮 动态顺序思考
- **强制首步分析**：每个任务必须以 `sequential_thinking` 开始，进行结构化推理
- **动态重规划**：当遇到错误时，使用 `is_revision=True` 更新计划
- **思维链探索**：在执行动作前探索假设并验证

### 🎨 丰富交互显示
- **实时进度追踪**：使用 Rich 库实现步骤可视化
- **色彩编码输出**：Shell 命令、代码块和 diff 的语法高亮
- **结构化观察**：支持语言感知的 Markdown 代码块输出
- **树形可视化**：Git 风格的目录树展示

### 🛡️ 企业级可靠性
- **超时保护**：为每个动作配置超时时间（默认 60s，长操作最多 300s）
- **自愈能力**：模糊字符串匹配为失败操作提供修正建议
- **语法验证**：Python 文件在写入前使用 `ast.parse()` 验证
- **路径安全**：基于工作区的路径解析防止越权访问

### 📊 记忆与轨迹
- **长期记忆**：跨任务步骤的持久化工作记忆
- **轨迹日志**：JSONL 格式的执行历史，用于调试和回放
- **思维追踪**：带修订标记的推理进度可视化

### 🔌 模块化架构
- **ActionSpace 模式**：通过 `UnionActionSpace` 组合多个动作空间
- **环境抽象**：支持本地、Jupyter 和远程服务器环境
- **自动生成模式**：通过 `inspect` 从文档字符串生成工具描述

---

## 🏗️ 架构设计

```
┌─────────────────────────────────────────────────────────────────┐
│                         YOGA Agent                               │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐ │
│  │   规划器    │  │   记忆      │  │      模型 (LLM)         │ │
│  └─────────────┘  └─────────────┘  └─────────────────────────┘ │
├─────────────────────────────────────────────────────────────────┤
│                    统一动作空间                                  │
│  ┌───────────┐ ┌───────────┐ ┌───────────┐ ┌───────────────┐  │
│  │  控制空间 │ │ 思考空间  │ │  编辑空间 │ │  本地/远程    │ │
│  └───────────┘ └───────────┘ └───────────┘ └───────────────┘  │
├─────────────────────────────────────────────────────────────────┤
│                    环境层                                       │
│  ┌───────────────┐  ┌─────────────────┐  ┌─────────────────┐   │
│  │ 本地Conda环境 │  │ Jupyter笔记本   │  │ 远程服务器环境  │   │
│  └───────────────┘  └─────────────────┘  └─────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

### 核心组件

| 组件 | 用途 |
|------|------|
| `Agent` | 主协调器，具备超时保护和 UI 渲染 |
| `ActionSpace` | 动作实现的基类 |
| `UnionActionSpace` | 动态组合多个动作空间 |
| `Environment` | 文件系统、Shell 和笔记本操作的抽象 |
| `Memory` | 对话上下文的工作记忆 |
| `MemoryStream` | 用于调试的轨迹日志 |

---

## 🚀 快速开始

### 安装

```bash
git clone https://github.com/your-org/yoga-next.git
cd yoga-next
pip install -e .
```

### 基本使用

```python
from yoga_next import Agent, AgentConfig, LocalActionSpace
from yoga_next.environments import LocalCondaEnvironment

# 配置 Agent
config = AgentConfig(
    api_base_url="https://api.openai.com/v1",
    model_name="gpt-4o",
    api_key="your-api-key"
)

# 创建环境和动作空间
env = LocalCondaEnvironment({"workspace_root": "/path/to/workspace"})
action_space = LocalActionSpace("local", env)

# 初始化 Agent
agent = Agent(
    agent_config=config,
    action_spaces=[action_space],
    use_rich_display=True
)

# 执行任务
from yoga_next import Task
task = Task(task_id="example", instruction="分析代码库结构")
result = await agent.execute(task)
```

---

## 💻 开发者指南

### 创建自定义动作空间

```python
from yoga_next.actions import ActionSpace
from typing import Dict, Any

class MyActionSpace(ActionSpace):
    def __init__(self, env=None):
        super().__init__("my_actions", env)

    async def execute(self, action_name: str, param_dict: Dict[str, Any]) -> Dict[str, Any]:
        handler = getattr(self, f"_handle_{action_name}", None)
        if not handler:
            return {"status": "error", "message": f"未知动作: {action_name}"}
        result = await handler(**param_dict)
        return {"status": "success", "output": result}

    async def _handle_my_action(self, param: str) -> Dict[str, Any]:
        """执行自定义动作。

        :param param: 参数描述。
        """
        # 在这里实现你的逻辑
        return {"result": "done"}
```

### 注册到 Agent

```python
from yoga_next import Agent, AgentConfig

agent = Agent(
    agent_config=config,
    action_spaces=[MyActionSpace(env), LocalActionSpace(env)],
    use_rich_display=True
)
```

### 路径安全

所有文件路径自动：
- 相对于 workspace_root 解析
- 验证防止越权访问
- 在 I/O 前转换为绝对路径

```python
# 在 EditActionSpace 处理程序中：
resolved_path = self._resolve_path(path)  # 安全的路径处理
await self.env.read_file(resolved_path)
```

### 记忆流使用

```python
# 启用轨迹日志
agent.dump("/path/to/trajectory.jsonl")

# 回放执行
from yoga_next import MemoryStream
stream = MemoryStream.load("/path/to/trajectory.jsonl")
```

---

## 🔧 动作空间

### EditActionSpace - 高级文件编辑

| 动作 | 描述 |
|------|------|
| `view(path, view_range)` | 查看文件/目录，带行号和语法高亮 |
| `create(path, file_text)` | 创建文件，自动创建父目录 |
| `str_replace(path, old_str, new_str)` | 替换内容，含唯一性检查和 diff 输出 |
| `insert(path, insert_line, new_str)` | 插入行，含 Python 语法验证 |
| `search(path, keyword)` | 基于 grep 的搜索，含结果限制 |
| `list_tree(path, depth)` | 递归目录树可视化 |

### LocalActionSpace - Shell 操作

| 动作 | 描述 |
|------|------|
| `execute_shell(command)` | 在 conda 环境中执行 bash 命令 |
| `run_in_conda_env(command)` | 在指定 conda 环境中运行命令 |
| `read_file(path)` | 读取文件内容 |
| `write_file(path, content)` | 写入文件内容 |
| `list_directory(path, depth)` | 递归列出目录 |
| `exists(path)` | 检查路径是否存在 |

### ThinkingActionSpace - 动态规划

| 动作 | 描述 |
|------|------|
| `sequential_thinking(...)` | 带计划修订支持的结构化推理 |

---

## 🎯 思维协议

每个任务**必须**以 `sequential_thinking` 开始：

```markdown
sequential_thinking(
    thought="分析需求并分解任务",
    thought_number=1,
    total_thoughts=3,
    next_thought_needed=True,
    is_revision=False
)
```

**协议规则：**
1. 新任务的第一个动作 = `sequential_thinking`
2. 遇到错误时：使用 `is_revision=True` 更新计划
3. 只有当计划完善时才设置 `next_thought_needed=False`
4. 连续 5 次失败 → 放弃子任务

---

## 📁 项目结构

```
yoga-next/
├── src/yoga_next/
│   ├── agent.py              # 主 Agent 实现
│   ├── memory.py             # 工作记忆管理
│   ├── model.py              # LLM 接口（含重试逻辑）
│   ├── planner.py            # 任务规划
│   ├── prompts.py            # 系统提示与思维协议
│   ├── utils.py              # 日志、提取、UI 工具
│   ├── hm.py                 # 记忆块定义
│   ├── agent_config.py       # 配置数据类
│   ├── actions/
│   │   ├── base.py           # ActionSpace 基类与模式生成
│   │   ├── edit_action_space.py  # 高级文件编辑
│   │   ├── local_action_space.py # Shell 和文件操作
│   │   ├── thinking.py       # 顺序思考处理器
│   │   ├── control.py        # 任务完成信号
│   │   └── ...               # 其他动作空间
│   ├── environments/
│   │   ├── base.py           # 环境抽象基类
│   │   ├── local_env.py      # 本地 conda 环境
│   │   ├── jupyter_notebook_env.py
│   │   └── remote_server_env.py
│   └── tasks/
│       └── task.py           # 任务定义
├── tests/                    # 测试套件
├── configs/                  # 配置文件
├── task_examples/            # 示例挑战
├── setup.py                  # 包设置
└── README.md                 # 英文文档
└── README_CN.md              # 中文文档
```

---

## 🧪 测试

```bash
# 运行所有测试
python -m pytest tests/ -v

# 运行特定测试
python tests/test_local_agent.py

# 运行模糊自愈测试
python tests/run_fuzzy_self_healing_test.py
```

---

## 📝 开源协议

MIT License

---

<p align="center">
  由 ❤️ 构建
</p>
