"""AI Agent planner and tool-calling reasoning loop for Hiring Radar."""

from __future__ import annotations

import json
import logging
from typing import Any

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


logger = logging.getLogger(__name__)

_OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"


# Retry-wrapped API call (matching app/enrich/ai.py conventions)
@retry(
    retry=retry_if_exception_type((httpx.TimeoutException, httpx.ConnectError)),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    stop=stop_after_attempt(3),  # 1 initial + 2 retries
    reraise=True,
)
def _post_with_retry(client: httpx.Client, headers: dict, json_body: dict) -> httpx.Response:
    """POST to OpenRouter completions API, retrying only on transient errors."""
    resp = client.post(_OPENROUTER_URL, headers=headers, json=json_body, timeout=60.0)
    resp.raise_for_status()
    return resp


def build_agent_system_prompt() -> str:
    """Return the system instructions for the AI Agent planner loop."""
    from app.agent.memory import load_memory
    mem = load_memory()
    prefs = mem.get("preferences", {})
    rejected = mem.get("rejected_companies", [])

    prefs_summary = "\n".join(f"- {k}: {v}" for k, v in prefs.items()) if prefs else "None"
    rejected_summary = ", ".join(rejected) if rejected else "None"

    return (
        "You are an expert AI agent assistant for job application research and outreach. "
        "Your task is to help the user manage their job search workflow using the tools provided. "
        "You must always prioritize using the official tools to retrieve actual data rather than inventing details. "
        "CRITICAL REQUIREMENT: You must NEVER perform side-effecting actions (such as sending an email, "
        "marking an application as contacted, or changing application status) unless the user has explicitly "
        "reviewed and confirmed the action in the chat history first. If the user asks for a side-effecting action, "
        "you must first explain what you intend to do, present the parameters/content to the user for review, "
        "and ask for explicit confirmation before calling the tool.\n\n"
        "--- PERSISTENT USER PREFERENCES & CONTEXT ---\n"
        f"Preferences:\n{prefs_summary}\n\n"
        f"Rejected/Excluded Companies: {rejected_summary}\n"
        "--------------------------------------------"
    )


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
) -> dict[str, Any]:
    """Execute a single agent reasoning turn.

    Submits the new message and conversation history to OpenRouter, executes tool calls,
    and loops back until a final text reply is generated (capped at 5 rounds).
    """
    if not settings.openrouter_api_key:
        raise RuntimeError(
            "OPENROUTER_API_KEY is not set. Please add it to your .env file."
        )

    # 1. Append user's new message to history (if provided)
    if user_message:
        conversation_history.append({"role": "user", "content": user_message})

    # 2. Resolve target model and headers
    target_model = model or settings.openrouter_model
    headers = {
        "Authorization": f"Bearer {settings.openrouter_api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/<placeholder>/hiring-radar",
        "X-Title": "hiring-radar-agent",
    }

    tool_specs = get_tool_specs()
    tool_calls_made = []

    # 3. Reasoning Loop (capped at 5 rounds)
    max_rounds = 5
    for round_idx in range(max_rounds):
        # Prepare body with system prompt prepended
        messages_to_send = [{"role": "system", "content": build_agent_system_prompt()}] + conversation_history
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
            return {
                "reply": f"Error: OpenRouter API error ({err_msg}).",
                "updated_history": conversation_history,
                "tool_calls_made": tool_calls_made,
            }
        except (httpx.TimeoutException, httpx.ConnectError, RetryError) as exc:
            err_msg = f"Network connection failed: {exc}"
            logger.error("Agent turn failed: %s", err_msg)
            return {
                "reply": f"Error: Network connection error ({err_msg}).",
                "updated_history": conversation_history,
                "tool_calls_made": tool_calls_made,
            }
        except Exception as exc:  # noqa: BLE001
            err_msg = f"Unexpected API error: {exc}"
            logger.error("Agent turn failed: %s", err_msg)
            return {
                "reply": f"Error: Unexpected service error ({err_msg}).",
                "updated_history": conversation_history,
                "tool_calls_made": tool_calls_made,
            }

        choices = resp_json.get("choices", [])
        if not choices:
            err_msg = "OpenRouter response did not return any choices."
            logger.warning(err_msg)
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
            # We must append the assistant's message requesting tool calls to history
            assistant_msg = {
                "role": "assistant",
                "content": content,
                "tool_calls": tool_calls,
            }
            conversation_history.append(assistant_msg)

            for tc in tool_calls:
                tc_id = tc.get("id")
                tc_type = tc.get("type")
                func = tc.get("function", {})
                func_name = func.get("name")
                args_raw = func.get("arguments", "{}")

                tool_calls_made.append(func_name)

                # Parse arguments safely
                if isinstance(args_raw, str):
                    try:
                        args = json.loads(args_raw)
                    except Exception as e:  # noqa: BLE001
                        args = {}
                        tool_result = {"error": f"Invalid arguments format (not valid JSON): {e}"}
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
                        tool_impl = TOOL_REGISTRY[func_name]
                        tool_result = tool_impl.fn(**args)
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

            # Loop back to let model process tool results
            continue

        else:
            # Final text response received
            final_reply = content or ""
            conversation_history.append({"role": "assistant", "content": final_reply})
            return {
                "reply": final_reply,
                "updated_history": conversation_history,
                "tool_calls_made": tool_calls_made,
            }

    # If cap is hit
    warn_msg = f"Reasoning loop exceeded max rounds ({max_rounds}). Returning current state."
    logger.warning(warn_msg)
    return {
        "reply": f"Warning: Reasoning loop capped at {max_rounds} rounds. Please refine your query.",
        "updated_history": conversation_history,
        "tool_calls_made": tool_calls_made,
    }
