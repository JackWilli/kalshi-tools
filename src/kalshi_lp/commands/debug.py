"""Debug command - detailed step-by-step calculation analysis."""

from argparse import _SubParsersAction
from typing import Any

from ..cli import async_command_runner
from ..debug_cli import debug_market_analysis
from .validators import validate_positive


def register_debug(subparsers: _SubParsersAction) -> None:
    """Register the 'debug' subcommand."""
    parser = subparsers.add_parser(
        "debug",
        help="Debug step-by-step calculation for a market",
    )

    # Arguments
    parser.add_argument("ticker", help="Market ticker (e.g., PRES-2024)")
    parser.add_argument(
        "--max-capital",
        type=float,
        default=5000.0,
        help="Maximum capital to simulate per side (default: 5000.0)",
    )

    # Set handler
    parser.set_defaults(func=handle_debug)


async def handle_debug_async(args: Any) -> None:
    """Async handler for debug command."""
    # Validation
    validate_positive(args.max_capital, "max-capital")

    # Run debug analysis
    await debug_market_analysis(
        ticker=args.ticker,
        max_capital=args.max_capital,
    )


def handle_debug(args: Any) -> None:
    """Sync handler that wraps async handler."""
    async_command_runner(handle_debug_async, args)
