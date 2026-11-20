# DHT Peer Finder

A lightweight, standalone desktop utility written in pure Python for discovering active network peer IP addresses corresponding to any BitTorrent DHT infohash.

This project extracts the core peer-discovery logic from decentralized DHT nodes, providing a clean graphical user interface (GUI) and CLI tool without requiring any C++ compilation or third-party package dependencies.

---

## Highlights

- **Pure Python Architecture**: Built entirely on the standard Python library (`socket`, `struct`, `threading`, `tkinter`). No `pip install` required.
- **Dual-Stack Networking**: Fully supports IPv4 (BEP 5) and IPv6 (BEP 32) DHT queries simultaneously.
- **Local Service Discovery (LSD)**: Incorporates BEP 14 multicast and broadcast to detect local network nodes immediately.
- **Interactive GUI**: Modern, responsive dark-themed dashboard built with Tkinter and TTK.
- **Reachability Verification**: Built-in concurrent socket probing to test peer response latency.
- **Flexible Input Formats**: Accepts 40-character hexadecimal infohashes, magnet links, or custom service identifier strings (hashed via SHA-1).
- **Data Export**: Easily export discovered IP endpoints to JSON or CSV files or copy to clipboard.

---

## File Structure

```text
git_dht_finder/
├── main.py              # Application entrypoint (launches GUI or CLI)
├── gui.py               # Tkinter desktop interface implementation
├── dht_core.py          # Bencode, UDP socket management, and DHT get_peers engine
├── requirements.txt     # Environment specifications (Python standard library)
├── run.bat              # One-click Windows startup batch script
└── README.md            # Project documentation and guide
```

---

## Getting Started

### Prerequisites

- Python 3.8 or higher installed on Windows, macOS, or Linux.

### Running the Application

1. **Launch the Graphical Interface**:
   ```bash
   python main.py
   ```
   *(On Windows, you can also double-click `run.bat`)*

2. **Run in Headless CLI Mode**:
   ```bash
   python main.py --hash "7acf8fb590b2060dd9c3146ef770169d593433b0" --timeout 10
   ```

---

## How It Works

1. **Hash Resolution**: The input target is parsed into a canonical 20-byte infohash binary representation.
2. **Local Broadcast (LSD)**: The engine broadcasts discovery datagrams over the local subnet to detect immediate neighborhood peers.
3. **Bootstrap Discovery**: Public root routers (`router.bittorrent.com`, `dht.transmissionbt.com`, etc.) are resolved across IPv4 and IPv6 to obtain initial routing candidate nodes.
4. **Iterative Kademlia Walk**: The engine dispatches `get_peers` queries, collects compact peer lists (`values`), and iteratively explores closer nodes until the search timeout completes.
5. **Interactive Inspection**: The discovered peer IP addresses and ports populate the GUI table in real time.

---

## License

This software is released under the MIT Open Source License.
