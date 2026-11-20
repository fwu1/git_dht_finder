"""
=============================================================================
DHT Core Engine (BEP 5 + BEP 32 IPv6 + BEP 14 LSD)
Pure Python BitTorrent Mainline DHT Peer & IP Discovery Implementation.
Zero external third-party dependencies (100% Python Standard Library).
=============================================================================
"""

import hashlib
import json
import os
import random
import re
import socket
import struct
import sys
import threading
import time

BOOTSTRAP_NODES = [
    ("router.bittorrent.com", 6881),
    ("dht.transmissionbt.com", 6881),
    ("dht.libtorrent.org", 25401),
    ("router.utorrent.com", 6881),
    ("router.silotis.us", 6881),
]


# ================= 1. Bencode / Bdecode =================

def bencode(obj):
    """Serialize Python data structures into BitTorrent Bencode format."""
    if isinstance(obj, int):
        return f"i{obj}e".encode("ascii")
    elif isinstance(obj, (bytes, bytearray)):
        return f"{len(obj)}:".encode("ascii") + bytes(obj)
    elif isinstance(obj, str):
        b = obj.encode("utf-8")
        return f"{len(b)}:".encode("ascii") + b
    elif isinstance(obj, list):
        return b"l" + b"".join(bencode(i) for i in obj) + b"e"
    elif isinstance(obj, dict):
        items = sorted([(k.encode("utf-8") if isinstance(k, str) else k, v) for k, v in obj.items()])
        return b"d" + b"".join(bencode(k) + bencode(v) for k, v in items) + b"e"
    raise TypeError(f"Bencode unsupported type: {type(obj)}")


def bdecode(data):
    """Parse BitTorrent Bencode binary data into Python objects."""
    def decode_next(idx):
        if idx >= len(data):
            raise ValueError("Truncated data")
        char = data[idx:idx + 1]
        if char == b"i":
            end = data.index(b"e", idx)
            return int(data[idx + 1:end]), end + 1
        elif char.isdigit():
            colon = data.index(b":", idx)
            length = int(data[idx:colon])
            start = colon + 1
            if start + length > len(data):
                raise ValueError("String out of bounds")
            return data[start:start + length], start + length
        elif char == b"l":
            idx += 1
            res = []
            while idx < len(data) and data[idx:idx + 1] != b"e":
                val, idx = decode_next(idx)
                res.append(val)
            return res, idx + 1
        elif char == b"d":
            idx += 1
            res = {}
            while idx < len(data) and data[idx:idx + 1] != b"e":
                k, idx = decode_next(idx)
                v, idx = decode_next(idx)
                res[k] = v
            return res, idx + 1
        raise ValueError("Invalid bencode format")

    val, _ = decode_next(0)
    return val


# ================= 2. Compact Structures Parser =================

def parse_compact_peers(values_list):
    """
    Parse compact peer addresses from DHT get_peers response.
    - IPv4: 6 bytes (4 bytes IP + 2 bytes Big-Endian Port)
    - IPv6: 18 bytes (16 bytes IPv6 + 2 bytes Big-Endian Port)
    """
    peers = []
    for val in values_list:
        if not isinstance(val, (bytes, bytearray)):
            continue
        if len(val) == 6:
            ip = socket.inet_ntoa(val[:4])
            port = struct.unpack(">H", val[4:6])[0]
            if ip not in ("0.0.0.0", "255.255.255.255") and 0 < port <= 65535:
                peers.append((ip, port))
        elif len(val) == 18:
            try:
                ip = socket.inet_ntop(socket.AF_INET6, val[:16])
                port = struct.unpack(">H", val[16:18])[0]
                if 0 < port <= 65535 and ip not in ("::", "::1") and not ip.startswith("fe80:"):
                    peers.append((ip, port))
            except Exception:
                pass
    return peers


def parse_compact_nodes(nodes_bytes):
    """Parse 26-byte compact IPv4 nodes (20B NodeID + 4B IP + 2B Port, BEP 5)."""
    nodes = []
    if not isinstance(nodes_bytes, (bytes, bytearray)):
        return nodes
    for i in range(0, len(nodes_bytes), 26):
        if i + 26 <= len(nodes_bytes):
            nid = nodes_bytes[i:i + 20]
            raw_ip = nodes_bytes[i + 20:i + 24]
            ip = socket.inet_ntoa(raw_ip)
            port = struct.unpack(">H", nodes_bytes[i + 24:i + 26])[0]
            if ip not in ("0.0.0.0", "255.255.255.255") and 0 < port <= 65535:
                nodes.append((nid, ip, port))
    return nodes


