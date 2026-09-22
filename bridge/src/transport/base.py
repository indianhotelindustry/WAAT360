from abc import ABC, abstractmethod
from typing import Any

from src.models.domain import DiscoveredCompany


class BridgeTransport(ABC):
    """
    Abstract outbound-initiated secure Bridge channel.
    Decouples Bridge orchestration from the concrete wire transport
    (PollingTransport in Lite, PersistentTransport in Prime).
    """

    @abstractmethod
    def send_heartbeat(self, bridge_status: dict[str, Any]) -> dict[str, Any]:
        """Transmit periodic heartbeat with Tally health and Bridge state."""

    @abstractmethod
    def report_companies(self, companies: list[DiscoveredCompany]) -> dict[str, Any]:
        """Synchronize discovered Tally companies with WAAST360 Cloud."""

    @abstractmethod
    def fetch_pending_jobs(self) -> list[dict[str, Any]]:
        """Retrieve queued posting/sync jobs assigned to this Bridge."""

    @abstractmethod
    def submit_attempt(self, job_id: str, attempt_data: dict[str, Any]) -> dict[str, Any]:
        """Report the result of a posting attempt to Cloud."""

    @abstractmethod
    def submit_verification(self, job_id: str, verification_data: dict[str, Any]) -> dict[str, Any]:
        """Report read-back verification evidence to Cloud."""
