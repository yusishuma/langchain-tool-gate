# LangChain Tool Gate

A lightweight tool gate framework for LangChain applications - manage tool lifecycles with dynamic approval workflows and runtime guardrails.

---

## Overview

LangChain Tool Governance provides a complete solution for managing AI agent tools in LangChain applications. It enables organizations to implement tool approval workflows and enforce runtime permission controls without requiring application restarts.

**Core Principles:**
- **Risk-Based Governance**: Permission levels determine approval requirements (auto-activate, single-approval, dual-approval + quiet period)
- **Dynamic Runtime**: Active tools are fetched with TTL caching - changes take effect immediately without restarting the Agent
- **Status-Only Interception**: Tool calls are blocked based solely on `status` (active/inactive), not permission levels

## Features

- **Tool Registration**: Automatically scan and register tools with comprehensive metadata
- **Approval Workflow**: Manage tool lifecycle (pending → active → rejected → deprecated)
- **Risk-Based Approval**: Permission levels determine initial status and approval requirements
- **Dynamic Runtime**: TTL-cached tool list for real-time updates without Agent restarts
- **Runtime Guardrails**: Block inactive tool calls at execution time
- **CLI Management**: Command-line interface for tool governance operations
- **External Approval Integration**: Support for DingTalk and Feishu approval workflows

## Installation

```bash
pip install langchain-tool-gate
```

## Quick Start

### Step 1: Define Governed Tools

```python
from pydantic import BaseModel, Field
from tool_governance import governed_tool

class CancelOrderInput(BaseModel):
    order_id: str = Field(description="Order ID")

@governed_tool(
    name="cancel_order",
    description="Cancel user's order",
    permission_level="confidential",
    args_schema=CancelOrderInput,
    creator="dev@company.com",
)
def cancel_order(order_id: str) -> str:
    return f"Order {order_id} cancelled"

@governed_tool(
    name="get_weather",
    description="Get weather information",
    permission_level="public",
    creator="dev@company.com",
)
def get_weather(city: str) -> str:
    return f"Weather for {city}"
```

### Step 2: Register Tools

```python
from tool_governance.core.registry import ToolRegistryService

registry = ToolRegistryService(db_url="sqlite:///./tools.db", cache_ttl=60)
result = registry.scan_and_register()
print(result)
```

### Step 3: Approve Tools via CLI

```bash
# List pending tools
tool-gov list --status pending

# Approve a tool
tool-gov approve cancel_order --approver team_leader
```

### Step 4: Apply Guardrails to Agent

```python
from tool_governance import apply_guardrails
from langchain.agents import AgentExecutor

executor = AgentExecutor(agent=agent, tools=[cancel_order, get_weather])
executor = apply_guardrails(executor, db_url="sqlite:///./tools.db")

# Only active tools can be called
result = executor.invoke({"input": "Please cancel order ORDER-123"})
```

## Risk-Based Approval Matrix

The framework uses permission levels to determine the initial approval workflow:

| Permission Level | Initial Status | Approval Required | Quiet Period | Developer Experience |
|------------------|---------------|------------------|--------------|---------------------|
| `public` | **auto-activated** | 0 approvals | None | Push code → 5 min → LLM uses tool |
| `internal` | pending | 1 approval (Leader) | None | DingTalk/Feishu notification → one click approve |
| `confidential` | pending | 2 approvals | 24 hours | Two approvals + 24h waiting period |
| `restricted` | pending | 2 approvals | 24 hours | Same as confidential |

### Permission Level Guidelines

- **`public`**: Read-only, non-sensitive operations (e.g., get_weather, query_public_data)
- **`internal`**: User-level write operations (e.g., update_profile, submit_form)
- **`confidential`**: High-risk operations (e.g., cancel_order, delete_data, batch_operations)
- **`restricted`**: System-level operations requiring strict controls

## CLI Usage

