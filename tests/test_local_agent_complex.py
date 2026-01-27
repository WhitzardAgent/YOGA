import asyncio
import os
import sys
import time
from pathlib import Path

# 设置路径
root_path = os.path.dirname(os.path.abspath(__file__))
if root_path not in sys.path:
    sys.path.insert(0, root_path)

from yoga_next.environments import LocalCondaEnvironment
from yoga_next.actions import LocalActionSpace
from yoga_next.agent_config import AgentConfig
from yoga_next.agent import Agent
from yoga_next.tasks import Task
from yoga_next.utils import log_info, log_error

async def run_complex_agent_test():
    workspace = Path("./yoga_complex_workspace").resolve()
    workspace.mkdir(exist_ok=True)

    local_env_config = {
        'env_name': 'yoga_complex_env',
        'python_version': '3.10',
        'workspace_root': str(workspace)
    }
    
    # 请确保路径正确
    config_path = '/inspire/hdd/global_user/25015/YOGA-Next/configs/config_local.yaml'
    agent_config = AgentConfig.from_yaml(config_path)

    env = LocalCondaEnvironment(local_env_config)
    local_action_space = LocalActionSpace('local_conda_space', env)

    # 复杂的任务描述
    instruction = (
        "1. 调研环境：检查当前目录并确认是否可以安装 requests 库。\n"
        "2. 配置文件：创建 config.json，包含内容 {'url': 'https://httpbin.org/delay/1'}。\n"
        "3. 核心功能：编写 monitor.py 抓取该 URL 的响应时间，并将 [timestamp, status_code, elapsed] 存入 monitor_log.csv。\n"
        "4. 数据分析：编写 analyzer.py 读取 csv 并计算平均 elapsed 时间。\n"
        "5. 执行流程：运行 monitor.py 3次（确保产生足够数据），最后运行 analyzer.py 输出结果。\n"
        "注意：在每一步关键操作前，请先使用 sequential_thinking 规划逻辑。"
    )

    task = Task(
        task_id="complex_workflow_001",
        instruction=instruction
    )

    agent = Agent(
        agent_config=agent_config,
        action_spaces=[local_action_space]
    )
    
    exp_file_path = f"exp_bank/{task.task_id}_{int(time.time())}.jsonl"
    os.makedirs("exp_bank", exist_ok=True)

    log_info(f"🚀 Starting Complex Task: {task.task_id}")
    
    try:
        # 这里会触发 Agent 的 sequential_thinking 链条
        result = await agent.execute(task, max_steps=50) 
        
        log_info(f"✅ Task Completed. Summary: {result}")
        agent.dump(exp_file_path)
        
    except Exception as e:
        log_error(f"❌ Agent failed: {e}")
        agent.dump(exp_file_path)
        raise
    finally:
        await env.close()

if __name__ == "__main__":
    asyncio.run(run_complex_agent_test())