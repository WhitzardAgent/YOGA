from .base import Environment
from typing import Dict, Any, Optional
import subprocess
import os
import tempfile
import nbformat
from nbclient import NotebookClient
import asyncio
from pathlib import Path
import webbrowser
import threading
import time
import random


class JupyterNotebookEnvironment(Environment):
    """
    Environment for executing Jupyter notebooks locally.
    This environment allows creating and executing Jupyter notebooks programmatically.
    """
    
    def __init__(self, config_dict: Optional[Dict[str, Any]] = None):
        super().__init__()
        self.config = config_dict or {}
        self.notebook_path: Optional[str] = None
        self.notebook: Optional[nbformat.NotebookNode] = None
        self.client: Optional[NotebookClient] = None
        self.tmp_dir: Optional[tempfile.TemporaryDirectory] = None
        self.jupyter_process = None
        self.state["is_initialized"] = False
        self.state["current_cell"] = 0
        self.state["kernel_status"] = "not_started"
        self.state["working_dir"] = self.config.get("working_dir", os.getcwd())
        
        # Use the specified notebook directory or default to working directory
        notebook_dir = self.config.get("notebook_dir", self.state["working_dir"])
        self.notebook_dir = os.path.abspath(notebook_dir)
        
        # Create notebook directory if it doesn't exist
        os.makedirs(self.notebook_dir, exist_ok=True)
        
        self.state["server_running"] = False
        self.state["server_url"] = None

    async def setup(self):
        """Initialize the Jupyter notebook environment."""
        if not self.state["is_initialized"]:
            # Create a temporary directory for notebook operations if needed
            if self.config.get("use_temp_dir", False):
                self.tmp_dir = tempfile.TemporaryDirectory()
                self.notebook_dir = self.tmp_dir.name
            
            # Create a new notebook if not provided
            if self.notebook_path is None:
                self.notebook = nbformat.v4.new_notebook()
                # Create a temporary notebook file in the specified directory
                self.notebook_path = os.path.join(self.notebook_dir, "temp_notebook.ipynb")
                
            # Ensure jupyter and ipykernel are installed
            try:
                subprocess.run(['jupyter', '--version'], capture_output=True, check=True)
            except (subprocess.CalledProcessError, FileNotFoundError):
                raise RuntimeError("Jupyter is not installed. Please install it using 'pip install jupyter'")

            try:
                subprocess.run(['python', '-m', 'ipykernel', '--version'], capture_output=True, check=True)
            except (subprocess.CalledProcessError, FileNotFoundError):
                raise RuntimeError("IPyKernel is not installed. Please install it using 'pip install ipykernel'")
            
            self.state["is_initialized"] = True
            self.state["kernel_status"] = "ready"
            self.state["working_dir"] = os.path.abspath(self.state["working_dir"])

    def create_notebook(self, notebook_path: str = None):
        """Create a new notebook at the specified path or in the default directory."""
        if notebook_path is None:
            # Generate a default notebook name in the notebook directory
            import uuid
            notebook_name = f"notebook_{uuid.uuid4().hex[:8]}.ipynb"
            notebook_path = os.path.join(self.notebook_dir, notebook_name)
        else:
            # Ensure the path is within the allowed directory
            notebook_path = os.path.abspath(notebook_path)
            if not notebook_path.startswith(self.notebook_dir):
                return {"status": "error", "message": f"Notebook path must be within the notebook directory: {self.notebook_dir}"}
        
        self.notebook_path = notebook_path
        self.notebook = nbformat.v4.new_notebook()
        self._save_notebook()
        return {"status": "success", "message": f"Notebook created at {notebook_path}"}

    def load_notebook(self, notebook_path: str):
        """Load an existing notebook from the specified path."""
        # Ensure the path is within the allowed directory
        notebook_path = os.path.abspath(notebook_path)
        if not notebook_path.startswith(self.notebook_dir):
            return {"status": "error", "message": f"Notebook path must be within the notebook directory: {self.notebook_dir}"}
        
        if not os.path.exists(notebook_path):
            return {"status": "error", "message": f"Notebook file does not exist: {notebook_path}"}
        
        self.notebook_path = notebook_path
        with open(notebook_path, 'r', encoding='utf-8') as f:
            self.notebook = nbformat.read(f, as_version=4)
        
        return {"status": "success", "message": f"Notebook loaded from {notebook_path}"}

    def add_cell(self, source: str, cell_type: str = "code"):
        """Add a new cell to the notebook."""
        if self.notebook is None:
            return {"status": "error", "message": "No notebook loaded or created"}
        
        if cell_type == "code":
            cell = nbformat.v4.new_code_cell(source)
        elif cell_type == "markdown":
            cell = nbformat.v4.new_markdown_cell(source)
        else:
            return {"status": "error", "message": f"Unknown cell type: {cell_type}. Use 'code' or 'markdown'"}
        
        self.notebook.cells.append(cell)
        self._save_notebook()
        
        cell_index = len(self.notebook.cells) - 1
        return {
            "status": "success", 
            "message": f"Added {cell_type} cell at index {cell_index}",
            "cell_index": cell_index
        }

    def execute_notebook(self):
        """Execute the entire notebook."""
        if self.notebook is None or self.notebook_path is None:
            return {"status": "error", "message": "No notebook loaded or created"}
        
        try:
            # Read the notebook again in case it was modified externally
            with open(self.notebook_path, 'r', encoding='utf-8') as f:
                nb = nbformat.read(f, as_version=4)
            
            # Create client and execute
            client = NotebookClient(nb, timeout=600, kernel_name='python3')
            executed_nb = client.execute()
            
            # Save the executed notebook
            with open(self.notebook_path, 'w', encoding='utf-8') as f:
                nbformat.write(executed_nb, f)
            
            self.notebook = executed_nb
            self.state["kernel_status"] = "executed"
            
            return {
                "status": "success",
                "message": "Notebook executed successfully",
                "outputs": self._extract_outputs(executed_nb)
            }
        except Exception as e:
            return {
                "status": "error",
                "message": f"Failed to execute notebook: {str(e)}"
            }

    def execute_cell(self, cell_index: int):
        """Execute a specific cell in the notebook."""
        if self.notebook is None:
            return {"status": "error", "message": "No notebook loaded or created"}
        
        if cell_index < 0 or cell_index >= len(self.notebook.cells):
            return {
                "status": "error", 
                "message": f"Cell index {cell_index} is out of range. Notebook has {len(self.notebook.cells)} cells."
            }
        
        # Create a temporary notebook with only the target cell
        temp_nb = nbformat.v4.new_notebook()
        temp_nb.cells = [self.notebook.cells[cell_index]]
        
        try:
            client = NotebookClient(temp_nb, timeout=600, kernel_name='python3')
            executed_nb = client.execute()
            
            # Update the original notebook with the executed cell
            self.notebook.cells[cell_index] = executed_nb.cells[0]
            self._save_notebook()
            
            outputs = self._extract_outputs(executed_nb)
            return {
                "status": "success",
                "message": f"Cell {cell_index} executed successfully",
                "outputs": outputs,
                "cell_index": cell_index
            }
        except Exception as e:
            return {
                "status": "error",
                "message": f"Failed to execute cell {cell_index}: {str(e)}"
            }

    def get_notebook_info(self):
        """Get information about the current notebook."""
        if self.notebook is None:
            return {"status": "error", "message": "No notebook loaded or created"}
        
        info = {
            "status": "success",
            "num_cells": len(self.notebook.cells),
            "path": self.notebook_path,
            "cells": []
        }
        
        for i, cell in enumerate(self.notebook.cells):
            cell_info = {
                "index": i,
                "type": cell.cell_type,
                "source_length": len(cell.source) if cell.source else 0,
                "outputs_count": len(cell.outputs) if hasattr(cell, 'outputs') and cell.cell_type == 'code' else 0
            }
            info["cells"].append(cell_info)
        
        return info

    def start_jupyter_server(self, port: Optional[int] = None, custom_notebook_dir: Optional[str] = None):
        """Start a Jupyter notebook server and open the notebook in the browser."""
        if not self.notebook_path:
            return {"status": "error", "message": "No notebook path specified"}
        
        if self.jupyter_process and self.jupyter_process.poll() is None:
            return {"status": "error", "message": "Jupyter server is already running"}
        
        # Use custom notebook directory if provided, otherwise use the default one
        notebook_dir = custom_notebook_dir if custom_notebook_dir else self.notebook_dir
        
        # Ensure the notebook directory exists
        os.makedirs(notebook_dir, exist_ok=True)
        
        # Find an available port if none specified
        if port is None:
            port = self._find_available_port()
        
        # Start the Jupyter server in a subprocess
        notebook_filename = os.path.basename(self.notebook_path)
        
        cmd = [
            'jupyter', 'notebook',
            f'--port={port}',
            f'--notebook-dir={notebook_dir}',
            '--no-browser',  # We'll open the browser manually
            '--allow-root',  # Allow running as root (if needed in some 
            '--NotebookApp.disable_check_xsrf=True'  # Disable XSRF checks for programmatic updates
        ]
        
        try:
            self.jupyter_process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            
            # Wait briefly to ensure the server has started
            time.sleep(3)
            
            # Check if the process is still running
            if self.jupyter_process.poll() is not None:
                # Process has terminated, get error output
                stderr_output = self.jupyter_process.stderr.read().decode() if self.jupyter_process.stderr else "Unknown error"
                return {"status": "error", "message": f"Failed to start Jupyter server: {stderr_output}"}
            
            # Set server state
            server_url = f"http://localhost:{port}/notebooks/{notebook_filename}"
            self.state["server_running"] = True
            self.state["server_url"] = server_url
            
            # Open the notebook in the browser
            webbrowser.open(server_url)
            
            return {
                "status": "success",
                "message": f"Jupyter server started on {server_url}",
                "url": server_url,
                "notebook_dir": notebook_dir
            }
        except Exception as e:
            return {
                "status": "error",
                "message": f"Failed to start Jupyter server: {str(e)}"
            }

    def stop_jupyter_server(self):
        """Stop the Jupyter notebook server."""
        if self.jupyter_process and self.jupyter_process.poll() is None:
            self.jupyter_process.terminate()
            try:
                self.jupyter_process.wait(timeout=5)  # Wait up to 5 seconds for process to terminate
            except subprocess.TimeoutExpired:
                self.jupyter_process.kill()  # Force kill if it doesn't terminate gracefully
            
            self.jupyter_process = None
            self.state["server_running"] = False
            self.state["server_url"] = None
            
            return {"status": "success", "message": "Jupyter server stopped"}
        else:
            return {"status": "error", "message": "Jupyter server is not running"}

    def _find_available_port(self, start_port: int = 8888):
        """Find an available port starting from start_port."""
        import socket
        
        port = start_port
        while True:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                try:
                    s.bind(('', port))
                    return port
                except OSError:
                    port += 1
                    if port > start_port + 100:  # Don't search too many ports
                        raise RuntimeError("Could not find an available port")

    def _save_notebook(self):
        """Save the current notebook to file."""
        if self.notebook is not None and self.notebook_path is not None:
            with open(self.notebook_path, 'w', encoding='utf-8') as f:
                nbformat.write(self.notebook, f)
                f.flush()


    def _extract_outputs(self, notebook):
        """Extract outputs from executed notebook."""
        outputs = []
        for i, cell in enumerate(notebook.cells):
            if cell.cell_type == 'code' and hasattr(cell, 'outputs'):
                cell_outputs = []
                for output in cell.outputs:
                    output_data = {
                        "output_type": output.output_type,
                    }
                    if hasattr(output, 'text'):
                        output_data["text"] = output.text
                    if hasattr(output, 'data'):
                        output_data["data"] = output.data
                    if hasattr(output, 'ename') and hasattr(output, 'evalue'):
                        output_data["error"] = {
                            "name": output.ename,
                            "value": output.evalue
                        }
                    cell_outputs.append(output_data)
                outputs.append({
                    "cell_index": i,
                    "outputs": cell_outputs
                })
        return outputs

    async def close(self):
        """Clean up resources."""
        # Stop the Jupyter server if running
        if self.state["server_running"]:
            self.stop_jupyter_server()
        
        if self.tmp_dir:
            self.tmp_dir.cleanup()
        
        self.state["is_initialized"] = False
        self.state["kernel_status"] = "closed"
        self.state["server_running"] = False