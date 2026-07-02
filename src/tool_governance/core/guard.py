from typing import Any, Optional
from tool_governance.core.registry import ToolRegistryService


def apply_guardrails(
    executor: Any,
    db_url: str = "sqlite:///./tools.db",
) -> Any:
    registry = ToolRegistryService(db_url)
    original_invoke = executor.invoke

    def wrapped_invoke(*args: tuple, **kwargs: dict) -> Any:
        active_tools = registry.get_active_tools()
        active_tool_names = {tool["name"] for tool in active_tools}

        result = original_invoke(*args, **kwargs)

        tool_calls = _extract_tool_calls(result)
        for tool_name, params, tool_result in tool_calls:
            if tool_name not in active_tool_names:
                raise RuntimeError(f"Tool '{tool_name}' is not active. Only active tools can be called.")

        return result

    executor.invoke = wrapped_invoke
    return executor


def _extract_tool_calls(result: Any) -> list:
    calls = []

    if hasattr(result, "intermediate_steps"):
        for step in result.intermediate_steps:
            if hasattr(step, "action") and hasattr(step.action, "tool"):
                tool_name = step.action.tool
                tool_args = step.action.tool_input if hasattr(step.action, "tool_input") else {}
                tool_result = step.observation if hasattr(step, "observation") else None
                calls.append((tool_name, tool_args, tool_result))

    elif isinstance(result, dict) and "intermediate_steps" in result:
        for step in result["intermediate_steps"]:
            if isinstance(step, tuple) and len(step) >= 2:
                action = step[0]
                observation = step[1] if len(step) > 1 else None

                if isinstance(action, dict):
                    tool_name = action.get("tool", "")
                    tool_args = action.get("tool_input", {})
                elif hasattr(action, "tool"):
                    tool_name = action.tool
                    tool_args = action.tool_input if hasattr(action, "tool_input") else {}
                else:
                    tool_name = str(action)
                    tool_args = {}

                calls.append((tool_name, tool_args, observation))

    return calls