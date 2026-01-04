
import yaml
from typing import List

class AgentConfig:
    def __init__(
        self,
        api_base_url: str,
        model_name: str,
        api_key: str,
    ):
        self.api_base_url = api_base_url
        self.model_name = model_name
        self.api_key = api_key

    @classmethod
    def from_yaml(cls, path: str) -> "AgentConfig":
        with open(path, "r", encoding="utf-8") as f:
            config_data = yaml.safe_load(f)

        required_fields = ["api_base_url", "api_key", "model_name"]
        missing = [field for field in required_fields if field not in config_data]
        if missing:
            raise ValueError(f"Missing required config fields: {missing}")

        return cls(
            api_base_url=config_data["api_base_url"],
            model_name=config_data["model_name"],
            api_key=config_data["api_key"]
        )
