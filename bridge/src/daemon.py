import logging
import time

from src.adapters.factory import get_tally_adapter
from src.config import BridgeSettings, bridge_settings
from src.engine.reconciler import PostingReconciler
from src.store.local_store import BridgeLocalStore
from src.transport.polling import PollingTransport

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("waast_bridge.daemon")


class BridgeDaemon:
    """
    Main execution service of the local WAAST360 Bridge.
    Connects to local Tally runtime, communicates outbound to WAAST360 Cloud,
    maintains a local durable queue, and executes jobs safely with reconciliation.
    """

    def __init__(self, settings: BridgeSettings | None = None):
        self.settings = settings or bridge_settings
        self.adapter = get_tally_adapter(
            host=self.settings.TALLY_HOST,
            port=self.settings.TALLY_PORT,
            prefer_json=self.settings.PREFER_JSON,
        )
        db_path = self.settings.DB_PATH if self.settings.DB_PATH else None
        self.store = BridgeLocalStore(db_path=db_path)
        self.transport = PollingTransport(
            cloud_url=self.settings.CLOUD_URL,
            bridge_client_id=self.settings.BRIDGE_CLIENT_ID,
            api_key=self.settings.BRIDGE_API_KEY,
        )
        self.reconciler = PostingReconciler(
            adapter=self.adapter,
            store=self.store,
            transport=self.transport,
        )
        self._running = False

    def run_cycle(self) -> dict:
        """
        Execute one operational cycle:
        1. Check Tally health
        2. Heartbeat to Cloud
        3. Discover & sync companies
        4. Poll for cloud jobs and enqueue
        5. Drain local queue
        """
        result = {
            "tally_online": False,
            "heartbeat_sent": False,
            "companies_discovered": 0,
            "jobs_processed": 0,
        }

        # 1. Tally Health
        tally_status = self.adapter.get_tally_status()
        result["tally_online"] = tally_status.is_online
        self.store.update_tally_health(
            is_online=tally_status.is_online,
            version=tally_status.tally_version,
            response_time_ms=tally_status.response_time_ms,
            capabilities=tally_status.capabilities.model_dump(),
        )

        # 2. Heartbeat
        try:
            self.transport.send_heartbeat(
                {
                    "bridge_client_id": self.settings.BRIDGE_CLIENT_ID,
                    "status": "ONLINE" if tally_status.is_online else "DEGRADED",
                    "tally_status": tally_status.model_dump(),
                }
            )
            result["heartbeat_sent"] = True
        except Exception as e:
            logger.warning("Cloud heartbeat failed: %s", e)
            self.store.log_diagnostic("HEARTBEAT_FAILED", str(e))

        # 3. Company discovery if Tally is online
        if tally_status.is_online:
            try:
                companies = self.adapter.get_companies()
                result["companies_discovered"] = len(companies)
                if companies:
                    self.transport.report_companies(companies)
            except Exception as e:
                logger.warning("Company discovery reporting failed: %s", e)
                self.store.log_diagnostic("DISCOVERY_FAILED", str(e))

        # 4. Poll Cloud for jobs
        try:
            cloud_jobs = self.transport.fetch_pending_jobs()
            for cjob in cloud_jobs:
                self.store.enqueue_job(
                    job_id=cjob["job_id"],
                    correlation_id=cjob["correlation_id"],
                    job_type=cjob.get("job_type", "POSTING"),
                    payload=cjob["payload"],
                )
        except Exception as e:
            logger.debug("Polling cloud for jobs failed: %s", e)

        # 5. Drain local pending jobs
        pending = self.store.get_pending_jobs(limit=10)
        for job in pending:
            try:
                self.reconciler.execute_posting_job(job)
                result["jobs_processed"] += 1
            except Exception as e:
                logger.error("Error executing job %s: %s", job["job_id"], e)
                self.store.log_diagnostic("JOB_EXECUTION_ERROR", str(e), {"job_id": job["job_id"]})

        return result

    def start(self):
        """Start daemon loop."""
        self._running = True
        logger.info("Starting WAAST360 Bridge daemon (%s)", self.settings.BRIDGE_CLIENT_ID)
        while self._running:
            try:
                self.run_cycle()
            except Exception as e:
                logger.error("Unhandled error in daemon cycle: %s", e)
            time.sleep(self.settings.POLL_INTERVAL_SECONDS)

    def stop(self):
        self._running = False
        logger.info("WAAST360 Bridge daemon stopped.")
