import logging
import os

from src.adapters.base import TallyAdapter
from src.adapters.json_adapter import TallyJsonAdapter
from src.adapters.simulated_adapter import TallySimulatedAdapter
from src.adapters.xml_adapter import TallyXmlAdapter

logger = logging.getLogger("waast_bridge.adapters")


def get_tally_adapter(
    host: str = "127.0.0.1",
    port: int = 9000,
    prefer_json: bool = True,
    timeout_seconds: float = 10.0,
    use_simulated: bool = False,
) -> TallyAdapter:
    """
    Factory function to select and instantiate the appropriate TallyAdapter.
    - If use_simulated or SIMULATED_TALLY=true, returns TallySimulatedAdapter for dev/testing.
    - Prefers TallyJsonAdapter if Tally supports native JSON (TallyPrime 7.0+).
    - Gracefully falls back to TallyXmlAdapter for standard compatibility.
    """
    if use_simulated or os.environ.get("SIMULATED_TALLY", "").lower() in ("true", "1", "yes"):
        logger.info("Using TallySimulatedAdapter (simulated Indian GST accounting state).")
        return TallySimulatedAdapter(host=host, port=port, timeout_seconds=timeout_seconds)

    if prefer_json:
        json_adapter = TallyJsonAdapter(host=host, port=port, timeout_seconds=timeout_seconds)
        try:
            status = json_adapter.get_tally_status()
            if status.is_online and status.capabilities.supports_json:
                logger.info("Tally JSON support detected. Using TallyJsonAdapter.")
                return json_adapter
        except Exception:
            logger.debug("Tally JSON detection failed. Falling back to TallyXmlAdapter.")

    logger.info("Using standard TallyXmlAdapter.")
    return TallyXmlAdapter(host=host, port=port, timeout_seconds=timeout_seconds)
