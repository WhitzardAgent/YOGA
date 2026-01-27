import asyncio
import os
import sys
import signal
import time
from pathlib import Path

root_path = os.path.dirname(os.path.abspath(__file__))
if root_path not in sys.path:
    sys.path.insert(0, root_path)

from yoga_next.environments import LocalCondaEnvironment
from yoga_next.actions import LocalActionSpace
from yoga_next.agent_config import AgentConfig
from yoga_next.agent import Agent
from yoga_next.tasks import Task
from yoga_next.utils import log_info, log_error

workspace = Path("./yoga_workspace").resolve()
workspace.mkdir(exist_ok=True)

local_env_config = {
    'env_name': 'yoga_dev_env',
    'python_version': '3.10',
    'workspace_root': str(workspace)
}

async def run_local_agent_test():
    env = LocalCondaEnvironment(local_env_config)
    
    local_action_space = LocalActionSpace('local_conda_space', env)
    
    task = Task(
        task_id="local_smoke_test_001",
        instruction="请在当前目录下创建一个名为 test_script.py 的文件，写入打印 'Hello from Yoga' 的代码，然后运行它，最后调用 done 标记任务完成。"
    )

    agent_config = AgentConfig(
        api_base_url="https://api.openai.com/v1",
        model_name="gpt-4",
        api_key=os.getenv("OPENAI_API_KEY", "")
    )
    
    agent = Agent(
        agent_config=agent_config,
        action_spaces=[local_action_space]
    )
    
    exp_file_path = f"exp_bank/{task.task_id}_{int(time.time())}.jsonl"
    os.makedirs("exp_bank", exist_ok=True)

    log_info(f"Starting Task: {task.task_id}")
    
    try:
        result = await agent.execute(task)
        
        log_info(f"Task Completed. Final Result: {result}")
        agent.dump(exp_file_path)
        return result
        
    except Exception as e:
        log_error(f"Agent failed: {e}")
        agent.dump(exp_file_path)
        raise
    finally:
        await env.close()

if __name__ == "__main__":
    asyncio.run(run_local_agent_test())
