"""Scale command - analyze how ROI changes as position size increases."""

from argparse import _SubParsersAction
from typing import Any

from ..cli import async_command_runner
from ..scale_cli import display_scale_analysis, run_scale_analysis
from .validators import validate_positive, validate_probability


def register_scale(subparsers: _SubParsersAction) -> None:
    """Register the 'scale' subcommand."""
    parser = subparsers.add_parser(
        "scale",
        help="Scale analysis showing ROI diminishing returns",
    )

    # Arguments
    parser.add_argument("ticker", help="Market ticker (e.g., PRES-2024)")
    parser.add_argument("side", choices=["yes", "no"], help="Side to analyze")
    parser.add_argument(
        "--your-prob",
        type=float,
        default=0.95,
        help="Your probability (0-1, default: 0.95)",
    )
    parser.add_argument(
        "--haircut",
        type=float,
        default=0.01,
        help="Haircut (default: 0.01)",
    )
    parser.add_argument(
        "--fill-prob",
        type=float,
        default=0.5,
        help="Fill probability (default: 0.5)",
    )
    parser.add_argument(
        "--max-size",
        type=int,
        default=1000,
        help="Maximum position size to analyze (default: 1000)",
    )
    parser.add_argument(
        "--points",
        type=int,
        default=20,
        help="Number of data points to calculate (default: 20)",
    )
    parser.add_argument(
        "--no-plot",
        action="store_true",
        help="Skip matplotlib charts (text output only)",
    )

    # Set handler
    parser.set_defaults(func=handle_scale)


async def handle_scale_async(args: Any) -> None:
    """Async handler for scale command."""
    # Validation
    validate_probability(args.your_prob, "your-prob")
    validate_probability(args.haircut, "haircut", allow_zero=True)
    validate_probability(args.fill_prob, "fill-prob")
    validate_positive(args.max_size, "max-size")
    validate_positive(args.points, "points")

    # Run analysis
    result = await run_scale_analysis(
        ticker=args.ticker,
        side=args.side,
        your_prob=args.your_prob,
        haircut=args.haircut,
        fill_prob=args.fill_prob,
        max_size=args.max_size,
        num_points=args.points,
    )

    # Display results
    display_scale_analysis(result, plot=not args.no_plot)


def handle_scale(args: Any) -> None:
    """Sync handler that wraps async handler."""
    async_command_runner(handle_scale_async, args)
