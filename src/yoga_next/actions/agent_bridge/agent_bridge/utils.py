"""
工具函数模块
"""

import asyncio
import logging
import os
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def setup_logging(level: str = "INFO", log_file: Optional[str] = None) -> None:
    """
    设置日志配置
    
    Args:
        level: 日志级别，默认INFO
        log_file: 日志文件路径，可选
    """
    log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    
    if log_file:
        logging.basicConfig(
            level=getattr(logging, level.upper()),
            format=log_format,
            handlers=[
                logging.FileHandler(log_file),
                logging.StreamHandler()
            ]
        )
    else:
        logging.basicConfig(
            level=getattr(logging, level.upper()),
            format=log_format
        )


def load_env_file(env_file: str = ".env") -> Dict[str, str]:
    """
    加载环境变量文件
    
    Args:
        env_file: 环境变量文件路径
        
    Returns:
        Dict[str, str]: 环境变量字典
    """
    env_vars = {}
    
    if os.path.exists(env_file):
        with open(env_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    env_vars[key.strip()] = value.strip()
    
    return env_vars


def save_temp_file(content: str, suffix: str = ".py") -> str:
    """
    保存临时文件
    
    Args:
        content: 文件内容
        suffix: 文件后缀，默认.py
        
    Returns:
        str: 临时文件路径
    """
    with tempfile.NamedTemporaryFile(mode='w', suffix=suffix, delete=False, encoding='utf-8') as f:
        f.write(content)
        return f.name


def read_file_content(file_path: str) -> str:
    """
    读取文件内容
    
    Args:
        file_path: 文件路径
        
    Returns:
        str: 文件内容
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        logger.error(f"读取文件失败 {file_path}: {str(e)}")
        return ""


def format_file_size(size_bytes: int) -> str:
    """
    格式化文件大小
    
    Args:
        size_bytes: 文件大小（字节）
        
    Returns:
        str: 格式化后的文件大小
    """
    if size_bytes == 0:
        return "0 B"
    
    size_names = ["B", "KB", "MB", "GB", "TB"]
    i = 0
    size = float(size_bytes)
    
    while size >= 1024.0 and i < len(size_names) - 1:
        size /= 1024.0
        i += 1
    
    return f"{size:.2f} {size_names[i]}"


def create_directory_if_not_exists(directory: str) -> bool:
    """
    创建目录（如果不存在）
    
    Args:
        directory: 目录路径
        
    Returns:
        bool: 创建成功返回True
    """
    try:
        Path(directory).mkdir(parents=True, exist_ok=True)
        return True
    except Exception as e:
        logger.error(f"创建目录失败 {directory}: {str(e)}")
        return False


def get_file_extension(file_path: str) -> str:
    """
    获取文件扩展名
    
    Args:
        file_path: 文件路径
        
    Returns:
        str: 文件扩展名（包含点）
    """
    return Path(file_path).suffix


def is_binary_file(file_path: str) -> bool:
    """
    判断是否为二进制文件
    
    Args:
        file_path: 文件路径
        
    Returns:
        bool: 是二进制文件返回True
    """
    try:
        with open(file_path, 'rb') as f:
            chunk = f.read(1024)
            return b'\0' in chunk
    except Exception:
        return True


def sanitize_filename(filename: str) -> str:
    """
    清理文件名中的非法字符
    
    Args:
        filename: 原始文件名
        
    Returns:
        str: 清理后的文件名
    """
    import re
    # 移除或替换非法字符
    filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
    filename = filename.strip('. ')
    return filename


def chunk_list(lst: List[Any], chunk_size: int) -> List[List[Any]]:
    """
    将列表分块
    
    Args:
        lst: 原始列表
        chunk_size: 每块大小
        
    Returns:
        List[List[Any]]: 分块后的列表
    """
    return [lst[i:i + chunk_size] for i in range(0, len(lst), chunk_size)]


def truncate_text(text: str, max_length: int = 100) -> str:
    """
    截断文本
    
    Args:
        text: 原始文本
        max_length: 最大长度
        
    Returns:
        str: 截断后的文本
    """
    if len(text) <= max_length:
        return text
    return text[:max_length - 3] + "..."


def merge_dicts(*dicts: Dict[str, Any]) -> Dict[str, Any]:
    """
    合并多个字典
    
    Args:
        *dicts: 要合并的字典
        
    Returns:
        Dict[str, Any]: 合并后的字典
    """
    result = {}
    for d in dicts:
        result.update(d)
    return result


def filter_dict_by_keys(d: Dict[str, Any], keys: List[str]) -> Dict[str, Any]:
    """
    根据键列表过滤字典
    
    Args:
        d: 原始字典
        keys: 要保留的键列表
        
    Returns:
        Dict[str, Any]: 过滤后的字典
    """
    return {k: v for k, v in d.items() if k in keys}


def get_nested_dict_value(d: Dict[str, Any], key_path: str, default: Any = None) -> Any:
    """
    获取嵌套字典中的值
    
    Args:
        d: 字典
        key_path: 键路径（使用点号分隔）
        default: 默认值
        
    Returns:
        Any: 键对应的值或默认值
    """
    keys = key_path.split('.')
    current = d
    
    for key in keys:
        if isinstance(current, dict) and key in current:
            current = current[key]
        else:
            return default
    
    return current


def set_nested_dict_value(d: Dict[str, Any], key_path: str, value: Any) -> None:
    """
    设置嵌套字典中的值
    
    Args:
        d: 字典
        key_path: 键路径（使用点号分隔）
        value: 要设置的值
    """
    keys = key_path.split('.')
    current = d
    
    for key in keys[:-1]:
        if key not in current:
            current[key] = {}
        current = current[key]
    
    current[keys[-1]] = value


def remove_nested_dict_key(d: Dict[str, Any], key_path: str) -> bool:
    """
    删除嵌套字典中的键
    
    Args:
        d: 字典
        key_path: 键路径（使用点号分隔）
        
    Returns:
        bool: 删除成功返回True
    """
    keys = key_path.split('.')
    current = d
    
    for key in keys[:-1]:
        if isinstance(current, dict) and key in current:
            current = current[key]
        else:
            return False
    
    if isinstance(current, dict) and keys[-1] in current:
        del current[keys[-1]]
        return True
    
    return False