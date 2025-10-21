"""Text utility functions."""


def append_text(
    new_text: str,
    existing_text: str | None,
    separator: str = "\n",
) -> str:
    """Append text to existing text with separator.

    Args:
        new_text: Text to append
        existing_text: Existing text (or None)
        separator: Separator to use (default: newline)

    Returns:
        Combined text

    Example:
        >>> append_text("line2", "line1", "\\n")
        "line1\\nline2"
        >>> append_text("line1", None, "\\n")
        "line1"
    """
    if existing_text is None:
        return new_text

    return f"{existing_text}{separator}{new_text}"
