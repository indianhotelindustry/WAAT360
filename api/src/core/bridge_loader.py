import importlib.util
import sys
from pathlib import Path
from typing import Any

# Locate bridge/src directory
_BRIDGE_SRC = Path(__file__).resolve().parent.parent.parent.parent / "bridge" / "src"

_simulated_adapter_instance: Any = None


def get_simulated_adapter() -> Any:
    """
    Control 1 & Directive 12: Load and return the genuine TallySimulatedAdapter
    from the bridge subsystem without namespace collision with api.src.

    ARCHITECTURAL BOUNDARY:
    This loader is strictly an isolated development/demo testing seam.
    The production architecture connects WAAST360 Cloud to WAAST360 Bridge via
    outbound HTTPS polling over BridgeTransport (POST /attempts, POST /verification).
    The Cloud API does NOT have a production runtime dependency on the Windows Bridge package.
    """
    global _simulated_adapter_instance
    if _simulated_adapter_instance is not None:
        return _simulated_adapter_instance

    if not _BRIDGE_SRC.exists():
        raise RuntimeError(
            "Bridge source directory not found. TallySimulatedAdapter is an isolated "
            "development/demo seam and is only accessible when the repository contains "
            "the bridge/ package."
        )

    # Augment src.models to resolve capabilities & domain from bridge
    import src.models

    bridge_models_dir = str(_BRIDGE_SRC / "models")
    if bridge_models_dir not in src.models.__path__:
        src.models.__path__.append(bridge_models_dir)

    # Register src.adapters from bridge
    if "src.adapters" not in sys.modules:
        adapters_dir = _BRIDGE_SRC / "adapters"
        adapters_spec = importlib.util.spec_from_file_location(
            "src.adapters",
            adapters_dir / "__init__.py",
            submodule_search_locations=[str(adapters_dir)],
        )
        if adapters_spec and adapters_spec.loader:
            adapters_mod = importlib.util.module_from_spec(adapters_spec)
            sys.modules["src.adapters"] = adapters_mod
            adapters_spec.loader.exec_module(adapters_mod)

    from src.adapters.simulated_adapter import TallySimulatedAdapter

    _simulated_adapter_instance = TallySimulatedAdapter()
    return _simulated_adapter_instance


def get_simulated_adapter_class() -> Any:
    get_simulated_adapter()
    from src.adapters.simulated_adapter import TallySimulatedAdapter

    return TallySimulatedAdapter
