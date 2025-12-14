"""
Unified CLI entry point for kalshi-lp command.

Consolidates all 5 separate CLI commands into a single command with subcommands,
eliminating ~100 lines of duplicate boilerplate code.

Usage:
    kalshi-lp analyze [OPTIONS]
    kalshi-lp debug TICKER [OPTIONS]
    kalshi-lp onesided TICKER SIDE YOUR_PROB SIZE [OPTIONS]
    kalshi-lp scale TICKER SIDE [OPTIONS]
    kalshi-lp snapshot TICKER [OPTIONS]
"""

import argparse
import asyncio
import sys
from typing import Any, Callable


def async_command_runner(func: Callable, args: Any) -> None:
    """
    Shared async command runner with error handling.

    Eliminates duplicated asyncio.run() + try/except patterns across all CLIs.

    Args:
        func: Async function to run
        args: Parsed command-line arguments

    Raises:
        SystemExit: Always exits with appropriate code
    """
    try:
        asyncio.run(func(args))
    except KeyboardInterrupt:
        print("\nOperation interrupted by user")
        sys.exit(1)
    except ValueError as e:
        print(f"\nError: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\nUnexpected error: {e}")
        sys.exit(1)


def main() -> None:
    """Main CLI entry point with subcommands."""
    parser = argparse.ArgumentParser(
        prog="kalshi-lp",
        description="Kalshi Liquidity Provider Analysis Tools",
    )

    subparsers = parser.add_subparsers(
        dest="command",
        required=True,
        help="Available commands",
    )

    # Register each subcommand
    from .commands import (
        register_analyze,
        register_debug,
        register_onesided,
        register_scale,
        register_snapshot,
    )

    register_analyze(subparsers)
    register_debug(subparsers)
    register_onesided(subparsers)
    register_scale(subparsers)
    register_snapshot(subparsers)

    args = parser.parse_args()

    # Each subcommand sets a 'func' attribute via set_defaults()
    args.func(args)


if __name__ == "__main__":
    main()
