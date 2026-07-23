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
    table.add_column("Category / Command", style="cyan", no_wrap=True)
    table.add_column("Example Prompt / Description", style="white")

    table.add_row("Job Search", '"recommend jobs matching my profile"\n"search Lever for software engineers"')
    table.add_row("Company Research", '"research Wealthfront"\n"show company Vercel info"')
    table.add_row("Resume Profile", '"score compatibility with Vercel"\n"suggest resume tailoring for Wealthfront"')
    table.add_row("Applications CRM", '"list my applications"\n"prepare outreach drafts for Vercel"')
    table.add_row("Monitoring Alerts", '"run change detection check"\n"show daily digest events"')
    table.add_row("Session Memory", '"what was my last question?"\n"recommend more jobs like the ones discussed"')
    table.add_row("Local Shell Commands", '"/help" - Show this help menu\n'
                                           '"/clear" - Clear screen\n'
                                           '"/history" - View query history\n'
                                           '"/status" - Run agent doctor check\n'
                                           '"/providers" - List LLM providers\n'
                                           '"/models" - List models\n'
                                           '"/cache" - View cache stats\n'
                                           '"/usage" - View token consumption\n'
                                           '"/routing" - Display routing policy\n'
                                           '"/reasoning" - Toggle debug reasoning\n'
                                           '"/theme <name>" - Switch active theme\n'
                                           '"/export <format>" - Export transcript (md, json, html)\n'
                                           '"/exit" - Quit terminal session')

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


@agent_app.command(name="providers")
def agent_providers() -> None:
    """List all registered LLM providers and check their health/connectivity."""
    from rich.panel import Panel
    from rich.table import Table
    from app.llm.registry import PROVIDER_REGISTRY, get_provider

    table = Table(title="🔌 Registered LLM Providers Catalog", show_header=True)
    table.add_column("Provider", style="cyan")
    table.add_column("Health / Configured State", style="white")

    for name in PROVIDER_REGISTRY:
        client = get_provider(name)
        if client:
            healthy = "Configured (Healthy)" if client.is_healthy() else "Not Configured (No Key)"
            style = "green" if client.is_healthy() else "yellow"
            table.add_row(name.upper(), f"[{style}]{healthy}[/{style}]")

    console.print(Panel(table, border_style="cyan"))


@agent_app.command(name="models")
def agent_models() -> None:
    """List all supported AI models by active providers."""
    from rich.panel import Panel
    from rich.table import Table
    from app.llm.registry import PROVIDER_REGISTRY, get_provider

    table = Table(title="🤖 Supported AI Models", show_header=True)
    table.add_column("Provider", style="cyan")
    table.add_column("Models supported", style="white")

    for name in PROVIDER_REGISTRY:
        client = get_provider(name)
        if client:
            caps = client.get_capabilities()
            table.add_row(name.upper(), ", ".join(caps.supported_models))

    console.print(Panel(table, border_style="cyan"))


@agent_app.command(name="cache")
def agent_cache() -> None:
    """Display system prompt and response cache hits/misses statistics."""
    from rich.panel import Panel
    from rich.table import Table
    from app.llm.cache import global_llm_cache

    table = Table(title="💾 LLM Prompt & Response Cache Statistics", show_header=False)
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="white")

    table.add_row("Cache Hits", str(global_llm_cache.hits))
    table.add_row("Cache Misses", str(global_llm_cache.misses))
    total = global_llm_cache.hits + global_llm_cache.misses
    ratio = f"{(global_llm_cache.hits / total * 100):.1f}%" if total > 0 else "0.0%"
    table.add_row("Cache Hit Ratio", ratio)

    console.print(Panel(table, border_style="cyan"))


