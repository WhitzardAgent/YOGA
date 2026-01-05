from abc import ABC, abstractmethod
from ..environments.base import Environment
from typing import Dict, Any, Union, List


class ActionSpace(ABC):
    def __init__(self, action_space_name: str, env: Environment):
        self.env = env
        self.action_space_name = action_space_name
        self.capabilities: Dict[str, Any] = {}  # Mapping: action_name -> OpenAI-style tool spec

    @abstractmethod
    def execute(self, action_name: str, param_dict: dict) -> dict:
        pass

    def get_capabilities(self) -> dict:
        return self.capabilities

    def get_action_space_description(self) -> str:
        """
        Returns a human-readable string listing all available actions as Python-like function signatures.
        Uses parameter types from the OpenAI-style JSON Schema if available.
        """
        lines: List[str] = []
        for name, spec in self.capabilities.items():
            params_info = []
            parameters = spec.get("parameters", {})
            properties = parameters.get("properties", {})
            required = set(parameters.get("required", []))

            for param_name, param_schema in properties.items():
                param_type = param_schema.get("type", "any")
                # Map JSON Schema types to Python-like annotations
                py_type = {
                    "string": "str",
                    "integer": "int",
                    "number": "float",
                    "boolean": "bool",
                    "array": "list",
                    "object": "dict"
                }.get(param_type, "Any")

                # Mark optional vs required
                if param_name not in required:
                    py_type += " | None"  # or use "Optional[...]" if preferred

                params_info.append(f"{param_name}: {py_type}")

            params_str = ", ".join(params_info) if params_info else ""
            lines.append(f"def {name}({params_str}) -> dict:")
            desc = spec.get("description", "No description.")
            lines.append(f'    """{desc}"""')
            lines.append("")  # blank line for readability

        return "\n".join(lines).strip()


class UnionActionSpace(ActionSpace):
    def __init__(self, action_spaces: list[ActionSpace]):
        # Pass a dummy environment since UnionActionSpace doesn't directly use one
        super().__init__(env=None)  # type: ignore
        self.sub_spaces = action_spaces
        self._merge_capabilities()

    def _merge_capabilities(self):
        """Unions all sub-space capabilities into one registry."""
        for space in self.sub_spaces:
            self.capabilities.update(space.get_capabilities())

    def execute(self, action_name: str, param_dict: dict) -> dict:
        # Route the action to the space that owns it
        for space in self.sub_spaces:
            if action_name in space.get_capabilities():
                return space.execute(action_name, param_dict)
        
        return {
            "status": "error", 
            "message": f"Action '{action_name}' not found in any registered space."
        }

    def get_action_space_description(self) -> str:
        """
        Aggregates descriptions from all sub-spaces. Since capabilities are merged,
        we can just call the parent implementation.
        """
        description = "\n".join([f'### {space.action_space_name}\n{space.get_action_space_description()}' for space in self.sub_spaces])
        return description