from abc import ABC, abstractmethod
from ..environments.base import Environment
from typing import Dict, Any, Union, List, Callable, Optional
import inspect
import re


def _parse_docstring_params(docstring: str) -> Dict[str, str]:
    """Parse :param: descriptions from docstring."""
    param_descriptions = {}
    if not docstring:
        return param_descriptions

    pattern = r":param\s+(\w+):\s*([^\n]+)"
    matches = re.findall(pattern, docstring)
    for name, desc in matches:
        param_descriptions[name] = desc.strip()
    return param_descriptions


def _python_type_to_json_type(python_type) -> str:
    """Map Python types to JSON Schema types."""
    type_str = str(python_type)

    if python_type is int or "int" in type_str.lower():
        return "integer"
    elif python_type is bool or "bool" in type_str.lower():
        return "boolean"
    elif python_type is list or "List" in type_str or "list" in type_str.lower():
        return "array"
    elif python_type is dict or "Dict" in type_str or "dict" in type_str.lower():
        return "object"
    else:
        return "string"


def _generate_tool_schema(func: Callable) -> Dict[str, Any]:
    """Generate OpenAI tool schema from a handler function."""
    sig = inspect.signature(func)
    doc = inspect.getdoc(func) or "No description provided."

    param_docs = _parse_docstring_params(doc)

    properties = {}
    required = []

    for name, param in sig.parameters.items():
        if name == "self":
            continue

        hints = {}
        try:
            hints = inspect.get_type_hints(func)
        except Exception:
            pass

        if name in hints:
            ptype = hints[name]
        elif param.annotation is not inspect.Parameter.empty:
            ptype = param.annotation
        else:
            ptype = str

        json_type = _python_type_to_json_type(ptype)

        description = param_docs.get(name, f"Parameter {name}")

        properties[name] = {
            "type": json_type,
            "description": description
        }

        if param.default is inspect.Parameter.empty:
            required.append(name)

    return {
        "description": doc,
        "parameters": {
            "type": "object",
            "properties": properties,
            "required": required
        }
    }


class ActionSpace(ABC):
    def __init__(self, action_space_name: str, env: Environment):
        self.env = env
        self.action_space_name = action_space_name
        self._capabilities: Dict[str, Any] = {}
        self._generated = False


    def _generate_capabilities(self) -> Dict[str, Any]:
        """Dynamically generate capabilities from _handle_* methods."""
        capabilities = {}
        for name, method in inspect.getmembers(self, predicate=inspect.ismethod):
            if name.startswith("_handle_"):
                action_name = name[len("_handle_"):]
                capabilities[action_name] = _generate_tool_schema(method)
        return capabilities

    def get_capabilities(self) -> Dict[str, Any]:
        if not self._generated:
            self._capabilities = self._generate_capabilities()
            self._generated = True
        return self._capabilities

    async def execute(self, action_name: str, param_dict: Dict[str, Any]) -> Dict[str, Any]:
        try:
            await self.env.setup()
            handler = getattr(self, f"_handle_{action_name}", None)
            if not handler:
                return {"status": "error", "message": f"Action '{action_name}' not supported."}
            result = await handler(**param_dict)
            return {
                "status": "success" if result.get("status") != "error" else "error",
                "action": action_name,
                "output": result
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def get_action_space_description(self) -> str:
        lines: List[str] = []
        for name, spec in self.get_capabilities().items():
            params_info = []
            parameters = spec.get("parameters", {})
            properties = parameters.get("properties", {})
            required = set(parameters.get("required", []))

            for param_name, param_schema in properties.items():
                param_type = param_schema.get("type", "any")
                py_type = {
                    "string": "str",
                    "integer": "int",
                    "number": "float",
                    "boolean": "bool",
                    "array": "list",
                    "object": "dict"
                }.get(param_type, "Any")

                if param_name not in required:
                    py_type += " | None"

                params_info.append(f"{param_name}: {py_type}")

            params_str = ", ".join(params_info) if params_info else ""
            lines.append(f"def {name}({params_str}) -> dict:")
            desc = spec.get("description", "No description.")
            lines.append(f'    """{desc}"""')
            lines.append("")

        return "\n".join(lines).strip()


class UnionActionSpace(ActionSpace):
    def __init__(self, action_spaces: list[ActionSpace]):
        super().__init__(env=None, action_space_name="union")
        self.sub_spaces = action_spaces
        self._generated = True
        self._capabilities = self._merge_capabilities()

    def _merge_capabilities(self) -> Dict[str, Any]:
        merged = {}
        for space in self.sub_spaces:
            merged.update(space.get_capabilities())
        return merged

    async def execute(self, action_name: str, param_dict: dict) -> dict:
        for space in self.sub_spaces:
            if action_name in space.get_capabilities():
                return await space.execute(action_name, param_dict)

        return {
            "status": "error",
            "message": f"Action '{action_name}' not found in any registered space."
        }

    def get_action_space_description(self) -> str:
        descriptions = []
        for space in self.sub_spaces:
            descriptions.append(f'### {space.action_space_name}\n{space.get_action_space_description()}')
        return "\n".join(descriptions)