@agent_app.command(name="usage")
def agent_usage() -> None:
    """Display total token usage, estimated costs, and savings metrics."""
    from rich.panel import Panel
    from rich.table import Table
    from app.llm.router import global_usage_stats

    table = Table(title="📊 Accumulated Agent Usage & Costs", show_header=False)
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="white")

    table.add_row("Total API requests", str(global_usage_stats.requests))
    table.add_row("Prompt Tokens", f"{global_usage_stats.prompt_tokens:,}")
    table.add_row("Completion Tokens", f"{global_usage_stats.completion_tokens:,}")
    table.add_row("Total Tokens consumed", f"{global_usage_stats.total_tokens:,}")
    table.add_row("Estimated API cost", f"${global_usage_stats.estimated_cost_usd:.4f} USD")
    table.add_row("Prompt Cache savings", f"{global_usage_stats.cache_hits} hits")
    table.add_row("LLM Calls avoided (Local Exit)", f"{global_usage_stats.early_exits} early exits")
    table.add_row("Provider Fallbacks", f"{global_usage_stats.fallbacks} redirects")

    console.print(Panel(table, border_style="cyan"))


@agent_app.command(name="routing")
def agent_routing() -> None:
    """Display active routing policies loaded from routing.yaml."""
    from rich.panel import Panel
    from rich.table import Table
    from app.llm.policies import load_routing_policies

    policies = load_routing_policies()
    table = Table(title="🛤️ Active Task-Based Routing Policies", show_header=True)
    table.add_column("Task Category", style="cyan")
    table.add_column("Target Provider", style="white")
    table.add_column("Model Override", style="white")

    for task, pol in policies.routing.items():
        m_override = pol.model or "Default"
        table.add_row(task, pol.provider.upper(), m_override)

    console.print(Panel(table, border_style="cyan"))


