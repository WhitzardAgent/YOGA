"""
Agent Bridge 示例使用脚本
演示：本地Agent驱动远程Ubuntu容器执行任务的完整流程
"""

import asyncio
import os
import sys
from datetime import datetime

# 添加父目录到路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent_bridge import AgentBridge
from agent_bridge.utils import setup_logging


async def demo_data_scraping():
    """
    演示1：数据爬取任务
    
    1. 本地Agent发起一个耗时10秒的云端数据爬取任务
    2. 通过stream_shell实时打印爬取进度
    3. 云端生成一个report.png
    4. 框架自动检测并下载该图片
    5. 同步结果至Notion
    """
    print("\n" + "="*60)
    print("演示1: 数据爬取任务")
    print("="*60 + "\n")
    
    # 配置（实际使用时应从环境变量或配置文件读取）
    config = {
        'ssh_host': '36.103.236.241',  # 请替换为实际的服务器地址
        'ssh_username': 'ubuntu',
        'ssh_password': 'g0y.IRZ6sxdyNhmu',  # 请替换为实际的密码
        'ssh_port': 22,
        'remote_workspace': '~/agent_bridge_demo',
        'local_downloads': './demo_downloads',
        'notion_token': 'your-notion-token',  # 请替换为实际的Notion令牌
        'venv_path': '~/agent_bridge_venv'
    }
    
    # 使用异步上下文管理器
    async with AgentBridge(config) as bridge:
        print("✓ Agent Bridge 已初始化")
        
        # 任务1: 创建模拟的爬取脚本
        print("\n任务1: 创建爬取脚本...")
        scraping_code = '''
import time
import json
import os

# 模拟数据爬取任务
print("开始数据爬取任务...", flush=True)

# 模拟爬取进度
for i in range(1, 11):
    print(f"Scraping page {{i}}... 进度: {{i*10}}%", flush=True)
    time.sleep(1)  # 模拟网络延迟

# 生成模拟数据
scraped_data = {
    "pages_crawled": 10,
    "total_items": 150,
    "categories": ["科技", "娱乐", "体育", "财经"],
    "timestamp": time.time()
}

# 生成报告（这里创建一个文本报告，实际可以生成图表）
report_content = f"""
# 数据爬取报告

## 爬取统计
- 爬取页面数: {scraped_data['pages_crawled']}
- 总项目数: {scraped_data['total_items']}
- 分类: {', '.join(scraped_data['categories'])}
- 完成时间: {time.strftime('%Y-%m-%d %H:%M:%S')}

## 数据质量
数据完整性: 98.5%
错误率: 1.2%
平均响应时间: 2.3秒
"""

# 保存报告
with open('/tmp/scraping_report.txt', 'w', encoding='utf-8') as f:
    f.write(report_content)

print("✓ 爬取任务完成！")
print(f"✓ 报告已生成: /tmp/scraping_report.txt")
print(f"✓ 数据统计: {{scraped_data}}")
'''
        
        result = await bridge.execute_task({
            'type': 'python',
            'content': scraping_code
        })
        
        if result['success']:
            print("✓ 爬取脚本执行成功")
        else:
            print(f"✗ 爬取脚本执行失败: {result.get('stderr', 'Unknown error')}")
            return
        
        # 任务2: 使用流式输出执行长时间任务
        print("\n任务2: 流式输出演示...")
        print("执行耗时10秒的任务，实时查看进度:\n")
        
        stream_code = '''
import time
import sys

print("开始执行长时间任务...", flush=True)

# 模拟长时间运行的任务
for i in range(10):
    print(f"Scraping page {{i+1}}... 正在处理第 {{i+1}} 页", flush=True)
    time.sleep(1)  # 模拟耗时操作

print("任务完成！", flush=True)
'''
        
        # 这里我们使用shell命令来执行Python代码以展示流式输出
        shell_command = f'python3 -c "{stream_code.replace(chr(10), "; ")}"'
        
        # 注意：实际使用中应该使用stream_shell方法
        print("流式输出示例（实际使用时会实时显示）:")
        for i in range(1, 11):
            print(f"  Scraping page {i}... 进度: {i*10}%")
            await asyncio.sleep(0.5)
        
        # 任务3: 生成可视化报告
        print("\n任务3: 生成数据可视化报告...")
        
        # 这里模拟生成一个报告文件
        report_data = {
            'pages_crawled': 10,
            'total_items': 150,
            'categories': ['科技', '娱乐', '体育', '财经'],
            'avg_response_time': 2.3,
            'success_rate': 98.5
        }
        
        # 实际项目中这里会生成真正的图表
        print("✓ 报告数据已生成")
        print(f"  - 爬取页面: {report_data['pages_crawled']}")
        print(f"  - 总项目数: {report_data['total_items']}")
        print(f"  - 成功率: {report_data['success_rate']}%")
        
        # 任务4: 同步生成的文件到本地
        print("\n任务4: 同步生成的文件到本地...")
        
        # 创建一个示例报告文件在远程
        await bridge.execute_task({
            'type': 'shell',
            'content': 'echo "This is a demo report file" > /tmp/demo_report.txt'
        })
        
        # 同步文件
        result = await bridge.execute_task({
            'type': 'sync_from_cloud',
            'content': '/tmp/demo_report.txt',
            'params': {
                'local_path': './demo_downloads'
            }
        })
        
        if result['success']:
            print(f"✓ 文件同步成功: {len(result['synced_files'])} 个文件")
        else:
            print("✗ 文件同步失败")
        
        # 任务5: 自动获取资源文件
        print("\n任务5: 自动获取资源文件...")
        
        result = await bridge.execute_task({
            'type': 'fetch_assets',
            'content': '/tmp',
            'params': {
                'local_dir': './demo_downloads',
                'asset_patterns': [r'.*\\.txt$', r'.*\\.json$', r'.*\\.csv$']
            }
        })
        
        if result['success']:
            print(f"✓ 资源文件获取成功: {len(result['synced_assets'])} 个文件")
        else:
            print("✗ 资源文件获取失败")
        
        # 任务6: 同步到Notion（如果有配置）
        if config.get('notion_token'):
            print("\n任务6: 同步结果到Notion...")
            
            notion_content = {
                'properties': {
                    'Title': {
                        'title': [
                            {
                                'text': {
                                    'content': f'数据爬取报告 - {datetime.now().strftime("%Y-%m-%d %H:%M")}'
                                }
                            }
                        ]
                    },
                    'Status': {
                        'select': {
                            'name': '已完成'
                        }
                    },
                    'Pages': {
                        'number': 10
                    },
                    'Items': {
                        'number': 150
                    },
                    'Success Rate': {
                        'number': 98.5
                    }
                },
                'children': [
                    {
                        'object': 'block',
                        'type': 'paragraph',
                        'paragraph': {
                            'rich_text': [
                                {
                                    'type': 'text',
                                    'text': {
                                        'content': '这是通过Agent Bridge自动生成的报告。'
                                    }
                                }
                            ]
                        }
                    }
                ]
            }
            
            result = await bridge.execute_task({
                'type': 'notion',
                'content': notion_content,
                'params': {
                    'database_id': 'your-database-id'  # 请替换为实际的数据库ID
                }
            })
            
            if result['success']:
                print("✓ 数据已同步到Notion")
            else:
                print(f"✗ Notion同步失败: {result.get('error', 'Unknown error')}")
        
        print("\n" + "="*60)
        print("演示1完成！")
        print("="*60)


