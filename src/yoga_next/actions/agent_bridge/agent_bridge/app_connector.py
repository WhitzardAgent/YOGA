"""
应用连接器：提供与第三方应用的集成接口
"""

import json
import logging
from typing import Any, Dict, List, Optional

from .action_executor import ActionExecutor
from .connection_manager import ConnectionManager
from .exceptions import ExecutionError

logger = logging.getLogger(__name__)


class AppConnector:
    """
    提供与第三方应用的集成接口
    """
    
    def __init__(self, connection_manager: ConnectionManager, action_executor: ActionExecutor):
        """
        初始化应用连接器
        
        Args:
            connection_manager: SSH连接管理器
            action_executor: 动作执行器
        """
        self.connection_manager = connection_manager
        self.action_executor = action_executor
    
    async def notion_write(self, content: Dict[str, Any], notion_token: str,
                          database_id: Optional[str] = None,
                          page_id: Optional[str] = None) -> Dict[str, Any]:
        """
        将内容写入Notion
        
        Args:
            content: 要写入的内容
            notion_token: Notion API令牌
            database_id: Notion数据库ID（如果创建新页面）
            page_id: Notion页面ID（如果更新现有页面）
            
        Returns:
            Dict[str, Any]: Notion API响应
            
        Raises:
            ExecutionError: Notion API调用失败时抛出
        """
        try:
            # 安装必要的依赖
            await self.action_executor.install_requirements(['requests', 'notion-client'])
            
            # 构建Notion API调用代码
            code = self._build_notion_code(content, notion_token, database_id, page_id)
            
            # 在云端执行
            result = await self.action_executor.run_python_script(code)
            
            if result['exit_code'] != 0:
                raise ExecutionError(f"Notion API调用失败: {result['stderr']}")
            
            # 解析JSON输出
            json_output = result.get('json_output', {})
            if not json_output or not json_output.get('success'):
                raise ExecutionError(f"Notion操作失败: {json_output.get('error', 'Unknown error')}")
            
            logger.info(f"Notion写入成功: {json_output.get('result', {})}")
            return json_output.get('result', {})
            
        except Exception as e:
            raise ExecutionError(f"Notion写入失败: {str(e)}")
    
    async def analyze_code(self, code_path: str, 
                          analysis_type: str = 'general') -> Dict[str, Any]:
        """
        分析代码文件
        
        Args:
            code_path: 代码文件路径（云端）
            analysis_type: 分析类型，可选值：general, complexity, security, performance
            
        Returns:
            Dict[str, Any]: 分析结果
            
        Raises:
            ExecutionError: 代码分析失败时抛出
        """
        try:
            # 安装必要的依赖
            await self.action_executor.install_requirements([
                'pylint', 'flake8', 'bandit', 'mccabe'
            ])
            
            # 构建代码分析代码
            code = self._build_code_analysis_code(code_path, analysis_type)
            
            # 在云端执行
            result = await self.action_executor.run_python_script(code)
            
            if result['exit_code'] != 0:
                raise ExecutionError(f"代码分析失败: {result['stderr']}")
            
            # 解析JSON输出
            json_output = result.get('json_output', {})
            if not json_output or not json_output.get('success'):
                raise ExecutionError(f"代码分析失败: {json_output.get('error', 'Unknown error')}")
            
            logger.info(f"代码分析完成: {json_output.get('result', {})}")
            return json_output.get('result', {})
            
        except Exception as e:
            
            raise ExecutionError(f"代码分析失败: {str(e)}")
    
    async def run_web_scraping(self, url: str, output_format: str = 'json',
                              selectors: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """
        运行网页爬虫任务
        
        Args:
            url: 目标URL
            output_format: 输出格式，可选值：json, csv, txt
            selectors: CSS选择器字典，用于提取特定内容
            
        Returns:
            Dict[str, Any]: 爬取结果
            
        Raises:
            ExecutionError: 爬虫任务失败时抛出
        """
        try:
            # 安装必要的依赖
            await self.action_executor.install_requirements([
                'requests', 'beautifulsoup4', 'lxml', 'selenium', 'pandas'
            ])
            
            # 构建爬虫代码
            code = self._build_web_scraping_code(url, output_format, selectors)
            
            # 在云端执行
            result = await self.action_executor.run_python_script(code)
            
            if result['exit_code'] != 0:
                raise ExecutionError(f"爬虫任务失败: {result['stderr']}")
            
            # 解析JSON输出
            json_output = result.get('json_output', {})
            if not json_output or not json_output.get('success'):
                raise ExecutionError(f"爬虫任务失败: {json_output.get('error', 'Unknown error')}")
            
            logger.info(f"爬虫任务完成: {json_output.get('result', {})}")
            return json_output.get('result', {})
            
        except Exception as e:
            raise ExecutionError(f"爬虫任务失败: {str(e)}")
    
    def _build_notion_code(self, content: Dict[str, Any], notion_token: str,
                          database_id: Optional[str], page_id: Optional[str]) -> str:
        """
        构建Notion API调用代码
        
        Args:
            content: 内容字典
            notion_token: Notion API令牌
            database_id: 数据库ID
            page_id: 页面ID
            
        Returns:
            str: Python代码
        """
        code = f'''
import json
import requests
import sys

try:
    # Notion API配置
    NOTION_TOKEN = "{notion_token}"
    DATABASE_ID = "{database_id}" if "{database_id}" != "None" else None
    PAGE_ID = "{page_id}" if "{page_id}" != "None" else None
    
    headers = {{
        "Authorization": f"Bearer {{NOTION_TOKEN}}",
        "Content-Type": "application/json",
        "Notion-Version": "2022-06-28"
    }}
    
    # 构建内容
    content = {json.dumps(content, ensure_ascii=False, indent=2)}
    
    # 根据参数决定是创建新页面还是更新现有页面
    if PAGE_ID:
        # 更新现有页面
        url = f"https://api.notion.com/v1/pages/{{PAGE_ID}}"
        response = requests.patch(url, headers=headers, json=content)
    else:
        # 创建新页面
        if not DATABASE_ID:
            raise ValueError("需要提供database_id来创建新页面")
        
        url = "https://api.notion.com/v1/pages"
        payload = {{
            "parent": {{"database_id": DATABASE_ID}},
            **content
        }}
        response = requests.post(url, headers=headers, json=payload)
    
    # 检查响应
    if response.status_code in [200, 201]:
        result = {{
            "success": True,
            "result": response.json(),
            "message": "Notion写入成功"
        }}
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        result = {{
            "success": False,
            "error": f"API调用失败: {{response.status_code}} - {{response.text}}",
            "response": response.json() if response.text else {{}}
        }}
        print(json.dumps(result, ensure_ascii=False, indent=2))
        sys.exit(1)
        
except Exception as e:
    result = {{
        "success": False,
        "error": str(e),
        "traceback": traceback.format_exc()
    }}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    sys.exit(1)
'''
        return code
    
    def _build_code_analysis_code(self, code_path: str, analysis_type: str) -> str:
        """
        构建代码分析代码
        
        Args:
            code_path: 代码文件路径
            analysis_type: 分析类型
            
        Returns:
            str: Python代码
        """
        code = """
import ast
import json
import sys
import os

try:
    # 读取代码文件
    with open("{code_path}", "r", encoding="utf-8") as f:
        code_content = f.read()
    
    # 解析AST
    try:
        tree = ast.parse(code_content)
    except SyntaxError as e:
        result = {{
            "success": False,
            "error": f"代码语法错误: {{str(e)}}"
        }}
        print(json.dumps(result, ensure_ascii=False, indent=2))
        sys.exit(1)
    
    # 根据分析类型执行不同的分析
    analysis_type = "{analysis_type}"
    analysis_result = {{}}
    
    if analysis_type == "general" or analysis_type == "complexity":
        # 基本统计和复杂度分析
        class CodeAnalyzer(ast.NodeVisitor):
            def __init__(self):
                self.functions = []
                self.classes = []
                self.imports = []
                self.lines_of_code = 0
                self.cyclomatic_complexity = 0
            
            def visit_FunctionDef(self, node):
                self.functions.append({{
                    "name": node.name,
                    "line": node.lineno,
                    "args": [arg.arg for arg in node.args.args]
                }})
                self.cyclomatic_complexity += 1  # 函数本身增加复杂度
                self.generic_visit(node)
            
            def visit_ClassDef(self, node):
                self.classes.append({{
                    "name": node.name,
                    "line": node.lineno,
                    "methods": len([n for n in node.body if isinstance(n, ast.FunctionDef)])
                }})
                self.generic_visit(node)
            
            def visit_Import(self, node):
                self.imports.extend([alias.name for alias in node.names])
                self.generic_visit(node)
            
            def visit_If(self, node):
                self.cyclomatic_complexity += 1
                self.generic_visit(node)
            
            def visit_For(self, node):
                self.cyclomatic_complexity += 1
                self.generic_visit(node)
            
            def visit_While(self, node):
                self.cyclomatic_complexity += 1
                self.generic_visit(node)
        
        analyzer = CodeAnalyzer()
        analyzer.visit(tree)
        
        analysis_result.update({{
            "functions": analyzer.functions,
            "classes": analyzer.classes,
            "imports": analyzer.imports,
            "total_lines": len(code_content.split('\\n')),
            "code_lines": len([line for line in code_content.split('\\n') if line.strip() and not line.strip().startswith('#')]),
            "cyclomatic_complexity": analyzer.cyclomatic_complexity
        }})
    
    if analysis_type == "security":
        # 安全分析（简单的模式匹配）
        security_issues = []
        
        # 检查危险函数
        dangerous_functions = ['eval', 'exec', 'input', 'raw_input', '__import__']
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                if node.func.id in dangerous_functions:
                    security_issues.append({{
                        "type": "dangerous_function",
                        "function": node.func.id,
                        "line": node.lineno,
                        "severity": "high"
                    }})
        
        # 检查SQL注入风险
        sql_patterns = ['SELECT', 'INSERT', 'UPDATE', 'DELETE', 'DROP']
        lines = code_content.split('\\n')
        for i, line in enumerate(lines, 1):
            for pattern in sql_patterns:
                if pattern in line.upper() and ('f"' in line or "f'" in line or '.format' in line):
                    security_issues.append({{
                        "type": "potential_sql_injection",
                        "line": i,
                        "code": line.strip(),
                        "severity": "medium"
                    }})
        
        analysis_result["security_issues"] = security_issues
    
    # 构建最终结果
    result = {{
        "success": True,
        "analysis_type": analysis_type,
        "result": analysis_result,
        "summary": {{
            "total_functions": len(analysis_result.get("functions", [])),
            "total_classes": len(analysis_result.get("classes", [])),
            "total_imports": len(analysis_result.get("imports", [])),
            "cyclomatic_complexity": analysis_result.get("cyclomatic_complexity", 0),
            "security_issues": len(analysis_result.get("security_issues", []))
        }}
    }}
    
    print(json.dumps(result, ensure_ascii=False, indent=2))
    
except Exception as e:
    result = {{
        "success": False,
        "error": str(e),
        "traceback": traceback.format_exc()
    }}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    sys.exit(1)
"""
        return code.format(code_path=code_path, analysis_type=analysis_type)
    
    def _build_web_scraping_code(self, url: str, output_format: str,
                                selectors: Optional[Dict[str, str]]) -> str:
        """
        构建网页爬虫代码
        
        Args:
            url: 目标URL
            output_format: 输出格式
            selectors: CSS选择器字典
            
        Returns:
            str: Python代码
        """
        selectors_json = json.dumps(selectors or {}, ensure_ascii=False)
        
        code = f'''
import json
import requests
from bs4 import BeautifulSoup
import sys
import time

try:
    url = "{url}"
    output_format = "{output_format}"
    selectors = {selectors_json}
    
    print(f"开始爬取: {{url}}", flush=True)
    
    # 发送请求
    headers = {{
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }}
    
    response = requests.get(url, headers=headers, timeout=30)
    response.raise_for_status()
    
    print(f"页面获取成功，状态码: {{response.status_code}}", flush=True)
    
    # 解析HTML
    soup = BeautifulSoup(response.text, 'html.parser')
    
    # 提取数据
    scraped_data = {{}}
    
    # 提取标题
    if soup.title:
        scraped_data['title'] = soup.title.string
    
    # 提取所有链接
    links = []
    for link in soup.find_all('a', href=True):
        links.append({{
            'text': link.get_text(strip=True),
            'url': link['href']
        }})
    scraped_data['links'] = links
    
    # 提取所有图片
    images = []
    for img in soup.find_all('img', src=True):
        images.append({{
            'alt': img.get('alt', ''),
            'src': img['src']
        }})
    scraped_data['images'] = images
    
    # 根据选择器提取特定内容
    if selectors:
        for name, selector in selectors.items():
            elements = soup.select(selector)
            scraped_data[name] = [elem.get_text(strip=True) for elem in elements]
    
    # 提取文本内容
    text_content = soup.get_text(separator=' ', strip=True)
    scraped_data['text_content'] = text_content[:1000]  # 限制长度
    
    print("爬取完成，正在保存数据...", flush=True)
    
    # 根据输出格式保存数据
    output_file = f"/tmp/scraped_data.{{output_format}}"
    
    if output_format == 'json':
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(scraped_data, f, ensure_ascii=False, indent=2)
    elif output_format == 'csv':
        import pandas as pd
        # 创建DataFrame
        df_data = []
        for link in scraped_data.get('links', []):
            df_data.append({{
                'type': 'link',
                'text': link['text'],
                'url': link['url']
            }})
        for img in scraped_data.get('images', []):
            df_data.append({{
                'type': 'image',
                'text': img['alt'],
                'url': img['src']
            }})
        
        df = pd.DataFrame(df_data)
        df.to_csv(output_file, index=False, encoding='utf-8')
    else:
        # 文本格式
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(f"Title: {{scraped_data.get('title', 'N/A')}}\\n\\n")
            f.write(f"Text Content:\\n{{scraped_data.get('text_content', '')}}\\n\\n")
            f.write(f"Links ({{len(scraped_data.get('links', []))}}):\\n")
            for link in scraped_data.get('links', []):
                f.write(f"- {{link['text']}}: {{link['url']}}\\n")
    
    print(f"数据已保存到: {{output_file}}", flush=True)
    
    # 构建结果
    result = {{
        "success": True,
        "url": url,
        "output_file": output_file,
        "data": {{
            "title": scraped_data.get('title'),
            "total_links": len(scraped_data.get('links', [])),
            "total_images": len(scraped_data.get('images', [])),
            "text_length": len(scraped_data.get('text_content', '')),
            "selectors_matched": {{k: len(v) for k, v in scraped_data.items() if k not in ['title', 'links', 'images', 'text_content']}}
        }},
        "summary": f"成功爬取 {{url}}，共提取 {{len(scraped_data.get('links', []))}} 个链接，{{len(scraped_data.get('images', []))}} 张图片"
    }}
    
    print(json.dumps(result, ensure_ascii=False, indent=2))
    
except Exception as e:
    result = {{
        "success": False,
        "error": str(e),
        "traceback": traceback.format_exc()
    }}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    sys.exit(1)
'''
        return code