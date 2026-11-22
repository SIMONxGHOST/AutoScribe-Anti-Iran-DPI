# -*- coding: utf-8 -*-
"""
AutoScribe Lightweight AI, DPI Feedback & Auto-Pilot Engine (Zero External Dependencies)
v1.6.2:
- Enhanced NetworkProfiler (Local IP + Default Gateway + ARP MAC + Wi-Fi SSID/BSSID)
- Pre-flight SocketProber for fast port RST/Drop detection
- FailureClassifier (CLI status, WireGuard-NT log.bin, service logs, timing, L7/speed)
- Time-Decayed Hierarchical Thompson Sampling Bandit (SQLite)
- AutoPilotController (L1 Cold-Start -> L4 Escalation, dynamic timings, IP rotation)
"""

import ctypes
import hashlib
import math
import os
import platform
import random
import re
import socket
import sqlite3
import struct
import subprocess
import threading
import time

IS_WINDOWS = platform.system() == "Windows"


def _hidden_kwargs():
    if IS_WINDOWS:
        return {"creationflags": subprocess.CREATE_NO_WINDOW}
    return {}


# ---------------------------------------------------------------------------
# Failure / DPI Feedback Classes
# ---------------------------------------------------------------------------
ERR_NONE = "SUCCESS"
ERR_UDP_DROP = "UDP_DROP"
ERR_IMMEDIATE_DPI_RESET = "IMMEDIATE_DPI_RESET"
ERR_DELAYED_DPI_RESET = "DELAYED_DPI_RESET"
ERR_BLACKHOLED = "BLACKHOLED_TUNNEL"
ERR_L7_HTTP_BLOCK = "L7_HTTP_BLOCK"
ERR_THROTTLED = "THROTTLED"
ERR_PRO_OR_LOC = "PRO_OR_LOC_ERR"
ERR_TIMEOUT_GENERIC = "TIMEOUT_GENERIC"


# ---------------------------------------------------------------------------
# Anti-Censorship Strategy Profiles (Ordered by Escalation Level)
# ---------------------------------------------------------------------------
STRATEGY_ORDER = [
    "L1_DIRECT",
    "L2_TLS_OBFUSCATION",
    "L3_PORT_HOPPING",
    "L4_DEEP_TUNNEL",
]

ANTI_CENSORSHIP_PROFILES = {
    "L1_DIRECT": {
        "label": "Direct / Low-Latency (WireGuard & UDP)",
        "protos": {"wireguard": {443, 53, 123, 80}, "udp": {443, 53}},
        "timeout": 20,
        "hold_seconds": 8,
    },
    "L2_TLS_OBFUSCATION": {
        "label": "TLS Obfuscation (Stealth & TCP on 443/8443/80)",
        "protos": {"stealth": {443, 8443, 80}, "tcp": {443, 80}},
        "timeout": 28,
        "hold_seconds": 12,
    },
    "L3_PORT_HOPPING": {
        "label": "Port-Hopping (Stealth & TCP on 587/22/8080/21)",
        "protos": {"stealth": {587, 22, 8080, 21, 143}, "tcp": {587, 22, 8080, 21}},
        "timeout": 30,
        "hold_seconds": 15,
    },
    "L4_DEEP_TUNNEL": {
        "label": "Deep Tunnel / WebSocket (WStunnel & Fallback Stealth)",
        "protos": {"wstunnel": {443}, "stealth": {443, 8443, 8080}},
        "timeout": 35,
        "hold_seconds": 18,
    },
}


class NetworkProfiler:
    """
    Computes a privacy-preserving local network fingerprint using:
    - Local outbound interface IP
    - Default gateway IP & gateway MAC (distinguishes different routers/hotspots sharing 192.168.1.x)
    - Wi-Fi SSID/BSSID when available
    """

    @staticmethod
    def _run_quick(cmd, timeout=0.8):
        try:
            res = subprocess.run(
                cmd, capture_output=True, text=True, encoding="utf-8",
                errors="replace", timeout=timeout, **_hidden_kwargs()
            )
            return res.stdout or ""
        except Exception:
            return ""

    @classmethod
    def _windows_net_details(cls):
        details = []
        # Default gateway from `route print 0.0.0.0`
        route_out = cls._run_quick(["route", "print", "0.0.0.0"])
        m_gw = re.search(r"0\.0\.0\.0\s+0\.0\.0\.0\s+(\d+\.\d+\.\d+\.\d+)", route_out)
        if m_gw:
            gw_ip = m_gw.group(1)
            details.append(f"gw:{gw_ip}")
            arp_out = cls._run_quick(["arp", "-a", gw_ip])
            m_mac = re.search(r"([0-9a-fA-F]{2}(?:-[0-9a-fA-F]{2}){5})", arp_out)
            if m_mac:
                details.append(f"mac:{m_mac.group(1).lower()}")

        # Wi-Fi SSID / BSSID
        wlan_out = cls._run_quick(["netsh", "wlan", "show", "interfaces"])
        m_bssid = re.search(r"BSSID\s*:\s*([0-9a-fA-F:]{17})", wlan_out, re.IGNORECASE)
        if m_bssid:
            details.append(f"bssid:{m_bssid.group(1).lower()}")
        else:
            m_ssid = re.search(r"^\s*SSID\s*:\s*(.+)$", wlan_out, re.MULTILINE | re.IGNORECASE)
            if m_ssid:
                details.append(f"ssid:{m_ssid.group(1).strip()}")
        return details

    @classmethod
    def _posix_net_details(cls):
        details = []
        if platform.system() == "Darwin":
            route_out = cls._run_quick(["route", "-n", "get", "default"])
            m_gw = re.search(r"gateway:\s*(\S+)", route_out)
            if m_gw:
                gw_ip = m_gw.group(1)
                details.append(f"gw:{gw_ip}")
                arp_out = cls._run_quick(["arp", "-n", gw_ip])
                m_mac = re.search(r"([0-9a-fA-F]{1,2}(?::[0-9a-fA-F]{1,2}){5})", arp_out)
                if m_mac:
                    details.append(f"mac:{m_mac.group(1).lower()}")
            return details

        ip_out = cls._run_quick(["ip", "route", "show", "default"])
        m_gw = re.search(r"default via (\S+)", ip_out)
        if m_gw:
            gw_ip = m_gw.group(1)
            details.append(f"gw:{gw_ip}")
            try:
                with open("/proc/net/arp", "r", encoding="utf-8", errors="ignore") as f:
                    for line in f:
                        if line.startswith(gw_ip + " "):
                            cols = line.split()
                            if len(cols) >= 4:
                                details.append(f"mac:{cols[3].lower()}")
                            break
            except OSError:
                pass
        return details

    @classmethod
    def get_network_fingerprint(cls):
        hw_parts = cls._windows_net_details() if IS_WINDOWS else cls._posix_net_details()
        has_stable_id = any(p.startswith(("mac:", "bssid:")) for p in hw_parts)

        parts = list(hw_parts)
        if not has_stable_id:
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                s.settimeout(0.5)
                s.connect(("1.1.1.1", 80))
                parts.insert(0, f"ip:{s.getsockname()[0]}")
                s.close()
            except Exception:
                if not parts:
                    parts.append("no_route")

        raw = "|".join(parts) if parts else "unknown"
        digest = hashlib.sha1(raw.encode("utf-8", errors="ignore")).hexdigest()[:10]
        return f"net_{digest}"



