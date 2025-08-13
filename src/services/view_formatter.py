# services/view_formatter.py
"""
Utility functions for formatting text output for the GUI.
"""


def format_as_box(title: str, content: str) -> str:
    """
    Wraps a title and content in a cool retro ASCII box.
    This version handles multi-line content correctly.
    """
    lines = content.split('\n')

    # Find the longest line to determine the width of the box
    # Consider both the title and the content lines
    max_len = len(title)
    if lines:
        max_len = max(len(title), max(len(line) for line in lines))

    # Top border with centered title
    title_padding = (max_len - len(title)) // 2
    top_border = f"┌─{'─' * title_padding} {title} {'─' * (max_len - len(title) - title_padding)}─┐"

    # Content lines
    content_lines = [f"│ {line.ljust(max_len)} │" for line in lines]

    # Bottom border
    bottom_border = f"└{'─' * (max_len + 2)}┘"

    # Join all parts
    return "\n".join([top_border] + content_lines + [bottom_border])