"""
数据同步测试
"""

import asyncio
import pytest
import tempfile
import os
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock

from agent_bridge.data_manager import DataManager
from agent_bridge.connection_manager import ConnectionManager
from agent_bridge.exceptions import DataSyncError


class TestDataManager:
    """数据管理器测试类"""
    
    def setup_method(self):
        """测试前置方法"""
        self.mock_connection = Mock(spec=ConnectionManager)
        self.manager = DataManager(connection_manager=self.mock_connection)
    
    @pytest.mark.asyncio
    async def test_initialization(self):
        """测试初始化"""
        assert self.manager.connection_manager == self.mock_connection
        assert self.manager.sync_metadata_file == ".agent_bridge_sync.json"
    
    @pytest.mark.asyncio
    async def test_sync_to_cloud_single_file(self):
        """测试同步单个文件到云端"""
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
            f.write("test content")
            temp_file = f.name
        
        try:
            # 模拟远程文件检查
            self.mock_connection.execute.side_effect = [
                (1, '', ''),  # 文件不存在
                (0, '', ''),  # 创建目录成功
                (0, '', ''),  # 同步文件成功
            ]
            
            result = await self.manager.sync_to_cloud(temp_file, '/tmp', incremental=True)
            
            assert len(result) == 1
            assert temp_file in result[0]
            
        finally:
            os.unlink(temp_file)
    
    @pytest.mark.asyncio
    async def test_sync_from_cloud(self):
        """测试从云端同步"""
        # 模拟远程文件列表
        self.mock_connection.execute.side_effect = [
            (0, '', ''),  # 路径存在
            (0, '/tmp/test1.txt\n/tmp/test2.txt', ''),  # 文件列表
            (0, '1234567890 100', ''),  # 文件1信息
            (0, '0987654321 200', ''),  # 文件2信息
        ]
        
        with tempfile.TemporaryDirectory() as temp_dir:
            result = await self.manager.sync_from_cloud('/tmp', temp_dir, incremental=True)
            
            assert len(result) == 2
    
    @pytest.mark.asyncio
    async def test_auto_fetch_assets(self):
        """测试自动获取资源文件"""
        # 模拟远程文件
        self.mock_connection.execute.side_effect = [
            (0, '', ''),  # 目录存在
            (0, '/tmp/report.png\n/tmp/data.csv\n/tmp/document.pdf\n/tmp/script.py', ''),  # 文件列表
            (0, '1234567890 100', ''),  # PNG文件信息
            (0, '0987654321 200', ''),  # CSV文件信息
            (0, '1122334455 300', ''),  # PDF文件信息
            (0, '5566778899 400', ''),  # PY文件信息
        ]
        
        with tempfile.TemporaryDirectory() as temp_dir:
            result = await self.manager.auto_fetch_assets('/tmp', temp_dir)
            
            # 应该只获取图片、CSV、PDF文件，不包括Python脚本
            assert len(result) == 3
    
    @pytest.mark.asyncio
    async def test_calculate_file_hash_local(self):
        """测试计算本地文件哈希"""
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
            f.write("test content for hashing")
            temp_file = f.name
        
        try:
            hash_value = self.manager.calculate_file_hash(temp_file, remote=False)
            
            assert len(hash_value) == 32  # MD5哈希长度
            assert hash_value != ""
            
        finally:
            os.unlink(temp_file)
    
    @pytest.mark.asyncio
    async def test_calculate_sync_files(self):
        """测试计算需要同步的文件"""
        # 源文件信息
        source_files = {
            Path('/file1.txt'): {'hash': 'abc123', 'mtime': 1000, 'size': 100},
            Path('/file2.txt'): {'hash': 'def456', 'mtime': 1001, 'size': 200},
            Path('/file3.txt'): {'hash': 'ghi789', 'mtime': 1002, 'size': 300},
        }
        
        # 目标文件信息（file2.txt哈希不同）
        target_files = {
            Path('/file1.txt'): {'hash': 'abc123', 'mtime': 1000, 'size': 100},
            Path('/file2.txt'): {'hash': 'different_hash', 'mtime': 1000, 'size': 200},
        }
        
        files_to_sync = self.manager._calculate_sync_files(source_files, target_files)
        
        # file1.txt 相同，不需要同步
        # file2.txt 哈希不同，需要同步
        # file3.txt 目标中不存在，需要同步
        assert len(files_to_sync) == 2
        assert Path('/file2.txt') in files_to_sync
        assert Path('/file3.txt') in files_to_sync
    
    @pytest.mark.asyncio
    async def test_create_remote_directories(self):
        """测试创建远程目录"""
        file_paths = [
            Path('/base/dir1/file1.txt'),
            Path('/base/dir1/file2.txt'),
            Path('/base/dir2/subdir/file3.txt'),
        ]
        
        await self.manager._create_remote_directories('/base', file_paths)
        
        # 验证创建了正确的目录
        calls = self.mock_connection.execute.call_args_list
        directories_created = set()
        for call in calls:
            command = call[0][0]
            if 'mkdir -p' in command:
                dir_path = command.replace('mkdir -p ', '').strip()
                directories_created.add(dir_path)
        
        assert '/base/dir1' in directories_created
        assert '/base/dir2/subdir' in directories_created
    
    @pytest.mark.asyncio
    async def test_update_sync_metadata(self):
        """测试更新同步元数据"""
        files_info = {
            Path('/file1.txt'): {'hash': 'abc123', 'mtime': 1000, 'size': 100},
            Path('/file2.txt'): {'hash': 'def456', 'mtime': 1001, 'size': 200},
        }
        
        await self.manager._update_sync_metadata('/tmp', files_info)
        
        # 验证元数据文件已创建
        call_args = self.mock_connection.execute.call_args
        command = call_args[0][0]
        assert '.agent_bridge_sync.json' in command
        assert 'abc123' in command  # 哈希值应该包含在JSON中


