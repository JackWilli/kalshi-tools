"""Analyze command - analyze all active liquidity incentive programs."""

from argparse import _SubParsersAction
from typing import Any

from ..analyze_cli import analyze_incentives
from ..cli import async_command_runner
from .validators import validate_positive


def register_analyze(subparsers: _SubParsersAction) -> None:
    """Register the 'analyze' subcommand."""
    parser = subparsers.add_parser(
        "analyze",
        help="Analyze all active liquidity incentive programs",
    )

    # Arguments
    parser.add_argument(
        "--min-roi",
        type=float,
        default=0.0,
        help="Minimum net ROI per day to display (%%, default: 0.0)",
    )
    parser.add_argument(
        "--max-capital",
        type=float,
        default=1000.0,
        help="Maximum capital to simulate per side (default: 1000.0)",
    )
    parser.add_argument(
        "--top-n",
        type=int,
        default=20,
        help="Number of top opportunities to show in summary (default: 20)",
    )
    parser.add_argument(
        "--show-all",
        action="store_true",
        help="Show all opportunities, even non-viable ones",
    )

    # Set handler
    parser.set_defaults(func=handle_analyze)


async def handle_analyze_async(args: Any) -> None:
    """Async handler for analyze command."""
    # Validation
    validate_positive(args.max_capital, "max-capital")
    validate_positive(args.top_n, "top-n")

    # Run analysis
    await analyze_incentives(
        min_roi=args.min_roi,
        max_capital_per_side=args.max_capital,
        top_n=args.top_n,
        show_all=args.show_all,
    )


def handle_analyze(args: Any) -> None:
    """Sync handler that wraps async handler."""
    async_command_runner(handle_analyze_async, args)
