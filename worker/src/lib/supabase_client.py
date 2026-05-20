"""
lib/supabase_client.py — Supabase REST API using CF built-in fetch (no httpx).
"""
import json
import logging
from datetime import datetime
from typing import List, Dict, Optional, Any

from .cf_fetch import cf_get, cf_post, cf_patch, cf_delete

logger = logging.getLogger(__name__)


class SupabaseDB:
    def __init__(self, url: str, key: str):
        self.base = f"{url}/rest/v1"
        self.rpc_base = f"{url}/rest/v1/rpc"
        self.headers = {
            "apikey": key,
            "Authorization": f"Bearer {key}",
            "Prefer": "return=representation",
        }

    # ── helpers ──────────────────────────────────────────────────────────────
    def _h(self, extra: dict = None) -> dict:
        return {**self.headers, **(extra or {})}

    async def _get(self, table: str, params: dict = None) -> list:
        return await cf_get(f"{self.base}/{table}", headers=self.headers, params=params or {})

    async def _post(self, table: str, data: dict, extra: dict = None) -> Any:
        return await cf_post(f"{self.base}/{table}", headers=self._h(extra), data=data)

    async def _rpc(self, fn: str, data: dict) -> Any:
        return await cf_post(f"{self.rpc_base}/{fn}", headers=self.headers, data=data)

    async def _patch(self, table: str, params: dict, data: dict) -> Any:
        return await cf_patch(f"{self.base}/{table}", headers=self.headers, params=params, data=data)

    async def _delete(self, table: str, params: dict) -> bool:
        return await cf_delete(f"{self.base}/{table}", headers=self.headers, params=params)

    # ── tasks ─────────────────────────────────────────────────────────────────
    async def add_task(self, user_id: int, title: str, description: str, deadline: datetime) -> int:
        result = await self._rpc("create_task_with_mapping", {
            "p_user_id": user_id, "p_title": title,
            "p_desc": description or "", "p_deadline": deadline.isoformat(),
        })
        return int(result)

    async def get_user_tasks(self, user_id: int, include_completed: bool = False) -> List[Dict]:
        params = {
            "user_id": f"eq.{user_id}",
            "select": "*, user_task_id_mapping(user_task_id), reminders(*)",
            "order": "deadline.asc",
        }
        if not include_completed:
            params["completed"] = "eq.false"
        rows = await self._get("tasks", params)
        tasks = []
        for row in rows:
            mapping = row.pop("user_task_id_mapping", None)
            row["user_task_id"] = _get_user_task_id(mapping)
            row["reminders"] = row.pop("reminders", []) or []
            row["deadline"] = _parse_iso(row.get("deadline"))
            tasks.append(row)
        return tasks

    async def get_task_by_id(self, user_id: int, user_task_id: int) -> Optional[Dict]:
        actual_id = await self.get_actual_task_id(user_id, user_task_id)
        if not actual_id:
            return None
        rows = await self._get("tasks", {
            "id": f"eq.{actual_id}", "user_id": f"eq.{user_id}",
            "select": "*, user_task_id_mapping(user_task_id), reminders(*)",
        })
        if not rows:
            return None
        row = rows[0]
        mapping = row.pop("user_task_id_mapping", None)
        row["user_task_id"] = _get_user_task_id(mapping) or user_task_id
        row["reminders"] = row.pop("reminders", []) or []
        row["deadline"] = _parse_iso(row.get("deadline"))
        return row

    async def update_task(self, actual_task_id: int, **kwargs) -> bool:
        allowed = {"title", "description", "deadline", "completed", "completed_at"}
        data = {k: (v.isoformat() if isinstance(v, datetime) else v)
                for k, v in kwargs.items() if k in allowed}
        if not data:
            return False
        await self._patch("tasks", {"id": f"eq.{actual_task_id}"}, data)
        return True

    async def delete_task(self, actual_task_id: int) -> bool:
        return await self._delete("tasks", {"id": f"eq.{actual_task_id}"})

    async def clear_all_user_data(self, user_id: int) -> int:
        rows = await self._get("tasks", {"user_id": f"eq.{user_id}", "select": "id"})
        if not rows:
            return 0
        await self._delete("tasks", {"user_id": f"eq.{user_id}"})
        return len(rows)

    async def get_actual_task_id(self, user_id: int, user_task_id: int) -> Optional[int]:
        rows = await self._get("user_task_id_mapping", {
            "user_id": f"eq.{user_id}",
            "user_task_id": f"eq.{user_task_id}",
            "select": "actual_task_id",
        })
        return rows[0]["actual_task_id"] if rows else None

    # ── reminders ─────────────────────────────────────────────────────────────
    async def add_reminder(self, task_id: int, frequency_type: str, frequency_value: int,
                           start_time=None, end_time=None, escalation_enabled=False,
                           escalation_threshold=60, custom_messages=None) -> Optional[int]:
        data = {
            "task_id": task_id, "frequency_type": frequency_type,
            "frequency_value": frequency_value, "start_time": start_time,
            "end_time": end_time, "escalation_enabled": escalation_enabled,
            "escalation_threshold": escalation_threshold,
            "custom_messages": json.dumps(custom_messages) if custom_messages else None,
        }
        result = await self._post("reminders", data)
        if isinstance(result, list) and result:
            return result[0].get("id")
        return None

    async def update_reminder(self, reminder_id: int, **kwargs) -> bool:
        allowed = {"frequency_type", "frequency_value", "start_time", "end_time",
                   "escalation_enabled", "escalation_threshold",
                   "custom_messages", "last_sent", "next_reminder"}
        data = {}
        for k, v in kwargs.items():
            if k not in allowed:
                continue
            if k == "custom_messages" and v is not None:
                v = json.dumps(v)
            elif isinstance(v, datetime):
                v = v.isoformat()
            data[k] = v
        if not data:
            return False
        await self._patch("reminders", {"id": f"eq.{reminder_id}"}, data)
        return True

    async def get_pending_reminders(self) -> List[Dict]:
        rows = await self._get("tasks", {
            "completed": "eq.false",
            "select": (
                "id,user_id,title,description,deadline,created_at,completed,"
                "user_task_id_mapping(user_task_id),"
                "reminders(id,frequency_type,frequency_value,start_time,end_time,"
                "escalation_enabled,escalation_threshold,custom_messages,last_sent)"
            ),
            "order": "deadline.asc",
        })
        results = []
        for row in rows:
            mapping = row.pop("user_task_id_mapping", None)
            user_task_id = _get_user_task_id(mapping)
            for r in (row.pop("reminders", []) or []):
                results.append({
                    "task_id": row["id"], "user_task_id": user_task_id,
                    "user_id": row["user_id"], "title": row["title"],
                    "description": row.get("description"), "deadline": row["deadline"],
                    "created_at": row.get("created_at"), "completed": row.get("completed"),
                    "reminder_id": r["id"], "frequency_type": r["frequency_type"],
                    "frequency_value": r["frequency_value"],
                    "start_time": r.get("start_time"), "end_time": r.get("end_time"),
                    "escalation_enabled": r.get("escalation_enabled", False),
                    "escalation_threshold": r.get("escalation_threshold", 60),
                    "custom_messages": _parse_json(r.get("custom_messages")),
                    "last_sent": r.get("last_sent"),
                })
        return results

    async def log_reminder_sent(self, task_id: int, message_type: str = "normal"):
        try:
            await self._post("reminder_history", {"task_id": task_id, "message_type": message_type},
                             extra={"Prefer": "return=minimal"})
        except Exception as e:
            logger.error(f"log_reminder_sent: {e}")

    # ── users ─────────────────────────────────────────────────────────────────
    async def set_user_timezone(self, user_id: int, timezone: str) -> bool:
        await self._post("users", {"user_id": user_id, "timezone": timezone},
                         extra={"Prefer": "resolution=merge-duplicates,return=minimal"})
        return True

    async def get_user_timezone(self, user_id: int) -> str:
        rows = await self._get("users", {"user_id": f"eq.{user_id}", "select": "timezone"})
        return (rows[0].get("timezone") or "UTC") if rows else "UTC"

    async def update_user_activity(self, user_id: int, username=None, full_name=None):
        try:
            await self._post("users", {
                "user_id": user_id, "username": username, "full_name": full_name,
                "last_active_at": datetime.utcnow().isoformat(),
            }, extra={"Prefer": "resolution=merge-duplicates,return=minimal"})
        except Exception as e:
            logger.error(f"update_user_activity: {e}")

    # ── conversation state ────────────────────────────────────────────────────
    async def get_conversation_state(self, user_id: int) -> Optional[Dict]:
        rows = await self._get("conversation_state", {"user_id": f"eq.{user_id}"})
        if rows:
            row = rows[0]
            row["data"] = row.get("data") or {}
            return row
        return None

    async def set_conversation_state(self, user_id: int, command: str, step: str, data: dict = None):
        await self._post("conversation_state", {
            "user_id": user_id, "command": command, "step": step,
            "data": data or {}, "updated_at": datetime.utcnow().isoformat(),
        }, extra={"Prefer": "resolution=merge-duplicates,return=minimal"})

    async def clear_conversation_state(self, user_id: int):
        await self._delete("conversation_state", {"user_id": f"eq.{user_id}"})

    # ── metrics & errors ──────────────────────────────────────────────────────
    async def log_bot_error(self, user_id, error_type, error_message, stack_trace):
        try:
            await self._post("bot_errors", {
                "user_id": user_id, "error_type": error_type,
                "error_message": error_message, "stack_trace": stack_trace,
            }, extra={"Prefer": "return=minimal"})
        except Exception:
            pass

    async def log_bot_metric(self, user_id: int, command: str, processing_time_ms: float):
        try:
            await self._post("bot_metrics", {
                "user_id": user_id, "command": command,
                "processing_time_ms": processing_time_ms,
            }, extra={"Prefer": "return=minimal"})
        except Exception:
            pass


# ── helpers ───────────────────────────────────────────────────────────────────
def _get_user_task_id(mapping) -> Optional[int]:
    if not mapping:
        return None
    if isinstance(mapping, list):
        return mapping[0].get("user_task_id") if mapping[0] else None
    if isinstance(mapping, dict):
        return mapping.get("user_task_id")
    return None


def _parse_iso(value) -> Optional[datetime]:
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except Exception:
        return None


def _parse_json(value):
    if not value:
        return None
    if isinstance(value, (list, dict)):
        return value
    try:
        return json.loads(value)
    except Exception:
        return None
