from abc import ABC, abstractmethod
from typing import Dict, Any, Optional


class ApprovalClient(ABC):
    @abstractmethod
    def submit_approval(self, tool_name: str, tool_description: str, creator: str, permission_level: str) -> Dict[str, Any]:
        pass

    @abstractmethod
    def get_approval_status(self, approval_id: str) -> Dict[str, Any]:
        pass

    @abstractmethod
    def approve(self, approval_id: str, comment: str = "") -> bool:
        pass

    @abstractmethod
    def reject(self, approval_id: str, comment: str = "") -> bool:
        pass


def create_approval_client(platform: str, **kwargs) -> ApprovalClient:
    if platform.lower() == "dingtalk":
        from tool_governance.core.dingtalk import DingTalkApprovalClient
        return DingTalkApprovalClient(**kwargs)
    elif platform.lower() == "feishu":
        from tool_governance.core.feishu import FeishuApprovalClient
        return FeishuApprovalClient(**kwargs)
    else:
        raise ValueError(f"Unsupported platform: {platform}")