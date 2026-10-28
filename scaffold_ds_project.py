#!/usr/bin/env python3
"""Creates a reusable project structure for Data Science, Machine Learning, and optimization projects.

Examples:
    python scaffold_ds_project_en.py .
    python scaffold_ds_project_en.py ./my-new-project
    python scaffold_ds_project_en.py . --package collections_engine

Safe for existing repositories: never overwrites files.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


def package_name(name: str) -> str:
    """Converts a repository name into a valid Python identifier."""
    normalized = re.sub(r"[^a-zA-Z0-9_]+", "_", name).strip("_").lower()
    normalized = re.sub(r"_+", "_", normalized)
    if not normalized:
        raise ValueError("The project name cannot be empty.")
    if normalized[0].isdigit():
        normalized = f"project_{normalized}"
    return normalized


def create_file(path: Path, content: str) -> bool:
    """Creates a new file without overwriting an existing one."""
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("x", encoding="utf-8", newline="\n") as f:
            f.write(content)
    except FileExistsError:
        return False
    return True


def markdown(title: str, description: str) -> str:
    return f"# {title}\n\n{description}\n\n## Context\n\nTODO\n\n## Decisions and Evidence\n\nTODO\n\n## Open Questions\n\nTODO\n"


def notebook() -> str:
    data = {
        "cells": [
            {
                "cell_type": "markdown",
                "metadata": {},
                "source": [
                    "# 01 — Data Profiling and EDA\\n".replace("\\n", "\n"),
                    "Load the data from `data/raw/` and assess quality, distributions, and integrity.\n",
                ],
            },
            {
                "cell_type": "code",
                "execution_count": None,
                "metadata": {},
                "outputs": [],
                "source": ["from pathlib import Path\n", "\n", "DATA_DIR = Path('../data/raw')\n", "print(DATA_DIR.resolve())\n"],
            },
        ],
        "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"}},
        "nbformat": 4,
        "nbformat_minor": 5,
    }
    return json.dumps(data, ensure_ascii=False, indent=2) + "\n"


def build_template(project: str, package: str) -> dict[str, str]:
    docs = {
        "01_business_process.md": ("Business Process", "Describe the actors, inputs, steps, outputs, and feedback loops in the process."),
        "02_domain_model.md": ("Domain Model / ERD", "Describe entities, cardinalities, keys, and temporal granularity."),
        "03_economic_model.md": ("Economic Model", "Map revenue, costs, contractual commitments, margins, and financial rules."),
        "04_problem_framing.md": ("Problem Framing", "Formalize decisions, the objective function, constraints, and planning horizon."),
        "05_architecture.md": ("System Architecture", "Describe components, data flows, storage, deployment, observability, and trade-offs."),
        "06_assumptions_and_risks.md": ("Assumptions and Risks", "Record assumptions, evidence, limitations, risks, and validation approaches."),
    }
    contents: dict[str, str] = {
        "README.md": f"""# {project}

Data Science / Machine Learning / optimization project.

## Objective

TODO: Describe the business problem, objective function, and success criteria.

## Project Structure

- `data/`: raw, external, intermediate, and processed data (not tracked by Git by default).
- `conf/`: non-sensitive configuration files.
- `docs/`: domain discovery, decisions, architecture, and risks.
- `diagrams/`: version-controlled Mermaid diagrams.
- `notebooks/`: exploration and experimentation.
- `src/{package}/`: importable application code.
- `scripts/`: operational commands and tasks.
- `tests/`: automated tests.
- `artifacts/models/`: generated models and artifacts (not tracked by Git by default).
- `reports/figures/`: figures and reports.

## Installation

```bash
python -m venv .venv
source .venv/bin/activate  # Windows PowerShell: .venv\\Scripts\\Activate.ps1
python -m pip install -e \".[dev]\"
```

## Run Checks

```bash
python -m pytest -q
python -m ruff check .
```

## Data

Copy local datasets to `data/raw/`. For safety, data files are not tracked by Git.
Never commit secrets or personal data.

## Running the Pipeline

TODO: Document the entry-point command after implementing the pipeline.
""",
        ".gitignore": """# Python
__pycache__/
*.py[cod]
*.egg-info/
.eggs/
build/
dist/
.pytest_cache/
.ruff_cache/
.mypy_cache/
.coverage
htmlcov/

# Notebooks
.ipynb_checkpoints/

# Environments / credentials
.venv/
venv/
.env
.env.*
!.env.example

# IDE / OS
.DS_Store
.idea/
.vscode/

