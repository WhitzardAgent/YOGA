import asyncio
import os
import sys
import signal
import time

# Get the absolute path to the 'yoga-next' directory
root_path = os.path.dirname(os.path.abspath(__file__))
if root_path not in sys.path:
    sys.path.insert(0, root_path)

from yoga_next.environments import RemoteServerEnvironment
from yoga_next.actions import RemoteServerSpace
from yoga_next.agent_config import AgentConfig
from yoga_next.agent import Agent
from yoga_next.tasks import Task
from yoga_next.utils import log_info, log_error

remote_server_config = {
    'ssh_host': '36.103.236.220',  # Replace with your server address
    'ssh_username': 'ubuntu',  # Replace with your username
    'ssh_password': 'g0y.IRZ6sxdyNhmu',  # Replace with your password
}

agent_config = AgentConfig.from_yaml('configs/config_base.yaml')


async def exec_async():
    env = RemoteServerEnvironment(
        remote_server_config
    )
    task = Task.from_yaml('task_examples/task_terminal_001/config.yaml')
    await env.setup(local_path='/Users/morinop/coding/yoga-next/task_examples/task_terminal_001/assets')
    remote_server_agent_space = RemoteServerSpace('remote_server_env', env)
    toolkit_str = remote_server_agent_space.get_action_space_description()
    log_info("Toolkit Str: \n"+toolkit_str)
    
    agent = Agent(agent_config=agent_config,
                  action_space=remote_server_agent_space)
    
    # Generate the experiment file path
    timestamp = int(time.time())
    task_id = task.task_id
    exp_file_path = f"exp_bank/{task_id}_{timestamp}.exp.jsonl"
    
    # Register signal handler for graceful shutdown
    def signal_handler(*args):
        log_info("Received interrupt signal. Dumping memory stream...")
        agent.dump(exp_file_path)
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    
    try:
        result = await agent.execute(task)
        # After execution, dump the memory stream
        agent.dump(exp_file_path)
        return result
    except Exception as e:
        log_error(f"Error during agent execution: {e}")
        agent.dump(exp_file_path)
        raise


if __name__ == "__main__":
    asyncio.run(
        exec_async()
    )