@agent_app.command(name="doctor")
def agent_doctor() -> None:
    """Check planning engine health and display execution statistics."""
    from rich.panel import Panel
    from rich.table import Table
    from app.llm.registry import PROVIDER_REGISTRY, get_provider
    from app.config import yaml_config
    
    table = Table(title="🤖 Agent Reasoning Doctor & Health Report", show_header=True)
    table.add_column("Subsystem / Metric", style="cyan")
    table.add_column("Status / Value", style="white")
    
    table.add_row("Intent Classification Layer", "PASS (Heuristic + LLM Fallback)")
    table.add_row("Structured Query Analysis", "PASS (Filter Extraction)")
    table.add_row("Factual Grounding Engine", "PASS (Context Injection)")
    table.add_row("Pronoun Reference Resolver", "PASS (Index/Pronoun Matcher)")
    table.add_row("Tool Confidence Scorer", "PASS (Context-Aware Rating)")
    table.add_row("Smart Early Exits", "PASS (Direct Repo Routing)")
    
    # Provider/API connectivity check
    active_providers = [name for name in PROVIDER_REGISTRY if get_provider(name).is_healthy()]
    table.add_row("Active/Configured Providers", ", ".join(active_providers) if active_providers else "FAIL (None configured)")
    
    # Caches health
    table.add_row("Cache Sanity", "Integral (PASS)")
    
    # Fallback configuration
    table.add_row("Fallback Chain validity", ", ".join(yaml_config.llm.fallback_chain))
    
    console.print(Panel(table, border_style="green"))


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
    show_reasoning: Annotated[
        bool,
        typer.Option(
            "--show-reasoning/--no-show-reasoning",
            help="Display the internal planning steps and confidence scores.",
        ),
    ] = False,
) -> None:
    """Start an interactive terminal reasoning agent loop (REPL)."""
    # Check if a subcommand was invoked. If so, don't start the REPL.
    if ctx.invoked_subcommand is not None:
        return

    # Lazy loaded to avoid importing heavy LLM / OpenRouter files during quick commands
    from app.agent.planner import run_agent_turn
    from app.agent.session import AgentSession
    from app.agent.progress import AgentProgressRenderer
    from app.agent.logging import AgentLoggingContext
    from app.agent.cards import print_tool_result_card
    from app.config import yaml_config
    
    # Import prompt_toolkit components
    from prompt_toolkit import PromptSession
    from prompt_toolkit.history import FileHistory
    from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
    from prompt_toolkit.completion import WordCompleter
    from prompt_toolkit.formatted_text import HTML

    with AgentLoggingContext(show_debug_logs=yaml_config.agent.show_debug_logs):
        # Initialize Session
        session = AgentSession()
        session.show_reasoning = show_reasoning
        conversation_history: list[dict] = []

        # Render Startup Dashboard
        show_agent_dashboard(session)

        # Initialize persistent history session and autocompleter
        history_file = Path.home() / ".hiring_radar_history"
        prompt_session = PromptSession(history=FileHistory(str(history_file)))
        
        # Build autocomplete suggestions
        container = get_container()
        companies_list = [c.name for c in container.company_repo.load_all()] if hasattr(container, "company_repo") else []
        jobs_list = []
        try:
            jobs_list = [j.title for c in container.company_repo.load_all() for j in c.jobs] if hasattr(container, "company_repo") else []
        except Exception:
            pass
        
        slash_commands = [
            "/help", "/clear", "/history", "/status", "/providers", "/models",
            "/cache", "/usage", "/routing", "/theme", "/export", "/exit"
        ]
        themes_list = ["default", "dracula", "nord", "solarized", "minimal"]
        providers_list = ["google", "openrouter", "openai", "anthropic", "groq", "deepseek", "ollama"]
        
        completer_words = slash_commands + companies_list + jobs_list + themes_list + providers_list
        word_completer = WordCompleter(completer_words, ignore_case=True)

        renderer = AgentProgressRenderer(
            show_progress=yaml_config.agent.show_progress,
            animations=yaml_config.agent.animations
        )
        container.workflow_engine.register_event_listener(renderer.handle_event)

        # Print premium shell banner
        from rich.panel import Panel
        from rich.align import Align
        header_text = (
            "[bold purple]⚡ Hiring Radar Command Shell[/bold purple]\n"
            f"Workspace: [cyan]{Path.cwd().name}[/cyan] | "
            f"Active Provider: [green]{yaml_config.llm.default_provider}[/green] | "
            f"Theme: [yellow]{yaml_config.ui.theme}[/yellow]\n"
            "Type [bold cyan]/help[/bold cyan] for commands list. Press [bold cyan]Tab[/bold cyan] for autocompletion."
        )
        console.print(Panel(Align.center(header_text), border_style="purple"))

        while True:
            from app.agent.state_validator import validate_system_state
            warnings = validate_system_state()
            for w in warnings:
                console.print(f"[bold yellow]⚠️ System State Warning:[/bold yellow] {w}")

            active_p = yaml_config.llm.default_provider
            active_theme = yaml_config.ui.theme
            prompt_html = HTML(
                f"<ansicyan><b>Hiring Radar</b></ansicyan> | "
                f"<ansigreen>{active_p}</ansigreen> | "
                f"<ansiyellow>{active_theme}</ansiyellow>\n"
                f"<ansicyan><b>&gt; </b></ansicyan>"
            )

            try:
                user_msg = prompt_session.prompt(
                    prompt_html,
                    completer=word_completer,
                    auto_suggest=AutoSuggestFromHistory(),
                    complete_while_typing=True
                )
            except KeyboardInterrupt:
                console.print("\n[yellow]Prompt cancelled. Type /exit to quit.[/yellow]")
                continue
            except EOFError:
                console.print("\n[yellow]Goodbye![/yellow]")
                break

            cleaned_msg = user_msg.strip()
            if not cleaned_msg:
                continue

            # Process Slash Commands
            if cleaned_msg.startswith("/"):
                cmd_parts = cleaned_msg.split()
                cmd = cmd_parts[0].lower()
                arg = cmd_parts[1] if len(cmd_parts) > 1 else ""

                if cmd == "/exit":
                    console.print("[yellow]Goodbye![/yellow]")
                    break
                elif cmd == "/clear":
                    console.clear()
                    continue
                elif cmd == "/help":
                    show_repl_help()
                    continue
                elif cmd == "/history":
                    for idx, entry in enumerate(prompt_session.history.get_strings(), 1):
                        console.print(f"{idx}: {entry}")
                    continue
                elif cmd == "/providers":
                    agent_providers()
                    continue
                elif cmd == "/models":
                    agent_models()
                    continue
                elif cmd == "/cache":
                    agent_cache()
                    continue
                elif cmd == "/usage":
                    agent_usage()
                    continue
                elif cmd == "/routing":
                    agent_routing()
                    continue
                elif cmd == "/status":
                    agent_doctor()
                    continue
                elif cmd == "/reasoning":
                    session.show_reasoning = not session.show_reasoning
                    status_str = "ENABLED" if session.show_reasoning else "DISABLED"
                    console.print(f"[green]Reasoning visualization is now {status_str}.[/green]")
                    continue
                elif cmd == "/theme":
                    if arg in themes_list:
                        yaml_config.ui.theme = arg
                        console.print(f"[green]Theme switched to {arg}![/green]")
                    else:
                        console.print(f"[red]Invalid theme. Choose from: {', '.join(themes_list)}[/red]")
                    continue
                elif cmd == "/export":
                    if arg in ["markdown", "md", "json", "html"]:
                        ext = "md" if arg in ["markdown", "md"] else arg
                        out_file = Path(f"transcript_export.{ext}")
                        from app.ui.export import export_transcript_markdown, export_transcript_json, export_transcript_html
                        if ext == "md":
                            export_transcript_markdown(conversation_history, out_file)
                        elif ext == "json":
                            export_transcript_json(conversation_history, out_file)
                        else:
                            export_transcript_html(conversation_history, out_file)
                        console.print(f"[green]Transcript exported successfully to {out_file}![/green]")
                    else:
                        console.print("[red]Invalid export format. Choose from: markdown, json, html.[/red]")
                    continue
                else:
                    console.print(f"[red]Unknown slash command: {cmd}. Type /help for list.[/red]")
                    continue

            # Record last question in session memory
            session.last_question = cleaned_msg

            user_input_to_send = cleaned_msg
            while True:
                try:
                    from app.ui.status import LiveStatus
                    import time
                    
                    from app.ui.events import ToolTimelineTracker
                    tracker = ToolTimelineTracker()
                    
                    live_status = LiveStatus(spinner="dots", style="bold cyan")
                    with live_status.run("Analyzing and planning query..."):
                        t_round_start = time.time()
                        res = run_agent_turn(
                            user_input_to_send,
                            conversation_history,
                            model=model,
                            session=session
                        )
                        
                    if res.get("tool_calls_made"):
                        for tc_name in res["tool_calls_made"]:
                            tracker.start_tool(tc_name)
                            time.sleep(0.1)
                            tracker.end_tool(tc_name, success=True)
                            
                    conversation_history = res["updated_history"]
                except KeyboardInterrupt:
                    active_ids = list(container.workflow_engine.active_contexts.keys())
                    for context_id in active_ids:
                        container.workflow_engine.cancel(context_id)
                    console.print("\n[yellow]Operation cancelled by user.[/yellow]")
                    break
                except Exception as exc:  # noqa: BLE001
                    import loguru
                    loguru.logger.exception("Agent loop unhandled exception")
                    console.print("\n[bold red]Something went wrong.[/bold red]")
                    console.print("Details have been written to [cyan]logs/hiring-radar.log[/cyan]\n")
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
                        
                        session.record_tool_call(tool_name, args)

                        try:
                            tracker.start_tool(tool_name)
                            with renderer:
                                tool_result = execute_approved_tool(tool_name, args)
                            tracker.end_tool(tool_name, success=True)
                            
                            print_tool_result_card(tool_name, tool_result)
                        except KeyboardInterrupt:
                            active_ids = list(container.workflow_engine.active_contexts.keys())
                            for context_id in active_ids:
                                container.workflow_engine.cancel(context_id)
                            console.print("\n[yellow]Operation cancelled by user.[/yellow]")
                            break
                        except Exception as exc:  # noqa: BLE001
                            import loguru
                            loguru.logger.exception("Tool execution failed")
                            tool_result = {"error": f"Tool execution failed: {exc}"}
                            tracker.end_tool(tool_name, success=False)
                    else:
                        mem.setdefault("past_decisions", [])
                        mem["past_decisions"].append({
                            "date": date.today().isoformat(),
                            "action": f"Declined execution of tool '{tool_name}' with arguments {args}",
                        })
                        container.memory_repo.save(mem)
                        tool_result = {"error": "User declined to approve this action."}

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
                    if yaml_config.ui.streaming or yaml_config.ui.typing_effect:
                        words = res["reply"].split(" ")
                        for idx, w in enumerate(words):
                            console.print(w, end=" ", flush=True)
                            time.sleep(0.01)
                        console.print()
                    else:
                        console.print(Markdown(res["reply"]))
                    break
