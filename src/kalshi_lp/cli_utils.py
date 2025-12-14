"""
Utility functions for CLI modules.

This module contains shared formatting and display functions used across
all CLI entry points, eliminating duplicate code.
"""


def format_percent(value: float, show_sign: bool = False) -> str:
    """
    Format a percentage value for display.

    Args:
        value: Percentage value (e.g., 5.0 for 5%)
        show_sign: If True, show + sign for positive values

    Returns:
        Formatted percentage string (e.g., "+5.00%" or "5.00%")
    """
    if show_sign and value >= 0:
        return f"+{value:.2f}%"
    return f"{value:.2f}%"


def print_section(title: str, width: int = 80, char: str = "=") -> None:
    """
    Print a formatted section header.

    Args:
        title: Section title to display
        width: Total width of the banner (default: 80)
        char: Character to use for the banner lines (default: "=")
    """
    print()
    print(char * width)
    print(title)
    print(char * width)
