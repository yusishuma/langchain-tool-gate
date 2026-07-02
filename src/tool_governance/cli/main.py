import click
import os
import time
from tabulate import tabulate
from tool_governance.core.registry import ToolRegistryService
from tool_governance.core.approval import create_approval_client
from tool_governance.core.metrics import (
    TOOL_STATUS_COUNT,
    TOOL_ACTIVE_COUNT,
)


@click.group()
@click.option("--db-url", default="sqlite:///./tools.db", help="Database URL")
@click.pass_context
def cli(ctx, db_url):
    ctx.ensure_object(dict)
    ctx.obj["registry"] = ToolRegistryService(db_url=db_url)


@cli.command("list")
@click.option("--status", default="all", help="Filter by status: pending, active, rejected, deprecated, or all")
@click.pass_context
def list_tools(ctx, status):
    registry = ctx.obj["registry"]
    tools = registry.get_tools_by_status(status)

    if not tools:
        click.echo(f"No tools found with status '{status}'")
        return

    table_data = [
        [
            t["id"],
            t["name"],
            t["description"],
            t["permission_level"],
            t["status"],
            t["approval_count"],
            t["approval_required"],
            t["quiet_period_until"],
            t["created_by"],
            t["approved_at"],
            t["call_count"],
        ]
        for t in tools
    ]

    headers = ["ID", "Name", "Description", "Permission", "Status", "Approvals", "Required", "Quiet Until", "Creator", "Approved At", "Call Count"]
    click.echo(tabulate(table_data, headers=headers, tablefmt="grid"))


@cli.command("approve")
@click.argument("tool_name")
@click.option("--approver", default="admin", help="Approver name")
@click.pass_context
def approve_tool(ctx, tool_name, approver):
    registry = ctx.obj["registry"]
    result = registry.approve_tool(tool_name, approver)

    if result["success"]:
        click.echo(result["message"])
    else:
        click.echo(f"Error: {result['message']}")


@cli.command("reject")
@click.argument("tool_name")
@click.pass_context
def reject_tool(ctx, tool_name):
    registry = ctx.obj["registry"]
    success = registry.reject_tool(tool_name)

    if success:
        click.echo(f"Tool '{tool_name}' rejected")
    else:
        click.echo(f"Tool '{tool_name}' not found")


@cli.command("submit-approval")
@click.argument("tool_name")
@click.option("--platform", required=True, type=click.Choice(["dingtalk", "feishu"]), help="Approval platform")
@click.option("--app-key", help="DingTalk app_key or Feishu app_id")
@click.option("--app-secret", help="DingTalk app_secret or Feishu app_secret")
@click.option("--process-code", help="DingTalk process_code or Feishu approval_code")
@click.option("--agent-id", help="DingTalk agent_id (optional)")
@click.pass_context
def submit_approval(ctx, tool_name, platform, app_key, app_secret, process_code, agent_id):
    registry = ctx.obj["registry"]

    app_key = app_key or os.getenv(f"{platform.upper()}_APP_KEY") or os.getenv(f"{platform.upper()}_APP_ID")
    app_secret = app_secret or os.getenv(f"{platform.upper()}_APP_SECRET")
    process_code = process_code or os.getenv(f"{platform.upper()}_PROCESS_CODE") or os.getenv(f"{platform.upper()}_APPROVAL_CODE")

    if not app_key or not app_secret or not process_code:
        click.echo("Error: Missing approval credentials. Please provide via options or environment variables.")
        return

    try:
        if platform == "dingtalk":
            client = create_approval_client(
                platform="dingtalk",
                app_key=app_key,
                app_secret=app_secret,
                process_code=process_code,
                agent_id=agent_id,
            )
        else:
            client = create_approval_client(
                platform="feishu",
                app_id=app_key,
                app_secret=app_secret,
                approval_code=process_code,
            )

        result = registry.submit_approval(tool_name, client)

        if result["success"]:
            click.echo(f"Approval submitted successfully for '{tool_name}'")
            click.echo(f"Approval ID: {result['approval_id']}")
        else:
            click.echo(f"Failed to submit approval: {result['message']}")
    except Exception as e:
        click.echo(f"Error: {str(e)}")


@cli.command("sync-approval")
@click.option("--platform", required=True, type=click.Choice(["dingtalk", "feishu"]), help="Approval platform")
@click.option("--app-key", help="DingTalk app_key or Feishu app_id")
@click.option("--app-secret", help="DingTalk app_secret or Feishu app_secret")
@click.option("--process-code", help="DingTalk process_code or Feishu approval_code")
@click.option("--agent-id", help="DingTalk agent_id (optional)")
@click.option("--tool-name", help="Sync specific tool (optional)")
@click.pass_context
def sync_approval(ctx, platform, app_key, app_secret, process_code, agent_id, tool_name):
    registry = ctx.obj["registry"]

    app_key = app_key or os.getenv(f"{platform.upper()}_APP_KEY") or os.getenv(f"{platform.upper()}_APP_ID")
    app_secret = app_secret or os.getenv(f"{platform.upper()}_APP_SECRET")
    process_code = process_code or os.getenv(f"{platform.upper()}_PROCESS_CODE") or os.getenv(f"{platform.upper()}_APPROVAL_CODE")

    if not app_key or not app_secret or not process_code:
        click.echo("Error: Missing approval credentials. Please provide via options or environment variables.")
        return

    try:
        if platform == "dingtalk":
            client = create_approval_client(
                platform="dingtalk",
                app_key=app_key,
                app_secret=app_secret,
                process_code=process_code,
                agent_id=agent_id,
            )
        else:
            client = create_approval_client(
                platform="feishu",
                app_id=app_key,
                app_secret=app_secret,
                approval_code=process_code,
            )

        results = registry.sync_approval_status(client, tool_name)

        for result in results:
            tool_name = result["tool_name"]
            status = result["status"]

            if status == "approved":
                click.echo(f"✓ Tool '{tool_name}' approved")
            elif status == "rejected":
                click.echo(f"✗ Tool '{tool_name}' rejected")
            elif status == "still_pending":
                click.echo(f"○ Tool '{tool_name}' still pending")
            else:
                click.echo(f"! Tool '{tool_name}' error: {result.get('error', 'Unknown')}")

    except Exception as e:
        click.echo(f"Error: {str(e)}")


@cli.command("metrics")
@click.option("--port", default=None, help="Metrics server port (default: 8000, or TOOL_GOVERNANCE_METRICS_PORT env)")
@click.option("--host", default=None, help="Metrics server host (default: 0.0.0.0, or TOOL_GOVERNANCE_METRICS_HOST env)")
@click.pass_context
def metrics_server(ctx, port, host):
    try:
        from prometheus_client import start_http_server, REGISTRY
    except ImportError:
        click.echo("Error: prometheus-client not installed. Run 'pip install prometheus-client'")
        return

    port = port or int(os.getenv("TOOL_GOVERNANCE_METRICS_PORT", "8000"))
    host = host or os.getenv("TOOL_GOVERNANCE_METRICS_HOST", "0.0.0.0")

    registry = ctx.obj["registry"]
    registry._update_status_metrics()

    start_http_server(port, addr=host)
    click.echo(f"Metrics server started at http://{host}:{port}/metrics")

    try:
        while True:
            time.sleep(10)
            registry._update_status_metrics()
    except KeyboardInterrupt:
        click.echo("\nMetrics server stopped")


if __name__ == "__main__":
    cli()