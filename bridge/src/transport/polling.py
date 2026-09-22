from typing import Any

import requests

from src.models.domain import DiscoveredCompany
from src.transport.base import BridgeTransport


class PollingTransport(BridgeTransport):
    """
    Outbound HTTPS polling transport for WAAST360 Lite.
    All connections are initiated by the local Bridge, meaning Tally port 9000
    is never exposed publicly and no inbound firewall rules are needed.
    """

    def __init__(
        self,
        cloud_url: str,
        bridge_client_id: str,
        api_key: str,
        timeout_seconds: float = 15.0,
    ):
        self.cloud_url = cloud_url.rstrip("/")
        self.bridge_client_id = bridge_client_id
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds

    def _headers(self) -> dict[str, str]:
        return {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "X-Bridge-Client-Id": self.bridge_client_id,
            "X-Bridge-Key": self.api_key,
        }

    def send_heartbeat(self, bridge_status: dict[str, Any]) -> dict[str, Any]:
        url = f"{self.cloud_url}/api/v1/bridge/heartbeat"
        resp = requests.post(
            url,
            json=bridge_status,
            headers=self._headers(),
            timeout=self.timeout_seconds,
        )
        resp.raise_for_status()
        return resp.json()

    def report_companies(self, companies: list[DiscoveredCompany]) -> dict[str, Any]:
        url = f"{self.cloud_url}/api/v1/bridge/companies"
        payload = {"companies": [c.model_dump() for c in companies]}
        resp = requests.post(
            url, json=payload, headers=self._headers(), timeout=self.timeout_seconds
        )
        resp.raise_for_status()
        return resp.json()

    def fetch_pending_jobs(self) -> list[dict[str, Any]]:
        url = f"{self.cloud_url}/api/v1/bridge/jobs/pending"
        resp = requests.get(url, headers=self._headers(), timeout=self.timeout_seconds)
        resp.raise_for_status()
        return resp.json().get("jobs", [])

    def submit_attempt(self, job_id: str, attempt_data: dict[str, Any]) -> dict[str, Any]:
        url = f"{self.cloud_url}/api/v1/bridge/jobs/{job_id}/attempts"
        resp = requests.post(
            url,
            json=attempt_data,
            headers=self._headers(),
            timeout=self.timeout_seconds,
        )
        resp.raise_for_status()
        return resp.json()

    def submit_verification(self, job_id: str, verification_data: dict[str, Any]) -> dict[str, Any]:
        url = f"{self.cloud_url}/api/v1/bridge/jobs/{job_id}/verification"
        resp = requests.post(
            url,
            json=verification_data,
            headers=self._headers(),
            timeout=self.timeout_seconds,
        )
        resp.raise_for_status()
        return resp.json()
