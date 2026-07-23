"""System integration and control commands: dashboard, mcp-serve, agent REPL."""

from __future__ import annotations

import os
import json
from datetime import date
from pathlib import Path
from typing import Annotated, Any, Optional

import typer
from rich.prompt import Prompt
from rich.markdown import Markdown

from app.cli.common import console, get_container

# ---------------------------------------------------------------------------
# 23. dashboard
# ---------------------------------------------------------------------------

def view_dashboard(
    input: Annotated[
        Path,
        typer.Option(
            "--input",
            help="Path to the JSON database/source file. Default: output/companies.json.",
        ),
    ] = Path("output/companies.json"),  # Handled fallback inline
    output: Annotated[
        Path,
        typer.Option(
            "--output",
            help="Path to save the generated static HTML dashboard. Default: output/dashboard.html.",
        ),
    ] = Path("output/dashboard.html"),
    open_browser: Annotated[
        bool,
        typer.Option(
            "--open/--no-open",
            help="Open the generated HTML dashboard directly in your default browser. Default: False.",
        ),
    ] = False,
) -> None:
    """Generate a self-contained static HTML dashboard for local data review."""
    import webbrowser
    container = get_container()
    
    # Resolve default settings.output_dir if input is generic relative path
    resolved_input = input
    if input == Path("output/companies.json"):
        resolved_input = container.settings.output_dir / "companies.json"

    console.print(f"Generating static dashboard from [bold cyan]{resolved_input}[/bold cyan]...")
    try:
        container.dashboard_service.generate_dashboard(output_path=output, input_path=resolved_input)
        console.print(f"[bold green][OK] Dashboard generated successfully![/bold green] Saved to: [dim]{output}[/dim]")

        if open_browser:
            console.print("Opening dashboard in your default browser...")
            webbrowser.open(output.absolute().as_uri())
    except Exception as exc:
        console.print(f"[bold red]Error generating dashboard:[/bold red] {exc}")
        raise typer.Exit(code=1) from exc


# ---------------------------------------------------------------------------
# 24. mcp-serve
# ---------------------------------------------------------------------------

def mcp_serve(
    transport: Annotated[
        str,
        typer.Option(
            "--transport",
            help="Transport protocol to run. Options: 'stdio', 'http', or 'sse'. Default: 'stdio'.",
        ),
    ] = "stdio",
    port: Annotated[
        int,
        typer.Option(
            "--port",
            help="Port to bind the HTTP/SSE transport server. Default: 8811.",
        ),
    ] = 8811,
    host: Annotated[
        str,
        typer.Option(
            "--host",
            help="Host address to bind the HTTP/SSE transport server. Default: '0.0.0.0'.",
        ),
    ] = "0.0.0.0",
) -> None:
    """Start the Model Context Protocol (MCP) server integration."""
    os.environ["MCP_TRANSPORT"] = transport.lower()
    os.environ["MCP_HTTP_PORT"] = str(port)
    os.environ["MCP_HTTP_HOST"] = host

    console.print(f"[bold green]Starting MCP server...[/bold green]")
    console.print(f"  [dim]Transport:[/dim] {transport}")
    if transport.lower() in ("http", "sse"):
        console.print(f"  [dim]Binding:[/dim]   {host}:{port}")

    # Lazy loaded to avoid loading all MCP fastmcp dependencies at standard CLI startup
    from mcp_server.server import main
    main()


# ---------------------------------------------------------------------------
# 25. agent
# ---------------------------------------------------------------------------

def show_repl_help() -> None:
    """Print clean categorized examples and help details for the Agent REPL."""
    from rich.panel import Panel
    from rich.table import Table
    from app.cli.common import console

    table = Table(title="Hiring Radar AI Agent Help Commands", show_header=True, header_style="bold magenta")
    table.add_column("Category", style="cyan", no_wrap=True)
    table.add_column("Example Prompt / Description", style="white")

    table.add_row("Job Search", '"recommend jobs matching my profile"\n"search Lever for software engineers"')
    table.add_row("Company Research", '"research Wealthfront"\n"show company Vercel info"')
    table.add_row("Resume Profile", '"score compatibility with Vercel"\n"suggest resume tailoring for Wealthfront"')
    table.add_row("Applications CRM", '"list my applications"\n"prepare outreach drafts for Vercel"')
    table.add_row("Monitoring Alerts", '"run change detection check"\n"show daily digest events"')
    table.add_row("Session Memory", '"what was my last question?"\n"recommend more jobs like the ones discussed"')
    table.add_row("General", '"help" (shows this table)\n"exit" / "quit" (terminates session)')

    console.print(Panel(table, border_style="cyan"))


