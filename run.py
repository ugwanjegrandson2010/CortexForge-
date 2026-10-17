#!/usr/bin/env python3
"""Run CortexForge without installing it.

    python3 run.py                 # start on 127.0.0.1:8731
    python3 run.py --port 9000
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from cortexforge.server import main  # noqa: E402

if __name__ == "__main__":
    main()
