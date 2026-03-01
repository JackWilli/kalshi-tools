"""
Command modules for unified kalshi-lp CLI.

Each module provides a register_<command>() function that adds a subcommand
to the main CLI parser.
"""

from .analyze import register_analyze
from .debug import register_debug
from .onesided import register_onesided
from .scale import register_scale
from .snapshot import register_snapshot

__all__ = [
    "register_analyze",
    "register_debug",
    "register_onesided",
    "register_scale",
    "register_snapshot",
]
