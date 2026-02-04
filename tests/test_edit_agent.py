import asyncio
import os
import sys
import time
from pathlib import Path

root_path = os.path.dirname(os.path.abspath(__file__))
if root_path not in sys.path:
    sys.path.insert(0, root_path)

from yoga_next.environments import LocalCondaEnvironment
from yoga_next.actions import EditActionSpace, LocalActionSpace
from yoga_next.agent_config import AgentConfig
from yoga_next.yoga_agent import YogaAgent
from yoga_next.tasks import Task
from yoga_next.utils import log_info, log_error

async def run_edit_agent_test():
    workspace = Path("./yoga_workspace").resolve()
    workspace.mkdir(exist_ok=True)

    local_env_config = {
        'env_name': 'yoga_dev_env',
        'python_version': '3.10',
        'workspace_root': str(workspace)
    }

    agent_config = AgentConfig.from_yaml('/Users/morinop/coding/yoga-next/configs/config_silicon.yaml')

    env = LocalCondaEnvironment(local_env_config)
    
    local_conda_space = LocalActionSpace('local_shell', env)
    edit_space = EditActionSpace('edit', env) 
    
    instruction = """
    请执行以下步骤：
    1. 在当前目录下创建 'math_utils.py'，写入一个名为 'calculate_area' 的函数，但故意留一个拼写错误（比如 print 写成 prrint）。
    2. 使用 edit 空间的 search 功能找到该拼写错误。
    3. 使用 str_replace 功能修正该错误，并增加一行注释。
    4. 运行该文件确保没有语法错误。
    5. 完成后调用 done。
    """
    
    task = Task(task_id="edit_action_test_001", instruction=instruction)

    agent = YogaAgent(
        agent_config=agent_config,
        action_spaces=[local_conda_space, edit_space]
    )
    
    log_info(f"🚀 Starting EditActionSpace E2E Test: {task.task_id}")
    
    exp_file_path = f"exp_bank/{task.task_id}_{int(time.time())}.jsonl"
    os.makedirs("exp_bank", exist_ok=True)

    try:
        result = await agent.execute(task)
        
        log_info(f"✅ Test Completed. Result: {result}")
        agent.dump(exp_file_path)
        
        final_file = workspace / "math_utils.py"
        if final_file.exists():
            content = final_file.read_text()
            if "prrint" not in content and "calculate_area" in content:
                log_info("验证成功：文件内容已正确修正。")
            else:
                log_error("验证失败：文件内容不符合预期。")
        
    except Exception as e:
        log_error(f"❌ Test Failed: {e}")
        agent.dump(exp_file_path)
        raise
    finally:
        await env.close()

if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(run_edit_agent_test())
    finally:
        loop.run_until_complete(loop.shutdown_asyncgens())
        loop.run_until_complete(asyncio.sleep(0.1))
        loop.close()