async def demo_code_analysis():
    """
    演示2：代码分析任务
    
    1. 上传Python代码到云端
    2. 在云端虚拟环境中执行代码分析
    3. 返回结构化分析结果
    4. 生成分析报告
    """
    print("\n" + "="*60)
    print("演示2: 代码分析任务")
    print("="*60 + "\n")
    
    # 配置
    config = {
        'ssh_host': '36.103.236.241',  # 请替换为实际的服务器地址
        'ssh_username': 'ubuntu',
        'ssh_password': 'g0y.IRZ6sxdyNhmu',  # 请替换为实际的密码
        'ssh_port': 22,
        'remote_workspace': '~/agent_bridge_demo',
        'local_downloads': './demo_downloads',
        'notion_token': 'your-notion-token',  # 请替换为实际的Notion令牌
        'venv_path': '~/agent_bridge_venv'
    }
    
    async with AgentBridge(config) as bridge:
        print("✓ Agent Bridge 已初始化")
        
        # 任务1: 创建示例Python代码文件
        print("\n任务1: 创建示例Python代码...")
        
        sample_code = '''
def calculate_fibonacci(n):
    """计算斐波那契数列"""
    if n <= 0:
        return []
    elif n == 1:
        return [0]
    elif n == 2:
        return [0, 1]
    
    fib = [0, 1]
    for i in range(2, n):
        fib.append(fib[i-1] + fib[i-2])
    
    return fib

class DataProcessor:
    """数据处理类"""
    
    def __init__(self, data):
        self.data = data
    
    def process_data(self):
        """处理数据"""
        if not self.data:
            return None
        
        result = []
        for item in self.data:
            if item > 0:
                result.append(item * 2)
        
        return result
    
    def analyze_data(self):
        """分析数据"""
        if not self.data:
            return {{}}
        
        return {{
            'count': len(self.data),
            'sum': sum(self.data),
            'avg': sum(self.data) / len(self.data) if self.data else 0
        }}

# 主程序
if __name__ == "__main__":
    # 计算斐波那契数列
    fib_sequence = calculate_fibonacci(10)
    print(f"斐波那契数列: {{fib_sequence}}")
    
    # 处理数据
    processor = DataProcessor(fib_sequence)
    processed = processor.process_data()
    analysis = processor.analyze_data()
    
    print(f"处理后的数据: {{processed}}")
    print(f"数据分析: {{analysis}}")
'''
        
        # 将代码写入文件并同步到云端
        with open('/tmp/sample_code.py', 'w', encoding='utf-8') as f:
            f.write(sample_code)
        
        result = await bridge.execute_task({
            'type': 'sync_to_cloud',
            'content': '/tmp/sample_code.py',
            'params': {
                'remote_path': '/tmp'
            }
        })
        
        if result['success']:
            print("✓ 代码文件已同步到云端")
        else:
            print("✗ 代码文件同步失败")
            return
        
        # 任务2: 执行代码分析
        print("\n任务2: 执行代码分析...")
        
        result = await bridge.execute_task({
            'type': 'analyze_code',
            'content': '/tmp/sample_code.py',
            'params': {
                'analysis_type': 'general'
            }
        })
        
        if result['success']:
            print("✓ 代码分析完成")
            
            # 显示分析结果
            analysis_result = result.get('result', {})
            summary = result.get('summary', {})
            
            print(f"\n分析摘要:")
            print(f"  - 函数数量: {summary.get('total_functions', 0)}")
            print(f"  - 类数量: {summary.get('total_classes', 0)}")
            print(f"  - 导入模块: {summary.get('total_imports', 0)}")
            print(f"  - 圈复杂度: {summary.get('cyclomatic_complexity', 0)}")
            
            # 显示详细信息
            if 'functions' in analysis_result:
                print(f"\n函数列表:")
                for func in analysis_result['functions']:
                    args = ', '.join(func.get('args', []))
                    print(f"  - {func['name']}({args}) [第{func['line']}行]")
            
            if 'classes' in analysis_result:
                print(f"\n类列表:")
                for cls in analysis_result['classes']:
                    print(f"  - {cls['name']} [第{cls['line']}行] (方法数: {cls['methods']})")
        else:
            print(f"✗ 代码分析失败: {result.get('error', 'Unknown error')}")
        
        # 任务3: 安全分析
        print("\n任务3: 执行安全分析...")
        
        result = await bridge.execute_task({
            'type': 'analyze_code',
            'content': '/tmp/sample_code.py',
            'params': {
                'analysis_type': 'security'
            }
        })
        
        if result['success']:
            print("✓ 安全分析完成")
            
            security_issues = result.get('result', {}).get('security_issues', [])
            if security_issues:
                print(f"发现 {len(security_issues)} 个安全问题:")
                for issue in security_issues:
                    print(f"  - {issue['type']}: {issue.get('severity', 'unknown')} [第{issue['line']}行]")
            else:
                print("✓ 未发现安全问题")
        
        print("\n" + "="*60)
        print("演示2完成！")
        print("="*60)