def parse_compact_nodes6(nodes_bytes):
    """Parse 38-byte compact IPv6 nodes (20B NodeID + 16B IPv6 + 2B Port, BEP 32)."""
    nodes = []
    if not isinstance(nodes_bytes, (bytes, bytearray)):
        return nodes
    for i in range(0, len(nodes_bytes), 38):
        if i + 38 <= len(nodes_bytes):
            nid = nodes_bytes[i:i + 20]
            raw_ip = nodes_bytes[i + 20:i + 36]
            try:
                ip = socket.inet_ntop(socket.AF_INET6, raw_ip)
                port = struct.unpack(">H", nodes_bytes[i + 36:i + 38])[0]
                if 0 < port <= 65535 and ip not in ("::", "::1") and not ip.startswith("fe80:"):
                    nodes.append((nid, ip, port))
            except Exception:
                continue
    return nodes


def normalize_addr(addr):
    """Strip IPv4-mapped IPv6 prefix (::ffff:) and return clean (ip, port)."""
    ip = str(addr[0])
    port = int(addr[1])
    if ip.startswith("::ffff:"):
        ip = ip[7:]
    return ip, port


def resolve_bootstrap_nodes(bootstrap_list, enable_ipv4=True, enable_ipv6=True):
    """Resolve DNS for DHT bootstrap routers into IPv4 and IPv6 address tuples."""
    resolved = []
    for host, port in bootstrap_list:
        try:
            for info in socket.getaddrinfo(host, port, socket.AF_UNSPEC, socket.SOCK_DGRAM):
                family, _, _, _, sockaddr = info
                ip = sockaddr[0]
                res_port = sockaddr[1]
                if enable_ipv6 and family == socket.AF_INET6:
                    if ip not in ("::", "::1") and not ip.startswith("fe80:"):
                        resolved.append((ip, res_port))
                elif enable_ipv4 and family == socket.AF_INET:
                    if ip not in ("0.0.0.0", "127.0.0.1", "255.255.255.255"):
                        resolved.append((ip, res_port))
        except Exception:
            continue
    return list(dict.fromkeys(resolved))


def create_dht_udp_socket(bind_port=None, broadcast=True, enable_ipv4=True, enable_ipv6=True):
    """Create UDP socket configured for IPv4, IPv6, or Dual-Stack."""
    if enable_ipv6:
        try:
            sock = socket.socket(socket.AF_INET6, socket.SOCK_DGRAM)
            v6only = 1 if not enable_ipv4 else 0
            sock.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, v6only)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            if broadcast:
                try:
                    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
                except Exception:
                    pass
            if bind_port is not None:
                sock.bind(("::", bind_port))
            return sock
        except Exception:
            if not enable_ipv4:
                raise

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    if broadcast:
        try:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        except Exception:
            pass
    if bind_port is not None:
        sock.bind(("0.0.0.0", bind_port))
    return sock


def safe_sendto(sock, data: bytes, target: tuple, enable_ipv4=True, enable_ipv6=True) -> bool:
    """Safely transmit UDP datagrams respecting network stack and IPv4-mapped address format."""
    try:
        host, port = target[0], target[1]
        if not host or host in ("0.0.0.0", "::") or port <= 0 or port > 65535:
            return False

        is_v6 = ":" in host
        if is_v6 and not enable_ipv6:
            return False
        if not is_v6 and not enable_ipv4:
            return False

        if sock.family == socket.AF_INET6:
            if not is_v6:
                try:
                    if sock.getsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY) != 0:
                        return False
                except Exception:
                    pass
                dest = (f"::ffff:{host}", port)
            else:
                dest = (host, port)
        else:
            if is_v6:
                return False
            dest = (host, port)

        sock.sendto(data, dest)
        return True
    except Exception:
        return False


