import asyncio
import os
import sys
import argparse
from pathlib import Path

# 确保导入路径正确
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
    # 1. 验证并初始化论文路径
    paper_abs_path = Path(paper_path_str).resolve()
    if not paper_abs_path.exists():
        log_error(f"Paper not found: {paper_abs_path}")
        return

    workspace = paper_abs_path.parent
    paper_name = paper_abs_path.name

    # 2. 环境配置
    local_env_config = {
        'env_name': 'yoga_research_env',
        'workspace_root': str(workspace)
    }

    # 这里的 config_path 请修改为你本地真实的路径
    config_path = '/inspire/hdd/global_user/25015/YOGA-Next/configs/config_local.yaml'
    agent_config = AgentConfig.from_yaml(config_path)

    env = LocalCondaEnvironment(local_env_config)
    
    # 3. 实例化 ResearchActionSpace
    research_space = ResearchActionSpace('research', env)
    
    # 4. 深度思想蒸馏指令：明确四维度提取目标
    instruction = f"""
    你现在的身份是顶级 AI 研究员。请对当前目录下的论文文件 '{paper_name}' 进行深度思想建模。
    你需要利用工具进行多次探测，最终在 research_notebook.jsonl 中产出用于 SFT 的“思想骨架”。
    
    你的探测流应包含：
    1. 获取大纲并定位 Methodology 与 Experiments。
    2. 扫描 Insight，识别作者观察到的“核心冲突”与“范式转变点”。
    3. 提取核心公式，并将其背后的“逻辑算子”抽象出来。
    4. 提取实验表格，理解作者如何设计对比来“证伪”或“证实”其 Hypothesis。
    
    最后，在 notebook 中记录如下结构的 JSON 笔记：
    {{
      "problem_formulation": "作者如何定义问题？",
      "intuition_heuristic": "作者解决问题的灵感直觉是什么？",
      "algorithmic_primitives": "核心算法逻辑的原子组合是什么？",
      "validation_logic": "实验设计的核心逻辑范式是什么？"
    }}
    完成提炼后调用 done。
    """
    
    task = Task(task_id=f"distill_{paper_abs_path.stem}", instruction=instruction)
    agent = Agent(agent_config=agent_config, action_spaces=[research_space])
    
    log_info(f"🧬 Starting Backbone Distillation for: {paper_name}")

    try:
        # 执行任务：Agent 会根据指令多次调用 research 空间的方法
        result = await agent.execute(task)
        log_info(f"✅ Distillation Finished. Result: {result}")
        
        # 物理检查产出
        notebook_path = workspace / "research_notebook.jsonl"
        if notebook_path.exists():
            log_info(f"✨ Successfully generated SFT data at: {notebook_path}")
        
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