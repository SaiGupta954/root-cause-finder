import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "backend"))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tests"))

DATA = os.path.join(ROOT, "tests", "data")


@pytest.fixture
def data_path():
    return lambda name: os.path.join(DATA, name)
