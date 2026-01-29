import asyncio
import json
import uuid
import os
from typing import Dict, Any, Optional
from pathlib import Path


class ElectronBridge:
    """Bridge for communicating with Electron main process via stdin/stdout."""

    def __init__(self, workspace_root: str):
        self.workspace_root = workspace_root
        self.pending_requests: Dict[str, asyncio.Future] = {}
        self._reader_task: Optional[asyncio.Task] = None
        self._writer_task: Optional[asyncio.Task] = None
        self._running = False

    async def connect(self) -> bool:
        """Establish connection with Electron."""
        self._running = True
        self._reader_task = asyncio.create_task(self._read_responses())
        return True

    async def disconnect(self) -> None:
        """Disconnect from Electron."""
        self._running = False
        if self._reader_task:
            self._reader_task.cancel()
            try:
                await self._reader_task
            except asyncio.CancelledError:
                pass

    async def _read_responses(self) -> None:
        """Read JSON responses from Electron stdout."""
        while self._running:
            try:
                line = await asyncio.get_event_loop().run_in_executor(
                    None, lambda: input()
                )
                if line.strip():
                    await self._handle_response(json.loads(line))
            except json.JSONDecodeError:
                pass
            except Exception:
                break

    async def _handle_response(self, response: Dict[str, Any]) -> None:
        """Handle incoming response and resolve pending futures."""
        call_id = response.get("call_id")
        if call_id and call_id in self.pending_requests:
            future = self.pending_requests.pop(call_id)
            if not future.done():
                future.set_result(response)

    async def send_request(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Send a request to Electron and wait for response."""
        call_id = str(uuid.uuid4())
        payload["call_id"] = call_id

        future = asyncio.get_event_loop().create_future()
        self.pending_requests[call_id] = future

        try:
            print(json.dumps(payload))
            await asyncio.wait_for(future, timeout=60.0)
            return future.result()
        except asyncio.TimeoutError:
            self.pending_requests.pop(call_id, None)
            return {"status": "error", "message": "Request timed out"}
        except Exception as e:
            self.pending_requests.pop(call_id, None)
            return {"status": "error", "message": str(e)}

    async def wait_for_user_approval(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Send a request requiring user approval and wait for response."""
        payload["requires_approval"] = True
        return await self.send_request(payload)


class WebSocketBridge:
    """WebSocket bridge for communicating with Electron."""

    def __init__(self, workspace_root: str, ws_url: str = "ws://localhost:8765"):
        self.workspace_root = workspace_root
        self.ws_url = ws_url
        self.ws = None
        self.pending_requests: Dict[str, asyncio.Future] = {}
        self._running = False
        self._receive_task: Optional[asyncio.Task] = None

    async def connect(self) -> bool:
        """Establish WebSocket connection."""
        try:
            import websockets
            self.ws = await websockets.connect(self.ws_url)
            self._running = True
            self._receive_task = asyncio.create_task(self._receive_messages())
            return True
        except Exception:
            return False

    async def disconnect(self) -> None:
        """Disconnect WebSocket."""
        self._running = False
        if self._receive_task:
            self._receive_task.cancel()
            try:
                await self._receive_task
            except asyncio.CancelledError:
                pass
        if self.ws:
            await self.ws.close()

    async def _receive_messages(self) -> None:
        """Receive and handle messages from WebSocket."""
        async for message in self.ws:
            if not self._running:
                break
            try:
                response = json.loads(message)
                await self._handle_response(response)
            except json.JSONDecodeError:
                pass

    async def _handle_response(self, response: Dict[str, Any]) -> None:
        """Handle incoming response and resolve pending futures."""
        call_id = response.get("call_id")
        if call_id and call_id in self.pending_requests:
            future = self.pending_requests.pop(call_id)
            if not future.done():
                future.set_result(response)

    async def send_request(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Send a request and wait for response."""
        call_id = str(uuid.uuid4())
        payload["call_id"] = call_id

        future = asyncio.get_event_loop().create_future()
        self.pending_requests[call_id] = future

        try:
            await self.ws.send(json.dumps(payload))
            await asyncio.wait_for(future, timeout=60.0)
            return future.result()
        except asyncio.TimeoutError:
            self.pending_requests.pop(call_id, None)
            return {"status": "error", "message": "Request timed out"}
        except Exception as e:
            self.pending_requests.pop(call_id, None)
            return {"status": "error", "message": str(e)}

    async def wait_for_user_approval(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Send a request requiring user approval."""
        payload["requires_approval"] = True
        return await self.send_request(payload)


class ElectronAppEnv:
    """
    Environment for integrating with Glim Electron App.
    Provides file operations with user approval workflow.
    """

    def __init__(self, config_dict: Optional[Dict[str, Any]] = None):
        self.config = config_dict or {}
        self.workspace_root = self.config.get("workspace_root", os.getcwd())
        self.bridge_type = self.config.get("bridge_type", "stdio")
        self.ws_url = self.config.get("ws_url", "ws://localhost:8765")

        if self.bridge_type == "websocket":
            self.bridge = WebSocketBridge(self.workspace_root, self.ws_url)
        else:
            self.bridge = ElectronBridge(self.workspace_root)

        self.state: Dict[str, Any] = {
            "is_initialized": False,
            "workspace_root": self.workspace_root,
            "current_file": None,
            "current_buffer": None
        }
        self._pending_approvals: Dict[str, asyncio.Event] = {}

    async def setup(self) -> None:
        """Initialize connection with Electron app."""
        if not self.state["is_initialized"]:
            connected = await self.bridge.connect()
            if connected:
                self.state["is_initialized"] = True

    async def close(self) -> None:
        """Close connection with Electron app."""
        await self.bridge.disconnect()
        self.state["is_initialized"] = False
        self.state["current_buffer"] = None

    def _format_result(self, status: str, stdout: str = "", message: str = "", error_code: int = 0) -> Dict[str, Any]:
        """统一返回格式"""
        return {
            "status": status,
            "stdout": stdout,
            "message": message,
            "error_code": error_code
        }

    async def read_file(self, path: str) -> Dict[str, Any]:
        """Read file content via Electron."""
        try:
            abs_path = self._get_abs_path(path)
            if not abs_path.exists():
                return self._format_result("error", message=f"File not found: {path}", error_code=-1)

            content = abs_path.read_text(encoding='utf-8')
            self.state["current_file"] = str(abs_path)
            self.state["current_buffer"] = content
            return self._format_result("success", stdout=content)
        except PermissionError:
            return self._format_result("error", message=f"Access denied: {path}", error_code=-1)
        except Exception as e:
            return self._format_result("error", message=str(e), error_code=-1)

    async def write_file(self, path: str, content: str) -> Dict[str, Any]:
        """Write file content via Electron with user approval."""
        try:
            abs_path = self._get_abs_path(path)
            payload = {
                "tool": "write_file",
                "params": {
                    "path": str(abs_path),
                    "content": content
                }
            }

            response = await self.bridge.wait_for_user_approval(payload)

            if response.get("status") == "accepted":
                abs_path.parent.mkdir(parents=True, exist_ok=True)
                abs_path.write_text(content, encoding='utf-8')
                self.state["current_buffer"] = content
                return self._format_result("success", message=f"File written: {path}")
            else:
                return self._format_result("error", message="User rejected the write operation", error_code=-1)
        except PermissionError:
            return self._format_result("error", message=f"Access denied: {path}", error_code=-1)
        except Exception as e:
            return self._format_result("error", message=str(e), error_code=-1)

    async def read_file_lines(self, path: str, start_line: int = None, end_line: int = None) -> Dict[str, Any]:
        """Read specific lines from file with line numbers."""
        try:
            abs_path = self._get_abs_path(path)
            if not abs_path.exists():
                return self._format_result("error", message=f"File not found: {path}", error_code=-1)

            lines = abs_path.read_text(encoding='utf-8').splitlines()

            if start_line is None:
                start_line = 1
            if end_line is None:
                end_line = len(lines)

            start_idx = max(0, start_line - 1)
            end_idx = min(len(lines), end_line)

            selected_lines = lines[start_idx:end_idx]
            numbered = "\n".join([f"{i + 1}\t{line}" for i, line in enumerate(selected_lines, start=start_line)])

            return self._format_result("success", stdout=numbered)
        except Exception as e:
            return self._format_result("error", message=str(e), error_code=-1)

    async def request_user_approval(self, action_type: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Request user approval for an action and wait for response.

        :param action_type: Type of action (insert, replace, etc.)
        :param params: Action parameters
        :return: {"status": "accepted" | "rejected"}
        """
        payload = {
            "tool": action_type,
            "params": params
        }

        response = await self.bridge.wait_for_user_approval(payload)
        return response

    async def list_file_tree(self, path: str = None, recursive: bool = True) -> Dict[str, Any]:
        """List file tree via Electron."""
        try:
            start_path = path if path else self.workspace_root
            abs_path = self._get_abs_path(start_path)

            payload = {
                "tool": "list_file_tree",
                "params": {
                    "path": str(abs_path),
                    "recursive": recursive
                }
            }

            response = await self.bridge.send_request(payload)
            return self._format_result(
                status="success",
                stdout=response.get("result", "")
            )
        except Exception as e:
            return self._format_result("error", message=str(e), error_code=-1)

    async def search_content(self, query: str, include: str = None) -> Dict[str, Any]:
        """Search content in the project."""
        try:
            payload = {
                "tool": "search",
                "params": {
                    "query": query,
                    "include": include
                }
            }

            response = await self.bridge.send_request(payload)
            return self._format_result(
                status="success",
                stdout=response.get("result", "")
            )
        except Exception as e:
            return self._format_result("error", message=str(e), error_code=-1)

    async def insert_content(self, path: str, at_line: int, content: str, description: str = "") -> Dict[str, Any]:
        """Insert content after a specific line (requires user approval)."""
        try:
            abs_path = self._get_abs_path(path)
            payload = {
                "tool": "insert",
                "params": {
                    "path": str(abs_path),
                    "at_line": at_line,
                    "content": content,
                    "description": description
                }
            }

            response = await self.bridge.wait_for_user_approval(payload)

            if response.get("status") == "accepted":
                return self._format_result(
                    "success",
                    message=f"Content inserted at line {at_line} in {path}"
                )
            else:
                return self._format_result(
                    "error",
                    message="User rejected the insertion",
                    error_code=-1
                )
        except Exception as e:
            return self._format_result("error", message=str(e), error_code=-1)

    async def replace_content(self, path: str, from_line: int, to_line: int,
                               new_content: str, original_snippet: str = "",
                               description: str = "") -> Dict[str, Any]:
        """Replace content in a line range (requires user approval)."""
        try:
            abs_path = self._get_abs_path(path)
            payload = {
                "tool": "replace",
                "params": {
                    "path": str(abs_path),
                    "from_line": from_line,
                    "to_line": to_line,
                    "new_content": new_content,
                    "original_code_snippet": original_snippet,
                    "description": description
                }
            }

            response = await self.bridge.wait_for_user_approval(payload)

            if response.get("status") == "accepted":
                return self._format_result(
                    "success",
                    message=f"Lines {from_line}-{to_line} replaced in {path}"
                )
            else:
                return self._format_result(
                    "error",
                    message="User rejected the replacement",
                    error_code=-1
                )
        except Exception as e:
            return self._format_result("error", message=str(e), error_code=-1)

    def _get_abs_path(self, path: str) -> Path:
        """Resolve absolute path within workspace."""
        p = Path(path)
        if p.is_absolute():
            abs_path = p.resolve()
        else:
            abs_path = (Path(self.workspace_root) / p).resolve()

        workspace_resolved = Path(self.workspace_root).resolve()
        if not str(abs_path).startswith(str(workspace_resolved) + os.sep) and abs_path != workspace_resolved:
            raise PermissionError(f"Access denied: {path} is outside workspace")

        return abs_path

    def get_observation(self) -> str:
        """Get current environment state for agent context."""
        return f"Electron App Environment\nWorkspace: {self.workspace_root}\nCurrent File: {self.state.get('current_file', 'None')}"