```bash
# List tools with filters
tool-gov list --status pending
tool-gov list --status active
tool-gov list --status all

# Approve/reject tools
tool-gov approve <tool_name> --approver <name>
tool-gov reject <tool_name>

# Submit approval to external system (DingTalk/Feishu)
tool-gov submit-approval <tool_name> --platform dingtalk
tool-gov submit-approval <tool_name> --platform feishu

# Sync approval status from external system
tool-gov sync-approval --platform dingtalk
tool-gov sync-approval --platform feishu

# Specify database URL
tool-gov --db-url sqlite:///./my_db.db list

# Start Prometheus metrics server
tool-gov metrics --port 8000 --host 0.0.0.0
```

## API Reference

### `governed_tool` Decorator

Register a tool with governance metadata.

```python
@governed_tool(
    name: Optional[str] = None,
    description: Optional[str] = None,
    permission_level: str = "default",
    args_schema: Optional[BaseModel] = None,
    creator: str = "system",
)
def my_tool():
    pass
```

### `apply_guardrails` Function

Apply runtime guardrails to an AgentExecutor - blocks inactive tool calls.

```python
executor = apply_guardrails(
    executor: AgentExecutor,
    db_url: str = "sqlite:///./tools.db",
)
```

### `ToolRegistryService` Class

Manage tool registration and lifecycle with TTL caching.

```python
registry = ToolRegistryService(
    db_url: str = "sqlite:///./tools.db",
    cache_ttl: int = 60,  # Cache expiration in seconds
)

registry.scan_and_register()          # Scan and register tools
registry.get_active_tools()           # Get active tools (with TTL cache)
registry.approve_tool(name, approver) # Approve a tool
registry.reject_tool(name)            # Reject a tool
registry.invalidate_cache()           # Manually invalidate cache
```

### External Approval Integration

Submit and sync approvals with DingTalk or Feishu:

```python
from tool_governance.core.approval import create_approval_client

client = create_approval_client(
    platform="dingtalk",
    app_key="your_app_key",
    app_secret="your_app_secret",
    process_code="your_process_code",
)

# Submit approval
result = registry.submit_approval("cancel_order", client)

# Sync approval status
results = registry.sync_approval_status(client)
```

#### Approval Status Sync Flow

```
1. submit_approval → Submit to DingTalk/Feishu, save approval_id
2. Approver operates in DingTalk/Feishu (approve/reject)
3. sync_approval_status → Query external status, update local status
   - "approved": Activate based on approval count and quiet period
   - "rejected": Mark as REJECTED
4. Auto invalidate_cache() on status change, Agent picks up changes immediately
```

## Dynamic Runtime Architecture

The framework enables **online maintenance** without restarting the Agent:

```
┌─────────────────────────────────────────────────────────────────┐
│                      Agent Runtime                              │
│                                                                 │
│   AgentExecutor.invoke()                                        │
│         │                                                       │
│         ▼                                                       │
│   apply_guardrails()                                            │
│         │                                                       │
│         ▼                                                       │
│   get_active_tools() ──┬── Cache Hit (TTL < 60s) ──► Return     │
│                        │                                        │
│                        ▼                                        │
│                   Database Query ──► Update Cache ──► Return    │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
                              ▲
                              │ Cache Invalidation
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Approval Actions                            │
│                                                                 │
│   approve_tool() → invalidate_cache()                           │
│   reject_tool()  → invalidate_cache()                           │
│   sync_approval_status() → invalidate_cache()                   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

**Key Benefits:**
- **No Restart Required**: Cache invalidation ensures changes take effect immediately
- **Performance**: TTL caching reduces database queries during high-frequency tool calls
- **Flexibility**: Adjust `cache_ttl` based on your update frequency requirements

## Database Configuration

### SQLite (Default)

```python
registry = ToolRegistryService(db_url="sqlite:///./tools.db")
```

### PostgreSQL

```python
registry = ToolRegistryService(db_url="postgresql://user:password@host:5432/dbname")
```

### Database Schema

**Table: `tool_registry`**

| Column | Type | Description |
|--------|------|-------------|
| `id` | INTEGER | Primary key |
| `name` | VARCHAR(100) | Tool name (unique) |
| `description` | TEXT | Tool description |
| `schema_json` | TEXT | Tool schema as JSON |
| `permission_level` | VARCHAR(50) | Permission level (public/internal/confidential/restricted/default) |
| `status` | VARCHAR(20) | Tool status (active/pending/rejected/deprecated) |
| `created_by` | VARCHAR(100) | Creator email |
| `created_at` | DATETIME | Creation timestamp |
| `approved_at` | DATETIME | Approval timestamp (nullable) |
| `approval_count` | INTEGER | Current approval count |
| `approval_required` | INTEGER | Required approvals |
| `approval_id` | VARCHAR(200) | External approval ID (nullable) |
| `approval_platform` | VARCHAR(50) | Approval platform (dingtalk/feishu) |
| `approvers` | TEXT | JSON list of approvers |
| `quiet_period_until` | DATETIME | Quiet period end time (nullable) |

## Monitoring & Metrics

### Prometheus Integration

The framework exposes Prometheus metrics for monitoring tool governance activity.

#### Start Metrics Server

```bash
# Using CLI options
tool-gov metrics --port 9090 --host 127.0.0.1

