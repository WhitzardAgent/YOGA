import asyncio
import json
import uuid
import os
import time
from typing import Dict, Any, Optional, AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from yoga_next.agent import Agent
from yoga_next.agent_config import AgentConfig
from yoga_next.tasks import Task
from yoga_next.environments.electron_app_env import ElectronAppEnv
from yoga_next.actions.glim_app_action_space import GlimAppActionSpace
from yoga_next.utils import log_info, log_error


class TaskRequest(BaseModel):
    instruction: str
    task_id: Optional[str] = None


class CallbackRequest(BaseModel):
    call_id: str
    status: str
    details: Optional[Dict[str, Any]] = None


class ViewProxyRequest(BaseModel):
    path: str
    start_line: Optional[int] = None
    end_line: Optional[int] = None


class ViewProxyResponse(BaseModel):
    path: str
    content: str
    pending_modifications: list


class TaskStatus(BaseModel):
    task_id: str
    status: str
    current_step: int = 0
    thought: Optional[str] = None
    action: Optional[str] = None
    observation: Optional[str] = None
    pending_approval: Optional[bool] = False


class PendingModification(BaseModel):
    call_id: str
    tool: str
    path: str
    params: Dict[str, Any]
    timestamp: float
    status: str = "pending"


class AgentService:
    def __init__(self):
        self.agent: Optional[Agent] = None
        self.env: Optional[ElectronAppEnv] = None
        self.glim_space: Optional[GlimAppActionSpace] = None
        self.config_path: str = ""
        self.current_task_id: Optional[str] = None
        self.task_status: Dict[str, TaskStatus] = {}
        self._pending_modifications: Dict[str, PendingModification] = {}
        self._events: asyncio.Queue = asyncio.Queue()
        self._running_tasks: Dict[str, asyncio.Task] = {}

    async def initialize(self, workspace_root: str, config_path: str = ""):
        self.config_path = config_path or os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "configs/config_local.yaml"
        )

        env_config = {
            "workspace_root": workspace_root,
            "bridge_type": "stdio"
        }

        self.env = ElectronAppEnv(env_config)
        await self.env.setup()

        self.glim_space = GlimAppActionSpace("glim_app", self.env)

        try:
            agent_config = AgentConfig.from_yaml(self.config_path)
        except Exception as e:
            log_error(f"Failed to load config from {self.config_path}: {e}")
            agent_config = AgentConfig(
                api_base_url="https://api.openai.com/v1",
                model_name="gpt-4o",
                api_key=""
            )

        self.agent = Agent(
            agent_config=agent_config,
            action_spaces=[self.glim_space],
            use_rich_display=False
        )

        log_info(f"AgentService initialized with workspace: {workspace_root}")

    async def _run_task_background(self, task_id: str, instruction: str):
        self.task_status[task_id] = TaskStatus(
            task_id=task_id,
            status="running",
            current_step=0
        )

        await self._push_event({
            "event": "started",
            "data": {"task_id": task_id, "status": "started"}
        })

        task = Task(task_id=task_id, instruction=instruction)

        try:
            result = await self.agent.execute(task)
            self.task_status[task_id].status = "completed"
            await self._push_event({
                "event": "completed",
                "data": {"task_id": task_id, "result": result}
            })
        except Exception as e:
            log_error(f"Task execution failed: {e}")
            self.task_status[task_id].status = "error"
            await self._push_event({
                "event": "error",
                "data": {"task_id": task_id, "error": str(e)}
            })

        self._running_tasks.pop(task_id, None)

    async def execute_task(self, instruction: str, task_id: Optional[str] = None) -> str:
        if not self.agent:
            raise RuntimeError("Agent not initialized. Call initialize() first.")

        task_id = task_id or f"task_{uuid.uuid4().hex[:8]}"
        self.current_task_id = task_id

        self._running_tasks[task_id] = asyncio.create_task(
            self._run_task_background(task_id, instruction)
        )

        return task_id

    async def wait_for_approval(self, tool: str, params: Dict[str, Any]) -> Dict[str, Any]:
        call_id = str(uuid.uuid4())
        timestamp = time.time()

        pending = PendingModification(
            call_id=call_id,
            tool=tool,
            path=params.get("path", ""),
            params=params,
            timestamp=timestamp
        )
        self._pending_modifications[call_id] = pending

        await self._push_event({
            "event": "PROPOSE_MODIFICATION",
            "data": {
                "call_id": call_id,
                "type": "PROPOSE_MODIFICATION",
                "tool_call": {
                    "tool": tool,
                    "params": params
                },
                "timestamp": timestamp
            }
        })

        return {"status": "pended", "message": "Change sent to UI for review"}

    def get_pending_modification(self, call_id: str) -> Optional[PendingModification]:
        return self._pending_modifications.get(call_id)

    def get_all_pending_modifications(self) -> Dict[str, Dict[str, Any]]:
        return {
            call_id: {
                "call_id": mod.call_id,
                "tool": mod.tool,
                "path": mod.path,
                "params": mod.params,
                "timestamp": mod.timestamp,
                "status": mod.status
            }
            for call_id, mod in self._pending_modifications.items()
        }

    async def apply_modification_to_content(self, path: str, content: str) -> str:
        pending = sorted(
            [mod for mod in self._pending_modifications.values() 
             if mod.path == path and mod.status == "pending"],
            key=lambda m: m.timestamp
        )

        result = content
        for mod in pending:
            if mod.tool == "replace":
                from_line = mod.params.get("from_line", 1)
                to_line = mod.params.get("to_line", from_line)
                new_content = mod.params.get("new_content", "")

                lines = result.splitlines()
                if from_line <= len(lines):
                    end_idx = min(to_line, len(lines))
                    lines[from_line - 1:end_idx] = [new_content]
                    result = "\n".join(lines)

            elif mod.tool == "insert":
                at_line = mod.params.get("at_line", 1)
                new_content = mod.params.get("content", "")

                lines = result.splitlines()
                insert_idx = min(at_line, len(lines) + 1)
                lines.insert(insert_idx - 1, new_content)
                result = "\n".join(lines)

        return result

    async def resolve_approval(self, call_id: str, status: str, details: Optional[Dict] = None) -> Dict[str, Any]:
        if call_id not in self._pending_modifications:
            return {"status": "error", "message": "Pending modification not found"}

        pending = self._pending_modifications[call_id]

        if status == "accepted":
            if pending.tool == "replace":
                await self._apply_replace(pending)
            elif pending.tool == "insert":
                await self._apply_insert(pending)

            pending.status = "accepted"

            await self._push_event({
                "event": "MODIFICATION_APPROVED",
                "data": {
                    "call_id": call_id,
                    "tool": pending.tool,
                    "path": pending.path,
                    "status": "applied"
                }
            })

            self._pending_modifications.pop(call_id, None)

            return {"status": "accepted", "message": "Modification applied"}

        else:
            pending.status = "rejected"

            await self._push_event({
                "event": "MODIFICATION_REJECTED",
                "data": {
                    "call_id": call_id,
                    "tool": pending.tool,
                    "path": pending.path,
                    "status": "rejected"
                }
            })

            self._pending_modifications.pop(call_id, None)

            return {"status": "rejected", "message": "Modification rejected"}

    async def _apply_replace(self, pending: PendingModification):
        path = pending.params.get("path")
        from_line = pending.params.get("from_line", 1)
        to_line = pending.params.get("to_line", from_line)
        new_content = pending.params.get("new_content", "")

        abs_path = Path(path)
        if abs_path.exists():
            content = abs_path.read_text(encoding='utf-8')
            modified = await self.apply_modification_to_content(path, content)
            abs_path.write_text(modified, encoding='utf-8')
            log_info(f"Applied replace to {path}: lines {from_line}-{to_line}")

    async def _apply_insert(self, pending: PendingModification):
        path = pending.params.get("path")
        at_line = pending.params.get("at_line", 1)
        new_content = pending.params.get("content", "")

        abs_path = Path(path)
        if abs_path.exists():
            content = abs_path.read_text(encoding='utf-8')
            modified = await self.apply_modification_to_content(path, content)
            abs_path.write_text(modified, encoding='utf-8')
            log_info(f"Applied insert to {path}: at line {at_line}")

    async def _push_event(self, event: Dict[str, Any]):
        await self._events.put(event)

    async def event_stream(self, task_id: str) -> AsyncGenerator[Dict[str, Any], None]:
        while True:
            try:
                event = await asyncio.wait_for(self._events.get(), timeout=30.0)
                if event.get("data", {}).get("task_id") == task_id:
                    yield event
            except asyncio.TimeoutError:
                yield {"event": "heartbeat", "data": {}}
            except asyncio.CancelledError:
                break

    def get_task_status(self, task_id: str) -> Optional[TaskStatus]:
        return self.task_status.get(task_id)


