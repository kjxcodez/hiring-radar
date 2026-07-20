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

def agent(
    model: Annotated[
        Optional[str],
        typer.Option(
            "--model",
            help="OpenRouter model identifier override to use for the agent loop.",
        ),
    ] = None,
) -> None:
    """Start an interactive terminal reasoning agent loop (REPL)."""
    # Lazy loaded to avoid importing heavy LLM / OpenRouter files during quick commands
    from app.agent.planner import run_agent_turn

    console.print(
        "\n[bold purple]🤖 Hiring Radar Autonomous AI Agent REPL[/bold purple]\n"
        "Type your requests to discover, score, research, or recommend jobs.\n"
        "Type [bold red]exit[/bold red] or [bold red]quit[/bold red] to end the session.\n"
    )

    conversation_history: list[dict] = []

    while True:
        try:
            user_msg = Prompt.ask("\n[bold cyan]Agent[/bold cyan]")
        except (KeyboardInterrupt, EOFError):
            console.print("\n[yellow]Session ended.[/yellow]")
            break

        if user_msg.strip().lower() in ("exit", "quit"):
            console.print("[yellow]Goodbye![/yellow]")
            break

        if not user_msg.strip():
            continue

        user_input_to_send = user_msg
        while True:
            with console.status("[bold yellow]Thinking...[/bold yellow]"):
                try:
                    res = run_agent_turn(user_input_to_send, conversation_history, model=model)
                    conversation_history = res["updated_history"]
                except Exception as exc:  # noqa: BLE001
                    console.print(f"[bold red]Error in agent loop:[/bold red] {exc}")
                    break

            if "pending_approval" in res:
                pending = res["pending_approval"]
                tool_name = pending["tool"]
                args = pending["arguments"]
                tc_id = pending["tool_call_id"]
                desc = pending["description"]

                if res.get("tool_calls_made"):
                    tools_str = ", ".join(res["tool_calls_made"])
                    console.print(f"[dim]🔧 Tools invoked: {tools_str}[/dim]")

                console.print(f"\n[bold yellow]⚠️ Pending Approval:[/bold yellow] Agent wants to {desc}")
                approved = typer.confirm("Approve this action?")

                from app.agent.tools import execute_approved_tool
                container = get_container()
                mem = container.memory_repo.load()

                if approved:
                    mem["past_decisions"].append({
                        "date": date.today().isoformat(),
                        "action": f"Approved and executed tool '{tool_name}' with arguments {args}",
                    })
                    container.memory_repo.save(mem)
                    with console.status(f"[bold yellow]Executing {tool_name}...[/bold yellow]"):
                        tool_result = execute_approved_tool(tool_name, args)
                else:
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
                if res.get("tool_calls_made"):
                    tools_str = ", ".join(res["tool_calls_made"])
                    console.print(f"[dim]🔧 Tools invoked: {tools_str}[/dim]")

                console.print(Markdown(res["reply"]))
                break