# Using environment variables
export TOOL_GOVERNANCE_METRICS_PORT=9090
export TOOL_GOVERNANCE_METRICS_HOST=127.0.0.1
tool-gov metrics

# Default values (port: 8000, host: 0.0.0.0)
tool-gov metrics
```

#### Configuration

The metrics server can be configured via:

1. **CLI arguments** (highest priority)
   - `--port`: Metrics server port
   - `--host`: Metrics server host

2. **Environment variables**
   - `TOOL_GOVERNANCE_METRICS_PORT`: Port (default: 8000)
   - `TOOL_GOVERNANCE_METRICS_HOST`: Host (default: 0.0.0.0)

3. **Default values** (lowest priority)
   - Port: `8000`
   - Host: `0.0.0.0`

#### Metrics Endpoint

```
http://localhost:8000/metrics
```

#### Available Metrics

| Metric | Type | Description | Labels |
|--------|------|-------------|--------|
| `toolgovernance_tool_registered_total` | Counter | Total tools registered | `permission_level` |
| `toolgovernance_tool_activated_total` | Counter | Total tools activated | `permission_level` |
| `toolgovernance_tool_rejected_total` | Counter | Total tools rejected | `permission_level` |
| `toolgovernance_tool_approvals_total` | Counter | Total approvals | `tool_name` |
| `toolgovernance_tool_active_count` | Gauge | Active tools count | `permission_level` |
| `toolgovernance_tool_status_count` | Gauge | Tools count by status | `status` |
| `toolgovernance_approval_pending_seconds` | Histogram | Pending duration before approval | `permission_level` |
| `toolgovernance_cache_hits_total` | Counter | Cache hits | None |
| `toolgovernance_cache_misses_total` | Counter | Cache misses | None |
| `toolgovernance_cache_invalidations_total` | Counter | Cache invalidations | None |

#### Grafana Dashboard Suggestions

Create panels for:
- **Tool Status Distribution**: Pie chart of `toolgovernance_tool_status_count`
- **Active Tools by Permission Level**: Bar chart of `toolgovernance_tool_active_count`
- **Approval Rate**: Rate of `toolgovernance_tool_approvals_total`
- **Approval Latency**: Histogram of `toolgovernance_approval_pending_seconds`
- **Cache Hit Ratio**: `toolgovernance_cache_hits_total / (hits + misses)`

#### Prometheus Scrape Config

```yaml
scrape_configs:
  - job_name: 'tool-governance'
    static_configs:
      - targets: ['localhost:8000']
    metrics_path: /metrics
```

## Configuration

### Environment Variables

```bash
# DingTalk Approval
export DINGTALK_APP_KEY=your_app_key
export DINGTALK_APP_SECRET=your_app_secret
export DINGTALK_PROCESS_CODE=your_process_code

# Feishu Approval
export FEISHU_APP_ID=your_app_id
export FEISHU_APP_SECRET=your_app_secret
export FEISHU_APPROVAL_CODE=your_approval_code

# Prometheus Metrics
export TOOL_GOVERNANCE_METRICS_PORT=8000
export TOOL_GOVERNANCE_METRICS_HOST=0.0.0.0
```

## Testing

```bash
pip install pytest
pytest tests/ -v
```

## License

MIT License

## Contributing

Contributions are welcome! Please submit a pull request or create an issue.