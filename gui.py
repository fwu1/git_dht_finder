"""
=============================================================================
DHT Peer Finder - GUI Module
Modern, responsive Tkinter desktop interface for BitTorrent DHT peer discovery.
Zero external dependencies (pure Python standard library).
=============================================================================
"""

import concurrent.futures
import csv
import json
import os
import sys
import threading
import time
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, scrolledtext

import dht_core

# Sample preset infohashes for quick user testing
PRESETS = {
    "Debian 13 NetInst (Verified Active)": "7acf8fb590b2060dd9c3146ef770169d593433b0",
    "DHC Cloud Service Node": "dhc.platform.service.v1:ip_manager",
    "Ubuntu 24.04 Desktop ISO": "e7b0ecda51a37a93a10526e0e0ab70b8a361bc9b",
    "Arch Linux ISO": "99352e0be38ff401e405a8f4c24719299723ecbe",
}


class DHTFinderGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("DHT Peer Finder - BitTorrent DHT Peer & IP Discovery")
        self.geometry("960x700")
        self.minsize(800, 560)

        # Application state
        self.engine = dht_core.DHTFinderEngine()
        self.peers_data = {}  # { "ip:port": dict }
        self.peer_counter = 0

        # UI Variables
        self.var_hash_input = tk.StringVar(value=PRESETS["Debian 13 NetInst (Verified Active)"])
        self.var_ipv4 = tk.BooleanVar(value=True)
        self.var_ipv6 = tk.BooleanVar(value=True)
        self.var_lsd = tk.BooleanVar(value=True)
        self.var_timeout = tk.IntVar(value=10)
        self.var_status_text = tk.StringVar(value="Ready. Enter a target InfoHash to start discovering peer IPs.")
        self.var_peers_count = tk.StringVar(value="Peers Found: 0")

        self._init_theme()
        self._build_widgets()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _init_theme(self):
        """Configure modern dark slate theme for ttk widgets."""
        self.configure(bg="#0f172a")

        self.style = ttk.Style(self)
        try:
            self.style.theme_use("clam")
        except Exception:
            pass

        # Global styles
        self.style.configure(".", background="#0f172a", foreground="#f8fafc", font=("Segoe UI", 9))
        self.style.configure("TFrame", background="#0f172a")
        self.style.configure("Card.TFrame", background="#1e293b", relief="flat")
        self.style.configure("TLabelframe", background="#1e293b", foreground="#38bdf8", bordercolor="#334155")
        self.style.configure("TLabelframe.Label", background="#1e293b", foreground="#38bdf8", font=("Segoe UI", 9, "bold"))

        # Buttons
        self.style.configure("TButton", font=("Segoe UI", 9), padding=(8, 4), borderwidth=0)
        self.style.configure("Primary.TButton", background="#0284c7", foreground="#ffffff", font=("Segoe UI", 9, "bold"))
        self.style.map("Primary.TButton", background=[("active", "#0369a1"), ("disabled", "#334155")])

        self.style.configure("Danger.TButton", background="#dc2626", foreground="#ffffff", font=("Segoe UI", 9, "bold"))
        self.style.map("Danger.TButton", background=[("active", "#b91c1c"), ("disabled", "#334155")])

        self.style.configure("Accent.TButton", background="#d97706", foreground="#ffffff", font=("Segoe UI", 9, "bold"))
        self.style.map("Accent.TButton", background=[("active", "#b45309"), ("disabled", "#334155")])

        self.style.configure("Secondary.TButton", background="#334155", foreground="#f8fafc")
        self.style.map("Secondary.TButton", background=[("active", "#475569")])

        # Treeview styling
        self.style.configure(
            "Treeview",
            background="#090d16",
            foreground="#f8fafc",
            fieldbackground="#090d16",
            rowheight=26,
            font=("Consolas", 9),
            borderwidth=0,
        )
        self.style.configure("Treeview.Heading", background="#1e293b", foreground="#38bdf8", font=("Segoe UI", 9, "bold"))
        self.style.map("Treeview", background=[("selected", "#0284c7")], foreground=[("selected", "#ffffff")])

        # Notebook tabs
        self.style.configure("TNotebook", background="#0f172a", borderwidth=0)
        self.style.configure("TNotebook.Tab", background="#1e293b", foreground="#94a3b8", padding=(12, 5), font=("Segoe UI", 9))
        self.style.map("TNotebook.Tab", background=[("selected", "#0284c7")], foreground=[("selected", "#ffffff")])

    def _build_widgets(self):
        """Construct user interface layout."""
        # 1. Header banner
        header = tk.Frame(self, bg="#1e293b", height=56)
        header.pack(fill=tk.X, side=tk.TOP)

        title_lbl = tk.Label(
            header,
            text="🌐 DHT Peer Finder",
            font=("Segoe UI", 15, "bold"),
            bg="#1e293b",
            fg="#38bdf8",
        )
        title_lbl.pack(side=tk.LEFT, padx=16, pady=(8, 2))

        sub_lbl = tk.Label(
            header,
            text="BitTorrent Mainline DHT Peer & IP Address Discovery (BEP 5 / BEP 32 IPv6 / BEP 14 LSD)",
            font=("Segoe UI", 9),
            bg="#1e293b",
            fg="#94a3b8",
        )
        sub_lbl.pack(side=tk.LEFT, padx=(4, 0), pady=(12, 0))

        # 2. Main container
        main_box = tk.Frame(self, bg="#0f172a", padx=14, pady=10)
        main_box.pack(fill=tk.BOTH, expand=True)

        # 2.1 Input card
        input_card = ttk.LabelFrame(main_box, text=" 🎯 Target InfoHash & Discovery Configuration ", padding=10)
        input_card.pack(fill=tk.X, pady=(0, 10))

        # Row 1: Target Hash Entry
        r1 = tk.Frame(input_card, bg="#1e293b")
        r1.pack(fill=tk.X, pady=(0, 6))

        tk.Label(r1, text="Target InfoHash:", font=("Segoe UI", 9, "bold"), bg="#1e293b", fg="#f8fafc").pack(side=tk.LEFT, padx=(0, 8))
        self.entry_hash = tk.Entry(
            r1,
            textvariable=self.var_hash_input,
            font=("Consolas", 10),
            bg="#090d16",
            fg="#38bdf8",
            insertbackground="#ffffff",
            relief="solid",
            bd=1,
        )
        self.entry_hash.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8))

        # Preset Dropdown
        self.combo_preset = ttk.Combobox(r1, values=list(PRESETS.keys()), state="readonly", width=28)
        self.combo_preset.set("Load Sample Preset...")
        self.combo_preset.bind("<<ComboboxSelected>>", self._on_preset_selected)
        self.combo_preset.pack(side=tk.RIGHT)

        # Row 2: Options
        r2 = tk.Frame(input_card, bg="#1e293b")
        r2.pack(fill=tk.X, pady=(4, 6))

        tk.Label(r2, text="Network Stack:", font=("Segoe UI", 9, "bold"), bg="#1e293b", fg="#94a3b8").pack(side=tk.LEFT, padx=(0, 6))

        cb_v4 = tk.Checkbutton(
            r2,
            text="IPv4 DHT (BEP 5)",
            variable=self.var_ipv4,
            bg="#1e293b",
            fg="#f8fafc",
            selectcolor="#090d16",
            activebackground="#1e293b",
            activeforeground="#38bdf8",
        )
        cb_v4.pack(side=tk.LEFT, padx=6)

        cb_v6 = tk.Checkbutton(
            r2,
            text="IPv6 DHT (BEP 32)",
            variable=self.var_ipv6,
            bg="#1e293b",
            fg="#f8fafc",
            selectcolor="#090d16",
            activebackground="#1e293b",
            activeforeground="#38bdf8",
        )
        cb_v6.pack(side=tk.LEFT, padx=6)

        cb_lsd = tk.Checkbutton(
            r2,
            text="Local LSD Broadcast (BEP 14)",
            variable=self.var_lsd,
            bg="#1e293b",
            fg="#f8fafc",
            selectcolor="#090d16",
            activebackground="#1e293b",
            activeforeground="#38bdf8",
        )
        cb_lsd.pack(side=tk.LEFT, padx=6)

        tk.Label(r2, text="Timeout (s):", font=("Segoe UI", 9), bg="#1e293b", fg="#94a3b8").pack(side=tk.LEFT, padx=(16, 4))
        sp_timeout = tk.Spinbox(r2, from_=3, to=60, textvariable=self.var_timeout, width=4, bg="#090d16", fg="#f8fafc", bd=1)
        sp_timeout.pack(side=tk.LEFT)

        # Row 3: Action Buttons
        r3 = tk.Frame(input_card, bg="#1e293b")
        r3.pack(fill=tk.X, pady=(4, 0))

        self.btn_start = ttk.Button(r3, text="🔍 Start Discovery", style="Primary.TButton", command=self.on_start_discovery)
        self.btn_start.pack(side=tk.LEFT, padx=(0, 6))

        self.btn_stop = ttk.Button(r3, text="⏹ Stop", style="Danger.TButton", state="disabled", command=self.on_stop_discovery)
        self.btn_stop.pack(side=tk.LEFT, padx=6)

        self.btn_ping = ttk.Button(r3, text="⚡ Ping All Peers", style="Accent.TButton", command=self.on_ping_all)
        self.btn_ping.pack(side=tk.LEFT, padx=6)

        btn_copy = ttk.Button(r3, text="📋 Copy Selected IP", style="Secondary.TButton", command=self.on_copy_selected)
        btn_copy.pack(side=tk.LEFT, padx=6)

        btn_export = ttk.Button(r3, text="💾 Export (JSON/CSV)", style="Secondary.TButton", command=self.on_export)
        btn_export.pack(side=tk.LEFT, padx=6)

        btn_clear = ttk.Button(r3, text="🗑️ Clear", style="Secondary.TButton", command=self.on_clear)
        btn_clear.pack(side=tk.RIGHT)

        # 2.2 Content Notebook (Peers Table & Live Logs)
        self.notebook = ttk.Notebook(main_box)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        # Tab 1: Peers Table
        tab_peers = tk.Frame(self.notebook, bg="#0f172a")
        self.notebook.add(tab_peers, text="  🎯 Discovered Peer IPs  ")

        tree_frame = tk.Frame(tab_peers, bg="#090d16")
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=2, pady=4)

        columns = ("idx", "ip", "port", "stack", "first_seen", "latency")
        self.tree = ttk.Treeview(tree_frame, columns=columns, show="headings", selectmode="browse")

        self.tree.heading("idx", text="#", anchor=tk.CENTER)
        self.tree.heading("ip", text="IP Address", anchor=tk.W)
        self.tree.heading("port", text="Port", anchor=tk.CENTER)
        self.tree.heading("stack", text="Protocol Stack", anchor=tk.CENTER)
        self.tree.heading("first_seen", text="First Discovered", anchor=tk.CENTER)
        self.tree.heading("latency", text="Ping / Reachability", anchor=tk.W)

        self.tree.column("idx", width=45, minwidth=40, anchor=tk.CENTER)
        self.tree.column("ip", width=260, minwidth=180, anchor=tk.W)
        self.tree.column("port", width=80, minwidth=60, anchor=tk.CENTER)
        self.tree.column("stack", width=120, minwidth=90, anchor=tk.CENTER)
        self.tree.column("first_seen", width=120, minwidth=90, anchor=tk.CENTER)
        self.tree.column("latency", width=220, minwidth=150, anchor=tk.W)

        scroll_y = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll_y.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll_y.pack(side=tk.RIGHT, fill=tk.Y)

        self.tree.bind("<Double-1>", self.on_double_click_peer)

        # Tab 2: Live Protocol Inspector
        tab_logs = tk.Frame(self.notebook, bg="#0f172a")
        self.notebook.add(tab_logs, text="  📜 Live Protocol Log  ")

        self.log_area = scrolledtext.ScrolledText(
            tab_logs,
            bg="#090d16",
            fg="#e2e8f0",
            insertbackground="#ffffff",
            font=("Consolas", 9),
            bd=0,
            padx=8,
            pady=8,
        )
        self.log_area.pack(fill=tk.BOTH, expand=True, padx=2, pady=4)

        # Log tag colors
        self.log_area.tag_config("SYS", foreground="#38bdf8")
        self.log_area.tag_config("BOOT", foreground="#c084fc")
        self.log_area.tag_config("LSD", foreground="#fbbf24")
        self.log_area.tag_config("PEER", foreground="#4ade80", font=("Consolas", 9, "bold"))
        self.log_area.tag_config("DONE", foreground="#60a5fa", font=("Consolas", 9, "bold"))
        self.log_area.tag_config("ERR", foreground="#f87171")

        # 3. Status Bar
        status_bar = tk.Frame(self, bg="#1e293b", height=28, padx=12)
        status_bar.pack(fill=tk.X, side=tk.BOTTOM)

        lbl_status = tk.Label(status_bar, textvariable=self.var_status_text, bg="#1e293b", fg="#94a3b8", font=("Segoe UI", 9))
        lbl_status.pack(side=tk.LEFT, pady=3)

        lbl_peers = tk.Label(status_bar, textvariable=self.var_peers_count, bg="#1e293b", fg="#38bdf8", font=("Segoe UI", 9, "bold"))
        lbl_peers.pack(side=tk.RIGHT, pady=3)

    # ================= Event Handlers =================

    def _on_preset_selected(self, event):
        selected_name = self.combo_preset.get()
        if selected_name in PRESETS:
            self.var_hash_input.set(PRESETS[selected_name])

    def append_log(self, message: str, level: str = "SYS"):
        """Thread-safe log output."""
        def _insert():
            timestamp = time.strftime("[%H:%M:%S] ")
            self.log_area.insert(tk.END, timestamp + message + "\n", level)
            self.log_area.see(tk.END)
        self.after(0, _insert)

    def on_start_discovery(self):
        """Parse hash and trigger discovery engine."""
        raw_input = self.var_hash_input.get().strip()
        if not raw_input:
            messagebox.showwarning("Warning", "Please provide a valid InfoHash, Magnet link, or Service name.")
            return

        try:
            h_bytes, h_hex = dht_core.parse_target_hash(raw_input)
        except Exception as e:
            messagebox.showerror("Invalid Hash", f"Failed to parse target hash: {e}")
            return

        want_v4 = self.var_ipv4.get()
        want_v6 = self.var_ipv6.get()
        if not want_v4 and not want_v6:
            messagebox.showwarning("Warning", "You must enable at least one protocol stack (IPv4 or IPv6).")
            return

        self.btn_start.configure(state="disabled")
        self.btn_stop.configure(state="normal")
        self.var_status_text.set(f"Discovering peers for [{h_hex[:16]}...]...")

        self.append_log(f"--- Starting new discovery session for InfoHash: {h_hex} ---", "SYS")

        def _on_peer(ip, port, is_v6):
            self.after(0, lambda: self._add_peer_to_table(ip, port, is_v6))

        def _on_done(count, elapsed):
            self.after(0, lambda: self._handle_discovery_done(count, elapsed))

        self.engine.start_discovery(
            info_hash=h_bytes,
            enable_ipv4=want_v4,
            enable_ipv6=want_v6,
            enable_lsd=self.var_lsd.get(),
            timeout=float(self.var_timeout.get()),
            on_log=self.append_log,
            on_peer=_on_peer,
            on_done=_on_done,
        )

    def on_stop_discovery(self):
        """Signal engine to stop."""
        self.engine.stop()
        self.var_status_text.set("Stopping discovery...")
        self.append_log("Stop requested by user.", "ERR")

    def _add_peer_to_table(self, ip: str, port: int, is_v6: bool):
        """Insert or update discovered peer in GUI table."""
        key = f"[{ip}]:{port}" if is_v6 else f"{ip}:{port}"
        if key in self.peers_data:
            return

        self.peer_counter += 1
        now_time = time.strftime("%H:%M:%S")
        stack_str = "IPv6 (BEP 32)" if is_v6 else "IPv4 (BEP 5)"

        self.peers_data[key] = {
            "idx": self.peer_counter,
            "ip": ip,
            "port": port,
            "stack": stack_str,
            "first_seen": now_time,
            "latency": "Discovered (Pending Ping)",
        }

        item_id = self.tree.insert(
            "",
            tk.END,
            iid=key,
            values=(self.peer_counter, ip, port, stack_str, now_time, "Discovered"),
        )
        self.tree.see(item_id)
        self.var_peers_count.set(f"Peers Found: {len(self.peers_data)}")

    def _handle_discovery_done(self, count: int, elapsed: float):
        """Reset button states when discovery finishes."""
        self.btn_start.configure(state="normal")
        self.btn_stop.configure(state="disabled")
        self.var_status_text.set(f"Finished. Found {count} active peers in {elapsed}s.")
        self.var_peers_count.set(f"Peers Found: {len(self.peers_data)}")

    def on_ping_all(self):
        """Concurrently ping all discovered peers to test reachability."""
        if not self.peers_data:
            messagebox.showinfo("Info", "No peers to ping. Discover peers first.")
            return

        self.btn_ping.configure(state="disabled")
        self.var_status_text.set("Probing peer reachability and measuring round-trip latency...")
        self.append_log(f"Starting concurrent ping for {len(self.peers_data)} peers...", "SYS")

        def _worker():
            with concurrent.futures.ThreadPoolExecutor(max_workers=16) as executor:
                futures = {}
                for key, info in self.peers_data.items():
                    fut = executor.submit(dht_core.ping_peer, info["ip"], info["port"])
                    futures[fut] = key

                for fut in concurrent.futures.as_completed(futures):
                    key = futures[fut]
                    try:
                        ok, lat_ms, status_str = fut.result()
                        if ok:
                            res_str = f"🟢 {lat_ms} ms ({status_str})"
                        else:
                            res_str = f"⚪ {status_str}"
                    except Exception as e:
                        res_str = f"🔴 Error: {e}"

                    self.peers_data[key]["latency"] = res_str
                    self.after(0, lambda k=key, r=res_str: self._update_row_latency(k, r))

            self.after(0, lambda: self.btn_ping.configure(state="normal"))
            self.after(0, lambda: self.var_status_text.set("Peer latency probe completed."))
            self.append_log("Peer latency probe finished.", "DONE")

        threading.Thread(target=_worker, daemon=True).start()

    def _update_row_latency(self, key: str, latency_str: str):
        if self.tree.exists(key):
            curr_vals = list(self.tree.item(key, "values"))
            if len(curr_vals) >= 6:
                curr_vals[5] = latency_str
                self.tree.item(key, values=curr_vals)

    def on_copy_selected(self):
        """Copy selected peer IP or IP:Port to clipboard."""
        selected = self.tree.selection()
        if not selected:
            messagebox.showinfo("Copy", "Please select a row first.")
            return

        key = selected[0]
        if key in self.peers_data:
            ip = self.peers_data[key]["ip"]
            self.clipboard_clear()
            self.clipboard_append(ip)
            self.var_status_text.set(f"Copied IP address to clipboard: {ip}")

    def on_double_click_peer(self, event):
        """Double click row to copy IP:Port."""
        self.on_copy_selected()

    def on_export(self):
        """Export discovered peers to JSON or CSV."""
        if not self.peers_data:
            messagebox.showinfo("Export", "No peers to export.")
            return

        file_path = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON files (*.json)", "*.json"), ("CSV files (*.csv)", "*.csv")],
            initialfile="dht_discovered_peers.json",
        )
        if not file_path:
            return

        try:
            if file_path.endswith(".csv"):
                with open(file_path, "w", newline="", encoding="utf-8") as f:
                    writer = csv.writer(f)
                    writer.writerow(["Index", "IP", "Port", "Protocol", "First Seen", "Latency/Status"])
                    for p in self.peers_data.values():
                        writer.writerow([p["idx"], p["ip"], p["port"], p["stack"], p["first_seen"], p["latency"]])
            else:
                with open(file_path, "w", encoding="utf-8") as f:
                    json.dump(list(self.peers_data.values()), f, indent=2, ensure_ascii=False)

            messagebox.showinfo("Export Success", f"Successfully exported {len(self.peers_data)} peers to:\n{file_path}")
        except Exception as e:
            messagebox.showerror("Export Error", f"Failed to export: {e}")

    def on_clear(self):
        """Clear table and reset counts."""
        self.tree.delete(*self.tree.get_children())
        self.peers_data.clear()
        self.peer_counter = 0
        self.var_peers_count.set("Peers Found: 0")
        self.log_area.delete("1.0", tk.END)
        self.var_status_text.set("Table and logs cleared.")

    def _on_close(self):
        """Gracefully terminate engine and close window."""
        self.engine.stop()
        self.destroy()


def run_app():
    app = DHTFinderGUI()
    app.mainloop()


if __name__ == "__main__":
    run_app()