# Generated runtime artifacts
logs/
**/*.log
""",
        ".env.example": """# Example values only; never put real credentials in this file.
APP_ENV=local
LOG_LEVEL=INFO
""",
        "pyproject.toml": f"""[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[project]
name = "{project}"
version = "0.1.0"
description = "Data Science and decision-engine project"
requires-python = ">=3.10"
dependencies = []

[project.optional-dependencies]
dev = ["pytest>=8.0", "ruff>=0.6", "ipykernel>=6.0"]
data = ["pandas>=2.0", "numpy>=1.24", "PyYAML>=6.0", "scikit-learn>=1.3"]

[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
testpaths = ["tests"]

[tool.ruff]
line-length = 100
""",
        "Makefile": """.PHONY: setup setup-data test lint
setup:
\tpython -m pip install -e \".[dev]\"

setup-data:
\tpython -m pip install -e \".[dev,data]\"

test:
\tpython -m pytest -q

lint:
\tpython -m ruff check .
""",
        "conf/base.yaml": """# Non-sensitive configuration settings (customize for your project).
project:
  seed: 42
paths:
  raw: data/raw
  interim: data/interim
  processed: data/processed
  models: artifacts/models
""",
        "data/.gitignore": """# Real datasets should not be tracked by Git by default.
/raw/**
/interim/**
/processed/**
/external/**
!/raw/.gitkeep
!/interim/.gitkeep
!/processed/.gitkeep
!/external/.gitkeep
""",
        "artifacts/models/.gitignore": """*
!.gitignore
!.gitkeep
""",
        "reports/figures/.gitkeep": "",
        "data/raw/.gitkeep": "",
        "data/interim/.gitkeep": "",
        "data/processed/.gitkeep": "",
        "data/external/.gitkeep": "",
        "notebooks/01_data_profiling.ipynb": notebook(),
        f"src/{package}/__init__.py": '"""Main project package."""\n\n__version__ = "0.1.0"\n',
        "tests/test_package.py": f"""from {package} import __version__


def test_package_has_version() -> None:
    assert __version__ == "0.1.0"
""",
        "scripts/README.md": """# Scripts

Place operational commands here (data preparation, training, evaluation, batch execution).
Keep business logic in `src/` and import it from your scripts.
""",
        ".github/workflows/ci.yml": """name: CI
on:
  push:
  pull_request:

jobs:
  checks:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - run: python -m pip install -e \".[dev]\"
      - run: python -m ruff check .
      - run: python -m pytest -q
""",
    }
    for file_name, (title, purpose) in docs.items():
        contents[f"docs/{file_name}"] = markdown(title, purpose)
    for file_name, title in {
        "business_flow.mmd": "Business flow",
        "entity_relationship.mmd": "Entity relationship model",
        "economic_flow.mmd": "Economic flow",
    }.items():
        contents[f"diagrams/{file_name}"] = f"flowchart LR\n    A[\"{title}: TODO\"] --> B[\"Detail\"]\n"

    for directory in ("data", "features", "models", "optimization", "evaluation", "pipelines", "utils"):
        contents[f"src/{package}/{directory}/__init__.py"] = ""
    return contents


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "root", nargs="?", default=".", type=Path,
        help="Project directory (default: current directory)",
    )
    parser.add_argument("--name", help="Project name (default: directory name)")
    parser.add_argument("--package", help="Python package name under src/ (default: derived from project name)")
    args = parser.parse_args()

    root = args.root.expanduser().resolve()
    name = args.name or root.name
    package = args.package or package_name(name)
    if not package.isidentifier() or __import__("keyword").iskeyword(package):
        parser.error("--package must be a valid Python identifier (e.g., collections_engine).")
    if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_.-]*", name):
        parser.error("--name must contain only letters, numbers, hyphens, underscores, or periods.")

    root.mkdir(parents=True, exist_ok=True)
    created: list[str] = []
    skipped: list[str] = []
    for relative, content in build_template(name, package).items():
        if create_file(root / relative, content):
            created.append(relative)
        else:
            skipped.append(relative)

    print(f"Project: {root}")
    print(f"Python package: {package}")
    print(f"Files created: {len(created)} | existing files preserved: {len(skipped)}")
    if skipped:
        print("Existing files left unchanged:")
        for filename in skipped:
            print(f"  - {filename}")
    print("\nNext steps:")
    print(f"  cd {root}")
    print("  python -m pip install -e \".[dev]\"")
    print("  python -m pytest -q")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
