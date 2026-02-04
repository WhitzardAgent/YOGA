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
        "pyyaml>=6.0",
        "openai>=1.0.0",
        "paramiko>=3.0.0",
        "requests>=2.31.0",
        "beautifulsoup4>=4.12.0",
        "tenacity>=8.2.0",
        "nbformat>=5.9.0",
        "nbclient>=0.8.0",
        "rich>=13.0.0",
        "colorama>=0.4.6",
        "pydantic>=2.0.0",
        "fastapi>=0.100.0",
        "sse-starlette>=1.6.0",
        "typer>=0.9.0",
        "pandas>=2.0.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "pytest-asyncio>=0.21.0",
            "black>=23.0.0",
            "mypy>=1.0.0",
        ],
    },
    python_requires=">=3.10",
)
