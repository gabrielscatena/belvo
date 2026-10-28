#!/usr/bin/env python3
"""Run the challenge-specific EDA without installing the project package."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from belvo.data.eda import main

if __name__ == "__main__":
    raise SystemExit(main())
