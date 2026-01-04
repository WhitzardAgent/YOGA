"""
命令行接口
提供Agent Bridge的命令行工具
"""

import asyncio
import argparse
import json
import sys
from pathlib import Path

from . import AgentBridge
from .utils import load_env_file, setup_logging


def load_config_from_file(config_file):
    """从配置文件加载配置"""
    if not Path(config_file).exists():
        print(f"配置文件不存在: {config_file}")
        return None
    
    try:
        with open(config_file, 'r', encoding='utf-8') as f:
            if config_file.endswith('.json'):
                return json.load(f)
            else:
                # 支持简单的key=value格式
                config = {}
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, value = line.split('=', 1)
                        config[key.strip()] = value.strip()
                return config
    except Exception as e:
        print(f"加载配置文件失败: {str(e)}")
        return None


def create_sample_config():
    """创建示例配置文件"""
    config = {
        "ssh_host": "your-server.com",
        "ssh_username": "ubuntu",
        "ssh_password": "your-password",
        "ssh_port": 22,
        "remote_workspace": "~/agent_bridge_workspace",
        "local_downloads": "./downloads",
        "venv_path": "~/agent_bridge_venv",
        "timeout": 30,
        "retry_times": 3
    }
    
    config_file = "agent_bridge_config.json"
    with open(config_file, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2, ensure_ascii=False)
    
    print(f"示例配置文件已创建: {config_file}")
    print("请编辑配置文件并填入实际的服务器信息")


def print_result(result):
    """打印执行结果"""
    if result.get('success', False):
        print("✓ 任务执行成功")
        if 'stdout' in result:
            print(f"输出:\n{result['stdout']}")
        if 'json_output' in result:
            print(f"JSON输出:\n{json.dumps(result['json_output'], ensure_ascii=False, indent=2)}")
    else:
        print("✗ 任务执行失败")
        if 'stderr' in result:
            print(f"错误:\n{result['stderr']}")
        if 'error' in result:
            print(f"错误信息: {result['error']}")


async def execute_shell_command(bridge, command):
    """执行shell命令"""
    task = {
        'type': 'shell',
        'content': command
    }
    return await bridge.execute_task(task)


async def execute_python_code(bridge, code_or_file):
    """执行Python代码"""
    # 检查是否是文件
    if Path(code_or_file).exists():
        with open(code_or_file, 'r', encoding='utf-8') as f:
            code = f.read()
    else:
        code = code_or_file
    
    task = {
        'type': 'python',
        'content': code
    }
    return await bridge.execute_task(task)


async def sync_files(bridge, local_path, remote_path, direction='to_cloud'):
    """同步文件"""
    if direction == 'to_cloud':
        task = {
            'type': 'sync_to_cloud',
            'content': local_path,
            'params': {'remote_path': remote_path}
        }
    else:
        task = {
            'type': 'sync_from_cloud',
            'content': remote_path,
            'params': {'local_path': local_path}
        }
    
    return await bridge.execute_task(task)


async def fetch_assets(bridge, remote_dir, local_dir, patterns):
    """获取资源文件"""
    task = {
        'type': 'fetch_assets',
        'content': remote_dir,
        'params': {
            'local_dir': local_dir,
            'asset_patterns': patterns
        }
    }
    return await bridge.execute_task(task)


async def run_interactive_mode(bridge):
    """运行交互模式"""
    print("\nAgent Bridge 交互模式")
    print("=" * 50)
    print("支持的命令:")
    print("  shell <command>     - 执行shell命令")
    print("  python <code/file>  - 执行Python代码或文件")
    print("  sync <local> <remote> - 同步文件到云端")
    print("  fetch <remote> <local> - 从云端同步文件")
    print("  assets <remote> <local> <patterns> - 获取资源文件")
    print("  exit               - 退出")
    print()
    
    while True:
        try:
            command = input("agent-bridge> ").strip()
            
            if not command:
                continue
            
            if command.lower() == 'exit':
                print("退出交互模式")
                break
            
            parts = command.split(maxsplit=1)
            if not parts:
                continue
            
            cmd_type = parts[0].lower()
            
            if cmd_type == 'shell' and len(parts) > 1:
                result = await execute_shell_command(bridge, parts[1])
                print_result(result)
            
            elif cmd_type == 'python' and len(parts) > 1:
                result = await execute_python_code(bridge, parts[1])
                print_result(result)
            
            elif cmd_type == 'sync' and len(parts) > 1:
                args = parts[1].split()
                if len(args) >= 2:
                    result = await sync_files(bridge, args[0], args[1], 'to_cloud')
                    print_result(result)
                else:
                    print("用法: sync <local_path> <remote_path>")
            
            elif cmd_type == 'fetch' and len(parts) > 1:
                args = parts[1].split()
                if len(args) >= 2:
                    result = await sync_files(bridge, args[1], args[0], 'from_cloud')
                    print_result(result)
                else:
                    print("用法: fetch <remote_path> <local_path>")
            
            elif cmd_type == 'assets' and len(parts) > 1:
                args = parts[1].split()
                if len(args) >= 3:
                    patterns = args[2:]
                    result = await fetch_assets(bridge, args[0], args[1], patterns)
                    print_result(result)
                else:
                    print("用法: assets <remote_dir> <local_dir> <patterns...>")
            
            else:
                print("未知命令或参数不足")
        
        except KeyboardInterrupt:
            print("\n退出交互模式")
            break
        except Exception as e:
            print(f"错误: {str(e)}")


