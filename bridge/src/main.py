import argparse
import os
import sys

# Ensure bridge root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


from src.adapters.factory import get_tally_adapter
from src.config import bridge_settings
from src.daemon import BridgeDaemon
from src.store.local_store import BridgeLocalStore
from src.transport.polling import PollingTransport


def cmd_test_tally(args):
    print(f"Testing Tally connectivity at http://{args.host}:{args.port}...")
    adapter = get_tally_adapter(
        host=args.host,
        port=args.port,
        prefer_json=not args.force_xml,
        use_simulated=args.simulated,
    )
    status = adapter.get_tally_status()
    print("\n--- TALLY STATUS ---")
    print(f"Online: {status.is_online}")
    print(f"Version: {status.tally_version}")
    print(f"Response Time: {status.response_time_ms} ms")
    if status.error_message:
        print(f"Error: {status.error_message}")
    print("\n--- CAPABILITIES ---")
    for k, v in status.capabilities.model_dump().items():
        print(f"  {k}: {v}")
    return 0 if status.is_online else 1


def cmd_discover(args):
    print(f"Querying companies from Tally at http://{args.host}:{args.port}...")
    adapter = get_tally_adapter(
        host=args.host,
        port=args.port,
        prefer_json=not args.force_xml,
        use_simulated=args.simulated,
    )
    companies = adapter.get_companies()
    print(f"\nDiscovered {len(companies)} company/companies in Tally:")
    for c in companies:
        print(
            f"  - Name: {c.name} | GUID: {c.guid or 'N/A'} | FY: {c.financial_year_from or 'N/A'}"
        )

    if companies:
        print(
            f"\nSynchronizing discovered companies with WAAST360 Cloud API ({bridge_settings.CLOUD_URL})..."
        )
        try:
            transport = PollingTransport(
                cloud_url=bridge_settings.CLOUD_URL,
                bridge_client_id=bridge_settings.BRIDGE_CLIENT_ID,
                api_key=bridge_settings.BRIDGE_API_KEY,
            )
            res = transport.report_companies(companies)
            print(
                f"Cloud Synchronization Status: {res.get('status')} ({res.get('companies_recorded')} companies recorded)"
            )
        except Exception as e:
            print(f"Note: Cloud synchronization skipped or failed ({e})")
    return 0


def cmd_status(args):
    store = BridgeLocalStore()
    health = store.get_last_tally_health()
    pending = store.get_pending_jobs()
    print("--- WAAST360 BRIDGE LOCAL STATUS ---")
    print(f"Last Tally Health: {health}")
    print(f"Pending Local Jobs: {len(pending)}")
    return 0


def cmd_start(args):
    daemon = BridgeDaemon(use_simulated=args.simulated)
    try:
        daemon.start()
    except KeyboardInterrupt:
        daemon.stop()
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="WAAST360 Bridge — Local Integration Agent for TallyPrime"
    )
    subparsers = parser.add_subparsers(dest="command", help="Bridge commands")

    # start
    p_start = subparsers.add_parser("start", help="Start the Bridge daemon loop")
    p_start.add_argument(
        "--simulated",
        action="store_true",
        help="Run against simulated TallyAdapter (for dev & demonstration)",
    )

    # test-tally
    p_test = subparsers.add_parser("test-tally", help="Test local Tally connection & capabilities")
    p_test.add_argument(
        "--host",
        default=bridge_settings.TALLY_HOST,
        help="Tally host (default 127.0.0.1)",
    )
    p_test.add_argument(
        "--port",
        type=int,
        default=bridge_settings.TALLY_PORT,
        help="Tally port (default 9000)",
    )
    p_test.add_argument("--force-xml", action="store_true", help="Force XML adapter")
    p_test.add_argument(
        "--simulated",
        action="store_true",
        help="Use simulated Tally adapter (for dev & demonstration)",
    )

    # discover
    p_disc = subparsers.add_parser("discover", help="Discover companies in Tally")
    p_disc.add_argument(
        "--host",
        default=bridge_settings.TALLY_HOST,
        help="Tally host (default 127.0.0.1)",
    )
    p_disc.add_argument(
        "--port",
        type=int,
        default=bridge_settings.TALLY_PORT,
        help="Tally port (default 9000)",
    )
    p_disc.add_argument("--force-xml", action="store_true", help="Force XML adapter")
    p_disc.add_argument(
        "--simulated",
        action="store_true",
        help="Use simulated Tally adapter (for dev & demonstration)",
    )

    # status
    subparsers.add_parser("status", help="Show local queue and diagnostic stats")

    args = parser.parse_args(argv)

    if args.command == "start":
        return cmd_start(args)
    elif args.command == "test-tally":
        return cmd_test_tally(args)
    elif args.command == "discover":
        return cmd_discover(args)
    elif args.command == "status":
        return cmd_status(args)
    else:
        # Default behavior without arguments
        print("WAAST360 Bridge initialized. Use --help for command line usage.")
        return 0


if __name__ == "__main__":
    sys.exit(main())
