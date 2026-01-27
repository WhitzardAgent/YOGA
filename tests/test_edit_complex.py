import asyncio
import os
import sys
import time
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

async def run_complex_edit_test():
    # 1. 初始化环境
    workspace = Path("./yoga_workspace_complex").resolve()
    workspace.mkdir(exist_ok=True)

    local_env_config = {
        'env_name': 'yoga_dev_env',
        'python_version': '3.10',
        'workspace_root': str(workspace)
    }

    # 请确保该路径指向你正确的配置文件
    config_path = '/inspire/hdd/global_user/25015/YOGA-Next/configs/config_local.yaml'
    agent_config = AgentConfig.from_yaml(config_path)

    env = LocalCondaEnvironment(local_env_config)
    
    # 2. 实例化 ActionSpaces
    local_conda_space = LocalActionSpace('local_shell', env)
    edit_space = EditActionSpace('edit', env) 
    
    # 3. 极其复杂的指令：
    # 涵盖了：创建、跨文件引用、故意犯错、根据反馈纠错、重构、展示树状结构
    instruction = """
    你现在需要完成一个名为 'MathProject' 的重构任务：
    1. 在 'src/core/' 目录下创建 'calculator.py'，实现一个 Calculator 类，包含一个 add(self, a, b) 方法。
    2. 在根目录下创建 'main.py'，从 'src.core.calculator' 导入 Calculator 类，实例化并打印 add(10, 5) 的结果。
    3. 运行 'main.py' 确保一切正常。
    4. 需求变更：
       a. 使用 `insert` 在 'calculator.py' 的 add 方法之后添加一个 subtract(self, a, b) 方法。
       b. 使用 `str_replace` 修改 'main.py'，增加对 subtract(20, 8) 的调用，但在修改时请“故意”留一个语法错误（比如在 print 语句中少写一个括号）。
    5. 当你收到语法错误反馈时，利用反馈中的 line_number 和 diagnostic 信息自动修复 'main.py'。
    6. 使用 `list_tree` 查看最终的项目结构。
    7. 再次运行 'main.py' 验证最终逻辑。
    8. 完成后调用 done。
    """
    
    task = Task(task_id="complex_refactor_test_002", instruction=instruction)

    # 4. 初始化 Agent
    agent = Agent(
        agent_config=agent_config,
        action_spaces=[local_conda_space, edit_space]
    )
    
    log_info(f"🚀 Starting Complex E2E Test: {task.task_id}")
    exp_file_path = f"exp_bank/{task.task_id}_{int(time.time())}.jsonl"
    os.makedirs("exp_bank", exist_ok=True)

    try:
        # 执行任务
        result = await agent.execute(task)
        log_info(f"✅ Agent Execution Finished. Result: {result}")
        
        # 物理验证逻辑
        calc_file = workspace / "src" / "core" / "calculator.py"
        main_file = workspace / "main.py"
        
        if calc_file.exists() and "subtract" in calc_file.read_text():
            log_info("验证 1: calculator.py 重构成功（已包含 subtract）。")
        else:
            log_error("验证 1: calculator.py 验证失败。")

        if main_file.exists():
            content = main_file.read_text()
            # 检查是否修复了括号错误
            if content.count('(') == content.count(')'):
                log_info("验证 2: main.py 语法错误已自我修复。")
            else:
                log_error("验证 2: main.py 仍然存在语法错误。")

        agent.dump(exp_file_path)
        
    except Exception as e:
        log_error(f"❌ Test Failed: {e}")
        agent.dump(exp_file_path)
        raise
    finally:
        await env.close()

if __name__ == "__main__":
    # 使用你推荐的优雅退出逻辑
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(run_complex_edit_test())
    finally:
        loop.run_until_complete(loop.shutdown_asyncgens())
        loop.run_until_complete(asyncio.sleep(0.1))
        loop.close()