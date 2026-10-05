"""Shared lookup for audit.materiality_thresholds overrides.

Each check that compares a metric against a materiality threshold keeps its
own default as a module-level constant (see that check's own module for why
its specific number was chosen); this only looks up whether the config
overrides it. Validated in config.py's validate_config, not here - by the
time a check calls this, the config has already passed validation, so this
stays a trusting, unconditional lookup rather than repeating those checks.
"""

from __future__ import annotations


def threshold(cfg: dict, check: str, default):
    """Return cfg['audit']['materiality_thresholds'][check] if set, else default."""
    return cfg["audit"]["materiality_thresholds"].get(check, default)


def accuracy_gap_margin(acc_a: float, n_a: int, acc_b: float, n_b: int) -> float:
    """Half-width of a 95% normal-approximation interval on the difference
    between two accuracies measured on test sets of n_a and n_b rows.

    Treats the two test sets as independent, which is conservative when they
    share rows (a paired difference has smaller variance), so a gap that clears
    a threshold by more than this margin is not just test-set sampling noise.
    """
    var = acc_a * (1 - acc_a) / max(n_a, 1) + acc_b * (1 - acc_b) / max(n_b, 1)
    return 1.959964 * var ** 0.5
