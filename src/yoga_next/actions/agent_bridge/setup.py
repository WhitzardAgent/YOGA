"""
Agent Bridge 安装配置
"""

from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

with open("requirements.txt", "r", encoding="utf-8") as fh:
    requirements = [line.strip() for line in fh if line.strip() and not line.startswith("#")]

setup(
    name="agent-bridge",
    version="1.0.0",
    author="Agent Bridge Team",
    author_email="contact@agentbridge.dev",
    description="Cloud-Local Bridge Framework for Agent Computing",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/your-org/agent-bridge",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: System :: Networking",
        "Topic :: System :: Systems Administration",
    ],
    python_requires=">=3.8",
    install_requires=requirements,
    extras_require={
        "dev": [
            "pytest>=7.4.0",
            "pytest-asyncio>=0.21.0",
            "black>=23.0.0",
            "isort>=5.12.0",
            "mypy>=1.5.0",
        ],
        "analysis": [
            "pylint>=2.17.0",
            "flake8>=6.0.0",
            "bandit>=1.7.0",
            "mccabe>=0.7.0",
        ],
        "scraping": [
            "beautifulsoup4>=4.12.0",
            "lxml>=4.9.0",
            "selenium>=4.0.0",
        ],
        "notion": [
            "notion-client>=2.0.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "agent-bridge=agent_bridge.cli:main",
        ],
    },
    include_package_data=True,
    package_data={
        "agent_bridge": ["*.py", "templates/*", "configs/*"],
    },
)