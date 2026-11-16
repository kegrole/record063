"""Compatibility entry point for ``python -m unittest test_encnorm -v``.

The complete suite lives in ``tests/test_encnorm.py`` as required by the
deliverables; this thin module re-exports its unittest symbols from the repo
root so both common discovery commands run the same tests.
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from tests.test_encnorm import *  # noqa: F401,F403


if __name__ == "__main__":
    unittest.main()
