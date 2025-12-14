"""Snapshot command - analyze LP score for a specific market."""

from argparse import _SubParsersAction
from typing import Any

from ..cli import async_command_runner
from ..snapshot_cli import _run as run_snapshot_analysis
from .validators import validate_positive


def register_snapshot(subparsers: _SubParsersAction) -> None:
    """Register the 'snapshot' subcommand."""
    parser = subparsers.add_parser(
        "snapshot",
        help="Snapshot analysis of your LP score for a specific market",
    )

    # Arguments
    parser.add_argument("ticker", help="Market ticker (e.g., PRES-2024)")
    parser.add_argument(
        "--target-size",
        type=int,
        required=True,
        help="Program target size in contracts",
    )
    parser.add_argument(
        "--discount-factor",
        type=float,
        required=True,
        help="Program discount factor (e.g., 0.9)",
    )
    parser.add_argument(
        "--lp-rewards-dollars",
        type=float,
        required=True,
        help="Total LP rewards pool in dollars",
    )

    # Set handler
    parser.set_defaults(func=handle_snapshot)


async def handle_snapshot_async(args: Any) -> None:
    """Async handler for snapshot command."""
    # Validation
    validate_positive(args.target_size, "target-size")
    validate_positive(args.discount_factor, "discount-factor")
    validate_positive(args.lp_rewards_dollars, "lp-rewards-dollars")

    # Run analysis (reuse existing function)
    await run_snapshot_analysis(
        ticker=args.ticker,
        target_size=args.target_size,
        discount_factor=args.discount_factor,
        lp_rewards_dollars=args.lp_rewards_dollars,
    )


def handle_snapshot(args: Any) -> None:
    """Sync handler that wraps async handler."""
    async_command_runner(handle_snapshot_async, args)
