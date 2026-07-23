"""Terminal UX card and presentation system for the AI Agent."""

from __future__ import annotations

from typing import Any
from rich.panel import Panel
from rich.table import Table
from rich.text import Text


def render_recommendation_card(rec: dict[str, Any]) -> Panel:
    """Render a premium job recommendation card."""
    title = rec.get("job_title", "Unknown Role")
    company = rec.get("company_name", "Unknown Company")
    score_val = rec.get("score", 0.0)
    match_pct = int(score_val * 100)
    
    # Select color by score
    if match_pct >= 85:
        score_color = "bold green"
    elif match_pct >= 60:
        score_color = "bold yellow"
    else:
        score_color = "bold red"
        
    url = rec.get("job_url", "")
    strengths = rec.get("strengths", [])
    weaknesses = rec.get("weaknesses", [])
    
    content = []
    content.append(f"[bold cyan]Company:[/bold cyan] {company}")
    content.append(f"[bold cyan]Match Score:[/bold cyan] [{score_color}]{match_pct}%[/{score_color}]")
    if url:
        content.append(f"[bold cyan]URL:[/bold cyan] [dim]{url}[/dim]")
        
    if strengths:
        content.append(f"[bold green]✓ Strengths:[/bold green] {', '.join(strengths[:5])}")
    if weaknesses:
        content.append(f"[bold yellow]⚠ Missing Skills:[/bold yellow] {', '.join(weaknesses[:5])}")
        
    explanation = rec.get("explanation")
    if isinstance(explanation, dict) and explanation.get("summary"):
        content.append(f"\n[dim]{explanation.get('summary')}[/dim]")
    elif isinstance(explanation, str) and explanation:
        content.append(f"\n[dim]{explanation}[/dim]")

    panel = Panel(
        "\n".join(content),
        title=f"[bold white]{title}[/bold white]",
        border_style="green" if match_pct >= 85 else "yellow" if match_pct >= 60 else "red",
        expand=False
    )
    return panel


def render_company_card(company: Any) -> Panel:
    """Render a structured corporate intelligence profile card."""
    # Handle dict or Company object
    is_dict = isinstance(company, dict)
    name = company.get("name") if is_dict else getattr(company, "name", "Unknown")
    domain = company.get("domain") if is_dict else getattr(company, "domain", None)
    size = company.get("company_size") if is_dict else getattr(company, "company_size", None)
    founded = company.get("founded_year") if is_dict else getattr(company, "founded_year", None)
    
    content = []
    if domain:
        content.append(f"[bold cyan]Domain:[/bold cyan] {domain}")
    if size:
        content.append(f"[bold cyan]Size:[/bold cyan] {size}")
    if founded:
        content.append(f"[bold cyan]Founded:[/bold cyan] {founded}")
        
    # Check for intelligence profile
    intel = company.get("intelligence") if is_dict else getattr(company, "intelligence", None)
    if intel:
        if isinstance(intel, dict):
            bus = intel.get("business", {})
            eng = intel.get("engineering", {})
            
            industry = bus.get("industry")
            hq = bus.get("headquarters")
            langs = eng.get("languages", [])
            frameworks = eng.get("frameworks", [])
            cloud = eng.get("cloud", [])
        else:
            industry = intel.business.industry
            hq = intel.business.headquarters
            langs = intel.engineering.languages
            frameworks = intel.engineering.frameworks
            cloud = intel.engineering.cloud
            
        if industry:
            content.append(f"[bold cyan]Industry:[/bold cyan] {industry}")
        if hq:
            content.append(f"[bold cyan]HQ:[/bold cyan] {hq}")
        if langs:
            content.append(f"[bold green]Languages:[/bold green] {', '.join(langs)}")
        if frameworks:
            content.append(f"[bold green]Frameworks:[/bold green] {', '.join(frameworks)}")
        if cloud:
            content.append(f"[bold green]Cloud:[/bold green] {', '.join(cloud)}")
            
    panel = Panel(
        "\n".join(content),
        title=f"[bold white]{name}[/bold white]",
        border_style="purple",
        expand=False
    )
    return panel


