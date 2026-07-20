"""Shared console, container singleton, and CLI helper functions.

All command modules import from here instead of the top-level package to
avoid circular imports (command modules cannot import from app.cli.__init__
because __init__ imports from them).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from rich.console import Console
from rich.panel import Panel

from app.config import settings
from app.resume.versions import resolve_resume_version
from app.services.config import ServiceContainer


def resolve_symbol(name: str, fallback: Any) -> Any:
    """Retrieve the value of an attribute from the app.cli module.

    Allows tests to patch symbols (e.g. settings, load_applications, etc.)
    on app.cli, and ensures that modular sub-commands fetch the mocked version.
    """
    import sys
    if "app.cli" in sys.modules:
        val = getattr(sys.modules["app.cli"], name, fallback)
        if type(val).__name__ in ("ConsoleProxy", "ModuleProxy", "FuncProxy"):
            return fallback
        return val
    return fallback




class ConsoleProxy:
    def __getattr__(self, name: str) -> Any:
        return getattr(resolve_symbol("console", _real_console), name)


class ModuleProxy:
    def __init__(self, name: str, fallback_module: Any):
        self._name = name
        self._fallback = fallback_module

    def __getattr__(self, name: str) -> Any:
        return getattr(resolve_symbol(self._name, self._fallback), name)


class FuncProxy:
    def __init__(self, name: str, fallback_func: Any):
        self._name = name
        self._fallback = fallback_func

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        return resolve_symbol(self._name, self._fallback)(*args, **kwargs)


# ---------------------------------------------------------------------------
# Global console — all command modules share this single instance.
# ---------------------------------------------------------------------------


_real_console = Console()
console: Any = ConsoleProxy()

# ---------------------------------------------------------------------------
# ServiceContainer singleton
# ---------------------------------------------------------------------------

_container: Optional[ServiceContainer] = None



def get_container() -> ServiceContainer:
    """Return (or lazily create) the shared ServiceContainer singleton."""
    global _container
    if _container is None:
        _container = ServiceContainer()
    return _container


def reset_container() -> None:
    """Reset the ServiceContainer singleton.

    Forces re-initialisation on the next call to get_container().
    Used in tests to propagate patched settings into the container.
    """
    global _container
    _container = None


# ---------------------------------------------------------------------------
# Resume path resolution helper
# ---------------------------------------------------------------------------

def resolve_resume_path(resume_arg: Optional[str]) -> Optional[Path]:
    """Resolve a resume option (label or path string) to a Path, falling back to settings.resume_path."""
    curr_settings = resolve_symbol("settings", settings)
    if not resume_arg:
        return curr_settings.resume_path

    curr_path_cls = resolve_symbol("Path", Path)
    p = curr_path_cls(resume_arg)
    if p.exists() and p.is_file():
        return p

    return resolve_resume_version(resume_arg)




# ---------------------------------------------------------------------------
# Outreach preview panel helper
# ---------------------------------------------------------------------------

def _render_preview_panel(
    company_name: str,
    recipient: str,
    subject: str,
    body: str,
    template_used: str,
) -> None:
    curr_console = resolve_symbol("console", console)
    content = (
        f"[bold]To:[/bold] {recipient}\n"
        f"[bold]Subject:[/bold] {subject}\n\n"
        f"{body}"
    )
    panel = Panel(
        content,
        title=f"[bold magenta]Outreach Preview: {company_name}[/bold magenta]",
        subtitle=f"[dim]Template: {template_used}[/dim]",
        expand=False,
        border_style="cyan",
    )
    curr_console.print()
    curr_console.print(panel)
    curr_console.print()


# ---------------------------------------------------------------------------
# Discovery event-callback factory
# ---------------------------------------------------------------------------

def build_discovery_event_callback() -> Any:
    """Return a closure that prints discovery progress events to the console."""

    def event_callback(event_type: str, data: dict[str, Any]) -> None:
        curr_console = resolve_symbol("console", console)
        if event_type == "query_start":
            curr_console.print(f"  Querying [bold]{data['source']}[/bold]...")
        elif event_type == "no_slugs":
            curr_console.print(
                f"  [yellow]⚠[/yellow]  No slugs for [bold]{data['source']}[/bold] — "
                f"add them to [dim]output/seed_slugs_{data['source']}.txt[/dim] and re-run."
            )
        elif event_type == "slugs_loaded":
            curr_console.print(f"    ({data['count']} slug(s) loaded)")
        elif event_type == "query_success":
            curr_console.print(f"  [green]✓[/green]  {data['source']}: {data['count']} company/companies found")
        elif event_type == "query_error":
            curr_console.print(f"  [red]✗[/red]  {data['source']}: error during discovery — {data['error']}")
        elif event_type == "existing_loaded":
            curr_console.print(f"  [dim]Loaded {data['count']} existing company/companies from {data['filepath']}[/dim]")
        elif event_type == "existing_load_failed":
            curr_console.print(f"  [yellow]⚠[/yellow]  Could not load existing data ({data['error']}) — starting fresh.")

    return event_callback

