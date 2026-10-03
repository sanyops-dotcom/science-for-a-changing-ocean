"""Module 4/6 - temporal / seasonal.

The current Master file has no date/time column, so the eligibility gate says NOT_SUPPORTED and a
`not_run` record is written. This module activates when the reader supplies a date column.
"""
from stats.common import Context
from stats.util import skip_if_unsupported


def run(ctx: Context) -> None:
    skip_if_unsupported(ctx, "temporal", "temporal", "Temporal / seasonal analysis")
