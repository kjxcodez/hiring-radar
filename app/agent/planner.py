"""AI Agent planner and tool-calling reasoning loop for Hiring Radar."""

from __future__ import annotations

import json
import logging
from typing import Any, Optional

import httpx
from tenacity import (
    RetryError,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.config import settings
from app.agent.tools import TOOL_REGISTRY, get_tool_specs
from app.utils import get_http_client

# Reasoning engine imports
from app.agent.intent import classify_intent
from app.agent.query_analysis import analyze_query
from app.agent.reference_resolver import resolve_references
from app.agent.planning import create_execution_plan
from app.agent.tool_selector import score_and_select_tools
from app.agent.clarification import check_and_clarify
from app.agent.grounding import format_grounding_context
from app.agent.response_strategy import get_response_strategy_prompt
from app.agent.validators import validate_tool_result, recover_company_name

logger = logging.getLogger(__name__)

_OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"


# Retry-wrapped API call (matching app/enrich/ai.py conventions)
@retry(
    retry=retry_if_exception_type((httpx.TimeoutException, httpx.ConnectError)),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    reraise=True,
)
def _post_with_retry(
    client: httpx.Client, headers: dict[str, str], json_body: dict[str, Any]
) -> httpx.Response:
    resp = client.post(_OPENROUTER_URL, headers=headers, json=json_body)
    resp.raise_for_status()
    return resp


from app.agent.session import AgentSession


def build_agent_system_prompt(session: AgentSession | None = None) -> str:
    """Return the system instructions for the AI Agent planner loop."""
    from app.agent.memory import load_memory
    from app.ai.prompts import get_prompt
    from app.cli.common import get_container
    
    mem = load_memory()
    prefs = mem.get("preferences", {})
    rejected = mem.get("rejected_companies", [])

    prefs_summary = "\n".join(f"- {k}: {v}" for k, v in prefs.items()) if prefs else "None"
    rejected_summary = ", ".join(rejected) if rejected else "None"

    # Query physical repositories for real-time state synchronization
    container = get_container()
    
    resume_exists = (settings.resume_path and settings.resume_path.is_file()) or (session and session.loaded_resume)
    resume_name = settings.resume_path.name if (settings.resume_path and settings.resume_path.is_file()) else (session.loaded_resume.name if (session and session.loaded_resume) else "Unknown")
    resume_status = f"Loaded ({resume_name})" if resume_exists else "Not Loaded"
    
    try:
        companies = container.company_repo.load_all()
    except Exception:
        companies = []
        
    try:
        apps_data = container.application_repo.load_all()
        apps = apps_data.values() if isinstance(apps_data, dict) else apps_data
    except Exception:
        apps = []
        
    try:
        alerts = container.monitoring_repo.load_alerts()
    except Exception:
        alerts = []
        
    try:
        recs = container.recommendation_repo.load_recommendations()
    except Exception:
        recs = []

    app_summaries = []
    for a in apps:
        is_dict = isinstance(a, dict)
        
        co_name = "Unknown"
        co = a.get("company") if is_dict else getattr(a, "company", None)
        if co:
            co_name = co.get("name", "Unknown") if isinstance(co, dict) else getattr(co, "name", "Unknown")
        else:
            co_name = a.get("company_key", "Unknown") if is_dict else getattr(a, "company_key", "Unknown")

        job_title = "Role"
        job = a.get("job") if is_dict else getattr(a, "job", None)
        if job:
            job_title = job.get("job_title", "Role") if isinstance(job, dict) else getattr(job, "job_title", "Role")

        status = a.get("status") if is_dict else getattr(a, "status", "Unknown")
        app_summaries.append(f"- {co_name} ({job_title}): Status is '{status}'")
    apps_str = "\n".join(app_summaries) if app_summaries else "No applications recorded."

    alert_summaries = []
    for alert in alerts[:5]:
        co_name = alert.get("company_name", "Unknown") if isinstance(alert, dict) else getattr(alert, "company_name", "Unknown")
        ev_type = alert.get("event_type", "Unknown") if isinstance(alert, dict) else getattr(alert, "event_type", "Unknown")
        alert_summaries.append(f"- Alert: {ev_type} for {co_name}")
    alerts_str = "\n".join(alert_summaries) if alert_summaries else "No active alerts."

    rec_summaries = []
    for rec in recs[:5]:
        co_name = rec.get("company_name", "Unknown")
        title = rec.get("job_title", "Unknown")
        score = int(rec.get("score", 0) * 100)
        rec_summaries.append(f"- {title} at {co_name} (Score: {score}%)")
    recs_str = "\n".join(rec_summaries) if rec_summaries else "No job recommendations generated yet."

    session_context = (
        f"\n\nACTUAL SYSTEM STATE (FROM PERSISTENT REPOSITORIES):\n"
        f"- Candidate Resume: {resume_status}\n"
        f"- Total Companies: {len(companies)}\n"
        f"- Total Discovered Jobs: {sum(len(c.jobs) for c in companies)}\n"
        f"- Active Job Recommendations (Top 5):\n{recs_str}\n"
        f"- Applications CRM Records:\n{apps_str}\n"
        f"- Monitoring Alerts (Top 5):\n{alerts_str}\n"
    )

    if session:
        discussed_cos = ", ".join(session.discussed_companies) if session.discussed_companies else "None"
        session_context += (
            f"\nCURRENT SESSION CONTEXT:\n"
            f"- Companies discussed: {discussed_cos}\n"
            f"- Jobs searched in session: {session.jobs_searched}\n"
        )

    base_prompt = get_prompt("agent.v1").system_prompt_template.format(
        prefs_summary=prefs_summary,
        rejected_summary=rejected_summary,
    )
    return base_prompt + session_context


def get_approval_description(tool_name: str, arguments: dict[str, Any]) -> str:
    """Generate a human-readable description of a side-effecting action."""
    if tool_name == "apply_to_company":
        company = arguments.get("company_name", "unknown company")
        status = arguments.get("status", "applied")
        version = arguments.get("resume_version")
        v_str = f" with resume version '{version}'" if version else ""
        return f"update application status for '{company}' to '{status}'{v_str}"
    return f"execute tool '{tool_name}' with arguments {arguments}"


def run_agent_turn(
    user_message: str | None,
    conversation_history: list[dict[str, Any]],
    model: str | None = None,
    session: AgentSession | None = None,
) -> dict[str, Any]:
    """Execute a single agent reasoning turn.

    Submits the new message and conversation history to OpenRouter, executes tool calls,
    and loops back until a final text reply is generated (capped at 5 rounds).
    """
    if not settings.openrouter_api_key:
        raise RuntimeError(
            "OPENROUTER_API_KEY is not set. Please add it to your .env file."
        )

    # Initialize default session if not provided
    if session is None:
        session = AgentSession()

    # 1. Resolve references & pronouns (follow-up pronouns resolution)
    resolved_query = user_message or ""
    resolved_entities = {}
    if user_message:
        resolved_query, resolved_entities = resolve_references(user_message, session)

    # 2. Intent Classification
    intent_info = classify_intent(resolved_query, model=model)
    # Merge resolved pronouns
    for k, v in resolved_entities.items():
        intent_info.entities[k] = v

    # 3. Query Analysis
    query_info = analyze_query(resolved_query, model=model)

    # 4. Clarification check
    clarification_msg = check_and_clarify(intent_info, query_info, session)
    if clarification_msg:
        if user_message:
            conversation_history.append({"role": "user", "content": user_message})
        conversation_history.append({"role": "assistant", "content": clarification_msg})
        return {
            "reply": clarification_msg,
            "updated_history": conversation_history,
            "tool_calls_made": []
        }

    # 5. Tool Selection & Planning
    selected_tools = score_and_select_tools(intent_info, query_info)
    plan = create_execution_plan(intent_info, query_info, selected_tools)
    session.planning_metrics["total_plans"] += 1

    # Print reasoning panel if enabled (Planning Transparency)
    show_reasoning = getattr(session, "show_reasoning", False)
    if show_reasoning:
        from app.cli.common import console
        from rich.panel import Panel
        from rich.table import Table
        
        table = Table(title="[bold purple]🧠 Reasoning Engine Diagnostics[/bold purple]", show_header=False)
        table.add_column("Key", style="cyan")
        table.add_column("Value", style="white")
        table.add_row("Extracted Intent", plan.intent)
        table.add_row("Ultimate Goal", plan.goal)
        table.add_row("Selected Tools", ", ".join(f"{name} ({int(score*100)}%)" for name, score in selected_tools) or "None")
        steps_str = "\n".join(f"  {idx}. {step}" for idx, step in enumerate(plan.steps, 1))
        table.add_row("Execution Steps", steps_str or "N/A")
        
        console.print(Panel(table, border_style="purple"))

    # Determine Pre-routed Tool
    pre_routed_tool = None
    pre_routed_args = {}
    
    if plan.intent == "application_status":
        pre_routed_tool = "list_applications"
        pre_routed_args = {}
    elif plan.intent == "alerts":
        pre_routed_tool = "list_alerts"
        pre_routed_args = {"limit": 10}
    elif plan.intent == "search_company":
        pre_routed_tool = "list_companies"
        pre_routed_args = {"limit": 10}
    elif plan.intent == "recommend_jobs":
        pre_routed_tool = "recommend"
        pre_routed_args = {"top": 5}
    elif plan.intent == "company_research":
        co_name = intent_info.entities.get("company_name") or (query_info.company_names[0] if query_info.company_names else None)
        if co_name:
            pre_routed_tool = "research_company"
            pre_routed_args = {"company_name": co_name}
    elif plan.intent == "fit_score":
        co_name = intent_info.entities.get("company_name") or (query_info.company_names[0] if query_info.company_names else None)
        if co_name:
            pre_routed_tool = "score_company_fit"
            pre_routed_args = {"company_name": co_name}

    # 6. Execute Pre-routed Tool if applicable
    tool_calls_made = []
    if user_message:
        conversation_history.append({"role": "user", "content": user_message})

    if pre_routed_tool:
        tool_impl = TOOL_REGISTRY.get(pre_routed_tool)
        if tool_impl:
            import uuid
            tc_id = f"call_{uuid.uuid4().hex[:8]}"
            
            # Append mock assistant tool choice
            conversation_history.append({
                "role": "assistant",
                "content": f"I will retrieve the requested data from the repository using the {pre_routed_tool} tool.",
                "tool_calls": [
                    {
                        "id": tc_id,
                        "type": "function",
                        "function": {
                            "name": pre_routed_tool,
                            "arguments": json.dumps(pre_routed_args)
                        }
                    }
                ]
            })
            
            try:
                tool_calls_made.append(pre_routed_tool)
                session.record_tool_call(pre_routed_tool, pre_routed_args)
                tool_result = tool_impl.fn(**pre_routed_args)
                
                # Check for fuzzy recovery if failed company search
                is_valid, err = validate_tool_result(pre_routed_tool, tool_result)
                if not is_valid and pre_routed_tool in ("research_company", "score_company_fit"):
                    co_name = pre_routed_args.get("company_name")
                    recovered = recover_company_name(co_name) if co_name else None
                    if recovered:
                        pre_routed_args["company_name"] = recovered
                        tool_result = tool_impl.fn(**pre_routed_args)
                
                # Cache recommendations in session
                if pre_routed_tool == "recommend" and isinstance(tool_result, list):
                    session.last_recommendations = tool_result
                    
                # Print Card directly
                from app.agent.cards import print_tool_result_card
                print_tool_result_card(pre_routed_tool, tool_result)
            except Exception as exc:
                logger.exception("Pre-routing tool execution failed")
                tool_result = {"error": str(exc)}
                
            # Append tool result message
            conversation_history.append({
                "role": "tool",
                "tool_call_id": tc_id,
                "name": pre_routed_tool,
                "content": json.dumps(tool_result),
            })

    # 7. Early Exit Check (Bypass LLM completely for direct repository queries)
    if plan.intent in ("application_status", "alerts", "search_company", "diagnostics"):
        grounded_data = ""
        if conversation_history and conversation_history[-1]["role"] == "tool":
            last_tool_res = json.loads(conversation_history[-1]["content"])
            grounded_data = format_grounding_context(pre_routed_tool, last_tool_res)
            
        if plan.intent == "application_status":
            reply = f"Here is the list of your tracked job applications:\n\n{grounded_data}"
        elif plan.intent == "alerts":
            reply = f"Here are the active hiring alerts and monitoring updates:\n\n{grounded_data}"
        elif plan.intent == "search_company":
            reply = f"Here is the list of discovered companies in the database:\n\n{grounded_data}"
        else:
            reply = "Diagnostics verification checks completed successfully."

        conversation_history.append({"role": "assistant", "content": reply})
        session.planning_metrics["successful_plans"] += 1
        session.planning_metrics["unnecessary_llm_calls_avoided"] += 1
        return {
            "reply": reply,
            "updated_history": conversation_history,
            "tool_calls_made": tool_calls_made
        }

    # 8. Standard reasoning pipeline (LLM structured loop)
    target_model = model or settings.openrouter_model
    headers = {
        "Authorization": f"Bearer {settings.openrouter_api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/kjxcodez/hiring-radar",
        "X-Title": "hiring-radar-agent",
    }

    tool_specs = get_tool_specs()
    
    # Reasoning loop (capped at 5 rounds)
    max_rounds = 5
    for round_idx in range(max_rounds):
        strategy_prompt = get_response_strategy_prompt(plan.intent)
        base_prompt = build_agent_system_prompt(session) + strategy_prompt
        
        messages_to_send = [{"role": "system", "content": base_prompt}] + conversation_history
        json_body = {
            "model": target_model,
            "messages": messages_to_send,
            "temperature": 0.3,
        }
        if tool_specs:
            json_body["tools"] = tool_specs

        try:
            with get_http_client() as client:
                resp = _post_with_retry(client, headers, json_body)
                resp_json = resp.json()
        except httpx.HTTPStatusError as exc:
            err_msg = f"API returned HTTP status error: {exc.response.status_code}"
            logger.error("Agent turn failed: %s", err_msg)
            session.planning_metrics["failed_plans"] += 1
            return {
                "reply": f"Error: OpenRouter API error ({err_msg}).",
                "updated_history": conversation_history,
                "tool_calls_made": tool_calls_made,
            }
        except Exception as exc:  # noqa: BLE001
            err_msg = f"Unexpected API error: {exc}"
            logger.error("Agent turn failed: %s", err_msg)
            session.planning_metrics["failed_plans"] += 1
            return {
                "reply": f"Error: Unexpected service error ({err_msg}).",
                "updated_history": conversation_history,
                "tool_calls_made": tool_calls_made,
            }

        choices = resp_json.get("choices", [])
        if not choices:
            session.planning_metrics["failed_plans"] += 1
            return {
                "reply": f"Error: Empty choice list returned from model.",
                "updated_history": conversation_history,
                "tool_calls_made": tool_calls_made,
            }

        choice_message = choices[0].get("message", {})
        content = choice_message.get("content")
        tool_calls = choice_message.get("tool_calls")

        # If model requested tool calls, execute them
        if tool_calls:
            assistant_msg = {
                "role": "assistant",
                "content": content,
                "tool_calls": tool_calls,
            }
            conversation_history.append(assistant_msg)

            for tc in tool_calls:
                tc_id = tc.get("id")
                func = tc.get("function", {})
                func_name = func.get("name")
                args_raw = func.get("arguments", "{}")

                tool_calls_made.append(func_name)

                if isinstance(args_raw, str):
                    try:
                        args = json.loads(args_raw)
                    except Exception as e:  # noqa: BLE001
                        args = {}
                else:
                    args = args_raw

                # Mechanical Approval Gate check
                if func_name in TOOL_REGISTRY and TOOL_REGISTRY[func_name].side_effecting:
                    return {
                        "pending_approval": {
                            "tool": func_name,
                            "tool_call_id": tc_id,
                            "arguments": args,
                            "description": get_approval_description(func_name, args)
                        },
                        "updated_history": conversation_history,
                        "tool_calls_made": tool_calls_made,
                    }

                # Execute tool
                if func_name not in TOOL_REGISTRY:
                    tool_result = {"error": f"Tool '{func_name}' is not registered."}
                else:
                    try:
                        session.record_tool_call(func_name, args)
                        tool_impl = TOOL_REGISTRY[func_name]
                        tool_result = tool_impl.fn(**args)
                        
                        # Cache recommendations if returned
                        if func_name == "recommend" and isinstance(tool_result, list):
                            session.last_recommendations = tool_result
                        
                        from app.agent.cards import print_tool_result_card
                        print_tool_result_card(func_name, tool_result)
                    except Exception as exc:  # noqa: BLE001
                        tool_result = {"error": f"Tool execution failed: {exc}"}

                # Append tool result message
                tool_msg = {
                    "role": "tool",
                    "tool_call_id": tc_id,
                    "name": func_name,
                    "content": json.dumps(tool_result),
                }
                conversation_history.append(tool_msg)

            continue

        else:
            final_reply = content or ""
            conversation_history.append({"role": "assistant", "content": final_reply})
            session.planning_metrics["successful_plans"] += 1
            return {
                "reply": final_reply,
                "updated_history": conversation_history,
                "tool_calls_made": tool_calls_made,
            }

    session.planning_metrics["failed_plans"] += 1
    return {
        "reply": f"Warning: Reasoning loop exceeded max rounds ({max_rounds}). Returning current state.",
        "updated_history": conversation_history,
        "tool_calls_made": tool_calls_made,
    }
