from setuptools import setup, find_packages

setup(
    name="yoga_next",
    version="0.1.0",
    description="A Python package for AI agent system",
    author="Yoga-Next Team",
    author_email="",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    install_requires=[
        "pyyaml",      # For YAML parsing
        "openai",      # For OpenAI API integration
        "paramiko",    # For SSH connections in agent_bridge
        "requests",    # For HTTP requests in agent_bridge
        "beautifulsoup4",  # For HTML parsing in agent_bridge
        "tenacity",    # For retry logic in model.py
        "nbformat",    # For Jupyter notebook format handling
        "nbclient",    # For executing Jupyter notebooks
    ],
    extras_require={
        "dev": [
            # Add development dependencies here
        ],
    },
    python_requires=">=3.7",
)