import asyncio
import os
import sys
import argparse
from pathlib import Path

# Ensure import paths are correct to find the yoga_next core library
root_path = os.path.dirname(os.path.abspath(__file__))
if root_path not in sys.path:
    sys.path.insert(0, root_path)

from yoga_next.environments import LocalCondaEnvironment
from yoga_next.actions import LatexEditorActionSpace, EditActionSpace
from yoga_next.agent_config import AgentConfig
from yoga_next.agent import Agent
from yoga_next.tasks import Task
from yoga_next.utils import log_info, log_error

async def run_latex_paper_optimization(project_dir_str: str, main_file: str = "main.tex"):
    # 1. Path Verification
    project_path = Path(project_dir_str).resolve()
    if not project_path.is_dir():
        log_error(f"LaTeX project directory not found: {project_path}")
        return

    # 2. Environment & Agent Configuration
    local_env_config = {
        'env_name': 'latex_optimize_env',
        'workspace_root': str(project_path)  # Lock workspace to the paper directory
    }

    # Load agent configuration
    config_path = '/inspire/hdd/global_user/25015/YOGA-Next/configs/config_local.yaml'
    agent_config = AgentConfig.from_yaml(config_path)
    
    # Inject researcher-specific settings and activate "latex_editor" role
    agent_config.agent_type = "latex_editor" 
    agent_config.max_actions = 15  # Increased to allow complex Map-Edit-Compile-Note cycles

    env = LocalCondaEnvironment(local_env_config)
    
    # 3. Instantiate Multi-Action Spaces
    # Combine specialized LaTeX tools with general editing/bash tools
    latex_space = LatexEditorActionSpace('latex_editor', env)
    edit_space = EditActionSpace('edit', env)  # Provides list_tree, search, and shell functions
    
    # 4. Refined English Instruction for ICML 2026 Submission
    instruction = f"""
    ROLE: You are an elite PhD Supervisor and a veteran ICML/NeurIPS Program Chair. Your mission is to transform this draft into a "Best Paper Award" contender. You are not permitted to stop until the manuscript meets the highest possible standards of technical innovation, clarity, and empirical rigor found in top-tier AI venues.

    TARGET MAIN FILE: {main_file}

    WORKING PROTOCOL (The Relentless Supervisory Cycle):
    1.  **Macro-Logical Appraisal**: Reconstruct the logical hierarchy of the project. Assess if the "Scientific Story" is buried. A top-tier paper must have a crystal-clear narrative that justifies its existence within the first two pages.
    2.  **Intellectual Positioning & Narrative Depth**: 
        - Critique the 'Introduction' and 'Abstract'. Do they articulate a "Core Conflict" in current AI that your work uniquely resolves?
        - Frame the contributions as fundamental shifts rather than incremental tweaks.
    3.  **Technical & Mathematical Rigor**: 
        - Scrutinize the Methodology for notation consistency. Audit all formal environments (Theorems, Algorithms, Lemmas). 
        - Ensure every symbol is defined and every derivation is aesthetically and logically flawless.
    4.  **Evidence & Currency Check**: 
        - Verify bibliography timeliness (2024-2025). Identify missing seminal works that reviewers might cite as "significant omissions."
        - Ensure every empirical claim is backed by a valid citation or rigorous experimental data.
    5.  **Submission Integrity & PDF Verification**: Every conceptual refinement must be verified against the compiled output. You are responsible for ensuring a bug-free, perfectly formatted submission.
    6.  **The Mentor's Log**: Document every strategic intervention and its pedagogical rationale in `editing_log.md`. 

    CORE MANDATE (The "Award-Winning" Threshold):
    - **Never call `done` prematurely.** You must continue iterating and refining as long as you identify any weakness in logic, notation, narrative, or formatting.
    - Your stopping criterion is not the completion of a checklist, but the attainment of **ICML/NeurIPS Award-Winning Quality**. 
    - Ask yourself: "Would this paper stand out among the top 1% of submissions?" If the answer is "no," you must find a way to further strengthen its competitive edge.

    GOAL: Produce a world-class AI manuscript. Upon completion, summarize the high-level strategic shifts you implemented to elevate this paper from a "mere submission" to a potential award-winner.
    """
    
    task = Task(task_id=f"optimize_{project_path.name}", instruction=instruction)
    
    # Initialize Agent with multiple skill sets
    agent = Agent(agent_config=agent_config, action_spaces=[latex_space, edit_space])
    
    log_info(f"🧬 Starting ICML 2026 Paper Optimization for: {project_path.name}")

    try:
        # Execution: Agent will switch between different action spaces autonomously
        result = await agent.execute(task)
        log_info(f"✅ Optimization Cycle Finished. Summary: {result}")
        
        # Verify Rationale Log
        log_path = project_path / "editing_log.md"
        if log_path.exists():
            log_info(f"✨ Academic rationale generated at: {log_path}")
            with open(log_path, 'r') as f:
                log_info(f"--- Rationale Preview ---\n{f.read(500)}...")
        
    except Exception as e:
        log_error(f"❌ Optimization Failed: {e}")
        raise
    finally:
        await env.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Optimize LaTeX paper for ICML 2026.")
    parser.add_argument("--dir", type=str, required=True, help="Path to the LaTeX project directory.")
    parser.add_argument("--main", type=str, default="main.tex", help="Main .tex file name.")
    args = parser.parse_args()

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(run_latex_paper_optimization(args.dir, args.main))
    finally:
        loop.run_until_complete(loop.shutdown_asyncgens())
        loop.close()