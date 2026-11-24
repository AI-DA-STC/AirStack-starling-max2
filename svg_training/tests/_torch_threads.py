"""Torch's default intra-op thread count, read in a fresh process (24 Nov 2026).

Some test modules call ``torch.set_num_threads(2)`` in fixtures and never restore it (for example
``test_ste_l03.py``). Bit-exact goldens recorded at the default count then fail when they run later in the same
session, because a CPU reduction's order follows the thread count. Tests that compare bit for bit use
``default_torch_threads`` to run at the count their goldens were recorded with and restore the previous count after.
"""
import subprocess
import sys

import pytest
import torch

DEFAULT_THREADS = int(subprocess.run([sys.executable, "-c", "import torch; print(torch.get_num_threads())"],
                                     capture_output=True, text=True, check=True).stdout.strip())


@pytest.fixture(autouse=True)
def default_torch_threads():
    old = torch.get_num_threads()
    torch.set_num_threads(DEFAULT_THREADS)
    yield
    torch.set_num_threads(old)
