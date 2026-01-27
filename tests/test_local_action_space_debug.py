import asyncio
import os
import shutil
from pathlib import Path
from yoga_next.environments import LocalCondaEnvironment
from yoga_next.actions import LocalActionSpace


async def main():
    test_workspace = Path("./test_workspace").resolve()
    test_workspace.mkdir(exist_ok=True)
    
    config = {
        "env_name": "test_yoga_env",
        "workspace_root": str(test_workspace),
        "python_version": "3.10"
    }
    
    env = LocalCondaEnvironment(config)
    action_space = LocalActionSpace(action_space_name="local_cmd", env=env)
    
    print("=" * 50)
    print("Test 1: File Operations")
    print("=" * 50)
    
    write_res = await action_space.execute("write_file", {
        "path": "hello.txt",
        "content": "Hello Yoga Agent!"
    })
    print(f"write_file status: {write_res['status']}")
    assert write_res["status"] == "success", f"write_file failed: {write_res}"
    
    read_res = await action_space.execute("read_file", {"path": "hello.txt"})
    print(f"read_file status: {read_res['status']}")
    print(f"read_file output: {read_res['output']}")
    assert read_res["status"] == "success", f"read_file failed: {read_res}"
    assert "Hello Yoga Agent!" in read_res["output"]["stdout"], "Content mismatch"
    
    list_res = await action_space.execute("list_directory", {"path": "."})
    print(f"list_directory status: {list_res['status']}")
    print(f"list_directory output: {list_res['output']}")
    assert list_res["status"] == "success", f"list_directory failed: {list_res}"
    assert "hello.txt" in list_res["output"]["stdout"], "File not in listing"
    
    print("\n✅ File operations test passed!")
    
    print("\n" + "=" * 50)
    print("Test 2: Shell Execution")
    print("=" * 50)
    
    shell_res = await action_space.execute("execute_shell", {"command": "echo 'ActionSpace Test'"})
    print(f"execute_shell status: {shell_res['status']}")
    print(f"execute_shell output: {shell_res['output']}")
    assert shell_res["status"] == "success", f"execute_shell failed: {shell_res}"
    assert "ActionSpace Test" in shell_res["output"]["stdout"], "Shell output mismatch"
    
    print("\n✅ Shell execution test passed!")
    
    print("\n" + "=" * 50)
    print("Test 3: Sandbox Security")
    print("=" * 50)
    
    security_res = await action_space.execute("read_file", {"path": "/etc/passwd"})
    print(f"read_file (restricted) status: {security_res['status']}")
    print(f"read_file (restricted) message: {security_res.get('message', '')}")
    assert security_res["status"] == "error", "Should reject path outside workspace"

    print("\n✅ Sandbox security test passed!")
    
    print("\n" + "=" * 50)
    print("Test 4: Python Execution")
    print("=" * 50)
    
    code = "import math; print(f'PI is {math.pi:.2f}')"
    py_res = await action_space.execute("execute_python", {"code": code})
    print(f"execute_python status: {py_res['status']}")
    print(f"execute_python output: {py_res['output']}")
    assert py_res["status"] == "success", f"execute_python failed: {py_res}"
    assert "PI is 3.14" in py_res["output"]["stdout"], "Python output mismatch"
    
    print("\n✅ Python execution test passed!")
    
    await action_space.close()
    
    if test_workspace.exists():
        shutil.rmtree(test_workspace)
    
    print("\n" + "=" * 50)
    print("All tests passed! ✅")
    print("=" * 50)


if __name__ == "__main__":
    asyncio.run(main())
