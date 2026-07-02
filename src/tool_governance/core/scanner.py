from typing import Any, Callable, Optional
from pydantic import BaseModel
from langchain.tools import tool

_TOOL_METADATA = {}


def governed_tool(
    name: Optional[str] = None,
    description: Optional[str] = None,
    permission_level: str = "default",
    args_schema: Optional[BaseModel] = None,
    creator: str = "system",
) -> Callable:
    def decorator(fn: Callable) -> Any:
        tool_name = name or fn.__name__
        tool_description = description or fn.__doc__ or ""

        if args_schema:
            schema_json = args_schema.model_json_schema()
        else:
            schema_json = None

        _TOOL_METADATA[tool_name] = {
            "name": tool_name,
            "description": tool_description,
            "schema_json": schema_json,
            "permission_level": permission_level,
            "creator": creator,
            "function": fn,
        }

        return tool(
            name_or_callable=tool_name,
            description=tool_description,
            args_schema=args_schema,
        )(fn)

    return decorator