async def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="Agent Bridge - Cloud-Local Bridge Framework",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  agent-bridge --init-config                    # 创建示例配置文件
  agent-bridge --config config.json shell "ls -la"  # 执行shell命令
  agent-bridge --config config.json python "print('Hello')"  # 执行Python代码
  agent-bridge --config config.json sync ./data ~/workspace  # 同步文件
  agent-bridge --config config.json --interactive  # 交互模式
        """
    )
    
    parser.add_argument('--init-config', action='store_true',
                       help='创建示例配置文件')
    parser.add_argument('--config', '-c', default='agent_bridge_config.json',
                       help='配置文件路径 (默认: agent_bridge_config.json)')
    parser.add_argument('--log-level', default='INFO',
                       choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
                       help='日志级别 (默认: INFO)')
    parser.add_argument('--interactive', '-i', action='store_true',
                       help='运行交互模式')
    
    # 任务参数
    parser.add_argument('task_type', nargs='?',
                       choices=['shell', 'python', 'sync', 'fetch', 'assets'],
                       help='任务类型')
    parser.add_argument('arguments', nargs='*',
                       help='任务参数')
    
    args = parser.parse_args()
    
    # 设置日志
    setup_logging(level=args.log_level)
    
    # 创建示例配置
    if args.init_config:
        create_sample_config()
        return
    
    # 加载配置
    config = load_config_from_file(args.config)
    if not config:
        print("请创建配置文件或检查配置文件格式")
        print("使用 --init-config 创建示例配置文件")
        return
    
    # 检查必要的配置项
    required_keys = ['ssh_host', 'ssh_username', 'ssh_password']
    missing_keys = [key for key in required_keys if key not in config]
    if missing_keys:
        print(f"配置文件缺少必要项: {', '.join(missing_keys)}")
        print("请编辑配置文件并填入实际的服务器信息")
        return
    
    try:
        async with AgentBridge(config) as bridge:
            if args.interactive:
                await run_interactive_mode(bridge)
            elif args.task_type:
                if args.task_type == 'shell' and args.arguments:
                    result = await execute_shell_command(bridge, ' '.join(args.arguments))
                    print_result(result)
                elif args.task_type == 'python' and args.arguments:
                    result = await execute_python_code(bridge, ' '.join(args.arguments))
                    print_result(result)
                elif args.task_type == 'sync' and len(args.arguments) >= 2:
                    result = await sync_files(bridge, args.arguments[0], args.arguments[1], 'to_cloud')
                    print_result(result)
                elif args.task_type == 'fetch' and len(args.arguments) >= 2:
                    result = await sync_files(bridge, args.arguments[1], args.arguments[0], 'from_cloud')
                    print_result(result)
                elif args.task_type == 'assets' and len(args.arguments) >= 3:
                    result = await fetch_assets(bridge, args.arguments[0], args.arguments[1], args.arguments[2:])
                    print_result(result)
                else:
                    print("参数不足，请查看帮助信息")
                    parser.print_help()
            else:
                parser.print_help()
    
    except KeyboardInterrupt:
        print("\n程序被中断")
    except Exception as e:
        print(f"错误: {str(e)}")
        sys.exit(1)


def main_sync():
    """同步主函数入口"""
    asyncio.run(main())


if __name__ == "__main__":
    main_sync()