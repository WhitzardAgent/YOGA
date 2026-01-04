"""
基本功能测试脚本
用于验证Agent Bridge框架的核心功能
"""

import asyncio
import sys
import os
import logging

# Add the parent directory to the path so we can import agent_bridge
current_dir = os.path.dirname(__file__)
parent_dir = os.path.join(current_dir, '..')
sys.path.insert(0, parent_dir)

from .agent_bridge import AgentBridge
from .utils import setup_logging


async def test_basic_functionality():
    """测试基本功能"""
    print("="*60)
    print("Agent Bridge 基本功能测试")
    print("="*60)
    
    # 设置日志
    setup_logging(level="DEBUG")
    
    # 注意：以下配置需要替换为实际的服务器信息
    config = {
        'ssh_host': '36.103.236.241',  # 请替换为实际的服务器地址
        'ssh_username': 'ubuntu',   # 请替换为实际的用户名
        'ssh_password': 'g0y.IRZ6sxdyNhmu',   # 请替换为实际的密码
        'ssh_port': 22,
        'remote_workspace': '~/agent_bridge_test',
        'local_downloads': './test_downloads',
        'venv_path': '~/agent_bridge_test_venv'
    }
    
    print("\n配置信息:")
    print(f"  SSH主机: {config['ssh_host']}")
    print(f"  SSH用户: {config['ssh_username']}")
    print(f"  工作目录: {config['remote_workspace']}")
    print(f"  下载目录: {config['local_downloads']}")
    
    print("\n⚠ 警告: 请确保已配置正确的服务器信息！")
    print("是否继续测试? (y/N): ", end="")
    
    response = input().strip().lower()
    if response != 'y':
        print("测试已取消")
        return
    
    try:
        print("\n开始测试...")
        
        # 测试1: 初始化
        print("\n测试1: 初始化Agent Bridge...")
        bridge = AgentBridge(config)
        await bridge.initialize()
        print("✓ Agent Bridge 初始化成功")
        
        # 测试2: 执行简单shell命令
        print("\n测试2: 执行shell命令...")
        result = await bridge.execute_task({
            'type': 'shell',
            'content': 'echo "Hello from Agent Bridge!" && date'
        })
        
        if result['success']:
            print("✓ Shell命令执行成功")
            print(f"  输出: {result['stdout'].strip()}")
        else:
            print("✗ Shell命令执行失败")
            print(f"  错误: {result['stderr']}")
        
        # 测试3: 执行Python代码
        print("\n测试3: 执行Python代码...")
        result = await bridge.execute_task({
            'type': 'python',
            'content': '''
import sys
import os

print("Python版本:", sys.version)
print("当前工作目录:", os.getcwd())
print("✓ Python代码执行成功")

# 创建测试数据
with open('/tmp/test_output.txt', 'w') as f:
    f.write("这是由Agent Bridge生成的测试文件\\n")
    f.write(f"Python版本: {sys.version}\\n")
    f.write(f"时间: {__import__('datetime').datetime.now()}\\n")

print("✓ 测试文件已创建: /tmp/test_output.txt")
'''
        })
        
        if result['success']:
            print("✓ Python代码执行成功")
            if result.get('json_output'):
                print(f"  JSON输出: {result['json_output']}")
        else:
            print("✗ Python代码执行失败")
            print(f"  错误: {result['stderr']}")
        
        # 测试4: 文件同步
        print("\n测试4: 测试文件同步...")
        
        # 创建本地测试文件
        test_file = Path('./test_local_file.txt')
        test_file.write_text("这是本地测试文件\n用于测试同步功能\n")
        
        result = await bridge.execute_task({
            'type': 'sync_to_cloud',
            'content': str(test_file),
            'params': {'remote_path': '/tmp'}
        })
        
        if result['success']:
            print("✓ 文件同步到云端成功")
            print(f"  已同步文件: {result['synced_files']}")
        else:
            print("✗ 文件同步到云端失败")
        
        # 测试5: 获取资源文件
        print("\n测试5: 获取资源文件...")
        result = await bridge.execute_task({
            'type': 'fetch_assets',
            'content': '/tmp',
            'params': {
                'local_dir': './test_downloads',
                'asset_patterns': [r'.*\.txt$', r'.*\.csv$', r'.*\.json$']
            }
        })
        
        if result['success']:
            print("✓ 资源文件获取成功")
            print(f"  获取文件数: {len(result['synced_assets'])}")
            for asset in result['synced_assets']:
                print(f"    - {asset}")
        else:
            print("✗ 资源文件获取失败")
        
        # 测试6: 虚拟环境
        print("\n测试6: 测试虚拟环境...")
        result = await bridge.execute_task({
            'type': 'python',
            'content': '''
import sys
import subprocess

# 检查是否在虚拟环境中
print("Python可执行文件:", sys.executable)

# 尝试安装包
result = subprocess.run([sys.executable, '-m', 'pip', 'install', 'requests'], 
                       capture_output=True, text=True)
if result.returncode == 0:
    print("✓ 包安装成功")
else:
    print("✗ 包安装失败:", result.stderr)

# 测试导入
import requests
print("✓ requests模块可导入")
print("✓ 虚拟环境测试完成")
'''
        })
        
        if result['success']:
            print("✓ 虚拟环境测试成功")
        else:
            print("✗ 虚拟环境测试失败")
        
        # 测试7: 管道任务
        print("\n测试7: 测试管道任务...")
        
        pipeline = [
            {
                'type': 'shell',
                'content': 'echo "管道任务步骤1"',
                'stop_on_error': True
            },
            {
                'type': 'python',
                'content': 'print("管道任务步骤2")',
                'stop_on_error': True
            },
            {
                'type': 'shell',
                'content': 'echo "管道任务步骤3"',
                'stop_on_error': True
            }
        ]
        
        results = await bridge.execute_pipeline(pipeline)
        
        success_count = sum(1 for r in results if r.get('success', False))
        print(f"✓ 管道任务完成: {success_count}/{len(results)} 成功")
        
        # 测试8: 错误处理
        print("\n测试8: 测试错误处理...")
        
        result = await bridge.execute_task({
            'type': 'shell',
            'content': 'false'  # 这个命令会返回非零状态码
        })
        
        if not result['success']:
            print("✓ 错误处理正常（预期失败）")
            print(f"  返回码: {result['exit_code']}")
        else:
            print("✗ 错误处理异常")
        
        # 清理
        print("\n清理测试文件...")
        
        # 删除本地测试文件
        if test_file.exists():
            test_file.unlink()
        
        # 清理远程文件
        await bridge.execute_task({
            'type': 'shell',
            'content': 'rm -f /tmp/test_*.txt /tmp/test_*.csv'
        })
        
        # 关闭连接
        await bridge.cleanup()
        
        print("✓ 所有测试完成！")
        
    except Exception as e:
        print(f"\n✗ 测试失败: {str(e)}")
        import traceback
        traceback.print_exc()


