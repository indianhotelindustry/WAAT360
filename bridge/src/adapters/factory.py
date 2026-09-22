import logging

from src.adapters.base import TallyAdapter
from src.adapters.json_adapter import TallyJsonAdapter
from src.adapters.xml_adapter import TallyXmlAdapter

logger = logging.getLogger("waast_bridge.adapters")


def get_tally_adapter(
    host: str = "127.0.0.1",
    port: int = 9000,
    prefer_json: bool = True,
    timeout_seconds: float = 10.0,
) -> TallyAdapter:
    """
    Factory function to select and instantiate the appropriate TallyAdapter.
    Prefers TallyJsonAdapter if Tally supports native JSON (TallyPrime 7.0+),
    otherwise gracefully falls back to TallyXmlAdapter.
    """
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