def render_application_card(app: Any) -> Panel:
    """Render a CRM application tracker card."""
    is_dict = isinstance(app, dict)
    
    # Resolve company name
    co_name = "Unknown"
    if is_dict:
        co = app.get("company")
        if isinstance(co, dict):
            co_name = co.get("name", "Unknown")
        elif co:
            co_name = getattr(co, "name", "Unknown")
    else:
        co = getattr(app, "company", None)
        if co:
            co_name = getattr(co, "name", "Unknown")

    # Resolve job title
    job_title = "Role"
    if is_dict:
        job = app.get("job")
        if isinstance(job, dict):
            job_title = job.get("job_title", "Role")
        elif job:
            job_title = getattr(job, "job_title", "Role")
    else:
        job = getattr(app, "job", None)
        if job:
            job_title = getattr(job, "job_title", "Role")

    status = app.get("status") if is_dict else getattr(app, "status", "Unknown")
    
    content = []
    content.append(f"[bold cyan]Role:[/bold cyan] {job_title}")
    content.append(f"[bold cyan]Status:[/bold cyan] [bold yellow]{status}[/bold yellow]")
    
    next_followup = app.get("next_followup") if is_dict else getattr(app, "next_followup", None)
    if next_followup:
        content.append(f"[bold cyan]Next Follow-up:[/bold cyan] {next_followup}")
        
    cover_letter = app.get("cover_letter_version") if is_dict else getattr(app, "cover_letter_version", None)
    if cover_letter:
        snippet = cover_letter[:150] + "..." if len(cover_letter) > 150 else cover_letter
        content.append(f"\n[bold green]Cover Letter Snippet:[/bold green]\n[dim]\"{snippet}\"[/dim]")
        
    panel = Panel(
        "\n".join(content),
        title=f"[bold white]CRM Application: {co_name}[/bold white]",
        border_style="magenta",
        expand=False
    )
    return panel


def render_monitoring_card(events: list[Any]) -> Panel:
    """Render list of detected hiring updates/alerts."""
    table = Table(show_header=True, header_style="bold magenta", box=None)
    table.add_column("Event Type", style="cyan")
    table.add_column("Company", style="bold white")
    table.add_column("Details", style="dim white")
    
    for ev in events:
        is_dict = isinstance(ev, dict)
        ev_type = ev.get("event_type") if is_dict else getattr(ev, "event_type", "Unknown")
        co_name = ev.get("company_name") if is_dict else getattr(ev, "company_name", "Unknown")
        metadata = ev.get("metadata", {}) if is_dict else getattr(ev, "metadata", {})
        
        details = ""
        if isinstance(metadata, dict):
            if "title" in metadata:
                details = f"Role: {metadata.get('title')}"
            elif "status" in metadata:
                details = f"Status changed to: {metadata.get('status')}"
            
        table.add_row(ev_type, co_name, details)
        
    panel = Panel(
        table,
        title="[bold white]Hiring Alerts & Change Events[/bold white]",
        border_style="yellow",
        expand=False
    )
    return panel


def print_tool_result_card(tool_name: str, tool_result: Any) -> None:
    """Detect and render structured tool results as beautiful Rich Cards."""
    if not tool_result:
        return
        
    if isinstance(tool_result, dict) and "error" in tool_result:
        return

    from app.cli.common import console

    try:
        if tool_name in ("search_jobs", "generate_recommendations"):
            # Check if list of jobs
            if isinstance(tool_result, list):
                # Print at most 3 jobs as cards to avoid terminal clutter
                for item in tool_result[:3]:
                    console.print(render_recommendation_card(item))
                if len(tool_result) > 3:
                    console.print(f"  [dim]... and {len(tool_result) - 3} more opportunities.[/dim]")
            elif isinstance(tool_result, dict):
                console.print(render_recommendation_card(tool_result))
                
        elif tool_name in ("get_company", "enrich_company_profile"):
            console.print(render_company_card(tool_result))
            
        elif tool_name in ("apply_to_company", "prepare_outreach"):
            console.print(render_application_card(tool_result))
            
        elif tool_name == "check_monitoring_alerts":
            # If list of events
            if isinstance(tool_result, list) and tool_result:
                console.print(render_monitoring_card(tool_result))
    except Exception:
        pass
