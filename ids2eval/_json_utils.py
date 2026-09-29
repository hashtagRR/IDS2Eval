"""Shared json.dumps(default=...) handler for numpy scalar/array types.

Findings can carry numpy bool/int/float scalars or arrays in their `details`
(most checks compute over pandas/numpy data), which the stdlib json module
doesn't know how to serialize on its own. Shared rather than duplicated
since both cli.py's output-writing and audit/_checkpoint.py's checkpoint
writing need the exact same conversion.
"""

from __future__ import annotations

import numpy as np


def json_default(obj):
    if isinstance(obj, np.bool_):
        return bool(obj)
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, np.floating):
        return float(obj)
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")