def show_agent_dashboard(session: Any) -> None:
    """Renders a beautiful startup dashboard summarizing Hiring Radar status metrics."""
    from rich.panel import Panel
    from rich.text import Text
    from app.cli.common import console, get_container
    from app.config import settings, yaml_config

    container = get_container()
    
    # 1. Resume status
    resume_status = "[bold green]✓ Loaded[/bold green]" if settings.resume_path and settings.resume_path.exists() else "[bold yellow]Not Loaded[/bold yellow]"
    if settings.resume_path and settings.resume_path.exists():
        session.loaded_resume = settings.resume_path

    # 2. Database statistics directly from repositories
    try:
        companies_count = len(container.company_repo.load_all())
        jobs_count = sum(len(c.jobs) for c in container.company_repo.load_all())
    except Exception:
        companies_count = 0
        jobs_count = 0

    try:
        apps_count = len(container.application_repo.load_all())
    except Exception:
        apps_count = 0

    try:
        alerts_count = len(container.monitoring_repo.load_alerts())
    except Exception:
        alerts_count = 0

    try:
        recs_count = len(container.recommendation_repo.load_recommendations())
    except Exception:
        recs_count = 0
    
    # 3. Memory status
    memory_path = settings.output_dir / "agent_memory.json"
    memory_status = "[bold green]Enabled[/bold green]" if memory_path.exists() else "[bold yellow]Inactive[/bold yellow]"

    # 4. Database Status Check
    db_status = "[bold green]Integral[/bold green]" if companies_count > 0 or apps_count > 0 else "[bold yellow]Empty[/bold yellow]"

    # 5. AI Provider and Debug Mode
    ai_provider = settings.openrouter_model or "OpenRouter Default"
    debug_mode = "[bold red]ON[/bold red]" if yaml_config.agent.show_debug_logs else "[bold green]OFF[/bold green]"

    dashboard_text = (
        f"[bold purple]━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━[/bold purple]\n\n"
        f"                   [bold white]🤖 Hiring Radar AI Agent[/bold white]\n\n"
        f"  [bold cyan]Resume:[/bold cyan]          {resume_status}\n"
        f"  [bold cyan]Companies:[/bold cyan]       {companies_count}\n"
        f"  [bold cyan]Jobs:[/bold cyan]            {jobs_count}\n"
        f"  [bold cyan]Applications:[/bold cyan]    {apps_count}\n"
        f"  [bold cyan]Recommendations:[/bold cyan] {recs_count}\n"
        f"  [bold cyan]Alerts:[/bold cyan]          {alerts_count}\n"
        f"  [bold cyan]Memory:[/bold cyan]          {memory_status}\n"
        f"  [bold cyan]Database Status:[/bold cyan] {db_status}\n"
        f"  [bold cyan]AI Provider:[/bold cyan]     [dim]{ai_provider}[/dim]\n"
        f"  [bold cyan]Debug Mode:[/bold cyan]      {debug_mode}\n\n"
        f"  Type [bold yellow]help[/bold yellow] for examples. Type [bold red]exit[/bold red] to quit.\n\n"
        f"[bold purple]━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━[/bold purple]"
    )
    console.print(dashboard_text)


agent_app = typer.Typer(
    name="agent",
    help="Start an interactive terminal reasoning agent loop (REPL) or run diagnostics.",
    no_args_is_help=False,
)


@agent_app.command(name="doctor")
def agent_doctor() -> None:
    """Check health, api keys, configuration files, and cross-repository consistency."""
    from app.debug.diagnostics import run_doctor
    run_doctor()


@agent_app.command(name="diagnostics")
def agent_diagnostics() -> None:
    """Check health, api keys, configuration files, and cross-repository consistency."""
    from app.debug.diagnostics import run_doctor
    run_doctor()


@agent_app.command(name="inspect-logging")
def agent_inspect_logging() -> None:
    """Display programmatic audit report of active loggers, propagation, and handlers."""
    from app.debug.logging_inspector import inspect_logging_infrastructure
    console.print(inspect_logging_infrastructure())


@agent_app.command(name="inspect-repositories")
def agent_inspect_repositories() -> None:
    """Scan and verify sizes, counts, and integrity statuses of database stores."""
    from app.debug.diagnostics import inspect_repositories
    inspect_repositories()


@agent_app.command(name="inspect-memory")
def agent_inspect_memory() -> None:
    """Print the contents of the persistent AI Agent memory database."""
    from app.debug.diagnostics import inspect_memory_state
    inspect_memory_state()


