import json
import time
import requests
from typing import Dict, Any, Optional
from tool_governance.core.approval import ApprovalClient


class DingTalkApprovalClient(ApprovalClient):
    def __init__(self, app_key: str, app_secret: str, process_code: str, agent_id: Optional[str] = None):
        self.app_key = app_key
        self.app_secret = app_secret
        self.process_code = process_code
        self.agent_id = agent_id
        self._access_token = None
        self._token_expires_at = 0

    def _get_access_token(self) -> str:
        now = int(time.time())
        if self._access_token and now < self._token_expires_at:
            return self._access_token

        url = "https://oapi.dingtalk.com/gettoken"
        params = {
            "appkey": self.app_key,
            "appsecret": self.app_secret,
        }
        response = requests.get(url, params=params)
        data = response.json()

        if data.get("errcode") != 0:
            raise Exception(f"DingTalk API error: {data.get('errmsg')}")

        self._access_token = data["access_token"]
        self._token_expires_at = now + data.get("expires_in", 7200) - 60
        return self._access_token

    def submit_approval(self, tool_name: str, tool_description: str, creator: str, permission_level: str) -> Dict[str, Any]:
        url = "https://oapi.dingtalk.com/topapi/processinstance/create"
        access_token = self._get_access_token()

        form_component_values = [
            {"name": "Tool Name", "value": tool_name},
            {"name": "Tool Description", "value": tool_description},
            {"name": "Creator", "value": creator},
            {"name": "Permission Level", "value": permission_level},
        ]

        data = {
            "process_code": self.process_code,
            "originator_user_id": creator,
            "dept_id": "1",
            "form_component_values": json.dumps(form_component_values),
        }

        if self.agent_id:
            data["agent_id"] = self.agent_id

        response = requests.post(url, params={"access_token": access_token}, json=data)
        result = response.json()

        if result.get("errcode") != 0:
            raise Exception(f"DingTalk approval error: {result.get('errmsg')}")

        return {
            "approval_id": result["result"]["process_instance_id"],
            "message": "Approval submitted",
        }

    def get_approval_status(self, approval_id: str) -> Dict[str, Any]:
        url = "https://oapi.dingtalk.com/topapi/processinstance/get"
        access_token = self._get_access_token()

        data = {
            "process_instance_id": approval_id,
        }

        response = requests.post(url, params={"access_token": access_token}, json=data)
        result = response.json()

        if result.get("errcode") != 0:
            raise Exception(f"DingTalk API error: {result.get('errmsg')}")

        status_map = {
            "RUNNING": "running",
            "TERMINATED": "rejected",
            "COMPLETED": "approved",
        }

        process_instance = result["result"]
        return {
            "approval_id": approval_id,
            "status": status_map.get(process_instance.get("status"), "unknown"),
            "title": process_instance.get("title", ""),
            "creator": process_instance.get("originator_user_id", ""),
            "created_at": process_instance.get("create_time", 0),
            "approved_at": process_instance.get("finish_time", 0),
            "approver": process_instance.get("approver_user_id_list", []),
        }

    def approve(self, approval_id: str, comment: str = "") -> bool:
        url = "https://oapi.dingtalk.com/topapi/processinstance/approve"
        access_token = self._get_access_token()

        data = {
            "process_instance_id": approval_id,
            "action_type": "agree",
            "remark": comment,
        }

        response = requests.post(url, params={"access_token": access_token}, json=data)
        result = response.json()

        if result.get("errcode") != 0:
            raise Exception(f"DingTalk approval error: {result.get('errmsg')}")

        return True

    def reject(self, approval_id: str, comment: str = "") -> bool:
        url = "https://oapi.dingtalk.com/topapi/processinstance/approve"
        access_token = self._get_access_token()

        data = {
            "process_instance_id": approval_id,
            "action_type": "reject",
            "remark": comment,
        }

        response = requests.post(url, params={"access_token": access_token}, json=data)
        result = response.json()

        if result.get("errcode") != 0:
            raise Exception(f"DingTalk rejection error: {result.get('errmsg')}")

        return True