_service = AgentService()


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    if _service.agent:
        await _service.env.close()


app = FastAPI(
    title="YOGA Agent Service",
    description="FastAPI backend for YOGA Agent with Electron integration",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup_event():
    workspace_root = os.environ.get("WORKSPACE_ROOT", os.getcwd())
    config_path = os.environ.get("CONFIG_PATH", "")

    try:
        await _service.initialize(workspace_root, config_path)
        log_info("AgentService started successfully")
    except Exception as e:
        log_error(f"Failed to start AgentService: {e}")


@app.post("/execute")
async def execute_task(request: TaskRequest):
    if not _service.agent:
        raise HTTPException(status_code=500, detail="Agent not initialized")

    task_id = request.task_id or f"task_{uuid.uuid4().hex[:8]}"

    async def generate():
        try:
            yield {"event": "started", "data": json.dumps({"task_id": task_id})}

            execution_task = asyncio.create_task(
                _service._run_task_background(task_id, request.instruction)
            )

            event_gen = _service.event_stream(task_id)
            async for event in event_gen:
                yield {"event": event.get("event", "update"), "data": json.dumps(event.get("data", {}))}

                if event.get("event") in ["completed", "error"]:
                    break

            await execution_task

        except Exception as e:
            yield {"event": "error", "data": json.dumps({"error": str(e)})}

    return EventSourceResponse(generate())


@app.post("/callback")
async def handle_callback(request: CallbackRequest):
    result = await _service.resolve_approval(
        request.call_id,
        request.status,
        request.details
    )
    return result


@app.get("/status/{task_id}")
async def get_status(task_id: str):
    status = _service.get_task_status(task_id)
    if not status:
        raise HTTPException(status_code=404, detail="Task not found")
    return status


@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "agent_initialized": _service.agent is not None,
        "workspace_root": _service.env.workspace_root if _service.env else None
    }


