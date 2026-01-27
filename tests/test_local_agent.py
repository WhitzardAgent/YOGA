import asyncio
import os
import sys
import signal
import time
from pathlib import Path

# 确保项目根目录在 path 中
root_path = os.path.dirname(os.path.abspath(__file__))
if root_path not in sys.path:
    sys.path.insert(0, root_path)

from yoga_next.environments import LocalCondaEnvironment
from yoga_next.actions import LocalActionSpace
from yoga_next.agent_config import AgentConfig
from yoga_next.agent import Agent
from yoga_next.tasks import Task
from yoga_next.utils import log_info, log_error

# 1. 配置准备
workspace = Path("./yoga_workspace").resolve()
workspace.mkdir(exist_ok=True)

local_env_config = {
    'env_name': 'yoga_dev_env',
    'python_version': '3.10',
    'workspace_root': str(workspace)
}

# 假设你已经准备好了基础配置文件
# agent_config = AgentConfig.from_yaml('configs/config_base.yaml')

async def run_local_agent_test():
    # 2. 初始化环境 (Conda)
    env = LocalCondaEnvironment(local_env_config)
    
    # 3. 初始化 ActionSpace (挂载到同一个 Env)
    # 这里的 LocalActionSpace 应该是我们重构后的版本
    local_action_space = LocalActionSpace('local_conda_space', env)
    
    # 4. 加载任务
    # 假设任务是：创建一个 py 文件并运行它，检查输出
    task = Task(
        task_id="local_smoke_test_001",
        instruction="请在当前目录下创建一个名为 test_script.py 的文件，写入打印 'Hello from Yoga' 的代码，然后运行它。"
    )

    # 5. 初始化 Agent
    agent = Agent(
        agent_config=agent_config,
        action_space=local_action_space  # 传入我们的 ActionSpace
    )
    
    # 实验数据保存路径
    exp_file_path = f"exp_bank/{task.task_id}_{int(time.time())}.jsonl"
    os.makedirs("exp_bank", exist_ok=True)

    log_info(f"Starting Task: {task.task_id}")
    
    try:
        # 6. 执行任务循环 (Thought -> Action -> Observation)
        result = await agent.execute(task)
        
        log_info(f"Task Completed. Result: {result}")
        agent.dump(exp_file_path)
        return result
        
    except Exception as e:
        log_error(f"Agent failed: {e}")
        agent.dump(exp_file_path)
        raise
    finally:
        # 7. 清理环境（如果需要）
        # await env.close()
        pass

if __name__ == "__main__":
    asyncio.run(run_local_agent_test())