from typing import Any

from src.models.domain import DiscoveredCompany
from src.transport.base import BridgeTransport


class PersistentTransport(BridgeTransport):
    """
    Reserved for WAAST360 Prime.
    Implements long-polling, WebSocket, or Server-Sent Events (SSE)
    for bidirectional push notifications when infrastructure supports it.
    """

    def __init__(self, cloud_url: str, bridge_client_id: str, api_key: str):
        self.cloud_url = cloud_url
        self.bridge_client_id = bridge_client_id
        self.api_key = api_key

    def send_heartbeat(self, bridge_status: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError("PersistentTransport will be enabled in WAAST360 Prime.")

    def report_companies(self, companies: list[DiscoveredCompany]) -> dict[str, Any]:
        raise NotImplementedError("PersistentTransport will be enabled in WAAST360 Prime.")

    def fetch_pending_jobs(self) -> list[dict[str, Any]]:
        raise NotImplementedError("PersistentTransport will be enabled in WAAST360 Prime.")

    def submit_attempt(self, job_id: str, attempt_data: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError("PersistentTransport will be enabled in WAAST360 Prime.")

    def submit_verification(self, job_id: str, verification_data: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError("PersistentTransport will be enabled in WAAST360 Prime.")