@agent_app.callback(invoke_without_command=True)
def agent(
    ctx: typer.Context,
    model: Annotated[
        Optional[str],
        typer.Option(
            "--model",
            help="OpenRouter model identifier override to use for the agent loop.",
        ),
    ] = None,
) -> None:
    """Start an interactive terminal reasoning agent loop (REPL)."""
    # Check if a subcommand was invoked. If so, don't start the REPL.
    if ctx.invoked_subcommand is not None:
        return

    # Lazy loaded to avoid importing heavy LLM / OpenRouter files during quick commands
    from app.agent.planner import run_agent_turn
    from app.agent.session import AgentSession
    from app.agent.progress import AgentProgressRenderer
    from app.agent.logging import setup_agent_logging
    from app.agent.cards import print_tool_result_card
    from app.config import yaml_config

    # 1. Setup logging isolation
    setup_agent_logging(show_debug_logs=yaml_config.agent.show_debug_logs)

    # 2. Initialize Session
    session = AgentSession()
    conversation_history: list[dict] = []

    # 3. Render Dashboard
    show_agent_dashboard(session)

    # 4. Instantiate Progress Renderer
    renderer = AgentProgressRenderer(
        show_progress=yaml_config.agent.show_progress,
        animations=yaml_config.agent.animations
    )
    container = get_container()
    container.workflow_engine.register_event_listener(renderer.handle_event)

    while True:
        # Run state validation and raise warnings if inconsistencies exist
        from app.agent.state_validator import validate_system_state
        warnings = validate_system_state()
        for w in warnings:
            console.print(f"[bold yellow]⚠️ System State Warning:[/bold yellow] {w}")

        try:
            user_msg = Prompt.ask("\n[bold cyan]Agent[/bold cyan]")
        except (KeyboardInterrupt, EOFError):
            console.print("\n[yellow]Session ended.[/yellow]")
            break

        cleaned_msg = user_msg.strip()
        if not cleaned_msg:
            continue

        if cleaned_msg.lower() in ("exit", "quit"):
            console.print("[yellow]Goodbye![/yellow]")
            break

        if cleaned_msg.lower() == "help":
            show_repl_help()
            continue

        if cleaned_msg.lower() in ("cancel", "stop"):
            console.print("[yellow]Prompt reset. Conversation memory cleared.[/yellow]")
            conversation_history.clear()
            session.clear()
            continue

        # Record last question in session memory
        session.last_question = cleaned_msg

        user_input_to_send = cleaned_msg
        while True:
            try:
                # Run the reasoning loop with live progress rendering
                with renderer:
                    res = run_agent_turn(
                        user_input_to_send,
                        conversation_history,
                        model=model,
                        session=session
                    )
                conversation_history = res["updated_history"]
            except KeyboardInterrupt:
                # Cancel active workflows if any
                active_ids = list(container.workflow_engine.active_contexts.keys())
                for context_id in active_ids:
                    container.workflow_engine.cancel(context_id)
                console.print("\n[yellow]Operation cancelled by user.[/yellow]")
                break
            except Exception as exc:  # noqa: BLE001
                console.print(f"[bold red]Error in agent loop:[/bold red] {exc}")
                break

            if "pending_approval" in res:
                pending = res["pending_approval"]
                tool_name = pending["tool"]
                args = pending["arguments"]
                tc_id = pending["tool_call_id"]
                desc = pending["description"]

                console.print(f"\n[bold yellow]⚠️ Pending Approval:[/bold yellow] Agent wants to {desc}")
                approved = typer.confirm("Approve this action?")

                from app.agent.tools import execute_approved_tool
                mem = container.memory_repo.load()

                if approved:
                    mem.setdefault("past_decisions", [])
                    mem["past_decisions"].append({
                        "date": date.today().isoformat(),
                        "action": f"Approved and executed tool '{tool_name}' with arguments {args}",
                    })
                    container.memory_repo.save(mem)
                    
                    # Track tool call in session
                    session.record_tool_call(tool_name, args)

                    try:
                        with renderer:
                            tool_result = execute_approved_tool(tool_name, args)
                        
                        # Print Rich Card representation if enabled
                        print_tool_result_card(tool_name, tool_result)
                    except KeyboardInterrupt:
                        active_ids = list(container.workflow_engine.active_contexts.keys())
                        for context_id in active_ids:
                            container.workflow_engine.cancel(context_id)
                        console.print("\n[yellow]Operation cancelled by user.[/yellow]")
                        break
                    except Exception as exc:  # noqa: BLE001
                        tool_result = {"error": f"Tool execution failed: {exc}"}
                else:
                    mem.setdefault("past_decisions", [])
                    mem["past_decisions"].append({
                        "date": date.today().isoformat(),
                        "action": f"Declined execution of tool '{tool_name}' with arguments {args}",
                    })
                    container.memory_repo.save(mem)
                    tool_result = {"error": "User declined to approve this action."}

                # Append tool result message
                tool_msg = {
                    "role": "tool",
                    "tool_call_id": tc_id,
                    "name": tool_name,
                    "content": json.dumps(tool_result),
                }
                conversation_history.append(tool_msg)

                user_input_to_send = ""
                continue
            else:
                # Final response generated
                console.print()
                console.print(Markdown(res["reply"]))
                break
