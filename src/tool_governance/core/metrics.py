from prometheus_client import Counter, Gauge, Histogram, Summary

TOOL_REGISTERED = Counter(
    "toolgovernance_tool_registered_total",
    "Total number of tools registered",
    ["permission_level"],
)

TOOL_ACTIVATED = Counter(
    "toolgovernance_tool_activated_total",
    "Total number of tools activated",
    ["permission_level"],
)

TOOL_REJECTED = Counter(
    "toolgovernance_tool_rejected_total",
    "Total number of tools rejected",
    ["permission_level"],
)

TOOL_APPROVALS = Counter(
    "toolgovernance_tool_approvals_total",
    "Total number of tool approvals",
    ["tool_name"],
)

TOOL_ACTIVE_COUNT = Gauge(
    "toolgovernance_tool_active_count",
    "Number of active tools",
    ["permission_level"],
)

TOOL_STATUS_COUNT = Gauge(
    "toolgovernance_tool_status_count",
    "Number of tools by status",
    ["status"],
)

APPROVAL_PENDING_DURATION = Histogram(
    "toolgovernance_approval_pending_seconds",
    "Duration tools spend in pending state before approval",
    ["permission_level"],
    buckets=[60, 300, 600, 1800, 3600, 7200, 14400, 86400],
)

CACHE_HITS = Counter(
    "toolgovernance_cache_hits_total",
    "Number of cache hits",
)

CACHE_MISSES = Counter(
    "toolgovernance_cache_misses_total",
    "Number of cache misses",
)

CACHE_INVALIDATIONS = Counter(
    "toolgovernance_cache_invalidations_total",
    "Number of cache invalidations",
)

REGISTRY_OPERATION_DURATION = Summary(
    "toolgovernance_registry_operation_duration_seconds",
    "Duration of registry operations",
    ["operation"],
)