def parse_target_hash(input_text: str) -> tuple[bytes, str]:
    """
    Parse user input into 20-byte InfoHash.
    Supports:
    1. 40-character Hexadecimal string
    2. Magnet URI (xt=urn:btih:<hash>)
    3. Plain text / Service name (auto-computes SHA1)
    """
    text = input_text.strip()
    if not text:
        raise ValueError("Target hash input cannot be empty.")

    # Magnet link check
    if text.startswith("magnet:"):
        match = re.search(r"xt=urn:btih:([a-zA-Z0-9]{32,40})", text, re.IGNORECASE)
        if match:
            raw_hash = match.group(1)
            if len(raw_hash) == 40:
                return bytes.fromhex(raw_hash), raw_hash.lower()
            elif len(raw_hash) == 32:
                import base64
                decoded = base64.b32decode(raw_hash.upper())
                return decoded, decoded.hex().lower()

    # 40-char Hex check
    if len(text) == 40:
        try:
            h_bytes = bytes.fromhex(text)
            return h_bytes, text.lower()
        except ValueError:
            pass

    # 32-char Base32 check
    if len(text) == 32:
        try:
            import base64
            h_bytes = base64.b32decode(text.upper())
            return h_bytes, h_bytes.hex().lower()
        except Exception:
            pass

    # Fallback: Plain text / Service name identifier -> compute SHA1
    h_bytes = hashlib.sha1(text.encode("utf-8")).digest()
    return h_bytes, h_bytes.hex().lower()


