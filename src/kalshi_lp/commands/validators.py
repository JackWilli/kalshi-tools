"""
Shared validation functions for CLI arguments.

Eliminates duplicate validation logic across command modules.
"""

import sys


def validate_probability(
    value: float,
    name: str,
    allow_zero: bool = False,
) -> None:
    """
    Validate probability value (0-1 or 0<=val<1).

    Args:
        value: Value to validate
        name: Parameter name for error message
        allow_zero: If True, allow 0 (for haircut); else require > 0

    Raises:
        SystemExit: If validation fails
    """
    if allow_zero:
        if not 0 <= value < 1:
            print(f"Error: {name} must be between 0 and 1")
            sys.exit(1)
    else:
        if not 0 < value <= 1:
            print(f"Error: {name} must be between 0 and 1 (exclusive)")
            sys.exit(1)


def validate_positive(value: float, name: str) -> None:
    """
    Validate positive number.

    Args:
        value: Value to validate
        name: Parameter name for error message

    Raises:
        SystemExit: If validation fails
    """
    if value <= 0:
        print(f"Error: {name} must be positive")
        sys.exit(1)