class InternetMonitor:
    """
    Cross-platform OS-level + active network connectivity detector.
    - Uses Windows WinINet API (`InternetGetConnectedState`) or POSIX routing table
      to immediately detect disconnected adapters / Airplane Mode.
    - Performs fast parallel TCP reachability probes when Windscribe's firewall is off
      so Wi-Fi drops without adapter disconnect are also caught quickly.
    """

    PROBE_ENDPOINTS = (
        ("1.1.1.1", 53),
        ("8.8.8.8", 53),
        ("4.2.2.4", 53),
        ("1.1.1.1", 443),
        ("8.8.8.8", 443),
    )

    @staticmethod
    def os_network_connected():
        """Fast OS-level check for an active network connection / default route."""
        if IS_WINDOWS:
            try:
                flags = ctypes.c_ulong(0)
                connected = ctypes.windll.wininet.InternetGetConnectedState(ctypes.byref(flags), 0)
                if not connected:
                    return False, "Windows reports no active network connection"
                return True, "Windows network adapter connected"
            except Exception:
                # Fallback to routing table if wininet is unavailable
                out = NetworkProfiler._run_quick(["route", "print", "0.0.0.0"], timeout=1.0)
                if re.search(r"0\.0\.0\.0\s+0\.0\.0\.0\s+\d+\.\d+\.\d+\.\d+", out):
                    return True, "Windows default route present"
                return False, "No default route on Windows"

        if platform.system() == "Darwin":
            out = NetworkProfiler._run_quick(["route", "-n", "get", "default"], timeout=1.0)
            if "gateway:" in out or "interface:" in out:
                return True, "macOS default route present"
            return False, "No default route on macOS"

        out = NetworkProfiler._run_quick(["ip", "route", "show", "default"], timeout=1.0)
        if "default " in out:
            return True, "Linux default route present"
        return False, "No default route on Linux"

    @classmethod
    def _tcp_probe_any(cls, endpoints=None, timeout=1.5):
        """Returns True as soon as any endpoint accepts a TCP handshake."""
        targets = endpoints or cls.PROBE_ENDPOINTS
        found = threading.Event()
        threads = []

        def _probe(host, port):
            if found.is_set():
                return
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(timeout)
            try:
                s.connect((host, int(port)))
                found.set()
            except Exception:
                pass
            finally:
                try:
                    s.close()
                except Exception:
                    pass

        for h, p in targets:
            t = threading.Thread(target=_probe, args=(h, p), daemon=True)
            t.start()
            threads.append(t)

        found.wait(timeout=timeout + 0.25)
        return found.is_set()

    @classmethod
    def has_internet(cls, firewall_only=False, timeout=1.5):
        """
        Checks whether the machine currently has internet connectivity.
        When `firewall_only=True` (Windscribe Kill Switch kept ON while disconnected),
        only OS-level adapter/route state is checked so the firewall doesn't cause false positives.
        """
        os_ok, os_reason = cls.os_network_connected()
        if not os_ok:
            return False, os_reason
        if firewall_only:
            return True, f"{os_reason} (firewall mode)"
        if cls._tcp_probe_any(timeout=timeout):
            return True, "Internet reachable"
        return False, "Network adapter up but no internet reachability"