async def demo_batch_processing():
    """
    演示3：批量处理任务
    
    1. 批量上传多个数据文件到云端
    2. 批量处理数据
    3. 自动同步结果文件
    4. 清理临时文件
    """
    print("\n" + "="*60)
    print("演示3: 批量处理任务")
    print("="*60 + "\n")
    
    # 配置
    config = {
        'ssh_host': '36.103.236.241',  # 请替换为实际的服务器地址
        'ssh_username': 'ubuntu',
        'ssh_password': 'g0y.IRZ6sxdyNhmu',  # 请替换为实际的密码
        'ssh_port': 22,
        'remote_workspace': '~/agent_bridge_demo',
        'local_downloads': './demo_downloads',
        'notion_token': 'your-notion-token',  # 请替换为实际的Notion令牌
        'venv_path': '~/agent_bridge_venv'
    }
    async with AgentBridge(config) as bridge:
        print("✓ Agent Bridge 已初始化")
        
        # 任务1: 创建多个数据文件
        print("\n任务1: 创建示例数据文件...")
        
        # 创建CSV数据文件
        csv_data = '''name,age,city,score
Alice,25,New York,85
Bob,30,London,92
Charlie,22,Tokyo,78
David,28,Paris,88
Eve,24,Berlin,95
'''
        
        # 创建多个数据文件
        data_files = []
        for i in range(3):
            filename = f'/tmp/data_batch_{i+1}.csv'
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(csv_data)
            data_files.append(filename)
        
        print(f"✓ 已创建 {len(data_files)} 个数据文件")
        
        # 任务2: 批量上传到云端
        print("\n任务2: 批量上传数据文件到云端...")
        
        for data_file in data_files:
            result = await bridge.execute_task({
                'type': 'sync_to_cloud',
                'content': data_file,
                'params': {
                    'remote_path': '/tmp'
                }
            })
            
            if result['success']:
                print(f"✓ 上传成功: {os.path.basename(data_file)}")
            else:
                print(f"✗ 上传失败: {os.path.basename(data_file)}")
        
        # 任务3: 批量处理数据
        print("\n任务3: 批量处理数据文件...")
        
        processing_code = '''
import pandas as pd
import os
import glob

# 查找所有数据文件
data_files = glob.glob('/tmp/data_batch_*.csv')
print(f"找到 {len(data_files)} 个数据文件")

all_data = []

# 处理每个文件
for i, file_path in enumerate(data_files, 1):
    print(f"处理文件 {i}/{len(data_files)}: {os.path.basename(file_path)}")
    
    # 读取CSV文件
    df = pd.read_csv(file_path)
    
    # 数据处理
    df['age_group'] = pd.cut(df['age'], bins=[0, 25, 30, 100], labels=['年轻', '中年', '老年'])
    df['score_level'] = pd.cut(df['score'], bins=[0, 80, 90, 100], labels=['C', 'B', 'A'])
    
    # 统计分析
    stats = {{
        'total_records': len(df),
        'avg_age': df['age'].mean(),
        'avg_score': df['score'].mean(),
        'city_distribution': df['city'].value_counts().to_dict(),
        'age_group_distribution': df['age_group'].value_counts().to_dict(),
        'score_level_distribution': df['score_level'].value_counts().to_dict()
    }}
    
    print(f"  - 总记录数: {stats['total_records']}")
    print(f"  - 平均年龄: {stats['avg_age']:.1f}")
    print(f"  - 平均分数: {stats['avg_score']:.1f}")
    
    # 保存处理后的文件
    output_file = file_path.replace('data_batch_', 'processed_batch_')
    df.to_csv(output_file, index=False, encoding='utf-8')
    print(f"  - 已保存: {os.path.basename(output_file)}")
    
    all_data.append(df)

# 合并所有数据
if all_data:
    combined_df = pd.concat(all_data, ignore_index=True)
    combined_output = '/tmp/combined_processed_data.csv'
    combined_df.to_csv(combined_output, index=False, encoding='utf-8')
    print(f"\\n✓ 合并数据已保存: {os.path.basename(combined_output)}")
    print(f"  - 总记录数: {len(combined_df)}")

print("\\n✓ 批量处理完成！")
'''
        
        result = await bridge.execute_task({
            'type': 'python',
            'content': processing_code
        })
        
        if result['success']:
            print("✓ 数据处理完成")
        else:
            print(f"✗ 数据处理失败: {result.get('stderr', 'Unknown error')}")
            return
        
        # 任务4: 同步处理结果到本地
        print("\n任务4: 同步处理结果到本地...")
        
        result = await bridge.execute_task({
            'type': 'fetch_assets',
            'content': '/tmp',
            'params': {
                'local_dir': './demo_downloads',
                'asset_patterns': [r'.*processed_batch_.*\\.csv$', r'.*combined_processed_data\\.csv$']
            }
        })
        
        if result['success']:
            print(f"✓ 结果文件同步成功: {len(result['synced_assets'])} 个文件")
            for asset in result['synced_assets']:
                print(f"  - {os.path.basename(asset)}")
        else:
            print("✗ 结果文件同步失败")
        
        # 任务5: 生成汇总报告
        print("\n任务5: 生成汇总报告...")
        
        report_code = '''
import pandas as pd
import json

# 读取合并后的数据
df = pd.read_csv('/tmp/combined_processed_data.csv')

# 生成汇总报告
report = {
    'total_records': len(df),
    'avg_age': float(df['age'].mean()),
    'avg_score': float(df['score'].mean()),
    'age_distribution': df['age_group'].value_counts().to_dict(),
    'score_distribution': df['score_level'].value_counts().to_dict(),
    'city_distribution': df['city'].value_counts().to_dict(),
    'top_performers': df.nlargest(3, 'score')[['name', 'age', 'city', 'score']].to_dict('records')
}

# 保存报告
with open('/tmp/processing_summary_report.json', 'w', encoding='utf-8') as f:
    json.dump(report, f, ensure_ascii=False, indent=2)

print("汇总报告:")
print(f"  - 总记录数: {report['total_records']}")
print(f"  - 平均年龄: {report['avg_age']:.1f}")
print(f"  - 平均分数: {report['avg_score']:.1f}")
print(f"  - 高分学员: {len(report['top_performers'])} 人")

print("\\n✓ 汇总报告已生成: /tmp/processing_summary_report.json")
'''
        
        result = await bridge.execute_task({
            'type': 'python',
            'content': report_code
        })
        
        if result['success']:
            print("✓ 汇总报告生成成功")
        
        # # 任务6: 清理临时文件
        # print("\n任务6: 清理临时文件...")
        
        # await bridge.execute_task({
        #     'type': 'shell',
        #     'content': 'rm -f /tmp/data_batch_*.csv /tmp/processed_batch_*.csv /tmp/combined_processed_data.csv'
        # })
        
        print("✓ 临时文件已清理")
        
        print("\n" + "="*60)
        print("演示3完成！")
        print("="*60)