@app.post("/initialize")
async def initialize_service(workspace_root: str, config_path: str = ""):
    try:
        await _service.initialize(workspace_root, config_path)
        return {"status": "initialized", "workspace_root": workspace_root}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/pending_modifications")
async def get_pending_modifications():
    return {"pending": _service.get_all_pending_modifications()}


@app.get("/pending_modification/{call_id}")
async def get_pending_modification(call_id: str):
    mod = _service.get_pending_modification(call_id)
    if not mod:
        raise HTTPException(status_code=404, detail="Pending modification not found")
    return {
        "call_id": mod.call_id,
        "tool": mod.tool,
        "path": mod.path,
        "params": mod.params,
        "timestamp": mod.timestamp,
        "status": mod.status
    }


@app.post("/view_proxy")
async def view_proxy(request: ViewProxyRequest):
    path = request.path
    start_line = request.start_line
    end_line = request.end_line

    abs_path = Path(path)

    if not abs_path.exists():
        raise HTTPException(status_code=404, detail=f"File not found: {path}")

    try:
        content = abs_path.read_text(encoding='utf-8')

        content = await _service.apply_modification_to_content(path, content)

        if start_line is not None and end_line is not None:
            lines = content.splitlines()
            start_idx = max(0, start_line - 1)
            end_idx = min(len(lines), end_line)
            content = "\n".join(lines[start_idx:end_idx])
            numbered = "\n".join([
                f"{i + 1}\t{line}" 
                for i, line in enumerate(lines[start_idx:end_idx], start=start_line)
            ])
            content = numbered

        pending = [
            {
                "call_id": mod.call_id,
                "tool": mod.tool,
                "params": mod.params
            }
            for mod in _service._pending_modifications.values()
            if mod.path == path and mod.status == "pending"
        ]

        return ViewProxyResponse(
            path=path,
            content=content,
            pending_modifications=pending
        )

    except PermissionError:
        raise HTTPException(status_code=403, detail=f"Access denied: {path}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/tasks")
async def list_tasks():
    return {
        "running": list(_service._running_tasks.keys()),
        "status": {tid: st.status for tid, st in _service.task_status.items()}
    }


@app.post("/clear_pending")
async def clear_pending():
    count = len(_service._pending_modifications)
    _service._pending_modifications.clear()
    return {"cleared": count}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
