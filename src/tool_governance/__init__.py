from tool_governance.core.scanner import governed_tool, _TOOL_METADATA
from tool_governance.core.models import ToolPermission


def apply_guardrails(*args, **kwargs):
    from tool_governance.integrations.langchain import apply_guardrails as _apply_guardrails
    return _apply_guardrails(*args, **kwargs)


def create_guarded_agent(*args, **kwargs):
    from tool_governance.integrations.langchain import create_guarded_agent as _create_guarded_agent
    return _create_guarded_agent(*args, **kwargs)


__all__ = ["apply_guardrails", "create_guarded_agent", "governed_tool", "_TOOL_METADATA", "ToolPermission"]