class TestFileHashCalculation:
    """文件哈希计算测试"""
    
    @pytest.mark.asyncio
    async def test_calculate_remote_file_hash(self):
        """测试计算远程文件哈希"""
        mock_connection = Mock()
        manager = DataManager(connection_manager=mock_connection)
        
        mock_connection.execute.return_value = (0, 'abc123def456', '')
        
        hash_value = await manager.calculate_file_hash('/tmp/test.txt', remote=True)
        
        assert hash_value == 'abc123def456'
        mock_connection.execute.assert_called_with('md5sum /tmp/test.txt | cut -d\' \' -f1')
    
    @pytest.mark.asyncio
    async def test_calculate_remote_file_hash_error(self):
        """测试计算远程文件哈希失败"""
        mock_connection = Mock()
        manager = DataManager(connection_manager=mock_connection)
        
        mock_connection.execute.return_value = (1, '', 'File not found')
        
        hash_value = await manager.calculate_file_hash('/tmp/nonexistent.txt', remote=True)
        
        assert hash_value == ""


class TestSyncErrorHandling:
    """同步错误处理测试"""
    
    @pytest.mark.asyncio
    async def test_sync_to_cloud_invalid_path(self):
        """测试同步不存在的路径"""
        mock_connection = Mock()
        manager = DataManager(connection_manager=mock_connection)
        
        with pytest.raises(DataSyncError):
            await manager.sync_to_cloud('/nonexistent/path', '/tmp')
    
    @pytest.mark.asyncio
    async def test_sync_error_propagation(self):
        """测试错误传播"""
        mock_connection = Mock()
        manager = DataManager(connection_manager=mock_connection)
        
        # 模拟执行失败
        mock_connection.execute.side_effect = Exception("Connection failed")
        
        with tempfile.NamedTemporaryFile() as f:
            with pytest.raises(DataSyncError):
                await manager.sync_to_cloud(f.name, '/tmp')