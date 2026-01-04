"""
数据管理器：处理本地与云端的数据同步
"""

import asyncio
import hashlib
import json
import logging
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

from .connection_manager import ConnectionManager
from .exceptions import DataSyncError

logger = logging.getLogger(__name__)


class DataManager:
    """
    管理本地与云端的数据同步，支持增量同步
    """
    
    def __init__(self, connection_manager: ConnectionManager):
        """
        初始化数据管理器
        
        Args:
            connection_manager: SSH连接管理器
        """
        self.connection_manager = connection_manager
        self.sync_metadata_file = ".agent_bridge_sync.json"

    async def sync_to_cloud(self, local_path: str, remote_path: str, 
                           incremental: bool = True) -> List[str]:
        """
        将本地文件/目录同步到云端，行为类似挂载：本地路径完整映射到远程路径
        
        Args:
            local_path: 本地文件或目录路径
            remote_path: 云端目标路径（完整映射路径）
            incremental: 是否使用增量同步，默认True
            
        Returns:
            List[str]: 已同步的文件列表
            
        Raises:
            DataSyncError: 同步失败时抛出
        """
        try:
            local_path = Path(local_path)
            if not local_path.exists():
                raise DataSyncError(f"本地路径不存在: {local_path}")
            
            # 获取本地文件列表
            local_files = self._get_local_files_info(local_path)
            
            if incremental:
                # 获取云端文件信息
                remote_files = await self._get_remote_files_info(remote_path)
                
                # 计算需要同步的文件（基于哈希和时间戳）
                files_to_sync = self._calculate_sync_files(local_files, remote_files)
            else:
                # 全量同步
                files_to_sync = list(local_files.keys())
            
            if not files_to_sync:
                logger.info("所有文件已是最新，无需同步")
                return []
            
            # 创建远程目录结构（基于本地目录结构映射到远程）
            await self._create_remote_directories_mount(remote_path, files_to_sync, local_path)
            
            # 同步文件
            synced_files = []
            for file_path in files_to_sync:
                # 计算相对于本地根目录的路径
                relative_path = file_path.relative_to(local_path)
                
                # 构建远程目标路径：remote_path + 相对路径
                if relative_path == Path("."):  # 如果是单个文件（非目录）
                    target_path = Path(remote_path)
                else:
                    target_path = Path(remote_path) / relative_path
                
                logger.info(f"同步文件: {file_path} -> {target_path}")
                
                if await self._sync_single_file(str(file_path), str(target_path)):
                    synced_files.append(str(file_path))
            
            # 更新同步元数据
            if incremental:
                await self._update_sync_metadata(remote_path, local_files)
            
            logger.info(f"同步完成: {len(synced_files)} 个文件已同步")
            return synced_files
            
        except Exception as e:
            raise DataSyncError(f"同步到云端失败: {str(e)}")
    
    async def sync_from_cloud(self, remote_path: str, local_path: str,
                             incremental: bool = True) -> List[str]:
        """
        将云端文件/目录同步到本地，行为类似挂载：云端路径完整映射到本地路径
        
        Args:
            remote_path: 云端文件或目录路径
            local_path: 本地目标路径（完整映射路径）
            incremental: 是否使用增量同步，默认True
            
        Returns:
            List[str]: 已同步的文件列表
            
        Raises:
            DataSyncError: 同步失败时抛出
        """
        try:
            remote_path_obj = Path(remote_path)
            local_path_obj = Path(local_path)

            # 获取云端文件信息
            remote_files = await self._get_remote_files_info(str(remote_path_obj))
            
            if not remote_files:
                logger.info("云端路径为空或不存在")
                return []
            
            if incremental:
                # 获取本地文件信息
                local_files = {}
                if local_path_obj.exists():
                    local_files = self._get_local_files_info(local_path_obj)
                
                # 计算需要同步的文件
                files_to_sync = self._calculate_sync_files(remote_files, local_files)
            else:
                # 全量同步
                files_to_sync = list(remote_files.keys())
            
            if not files_to_sync:
                logger.info("所有文件已是最新，无需同步")
                return []

            # 创建本地目录结构（基于云端目录结构映射到本地）
            await self._create_local_directories_mount(local_path, files_to_sync, remote_path_obj)
            
            # 同步文件
            synced_files = []
            for file_path in files_to_sync:
                # 计算相对于云端根目录的路径
                relative_path = file_path.relative_to(remote_path_obj)
                
                # 构建本地目标路径：local_path + 相对路径
                if relative_path == Path("."):  # 如果是单个文件（非目录）
                    target_path = Path(local_path)
                else:
                    target_path = Path(local_path) / relative_path
                
                logger.info(f"同步文件: {file_path} -> {target_path}")
                
                if await self._sync_single_file_from_remote(str(file_path), str(target_path)):
                    synced_files.append(str(file_path))
            
            logger.info(f"同步完成: {len(synced_files)} 个文件已同步")
            return synced_files
            
        except Exception as e:
            raise DataSyncError(f"从云端同步失败: {str(e)}")
    
    async def auto_fetch_assets(self, remote_dir: str, local_dir: str,
                               asset_patterns: Optional[List[str]] = None) -> List[str]:
        """
        自动识别并同步云端生成的资源文件到本地
        
        Args:
            remote_dir: 云端目录路径
            local_dir: 本地目标目录
            asset_patterns: 资源文件模式列表，默认支持图片、PDF、CSV等
            
        Returns:
            List[str]: 已同步的资源文件列表
            
        Raises:
            DataSyncError: 同步失败时抛出
        """
        if asset_patterns is None:
            asset_patterns = [
                r'.*\.png$', r'.*\.jpg$', r'.*\.jpeg$', r'.*\.gif$', r'.*\.svg$',
                r'.*\.pdf$', r'.*\.csv$', r'.*\.xlsx$', r'.*\.xls$',
                r'.*\.json$', r'.*\.xml$', r'.*\.txt$', r'.*\.md$'
            ]
        
        try:
            # 获取云端所有文件
            remote_files = await self._get_remote_files_info(remote_dir)
            
            # 筛选资源文件
            asset_files = []
            for file_path, file_info in remote_files.items():
                file_name = str(file_path)
                for pattern in asset_patterns:
                    if re.match(pattern, file_name, re.IGNORECASE):
                        asset_files.append(file_path)
                        break
            
            if not asset_files:
                logger.info("未找到资源文件")
                return []
            
            logger.info(f"发现 {len(asset_files)} 个资源文件")
            
            # 创建本地目录结构
            await self._create_local_directories_mount(local_dir, asset_files, Path(remote_dir))
            
            # 同步资源文件
            synced_assets = []
            remote_dir_path = Path(remote_dir)
            for asset_file in asset_files:
                # 计算相对于云端根目录的路径
                relative_path = asset_file.relative_to(remote_dir_path)
                
                # 构建本地目标路径
                if relative_path == Path("."):  # 如果是单个文件（非目录）
                    local_target_path = Path(local_dir)
                else:
                    local_target_path = Path(local_dir) / relative_path
                
                logger.info(f"同步资源文件: {asset_file} -> {local_target_path}")
                
                if await self._sync_single_file_from_remote(str(asset_file), str(local_target_path)):
                    synced_assets.append(str(asset_file))
            
            logger.info(f"资源文件同步完成: {len(synced_assets)} 个文件")
            return synced_assets
            
        except Exception as e:
            raise DataSyncError(f"资源文件同步失败: {str(e)}")
    
    async def calculate_file_hash(self, file_path: str, remote: bool = False) -> str:
        """
        计算文件哈希值
        
        Args:
            file_path: 文件路径
            remote: 是否为远程文件，默认False
            
        Returns:
            str: 文件哈希值
        """
        if remote:
            return await self._calculate_remote_file_hash(file_path)
        else:
            return self._calculate_local_file_hash(file_path)
    
    def _get_local_files_info(self, local_path: Path) -> Dict[Path, Dict[str, Any]]:
        """
        获取本地文件信息
        
        Args:
            local_path: 本地路径
            
        Returns:
            Dict[Path, Dict[str, Any]]: 文件信息字典
        """
        files_info = {}
        
        if local_path.is_file():
            files_info[local_path] = {
                'hash': self._calculate_local_file_hash(str(local_path)),
                'mtime': os.path.getmtime(str(local_path)),
                'size': os.path.getsize(str(local_path))
            }
        elif local_path.is_dir():
            for root, dirs, files in os.walk(str(local_path)):
                for file in files:
                    file_path = Path(root) / file
                    files_info[file_path] = {
                        'hash': self._calculate_local_file_hash(str(file_path)),
                        'mtime': os.path.getmtime(str(file_path)),
                        'size': os.path.getsize(str(file_path))
                    }
        
        return files_info
    
    async def _get_remote_files_info(self, remote_path: str) -> Dict[Path, Dict[str, Any]]:
        """
        获取远程文件信息
        
        Args:
            remote_path: 远程路径
            
        Returns:
            Dict[Path, Dict[str, Any]]: 文件信息字典
        """
        files_info = {}
        
        try:
            # 检查路径是否存在
            exit_code, _, _ = await self.connection_manager.execute(
                f"test -e {remote_path}"
            )
            
            if exit_code != 0:
                return files_info
            
            # 检查是文件还是目录
            exit_code, _, _ = await self.connection_manager.execute(
                f"test -f {remote_path}"
            )
            
            if exit_code == 0:
                # 是文件
                file_info = await self._get_remote_file_info(remote_path)
                if file_info:
                    files_info[Path(remote_path)] = file_info
            else:
                # 是目录，获取所有文件
                exit_code, stdout, stderr = await self.connection_manager.execute(
                    f"find {remote_path} -type f"
                )
                
                if exit_code == 0 and stdout:
                    for file_path in stdout.strip().split('\n'):
                        if file_path.strip():
                            file_info = await self._get_remote_file_info(file_path.strip())
                            if file_info:
                                files_info[Path(file_path.strip())] = file_info
            
            return files_info
            
        except Exception as e:
            logger.error(f"获取远程文件信息失败: {str(e)}")
            return files_info
    
    async def _get_remote_file_info(self, file_path: str) -> Optional[Dict[str, Any]]:
        """
        获取单个远程文件信息
        
        Args:
            file_path: 文件路径
            
        Returns:
            Optional[Dict[str, Any]]: 文件信息或None
        """
        try:
            exit_code, stdout, stderr = await self.connection_manager.execute(
                f"stat -c '%Y %s' {file_path}"
            )
            
            if exit_code == 0 and stdout:
                mtime, size = stdout.strip().split()
                return {
                    'hash': await self._calculate_remote_file_hash(file_path),
                    'mtime': float(mtime),
                    'size': int(size)
                }
            
            return None
            
        except Exception as e:
            logger.error(f"获取远程文件信息失败 {file_path}: {str(e)}")
            return None
    
    def _calculate_local_file_hash(self, file_path: str) -> str:
        """
        计算本地文件哈希值
        
        Args:
            file_path: 文件路径
            
        Returns:
            str: 文件哈希值
        """
        hasher = hashlib.md5()
        try:
            with open(file_path, 'rb') as f:
                while chunk := f.read(8192):
                    hasher.update(chunk)
        except Exception as e:
            logger.error(f"计算本地文件哈希失败 {file_path}: {str(e)}")
            return ""
        return hasher.hexdigest()
    
    async def _calculate_remote_file_hash(self, file_path: str) -> str:
        """
        计算远程文件哈希值
        
        Args:
            file_path: 文件路径
            
        Returns:
            str: 文件哈希值
        """
        try:
            exit_code, stdout, stderr = await self.connection_manager.execute(
                f"md5sum {file_path} | cut -d' ' -f1"
            )
            
            if exit_code == 0 and stdout:
                return stdout.strip()
            else:
                return ""
                
        except Exception as e:
            logger.error(f"计算远程文件哈希失败 {file_path}: {str(e)}")
            return ""
    
    def _calculate_sync_files(self, source_files: Dict[Path, Dict], 
                             target_files: Dict[Path, Dict]) -> List[Path]:
        """
        计算需要同步的文件
        
        Args:
            source_files: 源文件信息
            target_files: 目标文件信息
            
        Returns:
            List[Path]: 需要同步的文件列表
        """
        files_to_sync = []
        
        for file_path, source_info in source_files.items():
            if file_path not in target_files:
                # 目标中不存在，需要同步
                files_to_sync.append(file_path)
            else:
                target_info = target_files[file_path]
                
                # 检查哈希值
                if source_info['hash'] != target_info['hash']:
                    files_to_sync.append(file_path)
                # 或者检查修改时间（如果哈希不可用）
                elif source_info['hash'] == "" and source_info['mtime'] > target_info['mtime']:
                    files_to_sync.append(file_path)
        
        return files_to_sync

    # ========================
    # ✅ 新增：SFTP 辅助方法
    # ========================
    def _mkdir_p_sftp(self, sftp, remote_directory: str):
        """递归创建远程目录（兼容 SFTP）"""
        if remote_directory == '/':
            return
        try:
            sftp.stat(remote_directory)
        except FileNotFoundError:
            parent = os.path.dirname(remote_directory)
            self._mkdir_p_sftp(sftp, parent)
            try:
                sftp.mkdir(remote_directory)
                logger.debug(f"创建远程目录: {remote_directory}")
            except Exception as e:
                # 可能已被其他进程创建，忽略
                logger.debug(f"创建远程目录时异常（可能已存在）: {remote_directory}, error: {e}")

    # ========================
    # ✅ 替换：使用 SFTP 上传
    # ========================
    async def _sync_single_file(self, local_path: str, remote_path: str) -> bool:
        """
        同步单个文件到云端（使用 SFTP）
        
        Args:
            local_path: 本地文件路径
            remote_path: 远程文件路径
            
        Returns:
            bool: 同步成功返回True
        """
        try:
            if not os.path.isfile(local_path):
                logger.error(f"本地文件不存在: {local_path}")
                return False

            sftp = self.connection_manager.get_sftp()

            # 确保远程目录存在
            remote_dir = os.path.dirname(remote_path)
            if remote_dir:
                self._mkdir_p_sftp(sftp, remote_dir)

            # 上传文件
            sftp.put(local_path, remote_path)
            logger.debug(f"文件同步成功: {local_path} -> {remote_path}")
            return True

        except Exception as e:
            logger.error(f"文件同步失败（上传）: {str(e)}")
            return False

    # ========================
    # ✅ 替换：使用 SFTP 下载
    # ========================
    async def _sync_single_file_from_remote(self, remote_path: str, local_path: str) -> bool:
        """
        从云端同步单个文件到本地（使用 SFTP）
        
        Args:
            remote_path: 远程文件路径
            local_path: 本地文件路径
            
        Returns:
            bool: 同步成功返回True
        """
        try:
            # 创建本地目录
            os.makedirs(os.path.dirname(local_path), exist_ok=True)

            sftp = self.connection_manager.get_sftp()

            # 下载文件
            sftp.get(remote_path, local_path)
            logger.debug(f"文件同步成功: {remote_path} -> {local_path}")
            return True

        except Exception as e:
            logger.error(f"文件同步失败（下载）: {str(e)}")
            return False

    # ========================
    # ✅ 修正：创建远程目录结构（mount模式）
    # ========================
    async def _create_remote_directories_mount(self, remote_base_path: str, file_paths: List[Path], local_base_path: Path) -> None:
        """
        根据本地目录结构创建远程目录（mount模式）
        
        Args:
            remote_base_path: 远程基础路径
            file_paths: 本地文件路径列表
            local_base_path: 本地基础路径（用于计算相对路径）
        """
        remote_dirs_to_create = set()
        
        for file_path in file_paths:
            # 计算相对于本地基础路径的相对路径
            relative_path = file_path.relative_to(local_base_path)
            
            # 如果是文件路径，获取其父目录
            if relative_path != Path("."):  # 不是单个文件的情况
                parent_dir = relative_path.parent
                # 构建对应的远程目录路径
                remote_dir = Path(remote_base_path) / parent_dir
                remote_dirs_to_create.add(str(remote_dir))
        
        # 按路径深度排序，确保父目录先创建
        sorted_dirs = sorted(remote_dirs_to_create, key=lambda x: x.count('/'))
        
        # 批量创建远程目录
        for remote_dir in sorted_dirs:
            await self.connection_manager.execute(f"mkdir -p {remote_dir}")

    # ========================
    # ✅ 修正：创建本地目录结构（mount模式）
    # ========================
    async def _create_local_directories_mount(self, local_base_path: str, file_paths: List[Path], remote_base_path: Path) -> None:
        """
        根据远程目录结构创建本地目录（mount模式）
        
        Args:
            local_base_path: 本地基础路径
            file_paths: 远程文件路径列表
            remote_base_path: 远程基础路径（用于计算相对路径）
        """
        local_dirs_to_create = set()
        
        for file_path in file_paths:
            # 计算相对于远程基础路径的相对路径
            relative_path = file_path.relative_to(remote_base_path)
            
            # 如果是文件路径，获取其父目录
            if relative_path != Path("."):  # 不是单个文件的情况
                parent_dir = relative_path.parent
                # 构建对应的本地目录路径
                local_dir = Path(local_base_path) / parent_dir
                local_dirs_to_create.add(str(local_dir))
        
        # 按路径深度排序，确保父目录先创建
        sorted_dirs = sorted(local_dirs_to_create, key=lambda x: x.count('/'))
        
        # 批量创建本地目录
        for local_dir in sorted_dirs:
            os.makedirs(local_dir, exist_ok=True)
    
    # 保留旧方法以兼容其他可能的调用（但已不再使用）
    async def _create_remote_directories(self, base_path: str, file_paths: List[Path]) -> None:
        """
        旧方法：创建远程目录结构（兼容旧逻辑，但不再使用）
        """
        directories = set()
        for file_path in file_paths:
            relative_path = file_path.relative_to(Path(base_path).parent)
            dir_path = Path(base_path) / relative_path.parent
            directories.add(str(dir_path))
        
        for directory in directories:
            await self.connection_manager.execute(f"mkdir -p {directory}")
    
    async def _create_local_directories(self, base_path: str, file_paths: List[Path]) -> None:
        """
        旧方法：创建本地目录结构（兼容旧逻辑，但不再使用）
        """
        directories = set()
        for file_path in file_paths:
            relative_path = file_path.relative_to(Path(base_path).parent)
            dir_path = Path(base_path) / relative_path.parent
            directories.add(str(dir_path))
        
        for directory in directories:
            os.makedirs(directory, exist_ok=True)
    
    async def _update_sync_metadata(self, remote_path: str, files_info: Dict[Path, Dict]) -> None:
        """
        更新同步元数据
        
        Args:
            remote_path: 远程路径
            files_info: 文件信息字典
        """
        try:
            metadata = {
                'sync_time': datetime.now().isoformat(),
                'files': {str(path): info for path, info in files_info.items()}
            }
            
            metadata_json = json.dumps(metadata, indent=2)
            
            # 保存元数据到远程
            metadata_path = Path(remote_path) / self.sync_metadata_file
            await self.connection_manager.execute(
                f"echo '{metadata_json}' > {metadata_path}"
            )
            
        except Exception as e:
            logger.warning(f"更新同步元数据失败: {str(e)}")