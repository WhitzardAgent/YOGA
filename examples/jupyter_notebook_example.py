#!/usr/bin/env python3
"""
Example script demonstrating the usage of JupyterNotebookEnvironment
and JupyterNotebookActionSpace with custom notebook directory.
The server is started first to allow real-time observation of agent interactions.
"""

import asyncio
import tempfile
import os
from yoga_next.environments.jupyter_notebook_env import JupyterNotebookEnvironment
from yoga_next.actions.jupyter_notebook_action_space import JupyterNotebookActionSpace


async def main():
    # Create a custom directory for our notebooks
    custom_notebook_dir = os.path.join(os.getcwd(), "my_notebooks")
    os.makedirs(custom_notebook_dir, exist_ok=True)
    
    # Initialize the environment with a custom notebook directory
    env = JupyterNotebookEnvironment({"notebook_dir": custom_notebook_dir})
    
    # Initialize the action space
    action_space = JupyterNotebookActionSpace(env)
    
    # Setup the environment
    await env.setup()
    
    print("=== Jupyter Notebook Environment Example with Real-time Interaction ===\n")
    print("IMPORTANT: After each interaction, you may need to manually refresh your browser")
    print("to see the changes. Press F5 or Ctrl+R (Cmd+R on Mac) in the browser window.\n")
    
    # First, create a new notebook in the custom directory
    result = action_space.execute("create_notebook", {"notebook_path": os.path.join(custom_notebook_dir, "realtime_interaction_notebook.ipynb")})
    print(f"Create notebook result: {result}\n")
    
    # Start the Jupyter server with the custom notebook directory and open the notebook in the browser
    result = action_space.execute("start_jupyter_server", {"custom_notebook_dir": custom_notebook_dir})
    print(f"Start Jupyter server result: {result}\n")
    
    if result["status"] == "success":
        print(f"Opening notebook in browser: {result['url']}")
        print(f"Notebook directory: {result['notebook_dir']}")
        print("You can now see the notebook in your browser!")
        print("The agent will now interact with the notebook in real time.\n")
    
    # Wait a moment for the server to fully start and user to see the notebook
    print("Waiting 10 seconds to allow browser to load...")
    await asyncio.sleep(5)
    
    # Now add a code cell with some Python code
    code = """
import numpy as np
import matplotlib.pyplot as plt

# Create some sample data
x = np.linspace(0, 10, 100)
y = np.sin(x)

print(f"Created arrays with {len(x)} points")
"""
    print("Adding a code cell with data generation code...")
    print("Please refresh your browser (F5 or Ctrl+R) to see the new cell.")
    result = action_space.execute("add_cell", {"source": code, "cell_type": "code"})
    print(f"Add code cell result: {result}\n")
    
    # Add a markdown cell
    markdown = """
# My Analysis

This notebook contains an analysis of sine wave data.
"""
    print("Adding a markdown cell with a title...")
    result = action_space.execute("add_cell", {"source": markdown, "cell_type": "markdown"})
    print(f"Add markdown cell result: {result}\n")
    

    # Get notebook info
    print("Getting notebook info...")
    result = action_space.execute("get_notebook_info", {})
    print(f"Notebook info: {result}\n")

    
    # Execute the first cell (index 0) - this will execute in the browser too
    print("Executing the first cell (index 0)...")
    result = action_space.execute("execute_cell", {"cell_index": 0})
    print(f"Execute cell result: {result}\n")
    
    
    # Add a visualization cell
    viz_code = """
# Plot the data
plt.figure(figsize=(10, 5))
plt.plot(x, y)
plt.title("Sine Wave")
plt.xlabel("X values")
plt.ylabel("Y values (sin(x))")
plt.grid(True)
plt.show()
"""
    print("Adding a visualization code cell...")
    result = action_space.execute("add_cell", {"source": viz_code, "cell_type": "code"})
    print(f"Add visualization cell result: {result}\n")
    asyncio.sleep(2)  # Wait a bit for user to refresh and see the new cell
    # Execute the visualization cell
    print("Executing the visualization cell (the last cell)...")
    # Get the current number of cells to know the index of the last cell
    info_result = action_space.execute("get_notebook_info", {})
    asyncio.sleep(2)  # Wait a bit for user to refresh and see the new cell
    print(info_result)
    if info_result["status"] == "success":
        last_cell_index = info_result["num_cells"] - 1
        print(f"Executing cell at index {last_cell_index}...")
        result = action_space.execute("execute_cell", {"cell_index": last_cell_index})
        print(f"Execute visualization cell result: {result}\n")
    asyncio.sleep(2)  # Wait a bit for user to refresh and see the new cell
    
    # Execute the entire notebook
    print("Executing the entire notebook...")
    result = action_space.execute("execute_notebook", {})
    print(f"Execute notebook result: {result}\n")
    
    
    # Get notebook info again after execution
    result = action_space.execute("get_notebook_info", {})
    print(f"Final notebook info: {result}\n")
    
    print("All interactions completed. The notebook in your browser is fully updated!")

    # Stop the Jupyter server
    result = action_space.execute("stop_jupyter_server", {})
    print(f"Stop Jupyter server result: {result}\n")
    
    # Close the environment
    await env.close()
    
    print("Example completed successfully!")


if __name__ == "__main__":
    asyncio.run(main())