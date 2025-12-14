"""Onesided command - one-sided market making return analysis."""

from argparse import _SubParsersAction
from typing import Any

from ..cli import async_command_runner
from ..onesided_cli import print_analysis, run_analysis
from .validators import validate_positive, validate_probability


def register_onesided(subparsers: _SubParsersAction) -> None:
    """Register the 'onesided' subcommand."""
    parser = subparsers.add_parser(
        "onesided",
        help="One-sided market making analysis combining position EV with LP rewards",
    )

    # Arguments
    parser.add_argument("ticker", help="Market ticker (e.g., PRES-2024)")
    parser.add_argument("side", choices=["yes", "no"], help="Side to analyze")
    parser.add_argument(
        "your_prob",
        type=float,
        help="Your probability (0-1, e.g., 0.95 for 95%%)",
    )
    parser.add_argument("size", type=int, help="Position size in contracts")
    parser.add_argument(
        "--haircut",
        type=float,
        default=0.01,
        help="Probability reduction if filled (default: 0.01)",
    )
    parser.add_argument(
        "--fill-prob",
        type=float,
        default=0.5,
        help="Fill probability (default: 0.5)",
    )

    # Set handler
    parser.set_defaults(func=handle_onesided)


async def handle_onesided_async(args: Any) -> None:
    """Async handler for onesided command."""
    # Validation
    validate_probability(args.your_prob, "your_prob")
    validate_probability(args.haircut, "haircut", allow_zero=True)
    validate_probability(args.fill_prob, "fill_prob")
    validate_positive(args.size, "size")

    # Run analysis (reuse existing function)
    result = await run_analysis(
        ticker=args.ticker,
        side=args.side,
        your_prob=args.your_prob,
        size=args.size,
        haircut=args.haircut,
        fill_prob=args.fill_prob,
    )

    # Display results (reuse existing function)
    print_analysis(result)


def handle_onesided(args: Any) -> None:
    """Sync handler that wraps async handler."""
    async_command_runner(handle_onesided_async, args)
