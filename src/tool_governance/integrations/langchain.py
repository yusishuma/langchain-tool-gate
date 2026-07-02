from typing import Any, Optional, List
from langchain_core.language_models import BaseLLM
from langchain_core.prompts import ChatPromptTemplate
from langchain.tools import BaseTool
from tool_governance.core.guard import apply_guardrails as _apply_guardrails

try:
    from langchain.agents import AgentExecutor
    from langchain.agents import create_openai_tools_agent
except ImportError:
    from langchain.agents.agent_executor import AgentExecutor
    from langchain.agents.openai_tools import create_openai_tools_agent


def apply_guardrails(
    executor: Any,
    db_url: str = "sqlite:///./tools.db",
) -> Any:
    return _apply_guardrails(executor, db_url)


def create_guarded_agent(
    llm: BaseLLM,
    tools: List[BaseTool],
    prompt: ChatPromptTemplate,
    db_url: str = "sqlite:///./tools.db",
    agent_kwargs: Optional[dict] = None,
    executor_kwargs: Optional[dict] = None,
) -> AgentExecutor:
    agent = create_openai_tools_agent(llm, tools, prompt, **(agent_kwargs or {}))
    executor = AgentExecutor(agent=agent, tools=tools, **(executor_kwargs or {}))
    return apply_guardrails(executor, db_url)