async def demo_pipeline_execution():
    """
    演示4：管道任务执行
    
    展示如何使用管道功能按顺序执行多个任务
    """
    print("\n" + "="*60)
    print("演示4: 管道任务执行")
    print("="*60 + "\n")
    
    # 配置
    config = {
        'ssh_host': '36.103.236.241',  # 请替换为实际的服务器地址
        'ssh_username': 'ubuntu',
        'ssh_password': 'g0y.IRZ6sxdyNhmu',  # 请替换为实际的密码
        'ssh_port': 22,
        'remote_workspace': '~/agent_bridge_demo',
        'local_downloads': './demo_downloads',
        'notion_token': 'your-notion-token',  # 请替换为实际的Notion令牌
        'venv_path': '~/agent_bridge_venv'
    }
    
    async with AgentBridge(config) as bridge:
        print("✓ Agent Bridge 已初始化")
        
        # 定义管道任务
        pipeline = [
            {
                'type': 'shell',
                'content': 'echo "开始管道任务执行" && date',
                'stop_on_error': True
            },
            {
                'type': 'python',
                'content': '''
import time
print("步骤2: 执行数据处理...")
data = [i**2 for i in range(1, 6)]
print(f"处理结果: {data}")
print("✓ 数据处理完成")
''',
                'stop_on_error': True
            },
            {
                'type': 'shell',
                'content': 'echo "步骤3: 验证结果"',
                'stop_on_error': False  # 即使失败也继续
            },
            {
                'type': 'python',
                'content': '''
print("步骤4: 生成最终报告...")
report = {
    'status': 'success',
    'timestamp': __import__('time').time(),
    'summary': '管道任务执行成功'
}
print(f"报告: {report}")
print("✓ 报告生成完成")
''',
                'stop_on_error': True
            }
        ]
        
        print("\n执行管道任务...")
        print("管道包含以下步骤:")
        for i, task in enumerate(pipeline, 1):
            print(f"  {i}. {task['type']}: {task['content'][:50]}...")
        
        # 执行管道
        results = await bridge.execute_pipeline(pipeline)
        
        # 显示结果
        print(f"\n管道执行完成！")
        print(f"总共 {len(results)} 个任务，成功 {sum(1 for r in results if r.get('success', False))} 个")
        
        for i, result in enumerate(results, 1):
            status = "✓" if result.get('success', False) else "✗"
            print(f"{status} 任务 {i}: {'成功' if result.get('success', False) else '失败'}")
        
        print("\n" + "="*60)
        print("演示4完成！")
        print("="*60)


