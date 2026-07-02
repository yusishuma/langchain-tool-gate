import json
import time
import requests
from typing import Dict, Any, Optional
from tool_governance.core.approval import ApprovalClient


class FeishuApprovalClient(ApprovalClient):
    def __init__(self, app_id: str, app_secret: str, approval_code: str):
        self.app_id = app_id
        self.app_secret = app_secret
        self.approval_code = approval_code
        self._access_token = None
        self._token_expires_at = 0

    def _get_access_token(self) -> str:
        now = int(time.time())
        if self._access_token and now < self._token_expires_at:
            return self._access_token

        url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
        data = {
            "app_id": self.app_id,
            "app_secret": self.app_secret,
        }
        response = requests.post(url, json=data)
        data = response.json()

        if data.get("code") != 0:
            raise Exception(f"Feishu API error: {data.get('msg')}")

        self._access_token = data["tenant_access_token"]
        self._token_expires_at = now + data.get("expire", 7200) - 60
        return self._access_token

    def submit_approval(self, tool_name: str, tool_description: str, creator: str, permission_level: str) -> Dict[str, Any]:
        url = "https://open.feishu.cn/open-apis/approval/v4/instances/create"
        access_token = self._get_access_token()

        form = [
            {"name": "Tool Name", "value": tool_name},
            {"name": "Tool Description", "value": tool_description},
            {"name": "Creator", "value": creator},
            {"name": "Permission Level", "value": permission_level},
        ]

        data = {
            "approval_code": self.approval_code,
            "originator_user_id": creator,
            "form": form,
        }

        headers = {"Authorization": f"Bearer {access_token}"}
        response = requests.post(url, headers=headers, json=data)
        result = response.json()

        if result.get("code") != 0:
            raise Exception(f"Feishu approval error: {result.get('msg')}")

        return {
            "approval_id": result["data"]["instance_id"],
            "message": "Approval submitted",
        }

    def get_approval_status(self, approval_id: str) -> Dict[str, Any]:
        url = "https://open.feishu.cn/open-apis/approval/v4/instances/get"
        access_token = self._get_access_token()

        params = {
            "instance_id": approval_id,
        }

        headers = {"Authorization": f"Bearer {access_token}"}
        response = requests.get(url, headers=headers, params=params)
        result = response.json()

        if result.get("code") != 0:
            raise Exception(f"Feishu API error: {result.get('msg')}")

        status_map = {
            "PENDING": "running",
            "RUNNING": "running",
            "APPROVED": "approved",
            "REJECTED": "rejected",
            "CANCELED": "canceled",
        }

        instance = result["data"]
        return {
            "approval_id": approval_id,
            "status": status_map.get(instance.get("status"), "unknown"),
            "title": instance.get("title", ""),
            "creator": instance.get("originator", {}).get("user_id", ""),
            "created_at": instance.get("create_time", 0),
            "approved_at": instance.get("finish_time", 0),
            "approver": [a.get("user_id", "") for a in instance.get("tasks", [])],
        }

    def approve(self, approval_id: str, comment: str = "") -> bool:
        url = "https://open.feishu.cn/open-apis/approval/v4/instances/approve"
        access_token = self._get_access_token()

        data = {
            "instance_id": approval_id,
            "action_type": "approve",
            "comment": comment,
        }

        headers = {"Authorization": f"Bearer {access_token}"}
        response = requests.post(url, headers=headers, json=data)
        result = response.json()

        if result.get("code") != 0:
            raise Exception(f"Feishu approval error: {result.get('msg')}")

        return True

    def reject(self, approval_id: str, comment: str = "") -> bool:
        url = "https://open.feishu.cn/open-apis/approval/v4/instances/approve"
        access_token = self._get_access_token()

        data = {
            "instance_id": approval_id,
            "action_type": "reject",
            "comment": comment,
        }

        headers = {"Authorization": f"Bearer {access_token}"}
        response = requests.post(url, headers=headers, json=data)
        result = response.json()

        if result.get("code") != 0:
            raise Exception(f"Feishu rejection error: {result.get('msg')}")

        return True