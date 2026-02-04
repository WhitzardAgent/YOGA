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


    def _handle_create_notebook(self, notebook_path: str = None) -> Dict[str, Any]:
        """Creates a new Jupyter notebook at the specified path.
        
        :param notebook_path: Optional path where the notebook should be created. 
            If not provided, creates in the default notebook directory.
        
        Returns confirmation with the created notebook path.
        """
        return self.env.create_notebook(notebook_path)

    def _handle_load_notebook(self, notebook_path: str) -> Dict[str, Any]:
        """Loads an existing Jupyter notebook from the specified path.
        
        :param notebook_path: Path to the notebook to load.
        
        Returns the notebook content and metadata.
        """
        return self.env.load_notebook(notebook_path)

    def _handle_add_cell(self, source: str, cell_type: str = "code") -> Dict[str, Any]:
        """Adds a new cell to the notebook.
        
        :param source: The source code or markdown content for the cell.
        :param cell_type: Type of cell to add, either 'code' or 'markdown'. Defaults to 'code'.
        
        Returns confirmation with the cell index.
        """
        return self.env.add_cell(source, cell_type)

    def _handle_execute_notebook(self) -> Dict[str, Any]:
        """Executes the entire notebook.
        
        Returns the execution results from all cells.
        """
        return self.env.execute_notebook()

    def _handle_execute_cell(self, cell_index: int) -> Dict[str, Any]:
        """Executes a specific cell in the notebook.
        
        :param cell_index: Index of the cell to execute (0-indexed).
        
        Returns the execution output from that cell.
        """
        return self.env.execute_cell(cell_index)

    def _handle_get_notebook_info(self) -> Dict[str, Any]:
        """Gets information about the current notebook.
        
        Returns notebook metadata including cell count, kernel status, and path.
        """
        return self.env.get_notebook_info()

    def _handle_start_jupyter_server(self, port: int = None, custom_notebook_dir: str = None) -> Dict[str, Any]:
        """Starts a Jupyter notebook server.
        
        :param port: Port to run the Jupyter server on. If not provided, a random available port will be chosen.
        :param custom_notebook_dir: Custom directory to serve notebooks from. If not provided, uses the default notebook directory.
        
        Returns confirmation with server details including the URL.
        """
        return self.env.start_jupyter_server(port, custom_notebook_dir)

    def _handle_stop_jupyter_server(self) -> Dict[str, Any]:
        """Stops the running Jupyter notebook server.
        
        Returns confirmation that the server has been stopped.
        """
        return self.env.stop_jupyter_server()

    def _handle_refresh_notebook(self) -> Dict[str, Any]:
        """Refreshes the current notebook by reloading it from disk.
        
        This discards any unsaved changes in memory.
        Returns confirmation of the refresh operation.
        """
        return self.env.refresh_notebook()
