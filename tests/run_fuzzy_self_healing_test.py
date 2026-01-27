import asyncio
import os
import sys
import time
import shutil
from pathlib import Path

# 确保导入路径正确
root_path = os.path.dirname(os.path.abspath(__file__))
if root_path not in sys.path:
    sys.path.insert(0, root_path)

from yoga_next.environments import LocalCondaEnvironment
from yoga_next.actions import LocalActionSpace, EditActionSpace 
from yoga_next.agent_config import AgentConfig
from yoga_next.agent import Agent
from yoga_next.tasks import Task
from yoga_next.utils import log_info, log_error

async def run_fuzzy_self_healing_test():
    # 1. 初始化工作区
    workspace = Path("./yoga_workspace_fuzzy").resolve()
    if workspace.exists():
        shutil.rmtree(workspace)
    workspace.mkdir(exist_ok=True)

    # --- 制造一个“破碎”的项目初始状态 ---
    # 创建一个引用了不存在模块的入口文件
    (workspace / "app.py").write_text("""
from core.processor import get_secret_code

def start():
    print("Checking system status...")
    # 这里会因为找不到 core 目录或 processor 模块而报错
    code = get_secret_code("data/token.txt")
    print(f"System Authorized. Code: {code}")

if __name__ == "__main__":
    start()
""")
    # 注意：故意不创建 core/ 目录，也不创建 data/token.txt
    # ----------------------------------------

    # 2. 环境配置
    local_env_config = {
        'env_name': 'yoga_dev_env',
        'python_version': '3.10',
        'workspace_root': str(workspace)
    }

    config_path = '/inspire/hdd/global_user/25015/YOGA-Next/configs/config_local.yaml'
    agent_config = AgentConfig.from_yaml(config_path)

    env = LocalCondaEnvironment(local_env_config)
    
    # 3. 实例化 ActionSpaces
    local_conda_space = LocalActionSpace('local_shell', env)
    edit_space = EditActionSpace('edit', env) 
    
    # 4. 模糊指令：只给目标，不给步骤
    # 强制 Agent 必须使用 list_tree 探测，使用 run_shell 报错，使用 create 修复
    instruction = """
    当前工作区有一个名为 app.py 的程序，但它目前由于文件缺失无法运行。
    你的任务是：
    1. 自主诊断程序运行失败的原因。
    2. 根据错误提示，补齐所有缺失的 Python 模块和数据文件。
    3. 要求：'core/processor.py' 中的 get_secret_code 函数应该读取文件并返回其内容的长度。
    4. 'data/token.txt' 文件的内容请随意设置。
    5. 修复后，确保执行 python app.py 能够成功打印出授权代码。
    6. 任务完成后，展示最终的项目目录树并调用 done。
    """
    
    task = Task(task_id="fuzzy_self_healing_003", instruction=instruction)

    # 5. 初始化 Agent
    agent = Agent(
        agent_config=agent_config,
        action_spaces=[local_conda_space, edit_space]
    )
    
    log_info(f"🚀 Starting Fuzzy Self-Healing Test: {task.task_id}")
    exp_file_path = f"exp_bank/{task.task_id}_{int(time.time())}.jsonl"
    os.makedirs("exp_bank", exist_ok=True)

    try:
        # 执行任务：观察 Agent 如何从报错中自我恢复
        result = await agent.execute(task)
        
        log_info(f"✅ Agent Task Result: {result}")
        
        # 物理验证逻辑：检查 Agent 是否创建了层级目录
        processor_path = workspace / "core" / "processor.py"
        token_path = workspace / "data" / "token.txt"
        
        if processor_path.exists() and token_path.exists():
            log_info("验证成功：Agent 自主创建了缺失的深层目录和文件。")
        else:
            log_error(f"验证失败：文件补全不完整。当前结构：{[str(p.relative_to(workspace)) for p in workspace.rglob('*')]}")

        agent.dump(exp_file_path)
        
    except Exception as e:
        log_error(f"❌ Test Failed: {e}")
        agent.dump(exp_file_path)
        raise
    finally:
        await env.close()

if __name__ == "__main__":
    # 使用优雅的退出逻辑，避免 Event Loop closed 报错
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(run_fuzzy_self_healing_test())
    finally:
        loop.run_until_complete(loop.shutdown_asyncgens())
        loop.run_until_complete(asyncio.sleep(0.1))
        loop.close()