def ping_peer(ip: str, port: int, timeout: float = 2.0) -> tuple[bool, float, str]:
    """
    Test socket connectivity and measure round-trip latency to a discovered peer.
    Returns: (is_reachable, latency_ms, status_str)
    """
    start_t = time.time()
    try:
        fam = socket.AF_INET6 if ":" in ip else socket.AF_INET
        sock = socket.socket(fam, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        sock.connect((ip, port))
        latency_ms = round((time.time() - start_t) * 1000, 1)
        sock.close()
        return True, latency_ms, "Connected (TCP)"
    except socket.timeout:
        return False, 0.0, "Timeout"
    except ConnectionRefusedError:
        latency_ms = round((time.time() - start_t) * 1000, 1)
        return True, latency_ms, "Port Closed (Host Alive)"
    except Exception as e:
        return False, 0.0, str(e)


# ================= 3. Asynchronous Discovery Engine =================

class DHTFinderEngine:
    """
    Multi-threaded BitTorrent Mainline DHT Peer Finder.
    Coordinates LSD local broadcast, bootstrap queries, and iterative Kademlia routing.
    """

    def __init__(self):
        self._running = False
        self._thread = None
        self._discovered_peers = set()
        self._queried_nodes = set()

    @property
    def is_running(self):
        return self._running

    def start_discovery(
        self,
        info_hash: bytes,
        enable_ipv4: bool = True,
        enable_ipv6: bool = True,
        enable_lsd: bool = True,
        timeout: float = 12.0,
        candidate_ports: list = None,
        on_log=None,
        on_peer=None,
        on_done=None,
    ):
        """Start discovery in background daemon thread."""
        if self._running:
            return False

        self._running = True
        self._discovered_peers.clear()
        self._queried_nodes.clear()

        def _worker():
            start_time = time.time()
            my_id = os.urandom(20)

            def log(msg, level="INFO"):
                if on_log:
                    on_log(msg, level)

            log(f"Starting DHT Discovery for InfoHash: {info_hash.hex()}", "SYS")
            log(f"Stack configuration: IPv4={enable_ipv4}, IPv6={enable_ipv6}, LSD={enable_lsd}", "SYS")

            wants = []
            if enable_ipv4:
                wants.append(b"n4")
            if enable_ipv6:
                wants.append(b"n6")

            try:
                sock = create_dht_udp_socket(broadcast=True, enable_ipv4=enable_ipv4, enable_ipv6=enable_ipv6)
                sock.settimeout(0.7)
            except Exception as e:
                log(f"Socket initialization failed: {e}", "ERR")
                self._running = False
                if on_done:
                    on_done(0, 0.0)
                return

            ports_to_probe = set(candidate_ports or [6881, 19998, 19999, 51413])

            try:
                # 1. Local Service Discovery (BEP 14)
                if enable_lsd:
                    log("Sending Local Service Discovery (LSD) broadcast probe...", "LSD")
                    lsd_msg = {
                        "t": b"lsd0",
                        "y": b"q",
                        "q": b"get_peers",
                        "a": {"id": my_id, "info_hash": info_hash, "want": wants},
                    }
                    encoded_lsd = bencode(lsd_msg)
                    for port in ports_to_probe:
                        if enable_ipv4:
                            safe_sendto(sock, encoded_lsd, ("255.255.255.255", port), enable_ipv4, enable_ipv6)
                            safe_sendto(sock, encoded_lsd, ("127.0.0.1", port), enable_ipv4, enable_ipv6)
                        if enable_ipv6:
                            safe_sendto(sock, encoded_lsd, ("::1", port), enable_ipv4, enable_ipv6)
                            safe_sendto(sock, encoded_lsd, ("ff02::1", port), enable_ipv4, enable_ipv6)

                # 2. Resolve & Query Global Bootstrap Nodes
                log("Resolving global DHT bootstrap router nodes...", "SYS")
                bootstraps = resolve_bootstrap_nodes(BOOTSTRAP_NODES, enable_ipv4=enable_ipv4, enable_ipv6=enable_ipv6)
                log(f"Resolved {len(bootstraps)} global bootstrap endpoints. Sending initial get_peers...", "BOOT")

                for b_ip, b_port in bootstraps:
                    if not self._running:
                        break
                    query_msg = {
                        "t": b"c0",
                        "y": b"q",
                        "q": b"get_peers",
                        "a": {"id": my_id, "info_hash": info_hash, "want": wants},
                    }
                    safe_sendto(sock, bencode(query_msg), (b_ip, b_port), enable_ipv4, enable_ipv6)

                # 3. Iterative UDP Listening Loop
                while self._running and (time.time() - start_time < timeout):
                    try:
                        data, raw_addr = sock.recvfrom(4096)
                        sender_ip, sender_port = normalize_addr(raw_addr)

                        try:
                            msg = bdecode(data)
                        except Exception:
                            continue

                        r = msg.get(b"r", {})
                        if not r or not isinstance(r, dict):
                            continue

                        # Check for matching target peers
                        values = r.get(b"values", [])
                        if values:
                            found_in_msg = parse_compact_peers(values)
                            for p_ip, p_port in found_in_msg:
                                is_v6 = ":" in p_ip
                                if is_v6 and not enable_ipv6:
                                    continue
                                if not is_v6 and not enable_ipv4:
                                    continue

                                peer_tuple = (p_ip, p_port)
                                if peer_tuple not in self._discovered_peers:
                                    self._discovered_peers.add(peer_tuple)
                                    log(f"🎯 Discovered Peer IP: {p_ip}:{p_port} from {sender_ip}", "PEER")
                                    if on_peer:
                                        on_peer(p_ip, p_port, is_v6)

                        # Parse closer Kademlia routing nodes
                        new_nodes = []
                        if enable_ipv4:
                            nodes_bytes = r.get(b"nodes", b"")
                            if nodes_bytes:
                                new_nodes.extend(parse_compact_nodes(nodes_bytes))
                        if enable_ipv6:
                            nodes6_bytes = r.get(b"nodes6", b"")
                            if nodes6_bytes:
                                new_nodes.extend(parse_compact_nodes6(nodes6_bytes))

                        for _, nip, nport in new_nodes:
                            target = (nip, nport)
                            if target not in self._queried_nodes and len(self._queried_nodes) < 120:
                                self._queried_nodes.add(target)
                                iter_msg = {
                                    "t": b"c1",
                                    "y": b"q",
                                    "q": b"get_peers",
                                    "a": {"id": my_id, "info_hash": info_hash, "want": wants},
                                }
                                safe_sendto(sock, bencode(iter_msg), target, enable_ipv4, enable_ipv6)

                    except socket.timeout:
                        continue
                    except Exception as e:
                        pass

            finally:
                sock.close()
                self._running = False
                elapsed = round(time.time() - start_time, 2)
                log(f"Discovery completed in {elapsed}s. Total Peers Found: {len(self._discovered_peers)}", "DONE")
                if on_done:
                    on_done(len(self._discovered_peers), elapsed)

        self._thread = threading.Thread(target=_worker, daemon=True)
        self._thread.start()
        return True

    def stop(self):
        """Signal engine to stop immediately."""
        self._running = False
