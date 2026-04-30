from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any
from urllib import error, parse, request


class SupabaseStore:
    def __init__(self, url: str | None = None, key: str | None = None):
        self.url = (url or os.getenv("SUPABASE_URL", "")).rstrip("/")
        self.key = key or os.getenv("SUPABASE_KEY", "")
        self.enabled = bool(self.url and self.key)

    def save_run(self, run_payload: dict[str, Any]) -> str | None:
        if not self.enabled:
            return None
        payload = {
            **run_payload,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        result = self._request("POST", "/rest/v1/runs", payload, prefer="return=representation")
        if result and isinstance(result, list) and result:
            return result[0].get("run_id")
        return None

    def save_findings(self, findings: list[dict[str, Any]]) -> None:
        if not self.enabled or not findings:
            return
        self._request("POST", "/rest/v1/findings", findings, prefer="resolution=merge-duplicates,return=minimal")

    def save_gate_result(self, gate_payload: dict[str, Any]) -> None:
        if not self.enabled:
            return
        self._request("POST", "/rest/v1/gate_results", gate_payload, prefer="return=minimal")

    def save_status_event(self, event_payload: dict[str, Any]) -> None:
        if not self.enabled:
            return
        payload = {**event_payload, "event_at": datetime.now(timezone.utc).isoformat()}
        self._request("POST", "/rest/v1/finding_status_events", payload, prefer="return=minimal")

    def fetch_latest_run_for_source(self, source_label: str) -> dict[str, Any] | None:
        if not self.enabled:
            return None
        query = parse.urlencode(
            {
                "source_label": f"eq.{source_label}",
                "order": "created_at.desc",
                "limit": 1,
            }
        )
        result = self._request("GET", f"/rest/v1/runs?{query}", None)
        if result and isinstance(result, list):
            return result[0]
        return None

    def fetch_findings_for_run(self, run_id: str) -> list[dict[str, Any]]:
        if not self.enabled or not run_id:
            return []
        query = parse.urlencode({"run_id": f"eq.{run_id}", "limit": 1000})
        result = self._request("GET", f"/rest/v1/findings?{query}", None)
        if isinstance(result, list):
            return result
        return []

    def fetch_issue_queue(self, source_filter: str | None = None) -> list[dict[str, Any]]:
        if not self.enabled:
            return []
        params = {"order": "updated_at.desc", "limit": 2000}
        if source_filter:
            params["source_label"] = f"eq.{source_filter}"
        query = parse.urlencode(params)
        result = self._request("GET", f"/rest/v1/findings?{query}", None)
        return result if isinstance(result, list) else []

    def update_finding(self, finding_id: str, updates: dict[str, Any]) -> None:
        if not self.enabled:
            return
        query = parse.urlencode({"finding_id": f"eq.{finding_id}"})
        payload = {
            **updates,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        self._request("PATCH", f"/rest/v1/findings?{query}", payload, prefer="return=minimal")

    def _request(self, method: str, path: str, payload: dict[str, Any] | list[dict[str, Any]] | None, prefer: str | None = None):
        endpoint = f"{self.url}{path}"
        data = None if payload is None else json.dumps(payload).encode("utf-8")
        headers = {
            "apikey": self.key,
            "Authorization": f"Bearer {self.key}",
            "Content-Type": "application/json",
        }
        if prefer:
            headers["Prefer"] = prefer
        req = request.Request(endpoint, method=method, headers=headers, data=data)
        try:
            with request.urlopen(req, timeout=20) as response:
                body = response.read().decode("utf-8")
                if not body:
                    return None
                return json.loads(body)
        except error.HTTPError:
            return None
        except error.URLError:
            return None
