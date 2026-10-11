"""Finding statuses.

"ok", "warning" and "flag" are results: the check ran on its input and measured
something. NOT_APPLICABLE means the check could not produce a result on this
input (no configured column, a pre-split dataset where raw files are needed, too
few classes or rows to test), so it says nothing about the dataset either way.
It never raises the overall verdict and is counted separately in the scorecard.
"""

OK = "ok"
WARNING = "warning"
FLAG = "flag"
NOT_APPLICABLE = "not_applicable"

STATUSES = (OK, WARNING, FLAG, NOT_APPLICABLE)
