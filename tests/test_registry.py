import pytest
from tool_governance.core.registry import ToolRegistryService
from tool_governance.core.scanner import governed_tool, _TOOL_METADATA


@pytest.fixture(autouse=True)
def reset_metadata():
    _TOOL_METADATA.clear()
    yield


def test_scan_and_register():
    db_url = "sqlite:///:memory:"
    registry = ToolRegistryService(db_url)

    @governed_tool(name="test_tool", description="A test tool", permission_level="low", creator="test_user")
    def test_tool():
        return "test"

    registry.scan_and_register()

    tools = registry.get_tools_by_status("all")
    assert len(tools) == 1
    assert tools[0]["name"] == "test_tool"
    assert tools[0]["status"] == "pending"
    assert tools[0]["created_by"] == "test_user"


def test_approve_tool():
    db_url = "sqlite:///:memory:"
    registry = ToolRegistryService(db_url)

    @governed_tool(name="test_tool", description="A test tool", creator="test_user")
    def test_tool():
        return "test"

    registry.scan_and_register()
    registry.approve_tool("test_tool", "admin")

    tools = registry.get_active_tools()
    assert len(tools) == 1
    assert tools[0]["name"] == "test_tool"
    assert tools[0]["status"] == "active"
    assert tools[0]["approved_at"] is not None


def test_reject_tool():
    db_url = "sqlite:///:memory:"
    registry = ToolRegistryService(db_url)

    @governed_tool(name="test_tool", description="A test tool", creator="test_user")
    def test_tool():
        return "test"

    registry.scan_and_register()
    registry.reject_tool("test_tool")

    tools = registry.get_tools_by_status("rejected")
    assert len(tools) == 1
    assert tools[0]["status"] == "rejected"


def test_get_active_tools_filters_by_status():
    db_url = "sqlite:///:memory:"
    registry = ToolRegistryService(db_url)

    @governed_tool(name="active_tool", description="Active tool", creator="user")
    def active_tool():
        return "active"

    @governed_tool(name="pending_tool", description="Pending tool", creator="user")
    def pending_tool():
        return "pending"

    registry.scan_and_register()
    registry.approve_tool("active_tool", "admin")

    active_tools = registry.get_active_tools()
    assert len(active_tools) == 1
    assert active_tools[0]["name"] == "active_tool"


def test_public_level_auto_activates():
    db_url = "sqlite:///:memory:"
    registry = ToolRegistryService(db_url)

    @governed_tool(name="public_tool", description="Public read-only tool", permission_level="public", creator="user")
    def public_tool():
        return "public"

    registry.scan_and_register()

    tools = registry.get_tools_by_status("all")
    assert len(tools) == 1
    assert tools[0]["status"] == "active"
    assert tools[0]["approval_required"] == 0


def test_internal_level_single_approval():
    db_url = "sqlite:///:memory:"
    registry = ToolRegistryService(db_url)

    @governed_tool(name="internal_tool", description="Internal write tool", permission_level="internal", creator="user")
    def internal_tool():
        return "internal"

    registry.scan_and_register()

    tools = registry.get_tools_by_status("pending")
    assert len(tools) == 1
    assert tools[0]["approval_required"] == 1

    result = registry.approve_tool("internal_tool", "leader")
    assert result["success"]
    assert tools[0]["name"] == "internal_tool"

    active_tools = registry.get_active_tools()
    assert len(active_tools) == 1


def test_confidential_level_dual_approval():
    db_url = "sqlite:///:memory:"
    registry = ToolRegistryService(db_url)

    @governed_tool(name="confidential_tool", description="High-risk tool", permission_level="confidential", creator="user")
    def confidential_tool():
        return "confidential"

    registry.scan_and_register()

    tools = registry.get_tools_by_status("pending")
    assert len(tools) == 1
    assert tools[0]["approval_required"] == 2
    assert tools[0]["quiet_period_until"] is not None

    result1 = registry.approve_tool("confidential_tool", "leader1")
    assert result1["success"]
    assert result1["approval_count"] == 1
    assert result1["approval_required"] == 2

    result2 = registry.approve_tool("confidential_tool", "leader2")
    assert result2["success"]
    assert "quiet period" in result2["message"].lower()


def test_duplicate_approval_rejected():
    db_url = "sqlite:///:memory:"
    registry = ToolRegistryService(db_url)

    @governed_tool(name="confidential_tool", description="Confidential tool", permission_level="confidential", creator="user")
    def confidential_tool():
        return "confidential"

    registry.scan_and_register()

    result1 = registry.approve_tool("confidential_tool", "leader")
    assert result1["success"]
    assert result1["approval_count"] == 1

    result2 = registry.approve_tool("confidential_tool", "leader")
    assert not result2["success"]
    assert "already approved" in result2["message"]


def test_cache_ttl_mechanism():
    db_url = "sqlite:///:memory:"
    registry = ToolRegistryService(db_url, cache_ttl=1)

    @governed_tool(name="public_tool", description="Public tool", permission_level="public", creator="user")
    def public_tool():
        return "public"

    registry.scan_and_register()

    tools1 = registry.get_active_tools()
    assert len(tools1) == 1

    tools2 = registry.get_active_tools()
    assert tools1 is tools2

    import time
    time.sleep(2)

    tools3 = registry.get_active_tools()
    assert tools1 is not tools3
    assert len(tools3) == 1


def test_cache_invalidation_on_approval():
    db_url = "sqlite:///:memory:"
    registry = ToolRegistryService(db_url, cache_ttl=3600)

    @governed_tool(name="internal_tool", description="Internal tool", permission_level="internal", creator="user")
    def internal_tool():
        return "internal"

    registry.scan_and_register()

    tools1 = registry.get_active_tools()
    assert len(tools1) == 0

    registry.approve_tool("internal_tool", "leader")

    tools2 = registry.get_active_tools()
    assert len(tools2) == 1
    assert tools1 is not tools2


def test_manual_cache_invalidation():
    db_url = "sqlite:///:memory:"
    registry = ToolRegistryService(db_url, cache_ttl=3600)

    @governed_tool(name="public_tool", description="Public tool", permission_level="public", creator="user")
    def public_tool():
        return "public"

    registry.scan_and_register()

    tools1 = registry.get_active_tools()
    tools2 = registry.get_active_tools()
    assert tools1 is tools2

    registry.invalidate_cache()

    tools3 = registry.get_active_tools()
    assert tools1 is not tools3