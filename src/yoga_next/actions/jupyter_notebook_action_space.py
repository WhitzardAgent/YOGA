from ..environments.jupyter_notebook_env import JupyterNotebookEnvironment
from .base import ActionSpace
from typing import Dict, Any, Union
import json


class JupyterNotebookActionSpace(ActionSpace):
    """
    Action space for interacting with Jupyter notebooks.
    Provides actions for creating, loading, executing, and modifying notebooks.
    """
    
    def __init__(self, env: JupyterNotebookEnvironment):
        super().__init__(action_space_name="jupyter_notebook_actions", env=env)
        
        # Define the capabilities (available actions) with OpenAI-style tool specs
        self.capabilities = {
            "create_notebook": {
                "name": "create_notebook",
                "description": "Creates a new Jupyter notebook at the specified path or in the default directory if no path is provided",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "notebook_path": {
                            "type": "string",
                            "description": "Optional path where the notebook should be created. If not provided, creates in the default notebook directory"
                        }
                    },
                    "required": []
                }
            },
            "load_notebook": {
                "name": "load_notebook",
                "description": "Loads an existing Jupyter notebook from the specified path",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "notebook_path": {
                            "type": "string",
                            "description": "Path to the notebook to load"
                        }
                    },
                    "required": ["notebook_path"]
                }
            },
            "add_cell": {
                "name": "add_cell",
                "description": "Adds a new cell to the notebook",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "source": {
                            "type": "string",
                            "description": "The source code or markdown content for the cell"
                        },
                        "cell_type": {
                            "type": "string",
                            "enum": ["code", "markdown"],
                            "description": "Type of cell to add, either 'code' or 'markdown'. Default is 'code'"
                        }
                    },
                    "required": ["source"]
                }
            },
            "execute_notebook": {
                "name": "execute_notebook",
                "description": "Executes the entire notebook",
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            },
            "execute_cell": {
                "name": "execute_cell",
                "description": "Executes a specific cell in the notebook",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "cell_index": {
                            "type": "integer",
                            "description": "Index of the cell to execute"
                        }
                    },
                    "required": ["cell_index"]
                }
            },
            "get_notebook_info": {
                "name": "get_notebook_info",
                "description": "Gets information about the current notebook",
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            },
            "start_jupyter_server": {
                "name": "start_jupyter_server",
                "description": "Starts a Jupyter notebook server and opens the notebook in the browser",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "port": {
                            "type": "integer",
                            "description": "Port to run the Jupyter server on. If not provided, a random available port will be chosen"
                        },
                        "custom_notebook_dir": {
                            "type": "string",
                            "description": "Custom directory to serve notebooks from. If not provided, uses the default notebook directory"
                        }
                    },
                    "required": []
                }
            },
            "stop_jupyter_server": {
                "name": "stop_jupyter_server",
                "description": "Stops the running Jupyter notebook server",
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            },
            "refresh_notebook": {
                "name": "refresh_notebook",
                "description": "Refreshes the current notebook by reloading it from disk, discarding any unsaved changes in memory",
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            }
        }

    def execute(self, action_name: str, param_dict: dict) -> dict:
        """
        Execute an action on the Jupyter notebook environment.
        """
        if not isinstance(self.env, JupyterNotebookEnvironment):
            return {
                "status": "error",
                "message": f"Environment is not a JupyterNotebookEnvironment, got {type(self.env)}"
            }

        try:
            if action_name == "create_notebook":
                notebook_path = param_dict.get("notebook_path")
                return self.env.create_notebook(notebook_path)
            
            elif action_name == "load_notebook":
                notebook_path = param_dict.get("notebook_path")
                return self.env.load_notebook(notebook_path)
            
            elif action_name == "add_cell":
                source = param_dict.get("source")
                cell_type = param_dict.get("cell_type", "code")
                return self.env.add_cell(source, cell_type)
            
            elif action_name == "execute_notebook":
                return self.env.execute_notebook()
            
            elif action_name == "execute_cell":
                cell_index = param_dict.get("cell_index")
                return self.env.execute_cell(cell_index)
            
            elif action_name == "get_notebook_info":
                return self.env.get_notebook_info()
            
            elif action_name == "start_jupyter_server":
                port = param_dict.get("port")
                custom_notebook_dir = param_dict.get("custom_notebook_dir")
                return self.env.start_jupyter_server(port, custom_notebook_dir)
            
            elif action_name == "stop_jupyter_server":
                return self.env.stop_jupyter_server()

            elif action_name == "refresh_notebook":
                return self.env.refresh_notebook()
            
            else:
                return {
                    "status": "error",
                    "message": f"Unknown action: {action_name}"
                }
        
        except Exception as e:
            return {
                "status": "error",
                "message": f"Error executing action {action_name}: {str(e)}"
            }