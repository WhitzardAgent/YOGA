import asyncio
import os
import sys
import time
import base64
import re
from pathlib import Path
from typing import Dict, Any
from openai import OpenAI

# ==========================================
# 1. 项目路径设置
# ==========================================
root_path = os.path.dirname(os.path.abspath(__file__))
if root_path not in sys.path:
    sys.path.insert(0, root_path)

from yoga_next.environments import LocalCondaEnvironment
from yoga_next.actions import LocalActionSpace, ActionSpace, MarkdownActionSpace, EditActionSpace
from yoga_next.agent_config import AgentConfig
from yoga_next.yoga_agent import YogaAgent
from yoga_next.tasks import Task
from yoga_next.utils import log_info, log_error

# ==========================================
# 3. 执行逻辑
# ==========================================
async def run_reconstruction_task():
    # --- 配置区域 ---
    # 指定您的真实工作区路径 (包含 markdown 和 图片)
    workspace_path = Path("./yoga_workspace").resolve()
    # 指定要分析的目标文件 (必须在工作区内)
    target_md_file = "HackTheBox_Walkthrough.md" 
    # ----------------
    
    workspace_path.mkdir(exist_ok=True)
    
    # 检查文件是否存在
    if not (workspace_path / target_md_file).exists():
        log_error(f"❌ Target file not found: {workspace_path / target_md_file}")
        log_info("Please place your markdown file and 'assets' folder in ./yoga_workspace/ first.")
        return

    # 初始化环境
    local_env_config = {
        'env_name': 'yoga_dev_env',
        'python_version': '3.10',
        'workspace_root': str(workspace_path)
    }
    env = LocalCondaEnvironment(local_env_config)

    # 加载 Agent 配置
    # 请根据您的实际路径修改 config_path
    config_path = Path(root_path).parent / 'configs/config_silicon.yaml'
    agent_config = AgentConfig.from_yaml(config_path)

    # 动作空间：Parser (读) + Shell (写/验证)
    md_space = MarkdownActionSpace('md_parser', env)
    local_shell = LocalActionSpace('local_shell', env)
    edit_space = EditActionSpace('edit', env)
    # 定义任务：轨迹重构
    instruction = f"""
        ### 角色定义
        你是一名网络安全数据工程师，专注于将非结构化的渗透测试报告（Write-ups）转化为结构化的 **攻击轨迹数据集 (Attack Trajectories)**。

        ### 任务目标
        对目标文件 '{target_md_file}' 进行全量解析，重构出一条完整的、具备因果关系的攻击链。
        最终产物必须是一个 **JSON Lines (.jsonl)** 格式的文件，名为 `trajectory_reconstruction.jsonl`。

        ### 执行步骤
        请严格按照以下逻辑流进行操作：

        1.  **全局侦察 (Structure Analysis):
            - 调用 `md_parser.get_outline` 获取文档骨架 [1]。
            - 识别攻击的关键阶段（如：Reconnaissance, Enumeration, Initial Access, Privilege Escalation）。

        2.  **碎片提取 (Fragment Extraction)**:
            - 按章节顺序，使用 `md_parser.extract_code_blocks` 提取所有的 Shell 命令和控制台输出。
            - 使用 `md_parser.extract_images` 定位所有截图。

        3.  **视觉感知与对齐 (Visual Grounding)**:
            - 对于每一个截图，必须结合上下文判断其性质。
            - **核心动作**：如果截图看似包含终端输出（如 Nmap 扫描结果）或 Web 报错信息，必须调用 `md_parser.perform_ocr` 获取文本内容。
            - **逻辑关联**：将 OCR 得到的文本作为 "Observation" 与前文的 "Action"（命令）进行配对。

        4.  **轨迹组装与清洗 (Trajectory Assembly)**:
            - 将提取的碎片组装成标准化的步骤（Step）。
            - **重要**：你需要阅读代码块周围的文本（Context），提取作者的意图作为 "reasoning"。
        
        ### 最终产物格式要求 (JSONL Schema)
        
        请将最终结果写入 `trajectory_reconstruction.jsonl`，每一行必须符合以下 JSON 结构：
        {{
            "step_id": 1,
            "phase": "Reconnaissance",
            "action": "nmap -sC -sV -p- 10.10.10.X", 
            "action_type": "shell_command",
            "observation": "PORT 80/tcp open http...", 
            "observation_source": "ocr_image" 或 "code_block",
            "reasoning": "作者发现端口扫描未显示详细信息，决定使用脚本扫描服务版本。",
            "raw_image_path": "assets/nmap_scan.png" (如果是OCR提取，否则为null)
        }}

        ### 完成条件
        - 确保所有关键步骤都已记录。
        - 生成文件后，调用 `done` 结束任务。
        """

    task = Task(task_id="reconstruction_demo_001", instruction=instruction)
    
    agent = YogaAgent(
        agent_config=agent_config,
        agent_type='trajectory_reconstructor',
        action_spaces=[local_shell, md_space, edit_space]
    )

    log_info(f"🚀 Starting Reconstruction on file: {target_md_file}")
    
    # 记录实验日志
    exp_dir = Path("exp_bank")
    exp_dir.mkdir(exist_ok=True)
    exp_file_path = exp_dir / f"{task.task_id}_{int(time.time())}.jsonl"

    try:
        result = await agent.execute(task)
        log_info(f"✅ Agent Execution Completed. Result: {result}")
        
        # 简单验证结果
        output_file = workspace_path / "reconstructed_trajectory.md"
        if output_file.exists():
            log_info(f"🎉 Success! Trajectory saved to: {output_file}")
        else:
            log_error("⚠️ Warning: Output file 'reconstructed_trajectory.md' was not created.")
            
    except Exception as e:
        log_error(f"❌ Execution Failed: {e}")
        raise
    finally:
        agent.dump(exp_file_path)
        await env.close()

if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(run_reconstruction_task())
    finally:
        loop.run_until_complete(loop.shutdown_asyncgens())
        loop.close()