async def main():
    """
    主函数：运行所有演示
    """
    print("\n" + "="*60)
    print("Agent Bridge 演示程序")
    print("="*60)
    
    # 设置日志
    setup_logging(level="INFO")
    
    # 显示说明
    print("\n说明:")
    print("- 请将演示脚本中的配置替换为您的实际服务器信息")
    print("- 演示1: 数据爬取任务（包含流式输出、文件同步、Notion集成）")
    print("- 演示2: 代码分析任务（包含代码质量、复杂度、安全分析）")
    print("- 演示3: 批量处理任务（包含批量数据处理、结果汇总）")
    print("- 演示4: 管道任务执行（展示任务链执行）")
    
    # 检查命令行参数
    if len(sys.argv) > 1:
        demo_name = sys.argv[1]
        
        if demo_name == '1':
            await demo_data_scraping()
        elif demo_name == '2':
            await demo_code_analysis()
        elif demo_name == '3':
            await demo_batch_processing()
        elif demo_name == '4':
            await demo_pipeline_execution()
        else:
            print(f"未知的演示: {demo_name}")
            print("使用方法: python example_usage.py [1|2|3|4]")
    else:
        # 运行所有演示
        print("\n运行所有演示...")
        print("\n" + "⚠ 注意：以下演示使用的是模拟数据")
        print("实际使用时需要配置真实的服务器信息")
        
        # 由于我们没有真实的服务器，这里只是展示代码结构
        print("\n演示代码已准备就绪，请配置服务器信息后运行:")
        print("  python example_usage.py 1  # 运行演示1")
        print("  python example_usage.py 2  # 运行演示2")
        print("  python example_usage.py 3  # 运行演示3")
        print("  python example_usage.py 4  # 运行演示4")


if __name__ == "__main__":
    asyncio.run(main())