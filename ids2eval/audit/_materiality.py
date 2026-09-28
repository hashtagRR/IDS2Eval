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