class SleepPreventer:
    """
    Prevents the OS from entering Sleep/Standby during long unattended scans.
    Allows the display to turn off normally while keeping CPU and network active.
    """

    ES_CONTINUOUS = 0x80000000
    ES_SYSTEM_REQUIRED = 0x00000001

    def __init__(self):
        self._proc = None
        self._active = False

    def acquire(self):
        if self._active:
            return
        if IS_WINDOWS:
            try:
                ctypes.windll.kernel32.SetThreadExecutionState(
                    self.ES_CONTINUOUS | self.ES_SYSTEM_REQUIRED
                )
                self._active = True
            except Exception:
                pass
        elif platform.system() == "Darwin":
            try:
                self._proc = subprocess.Popen(
                    ["caffeinate", "-i", "-w", str(os.getpid())],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                self._active = True
            except Exception:
                self._proc = None

    def release(self):
        if not self._active:
            return
        self._active = False
        if IS_WINDOWS:
            try:
                ctypes.windll.kernel32.SetThreadExecutionState(self.ES_CONTINUOUS)
            except Exception:
                pass
        elif self._proc is not None:
            try:
                self._proc.terminate()
            except Exception:
                pass
            self._proc = None

    def __enter__(self):
        self.acquire()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release()
        return False


class SocketProber:
    """Fast, non-invasive TCP port reachability prober to detect immediate ISP port blocks."""

    @staticmethod
    def probe_tcp_port(host, port, timeout=1.2):
        """
        Attempts a raw TCP handshake to (host, port).
        Returns 'OK', 'RST' (immediately refused/reset), or 'DROP' (timed out).
        """
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(timeout)
        try:
            s.connect((host, int(port)))
            return "OK"
        except ConnectionRefusedError:
            return "RST"
        except socket.timeout:
            return "DROP"
        except OSError:
            return "RST"
        finally:
            try:
                s.close()
            except Exception:
                pass

    @classmethod
    def probe_ports(cls, ports=(443, 8443, 80, 587, 22, 8080), host="1.1.1.1", timeout=1.0):
        """Probes common TCP ports in parallel and returns {port: status}."""
        results = {}
        threads = []
        lock = threading.Lock()

        def _worker(p):
            st = cls.probe_tcp_port(host, p, timeout=timeout)
            with lock:
                results[int(p)] = st

        for p in ports:
            t = threading.Thread(target=_worker, args=(p,), daemon=True)
            t.start()
            threads.append(t)
        for t in threads:
            t.join(timeout=timeout + 0.3)
        return results


class FailureClassifier:
    """Classifies connection failures using multi-source logs and telemetry."""

    @staticmethod
    def _tail_text(path, max_bytes=8192):
        if not path or not os.path.isfile(path):
            return ""
        try:
            size = os.path.getsize(path)
            with open(path, "rb") as f:
                if size > max_bytes:
                    f.seek(size - max_bytes)
                return f.read().decode("utf-8", errors="replace")
        except Exception:
            return ""

    @staticmethod
    def _recent_wg_ringlog_signals(ws_dir, lookback_secs=45):
        if not ws_dir:
            return {"initiations": 0, "timeouts": 0, "success": 0}
        log_bin = ""
        for rel in (os.path.join("config", "log.bin"), "log.bin"):
            cand = os.path.join(ws_dir, rel)
            if os.path.isfile(cand):
                log_bin = cand
                break
        if not log_bin:
            return {"initiations": 0, "timeouts": 0, "success": 0}

        try:
            with open(log_bin, "rb") as f:
                data = f.read()
            if len(data) < 8:
                return {"initiations": 0, "timeouts": 0, "success": 0}
            magic, _ = struct.unpack("<II", data[:8])
            if magic != 0x0BADBABE or len(data) < 8 + 2048 * 520:
                return {"initiations": 0, "timeouts": 0, "success": 0}

            cutoff_ns = int((time.time() - lookback_secs) * 1e9)
            init_c = to_c = ok_c = 0
            for i in range(2048):
                offset = 8 + i * 520
                ts_ns = struct.unpack("<q", data[offset:offset + 8])[0]
                if ts_ns < cutoff_ns:
                    continue
                msg = data[offset + 8:offset + 520].split(b"\x00", 1)[0].decode("utf-8", errors="ignore")
                if "Sending handshake initiation" in msg:
                    init_c += 1
                elif "did not complete" in msg:
                    to_c += 1
                elif "Receiving handshake response" in msg:
                    ok_c += 1
            return {"initiations": init_c, "timeouts": to_c, "success": ok_c}
        except Exception:
            return {"initiations": 0, "timeouts": 0, "success": 0}

    @classmethod
    def classify(
        cls,
        proto,
        port,
        status_str,
        duration,
        cli_out="",
        ping_res=None,
        http_ms=None,
        speed_kbps=None,
        ws_dir="",
    ):
        st_upper = (status_str or "").upper()
        out_lower = (cli_out or "").lower()

        if st_upper == "INVALID_LOC" or "location does not exist" in out_lower or "upgrade to a pro" in out_lower:
            return ERR_PRO_OR_LOC, "Location unavailable or Pro-only"

        if st_upper == "SUCCESS":
            if speed_kbps is not None and speed_kbps < 15.0:
                return ERR_THROTTLED, f"Severe throttling ({speed_kbps:.1f} KB/s)"
            return ERR_NONE, "Healthy tunnel"

        if st_upper == "DPI_RESET":
            if duration is not None and duration < 3.5:
                return ERR_IMMEDIATE_DPI_RESET, f"Immediate reset after {duration:.1f}s"
            return ERR_DELAYED_DPI_RESET, f"Delayed DPI reset after {duration or 0:.1f}s"

        if st_upper == "BLACKHOLED":
            return ERR_BLACKHOLED, "Tunnel up but traffic blackholed (0 replies)"

        if st_upper == "HTTP_FAIL":
            if ping_res:
                return ERR_L7_HTTP_BLOCK, "ICMP ping OK but L7 HTTP/TLS blocked"
            return ERR_BLACKHOLED, "Both ICMP and HTTP failed"

        if proto in ("wireguard", "udp"):
            wg_sig = cls._recent_wg_ringlog_signals(ws_dir, lookback_secs=45)
            if wg_sig["timeouts"] > 0 and wg_sig["success"] == 0:
                return ERR_UDP_DROP, f"WireGuard handshake timed out ({wg_sig['timeouts']}x UDP drop)"
            if wg_sig["initiations"] > 0 and wg_sig["success"] == 0:
                return ERR_UDP_DROP, "WireGuard handshake initiation received no response"

        svc_tail = cls._tail_text(os.path.join(ws_dir, "windscribe_service.log") if ws_dir else "")
        if not svc_tail and ws_dir:
            svc_tail = cls._tail_text(os.path.join(ws_dir, "wireguard_service.log"))
        svc_low = svc_tail.lower()

        if "connection reset" in svc_low or "rst" in out_lower or "connection refused" in svc_low:
            if duration is not None and duration < 4.0:
                return ERR_IMMEDIATE_DPI_RESET, "TCP RST / connection refused"
            return ERR_DELAYED_DPI_RESET, "Connection reset by peer/DPI"

        if proto in ("wireguard", "udp", "ikev2"):
            return ERR_UDP_DROP, f"{proto.upper()} timed out (likely UDP drop)"

        if duration is not None and duration < 4.0:
            return ERR_IMMEDIATE_DPI_RESET, f"Fast failure ({duration:.1f}s)"

        return ERR_TIMEOUT_GENERIC, f"Connection timed out ({duration or 0:.1f}s)"


# ---------------------------------------------------------------------------
# Time-Decayed Hierarchical Thompson Sampling Bandit
# ---------------------------------------------------------------------------
class AdaptiveBanditScheduler:
    """
    Online learning scheduler using Hierarchical Beta-Bernoulli Thompson Sampling
    with exponential time-decay to adapt to changing DPI/firewall rules.
    """

    HALF_LIFE_SECS = 12 * 3600.0

    W_PROTO = 0.40
    W_PROTO_PORT = 0.25
    W_COUNTRY_PROTO = 0.20
    W_NODE_PROTO = 0.15

    OBFUSCATED_PROTOS = ("wstunnel", "stealth")

    def __init__(self, db_path, network_id=None):
        self.db_path = db_path
        self.network_id = network_id or NetworkProfiler.get_network_fingerprint()
        self.lock = threading.RLock()
        self.conn = sqlite3.connect(self.db_path, timeout=15.0, check_same_thread=False)
        try:
            self.conn.execute("PRAGMA journal_mode=WAL")
        except Exception:
            pass
        self._init_table()
        self.bootstrapped_count = self.bootstrap_from_history()

    def _init_table(self):
        with self.lock:
            self.conn.execute(
                """
                CREATE TABLE IF NOT EXISTS ai_bandit_stats (
                    network_id TEXT NOT NULL,
                    arm_type TEXT NOT NULL,
                    arm_key TEXT NOT NULL,
                    alpha REAL NOT NULL DEFAULT 1.0,
                    beta REAL NOT NULL DEFAULT 1.0,
                    last_updated REAL NOT NULL,
                    last_error TEXT DEFAULT '',
                    total_trials INTEGER NOT NULL DEFAULT 0,
                    total_successes INTEGER NOT NULL DEFAULT 0,
                    PRIMARY KEY (network_id, arm_type, arm_key)
                )
                """
            )
            self.conn.commit()

    def bootstrap_from_history(self, limit=300):
        """Seeds ai_bandit_stats from existing `tests` table if this network has no AI history yet."""
        with self.lock:
            cur = self.conn.cursor()
            cur.execute(
                "SELECT COUNT(*) FROM ai_bandit_stats WHERE network_id=?",
                (self.network_id,),
            )
            if cur.fetchone()[0] > 0:
                return 0
            cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='tests'")
            if not cur.fetchone():
                return 0
            cur.execute(
                "SELECT location, city, country, protocol, port, status, duration, ping, http_ms, speed_kbps "
                "FROM tests WHERE status != 'INVALID_LOC' ORDER BY id DESC LIMIT ?",
                (int(limit),),
            )
            rows = cur.fetchall()
            if not rows:
                return 0

            now = time.time()
            imported = 0
            for node, city, country, proto, port, status, duration, ping, http_ms, speed_kbps in reversed(rows):
                st = (status or "").upper()
                if st == "SUCCESS":
                    err_cls = ERR_THROTTLED if (speed_kbps is not None and speed_kbps < 15.0) else ERR_NONE
                elif st == "DPI_RESET":
                    err_cls = ERR_IMMEDIATE_DPI_RESET if (duration is not None and duration < 3.5) else ERR_DELAYED_DPI_RESET
                elif st == "BLACKHOLED":
                    err_cls = ERR_BLACKHOLED
                elif st == "HTTP_FAIL":
                    err_cls = ERR_L7_HTTP_BLOCK if ping is not None else ERR_BLACKHOLED
                else:
                    err_cls = ERR_UDP_DROP if proto in ("wireguard", "udp", "ikev2") else ERR_TIMEOUT_GENERIC

                # Apply 0.5x weight for historical records so fresh live tests still adapt quickly
                loc = {"country": country or "Unknown", "city": city or "Unknown", "location": node or ""}
                is_succ = (err_cls == ERR_NONE)
                da = 0.5 if is_succ else 0.0
                db = 0.0 if is_succ else 0.5
                node_id = f"{loc['country']}|{loc['city']}|{loc['location']}"
                self._update_arm("proto", proto, da, db, err_cls, is_succ, now)
                self._update_arm("proto_port", f"{proto}:{port}", da, db, err_cls, is_succ, now)
                self._update_arm("country_proto", f"{loc['country']}|{proto}", da, db, err_cls, is_succ, now)
                self._update_arm("node_proto", f"{node_id}|{proto}", da, db, err_cls, is_succ, now)
                imported += 1

            self.conn.commit()
            return imported

    def _decay(self, alpha, beta, last_updated, now):
        dt = max(0.0, now - (last_updated or now))
        if dt <= 0:
            return max(1.0, alpha), max(1.0, beta)
        factor = math.pow(0.5, dt / self.HALF_LIFE_SECS)
        new_a = 1.0 + max(0.0, alpha - 1.0) * factor
        new_b = 1.0 + max(0.0, beta - 1.0) * factor
        return new_a, new_b

    def _get_arm(self, arm_type, arm_key, now):
        cur = self.conn.cursor()
        cur.execute(
            "SELECT alpha, beta, last_updated, last_error, total_trials, total_successes "
            "FROM ai_bandit_stats WHERE network_id=? AND arm_type=? AND arm_key=?",
            (self.network_id, arm_type, arm_key),
        )
        row = cur.fetchone()
        if not row:
            return 1.0, 1.0, "", 0, 0
        a, b, lu, err, trials, succ = row
        a, b = self._decay(a, b, lu, now)
        return a, b, err or "", trials, succ

    def _update_arm(self, arm_type, arm_key, delta_a, delta_b, error_class, is_success, now):
        a, b, _, trials, succ = self._get_arm(arm_type, arm_key, now)
        a = max(1.0, a + delta_a)
        b = max(1.0, b + delta_b)
        trials += 1
        if is_success:
            succ += 1
        self.conn.execute(
            """
            INSERT OR REPLACE INTO ai_bandit_stats
            (network_id, arm_type, arm_key, alpha, beta, last_updated, last_error, total_trials, total_successes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (self.network_id, arm_type, arm_key, a, b, now, error_class, trials, succ),
        )

    def seed_port_probe(self, port_status_map):
        """Applies light negative prior to TCP ports that failed pre-flight socket probing."""
        now = time.time()
        with self.lock:
            for port, st in (port_status_map or {}).items():
                if st in ("RST", "DROP"):
                    for proto in ("tcp", "stealth"):
                        self._update_arm("proto_port", f"{proto}:{port}", 0.0, 0.75, "PREFLIGHT_" + st, False, now)
            self.conn.commit()

    def record_feedback(self, loc, proto, port, error_class, ping_ms=None, http_ms=None, speed_kbps=None):
        if error_class == ERR_PRO_OR_LOC:
            return

        now = time.time()
        country = loc.get("country", "Unknown")
        city = loc.get("city", "Unknown")
        node = loc.get("location", "")
        node_id = f"{country}|{city}|{node}"
        proto_port = f"{proto}:{port}"
        country_proto = f"{country}|{proto}"
        node_proto = f"{node_id}|{proto}"

        with self.lock:
            if error_class == ERR_NONE:
                bonus = 0.25 if http_ms is not None else 0.0
                if speed_kbps is not None and speed_kbps >= 100.0:
                    bonus += 0.25
                da = 1.0 + bonus
                self._update_arm("proto", proto, da, 0.0, error_class, True, now)
                self._update_arm("proto_port", proto_port, da, 0.0, error_class, True, now)
                self._update_arm("country_proto", country_proto, da, 0.0, error_class, True, now)
                self._update_arm("node_proto", node_proto, da, 0.0, error_class, True, now)

            elif error_class == ERR_THROTTLED:
                self._update_arm("proto", proto, 0.4, 0.2, error_class, True, now)
                self._update_arm("proto_port", proto_port, 0.3, 0.3, error_class, True, now)
                self._update_arm("country_proto", country_proto, 0.2, 0.5, error_class, False, now)
                self._update_arm("node_proto", node_proto, 0.0, 1.0, error_class, False, now)

            elif error_class == ERR_UDP_DROP:
                self._update_arm("proto", proto, 0.0, 2.2, error_class, False, now)
                self._update_arm("proto_port", proto_port, 0.0, 1.8, error_class, False, now)
                self._update_arm("country_proto", country_proto, 0.0, 0.6, error_class, False, now)
                self._update_arm("node_proto", node_proto, 0.0, 0.5, error_class, False, now)
                for obf in self.OBFUSCATED_PROTOS:
                    if obf != proto:
                        self._update_arm("proto", obf, 0.30, 0.0, "", False, now)

            elif error_class in (ERR_IMMEDIATE_DPI_RESET, ERR_DELAYED_DPI_RESET):
                p_pen = 1.4 if error_class == ERR_IMMEDIATE_DPI_RESET else 1.1
                self._update_arm("proto", proto, 0.0, p_pen, error_class, False, now)
                self._update_arm("proto_port", proto_port, 0.0, 2.0, error_class, False, now)
                self._update_arm("country_proto", country_proto, 0.0, 0.8, error_class, False, now)
                self._update_arm("node_proto", node_proto, 0.0, 0.8, error_class, False, now)
                if proto not in self.OBFUSCATED_PROTOS:
                    for obf in self.OBFUSCATED_PROTOS:
                        self._update_arm("proto", obf, 0.20, 0.0, "", False, now)

            elif error_class in (ERR_L7_HTTP_BLOCK, ERR_BLACKHOLED):
                self._update_arm("proto", proto, 0.0, 0.4, error_class, False, now)
                self._update_arm("proto_port", proto_port, 0.0, 0.5, error_class, False, now)
                self._update_arm("country_proto", country_proto, 0.0, 1.6, error_class, False, now)
                self._update_arm("node_proto", node_proto, 0.0, 2.2, error_class, False, now)

            else:
                self._update_arm("proto", proto, 0.0, 1.0, error_class, False, now)
                self._update_arm("proto_port", proto_port, 0.0, 1.2, error_class, False, now)
                self._update_arm("country_proto", country_proto, 0.0, 0.8, error_class, False, now)
                self._update_arm("node_proto", node_proto, 0.0, 1.0, error_class, False, now)

            self.conn.commit()

    def _load_arms_cache(self, now):
        """Loads and time-decays all arms for this network in a single SQL query."""
        cache = {}
        cur = self.conn.cursor()
        cur.execute(
            "SELECT arm_type, arm_key, alpha, beta, last_updated, last_error "
            "FROM ai_bandit_stats WHERE network_id=?",
            (self.network_id,),
        )
        for arm_type, arm_key, a, b, lu, err in cur.fetchall():
            da, db = self._decay(a, b, lu, now)
            cache[(arm_type, arm_key)] = (da, db, err or "")
        return cache

    def score_task(self, loc, proto, port, now, priority_rank=0, total_protos=6, arms_cache=None):
        country = loc.get("country", "Unknown")
        city = loc.get("city", "Unknown")
        node = loc.get("location", "")
        node_id = f"{country}|{city}|{node}"

        if arms_cache is not None:
            a_p, b_p, err_p = arms_cache.get(("proto", proto), (1.0, 1.0, ""))
            a_pp, b_pp, _ = arms_cache.get(("proto_port", f"{proto}:{port}"), (1.0, 1.0, ""))
            a_cp, b_cp, _ = arms_cache.get(("country_proto", f"{country}|{proto}"), (1.0, 1.0, ""))
            a_np, b_np, _ = arms_cache.get(("node_proto", f"{node_id}|{proto}"), (1.0, 1.0, ""))
        else:
            a_p, b_p, err_p, _, _ = self._get_arm("proto", proto, now)
            a_pp, b_pp, _, _, _ = self._get_arm("proto_port", f"{proto}:{port}", now)
            a_cp, b_cp, _, _, _ = self._get_arm("country_proto", f"{country}|{proto}", now)
            a_np, b_np, _, _, _ = self._get_arm("node_proto", f"{node_id}|{proto}", now)

        s_p = random.betavariate(a_p, b_p)
        s_pp = random.betavariate(a_pp, b_pp)
        s_cp = random.betavariate(a_cp, b_cp)
        s_np = random.betavariate(a_np, b_np)

        prio_bonus = 0.03 * (1.0 - (priority_rank / max(1, total_protos)))
        score = (
            self.W_PROTO * s_p
            + self.W_PROTO_PORT * s_pp
            + self.W_COUNTRY_PROTO * s_cp
            + self.W_NODE_PROTO * s_np
            + prio_bonus
        )

        mean_p = a_p / (a_p + b_p)
        return score, mean_p, err_p

    def select_next_index(self, remaining_tasks, priority_order=None, candidate_indices=None):
        if not remaining_tasks:
            return 0, ""
        now = time.time()
        prio_map = {p: idx for idx, p in enumerate(priority_order or [])}
        total_protos = max(1, len(prio_map) or 6)

        pool = list(candidate_indices) if candidate_indices is not None else list(range(len(remaining_tasks)))
        if not pool:
            pool = list(range(len(remaining_tasks)))

        # Evaluate all candidates in memory using a single batched SQL read (no 300-item blind spot)
        best_idx = pool[0]
        best_score = -1.0
        best_mean = 0.5

        with self.lock:
            arms_cache = self._load_arms_cache(now)
            for idx in pool:
                loc, proto, port = remaining_tasks[idx]
                rank = prio_map.get(proto, total_protos)
                sc, mean_p, _ = self.score_task(
                    loc, proto, port, now, rank, total_protos, arms_cache=arms_cache
                )
                if sc > best_score:
                    best_score = sc
                    best_idx = idx
                    best_mean = mean_p

        loc, proto, port = remaining_tasks[best_idx]
        disp = f"{loc.get('city', '')} – {loc.get('location', '')}" if loc.get("location") else loc.get("city", "")
        reason = f"AI picked {disp} ({proto}:{port}) | score={best_score:.2f}, proto_prob={best_mean:.0%}"
        return best_idx, reason

    def get_network_summary(self):
        now = time.time()
        out = {}
        with self.lock:
            cur = self.conn.cursor()
            cur.execute(
                "SELECT arm_key, alpha, beta, last_updated, last_error, total_trials, total_successes "
                "FROM ai_bandit_stats WHERE network_id=? AND arm_type='proto'",
                (self.network_id,),
            )
            for proto, a, b, lu, err, trials, succ in cur.fetchall():
                da, db = self._decay(a, b, lu, now)
                out[proto] = {
                    "prob": round(da / (da + db), 3),
                    "trials": trials,
                    "successes": succ,
                    "last_error": err or "",
                }
        return out

    def close(self):
        with self.lock:
            try:
                self.conn.close()
            except Exception:
                pass


# ---------------------------------------------------------------------------
# AI Auto-Pilot Meta-Controller
# ---------------------------------------------------------------------------
class AutoPilotController:
    """
    Higher-level AI controller:
    - Starts at L1_DIRECT on cold-start (so clean networks get maximum speed) and
      rapidly escalates L1 -> L2 -> L3 -> L4 on DPI feedback.
    - Supports pre-flight socket probing to deprioritize hard-blocked TCP ports.
    - Enforces a smart working-route budget (default 3 verified working routes)
      so Auto-Pilot doesn't burn through hundreds of combinations unnecessarily.
    """

    DEFAULT_TARGET_ROUTES = 0  # 0 = unlimited (never stop early on unattended scans)

    def __init__(self, bandit: AdaptiveBanditScheduler, target_routes=DEFAULT_TARGET_ROUTES):
        self.bandit = bandit
        self.target_routes = max(0, int(target_routes))
        self.current_strategy = self._choose_initial_strategy()
        self.consec_udp_drop = 0
        self.consec_dpi_reset = 0
        self.consec_delayed_reset = 0
        self.consec_generic_fail = 0
        self.country_proto_fails = {}

    def _choose_initial_strategy(self):
        summary = self.bandit.get_network_summary()
        if not summary:
            # Cold-start at L1_DIRECT: if UDP/WireGuard is open, we win immediately;
            # if blocked, 2x UDP_DROP rapidly escalates to L2_TLS_OBFUSCATION.
            return "L1_DIRECT"

        best_strat = "L1_DIRECT"
        best_score = -1.0
        for strat_name in STRATEGY_ORDER:
            protos = ANTI_CENSORSHIP_PROFILES[strat_name]["protos"]
            probs = [summary[p]["prob"] for p in protos if p in summary and summary[p]["trials"] > 0]
            if probs:
                avg_p = sum(probs) / len(probs)
                if avg_p > best_score:
                    best_score = avg_p
                    best_strat = strat_name
        return best_strat

    def get_dynamic_timings(self):
        cfg = ANTI_CENSORSHIP_PROFILES[self.current_strategy]
        return cfg["timeout"], cfg["hold_seconds"]

    def strategy_label(self):
        return ANTI_CENSORSHIP_PROFILES[self.current_strategy]["label"]

    @staticmethod
    def should_try_ip_rotate(error_class):
        return error_class in (ERR_L7_HTTP_BLOCK, ERR_THROTTLED)

    def _matching_indices(self, remaining_tasks, strategy_name):
        allowed = ANTI_CENSORSHIP_PROFILES[strategy_name]["protos"]
        return [
            idx for idx, (_, proto, port) in enumerate(remaining_tasks)
            if proto in allowed and int(port) in allowed[proto]
        ]

    def select_next_index(self, remaining_tasks, priority_order=None):
        candidates = self._matching_indices(remaining_tasks, self.current_strategy)
        if not candidates:
            cur_pos = STRATEGY_ORDER.index(self.current_strategy)
            search_order = STRATEGY_ORDER[cur_pos + 1:] + STRATEGY_ORDER[:cur_pos]
            for alt in search_order:
                alt_cands = self._matching_indices(remaining_tasks, alt)
                if alt_cands:
                    self.current_strategy = alt
                    candidates = alt_cands
                    break

        pool = candidates if candidates else list(range(len(remaining_tasks)))
        # Location diversity: prefer (country, proto) pairs that have not just failed
        if pool and self.country_proto_fails:
            fresh = [
                i for i in pool
                if self.country_proto_fails.get(
                    (remaining_tasks[i][0].get("country", ""), remaining_tasks[i][1]), 0
                ) == 0
            ]
            if fresh:
                pool = fresh
        idx, reason = self.bandit.select_next_index(remaining_tasks, priority_order, candidate_indices=pool)
        return idx, f"[{self.current_strategy}] {reason}"

    def record_and_maybe_escalate(self, error_class, country=None, proto=None):
        if country and proto:
            cp_key = (country, proto)
            if error_class == ERR_NONE:
                self.country_proto_fails[cp_key] = 0
            elif error_class != ERR_PRO_OR_LOC:
                self.country_proto_fails[cp_key] = self.country_proto_fails.get(cp_key, 0) + 1
        if error_class == ERR_PRO_OR_LOC:
            return None

        if error_class == ERR_NONE:
            self.consec_udp_drop = 0
            self.consec_dpi_reset = 0
            self.consec_delayed_reset = 0
            self.consec_generic_fail = 0
            return None

        if error_class == ERR_UDP_DROP:
            self.consec_udp_drop += 1
        else:
            self.consec_udp_drop = 0

        if error_class == ERR_IMMEDIATE_DPI_RESET:
            self.consec_dpi_reset += 1
        else:
            self.consec_dpi_reset = 0

        if error_class == ERR_DELAYED_DPI_RESET:
            self.consec_delayed_reset += 1
        else:
            self.consec_delayed_reset = 0

        self.consec_generic_fail += 1

        old = self.current_strategy
        new_strat = None

        if old == "L1_DIRECT" and (self.consec_udp_drop >= 2 or self.consec_generic_fail >= 2):
            new_strat = "L2_TLS_OBFUSCATION"
        elif self.consec_delayed_reset >= 2 and old != "L4_DEEP_TUNNEL":
            new_strat = "L4_DEEP_TUNNEL"
        elif old == "L2_TLS_OBFUSCATION" and (self.consec_dpi_reset >= 3 or self.consec_generic_fail >= 4):
            new_strat = "L3_PORT_HOPPING"
        elif old == "L3_PORT_HOPPING" and (self.consec_dpi_reset >= 3 or self.consec_generic_fail >= 4):
            new_strat = "L4_DEEP_TUNNEL"

        if new_strat and new_strat != old:
            self.current_strategy = new_strat
            self.consec_udp_drop = 0
            self.consec_dpi_reset = 0
            self.consec_delayed_reset = 0
            self.consec_generic_fail = 0
            return new_strat
        return None


# ---------------------------------------------------------------------------
# Online AI Advisor: Snapshot Export & External JSON Config Import (v1.7.0)
# ---------------------------------------------------------------------------
def generate_ai_snapshot(db_path, current_strategy="AUTO", recent_errors=None):
    """
    Generates a structured, copy-pasteable report + prompt for online AIs
    (ChatGPT / Gemini / Claude) so they can analyze current DPI behavior
    and return a machine-readable JSON strategy config for AutoScribe.
    """
    import json as _json

    bandit = AdaptiveBanditScheduler(db_path)
    try:
        summary = bandit.get_network_summary()
        now = time.time()
        top_ports = []
        with bandit.lock:
            cur = bandit.conn.cursor()
            cur.execute(
                "SELECT arm_key, alpha, beta, last_updated, last_error, total_trials, total_successes "
                "FROM ai_bandit_stats WHERE network_id=? AND arm_type='proto_port' "
                "ORDER BY total_trials DESC LIMIT 20",
                (bandit.network_id,),
            )
            for key, a, b, lu, err, trials, succ in cur.fetchall():
                da, db = bandit._decay(a, b, lu, now)
                top_ports.append({
                    "route": key,
                    "prob": round(da / (da + db), 3),
                    "trials": trials,
                    "successes": succ,
                    "last_error": err or "",
                })
    finally:
        bandit.close()

    report_obj = {
        "app": "AutoScribe v1.7.2",
        "network_id": bandit.network_id,
        "active_strategy": current_strategy,
        "protocol_stats": summary,
        "top_port_stats": top_ports,
        "recent_dpi_errors": (recent_errors or [])[-12:],
        "windscribe_tips_iran_2026": [
            "WireGuard/AmneziaWG often bypasses 443 DPI when switched to port 80, 53, or 123 (with Circumvent Censorship enabled in Windscribe Desktop).",
            "WStunnel (443) and Stealth (443, 8443, 587, 22, 8080) are primary fallbacks when UDP is dropped.",
            "If L7 HTTP fails while ping works, IP rotation or switching country/datacenter is more effective than changing ports.",
        ],
    }

    schema_example = {
        "strategy": "L4_DEEP_TUNNEL",
        "priority_order": ["wstunnel", "stealth", "wireguard", "tcp", "udp", "ikev2"],
        "protocols": {
            "wstunnel": [443],
            "stealth": [443, 8443, 587, 22],
            "wireguard": [80, 53, 123],
            "tcp": [443, 8080],
        },
        "boost_arms": {
            "wireguard:80": 1.5,
            "wstunnel:443": 2.0,
            "udp": -1.5,
        },
        "timeout": 32,
        "hold_seconds": 15,
        "http_check": True,
        "speed_burst": True,
        "target_routes": 3,
        "note": "Short explanation of why this config fits the DPI pattern",
    }

    lines = [
        "=== AUTOSCRIBE AI DIAGNOSTIC SNAPSHOT ===",
        "Analyze the following Windscribe DPI/network telemetry and respond ONLY with a valid JSON block matching the schema below so AutoScribe's AI Engine can import and test it.",
        "",
        "--- CURRENT TELEMETRY ---",
        _json.dumps(report_obj, indent=2, ensure_ascii=False),
        "",
        "--- REQUIRED RESPONSE JSON SCHEMA ---",
        _json.dumps(schema_example, indent=2, ensure_ascii=False),
    ]
    return "\n".join(lines)


def parse_and_apply_ai_config(raw_text, db_path):
    """
    Parses JSON (including ```json ... ``` fenced output from online AIs),
    validates fields, seeds Bandit arm weights into SQLite, and returns
    a normalized config dict for the UI & Worker.
    Raises ValueError on invalid input.
    """
    import json as _json

    txt = (raw_text or "").strip()
    if not txt:
        raise ValueError("Empty input.")

    # Extract JSON from markdown code fences if present
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", txt, flags=re.DOTALL | re.IGNORECASE)
    if m:
        txt = m.group(1)
    else:
        first_b = txt.find("{")
        last_b = txt.rfind("}")
        if first_b != -1 and last_b > first_b:
            txt = txt[first_b:last_b + 1]

    data = _json.loads(txt)
    if not isinstance(data, dict):
        raise ValueError("AI config must be a JSON object.")

    valid_protos = {"wireguard", "ikev2", "udp", "tcp", "stealth", "wstunnel"}
    out = {}

    strat = data.get("strategy")
    if isinstance(strat, str) and strat in ANTI_CENSORSHIP_PROFILES:
        out["strategy"] = strat

    prio = data.get("priority_order")
    if isinstance(prio, list):
        clean_prio = [str(p).lower() for p in prio if str(p).lower() in valid_protos]
        for p in ("wstunnel", "stealth", "tcp", "wireguard", "udp", "ikev2"):
            if p not in clean_prio:
                clean_prio.append(p)
        out["priority_order"] = clean_prio

    protos = data.get("protocols")
    if isinstance(protos, dict):
        clean_protos = {}
        for p, ports in protos.items():
            p_low = str(p).lower()
            if p_low in valid_protos and isinstance(ports, list):
                clean_ports = [int(x) for x in ports if str(x).isdigit()]
                if clean_ports:
                    clean_protos[p_low] = clean_ports
        if clean_protos:
            out["protocols"] = clean_protos

    for num_key, lo, hi in (("timeout", 5, 180), ("hold_seconds", 5, 120), ("target_routes", 0, 100)):
        if num_key in data:
            try:
                val = int(data[num_key])
                out[num_key] = max(lo, min(hi, val))
            except (TypeError, ValueError):
                pass

    for bool_key in ("http_check", "speed_burst"):
        if bool_key in data:
            out[bool_key] = bool(data[bool_key])

    if isinstance(data.get("note"), str):
        out["note"] = data["note"].strip()[:300]

    # Seed Bandit weights if boost_arms provided
    boosts = data.get("boost_arms")
    seeded = 0
    if isinstance(boosts, dict) and boosts:
        bandit = AdaptiveBanditScheduler(db_path)
        now = time.time()
        try:
            with bandit.lock:
                for arm_key, weight in boosts.items():
                    try:
                        w = max(-4.0, min(4.0, float(weight)))
                    except (TypeError, ValueError):
                        continue
                    k_str = str(arm_key).strip().lower()
                    arm_type = "proto_port" if ":" in k_str else "proto"
                    da = w if w > 0 else 0.0
                    db = abs(w) if w < 0 else 0.0
                    bandit._update_arm(arm_type, k_str, da, db, "AI_IMPORT", w > 0, now)
                    seeded += 1
                bandit.conn.commit()
        finally:
            bandit.close()
    out["seeded_arms"] = seeded
    return out
