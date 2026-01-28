import asyncio
import os
import sys
import argparse
from pathlib import Path

# Ensure import paths are correct
root_path = os.path.dirname(os.path.abspath(__file__))
if root_path not in sys.path:
    sys.path.insert(0, root_path)

from yoga_next.environments import LocalCondaEnvironment
from yoga_next.actions import ResearchActionSpace
from yoga_next.agent_config import AgentConfig
from yoga_next.agent import Agent
from yoga_next.tasks import Task
from yoga_next.utils import log_info, log_error

async def run_research_backbone_distillation(paper_path_str: str):
    # 1. Path Verification
    paper_abs_path = Path(paper_path_str).resolve()
    if not paper_abs_path.exists():
        log_error(f"Paper not found: {paper_abs_path}")
        return

    workspace = paper_abs_path.parent
    paper_name = paper_abs_path.name
    paper_stem = paper_abs_path.stem  # 获取不带扩展名的文件名

    # 2. Environment & Agent Config
    local_env_config = {
        'env_name': 'yoga_research_env',
        'workspace_root': str(workspace)
    }

    # IMPORTANT: Update agent_config to use the "researcher" type
    config_path = '/inspire/hdd/global_user/25015/YOGA-Next/configs/config_local.yaml'
    agent_config = AgentConfig.from_yaml(config_path)
    
    # Inject researcher-specific settings
    agent_config.agent_type = "researcher" 
    agent_config.max_actions = 5  # Allow chaining for Read-Write Coupling

    env = LocalCondaEnvironment(local_env_config)
    research_space = ResearchActionSpace('research', env)
    
    # 3. Refined English Instruction (Principles-Driven)
    # We remove JSON formatting requirements and focus on the "Thought Skeleton"
    instruction = f"""
    OBJECTIVE: Distill the "Thought Skeleton" of the paper '{paper_name}'.
    
    WORKING PROTOCOL:
    1. Mapping: Use `get_outline` to locate critical sections (Methodology, Logic, Experiments).
    2. Synchronous Read-Write: As you use `read_section`, immediately use `append_to_notebook` to record:
       - Problem Formulation: How the conflict is defined.
       - Heuristic Intuition: The core "spark" or "trick" behind the solution.
       - Algorithmic Primitives: The atomic building blocks of the proposed logic.
       - Validation Paradigm: How the hypothesis is stressed and proven.
    3. Structural Evidence: Use `extract_all_tables` to find empirical proof.
    
    FINAL GOAL:
    Before calling `done`, review your research_notes_{paper_stem}.md. Your final response must present 
    a synthesized, hierarchical backbone of the paper's intellectual contribution.
    """
    
    task = Task(task_id=f"distill_{paper_abs_path.stem}", instruction=instruction)
    
    # The Agent will now use PromptFactory internally to load the "researcher" mindset
    agent = Agent(agent_config=agent_config, action_spaces=[research_space])
    
    log_info(f"🧬 Starting Backbone Distillation for: {paper_name}")

    try:
        # Execution Loop
        result = await agent.execute(task)
        log_info(f"✅ Distillation Finished. Summary: {result}")
        
        # Physical Verification of the Markdown Notebook - 使用动态文件名
        notebook_path = workspace / f"research_notes_{paper_stem}.md"
        if notebook_path.exists():
            log_info(f"✨ Successfully generated Thought Skeleton at: {notebook_path}")
            # Optional: Print the first few lines of the notes
            with open(notebook_path, 'r') as f:
                log_info(f"--- Notebook Preview ---\n{f.read(500)}...")
        
    except Exception as e:
        log_error(f"❌ Distillation Failed: {e}")
        raise
    finally:
        await env.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Distill research backbone from a MD paper.")
    parser.add_argument("--paper", type=str, required=True, help="Path to the research paper markdown file.")
    args = parser.parse_args()

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(run_research_backbone_distillation(args.paper))
    finally:
        loop.run_until_complete(loop.shutdown_asyncgens())
        loop.close()
