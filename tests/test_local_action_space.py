import pytest
import pytest_asyncio
import asyncio
import os
import shutil
from pathlib import Path
from yoga_next.environments import LocalCondaEnvironment
from yoga_next.actions import LocalActionSpace


@pytest_asyncio.fixture(scope="module")
async def action_space():
    """初始化环境和 ActionSpace 的 Fixture"""
    test_workspace = Path("./test_workspace").resolve()
    test_workspace.mkdir(exist_ok=True)
    
    config = {
        "env_name": "test_yoga_env",
        "workspace_root": str(test_workspace),
        "python_version": "3.10"
    }
    
    env = LocalCondaEnvironment(config)
    
    as_instance = LocalActionSpace(action_space_name="local_cmd", env=env)
    
    yield as_instance
    
    await as_instance.close()
    if test_workspace.exists():
        shutil.rmtree(test_workspace)


@pytest.mark.asyncio
async def test_file_operations(action_space):
    """测试文件读写和列表显示"""
    write_res = await action_space.execute("write_file", {
        "path": "hello.txt",
        "content": "Hello Yoga Agent!"
    })
    assert write_res["status"] == "success"
    
    read_res = await action_space.execute("read_file", {"path": "hello.txt"})
    assert read_res["status"] == "success"
    assert "Hello Yoga Agent!" in read_res["output"]["stdout"]
    
    list_res = await action_space.execute("list_directory", {"path": "."})
    assert list_res["status"] == "success"
    assert "hello.txt" in list_res["output"]["stdout"]


@pytest.mark.asyncio
async def test_python_execution(action_space):
    """测试 Conda 环境中的 Python 运行"""
    code = "import math; print(f'PI is {math.pi:.2f}')"
    res = await action_space.execute("execute_python", {"code": code})
    
    assert res["status"] == "success"
    assert "PI is 3.14" in res["output"]["stdout"]


@pytest.mark.asyncio
async def test_shell_execution(action_space):
    """测试 Shell 命令执行"""
    res = await action_space.execute("execute_shell", {"command": "echo 'ActionSpace Test'"})
    assert res["status"] == "success"
    assert "ActionSpace Test" in res["output"]["stdout"]


@pytest.mark.asyncio
async def test_sandbox_security(action_space):
    """测试路径安全校验（防止越权读取）"""
    res = await action_space.execute("read_file", {"path": "/etc/passwd"})
    assert res["status"] == "error"