async def test_demo_scenario():
    """测试演示场景"""
    print("\n" + "="*60)
    print("演示场景测试")
    print("="*60)
    
    # 这里我们可以模拟没有真实服务器的场景
    print("\n由于无法连接到真实服务器，这里展示代码结构:")
    
    print("""
# 示例：数据爬取任务
async def data_scraping_demo():
    config = {
        'ssh_host': 'your-server.com',
        'ssh_username': 'ubuntu',
        'ssh_password': 'your-password'
    }
    
    async with AgentBridge(config) as bridge:
        # 1. 执行爬取任务
        result = await bridge.execute_task({
            'type': 'python',
            'content': '''
import time
for i in range(10):
    print(f"Scraping page {i+1}...")
    time.sleep(1)
'''
        })
        
        # 2. 同步生成的报告
        await bridge.execute_task({
            'type': 'fetch_assets',
            'content': '/tmp',
            'params': {'asset_patterns': [r'.*\\.png$', r'.*\\.csv$']}
        })
        
        # 3. 同步到Notion
        await bridge.execute_task({
            'type': 'notion',
            'content': {'properties': {...}},
            'params': {'database_id': '...'}
        })
""")


async def main():
    """主函数"""
    print("Agent Bridge 测试程序")
    print("\n选择测试模式:")
    print("1. 基本功能测试（需要配置真实服务器）")
    print("2. 演示场景测试（展示代码结构）")
    print("3. 退出")
    
    choice = input("\n请输入选择 (1/2/3): ").strip()
    
    if choice == '1':
        await test_basic_functionality()
    elif choice == '2':
        await test_demo_scenario()
    else:
        print("退出测试")


if __name__ == "__main__":
    asyncio.run(main())