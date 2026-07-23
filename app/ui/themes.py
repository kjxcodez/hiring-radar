"""Terminal UX themes stylesheets catalog."""

from __future__ import annotations

from typing import Dict


THEMES: Dict[str, Dict[str, str]] = {
    "default": {
        "primary": "cyan",
        "secondary": "magenta",
        "success": "green",
        "warning": "yellow",
        "error": "red",
        "border": "blue",
        "prompt": "cyan",
    },
    "dracula": {
        "primary": "#ff79c6",
        "secondary": "#bd93f9",
        "success": "#50fa7b",
        "warning": "#f1fa8c",
        "error": "#ff5555",
        "border": "#6272a4",
        "prompt": "#bd93f9",
    },
    "nord": {
        "primary": "#88c0d0",
        "secondary": "#b48ead",
        "success": "#a3be8c",
        "warning": "#ebcb8b",
        "error": "#bf616a",
        "border": "#4c566a",
        "prompt": "#8fbcbb",
    },
    "solarized": {
        "primary": "#268bd2",
        "secondary": "#d33682",
        "success": "#859900",
        "warning": "#b58900",
        "error": "#dc322f",
        "border": "#586e75",
        "prompt": "#2aa198",
    },
    "minimal": {
        "primary": "white",
        "secondary": "bright_black",
        "success": "white",
        "warning": "white",
        "error": "bright_black",
        "border": "bright_black",
        "prompt": "white",
    }
}


def get_theme_colors(theme_name: str) -> Dict[str, str]:
    """Retrieve color dictionary mapping for requested theme name."""
    name = theme_name.lower().strip()
    return THEMES.get(name, THEMES["default"])
