from pathlib import Path
from setuptools import setup, find_packages

ROOT_DIR = Path(__file__).parent
README = (ROOT_DIR / "README.md").read_text(encoding="utf-8")

setup(
    name="toolanything",
    version="0.1.0",
    description="One function to MCP and Tool calling",
    long_description=README,
    long_description_content_type="text/markdown",
    author="ToolAnything",
    license="MIT",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    python_requires=">=3.10",
    install_requires=[],
    entry_points={
        "console_scripts": [
            "toolanything=toolanything.cli:main",
        ],
    },
)
