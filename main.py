"""
=============================================================================
DHT Peer Finder - Application Entrypoint
=============================================================================
Usage:
  GUI Mode (default):
    python main.py

  CLI Mode:
    python main.py --hash <info_hash_or_service_name> [--ipv4] [--ipv6] [--timeout 10]
=============================================================================
"""

import argparse
import sys
import time

import dht_core


def run_cli(args):
    """Headless CLI mode for searching DHT peers."""
    try:
        h_bytes, h_hex = dht_core.parse_target_hash(args.hash)
    except Exception as e:
        print(f"[Error] Failed to parse hash: {e}")
        sys.exit(1)

    print("=" * 65)
    print("🌐 DHT Peer Finder (BitTorrent Network Discovery - CLI)")
    print(f"Target InfoHash: {h_hex}")
    print(f"Stack: IPv4={args.ipv4}, IPv6={args.ipv6}, Timeout={args.timeout}s")
    print("=" * 65)

    engine = dht_core.DHTFinderEngine()
    found_peers = []

    def on_log(msg, level):
        print(f"[{level}] {msg}")

    def on_peer(ip, port, is_v6):
        proto = "IPv6" if is_v6 else "IPv4"
        print(f"\n🎯 [FOUND PEER] {ip}:{port} ({proto})")
        found_peers.append((ip, port))

    def on_done(count, elapsed):
        print("\n" + "=" * 65)
        print(f"Discovery complete in {elapsed}s. Total Peers: {count}")
        print("=" * 65)

    engine.start_discovery(
        info_hash=h_bytes,
        enable_ipv4=args.ipv4,
        enable_ipv6=args.ipv6,
        enable_lsd=not args.no_lsd,
        timeout=args.timeout,
        on_log=on_log,
        on_peer=on_peer,
        on_done=on_done,
    )

    # Wait until finished
    while engine.is_running:
        time.sleep(0.5)


def main():
    parser = argparse.ArgumentParser(description="DHT Peer Finder - BitTorrent Mainline DHT Discovery Tool")
    parser.add_argument("--hash", type=str, help="Target 40-char Hex InfoHash, Magnet Link, or Service Name")
    parser.add_argument("--ipv4", action="store_true", default=True, help="Enable IPv4 DHT (default: True)")
    parser.add_argument("--ipv6", action="store_true", default=True, help="Enable IPv6 DHT (default: True)")
    parser.add_argument("--no-lsd", action="store_true", default=False, help="Disable Local Service Discovery (LSD)")
    parser.add_argument("--timeout", type=float, default=10.0, help="Search timeout in seconds (default: 10.0)")

    args = parser.parse_args()

    if args.hash:
        run_cli(args)
    else:
        # Launch modern GUI
        import gui
        gui.run_app()


if __name__ == "__main__":
    main()
