import os
import sys

# PyInstaller --noconsole stream redirect fix
if sys.stdout is None:
    sys.stdout = open(os.devnull, "w")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w")

import csv
import datetime
import json
import platform
import queue
import random
import re
import shutil
import sqlite3
import struct
import subprocess
import threading
import time
import tkinter as tk
import urllib.request
from collections import Counter
from tkinter import filedialog, messagebox, ttk
from tkinter import font as tkfont

import customtkinter as ctk

import i18n
from i18n import num, t, vis
from ai_engine import AdaptiveBanditScheduler, AutoPilotController, FailureClassifier, InternetMonitor, NetworkProfiler, SleepPreventer, SocketProber, generate_ai_snapshot, parse_and_apply_ai_config

APP_NAME = "AutoScribe"
APP_VERSION = "1.7.2"

# ---------------------------------------------------------------------------
# Theme
# ---------------------------------------------------------------------------
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

BG = "#0B0D10"
SIDEBAR = "#101318"
CARD = "#12151A"
INPUT = "#161A20"
DEEP = "#0E1014"
ROW = "#141820"
ROW_ALT = "#15191F"
BORDER = "#1F242C"
BORDER_2 = "#262C35"
HOVER = "#1C222B"
TEXT = "#E8EAED"
TEXT_2 = "#AEB6C1"
MUTED = "#8E97A3"
DIM = "#5B6470"
ACCENT = "#7CC4FF"
ACCENT_HOVER = "#9BD2FF"
ON_ACCENT = "#0B0D10"
ACCENT_SOFT = "#18212C"
ACCENT_LINE = "#2E3B4C"
CHIP = "#1A2330"
CHIP_TEXT = "#A9D8FF"
SELECTED = "#1E2B3B"
GOOD = "#6EE7A8"
GOOD_SOFT = "#12201B"
GOOD_LINE = "#1E3A2E"
GOOD_TEXT = "#B7F0D2"
WARN = "#FBBF24"
WARN_SOFT = "#2A2312"
WARN_TEXT = "#FCD98A"
BAD = "#F87171"
BAD_SOFT = "#2A1517"
BAD_LINE = "#5A2A2E"
BAD_TEXT = "#FFB4B4"
BAD_HOVER = "#3A1C1F"
REC_BG = "#111A22"
REC_LINE = "#23364A"

IS_WINDOWS = platform.system() == "Windows"

# Resolved in init_fonts() once Tk is running; these are the fallbacks.
SANS = "Segoe UI" if IS_WINDOWS else "Helvetica"
MONO = "Consolas" if IS_WINDOWS else "Courier"
ICON_FONT = None

ICONS = {"globe": "\uE774", "list": "\uE8FD", "sliders": "\uE713", "save": "\uE74E", "delete": "\uE74D",
         "up": "\uE70E", "down": "\uE70D", "menu": "\uE700", "collapse": "\uE76B",
         "refresh": "\uE72C"}
ICON_FALLBACK = {"globe": "◎", "list": "≡", "sliders": "⚙", "save": "S", "delete": "✕",
                 "up": "▲", "down": "▼", "menu": "≡", "collapse": "‹", "refresh": "↻"}

PROTO_NAMES = {"wireguard": "WireGuard", "ikev2": "IKEv2", "udp": "UDP", "tcp": "TCP",
               "stealth": "Stealth", "wstunnel": "WStunnel"}

DEFAULT_PROTOCOLS = {
    "wireguard": [80, 53, 123, 443, 1194, 65142],
    "ikev2": [500],
    "udp": [443, 80, 53, 123, 1194, 54783],
    "tcp": [443, 587, 21, 22, 80, 123, 143, 3306, 8080, 54783, 1194],
    "stealth": [443, 587, 21, 22, 80, 123, 143, 3306, 8080, 54783, 8443],
    "wstunnel": [443],
}

# Optimized protocol priority & ports for Iranian networks (bypassing rapid DPI resets & UDP blocks)
IRAN_PRIORITY_ORDER = ["wstunnel", "stealth", "tcp", "wireguard", "udp", "ikev2"]
IRAN_PROTOCOL_CONFIG = {
    "wstunnel": {"enabled": True, "ports": [443]},
    "stealth": {"enabled": True, "ports": [443, 8443, 80, 587, 22, 8080]},
    "tcp": {"enabled": True, "ports": [443, 8080, 80, 587, 22]},
    "wireguard": {"enabled": True, "ports": [80, 53, 123, 443]},
    "udp": {"enabled": False, "ports": [443, 53]},
    "ikev2": {"enabled": False, "ports": [500]},
}

if getattr(sys, "frozen", False):
    APP_PATH = os.path.dirname(sys.executable)
else:
    _file_dir = os.path.dirname(os.path.abspath(__file__))
    if os.path.isfile(_file_dir):
        APP_PATH = os.path.dirname(_file_dir)
    else:
        APP_PATH = _file_dir

DB_FILE = os.path.join(APP_PATH, "windscribe_results.db")
CONFIG_FILE = os.path.join(APP_PATH, "config.json")
LOCATIONS_FILE = os.path.join(APP_PATH, "locations.json")
REPORTS_DIR = os.path.join(APP_PATH, "reports")

DEFAULT_CLI = r"C:\Program Files\Windscribe\windscribe-cli.exe" if IS_WINDOWS else "windscribe-cli"
# The public server list that windscribe.com/vpn-servers loads; same format as locations.json.
LOCATIONS_URL = "https://api.windscribe.com/WebsiteStatus"

def init_fonts(root):
    global SANS, MONO, ICON_FONT
    families = set(tkfont.families(root))
    if i18n.LANG == "fa":
        # One font with Persian glyphs everywhere: Tk splits text at font fallbacks, which breaks RTL ordering.
        SANS = next((f for f in ("Segoe UI", "Tahoma", "DejaVu Sans") if f in families), SANS)
        MONO = SANS
    else:
        SANS = next((f for f in ("IBM Plex Sans", "Segoe UI", "Helvetica Neue", "DejaVu Sans") if f in families),
                    SANS)
        MONO = next((f for f in ("IBM Plex Mono", "Cascadia Mono", "Consolas", "Menlo", "DejaVu Sans Mono")
                     if f in families), MONO)
    ICON_FONT = next((f for f in ("Segoe Fluent Icons", "Segoe MDL2 Assets") if f in families), None)


def sans(size, bold=False):
    return (SANS, size, "bold") if bold else (SANS, size)


def mono(size, bold=False):
    return (MONO, size, "bold") if bold else (MONO, size)


def icon(name):
    return ICONS[name] if ICON_FONT else ICON_FALLBACK[name]


def icon_font(size=13):
    return (ICON_FONT or SANS, size)


def hidden_process_kwargs():
    """Keeps console windows from flashing up on Windows."""
    if IS_WINDOWS:
        return {"creationflags": subprocess.CREATE_NO_WINDOW}
    return {}


def resolve_cli(path):
    """Returns a usable path to windscribe-cli, or None."""
    path = (path or "").strip().strip('"')
    if not path:
        return None
    if os.path.isfile(path):
        return path
    return shutil.which(path)


def open_path(path):
    try:
        if IS_WINDOWS:
            os.startfile(path)
        elif platform.system() == "Darwin":
            subprocess.Popen(["open", path])
        else:
            subprocess.Popen(["xdg-open", path])
    except Exception as e:
        print(f"Open Error: {e}")


def ping_color(ping):
    if ping is None:
        return MUTED
    return GOOD if ping < 50 else WARN if ping < 100 else BAD


def ping_quality(ping):
    if ping is None:
        return "slow"
    return "fast" if ping < 50 else "medium" if ping < 100 else "slow"


def rate_color(rate):
    return GOOD if rate >= 0.75 else WARN if rate >= 0.45 else BAD


def loc_key(loc):
    return f"{loc['country']}|{loc['city']}|{loc['location']}"


def loc_name(city, node):
    return f"{city} – {node}" if node else city


def matches_region(loc, region):
    if region == "All":
        return True
    if region == "USA":
        return loc["country"].startswith("US ")
    return loc["continent"] == region


def trunc(text, n):
    return text if len(text) <= n else text[:n - 1] + "…"


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
class ConfigManager:
    @staticmethod
    def default_settings():
        settings = {
            "timeout": "25",
            "settle": "2",
            "ping_host": "1.1.1.1",
            "ping_count": "5",
            "resume": False,
            "selected": [],
            "random_cities": False,
            "chaos_mode": False,
            "stop_on_success": False,
            "free_only": False,
            "dedup_cities": False,
            "keep_firewall": False,
            "http_check": False,
            "http_url": "http://cp.cloudflare.com/generate_204",
            "anti_dpi_hold": False,
            "hold_seconds": "15",
            "fast_skip": True,
            "smart_ai": True,
            "auto_pilot": True,
            "speed_burst": False,
            "watchdog": False,
            "priority_order": list(DEFAULT_PROTOCOLS.keys()),
            "protocols": {},
        }
        for proto, ports in DEFAULT_PROTOCOLS.items():
            settings["protocols"][proto] = {"enabled": True, "ports": {str(p): True for p in ports}}
        return settings

    @staticmethod
    def load_config():
        default_data = {"saved_profiles": {}, "last_settings": ConfigManager.default_settings(),
                        "cli_path": DEFAULT_CLI, "window": "", "sidebar_open": True, "language": ""}
        if not os.path.exists(CONFIG_FILE):
            return default_data
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                loaded = json.load(f)
            for key, val in default_data.items():
                loaded.setdefault(key, val)
            for key, val in default_data["last_settings"].items():
                loaded["last_settings"].setdefault(key, val)
            return loaded
        except Exception as e:
            print(f"Config Load Error: {e}")
            return default_data

    @staticmethod
    def save_config(data):
        try:
            tmp = CONFIG_FILE + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
            os.replace(tmp, CONFIG_FILE)
        except Exception as e:
            print(f"Config Save Error: {e}")


# ---------------------------------------------------------------------------
# Locations (Windscribe's locations.json)
# ---------------------------------------------------------------------------
class LocationManager:
    @staticmethod
    def load_locations():
        """Returns a flat list of dicts: city, location, country, continent."""
        locations = []
        if not os.path.exists(LOCATIONS_FILE):
            return locations
        try:
            with open(LOCATIONS_FILE, "r", encoding="utf-8") as f:
                raw = json.load(f)

            for _, entry in raw.get("data", {}).get("locations", {}).items():
                country = (entry.get("name") or "Unknown").strip()
                continent = (entry.get("continent") or "Unknown").strip()
                country_premium = bool(entry.get("premium_only", 0))

                for pop in entry.get("pops", []):
                    if pop.get("status", 1) != 1:
                        continue  # skip offline/disabled nodes
                    pop_name = (pop.get("name") or "").strip()
                    if not pop_name:
                        continue
                    if " - " in pop_name:
                        city, location = pop_name.split(" - ", 1)
                    else:
                        city, location = pop_name, ""

                    is_prem = bool(pop.get("is_premium", 1 if country_premium else 0)) or country_premium
                    locations.append({
                        "city": city.strip(),
                        "location": location.strip(),
                        "country": country,
                        "continent": continent,
                        "is_premium": is_prem,
                    })
        except Exception as e:
            print(f"Locations Load Error: {e}")
        return locations

    @staticmethod
    def download():
        """Fetches the current server list from windscribe.com and replaces locations.json.
        Raises on any network or format problem, leaving the old file untouched."""
        req = urllib.request.Request(LOCATIONS_URL, headers={
            "User-Agent": f"{APP_NAME}/{APP_VERSION}", "Accept": "application/json",
            # The same placeholder token windscribe.com's own server list page sends.
            "Authorization": "Bearer 1234"})
        with urllib.request.urlopen(req, timeout=20) as resp:
            raw = resp.read()
        data = json.loads(raw.decode("utf-8"))
        locations = data.get("data", {}).get("locations")
        if not isinstance(locations, dict) or not locations:
            raise ValueError("the response did not contain a server list")
        if not any(isinstance(v, dict) and v.get("pops") for v in locations.values()):
            raise ValueError("the server list has no servers in it")
        tmp = LOCATIONS_FILE + ".tmp"
        with open(tmp, "wb") as f:
            f.write(raw)
        os.replace(tmp, LOCATIONS_FILE)

    @staticmethod
    def last_updated():
        try:
            return datetime.datetime.fromtimestamp(os.path.getmtime(LOCATIONS_FILE))
        except OSError:
            return None


# ---------------------------------------------------------------------------
# Ping - uses the system `ping`, nothing else to install
# ---------------------------------------------------------------------------
class PingRunner:
    TIME_RE = re.compile(r"(?:time|시간|시간|zeit|temps|tiempo|tempo|время|زمان)[=<:\s]+(\d+(?:[.,]\d+)?)\s*ms|[=<]\s*(\d+(?:[.,]\d+)?)\s*ms", re.IGNORECASE)
    SUMMARY_RE = re.compile(r"(?:min/avg/max|minimum|maximum|average|평균|среднее)", re.IGNORECASE)

    @staticmethod
    def parse(output):
        """Extracts per-reply latencies across IPv4/IPv6 and localized Windows/POSIX ping outputs
        while excluding the final min/avg/max summary line."""
        times = []
        for line in output.splitlines():
            low = line.lower()
            if PingRunner.SUMMARY_RE.search(low):
                continue
            if "ttl" not in low and "bytes=" not in low and "bytes from" not in low and "icmp_seq" not in low and "time=" not in low and "time<" not in low:
                continue
            m = PingRunner.TIME_RE.search(line)
            if m:
                val = m.group(1) or m.group(2)
                times.append(float(val.replace(",", ".")))
        return times

    def run(self, host, count=5, reply_timeout_ms=2000):
        """Returns ({"avg", "min", "max", "loss"}, None) or (None, error)."""
        if IS_WINDOWS:
            cmd = ["ping", "-n", str(count), "-w", str(reply_timeout_ms), host]
        elif platform.system() == "Darwin":
            cmd = ["ping", "-c", str(count), "-W", str(int(reply_timeout_ms)), host]
        else:
            cmd = ["ping", "-c", str(count), "-W", str(max(1, reply_timeout_ms // 1000)), host]
        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, encoding="utf-8", errors="replace",
                timeout=count * (reply_timeout_ms / 1000 + 1) + 5, **hidden_process_kwargs())
        except FileNotFoundError:
            return None, "ping command not found"
        except subprocess.TimeoutExpired:
            return None, "ping timed out"
        except Exception as e:
            return None, str(e)

        times = self.parse(result.stdout)
        if not times:
            return None, "no replies"
        return {
            "avg": sum(times) / len(times),
            "min": min(times),
            "max": max(times),
            "loss": (count - len(times)) / count * 100,
        }, None


# ---------------------------------------------------------------------------
# HTTP / Web Connectivity Checker & Windscribe Binary Log Analyzer
# ---------------------------------------------------------------------------
class HttpChecker:
    """Verifies real HTTP/HTTPS traffic, filtered-domain reachability, and burst throughput through the tunnel."""
    DEFAULT_URL = "http://cp.cloudflare.com/generate_204"
    SECONDARY_URL = "https://www.gstatic.com/generate_204"
    SPEED_URLS = (
        "https://speed.cloudflare.com/__down?bytes=153600",
        "http://speed.cloudflare.com/__down?bytes=153600",
    )

    @staticmethod
    def _fetch_one(url, timeout=6.0, max_bytes=256):
        req = urllib.request.Request(
            url,
            headers={"User-Agent": f"{APP_NAME}/{APP_VERSION}", "Cache-Control": "no-cache"},
        )
        t0 = time.time()
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(req, timeout=timeout) as resp:
            data = resp.read(max_bytes)
            code = getattr(resp, "status", None) or resp.getcode()
            elapsed = max(0.001, time.time() - t0)
            return int(code), elapsed, len(data)

    @classmethod
    def check(cls, url=DEFAULT_URL, timeout=6.0, multi_target=True):
        """Returns (latency_ms, None) on HTTP 2xx/3xx response, or (None, error_str).
        Supports comma-separated URLs or automatic secondary filtered-domain TLS probe."""
        raw_urls = [u.strip() for u in (url or cls.DEFAULT_URL).split(",") if u.strip()]
        if not raw_urls:
            raw_urls = [cls.DEFAULT_URL]
        if multi_target and len(raw_urls) == 1 and raw_urls[0] == cls.DEFAULT_URL:
            raw_urls.append(cls.SECONDARY_URL)

        latencies = []
        last_err = None
        for target in raw_urls:
            try:
                code, elapsed, _ = cls._fetch_one(target, timeout=timeout, max_bytes=256)
                if 200 <= code < 400:
                    latencies.append(round(elapsed * 1000.0, 1))
                else:
                    last_err = f"HTTP {code} ({target})"
            except Exception as e:
                last_err = f"{e} ({target})"
        if latencies:
            return round(sum(latencies) / len(latencies), 1), None
        return None, last_err or "HTTP check failed"

    @classmethod
    def run_speed_burst(cls, num_bytes=153600, timeout=8.0):
        """Downloads a ~150 KB burst payload to measure real throughput (KB/s) and expose DPI data-volume throttles."""
        last_err = None
        for base_url in cls.SPEED_URLS:
            url = base_url if "bytes=" not in base_url else re.sub(r"bytes=\d+", f"bytes={int(num_bytes)}", base_url)
            try:
                code, elapsed, got_bytes = cls._fetch_one(url, timeout=timeout, max_bytes=int(num_bytes) + 4096)
                if 200 <= code < 400 and got_bytes >= min(16384, int(num_bytes) // 2):
                    kbps = round((got_bytes / 1024.0) / elapsed, 1)
                    return kbps, None
                last_err = f"HTTP {code} ({got_bytes}B)"
            except Exception as e:
                last_err = str(e) or e.__class__.__name__
        return None, last_err or "Speed burst failed"


class LogAnalyzer:
    """Parses Windscribe's binary WireGuard ringbuffer (config/log.bin), service logs, and config.ovpn."""
    MAGIC = 0x0BADBABE
    MAX_LINES = 2048
    ENTRY_SIZE = 520

    @staticmethod
    def find_windscribe_dir(cli_path="", custom_path=""):
        candidates = []
        if custom_path:
            if os.path.isfile(custom_path):
                if os.path.basename(custom_path).lower() == "log.bin":
                    candidates.append(os.path.dirname(os.path.dirname(os.path.abspath(custom_path))))
                candidates.append(os.path.dirname(os.path.abspath(custom_path)))
            elif os.path.isdir(custom_path):
                candidates.append(os.path.abspath(custom_path))
        if cli_path:
            resolved = resolve_cli(cli_path)
            if resolved:
                candidates.append(os.path.dirname(os.path.abspath(resolved)))
        if IS_WINDOWS:
            candidates.append(r"C:\Program Files\Windscribe")
            local_app = os.environ.get("LOCALAPPDATA", "")
            if local_app:
                candidates.append(os.path.join(local_app, "Windscribe", "Windscribe2"))
        for c in candidates:
            if c and os.path.isdir(c):
                if os.path.isfile(os.path.join(c, "config", "log.bin")) or os.path.isfile(os.path.join(c, "log.bin")):
                    return c
        return candidates[0] if candidates else ""

    @classmethod
    def parse_ringlog(cls, log_bin_path):
        """Parses WireGuard-NT binary ringbuffer log.bin and returns chronological (dt_utc, msg) entries."""
        with open(log_bin_path, "rb") as f:
            data = f.read()
        if len(data) < 8:
            raise ValueError("log.bin is too small")
        magic, next_idx = struct.unpack("<II", data[:8])
        entries = []
        if magic == cls.MAGIC and len(data) >= 8 + cls.MAX_LINES * cls.ENTRY_SIZE:
            for i in range(cls.MAX_LINES):
                offset = 8 + i * cls.ENTRY_SIZE
                ts_ns = struct.unpack("<q", data[offset:offset + 8])[0]
                raw_msg = data[offset + 8:offset + cls.ENTRY_SIZE].split(b"\x00", 1)[0]
                msg = raw_msg.decode("utf-8", errors="replace").strip()
                if ts_ns > 0 and msg:
                    dt = datetime.datetime.fromtimestamp(ts_ns / 1e9, tz=datetime.timezone.utc)
                    entries.append((dt, msg))
            entries.sort(key=lambda x: x[0])
        else:
            # Fallback string extraction if non-standard format
            text = data.decode("utf-8", errors="ignore")
            for m in re.findall(r"\[TUN\][^\x00\r\n]+", text):
                entries.append((datetime.datetime.now(datetime.timezone.utc), m.strip()))
        return magic, next_idx, entries

    @classmethod
    def analyze(cls, target_path="", cli_path=""):
        ws_dir = cls.find_windscribe_dir(cli_path=cli_path, custom_path=target_path)
        log_bin = ""
        if target_path and os.path.isfile(target_path) and target_path.lower().endswith(".bin"):
            log_bin = target_path
        elif ws_dir:
            for rel in (os.path.join("config", "log.bin"), "log.bin"):
                cand = os.path.join(ws_dir, rel)
                if os.path.isfile(cand):
                    log_bin = cand
                    break

        if not log_bin or not os.path.isfile(log_bin):
            return None, t("diag_not_found")

        base_dir = os.path.dirname(os.path.dirname(log_bin)) if os.path.basename(os.path.dirname(log_bin)).lower() == "config" else os.path.dirname(log_bin)
        try:
            magic, next_idx, entries = cls.parse_ringlog(log_bin)
        except Exception as e:
            return None, str(e)

        peers = Counter()
        ports = Counter()
        handshake_initiations = 0
        handshake_timeouts = 0
        handshake_success = 0
        os_info = "Unknown"
        driver_info = "Unknown"

        for _, msg in entries:
            if "Starting WireGuard/" in msg:
                os_info = msg.split("[WindscribeWireguard]")[-1].strip()
            elif "Using WireGuardNT/" in msg:
                driver_info = msg.split("[WindscribeWireguard]")[-1].strip()
            m_peer = re.search(r"peer \d+ \(([^)]+)\)", msg)
            if m_peer:
                ep = m_peer.group(1)
                peers[ep] += 1
                if ":" in ep:
                    ports[ep.rsplit(":", 1)[-1]] += 1
            if "Sending handshake initiation" in msg:
                handshake_initiations += 1
            elif "Handshake for peer" in msg and "did not complete" in msg:
                handshake_timeouts += 1
            elif "Receiving handshake response" in msg:
                handshake_success += 1

        lines = []
        lines.append(f"=== WINDSCRIBE DIAGNOSTIC REPORT (AutoScribe v{APP_VERSION}) ===")
        lines.append(f"Target File : {log_bin}")
        lines.append(f"Ringbuffer  : magic={hex(magic)}, write_index={next_idx}, valid_records={len(entries)}/{cls.MAX_LINES}")
        if entries:
            t_start = entries[0][0].strftime("%Y-%m-%d %H:%M:%S UTC")
            t_end = entries[-1][0].strftime("%Y-%m-%d %H:%M:%S UTC")
            lines.append(f"Time Range  : {t_start}  -->  {t_end}")
        lines.append(f"Environment : {os_info} | {driver_info}")
        lines.append("")
        lines.append("--- WIREGUARD / AMNEZIAWG HANDSHAKE SUMMARY ---")
        lines.append(f"  Handshake Initiations Sent : {handshake_initiations}")
        lines.append(f"  Handshake Responses (OK)   : {handshake_success}")
        lines.append(f"  Handshake Timeouts (5s)    : {handshake_timeouts}")
        lines.append(f"  Distinct Endpoints Tested  : {len(peers)}")
        if ports:
            port_summary = ", ".join(f"port {p} ({c}x)" for p, c in ports.most_common())
            lines.append(f"  Ports Contacted            : {port_summary}")
        if handshake_timeouts > 0 and handshake_success == 0:
            lines.append("  [!] DIAGNOSIS: 100% of WireGuard/AmneziaWG handshakes timed out.")
            lines.append("      UDP packets to these endpoints are being dropped/blocked by your ISP/firewall.")
            lines.append("      Recommendation: Test Stealth, WStunnel (port 443), or TCP protocols in AutoScribe.")
        lines.append("")

        if peers:
            lines.append("--- TOP CONTACTED ENDPOINTS (IP:PORT) ---")
            for ep, count in peers.most_common(15):
                lines.append(f"  {ep:<24} : {count} log events")
            lines.append("")

        # Check config.ovpn if present
        ovpn_path = os.path.join(base_dir, "config", "config.ovpn")
        if os.path.isfile(ovpn_path):
            lines.append("--- OPENVPN CONFIG (config/config.ovpn) ---")
            try:
                with open(ovpn_path, "r", encoding="utf-8", errors="replace") as f:
                    ovpn_txt = f.read()
                remotes = re.findall(r"^remote\s+.+$", ovpn_txt, flags=re.MULTILINE)
                protos = re.findall(r"^proto\s+.+$", ovpn_txt, flags=re.MULTILINE)
                ciphers = re.findall(r"^cipher\s+.+$", ovpn_txt, flags=re.MULTILINE)
                verify = re.findall(r"^verify-x509-name\s+.+$", ovpn_txt, flags=re.MULTILINE)
                dpi_flags = [flag for flag in ("udp-stuffing", "tcp-split-reset", "i1 ", "i2 ", "i3 ", "i4 ", "i5 ") if flag in ovpn_txt]
                for r in remotes + protos + ciphers + verify:
                    lines.append(f"  {r.strip()}")
                if dpi_flags:
                    lines.append(f"  Anti-DPI directives detected: {', '.join(dpi_flags)}")
            except Exception as e:
                lines.append(f"  Could not read config.ovpn: {e}")
            lines.append("")

        # Check wireguard_service.log if present
        wg_log = os.path.join(base_dir, "wireguard_service.log")
        if os.path.isfile(wg_log):
            lines.append("--- SERVICE LOG (wireguard_service.log) ---")
            try:
                with open(wg_log, "r", encoding="utf-8", errors="replace") as f:
                    for l in f.read().splitlines()[-10:]:
                        lines.append(f"  {l.strip()}")
            except Exception:
                pass
            lines.append("")

        lines.append("--- LAST 20 WIRE-LEVEL EVENTS (log.bin) ---")
        for dt, msg in entries[-20:]:
            lines.append(f"  {dt.strftime('%H:%M:%S.%f')[:-3]} UTC | {msg}")

        return "\n".join(lines), None


# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------
class DatabaseManager:
    EXPORT_COLUMNS = ["city", "location", "country", "protocol", "port", "status",
                      "duration", "ping", "packet_loss", "http_ms", "speed_kbps", "vpn_ip",
                      "profile_name", "timestamp"]

    def __init__(self, app=None):
        self.app = app
        self.lock = threading.RLock()
        self.conn = sqlite3.connect(DB_FILE, timeout=15.0, check_same_thread=False)
        try:
            self.conn.execute("PRAGMA journal_mode=WAL")
        except Exception:
            pass
        self.cursor = self.conn.cursor()
        self.create_table()

    def create_table(self):
        with self.lock:
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS tests (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    location TEXT,
                    city TEXT,
                    country TEXT,
                    protocol TEXT,
                    port INTEGER,
                    status TEXT,
                    duration REAL,
                    ping REAL,
                    packet_loss REAL,
                    profile_name TEXT,
                    timestamp TEXT,
                    UNIQUE(location, city, country, protocol, port)
                )
            ''')
            self.conn.commit()
            # Older databases from the speedtest version: add the new column if missing.
            cols = [r[1] for r in self.cursor.execute("PRAGMA table_info(tests)").fetchall()]
            if "packet_loss" not in cols:
                self.cursor.execute("ALTER TABLE tests ADD COLUMN packet_loss REAL")
                self.conn.commit()
            if "http_ms" not in cols:
                self.cursor.execute("ALTER TABLE tests ADD COLUMN http_ms REAL")
                self.conn.commit()
            if "speed_kbps" not in cols:
                self.cursor.execute("ALTER TABLE tests ADD COLUMN speed_kbps REAL")
                self.conn.commit()
            if "vpn_ip" not in cols:
                self.cursor.execute("ALTER TABLE tests ADD COLUMN vpn_ip TEXT")
                self.conn.commit()

    def record_result(self, location, city, country, proto, port, status, duration, ping, loss, profile_name,
                      http_ms=None, speed_kbps=None, vpn_ip=None):
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self.lock:
            try:
                self.cursor.execute('''
                    INSERT OR REPLACE INTO tests
                    (location, city, country, protocol, port, status, duration, ping, packet_loss, http_ms, speed_kbps, vpn_ip, profile_name, timestamp)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (location, city, country, proto, port, status, round(duration, 2), ping, loss, http_ms,
                      speed_kbps, vpn_ip or "", profile_name, timestamp))
                self.conn.commit()
                return True
            except Exception as e:
                if self.app:
                    self.app.post(self.app.log_message, f"DB ERROR: {e}", "FAILURE")
                return False

    def get_row_count(self):
        with self.lock:
            try:
                self.cursor.execute("SELECT COUNT(*) FROM tests")
                return self.cursor.fetchone()[0]
            except Exception:
                return 0

    def is_tested(self, location, city, country, proto, port):
        with self.lock:
            self.cursor.execute(
                "SELECT 1 FROM tests WHERE location=? AND city=? AND country=? AND protocol=? AND port=?",
                (location, city, country, proto, port))
            return self.cursor.fetchone() is not None

    def fetch_results(self):
        with self.lock:
            self.cursor.execute(
                "SELECT city, location, country, protocol, port, status, duration, ping, packet_loss, http_ms, speed_kbps, vpn_ip "
                "FROM tests ORDER BY id")
            return self.cursor.fetchall()

    def export_to_csv(self, current_profile_name="Manual"):
        try:
            os.makedirs(REPORTS_DIR, exist_ok=True)
        except OSError as e:
            return -1, f"Failed to create directory: {e}"

        max_id = 0
        for f in os.listdir(REPORTS_DIR):
            if f.endswith(".csv"):
                head = f.split("_")[0]
                if head.isdigit():
                    max_id = max(max_id, int(head))

        ts = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        safe_profile = "".join(c for c in current_profile_name if c.isalnum() or c in (" ", "-", "_")).strip()
        safe_profile = safe_profile.replace(" ", "_") or "Manual"
        csv_file = os.path.join(REPORTS_DIR, f"{max_id + 1}_{safe_profile}_{ts}.csv")

        with self.lock:
            self.cursor.execute(f"SELECT {', '.join(self.EXPORT_COLUMNS)} FROM tests ORDER BY id")
            rows = self.cursor.fetchall()

        try:
            with open(csv_file, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(self.EXPORT_COLUMNS)
                writer.writerows(rows)
            return len(rows), csv_file
        except PermissionError:
            return -1, "File Open Error - Close the file if open."

    def clear_db(self):
        with self.lock:
            self.cursor.execute("DELETE FROM tests")
            self.conn.commit()


# ---------------------------------------------------------------------------
# Worker
# ---------------------------------------------------------------------------
class WindscribeWorker:
    # Steps of one test, as shown in the UI.
    DISCONNECT, CONNECT, SETTLE, PING, HOLD = range(5)

    def __init__(self, app_instance, cli_cmd=DEFAULT_CLI):
        self.app = app_instance
        self.db = DatabaseManager(app=app_instance)
        self.pinger = PingRunner()
        self.http_checker = HttpChecker()
        self.stop_event = threading.Event()
        self.running = False
        self.cli_cmd = cli_cmd
        self.keep_firewall = False

    # -- helpers (all UI access goes through app.post, never touches widgets directly) --
    def log(self, msg, tag="INFO"):
        self.app.post(self.app.log_message, msg, tag)

    def phase(self, idx, state, secs=None):
        self.app.post(self.app.set_phase, idx, state, secs)

    def run_cli(self, args, timeout=30):
        cmd = [self.cli_cmd] + args
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace",
                                    timeout=timeout, **hidden_process_kwargs())
            return result.returncode, result.stdout
        except subprocess.TimeoutExpired:
            return -1, ""
        except Exception as e:
            self.log(f"CLI Error: {e}", "FAILURE")
            return -1, ""

    @staticmethod
    def is_connected_output(out):
        up = out.upper()
        return (
            "CONNECTED" in up
            and "DISCONNECTED" not in up
            and "CONNECTING" not in up
            and "(CHECKING THE CONNECTION)" not in up
            and "(NETWORK INTERFERENCE" not in up
        )

    @staticmethod
    def extract_vpn_ip(out):
        """Extracts '<ip> (VPN)' or IP line from `windscribe-cli status` output."""
        m = re.search(r"(\d{1,3}(?:\.\d{1,3}){3})\s*\(VPN\)", out, re.IGNORECASE)
        if m:
            return m.group(1)
        m2 = re.search(r"^IP\s+([0-9a-fA-F:.]+)", out, re.MULTILINE | re.IGNORECASE)
        if m2 and "(public)" not in out.lower():
            return m2.group(1)
        return ""

    def rotate_ip(self):
        """Calls `windscribe-cli ip rotate` to request a fresh IP on the active tunnel."""
        rc, out = self.run_cli(["ip", "rotate"], timeout=20)
        if rc == 0 and "IP rotated" in out:
            _, st = self.run_cli(["status"])
            return True, self.extract_vpn_ip(st)
        return False, ""

    def ensure_disconnected(self, keep_firewall=None):
        if keep_firewall is None:
            keep_firewall = self.keep_firewall
        for _ in range(5):
            _, out = self.run_cli(["status"])
            if "DISCONNECTED" in out.upper():
                return True
            if not keep_firewall:
                self.run_cli(["firewall", "off"])
            self.run_cli(["disconnect"])
            if self.stop_event.wait(3):
                break
        _, out = self.run_cli(["status"])
        return "DISCONNECTED" in out.upper()

    def wait_for_connection(self, start_time, timeout):
        while time.time() - start_time < timeout:
            _, out = self.run_cli(["status"])
            if self.is_connected_output(out):
                return True, time.time() - start_time
            if self.stop_event.wait(1):
                return False, 0.0
        return False, 0.0

    def verify_stability_hold(self, hold_secs, ping_host, http_check, http_url):
        """Multi-wave anti-DPI stability test.
        Holds the connection for `hold_secs` seconds, polling CLI status and probing traffic in waves
        to detect Iranian firewall delayed TCP RST / UDP blackholing that happens 3-15s after connect.
        Returns (status_override_or_None, latest_ping_res_or_None, latest_http_ms_or_None, elapsed_secs).
        """
        t0 = time.time()
        hold_secs = max(5, int(hold_secs))
        # Probe at ~halfway and at the end of hold window, while checking CLI status every 2.5s
        last_ping_res = None
        last_http_ms = None
        wave_interval = max(4.0, hold_secs / 2.0)
        next_wave = t0 + min(4.0, wave_interval)
        wave_num = 0

        while time.time() - t0 < hold_secs:
            if self.stop_event.wait(1.0):
                return "STOPPED", last_ping_res, last_http_ms, time.time() - t0

            _, st_out = self.run_cli(["status"])
            if not self.is_connected_output(st_out):
                self.log(f"[Anti-DPI Hold] Tunnel dropped after {time.time() - t0:.1f}s! CLI status is no longer Connected (DPI Reset).", "FAILURE")
                return "DPI_RESET", last_ping_res, last_http_ms, time.time() - t0

            now = time.time()
            if now >= next_wave or (hold_secs - (now - t0)) <= 1.2:
                wave_num += 1
                next_wave = now + wave_interval
                p_res, _ = self.pinger.run(ping_host, count=2, reply_timeout_ms=1500)
                h_ms = None
                if http_check:
                    h_ms, _ = self.http_checker.check(http_url, timeout=4.0)
                if p_res:
                    last_ping_res = p_res
                if h_ms is not None:
                    last_http_ms = h_ms

                if not p_res and h_ms is None:
                    # Re-check CLI status immediately: did the tunnel drop or did traffic get blackholed?
                    _, st_out2 = self.run_cli(["status"])
                    if not self.is_connected_output(st_out2):
                        self.log(f"[Anti-DPI Hold] Wave {wave_num} (@{now - t0:.1f}s): Connection reset by firewall (DPI_RESET).", "FAILURE")
                        return "DPI_RESET", last_ping_res, last_http_ms, time.time() - t0
                    self.log(f"[Anti-DPI Hold] Wave {wave_num} (@{now - t0:.1f}s): Tunnel stayed up but traffic is blackholed (0 replies).", "FAILURE")
                    return "BLACKHOLED", last_ping_res, last_http_ms, time.time() - t0
                else:
                    msg_parts = []
                    if p_res:
                        msg_parts.append(f"ping {p_res['avg']:.0f}ms")
                    if h_ms is not None:
                        msg_parts.append(f"HTTP {h_ms:.0f}ms")
                    self.log(f"[Anti-DPI Hold] Wave {wave_num} (@{now - t0:.1f}s) survived: {', '.join(msg_parts)}", "INFO")

        return None, last_ping_res, last_http_ms, time.time() - t0

    # -- job control --
    def start(self, work_plan, opts):
        self.stop_event.clear()
        self.running = True
        threading.Thread(target=self._run, args=(work_plan, opts), daemon=True).start()

    def stop(self):
        self.stop_event.set()
        self.log("Stopping after the current step...", "WARN")

    def connect_to(self, result, timeout):
        """Connects to a single route picked from the results."""
        self.stop_event.clear()
        self.running = True
        threading.Thread(target=self._connect_one, args=(result, timeout), daemon=True).start()

    def disconnect(self):
        self.stop_event.clear()
        self.running = True
        threading.Thread(target=self._disconnect, daemon=True).start()

    def _connect_one(self, r, timeout):
        connected = False
        dropped_by_dpi = False
        route = f"{r['proto']}:{r['port']}"
        disp = loc_name(r["city"], r.get("node", ""))
        try:
            self.log(f"Connecting to {disp} via {route}", "HEADER")
            self.phase(self.DISCONNECT, "active")
            t0 = time.time()
            if not self.ensure_disconnected():
                self.phase(self.DISCONNECT, "fail")
                self.log("Could not disconnect the current session first.", "FAILURE")
                return
            self.phase(self.DISCONNECT, "done", time.time() - t0)
            self.phase(self.CONNECT, "active")
            start_ts = time.time()
            target_loc = r.get("node") or r["city"]
            rc, out = self.run_cli(["connect", "-n", target_loc, route], timeout=timeout + 15)
            if rc != 0 or "Location does not exist" in out:
                if target_loc != r["city"]:
                    self.run_cli(["connect", "-n", r["city"], route], timeout=timeout + 15)
            connected, duration = self.wait_for_connection(start_ts, timeout)
            vpn_ip = ""
            if connected:
                self.phase(self.CONNECT, "done", duration)
                self.log(f"Connected to {disp} via {route} in {duration:.1f}s", "SUCCESS")
                # Post-connect watchdog: verify connection does not immediately get reset by DPI within 5s
                self.phase(self.HOLD, "active")
                h0 = time.time()
                for _ in range(5):
                    if self.stop_event.wait(1.0):
                        break
                    _, st_out = self.run_cli(["status"])
                    if not self.is_connected_output(st_out):
                        connected = False
                        dropped_by_dpi = True
                        break
                    vpn_ip = self.extract_vpn_ip(st_out) or vpn_ip
                if connected:
                    if vpn_ip:
                        r["vpn_ip"] = vpn_ip
                    self.phase(self.HOLD, "done", time.time() - h0)
                else:
                    self.phase(self.HOLD, "fail", time.time() - h0)
                    self.log(f"Connection to {disp} via {route} was reset by firewall after {time.time() - h0:.1f}s (DPI_RESET)!", "FAILURE")
            else:
                self.phase(self.CONNECT, "fail")
                self.log(f"Could not connect to {disp} via {route}", "FAILURE")
        except Exception as e:
            self.log(f"Critical Error: {e}", "FAILURE")
        finally:
            self.running = False
            self.app.post(self.app.manual_connect_finished, r, connected, dropped_by_dpi)

    def _disconnect(self):
        done = False
        try:
            done = self.ensure_disconnected()
            self.log("Disconnected." if done else "Could not disconnect.", "INFO" if done else "FAILURE")
        finally:
            self.running = False
            self.app.post(self.app.disconnect_finished, done)

    def _build_tasks(self, work_plan, opts):
        if opts.get("explicit_tasks"):
            explicit = opts["explicit_tasks"]
            locs = [t[0] for t in explicit]
            return locs, list(explicit)
        keys = opts["keys"]
        locations = [l for l in LocationManager.load_locations() if not keys or loc_key(l) in keys]
        if opts.get("free_only"):
            locations = [l for l in locations if not l.get("is_premium", False)]
        if opts.get("dedup_cities"):
            seen_cities = set()
            deduped = []
            for l in locations:
                ck = (l["country"].lower(), l["city"].lower())
                if ck not in seen_cities:
                    seen_cities.add(ck)
                    deduped.append(l)
            locations = deduped
        if opts["random_cities"]:
            random.shuffle(locations)
        tasks = [(loc, proto, port) for loc in locations for proto, ports in work_plan.items() for port in ports]
        if opts["chaos_mode"]:
            random.shuffle(tasks)
        return locations, tasks

    def _wait_for_internet(self, firewall_only=False):
        """
        Checks OS-level + external internet connectivity.
        If offline, pauses the scan (without stopping it) and polls every 5s
        until connectivity is restored or the user clicks Stop.
        Returns True if online/restored, False if stopped by user.
        """
        online, reason = InternetMonitor.has_internet(firewall_only=firewall_only)
        if online:
            return True

        self.log(f"[Network] Internet disconnected ({reason}). Pausing scan until connection returns...", "WARN")
        self.app.post(self.app.set_network_paused, True)
        while not self.stop_event.is_set():
            if self.stop_event.wait(5.0):
                self.app.post(self.app.set_network_paused, False)
                return False
            online, _ = InternetMonitor.has_internet(firewall_only=firewall_only)
            if online:
                # Brief settle wait so Wi-Fi/DHCP/DNS stabilizes before resuming
                if self.stop_event.wait(2.0):
                    self.app.post(self.app.set_network_paused, False)
                    return False
                online2, _ = InternetMonitor.has_internet(firewall_only=firewall_only)
                if online2:
                    self.log("[Network] Internet connection restored — resuming scan!", "SUCCESS")
                    self.app.post(self.app.set_network_paused, False)
                    return True
        self.app.post(self.app.set_network_paused, False)
        return False

    def _run(self, work_plan, opts):
        kept_connection = None
        kept_route = None
        ok = fail = executed = 0
        sleep_guard = SleepPreventer()
        sleep_guard.acquire()
        try:
            locations, tasks = self._build_tasks(work_plan, opts)
            if not locations:
                self.log(f"No locations match the selection (or locations.json is missing at {LOCATIONS_FILE})",
                         "FAILURE")
                return

            total = len(tasks)
            self.log(f"Queued {len(locations)} locations, {total} tests", "HEADER")

            self.keep_firewall = bool(opts.get("keep_firewall", False))
            auto_pilot = bool(opts.get("auto_pilot", False))
            # Disable heuristic fast_skip under Auto-Pilot so Bandit receives full feedback
            fast_skip = bool(opts.get("fast_skip", False)) and not auto_pilot
            smart_ai = bool(opts.get("smart_ai", False))
            loc_proto_Streaks = Counter()   # (country, city, node, proto) -> consecutive fails
            global_proto_streaks = Counter()  # proto -> consecutive fails when 0 successes
            global_proto_ok = Counter()       # proto -> total successes

            ws_dir = LogAnalyzer.find_windscribe_dir(cli_path=self.cli_cmd)
            bandit = AdaptiveBanditScheduler(DB_FILE) if (smart_ai or auto_pilot) else None
            autopilot = AutoPilotController(bandit) if (auto_pilot and bandit) else None
            if bandit:
                self.log(f"[AI] Network context: {bandit.network_id} | Adaptive DPI learning active", "INFO")
                if getattr(bandit, "bootstrapped_count", 0) > 0:
                    self.log(f"[AI] Imported {bandit.bootstrapped_count} historical test records into Bandit memory", "INFO")
            if not self._wait_for_internet(firewall_only=self.keep_firewall):
                return

            if autopilot:
                port_map = SocketProber.probe_ports((443, 8443, 80, 587, 22, 8080), timeout=1.0)
                bandit.seed_port_probe(port_map)
                blocked_p = [str(p) for p, st in sorted(port_map.items()) if st in ("RST", "DROP")]
                if blocked_p:
                    self.log(f"[AI Pre-Flight] TCP probe flagged blocked/dropped ports: {', '.join(blocked_p)}", "WARN")
                ap_to, ap_hold = autopilot.get_dynamic_timings()
                self.log(f"[AI Auto-Pilot] Initial profile: {autopilot.strategy_label()} (timeout={ap_to}s, hold={ap_hold}s)", "HEADER")
                self.app.post(self.app.update_ai_status, autopilot.current_strategy, bandit.get_network_summary())

            remaining_tasks = list(tasks)
            i = 0
            while remaining_tasks:
                if self.stop_event.is_set():
                    break
                i += 1
                if autopilot:
                    ap_to, ap_hold = autopilot.get_dynamic_timings()
                    opts["timeout"] = ap_to
                    opts["hold_seconds"] = ap_hold
                    opts["anti_dpi_hold"] = True
                    pick_idx, ai_reason = autopilot.select_next_index(remaining_tasks, opts.get("priority_order"))
                    loc, proto, port = remaining_tasks.pop(pick_idx)
                    self.log(f"[{i}/{total}] {ai_reason}", "INFO")
                elif bandit:
                    pick_idx, ai_reason = bandit.select_next_index(remaining_tasks, opts.get("priority_order"))
                    loc, proto, port = remaining_tasks.pop(pick_idx)
                    self.log(f"[{i}/{total}] {ai_reason}", "INFO")
                else:
                    loc, proto, port = remaining_tasks.pop(0)

                city, node, country = loc["city"], loc["location"], loc["country"]
                target_loc = city if opts.get("dedup_cities") or not node else node
                disp_loc = loc_name(city, node)
                route = f"{proto}:{port}"

                if opts["resume"] and self.db.is_tested(node, city, country, proto, port):
                    continue

                if fast_skip:
                    lp_key = (country, city, node, proto)
                    if global_proto_ok[proto] == 0 and global_proto_streaks[proto] >= 6:
                        self.log(f"[{i}/{total}] Fast-Skip {disp_loc} ({route}): protocol {PROTO_NAMES.get(proto, proto)} failed 6x globally", "WARN")
                        continue
                    if loc_proto_Streaks[lp_key] >= 2:
                        self.log(f"[{i}/{total}] Fast-Skip {disp_loc} ({route}): {PROTO_NAMES.get(proto, proto)} failed 2 ports on this server", "WARN")
                        continue

                executed += 1
                self.app.post(self.app.begin_test, i, total, executed, city, node, country, route)
                self.log(f"[{i}/{total}] {disp_loc} ({country}) via {route}", "HEADER")

                try:
                    self.phase(self.DISCONNECT, "active")
                    t0 = time.time()
                    if not self.ensure_disconnected(self.keep_firewall):
                        self.phase(self.DISCONNECT, "fail")
                        self.log("Could not disconnect, skipping this test.", "FAILURE")
                        continue
                    self.phase(self.DISCONNECT, "done", time.time() - t0)
                    if self.stop_event.is_set():
                        break

                    # Check OS/internet connectivity before attempting VPN connect; pause & resume if offline
                    online, _ = InternetMonitor.has_internet(firewall_only=self.keep_firewall)
                    if not online:
                        remaining_tasks.insert(0, (loc, proto, port))
                        i -= 1
                        executed -= 1
                        if not self._wait_for_internet(firewall_only=self.keep_firewall):
                            break
                        continue
                except Exception as pre_err:
                    self.log(f"[Recoverable Error] Pre-test step failed: {pre_err}; continuing...", "WARN")
                    self.stop_event.wait(2)
                    continue

                try:
                    self.phase(self.CONNECT, "active")
                    start_ts = time.time()
                    rc, cmd_out = self.run_cli(["connect", "-n", target_loc, route], timeout=opts["timeout"] + 15)
                    if (rc != 0 or "Location does not exist" in cmd_out) and target_loc != city:
                        self.run_cli(["connect", "-n", city, route], timeout=opts["timeout"] + 15)
                    self.stop_event.wait(1)

                    _, status_out = self.run_cli(["status"])
                    if "Location does not exist" in status_out or "is disabled" in status_out or "Please upgrade to a Pro account" in status_out:
                        self.phase(self.CONNECT, "fail")
                        self.log(f"{disp_loc} is unavailable or Pro-only, skipping.", "FAILURE")
                        self.db.record_result(node, city, country, proto, port, "INVALID_LOC", 0, None, None,
                                              opts["profile_name"], None)
                        self.app.post(self.app.add_result_row, city, node, country, proto, port,
                                      "INVALID_LOC", 0, None, None, None, None, "")
                        if bandit:
                            err_cls, _ = FailureClassifier.classify(proto, port, "INVALID_LOC", 0, cli_out=status_out, ws_dir=ws_dir)
                            bandit.record_feedback(loc, proto, port, err_cls)
                        fail += 1
                        continue

                    connected, duration = self.wait_for_connection(start_ts, opts["timeout"])

                    # User pressed Stop while we were still connecting: undo and leave, don't record a bogus failure.
                    if self.stop_event.is_set() and not connected:
                        self.run_cli(["disconnect"])
                        self.log("Stopped while connecting; this test was not recorded.", "WARN")
                        break

                    ping_avg = loss = http_ms = speed_kbps = None
                    vpn_ip = ""
                    status_str = "FAILURE"
                    if connected:
                        status_str = "SUCCESS"
                        self.phase(self.CONNECT, "done", duration)
                        _, st_now = self.run_cli(["status"])
                        vpn_ip = self.extract_vpn_ip(st_now)
                        ip_note = f" [IP: {vpn_ip}]" if vpn_ip else ""
                        self.log(f"Connected in {duration:.2f}s{ip_note}", "SUCCESS")

                        if opts["settle"] > 0:
                            self.phase(self.SETTLE, "active")
                            self.stop_event.wait(opts["settle"])
                            self.phase(self.SETTLE, "done", opts["settle"])
                        else:
                            self.phase(self.SETTLE, "skip")

                        self.phase(self.PING, "active")
                        t0 = time.time()
                        result, err = self.pinger.run(opts["ping_host"], opts["ping_count"])
                        if opts.get("http_check"):
                            http_ms, http_err = self.http_checker.check(opts.get("http_url"))
                            if http_ms is not None:
                                self.log(f"HTTP/TLS multi-check OK in {http_ms:.0f} ms", "SUCCESS")
                            else:
                                self.log(f"HTTP/TLS check failed: {http_err}", "WARN")
                                if not result:
                                    status_str = "HTTP_FAIL"
                        if opts.get("speed_burst") and status_str == "SUCCESS":
                            speed_kbps, sp_err = self.http_checker.run_speed_burst()
                            if speed_kbps is not None:
                                self.log(f"Speed burst OK: {speed_kbps:.0f} KB/s", "SUCCESS")
                            else:
                                self.log(f"Speed burst throttled/dropped: {sp_err}", "WARN")
                                if not result and http_ms is None:
                                    status_str = "BLACKHOLED"
                        # Auto-Pilot: if L7 HTTP blocked or severely throttled, try IP rotation once before failing
                        if autopilot and (status_str == "HTTP_FAIL" or (speed_kbps is not None and speed_kbps < 15.0)):
                            self.log("[AI Auto-Pilot] L7 block/throttling detected; trying windscribe-cli ip rotate...", "WARN")
                            rotated, new_ip = self.rotate_ip()
                            if rotated:
                                vpn_ip = new_ip or vpn_ip
                                self.stop_event.wait(1.5)
                                if opts.get("http_check"):
                                    h2, _ = self.http_checker.check(opts.get("http_url"))
                                    if h2 is not None:
                                        http_ms = h2
                                        status_str = "SUCCESS"
                                        self.log(f"[AI Auto-Pilot] IP rotate fixed L7 access (HTTP {http_ms:.0f} ms, IP: {vpn_ip})", "SUCCESS")
                                if opts.get("speed_burst") and status_str == "SUCCESS":
                                    sp2, _ = self.http_checker.run_speed_burst()
                                    if sp2 is not None:
                                        speed_kbps = sp2
                        self.phase(self.PING, "done" if (result or http_ms is not None) else "fail", time.time() - t0)
                        self.app.post(self.app.set_ping, result, http_ms, speed_kbps)
                        if result:
                            ping_avg, loss = result["avg"], result["loss"]
                            self.log(f"Ping avg {ping_avg:.0f} ms (min {result['min']:.0f} / max {result['max']:.0f}), "
                                     f"loss {loss:.0f}%", "INFO")
                        else:
                            self.log(f"Ping failed: {err}", "WARN")
                        # Phase 5: Anti-DPI Stability Hold (multi-wave check against delayed firewall drop)
                        if status_str == "SUCCESS" and (result or http_ms is not None) and opts.get("anti_dpi_hold"):
                            self.phase(self.HOLD, "active")
                            hold_override, w_ping, w_http, h_elapsed = self.verify_stability_hold(
                                opts.get("hold_seconds", 15), opts["ping_host"],
                                opts.get("http_check", False), opts.get("http_url")
                            )
                            if hold_override == "STOPPED":
                                self.run_cli(["disconnect"])
                                self.log("Stopped during stability hold; test was not recorded.", "WARN")
                                break
                            elif hold_override in ("DPI_RESET", "BLACKHOLED"):
                                status_str = hold_override
                                self.phase(self.HOLD, "fail", h_elapsed)
                            else:
                                self.phase(self.HOLD, "done", h_elapsed)
                                if w_ping:
                                    ping_avg, loss = w_ping["avg"], w_ping["loss"]
                                if w_http is not None:
                                    http_ms = w_http
                                if not vpn_ip:
                                    _, st_end = self.run_cli(["status"])
                                    vpn_ip = self.extract_vpn_ip(st_end)
                                self.app.post(self.app.set_ping, w_ping or result, http_ms, speed_kbps)
                        else:
                            self.phase(self.HOLD, "skip")

                        if status_str == "SUCCESS":
                            ok += 1
                            loc_proto_Streaks[(country, city, node, proto)] = 0
                            global_proto_streaks[proto] = 0
                            global_proto_ok[proto] += 1
                        else:
                            fail += 1
                            loc_proto_Streaks[(country, city, node, proto)] += 1
                            global_proto_streaks[proto] += 1
                    else:
                        self.run_cli(["disconnect"])
                        if not self.stop_event.is_set():
                            mid_online, _ = InternetMonitor.has_internet(firewall_only=self.keep_firewall)
                            if not mid_online:
                                self.log(f"[Network] Internet dropped during {disp_loc} ({route}); will retry after reconnect.", "WARN")
                                remaining_tasks.insert(0, (loc, proto, port))
                                i -= 1
                                executed -= 1
                                if not self._wait_for_internet(firewall_only=self.keep_firewall):
                                    break
                                continue
                        fail += 1
                        loc_proto_Streaks[(country, city, node, proto)] += 1
                        global_proto_streaks[proto] += 1
                        self.phase(self.CONNECT, "fail", opts["timeout"])
                        self.log(f"Timed out on {route}", "FAILURE")

                    self.db.record_result(node, city, country, proto, port, status_str, duration, ping_avg, loss,
                                          opts["profile_name"], http_ms, speed_kbps, vpn_ip)
                    self.app.post(self.app.add_result_row, city, node, country, proto, port, status_str,
                                  duration, ping_avg, loss, http_ms, speed_kbps, vpn_ip)
                    if bandit:
                        err_cls, err_detail = FailureClassifier.classify(
                            proto, port, status_str, duration,
                            cli_out=cmd_out or status_out,
                            ping_res=(None if ping_avg is None else {"avg": ping_avg, "loss": loss}),
                            http_ms=http_ms, speed_kbps=speed_kbps, ws_dir=ws_dir,
                        )
                        bandit.record_feedback(loc, proto, port, err_cls, ping_ms=ping_avg, http_ms=http_ms, speed_kbps=speed_kbps)
                        if status_str != "SUCCESS":
                            self.log(f"[AI Feedback] {err_cls}: {err_detail}", "WARN")
                            self.app.post(self.app.record_ai_error, f"{disp_loc} ({route}) -> {err_cls}: {err_detail}")
                        if autopilot:
                            escalated = autopilot.record_and_maybe_escalate(err_cls, country=country, proto=proto)
                            if escalated:
                                self.log(f"[AI Auto-Pilot] Escalating anti-censorship strategy -> {autopilot.strategy_label()}", "HEADER")
                            self.app.post(self.app.update_ai_status, autopilot.current_strategy, bandit.get_network_summary())
                        elif bandit:
                            self.app.post(self.app.update_ai_status, "AI_BANDIT", bandit.get_network_summary())

                    if status_str == "SUCCESS" and opts["stop_on_success"]:
                        kept_connection = f"{loc_name(city, node)} · {route}"
                        kept_route = {
                            "city": city, "node": node or "", "country": country,
                            "proto": proto, "port": port, "status": status_str,
                            "duration": duration or 0, "ping": ping_avg, "loss": loss,
                            "http_ms": http_ms, "speed_kbps": speed_kbps, "vpn_ip": vpn_ip or "",
                        }
                        self.log(f"Stop on success: staying connected to {kept_connection}.", "SUCCESS")
                        break
                    if autopilot and autopilot.target_routes > 0 and status_str == "SUCCESS" and ok >= autopilot.target_routes:
                        self.log(f"[AI Auto-Pilot] Found {ok} verified working routes; stopping scan early (best routes saved).", "SUCCESS")
                        self.run_cli(["disconnect"])
                        break

                    self.run_cli(["disconnect"])
                    self.stop_event.wait(2)

                except Exception as iter_err:
                    self.log(f"[Recoverable Error] {disp_loc} ({route}): {iter_err}; continuing scan...", "WARN")
                    try:
                        self.run_cli(["disconnect"])
                    except Exception:
                        pass
                    self.stop_event.wait(2)
                    continue

        except Exception as e:
            self.log(f"Critical Error: {e}", "FAILURE")
        finally:
            sleep_guard.release()
            if "bandit" in locals() and bandit is not None:
                bandit.close()
            self.running = False
            self.app.post(self.app.job_finished, kept_connection, ok, fail, kept_route)


# ---------------------------------------------------------------------------
# UI helpers
# ---------------------------------------------------------------------------
SCALE = 1.0  # CustomTkinter's window scaling, set once the window exists
_FONT_CACHE = {}


def measure(font, text):
    """Pixel width of text in a CustomTkinter font tuple (CustomTkinter sizes fonts in scaled pixels)."""
    font = tuple(font or (SANS, 13))
    f = _FONT_CACHE.get(font)
    if f is None:
        f = tkfont.Font(family=font[0], size=-round(font[1] * SCALE),
                        weight="bold" if "bold" in font[2:] else "normal")
        _FONT_CACHE[font] = f
    return f.measure(text)


def display_text(text, wraplength=0, font=None, px_width=None):
    """Text as it should be handed to Tk: Farsi is wrapped in reading order, then put in display order."""
    if not i18n.RTL or not isinstance(text, str) or not text:
        return text
    width = px_width or (wraplength * SCALE if wraplength else 0)
    if width:
        text = i18n.wrap(text, lambda s: measure(font, s), width)
    return vis(text)


def _hook_text(cls, keys=("text",)):
    """Runs every text a widget class displays through display_text(), so call sites pass plain strings."""
    original_init, original_configure = cls.__init__, cls.configure

    def __init__(self, *args, **kw):
        wrap_len = kw.get("wraplength", 0)
        if i18n.RTL:
            for key in keys:
                if key in kw:
                    kw[key] = display_text(kw[key], wrap_len, kw.get("font"))
            if wrap_len:
                kw["wraplength"] = 0  # already wrapped; Tk would re-wrap the display-order text from the wrong end
        original_init(self, *args, **kw)
        self._i18n_wrap, self._i18n_font = wrap_len, kw.get("font")

    def configure(self, require_redraw=False, **kw):
        if i18n.RTL:
            if "font" in kw:
                self._i18n_font = kw["font"]
            for key in keys:
                if key in kw:
                    kw[key] = display_text(kw[key], getattr(self, "_i18n_wrap", 0), getattr(self, "_i18n_font", None))
        return original_configure(self, require_redraw=require_redraw, **kw)

    cls.__init__, cls.configure = __init__, configure


_hook_text(ctk.CTkLabel)
_hook_text(ctk.CTkButton)
_hook_text(ctk.CTkEntry, keys=("placeholder_text",))


# Layout direction. Farsi mirrors the whole window, so every "left"/"right" goes through these.
def start():
    return "right" if i18n.RTL else "left"


def end():
    return "left" if i18n.RTL else "right"


def a_start():
    return "e" if i18n.RTL else "w"


def a_end():
    return "w" if i18n.RTL else "e"


def pads(first, second):
    """(start, end) padding, mirrored for RTL."""
    return (second, first) if i18n.RTL else (first, second)


def gcol(i, n):
    return n - 1 - i if i18n.RTL else i


def justify():
    return "right" if i18n.RTL else "left"


def frame(parent, **kw):
    kw.setdefault("fg_color", "transparent")
    return ctk.CTkFrame(parent, corner_radius=kw.pop("corner_radius", 0), **kw)


def card(parent, **kw):
    return ctk.CTkFrame(parent, fg_color=kw.pop("fg_color", CARD), corner_radius=kw.pop("corner_radius", 14),
                        border_width=1, border_color=kw.pop("border_color", BORDER), **kw)


def caps(parent, text, color=MUTED):
    return ctk.CTkLabel(parent, text=text.upper(), font=sans(10, True), text_color=color, anchor=a_start())


def label(parent, text="", size=12, color=TEXT, bold=False, font=None, **kw):
    kw.setdefault("justify", justify())
    return ctk.CTkLabel(parent, text=text, font=font or sans(size, bold), text_color=kw.pop("text_color", color),
                        anchor=kw.pop("anchor", a_start()), **kw)


def divider(parent):
    return ctk.CTkFrame(parent, fg_color=BORDER, height=1, corner_radius=0)


def ghost_button(parent, text, command, width=70, height=32, font=None, **kw):
    return ctk.CTkButton(parent, text=text, command=command, width=width, height=height,
                         corner_radius=kw.pop("corner_radius", 8), fg_color=kw.pop("fg_color", CARD),
                         border_width=1, border_color=kw.pop("border_color", BORDER_2), hover_color=HOVER,
                         text_color=kw.pop("text_color", TEXT), text_color_disabled=DIM,
                         font=font or sans(12), **kw)


def icon_button(parent, name, command, size=32, icon_size=13, **kw):
    return ghost_button(parent, icon(name), command, width=size, height=size, font=icon_font(icon_size), **kw)


def primary_button(parent, text, command, width=140, height=40, **kw):
    return ctk.CTkButton(parent, text=text, command=command, width=width, height=height, corner_radius=9,
                         fg_color=ACCENT, hover_color=ACCENT_HOVER, text_color=ON_ACCENT,
                         text_color_disabled="#3B5870", font=sans(13, True), **kw)


def chip(parent, text=""):
    return ctk.CTkLabel(parent, text=f" {text} ", font=mono(11), fg_color=CHIP, text_color=CHIP_TEXT,
                        corner_radius=6, height=22)


def entry(parent, height=34, size=12, rtl_text=True, **kw):
    """Entry box; text the user types in their language is right-aligned in Farsi, paths and numbers are not."""
    return ctk.CTkEntry(parent, height=height, fg_color=kw.pop("fg_color", INPUT), border_color=BORDER_2,
                        font=sans(size), justify="right" if i18n.RTL and rtl_text else "left", **kw)


class Bar(ctk.CTkProgressBar):
    """Progress bar that fills from the right in Farsi (by swapping the fill and track colours)."""

    def __init__(self, parent, track, fill, **kw):
        self._track, self._fill, self._value = track, fill, 0.0
        super().__init__(parent, fg_color=track, progress_color=fill, **kw)
        self.show(0.0, fill)

    def show(self, value, color=None):
        self.stop()
        self.configure(mode="determinate")
        self._fill = color or self._fill
        self._value = value
        if i18n.RTL:
            self.configure(fg_color=self._fill, progress_color=self._track)
            self.set(1.0 - value)
        else:
            self.configure(fg_color=self._track, progress_color=self._fill)
            self.set(value)

    def busy(self, color):
        self.configure(mode="indeterminate", fg_color=self._track, progress_color=color)
        self.start()


def make_dot(color, size=14, radius=4.0):
    img = tk.PhotoImage(width=size, height=size)
    c = (size - 1) / 2
    for y in range(size):
        for x in range(size):
            if (x - c) ** 2 + (y - c) ** 2 <= radius ** 2:
                img.put(color, (x, y))
    return img


def bind_click(widgets, command):
    for w in widgets:
        w.bind("<Button-1>", lambda _e: command(), add="+")


def ask_yes_no(parent, title, message):
    message = display_text(message, px_width=380, font=(SANS, 12)) if i18n.RTL else message
    return messagebox.askyesno(vis(title), message, parent=parent)


class Tooltip:
    """Small hover hint. Works with plain Tk and CustomTkinter widgets."""

    def __init__(self, widget, text, delay=450):
        self.widget, self.text, self.delay = widget, text, delay
        self.tip = None
        self.job = None
        widget.bind("<Enter>", self._schedule, add="+")
        widget.bind("<Leave>", self._hide, add="+")
        widget.bind("<ButtonPress>", self._hide, add="+")

    def _schedule(self, _=None):
        self._cancel()
        self.job = self.widget.after(self.delay, self._show)

    def _cancel(self):
        if self.job:
            self.widget.after_cancel(self.job)
            self.job = None

    def _show(self):
        if self.tip or not self.text:
            return
        self.tip = tk.Toplevel(self.widget)
        self.tip.wm_overrideredirect(True)
        self.tip.attributes("-topmost", True)
        self.tip.configure(bg=BORDER_2)
        width = int(280 * SCALE)
        text = display_text(self.text, px_width=width, font=(SANS, 12)) if i18n.RTL else self.text
        tk.Label(self.tip, text=text, bg=INPUT, fg=TEXT, font=sans(9), justify=justify(),
                 wraplength=0 if i18n.RTL else width, padx=9, pady=6).pack(padx=1, pady=1)
        self.tip.update_idletasks()
        x = self.widget.winfo_rootx() + 10
        if i18n.RTL:
            x = self.widget.winfo_rootx() + self.widget.winfo_width() - self.tip.winfo_reqwidth() - 10
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 6
        self.tip.wm_geometry(f"+{max(0, x)}+{y}")

    def _hide(self, _=None):
        self._cancel()
        if self.tip:
            self.tip.destroy()
            self.tip = None


def place_dialog(dialog, app, w, h, top=80):
    x = app.winfo_rootx() + max(0, (app.winfo_width() - w) // 2)
    y = app.winfo_rooty() + top
    dialog.geometry(f"{w}x{h}+{x}+{y}")
    dialog.configure(fg_color=BG)
    dialog.transient(app)

    def grab():
        try:
            dialog.focus()
            dialog.grab_set()
        except tk.TclError:
            pass

    dialog.after(150, grab)


def tree_heading(tree, key, text, anchor):
    tree.heading(key, text=vis(text), anchor=anchor)


# ---------------------------------------------------------------------------
# Location picker - search and pick countries, cities and servers
# ---------------------------------------------------------------------------
class LocationPicker(ctk.CTkToplevel):
    def __init__(self, app, locations, selected, on_done):
        super().__init__(app)
        self.app, self.on_done = app, on_done
        self.selected = set(selected)
        self.region = "All"
        self.item_keys = {}
        self.country_items = set()

        self.title(vis(t("choose_locations")))
        place_dialog(self, app, 560, 700, top=40)
        self.minsize(460, 520)

        head = frame(self)
        head.pack(fill="x", padx=22, pady=(18, 0))
        title_row = frame(head)
        title_row.pack(fill="x")
        label(title_row, t("choose_locations"), 18, bold=True).pack(side=start())
        self.btn_update = ghost_button(title_row, t("update_list"), app.update_locations,
                                       width=app.text_width(t("updating"), sans(12)) + 28, height=30)
        self.btn_update.pack(side=end())
        Tooltip(self.btn_update, t("update_tip"))
        label(head, t("picker_hint"), 11, MUTED, wraplength=500).pack(anchor=a_start(), fill="x", pady=(2, 0))

        self.entry = entry(self, height=40, size=13, placeholder_text=t("search_locations"))
        self.entry.pack(fill="x", padx=22, pady=(14, 0))
        self.entry.bind("<KeyRelease>", self._on_search)
        self.entry.bind("<Down>", lambda _e: self._focus_tree())
        self.entry.bind("<Return>", lambda _e: self.done())

        self.chips = frame(self)
        self.chips.pack(fill="x", padx=22, pady=(10, 0))
        self.region_buttons = {}

        box = card(self, corner_radius=12)
        box.pack(fill="both", expand=True, padx=22, pady=(6, 0))
        box.grid_columnconfigure(gcol(0, 2), weight=1)
        box.grid_rowconfigure(0, weight=1)
        self.tree = ttk.Treeview(box, columns=("sel",), show="tree", style="Pick.Treeview", selectmode="browse")
        self.tree.column("#0", width=360, stretch=True, anchor=a_start())
        self.tree.column("sel", width=96, anchor="center", stretch=False)
        self.tree.tag_configure("country", font=sans(10, True))
        self.tree.tag_configure("on", foreground=ACCENT)
        self.tree.tag_configure("empty", foreground=MUTED)
        sb = ctk.CTkScrollbar(box, command=self.tree.yview, button_color=BORDER_2, button_hover_color=HOVER)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.grid(row=0, column=gcol(0, 2), sticky="nsew", padx=pads(8, 0), pady=8)
        sb.grid(row=0, column=gcol(1, 2), sticky="ns", padx=pads(0, 4), pady=8)
        self.tree.bind("<Button-1>", self._on_click)
        self.tree.bind("<Double-1>", lambda _e: "break")
        self.tree.bind("<space>", lambda _e: self._toggle_focused())
        self.tree.bind("<Return>", lambda _e: self.done())

        self.lbl_count = label(self, "", 12, TEXT_2)
        self.lbl_count.pack(fill="x", padx=24, pady=(10, 0))
        foot = frame(self)
        foot.pack(fill="x", padx=22, pady=(8, 18))
        ghost_button(foot, t("select_shown"), self.select_shown,
                     width=app.text_width(t("select_shown"), sans(12)) + 28, height=36).pack(side=start())
        ghost_button(foot, t("clear"), self.clear, width=70, height=36).pack(side=start(), padx=pads(6, 0))
        primary_button(foot, t("done"), self.done, width=100, height=36).pack(side=end())
        ghost_button(foot, t("cancel"), self.close, width=80, height=36).pack(side=end(), padx=pads(0, 8))

        self.bind("<Escape>", lambda _e: self.close())
        self.protocol("WM_DELETE_WINDOW", self.close)
        self.after(200, self.entry.focus_set)
        self.set_locations(locations)

    def set_locations(self, locations):
        """(Re)loads the server list, e.g. after it was downloaded again."""
        self.total = len(locations)
        self.by_country = {}
        for l in sorted(locations, key=lambda l: (l["country"].lower(), l["city"].lower(), l["location"].lower())):
            self.by_country.setdefault(l["country"], []).append(l)
        self.selected &= {loc_key(l) for l in locations}

        for w in self.chips.winfo_children():
            w.destroy()
        self.region_buttons = {}
        regions = ["All"] + sorted({l["continent"] for l in locations})
        if any(l["country"].startswith("US ") for l in locations):
            regions.append("USA")
        line = None
        for i, region in enumerate(regions):
            if i % 5 == 0:
                line = frame(self.chips)
                line.pack(fill="x", pady=(0, 6))
            name = i18n.region_name(region)
            b = ctk.CTkButton(line, text=name, height=28, width=self.app.text_width(name, sans(11)) + 26,
                              corner_radius=14, border_width=1, font=sans(11), hover_color=HOVER,
                              command=lambda r=region: self.set_region(r))
            b.pack(side=start(), padx=pads(0, 6))
            self.region_buttons[region] = b
        self.set_region(self.region if self.region in self.region_buttons else "All")

    # -- data --
    def _matches(self):
        tokens = self.entry.get().lower().split()
        out = []
        for country, locs in self.by_country.items():
            locs = [l for l in locs if matches_region(l, self.region)]
            if not locs:
                continue
            if tokens:
                country_hay = f"{country} {locs[0]['continent']} {i18n.region_name(locs[0]['continent'])}".lower()
                if not all(tok in country_hay for tok in tokens):
                    locs = [l for l in locs if all(
                        tok in f"{country} {l['continent']} {l['city']} {l['location']}".lower() for tok in tokens)]
            if locs:
                out.append((country, locs))
        return out, bool(tokens)

    # -- rendering --
    def render(self):
        self.tree.delete(*self.tree.get_children())
        self.item_keys.clear()
        self.country_items.clear()
        matches, searching = self._matches()
        pad = "" if i18n.RTL else "  "
        for country, locs in matches:
            cid = self.tree.insert("", "end", text=f"{pad}{country}", open=searching or len(matches) == 1,
                                   tags=("country",))
            self.country_items.add(cid)
            self.item_keys[cid] = [loc_key(l) for l in locs]
            for l in locs:
                badge = f"  [{t('free_badge')}]" if not l.get("is_premium", True) else ""
                iid = self.tree.insert(cid, "end", text=f"{pad}{loc_name(l['city'], l['location'])}{badge}")
                self.item_keys[iid] = [loc_key(l)]
        if not matches:
            self.tree.insert("", "end", text=f"{pad}{vis(t('no_match_locations'))}", tags=("empty",))
        self.refresh_marks()

    def refresh_marks(self):
        for iid, keys in self.item_keys.items():
            n = sum(k in self.selected for k in keys)
            if iid in self.country_items:
                mark = "☑" if n == len(keys) else "▣" if n else "☐"
                count = f"{n}/{len(keys)}" if n else str(len(keys))
                text = f"{count}   {mark}" if i18n.RTL else f"{mark}   {count}"
                self.tree.item(iid, values=(text,), tags=("country", "on") if n else ("country",))
            else:
                self.tree.item(iid, values=("☑" if n else "☐",), tags=("on",) if n else ())
        n = len(self.selected)
        self.lbl_count.configure(text=t("n_selected", n=num(n), total=num(self.total)) if n
                                 else t("nothing_selected", total=num(self.total)))

    def set_region(self, region):
        self.region = region
        for name, b in self.region_buttons.items():
            active = name == region
            b.configure(fg_color=ACCENT_SOFT if active else "transparent",
                        border_color=ACCENT_LINE if active else BORDER_2,
                        text_color=TEXT if active else TEXT_2)
        self.render()

    # -- interaction --
    def _on_search(self, event):
        if event.keysym in ("Down", "Return", "Escape"):
            return
        self.render()

    def _focus_tree(self):
        children = self.tree.get_children()
        if children:
            self.tree.focus_set()
            self.tree.focus(children[0])
            self.tree.selection_set(children[0])

    def _on_click(self, event):
        iid = self.tree.identify_row(event.y)
        if not iid or iid not in self.item_keys:
            return None
        if "indicator" in self.tree.identify_element(event.x, event.y):
            return None  # let the tree expand/collapse
        if iid in self.country_items and self.tree.identify_column(event.x) == "#0":
            self.tree.item(iid, open=not self.tree.item(iid, "open"))
        else:
            self.toggle(iid)
        self.tree.focus(iid)
        self.tree.selection_set(iid)
        return "break"

    def _toggle_focused(self):
        iid = self.tree.focus()
        if iid in self.item_keys:
            self.toggle(iid)
        return "break"

    def toggle(self, iid):
        keys = self.item_keys[iid]
        if all(k in self.selected for k in keys):
            self.selected.difference_update(keys)
        else:
            self.selected.update(keys)
        self.refresh_marks()

    def select_shown(self):
        for iid in self.country_items:
            self.selected.update(self.item_keys[iid])
        self.refresh_marks()

    def clear(self):
        self.selected.clear()
        self.refresh_marks()

    def done(self):
        self.on_done(set(self.selected))
        self.close()

    def close(self):
        try:
            self.grab_release()
        except tk.TclError:
            pass
        self.destroy()


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
class App(ctk.CTk):
    # (key, title string, width, numeric)
    RESULT_COLUMNS = [("#0", "col_location", 185, False), ("country", "col_country", 105, False),
                      ("route", "col_route", 104, False), ("status", "col_result", 105, False),
                      ("time", "col_connect", 60, True), ("ping", "col_ping", 62, True),
                      ("loss", "col_loss", 52, True), ("http", "col_http", 62, True),
                      ("speed", "col_speed", 72, True), ("ip", "col_ip", 108, False)]
    BEST_COLUMNS = [("#0", "col_location", 210, False), ("country", "col_country", 110, False),
                    ("route", "col_route", 108, False), ("ping", "col_ping", 66, True),
                    ("loss", "col_loss", 54, True), ("http", "col_http", 66, True),
                    ("speed", "col_speed", 74, True), ("ip", "col_ip", 108, False),
                    ("time", "col_connect", 66, True)]
    SORT_KEYS = {
        "#0": lambda r: (r["city"].lower(), r["node"].lower()),
        "country": lambda r: r["country"].lower(),
        "route": lambda r: (r["proto"], r["port"]),
        "status": lambda r: r["status"],
        "time": lambda r: r["duration"] if r["status"] == "SUCCESS" else float("inf"),
        "ping": lambda r: r["ping"] if r["ping"] is not None else float("inf"),
        "loss": lambda r: r["loss"] if r["loss"] is not None else float("inf"),
        "http": lambda r: r.get("http_ms") if r.get("http_ms") is not None else float("inf"),
        "speed": lambda r: -(r.get("speed_kbps") or 0.0),
        "ip": lambda r: r.get("vpn_ip") or "",
    }
    PHASES = ["phase_disconnect", "phase_connect", "phase_settle", "phase_ping", "phase_hold"]
    VIEWS = ["Results", "Best routes", "Log", "Diagnostics"]
    VIEW_KEYS = {"Results": "tab_results", "Best routes": "tab_best", "Log": "tab_log", "Diagnostics": "tab_diag"}
    FILTER_KEYS = {"All": "filter_all", "Connected": "filter_connected", "Failed": "filter_failed"}

    def __init__(self):
        global SCALE
        self.config_data = ConfigManager.load_config()
        if not self.config_data.get("language"):
            self.config_data["language"] = i18n.detect_language()
        i18n.set_language(self.config_data["language"])
        _FONT_CACHE.clear()

        super().__init__()
        init_fonts(self)
        try:
            self.scale = ctk.ScalingTracker.get_window_scaling(self)
        except Exception:
            self.scale = 1.0
        SCALE = self.scale
        self.relaunch = False
        self.title(APP_NAME)
        self.geometry("1280x860")
        self.minsize(1100, 720)
        self.configure(fg_color=BG)

        self._ui_queue = queue.Queue()
        self._toast = None
        self._picker = None
        self.protocol_vars = {}
        self.port_vars = {}
        self.port_buttons = {}
        self.results = []
        self.sort_col = None
        self.sort_desc = False
        self.result_filter = "All"
        self.view = "Results"
        self.step = None
        self.run = None
        self.connected_to = None
        self.connected_route = None
        self._watchdog_busy = False
        self._last_watchdog_ts = 0.0
        self._recent_ai_errors = []
        self._active_ai_strategy = 'AUTO'
        self.timing_open = False

        self.last_settings = self.config_data.get("last_settings", {})
        self.saved_profiles = self.config_data.get("saved_profiles", {})
        self.priority_order = self.sanitize_priority(self.last_settings.get("priority_order"))
        self.current_profile_name = "Manual"
        self.locations = LocationManager.load_locations()
        self.all_keys = {loc_key(l) for l in self.locations}
        self.selected_keys = set()
        self.sidebar_open = bool(self.config_data.get("sidebar_open", True))

        size, radius = max(10, int(14 * self.scale)), 4.0 * self.scale
        self.dots = {"SUCCESS": make_dot(GOOD, size, radius), "FAILURE": make_dot(BAD, size, radius),
                     "HTTP_FAIL": make_dot(WARN, size, radius), "DPI_RESET": make_dot(BAD, size, radius),
                     "BLACKHOLED": make_dot(WARN, size, radius),
                     "INVALID_LOC": make_dot(WARN, size, radius), "fast": make_dot(GOOD, size, radius),
                     "medium": make_dot(WARN, size, radius), "slow": make_dot(BAD, size, radius)}

        self.init_vars()
        self.setup_ui()
        self.worker = WindscribeWorker(self, resolve_cli(self.entry_cli.get()) or DEFAULT_CLI)
        self.apply_config_to_ui(self.last_settings)
        self.reload_results_table()
        self.refresh_cli_status()
        self.refresh_locations_info()
        self.restore_window()
        self.bind_shortcuts()
        self.apply_sidebar_state()

        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self.after(60, self._drain_ui_queue)
        self.after(1000, self._tick)

    # ---------------- thread-safe UI bridge ----------------
    def post(self, fn, *args, **kwargs):
        """Called from the worker thread; the callable runs on the Tk main thread."""
        self._ui_queue.put((fn, args, kwargs))

    def _drain_ui_queue(self):
        try:
            while True:
                fn, args, kwargs = self._ui_queue.get_nowait()
                try:
                    fn(*args, **kwargs)
                except Exception as e:
                    print(f"UI error: {e}")
        except queue.Empty:
            pass
        self.after(60, self._drain_ui_queue)

    # ---------------- data ----------------
    @staticmethod
    def sanitize_priority(order):
        order = [p for p in (order or []) if p in DEFAULT_PROTOCOLS]
        return order + [p for p in DEFAULT_PROTOCOLS if p not in order]

    def init_vars(self):
        saved_protocols = self.last_settings.get("protocols", {})
        for proto, ports in DEFAULT_PROTOCOLS.items():
            self.protocol_vars[proto] = ctk.BooleanVar(value=saved_protocols.get(proto, {}).get("enabled", True))
            self.protocol_vars[proto].trace_add("write", lambda *_: self.update_scope_preview(user_change=True))
            self.port_vars[proto] = {}
            saved_ports = saved_protocols.get(proto, {}).get("ports", {})
            for port in ports:
                self.port_vars[proto][port] = ctk.BooleanVar(value=saved_ports.get(str(port), True))

    def text_width(self, text, font):
        """Width in CustomTkinter's unscaled units."""
        return int(measure(font, text) / self.scale)

    def worker_running(self):
        return hasattr(self, "worker") and self.worker.running

    def scope_locations(self):
        locs = self.locations if not self.selected_keys else [l for l in self.locations if loc_key(l) in self.selected_keys]
        if hasattr(self, "sw_free_only") and self.sw_free_only.get():
            locs = [l for l in locs if not l.get("is_premium", False)]
        if hasattr(self, "sw_dedup_cities") and self.sw_dedup_cities.get():
            seen = set()
            deduped = []
            for l in locs:
                ck = (l["country"].lower(), l["city"].lower())
                if ck not in seen:
                    seen.add(ck)
                    deduped.append(l)
            locs = deduped
        return locs

    @staticmethod
    def servers_in(n, countries):
        if countries == 1:
            return t("servers_in_one", n=num(n))
        return t("servers_in", n=num(n), c=num(countries))

    def scope_summary(self):
        """(title, subtitle) describing the selected locations."""
        if not self.selected_keys:
            return t("all_servers"), self.servers_in(len(self.locations), len({l["country"] for l in self.locations}))
        chosen = self.scope_locations()
        names, covered = [], set()
        for continent in sorted({l["continent"] for l in self.locations}):
            group = [l for l in self.locations if l["continent"] == continent]
            if all(loc_key(l) in self.selected_keys for l in group):
                names.append(i18n.region_name(continent))
                covered.update(l["country"] for l in group)
        for country in sorted({l["country"] for l in chosen} - covered):
            group = [l for l in self.locations if l["country"] == country]
            if all(loc_key(l) in self.selected_keys for l in group):
                names.append(country)
            else:
                names.extend(sorted({l["city"] for l in chosen if l["country"] == country}))
        sep = "، " if i18n.RTL else ", "
        title = sep.join(names[:2]) + (t("more", n=len(names) - 2) if len(names) > 2 else "")
        return title, self.servers_in(len(chosen), len({l["country"] for l in chosen}))

    # ---------------- layout ----------------
    def setup_ui(self):
        self.grid_columnconfigure(gcol(1, 2), weight=1)
        self.grid_rowconfigure(0, weight=1)
        self.setup_tree_styles()
        self.build_sidebar()
        self.build_rail()
        self.build_main()

    def setup_tree_styles(self):
        style = ttk.Style()
        style.theme_use("clam")
        row_h = int(32 * self.scale)
        for name, bg in (("AS", CARD), ("Pick", CARD)):
            style.configure(f"{name}.Treeview", background=bg, fieldbackground=bg, foreground=TEXT, borderwidth=0,
                            rowheight=row_h, font=sans(10), indent=int(18 * self.scale))
            style.map(f"{name}.Treeview", background=[("selected", SELECTED)], foreground=[("selected", TEXT)])
            style.layout(f"{name}.Treeview", [("Treeview.treearea", {"sticky": "nswe"})])
        style.configure("AS.Treeview.Heading", background=CARD, foreground=MUTED, relief="flat", borderwidth=0,
                        font=sans(9, True), padding=(8, 8))
        style.map("AS.Treeview.Heading", background=[("active", HOVER)], foreground=[("active", TEXT)])
        style.configure("Treeitem.indicator", foreground=MUTED)

    def draw_logo(self, parent):
        box = ctk.CTkFrame(parent, width=34, height=34, corner_radius=9, fg_color="#16202B", border_width=1,
                           border_color="#27384A")
        box.grid_propagate(False)
        s = self.scale
        size = int(20 * s)
        c = tk.Canvas(box, width=size, height=size, bg="#16202B", highlightthickness=0, bd=0)
        c.place(relx=0.5, rely=0.5, anchor="center")
        cx, cy = size / 2, size * 0.85
        for r in (4.5, 9, 13.5):
            r *= s
            c.create_arc(cx - r, cy - r, cx + r, cy + r, start=45, extent=90, style="arc", outline=ACCENT,
                         width=max(2, int(2 * s)))
        d = 1.4 * s
        c.create_oval(cx - d, cy - d, cx + d, cy + d, fill=ACCENT, outline=ACCENT)
        return box

    def edge_line(self, panel):
        """1px border on the side of the sidebar that faces the content."""
        ctk.CTkFrame(panel, fg_color=BORDER, width=1, height=1, corner_radius=0).place(
            relx=0.0 if i18n.RTL else 1.0, rely=0, relheight=1, anchor="nw" if i18n.RTL else "ne")

    # ---- sidebar ----
    def build_sidebar(self):
        side = ctk.CTkFrame(self, fg_color=SIDEBAR, corner_radius=0, width=320)
        side.grid(row=0, column=gcol(0, 2), sticky="nsew")
        side.grid_propagate(False)
        side.grid_rowconfigure(1, weight=1)
        side.grid_columnconfigure(0, weight=1)
        self.edge_line(side)
        self.sidebar = side

        head = frame(side)
        head.grid(row=0, column=0, sticky="ew", padx=18, pady=(18, 6))
        head.grid_columnconfigure(gcol(1, 3), weight=1)
        self.draw_logo(head).grid(row=0, column=gcol(0, 3), rowspan=2, padx=pads(0, 10))
        label(head, APP_NAME, 16, bold=True).grid(row=0, column=gcol(1, 3), sticky=a_start())
        label(head, t("tagline", v=APP_VERSION), 10, MUTED).grid(row=1, column=gcol(1, 3), sticky=a_start())
        btn = icon_button(head, "menu" if i18n.RTL else "collapse", self.toggle_sidebar, size=30,
                          fg_color="transparent", border_color=SIDEBAR)
        btn.grid(row=0, column=gcol(2, 3), rowspan=2)
        Tooltip(btn, t("hide_panel_tip"))

        scroll = ctk.CTkScrollableFrame(side, fg_color="transparent", corner_radius=0,
                                        scrollbar_button_color=BORDER_2, scrollbar_button_hover_color=HOVER)
        scroll.grid(row=1, column=0, sticky="nsew", padx=pads(0, 2))
        self.sidebar_scroll = scroll
        px = 16

        # --- Profile ---
        caps(scroll, t("profile")).pack(fill="x", padx=px, pady=(16, 6))
        row = frame(scroll)
        row.pack(fill="x", padx=px)
        self.combo_profiles = ctk.CTkComboBox(
            row, values=list(self.saved_profiles.keys()), command=self.load_profile, height=36, state="readonly",
            fg_color=INPUT, border_color=BORDER_2, button_color=INPUT, button_hover_color=HOVER,
            dropdown_fg_color=INPUT, dropdown_hover_color=HOVER, dropdown_text_color=TEXT, font=sans(12),
            dropdown_font=sans(12), justify=justify())
        self.combo_profiles.pack(side=start(), fill="x", expand=True)
        self.set_profile_placeholder()
        b = icon_button(row, "save", self.ask_profile_name, size=36, fg_color=INPUT)
        b.pack(side=start(), padx=pads(6, 0))
        Tooltip(b, t("save_profile_tip"))
        b = icon_button(row, "delete", self.delete_profile, size=36, fg_color=INPUT)
        b.pack(side=start(), padx=pads(6, 0))
        Tooltip(b, t("delete_profile_tip"))

        # --- Locations ---
        lh = frame(scroll)
        lh.pack(fill="x", padx=px, pady=(20, 6))
        caps(lh, t("locations")).pack(side=start())
        self.btn_update_list = ctk.CTkButton(lh, text=t("update_list"), command=self.update_locations, width=20,
                                             height=20, fg_color="transparent", hover_color=HOVER,
                                             text_color=ACCENT, text_color_disabled=MUTED, font=sans(11))
        self.btn_update_list.pack(side=end())
        self.tip_update_list = Tooltip(self.btn_update_list, "")
        sc = ctk.CTkFrame(scroll, fg_color=INPUT, corner_radius=10, border_width=1, border_color=BORDER_2)
        sc.pack(fill="x", padx=px)
        sc.grid_columnconfigure(gcol(0, 2), weight=1)
        self.lbl_scope_title = label(sc, "", 13, bold=True)
        self.lbl_scope_title.grid(row=0, column=gcol(0, 2), sticky=a_start(), padx=pads(12, 6), pady=(10, 0))
        self.lbl_scope_sub = label(sc, "", 11, MUTED)
        self.lbl_scope_sub.grid(row=1, column=gcol(0, 2), sticky=a_start(), padx=pads(12, 6), pady=(0, 10))
        change = ctk.CTkLabel(sc, text=t("change"), font=sans(12, True), text_color=ACCENT, cursor="hand2")
        change.grid(row=0, column=gcol(1, 2), rowspan=2, padx=pads(0, 12))
        bind_click([sc, self.lbl_scope_title, self.lbl_scope_sub, change], self.open_location_picker)
        Tooltip(change, t("change_tip"))

        tests = ctk.CTkFrame(scroll, fg_color="#141922", corner_radius=8, border_width=1, border_color="#2A3442")
        tests.pack(fill="x", padx=px, pady=(8, 0))
        self.lbl_scope_math = label(tests, "", 12, TEXT_2)
        self.lbl_scope_math.pack(side=start(), padx=11, pady=8)
        self.lbl_scope_tests = label(tests, "", font=mono(12, True))
        self.lbl_scope_tests.pack(side=end(), padx=11, pady=8)
        self.lbl_no_locations = label(scroll, t("no_list_hint"), 11, WARN, wraplength=270)
        self.locations_hint_anchor = tests

        # --- Protocols ---
        ph = frame(scroll)
        ph.pack(fill="x", padx=px, pady=(20, 6))
        caps(ph, t("protocols")).pack(side=start())
        label(ph, t("top_first"), 10, MUTED).pack(side=end())
        self.btn_iran_preset = ghost_button(
            scroll, t("iran_preset_btn"), self.apply_iran_preset,
            height=32, fg_color=ACCENT_SOFT, border_color=ACCENT_LINE, text_color=CHIP_TEXT, font=sans(12, True)
        )
        self.btn_iran_preset.pack(fill="x", padx=px, pady=(0, 8))
        Tooltip(self.btn_iran_preset, t("iran_preset_tip"))
        self.protocol_container = ctk.CTkFrame(scroll, fg_color=BORDER, corner_radius=10)
        self.protocol_container.pack(fill="x", padx=px)
        self.refresh_protocol_list()

        # --- Options ---
        caps(scroll, t("options")).pack(fill="x", padx=px, pady=(20, 4))
        self.sw_resume = self.make_switch(scroll, t("opt_resume"), t("opt_resume_tip"))
        self.sw_anti_dpi_hold = self.make_switch(scroll, t("opt_anti_dpi_hold"), t("opt_anti_dpi_hold_tip"))
        self.sw_watchdog = self.make_switch(scroll, t("opt_watchdog"), t("opt_watchdog_tip"))
        self.sw_fast_skip = self.make_switch(scroll, t("opt_fast_skip"), t("opt_fast_skip_tip"))
        self.sw_smart_ai = self.make_switch(scroll, t("opt_smart_ai"), t("opt_smart_ai_tip"))
        self.sw_auto_pilot = self.make_switch(scroll, t("opt_auto_pilot"), t("opt_auto_pilot_tip"))
        self.sw_speed_burst = self.make_switch(scroll, t("opt_speed_burst"), t("opt_speed_burst_tip"))
        self.sw_free_only = self.make_switch(scroll, t("opt_free_only"), t("opt_free_only_tip"),
                                             command=lambda: self.update_scope_preview(user_change=True))
        self.sw_dedup_cities = self.make_switch(scroll, t("opt_dedup_cities"), t("opt_dedup_cities_tip"),
                                                command=lambda: self.update_scope_preview(user_change=True))
        self.sw_keep_firewall = self.make_switch(scroll, t("opt_keep_firewall"), t("opt_keep_firewall_tip"))
        self.sw_http_check = self.make_switch(scroll, t("opt_http_check"), t("opt_http_check_tip"))
        self.sw_random_cities = self.make_switch(scroll, t("opt_shuffle"), t("opt_shuffle_tip"))
        self.sw_chaos = self.make_switch(scroll, t("opt_chaos"), t("opt_chaos_tip"))
        self.sw_stop_success = self.make_switch(scroll, t("opt_stop"), t("opt_stop_tip"))

        self.btn_timing = ctk.CTkButton(scroll, text="", anchor=a_start(), height=30, fg_color="transparent",
                                        hover_color=HOVER, text_color=TEXT_2, font=sans(12),
                                        command=self.toggle_timing)
        self.btn_timing.pack(fill="x", padx=px - 6, pady=(8, 0))
        self.timing_frame = frame(scroll)
        grid = frame(self.timing_frame)
        grid.pack(fill="x", padx=px)
        grid.grid_columnconfigure((0, 1), weight=1, uniform="t")
        self.entry_ping_host = self.make_grid_entry(grid, t("ping_host"), 0, 0, colspan=2,
                                                    tip=t("ping_host_tip"), rtl_text=False)
        self.entry_ping_count = self.make_grid_entry(grid, t("pings_per_test"), 2, 0, tip="1 – 20")
        self.entry_timeout = self.make_grid_entry(grid, t("connect_timeout"), 2, 1, tip=t("connect_timeout_tip"))
        self.entry_settle = self.make_grid_entry(grid, t("settle_delay"), 4, 0, tip=t("settle_delay_tip"))
        self.entry_hold = self.make_grid_entry(grid, t("hold_seconds"), 4, 1, tip=t("hold_seconds_tip"))
        self.entry_http_url = self.make_grid_entry(grid, t("http_url"), 6, 0, colspan=2,
                                                   tip=t("http_url_tip"), rtl_text=False)
        label(grid, t("windscribe_cli"), 11, MUTED).grid(row=8, column=0, columnspan=2, sticky=a_start(),
                                                         pady=(10, 3))
        cli_row = frame(grid)
        cli_row.grid(row=9, column=0, columnspan=2, sticky="ew")
        self.entry_cli = entry(cli_row, size=11, rtl_text=False)
        self.entry_cli.pack(side=start(), fill="x", expand=True)
        saved_cli = (self.config_data.get("cli_path") or "").strip()
        if saved_cli and not IS_WINDOWS and ("\\" in saved_cli or saved_cli.lower().endswith(".exe") or ":\\" in saved_cli):
            saved_cli = ""
        self.entry_cli.insert(0, saved_cli or DEFAULT_CLI)
        self.entry_cli.bind("<FocusOut>", lambda _e: self.refresh_cli_status())
        self.entry_cli.bind("<Return>", lambda _e: self.refresh_cli_status())
        ghost_button(cli_row, t("browse"), self.browse_cli, width=64, height=34, fg_color=INPUT).pack(
            side=start(), padx=pads(6, 0))
        for e in (self.entry_ping_host, self.entry_ping_count, self.entry_timeout):
            e.bind("<KeyRelease>", lambda _e: self.update_timing_summary(), add="+")
        frame(scroll, height=16).pack()

        # --- Language + CLI status ---
        lang_row = frame(side)
        lang_row.grid(row=2, column=0, sticky="ew", padx=16, pady=(8, 0))
        codes = list(i18n.LANGUAGES)
        names = [i18n.LANGUAGES[c] for c in (codes[::-1] if i18n.RTL else codes)]
        self.seg_lang = ctk.CTkSegmentedButton(
            lang_row, values=names, command=self.change_language, height=30, font=sans(12),
            fg_color=DEEP, selected_color="#20262F", selected_hover_color="#262D37", unselected_color=DEEP,
            unselected_hover_color=HOVER, text_color=TEXT, corner_radius=8)
        self.seg_lang.set(i18n.LANGUAGES[i18n.LANG])
        self.seg_lang.pack(fill="x")

        self.cli_pill = ctk.CTkFrame(side, corner_radius=10, border_width=1, height=40)
        self.cli_pill.grid(row=3, column=0, sticky="ew", padx=16, pady=(8, 16))
        self.cli_dot = ctk.CTkLabel(self.cli_pill, text="●", font=sans(10))
        self.cli_dot.pack(side=start(), padx=pads(12, 6), pady=8)
        self.cli_text = label(self.cli_pill, "", 12)
        self.cli_text.pack(side=start(), pady=8)
        bind_click([self.cli_pill, self.cli_dot, self.cli_text], self.focus_cli_entry)

    def build_rail(self):
        rail = ctk.CTkFrame(self, fg_color=SIDEBAR, corner_radius=0, width=64)
        rail.grid(row=0, column=gcol(0, 2), sticky="nsew")
        rail.grid_propagate(False)
        self.edge_line(rail)
        self.rail = rail
        inner = frame(rail)
        inner.pack(fill="y", expand=True, pady=18)
        self.draw_logo(inner).pack(pady=(0, 18))
        for name, tip, cmd in (("menu", t("show_panel_tip"), self.toggle_sidebar),
                               ("globe", t("locations_tip"), lambda: (self.toggle_sidebar(),
                                                                     self.open_location_picker())),
                               ("list", t("protocols"), self.toggle_sidebar),
                               ("sliders", t("ping_timing"), lambda: (self.toggle_sidebar(),
                                                                     self.toggle_timing(True)))):
            b = icon_button(inner, name, cmd, size=44, icon_size=16, fg_color="transparent", border_color=SIDEBAR,
                            text_color=TEXT_2)
            b.pack(pady=3)
            Tooltip(b, tip)
        self.rail_dot = ctk.CTkLabel(rail, text="●", font=sans(12), cursor="hand2")
        self.rail_dot.pack(side="bottom", pady=18)
        bind_click([self.rail_dot], lambda: (self.toggle_sidebar(), self.focus_cli_entry()))
        rail.grid_remove()

    def make_switch(self, parent, text, tip=None, command=None):
        row = frame(parent)
        row.pack(fill="x", padx=16, pady=2)
        lbl = label(row, text, 12, TEXT_2)
        lbl.pack(side=start(), pady=4)
        sw = ctk.CTkSwitch(row, text="", width=40, switch_width=36, switch_height=20, progress_color=ACCENT,
                           button_color=TEXT, button_hover_color="#FFFFFF", fg_color=BORDER_2, command=command)
        sw.pack(side=end())
        bind_click([lbl], sw.toggle)
        if tip:
            Tooltip(lbl, tip)
        return sw

    def make_grid_entry(self, parent, text, row, col, colspan=1, tip=None, rtl_text=True):
        c = gcol(col, 2) if colspan == 1 else 0
        label(parent, text, 11, MUTED).grid(row=row, column=c, columnspan=colspan, sticky=a_start(), pady=(8, 3))
        e = entry(parent, rtl_text=rtl_text)
        e.grid(row=row + 1, column=c, columnspan=colspan, sticky="ew",
               padx=(0, 0) if colspan > 1 else pads(0, 6) if col == 0 else (0, 0))
        e.bind("<Key>", lambda _e: e.configure(border_color=BORDER_2), add="+")
        if tip:
            Tooltip(e, tip)
        return e

    # ---- main area ----
    def build_main(self):
        main = frame(self)
        main.grid(row=0, column=gcol(1, 2), sticky="nsew", padx=24, pady=(18, 22))
        main.grid_columnconfigure(0, weight=1)
        main.grid_rowconfigure(3, weight=1)

        self.build_header(main)
        self.live_card = self.build_live_card(main)
        self.live_card.grid(row=1, column=0, sticky="ew", pady=(16, 0))
        self.rec_card = self.build_rec_card(main)
        self.rec_card.grid(row=1, column=0, sticky="ew", pady=(16, 0))
        self.rec_card.grid_remove()
        self.build_stats(main).grid(row=2, column=0, sticky="ew", pady=(16, 0))

        bottom = frame(main)
        bottom.grid(row=3, column=0, sticky="nsew", pady=(16, 0))
        bottom.grid_columnconfigure(gcol(0, 2), weight=1)
        bottom.grid_rowconfigure(0, weight=1)
        self.build_results_card(bottom).grid(row=0, column=gcol(0, 2), sticky="nsew")
        side = frame(bottom, width=290)
        side.grid(row=0, column=gcol(1, 2), sticky="ns", padx=pads(16, 0))
        side.pack_propagate(False)
        self.build_insights(side)

    def build_header(self, parent):
        h = frame(parent)
        h.grid(row=0, column=0, sticky="ew")
        n = 5
        h.grid_columnconfigure(gcol(0, n), weight=1)
        left = frame(h)
        left.grid(row=0, column=gcol(0, n), sticky=a_start())
        tr = frame(left)
        tr.pack(anchor=a_start())
        self.lbl_title = label(tr, t("ready"), 20, bold=True)
        self.lbl_title.pack(side=start())
        self.lbl_badge = ctk.CTkLabel(tr, text="", font=sans(11), corner_radius=10, height=22)
        self.lbl_sub = label(left, "", 12, MUTED)
        self.lbl_sub.pack(anchor=a_start())

        self.lbl_conn = ctk.CTkLabel(h, text="", font=sans(11), fg_color=GOOD_SOFT, text_color=GOOD_TEXT,
                                     corner_radius=14, height=30)
        self.lbl_conn.grid(row=0, column=gcol(1, n), padx=pads(8, 0))
        self.lbl_conn.grid_remove()

        def width_for(*keys, minimum=108, font=sans(12)):
            return max([minimum] + [self.text_width(t(k), font) + 36 for k in keys])

        self.btn_export = ghost_button(h, t("export_csv"), self.export_csv, width=width_for("export_csv"),
                                       height=40, corner_radius=9)
        self.btn_export.grid(row=0, column=gcol(2, n), padx=pads(10, 0))
        Tooltip(self.btn_export, t("export_tip"))
        self.btn_disconnect = ghost_button(h, t("disconnect"), self.disconnect_vpn, width=width_for("disconnect"),
                                           height=40, corner_radius=9)
        self.btn_disconnect.grid(row=0, column=gcol(3, n), padx=pads(8, 0))
        Tooltip(self.btn_disconnect, t("disconnect_tip"))
        main_width = max(176, self.text_width(t("start_n", n="0,000"), sans(13, True)) + 40)
        self.btn_start = primary_button(h, t("start"), self.start_job, width=main_width, height=40)
        self.btn_start.grid(row=0, column=gcol(4, n), padx=pads(8, 0))
        Tooltip(self.btn_start, t("start_tip"))
        self.btn_stop = ctk.CTkButton(h, text=t("stop"), command=self.stop_job, width=main_width, height=40,
                                      corner_radius=9, fg_color=BAD_SOFT, hover_color=BAD_HOVER, border_width=1,
                                      border_color=BAD_LINE, text_color=BAD_TEXT, text_color_disabled="#8A5A5A",
                                      font=sans(13, True))
        self.btn_stop.grid(row=0, column=gcol(4, n), padx=pads(8, 0))
        self.btn_stop.grid_remove()

    def build_live_card(self, parent):
        c = card(parent)
        c.grid_columnconfigure(0, weight=1)
        top = frame(c)
        top.grid(row=0, column=0, sticky="ew", padx=22, pady=(18, 0))
        top.grid_columnconfigure(gcol(0, 2), weight=1)
        info = frame(top)
        info.grid(row=0, column=gcol(0, 2), sticky=a_start())
        self.lbl_caption = caps(info, "")
        self.lbl_caption.pack(anchor=a_start())
        self.lbl_target = label(info, "", 24, bold=True)
        self.lbl_target.pack(anchor=a_start(), pady=(2, 0))
        sub = frame(info)
        sub.pack(anchor=a_start(), pady=(2, 0))
        self.lbl_target_sub = label(sub, "", 12, TEXT_2)
        self.lbl_target_sub.pack(side=start())
        self.lbl_route = chip(sub)

        ping_box = frame(top)
        ping_box.grid(row=0, column=gcol(1, 2), sticky="n" + a_end())
        pr = frame(ping_box)
        pr.pack(anchor=a_end())
        # Numbers read left to right in every language, so the value/unit pair keeps its order.
        self.lbl_ping = label(pr, "–", font=mono(40, True))
        self.lbl_ping.pack(side="left")
        label(pr, t("ms"), 13, MUTED).pack(side="left", padx=(4, 0), pady=(16, 0))
        self.lbl_ping_detail = label(ping_box, " ", font=mono(11), text_color=MUTED)
        self.lbl_ping_detail.pack(anchor=a_end())

        steps = frame(c)
        steps.grid(row=1, column=0, sticky="ew", padx=22, pady=(16, 0))
        n_phases = len(self.PHASES)
        steps.grid_columnconfigure(tuple(range(n_phases)), weight=1, uniform="steps")
        self.phase_widgets = []
        for i, key in enumerate(self.PHASES):
            f = frame(steps)
            f.grid(row=0, column=gcol(i, n_phases), sticky="ew", padx=pads(0 if i == 0 else 8, 0))
            bar = Bar(f, BORDER_2, BORDER_2, height=4, corner_radius=2)
            bar.pack(fill="x")
            row = frame(f)
            row.pack(fill="x", pady=(6, 0))
            name_lbl = label(row, t(key), 12, MUTED)
            name_lbl.pack(side=start())
            time_lbl = label(row, "", font=mono(11), text_color=MUTED)
            time_lbl.pack(side=end())
            self.phase_widgets.append((bar, name_lbl, time_lbl))

        divider(c).grid(row=2, column=0, sticky="ew", padx=22, pady=(16, 14))
        self.progress_bar = Bar(c, BORDER, ACCENT, height=8, corner_radius=4)
        self.progress_bar.grid(row=3, column=0, sticky="ew", padx=22)
        pr = frame(c)
        pr.grid(row=4, column=0, sticky="ew", padx=22, pady=(8, 16))
        self.lbl_prog_left = label(pr, "", 12, MUTED)
        self.lbl_prog_left.pack(side=start())
        self.lbl_prog_right = label(pr, "", 12, MUTED)
        self.lbl_prog_right.pack(side=end())
        self.lbl_ai_status = label(c, "", 11, CHIP_TEXT)
        self.lbl_ai_status.grid(row=5, column=0, sticky="w", padx=22, pady=(0, 12))
        return c

    def build_rec_card(self, parent):
        c = card(parent, fg_color=REC_BG, border_color=REC_LINE, corner_radius=16)
        c.grid_columnconfigure(gcol(0, 3), weight=1)
        info = frame(c, fg_color=REC_BG)
        info.grid(row=0, column=gcol(0, 3), sticky=a_start(), padx=24, pady=22)
        caps(info, t("best_route_caption"), ACCENT).pack(anchor=a_start())
        self.lbl_rec_name = label(info, "", 26, bold=True)
        self.lbl_rec_name.pack(anchor=a_start(), pady=(4, 0))
        sub = frame(info, fg_color=REC_BG)
        sub.pack(anchor=a_start(), pady=(4, 0))
        self.lbl_rec_country = label(sub, "", 12, TEXT_2)
        self.lbl_rec_country.pack(side=start())
        self.lbl_rec_route = chip(sub)
        self.lbl_rec_route.pack(side=start(), padx=pads(8, 0))
        stats = frame(c, fg_color=REC_BG)
        stats.grid(row=0, column=gcol(1, 3), padx=pads(0, 28))
        self.rec_stats = {}
        for i, (key, text) in enumerate((("ping", "ping"), ("loss", "loss"), ("time", "connect_time"))):
            f = frame(stats, fg_color=REC_BG)
            f.grid(row=0, column=gcol(i, 3), padx=pads(0 if i == 0 else 28, 0))
            label(f, t(text), 11, MUTED).pack(anchor=a_start())
            v = label(f, "", font=mono(22, True))
            v.pack(anchor=a_start())
            self.rec_stats[key] = v
        self.btn_rec_connect = primary_button(c, t("connect_btn"), lambda: self.connect_result(self.best_result()),
                                              width=max(130, self.text_width(t("connect_btn"), sans(13, True)) + 40),
                                              height=46)
        self.btn_rec_connect.grid(row=0, column=gcol(2, 3), padx=pads(0, 24))
        return c

    def build_stats(self, parent):
        c = card(parent)
        self.stat_labels = {}
        items = [("ok", "stat_connected", GOOD), ("fail", "stat_failed", BAD), ("rate", "stat_rate", TEXT),
                 ("best", "stat_best", GOOD), ("avg", "stat_avg", TEXT)]
        n = len(items) * 2 - 1
        for i, (key, text, color) in enumerate(items):
            col = gcol(i * 2, n)
            c.grid_columnconfigure(col, weight=1, uniform="stat")
            f = frame(c, fg_color=CARD)
            f.grid(row=0, column=col, sticky="ew", padx=18, pady=12)
            label(f, t(text), 11, MUTED).pack(anchor=a_start())
            v = label(f, "–", font=mono(20, True), text_color=color)
            v.pack(anchor=a_start())
            self.stat_labels[key] = v
            if i < len(items) - 1:
                ctk.CTkFrame(c, fg_color=BORDER, width=1, height=1, corner_radius=0).grid(
                    row=0, column=gcol(i * 2 + 1, n), sticky="ns", pady=1)
        return c

    def build_results_card(self, parent):
        c = card(parent)
        c.grid_columnconfigure(0, weight=1)
        c.grid_rowconfigure(2, weight=1)

        tb = frame(c, fg_color=CARD)
        tb.grid(row=0, column=0, sticky="ew", padx=12, pady=10)
        tabs = [t(self.VIEW_KEYS[v]) for v in self.VIEWS]
        self.seg_view = ctk.CTkSegmentedButton(
            tb, values=tabs[::-1] if i18n.RTL else tabs, command=self.on_view_clicked, height=30, font=sans(12),
            fg_color=DEEP, selected_color="#20262F", selected_hover_color="#262D37", unselected_color=DEEP,
            unselected_hover_color=HOVER, text_color=TEXT, corner_radius=8)
        self.seg_view.pack(side=start())
        self.results_tools = frame(tb, fg_color=CARD)
        self.entry_search = entry(self.results_tools, height=30, width=90, fg_color=DEEP,
                                  placeholder_text=t("search_results"))
        self.entry_search.pack(side=start(), fill="x", expand=True)
        self.entry_search.bind("<KeyRelease>", lambda _e: self.render_results())
        Tooltip(self.entry_search, t("search_tip"))
        self.filter_buttons = {}
        for name, key in self.FILTER_KEYS.items():
            b = ctk.CTkButton(self.results_tools, text=t(key), height=28, corner_radius=14, border_width=1,
                              width=self.text_width(f"{t(key)}  0000", sans(11)) + 22,
                              font=sans(11), hover_color=HOVER, command=lambda n=name: self.set_result_filter(n))
            b.pack(side=start(), padx=pads(6, 0))
            self.filter_buttons[name] = b
        self.best_tools = frame(tb, fg_color=CARD)
        btn_rev = ghost_button(
            self.best_tools, t("reverify_best"), self.reverify_best_routes,
            width=self.text_width(t("reverify_best"), sans(12)) + 32, height=28,
            fg_color=ACCENT_SOFT, border_color=ACCENT_LINE, text_color=CHIP_TEXT
        )
        btn_rev.pack(side=end())
        Tooltip(btn_rev, t("reverify_best_tip"))
        self.log_tools = frame(tb, fg_color=CARD)
        ghost_button(self.log_tools, t("copy"), self.copy_log, width=self.text_width(t("copy"), sans(12)) + 28,
                     height=28).pack(side=end())
        ghost_button(self.log_tools, t("clear"), self.clear_logs, width=self.text_width(t("clear"), sans(12)) + 28,
                     height=28).pack(side=end(), padx=pads(0, 6))
        self.diag_tools = frame(tb, fg_color=CARD)
        ghost_button(self.diag_tools, t("copy"), self.copy_diag, width=self.text_width(t("copy"), sans(12)) + 28,
                     height=28).pack(side=end())
        ghost_button(self.diag_tools, t("diag_browse"), self.browse_diag_log,
                     width=self.text_width(t("diag_browse"), sans(12)) + 28, height=28).pack(side=end(), padx=pads(0, 6))
        ghost_button(self.diag_tools, t("diag_analyze"), lambda: self.run_diagnostics(),
                     width=self.text_width(t("diag_analyze"), sans(12)) + 28, height=28).pack(side=end(), padx=pads(0, 6))
        btn_ai_rep = ghost_button(self.diag_tools, t("ai_report_btn"), self.show_ai_snapshot,
                                  width=self.text_width(t("ai_report_btn"), sans(12)) + 28, height=28)
        btn_ai_rep.pack(side=end(), padx=pads(0, 6))
        Tooltip(btn_ai_rep, t("ai_report_tip"))
        btn_ai_imp = ghost_button(self.diag_tools, t("ai_import_btn"), self.open_ai_import_dialog,
                                  width=self.text_width(t("ai_import_btn"), sans(12)) + 28, height=28)
        btn_ai_imp.pack(side=end(), padx=pads(0, 6))
        Tooltip(btn_ai_imp, t("ai_import_tip"))

        divider(c).grid(row=1, column=0, sticky="ew")
        body = frame(c, fg_color=CARD)
        body.grid(row=2, column=0, sticky="nsew", padx=pads(6, 4), pady=(2, 8))
        body.grid_columnconfigure(0, weight=1)
        body.grid_rowconfigure(0, weight=1)

        self.views = {}
        rf = frame(body, fg_color=CARD)
        self.tree = self.make_tree(rf, self.RESULT_COLUMNS)
        for key, *_ in self.RESULT_COLUMNS:
            self.tree.heading(self.tree_key(key), command=lambda k=key: self.on_sort(k))
        self.lbl_empty = ctk.CTkLabel(rf, text="", font=sans(13), text_color=MUTED, fg_color=CARD, justify="center")
        self.views["Results"] = rf

        bf = frame(body, fg_color=CARD)
        self.best_tree = self.make_tree(bf, self.BEST_COLUMNS)
        self.views["Best routes"] = bf

        lf = frame(body, fg_color=CARD)
        self.log_box = tk.Text(lf, bg=CARD, fg=TEXT_2, font=mono(10), relief="flat", borderwidth=0,
                               state="disabled", padx=10, pady=8, selectbackground=SELECTED,
                               insertbackground=TEXT, highlightthickness=0)
        self.log_box.pack(fill="both", expand=True)
        for tag, color in (("SUCCESS", GOOD), ("FAILURE", BAD), ("WARN", WARN), ("INFO", TEXT_2), ("TS", DIM)):
            self.log_box.tag_config(tag, foreground=color)
        self.log_box.tag_config("HEADER", foreground=ACCENT, font=mono(10, True))
        self.views["Log"] = lf

        df = frame(body, fg_color=CARD)
        label(df, t("diag_hint"), 11, MUTED, wraplength=760).pack(anchor=a_start(), fill="x", padx=12, pady=(8, 4))
        self.diag_box = tk.Text(df, bg=CARD, fg=TEXT_2, font=mono(10), relief="flat", borderwidth=0,
                                state="disabled", padx=10, pady=8, selectbackground=SELECTED,
                                insertbackground=TEXT, highlightthickness=0)
        self.diag_box.pack(fill="both", expand=True)
        self.views["Diagnostics"] = df

        for tree in (self.tree, self.best_tree):
            tree.bind("<Double-1>", lambda _e, tr=tree: self.connect_selected(tr))
            tree.bind("<Button-3>", lambda e, tr=tree: self.show_row_menu(e, tr))
            if platform.system() == "Darwin":
                tree.bind("<Button-2>", lambda e, tr=tree: self.show_row_menu(e, tr))

        self.row_menu = tk.Menu(self, tearoff=0, bg=INPUT, fg=TEXT, activebackground=SELECTED,
                                activeforeground=TEXT, bd=0, font=sans(10))
        self.row_menu.add_command(label=vis(t("menu_connect")), command=lambda: self.connect_selected(self._menu_tree))
        self.row_menu.add_separator()
        self.row_menu.add_command(label=vis(t("menu_copy_route")), command=lambda: self.copy_selected("route"))
        self.row_menu.add_command(label=vis(t("menu_copy_row")), command=lambda: self.copy_selected("row"))
        self._menu_tree = self.tree

        self.set_view("Results")
        self.set_result_filter("All")
        return c

    @staticmethod
    def tree_key(key):
        # Farsi tables are mirrored; the tree column (#0) is pinned to the left, so the location becomes a data column.
        return "loc" if i18n.RTL and key == "#0" else key

    def make_tree(self, parent, columns):
        parent.grid_columnconfigure(gcol(0, 2), weight=1)
        parent.grid_rowconfigure(0, weight=1)
        keys = [self.tree_key(c[0]) for c in columns]
        data_keys = [k for k in keys if k != "#0"]
        tree = ttk.Treeview(parent, columns=data_keys, show="headings" if i18n.RTL else "tree headings",
                            style="AS.Treeview", selectmode="browse")
        if i18n.RTL:
            tree["displaycolumns"] = data_keys[::-1]
        for (key, text, width, numeric), tkey in zip(columns, keys):
            anchor = ("w" if i18n.RTL else "e") if numeric else a_start()
            tree_heading(tree, tkey, t(text), anchor)
            tree.column(tkey, width=int(width * self.scale), minwidth=40, anchor=anchor, stretch=False)
        specs = [(k, c[2] * self.scale) for k, c in zip(keys, columns)]
        total = sum(w for _, w in specs)

        def fit(event):
            # Every column always fits: the location column takes any spare room, and when space is short
            # all columns shrink together (Tk would otherwise push the last ones out of view).
            available = event.width - 2
            if available >= total:
                for k, w in specs[1:]:
                    tree.column(k, width=int(w))
                tree.column(specs[0][0], width=int(available - (total - specs[0][1])))
            else:
                for k, w in specs:
                    tree.column(k, width=max(30, int(w * available / total)))

        tree.bind("<Configure>", fit, add="+")
        tree.tag_configure("odd", background=ROW_ALT)
        tree.tag_configure("muted", foreground=MUTED)
        sb = ctk.CTkScrollbar(parent, command=tree.yview, button_color=BORDER_2, button_hover_color=HOVER)
        tree.configure(yscrollcommand=sb.set)
        tree.grid(row=0, column=gcol(0, 2), sticky="nsew")
        sb.grid(row=0, column=gcol(1, 2), sticky="ns")
        return tree

    def tree_insert(self, tree, iid, name, image, values, tags):
        if i18n.RTL:
            tree.insert("", "end", iid=iid, values=tuple(vis(v) for v in (name,) + tuple(values)), tags=tags)
        else:
            tree.insert("", "end", iid=iid, text=f"  {name}", image=image, values=values, tags=tags)

    def build_insights(self, parent):
        works = card(parent)
        works.pack(fill="x")
        label(works, t("works_title"), 14, bold=True).pack(anchor=a_start(), fill="x", padx=16, pady=(14, 0))
        label(works, t("works_sub"), 11, MUTED).pack(anchor=a_start(), fill="x", padx=16)
        self.works_rows = frame(works, fg_color=CARD)
        self.works_rows.pack(fill="x", padx=16, pady=(12, 0))
        self.lbl_tip = label(works, "", 11, TEXT_2, wraplength=250)
        self.works_pad = frame(works, height=12, fg_color=CARD)
        self.works_pad.pack()

    # ---------------- views ----------------
    def on_view_clicked(self, shown):
        for v in self.VIEWS:
            if t(self.VIEW_KEYS[v]) == shown:
                self.set_view(v)

    def set_view(self, name):
        self.view = name
        self.seg_view.set(t(self.VIEW_KEYS[name]))
        for key, f in self.views.items():
            if key == name:
                f.grid(row=0, column=0, sticky="nsew")
            else:
                f.grid_remove()
        self.results_tools.pack_forget()
        self.best_tools.pack_forget()
        self.log_tools.pack_forget()
        self.diag_tools.pack_forget()
        if name == "Results":
            self.results_tools.pack(side=start(), fill="x", expand=True, padx=pads(10, 0))
        elif name == "Best routes":
            self.best_tools.pack(side=start(), fill="x", expand=True, padx=pads(10, 0))
        elif name == "Log":
            self.log_tools.pack(side=start(), fill="x", expand=True, padx=pads(10, 0))
        elif name == "Diagnostics":
            self.diag_tools.pack(side=start(), fill="x", expand=True, padx=pads(10, 0))
            if not self.diag_box.get("1.0", "end-1c").strip():
                self.run_diagnostics(silent_if_missing=True)

    def set_result_filter(self, name):
        self.result_filter = name
        self.render_results()

    def show_hero(self, which):
        if which == "rec":
            self.live_card.grid_remove()
            self.rec_card.grid()
        else:
            self.rec_card.grid_remove()
            self.live_card.grid()

    # ---------------- toasts ----------------
    def toast(self, msg, kind="info", action=None, action_text=None, ms=4000):
        if self._toast is not None:
            try:
                self._toast.destroy()
            except tk.TclError:
                pass
        color = {"info": ACCENT, "success": GOOD, "error": BAD, "warn": WARN}.get(kind, ACCENT)
        toast = ctk.CTkFrame(self, fg_color=INPUT, corner_radius=10, border_width=1, border_color=BORDER_2)
        ctk.CTkFrame(toast, fg_color=color, width=4, height=1, corner_radius=2).pack(
            side=start(), fill="y", padx=pads(10, 0), pady=10)
        label(toast, msg, 12, wraplength=360).pack(side=start(), padx=12, pady=10)

        def close():
            try:
                toast.destroy()
            except tk.TclError:
                pass

        if action:
            ghost_button(toast, action_text, lambda: (action(), close()),
                         width=max(90, self.text_width(action_text, sans(12)) + 28), height=28,
                         fg_color=INPUT).pack(side=start(), padx=pads(0, 10))
        if i18n.RTL:
            toast.place(relx=0.0, rely=1.0, x=24, y=-24, anchor="sw")
        else:
            toast.place(relx=1.0, rely=1.0, x=-24, y=-24, anchor="se")
        toast.lift()
        toast.bind("<Button-1>", lambda _e: close())
        self._toast = toast
        self.after(ms, close)

    # ---------------- header / hero ----------------
    def render_header(self):
        run = self.run
        badge = None
        if self.worker_running() and run and run["kind"] == "job":
            title = t("testing", scope=run["scope"])
            sub = t("started", t=run["started"].strftime("%H:%M"))
            if run["profile"] != "Manual":
                sub += t("with_profile", p=run["profile"])
        elif run and run.get("finished"):
            took = i18n.duration((run["finished"] - run["started"]).total_seconds())
            sub = t("finished_sub", scope=run["scope"], t=run["finished"].strftime("%H:%M"), d=took)
            if run.get("kept"):
                title, badge = t("found_route"), (t("stopped_first"), GOOD_SOFT, GOOD_TEXT)
            elif run["stopped"]:
                title = t("run_stopped")
                badge = (t("n_of_tests", a=num(run.get("current", 0)), b=num(run.get("total", 0))),
                         WARN_SOFT, WARN_TEXT)
            else:
                title = t("run_complete")
                total = run.get("total", 0)
                badge = (t("n_of_tests", a=num(total), b=num(total)), GOOD_SOFT, GOOD_TEXT) if total else None
        else:
            scope_title, _ = self.scope_summary()
            title, sub = t("ready"), t("ready_sub", scope=scope_title, n=num(self.test_count()))
        self.lbl_title.configure(text=title)
        self.lbl_sub.configure(text=sub)
        if badge:
            self.lbl_badge.configure(text=f"  {badge[0]}  ", fg_color=badge[1], text_color=badge[2])
            self.lbl_badge.pack(side=start(), padx=pads(12, 0))
        else:
            self.lbl_badge.pack_forget()

    def render_hero(self):
        if self.worker_running():
            self.show_hero("live")
            return
        best = self.best_result()
        if best:
            eff_ping = best["ping"] if best["ping"] is not None else best.get("http_ms")
            self.lbl_rec_name.configure(text=loc_name(best["city"], best["node"]))
            self.lbl_rec_country.configure(text=best["country"])
            self.lbl_rec_route.configure(text=f" {best['proto']}:{best['port']} ")
            self.rec_stats["ping"].configure(
                text=f"{eff_ping:.0f} {t('ms')}" if eff_ping is not None else "–",
                text_color=ping_color(eff_ping))
            self.rec_stats["loss"].configure(text=f"{best['loss']:.0f}%" if best["loss"] is not None else "–")
            self.rec_stats["time"].configure(text=t("secs", v=f"{best['duration']:.1f}"))
            self.show_hero("rec")
        else:
            self.reset_live_idle()
            self.show_hero("live")

    def reset_live_idle(self):
        title, sub = self.scope_summary()
        self.lbl_caption.configure(text=t("cap_ready").upper(), text_color=MUTED)
        self.lbl_target.configure(text=title)
        self.lbl_target_sub.configure(text=sub)
        self.lbl_route.pack_forget()
        self.lbl_ping.configure(text="–", text_color=TEXT)
        self.lbl_ping_detail.configure(text=" ")
        self.reset_phases()
        self.progress_bar.show(0)
        self.lbl_prog_left.configure(text=t("tests_queued", n=num(self.test_count())))
        self.lbl_prog_right.configure(text=t("press_start"))

    def set_target(self, caption_key, city, node, country, route):
        self.lbl_caption.configure(text=t(caption_key).upper(), text_color=ACCENT)
        self.lbl_target.configure(text=loc_name(city, node))
        self.lbl_target_sub.configure(text=country)
        self.lbl_route.configure(text=f" {route} ")
        self.lbl_route.pack(side=start(), padx=pads(8, 0))
        self.lbl_ping.configure(text="–", text_color=TEXT)
        self.lbl_ping_detail.configure(text=" ")
        self.reset_phases()

    def reset_phases(self):
        for bar, name_lbl, time_lbl in self.phase_widgets:
            bar.show(0, BORDER_2)
            name_lbl.configure(text_color=MUTED, font=sans(12))
            time_lbl.configure(text="")

    def set_phase(self, idx, state, secs=None):
        bar, name_lbl, time_lbl = self.phase_widgets[idx]
        if state == "active":
            bar.busy(ACCENT)
            name_lbl.configure(text_color=TEXT, font=sans(12, True))
            time_lbl.configure(text="…", text_color=ACCENT)
            return
        bar.show(1, {"done": GOOD, "fail": BAD}.get(state, BORDER_2))
        name_lbl.configure(text_color=TEXT_2, font=sans(12))
        if state == "skip":
            time_lbl.configure(text=t("skipped"), text_color=MUTED)
        elif state == "fail" and secs is None:
            time_lbl.configure(text=t("failed_lc"), text_color=BAD)
        else:
            time_lbl.configure(text=t("secs", v=f"{secs:.1f}") if secs is not None else "",
                               text_color=BAD if state == "fail" else MUTED)

    def record_ai_error(self, msg):
        self._recent_ai_errors.append(msg)
        if len(self._recent_ai_errors) > 30:
            self._recent_ai_errors = self._recent_ai_errors[-30:]

    def show_ai_snapshot(self):
        snap = generate_ai_snapshot(
            DB_FILE,
            current_strategy=getattr(self, "_active_ai_strategy", "AUTO"),
            recent_errors=getattr(self, "_recent_ai_errors", []),
        )
        self.diag_box.configure(state="normal")
        self.diag_box.delete("1.0", "end")
        self.diag_box.insert("1.0", snap)
        self.diag_box.configure(state="disabled")
        self.set_view("Diagnostics")
        self.clipboard_clear()
        self.clipboard_append(snap)
        self.toast(t("copied"), "success")

    def open_ai_import_dialog(self):
        dlg = ctk.CTkToplevel(self)
        dlg.title(t("ai_import_title"))
        dlg.configure(fg_color=BG)
        dlg.transient(self)

        label(dlg, t("ai_import_hint"), 12, TEXT_2, wraplength=510).pack(anchor=a_start(), padx=18, pady=(16, 8))
        txt = ctk.CTkTextbox(dlg, fg_color=INPUT, text_color=TEXT, border_width=1, border_color=BORDER_2,
                             font=mono(11), corner_radius=8)
        txt.pack(fill="both", expand=True, padx=18, pady=(0, 12))

        def apply_cfg():
            raw = txt.get("1.0", "end").strip()
            try:
                cfg = parse_and_apply_ai_config(raw, DB_FILE)
            except Exception as e:
                messagebox.showerror(t("ai_import_title"), t("ai_import_err", err=str(e)), parent=dlg)
                return

            if "priority_order" in cfg:
                self.priority_order = self.sanitize_priority(cfg["priority_order"])
                self.refresh_protocol_list()
            if "protocols" in cfg:
                for p, p_var in self.protocol_vars.items():
                    if p in cfg["protocols"]:
                        p_var.set(True)
                        wanted = set(cfg["protocols"][p])
                        for port_num, pv in self.port_vars[p].items():
                            pv.set(port_num in wanted)
                    else:
                        p_var.set(False)
                self.refresh_protocol_list()
            if "timeout" in cfg:
                self.set_entry(self.entry_timeout, str(cfg["timeout"]))
            if "hold_seconds" in cfg:
                self.set_entry(self.entry_hold, str(cfg["hold_seconds"]))
            if "http_check" in cfg:
                self.sw_http_check.select() if cfg["http_check"] else self.sw_http_check.deselect()
            if "speed_burst" in cfg:
                self.sw_speed_burst.select() if cfg["speed_burst"] else self.sw_speed_burst.deselect()
            if "strategy" in cfg:
                self._active_ai_strategy = cfg["strategy"]
                self.update_ai_status(cfg["strategy"], {})

            self.update_timing_summary()
            self.update_scope_preview(user_change=True)
            self.save_all_config()
            note = f" — {cfg['note']}" if cfg.get("note") else ""
            self.log_message(f"[AI Import] Applied external AI config{note}", "HEADER")
            self.toast(t("ai_import_ok", n=cfg.get("seeded_arms", 0)), "success", ms=5000)
            dlg.grab_release()
            dlg.destroy()

        def _close_dlg(_e=None):
            try:
                dlg.grab_release()
            except Exception:
                pass
            dlg.destroy()

        foot = frame(dlg, fg_color=BG)
        foot.pack(fill="x", padx=18, pady=(0, 16))
        primary_button(foot, t("ai_import_apply"), apply_cfg, height=36).pack(side=end())
        ghost_button(foot, t("cancel"), _close_dlg, width=80, height=36).pack(side=end(), padx=pads(0, 8))
        dlg.bind("<Escape>", _close_dlg)
        dlg.protocol("WM_DELETE_WINDOW", _close_dlg)
        place_dialog(dlg, self, 560, 440)
        dlg.update_idletasks()
        dlg.lift()
        dlg.grab_set()
        dlg.focus_force()
        txt.focus_set()

    def update_ai_status(self, strategy_name, summary):
        self._active_ai_strategy = strategy_name
        if not hasattr(self, "lbl_ai_status"):
            return
        if not summary:
            self.lbl_ai_status.configure(text=f"AI: {strategy_name}")
            return
        top = sorted(summary.items(), key=lambda kv: kv[1].get("prob", 0.5), reverse=True)[:3]
        probs_txt = " · ".join(f"{PROTO_NAMES.get(p, p)} {int(d['prob']*100)}%" for p, d in top)
        self.lbl_ai_status.configure(text=f"AI: {strategy_name}  |  {probs_txt}")

    def set_network_paused(self, paused):
        now = time.time()
        if paused:
            if self.run and not self.run.get("pause_started_ts"):
                self.run["pause_started_ts"] = now
            self.lbl_caption.configure(text=t("cap_paused_net").upper(), text_color=WARN)
            self.title(f"{APP_NAME} · {t('cap_paused_net')}")
        else:
            if self.run and self.run.get("pause_started_ts"):
                self.run["paused_total_secs"] = self.run.get("paused_total_secs", 0.0) + max(0.0, now - self.run["pause_started_ts"])
                self.run["pause_started_ts"] = None
            if self.worker.running:
                self.lbl_caption.configure(text=t("cap_testing").upper(), text_color=ACCENT)

    def begin_test(self, i, total, executed, city, node, country, route):
        self.step = (i, total, executed, time.time())
        if self.run:
            self.run.update(current=i, total=total)
        self.set_target("cap_testing", city, node, country, route)
        self.progress_bar.show((i - 1) / total)
        self.lbl_prog_left.configure(text=t("test_progress", i=num(i), total=num(total),
                                            pct=int((i - 1) / total * 100)))
        self.title(f"{APP_NAME}  ·  {i}/{total}")

    def set_ping(self, result, http_ms=None, speed_kbps=None):
        extra = ""
        if http_ms is not None:
            extra += f" · HTTP {http_ms:.0f}ms"
        if speed_kbps is not None:
            extra += f" · {speed_kbps:.0f}KB/s"
        if result:
            self.lbl_ping.configure(text=f"{result['avg']:.0f}", text_color=ping_color(result["avg"]))
            detail = t("ping_detail", a=f"{result['min']:.0f}", b=f"{result['max']:.0f}", c=f"{result['loss']:.0f}") + extra
            self.lbl_ping_detail.configure(text=detail)
        elif http_ms is not None:
            self.lbl_ping.configure(text=f"{http_ms:.0f}", text_color=ping_color(http_ms))
            self.lbl_ping_detail.configure(text=f"HTTP {http_ms:.0f} ms · ICMP {t('no_reply')}" + (f" · {speed_kbps:.0f}KB/s" if speed_kbps else ""))
        else:
            self.lbl_ping.configure(text="–", text_color=BAD)
            self.lbl_ping_detail.configure(text=t("no_reply"))

    def set_connected(self, text):
        self.connected_to = text
        if text:
            self.lbl_conn.configure(text=f"   ●  {t('connected_chip', x=text)}   ")
            self.lbl_conn.grid()
        else:
            self.lbl_conn.grid_remove()

    def _tick(self):
        run = self.run
        now = time.time()
        if self.worker_running() and run and run["kind"] == "job" and not run.get("finished"):
            elapsed = t("elapsed", t=i18n.duration(now - run["started_ts"]))
            text = elapsed
            if self.step:
                i, total, executed, step_ts = self.step
                if executed > 1 and not run.get("pause_started_ts"):
                    active_secs = max(1.0, (step_ts - run["started_ts"]) - run.get("paused_total_secs", 0.0))
                    avg = active_secs / (executed - 1)
                    left = max(avg * (total - i + 1) - (now - step_ts), avg * (total - i))
                    text = t("time_left", left=i18n.duration(left), elapsed=elapsed)
                else:
                    text = t("estimating", elapsed=elapsed)
            self.lbl_prog_right.configure(text=text)
        elif (not self.worker_running() and self.connected_to and hasattr(self, "sw_watchdog")
              and self.sw_watchdog.get() and not self._watchdog_busy and now - self._last_watchdog_ts >= 25.0):
            self._last_watchdog_ts = now
            self._run_watchdog_check()
        self.after(1000, self._tick)

    def _run_watchdog_check(self):
        """Background health check for active connection. Rotates IP or fails over to next best route if dropped."""
        self._watchdog_busy = True
        host = self.entry_ping_host.get().strip() or "1.1.1.1"
        http_check = bool(self.sw_http_check.get())
        http_url = self.entry_http_url.get().strip() or HttpChecker.DEFAULT_URL

        def check_work():
            try:
                os_ok, os_reason = InternetMonitor.os_network_connected()
                if not os_ok:
                    self.post(self.log_message, f"[Watchdog] Host network offline ({os_reason}); skipping failover.", "WARN")
                    return
                _, st_out = self.worker.run_cli(["status"])
                still_conn = self.worker.is_connected_output(st_out)
                healthy = False
                if still_conn:
                    p_res, _ = self.worker.pinger.run(host, count=2, reply_timeout_ms=1500)
                    h_ms = None
                    if http_check:
                        h_ms, _ = self.worker.http_checker.check(http_url, timeout=4.0)
                    healthy = bool(p_res) or (h_ms is not None)
                    if not healthy:
                        # First attempt IP rotation on the same server before full failover
                        rotated, new_ip = self.worker.rotate_ip()
                        if rotated:
                            time.sleep(2.0)
                            p2, _ = self.worker.pinger.run(host, count=2, reply_timeout_ms=1500)
                            h2 = None
                            if not p2 and http_check:
                                h2, _ = self.worker.http_checker.check(http_url, timeout=4.0)
                            if p2 or h2 is not None:
                                self.post(self.toast, t("watchdog_rotated", ip=new_ip or "OK"), "info", None, None, 4000)
                                self.post(self.log_message, f"[Watchdog] Rotated IP on active server ({new_ip}).", "SUCCESS")
                                return
                if not healthy:
                    os_ok2, _ = InternetMonitor.os_network_connected()
                    if not os_ok2:
                        self.post(self.log_message, "[Watchdog] Host network went offline; preserving route status.", "WARN")
                        return
                    self.post(self._trigger_watchdog_failover)
            finally:
                self._watchdog_busy = False

        threading.Thread(target=check_work, daemon=True).start()

    def _trigger_watchdog_failover(self):
        if self.worker_running() or not self.connected_to:
            return
        # Mark the currently failed route as DPI_RESET so best_routes() picks the next working route
        cur = self.connected_route
        if cur:
            cur["status"] = "DPI_RESET"
            self.worker.db.record_result(
                cur.get("node", ""), cur["city"], cur["country"], cur["proto"], cur["port"],
                "DPI_RESET", cur.get("duration", 0), cur.get("ping"), cur.get("loss"),
                self.current_profile_name or "Manual", cur.get("http_ms"), cur.get("speed_kbps"), cur.get("vpn_ip")
            )
            self.render_data()
        candidates = self.best_routes()
        if candidates:
            nxt = candidates[0]
            where = loc_name(nxt["city"], nxt["node"])
            route = f"{nxt['proto']}:{nxt['port']}"
            self.log_message(f"[Watchdog] Active connection dropped! Auto-switching to {where} ({route})...", "WARN")
            self.toast(t("watchdog_failover", w=where, r=route), "warn", ms=6000)
            self.connect_result(nxt)
        else:
            self.set_connected(None)

    # ---------------- results ----------------
    def add_result_row(self, city, node, country, proto, port, status, duration, ping, loss,
                       http_ms=None, speed_kbps=None, vpn_ip=None):
        # Update existing in-memory entry if re-verifying the same route
        for existing in self.results:
            if (existing["city"] == city and existing["node"] == (node or "")
                    and existing["country"] == country and existing["proto"] == proto and existing["port"] == port):
                existing.update({"status": status, "duration": duration or 0, "ping": ping,
                                 "loss": loss, "http_ms": http_ms, "speed_kbps": speed_kbps, "vpn_ip": vpn_ip or ""})
                self.render_data()
                return
        self.results.append({"id": len(self.results), "city": city, "node": node or "", "country": country,
                             "proto": proto, "port": port, "status": status, "duration": duration or 0,
                             "ping": ping, "loss": loss, "http_ms": http_ms,
                             "speed_kbps": speed_kbps, "vpn_ip": vpn_ip or ""})
        self.render_data()

    def reload_results_table(self):
        self.results = []
        for row in self.worker.db.fetch_results():
            city, node, country, proto, port, status, duration, ping, loss = row[:9]
            http_ms = row[9] if len(row) > 9 else None
            speed_kbps = row[10] if len(row) > 10 else None
            vpn_ip = row[11] if len(row) > 11 else ""
            self.results.append({"id": len(self.results), "city": city, "node": node or "", "country": country,
                                 "proto": proto, "port": port, "status": status, "duration": duration or 0,
                                 "ping": ping, "loss": loss, "http_ms": http_ms,
                                 "speed_kbps": speed_kbps, "vpn_ip": vpn_ip or ""})
        self.render_data()

    def render_data(self):
        self.render_results()
        self.render_best()
        self.render_stats()
        self.render_insights()
        if not self.worker_running():
            self.render_hero()

    def best_routes(self):
        rows = [r for r in self.results if r["status"] == "SUCCESS" and (r["ping"] is not None or r.get("http_ms") is not None)]
        rows.sort(key=lambda r: (
            r["ping"] if r["ping"] is not None else r.get("http_ms", float("inf")),
            r["loss"] or 0,
            r.get("http_ms") if r.get("http_ms") is not None else float("inf"),
            r["duration"],
        ))
        return rows

    def best_result(self):
        rows = self.best_routes()
        return rows[0] if rows else None

    @staticmethod
    def status_label(status):
        key = f"status_{status}"
        return t(key) if key in i18n.STRINGS else status

    def result_values(self, r):
        return (r["country"], f"{r['proto']}:{r['port']}", self.status_label(r["status"]),
                t("secs", v=f"{r['duration']:.1f}") if r["status"] == "SUCCESS" else "–",
                f"{r['ping']:.0f} {t('ms')}" if r["ping"] is not None else "–",
                f"{r['loss']:.0f}%" if r["loss"] is not None else "–",
                f"{r['http_ms']:.0f} {t('ms')}" if r.get("http_ms") is not None else "–",
                f"{r['speed_kbps']:.0f} KB/s" if r.get("speed_kbps") is not None else "–",
                r.get("vpn_ip") or "–")

    def render_results(self):
        if not hasattr(self, "tree"):
            return
        query = self.entry_search.get().strip().lower()
        ok = sum(1 for r in self.results if r["status"] == "SUCCESS")
        counts = {"All": len(self.results), "Connected": ok, "Failed": len(self.results) - ok}
        for name, b in self.filter_buttons.items():
            active = name == self.result_filter
            b.configure(text=f"{t(self.FILTER_KEYS[name])}  {num(counts[name])}",
                        fg_color=ACCENT_SOFT if active else "transparent",
                        border_color=ACCENT_LINE if active else BORDER_2, text_color=TEXT if active else TEXT_2)

        rows = []
        for r in self.results:
            if self.result_filter == "Connected" and r["status"] != "SUCCESS":
                continue
            if self.result_filter == "Failed" and r["status"] == "SUCCESS":
                continue
            if query:
                hay = f"{loc_name(r['city'], r['node'])} {r['country']} {r['proto']}:{r['port']} " \
                      f"{self.status_label(r['status'])}".lower()
                if not all(tok in hay for tok in query.split()):
                    continue
            rows.append(r)
        if self.sort_col:
            rows.sort(key=self.SORT_KEYS[self.sort_col], reverse=self.sort_desc)
        else:
            rows.reverse()  # newest first

        self.tree.delete(*self.tree.get_children())
        for n, r in enumerate(rows):
            tags = ["odd" if n % 2 else "even"]
            if r["status"] != "SUCCESS":
                tags.append("muted")
            self.tree_insert(self.tree, str(r["id"]), loc_name(r["city"], r["node"]), self.dots[r["status"]],
                             self.result_values(r), tags)

        if not self.results:
            self.lbl_empty.configure(text=t("empty_results"))
            self.lbl_empty.place(relx=0.5, rely=0.5, anchor="center")
        elif not rows:
            self.lbl_empty.configure(text=t("empty_filter"))
            self.lbl_empty.place(relx=0.5, rely=0.5, anchor="center")
        else:
            self.lbl_empty.place_forget()

    def render_best(self):
        rows = self.best_routes()
        self.best_tree.delete(*self.best_tree.get_children())
        for n, r in enumerate(rows[:100], 1):
            eff_ping = r["ping"] if r["ping"] is not None else r.get("http_ms")
            self.tree_insert(self.best_tree, str(r["id"]), f"{n}.  {loc_name(r['city'], r['node'])}",
                             self.dots[ping_quality(eff_ping)],
                             (r["country"], f"{r['proto']}:{r['port']}",
                              f"{r['ping']:.0f} {t('ms')}" if r["ping"] is not None else "–",
                              f"{r['loss']:.0f}%" if r["loss"] is not None else "–",
                              f"{r['http_ms']:.0f} {t('ms')}" if r.get("http_ms") is not None else "–",
                              f"{r['speed_kbps']:.0f} KB/s" if r.get("speed_kbps") is not None else "–",
                              r.get("vpn_ip") or "–",
                              t("secs", v=f"{r['duration']:.1f}")),
                             ("odd" if n % 2 == 0 else "even",))

    def render_stats(self):
        total = len(self.results)
        ok_rows = [r for r in self.results if r["status"] == "SUCCESS"]
        s = self.stat_labels
        s["ok"].configure(text=num(len(ok_rows)))
        s["fail"].configure(text=num(total - len(ok_rows)))
        s["rate"].configure(text=f"{len(ok_rows) / total:.0%}" if total else "–")
        best = self.best_result()
        eff_ping = (best["ping"] if best["ping"] is not None else best.get("http_ms")) if best else None
        s["best"].configure(text=f"{eff_ping:.0f} {t('ms')}" if eff_ping is not None else "–",
                            text_color=ping_color(eff_ping) if eff_ping is not None else TEXT)
        s["avg"].configure(text=t("secs", v=f"{sum(r['duration'] for r in ok_rows) / len(ok_rows):.1f}")
                           if ok_rows else "–")

    def render_insights(self):
        for w in self.works_rows.winfo_children():
            w.destroy()
        stats = {}
        for r in self.results:
            s = stats.setdefault(r["proto"], [0, 0])
            s[1] += 1
            if r["status"] == "SUCCESS":
                s[0] += 1
        if not stats:
            label(self.works_rows, t("works_empty"), 11, MUTED, wraplength=250).pack(anchor=a_start(), fill="x")
        for proto, (ok, total) in sorted(stats.items(), key=lambda kv: -kv[1][0] / kv[1][1]):
            rate = ok / total
            row = frame(self.works_rows, fg_color=CARD)
            row.pack(fill="x", pady=(0, 10))
            top = frame(row, fg_color=CARD)
            top.pack(fill="x")
            label(top, PROTO_NAMES.get(proto, proto), 12).pack(side=start())
            label(top, f"{rate:.0%}", font=mono(11)).pack(side=end())
            label(top, f"{ok}/{total}", font=mono(11), text_color=MUTED).pack(side=end(), padx=pads(0, 10))
            bar = Bar(row, BORDER, rate_color(rate), height=6, corner_radius=3)
            bar.show(rate)
            bar.pack(fill="x", pady=(4, 0))

        weak = [p for p, (ok, total) in stats.items() if total >= 4 and ok / total < 0.4]
        if weak and len(weak) < len(stats) and not self.worker_running():
            names = t("and").join(PROTO_NAMES.get(p, p) for p in weak)
            self.lbl_tip.configure(text=t("tip_one" if len(weak) == 1 else "tip_many", names=names))
            self.lbl_tip.pack(fill="x", padx=16, pady=(2, 0), before=self.works_pad)
        else:
            self.lbl_tip.pack_forget()

    def on_sort(self, col):
        if self.sort_col == col:
            if self.sort_desc:
                self.sort_col, self.sort_desc = None, False  # third click: back to newest first
            else:
                self.sort_desc = True
        else:
            self.sort_col, self.sort_desc = col, False
        for key, text, _, _ in self.RESULT_COLUMNS:
            arrow = ("  ↓" if self.sort_desc else "  ↑") if key == self.sort_col else ""
            title = vis(t(text))
            self.tree.heading(self.tree_key(key), text=(arrow.strip() + "  " + title) if arrow and i18n.RTL
                              else title + arrow)
        self.render_results()

    def selected_result(self, tree):
        sel = tree.selection()
        if not sel:
            return None
        idx = int(sel[0])
        return self.results[idx] if 0 <= idx < len(self.results) else None

    def show_row_menu(self, event, tree):
        row = tree.identify_row(event.y)
        if not row:
            return
        tree.selection_set(row)
        self._menu_tree = tree
        self.row_menu.entryconfigure(0, state="disabled" if self.worker.running else "normal")
        try:
            self.row_menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.row_menu.grab_release()

    def copy_selected(self, what):
        r = self.selected_result(self._menu_tree)
        if not r:
            return
        if what == "route":
            text = f"{r['city']}  {r['proto']}:{r['port']}"
        else:
            text = "\t".join((loc_name(r["city"], r["node"]),) + self.result_values(r))
        self.clipboard_clear()
        self.clipboard_append(text)
        self.toast(t("copied"), "success", ms=1800)

    # ---------------- log (kept in English: it is technical output, handy for bug reports) ----------------
    def log_message(self, msg, tag="INFO"):
        ts = datetime.datetime.now().strftime("%H:%M:%S  ")
        self.log_box.configure(state="normal")
        self.log_box.insert("end", ts, "TS")
        self.log_box.insert("end", msg + "\n", tag)
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

    def clear_logs(self):
        self.log_box.configure(state="normal")
        self.log_box.delete("1.0", "end")
        self.log_box.configure(state="disabled")

    def copy_log(self):
        self.clipboard_clear()
        self.clipboard_append(self.log_box.get("1.0", "end-1c"))
        self.toast(t("log_copied"), "success", ms=1800)

    def run_diagnostics(self, target_path="", silent_if_missing=False):
        report, err = LogAnalyzer.analyze(target_path=target_path, cli_path=self.entry_cli.get())
        self.diag_box.configure(state="normal")
        self.diag_box.delete("1.0", "end")
        if report:
            self.diag_box.insert("end", report + "\n")
            if not silent_if_missing:
                self.toast(t("diag_done"), "success", ms=2500)
        else:
            self.diag_box.insert("end", (err or t("diag_not_found")) + "\n")
            if not silent_if_missing:
                self.toast(err or t("diag_not_found"), "warn", ms=4000)
        self.diag_box.configure(state="disabled")

    def browse_diag_log(self):
        path = filedialog.askopenfilename(
            title=vis(t("diag_browse")),
            filetypes=[("Windscribe log.bin", "log.bin *.bin *.log"), (vis(t("all_files")), "*.*")]
        )
        if not path:
            path = filedialog.askdirectory(title=vis(t("diag_browse")))
        if path:
            self.set_view("Diagnostics")
            self.run_diagnostics(target_path=path)

    def copy_diag(self):
        self.clipboard_clear()
        self.clipboard_append(self.diag_box.get("1.0", "end-1c"))
        self.toast(t("copied"), "success", ms=1800)

    # ---------------- language ----------------
    def change_language(self, shown):
        code = next((c for c, name in i18n.LANGUAGES.items() if name == shown), "en")
        if code == i18n.LANG:
            return
        if self.worker.running:
            self.seg_lang.set(i18n.LANGUAGES[i18n.LANG])
            self.toast(t("lang_busy"), "warn")
            return
        self.config_data["language"] = code
        self.relaunch = True
        self.on_close()

    # ---------------- scope ----------------
    def open_location_picker(self):
        if self._picker is not None and self._picker.winfo_exists():
            self._picker.focus()
            return
        if not self.locations:
            self.toast(t("no_list_toast"), "warn", action=self.update_locations, action_text=t("download"), ms=7000)
            return
        self._picker = LocationPicker(self, self.locations, self.selected_keys, self.on_locations_chosen)

    def refresh_locations_info(self):
        """The missing-list hint and the 'last updated' tooltip in the sidebar."""
        updated = LocationManager.last_updated()
        self.tip_update_list.text = t("update_tip") + "\n" + (
            t("current_list", d=updated.strftime("%Y-%m-%d %H:%M")) if updated else t("no_list_yet"))
        if self.locations:
            self.lbl_no_locations.pack_forget()
        else:
            self.lbl_no_locations.pack(fill="x", padx=16, pady=(6, 0), after=self.locations_hint_anchor)

    def update_locations(self):
        if getattr(self, "_updating_locations", False):
            return
        self._updating_locations = True
        buttons = [self.btn_update_list]
        if self._picker is not None and self._picker.winfo_exists():
            buttons.append(self._picker.btn_update)
        for b in buttons:
            b.configure(state="disabled", text=t("updating"))

        def work():
            try:
                LocationManager.download()
                self.post(self.locations_updated, None)
            except Exception as e:
                self.post(self.locations_updated, str(e) or e.__class__.__name__)

        threading.Thread(target=work, daemon=True).start()

    def locations_updated(self, error):
        self._updating_locations = False
        self.btn_update_list.configure(state="normal", text=t("update_list"))
        picker = self._picker if self._picker is not None and self._picker.winfo_exists() else None
        if picker:
            picker.btn_update.configure(state="normal", text=t("update_list"))
        if error:
            self.log_message(f"Server list update failed: {error}", "FAILURE")
            self.toast(t("update_failed", e=error), "error", ms=7000)
            return

        old_keys = self.all_keys
        self.locations = LocationManager.load_locations()
        self.all_keys = {loc_key(l) for l in self.locations}
        added, removed = len(self.all_keys - old_keys), len(old_keys - self.all_keys)
        had_selection = bool(self.selected_keys)
        self.selected_keys &= self.all_keys
        if picker:
            picker.set_locations(self.locations)
        self.refresh_locations_info()
        self.update_scope_preview(user_change=True)
        self.save_all_config()

        countries = len({l["country"] for l in self.locations})
        msg = t("list_updated", n=num(len(self.locations)), c=num(countries))
        changes = [x for x in (t("changes_new", n=added) if added else "",
                               t("changes_removed", n=removed) if removed else "") if x]
        sep = "، " if i18n.RTL else ", "
        msg += f" ({sep.join(changes)})." if changes and old_keys else "."
        if had_selection and not self.selected_keys:
            msg += t("selection_gone")
        self.log_message(f"Server list updated: {len(self.locations)} servers, {added} new, {removed} removed.",
                         "SUCCESS")
        self.toast(msg, "success", ms=6000)

    def on_locations_chosen(self, keys):
        keys &= self.all_keys
        self.selected_keys = set() if keys == self.all_keys else keys
        self.update_scope_preview(user_change=True)
        self.save_all_config()

    def test_count(self):
        return len(self.scope_locations()) * sum(len(p) for p in self.get_plan().values())

    def update_scope_preview(self, user_change=False):
        if not hasattr(self, "btn_start") or not hasattr(self, "lbl_scope_tests"):
            return
        title, sub = self.scope_summary()
        servers = len(self.scope_locations())
        routes = sum(len(p) for p in self.get_plan().values())
        tests = servers * routes
        self.lbl_scope_title.configure(text=trunc(title, 30))
        self.lbl_scope_sub.configure(text=sub)
        self.lbl_scope_math.configure(text=t("scope_math", s=num(servers), r=num(routes)))
        self.lbl_scope_tests.configure(text=t("tests_n", n=num(tests)))
        if self.worker_running():
            return
        if user_change:
            self.run = None
        self.btn_start.configure(text=t("start_n", n=num(tests)) if tests else t("start"))
        self.render_header()
        if self.live_card.winfo_ismapped() or not self.best_result():
            self.render_hero()

    # ---------------- protocols / priority ----------------
    def refresh_protocol_list(self):
        for w in self.protocol_container.winfo_children():
            w.destroy()
        self.port_buttons = {}
        last = len(self.priority_order) - 1
        for i, proto in enumerate(self.priority_order):
            row = ctk.CTkFrame(self.protocol_container, fg_color=ROW, corner_radius=9 if i in (0, last) else 0)
            row.pack(fill="x", padx=1, pady=(1 if i == 0 else 0, 1))
            ctk.CTkCheckBox(row, text=PROTO_NAMES[proto], variable=self.protocol_vars[proto], font=sans(12, True),
                            text_color=TEXT, checkbox_width=17, checkbox_height=17, border_width=2, corner_radius=4,
                            fg_color=ACCENT, hover_color=ACCENT_HOVER, border_color=DIM,
                            checkmark_color=ON_ACCENT, width=100).pack(side=start(), padx=pads(10, 4), pady=8)
            down = icon_button(row, "down", lambda p=proto: self.move(p, 1), size=24, icon_size=10,
                               fg_color="transparent", border_color=ROW, text_color=MUTED,
                               state="normal" if i < last else "disabled")
            down.pack(side=end(), padx=pads(0, 6))
            up = icon_button(row, "up", lambda p=proto: self.move(p, -1), size=24, icon_size=10,
                             fg_color="transparent", border_color=ROW, text_color=MUTED,
                             state="normal" if i > 0 else "disabled")
            up.pack(side=end())
            btn = ghost_button(row, "", lambda p=proto: self.open_port_dialog(p), width=60, height=24,
                               font=mono(10), fg_color="transparent", corner_radius=6)
            btn.pack(side=end(), padx=pads(0, 4))
            Tooltip(btn, t("ports_tip"))
            self.port_buttons[proto] = btn
            self.update_summary(proto)
        self.update_scope_preview()

    def move(self, proto, delta):
        idx = self.priority_order.index(proto)
        new = idx + delta
        if 0 <= new < len(self.priority_order):
            self.priority_order[idx], self.priority_order[new] = self.priority_order[new], self.priority_order[idx]
            self.refresh_protocol_list()

    def open_port_dialog(self, proto):
        dialog = ctk.CTkToplevel(self)
        dialog.title(vis(t("ports_title", p=PROTO_NAMES[proto])))
        place_dialog(dialog, self, 320, 480, top=120)
        dialog.resizable(False, True)

        def set_all(value):
            for v in self.port_vars[proto].values():
                v.set(value)

        label(dialog, t("ports_title", p=PROTO_NAMES[proto]), 16, bold=True).pack(fill="x", padx=18, pady=(16, 0))
        label(dialog, t("ports_hint"), 11, MUTED, wraplength=280).pack(fill="x", padx=18)
        top = frame(dialog)
        top.pack(fill="x", padx=18, pady=(10, 0))
        ghost_button(top, t("select_all"), lambda: set_all(True),
                     width=self.text_width(t("select_all"), sans(12)) + 28, height=28).pack(side=start())
        ghost_button(top, t("select_none"), lambda: set_all(False),
                     width=self.text_width(t("select_none"), sans(12)) + 28, height=28).pack(side=start(), padx=6)

        scroll = ctk.CTkScrollableFrame(dialog, fg_color=CARD, corner_radius=10, border_width=1, border_color=BORDER)
        scroll.pack(fill="both", expand=True, padx=18, pady=10)
        for port, var in self.port_vars[proto].items():
            ctk.CTkCheckBox(scroll, text=str(port), variable=var, font=mono(12), checkbox_width=18,
                            checkbox_height=18, fg_color=ACCENT, hover_color=ACCENT_HOVER, border_color=DIM,
                            checkmark_color=ON_ACCENT, border_width=2, corner_radius=4).pack(anchor=a_start(),
                                                                                            pady=5, padx=10)

        def done():
            self.update_summary(proto)
            self.update_scope_preview(user_change=True)
            dialog.grab_release()
            dialog.destroy()

        dialog.protocol("WM_DELETE_WINDOW", done)
        dialog.bind("<Escape>", lambda _e: done())
        dialog.bind("<Return>", lambda _e: done())
        primary_button(dialog, t("done"), done, height=36).pack(fill="x", padx=18, pady=(0, 16))

    def update_summary(self, proto):
        active = [p for p, v in self.port_vars[proto].items() if v.get()]
        total = len(self.port_vars[proto])
        if not active:
            txt = t("ports_none")
        elif len(active) == total and total > 2:
            txt = t("ports_all", n=total)
        elif len(active) <= 2:
            txt = ", ".join(str(p) for p in active)
        else:
            txt = t("ports_some", a=len(active), b=total)
        btn = self.port_buttons.get(proto)
        if btn is not None:
            btn.configure(text=txt, text_color=TEXT_2 if active else WARN)

    # ---------------- sidebar ----------------
    def toggle_sidebar(self):
        self.sidebar_open = not self.sidebar_open
        self.apply_sidebar_state()

    def apply_sidebar_state(self):
        if self.sidebar_open:
            self.rail.grid_remove()
            self.sidebar.grid()
        else:
            self.sidebar.grid_remove()
            self.rail.grid()

    def toggle_timing(self, force_open=None):
        self.timing_open = (not self.timing_open) if force_open is None else force_open
        if self.timing_open:
            self.timing_frame.pack(fill="x", after=self.btn_timing)
        else:
            self.timing_frame.pack_forget()
        self.update_timing_summary()

    def update_timing_summary(self):
        arrow = "▾" if self.timing_open else ("◂" if i18n.RTL else "▸")
        summary = t("timing_summary", host=self.entry_ping_host.get().strip() or "?",
                    count=self.entry_ping_count.get().strip(), timeout=self.entry_timeout.get().strip())
        self.btn_timing.configure(text=f"{arrow}   {summary}")

    # ---------------- CLI ----------------
    def refresh_cli_status(self):
        path = resolve_cli(self.entry_cli.get())
        if path:
            self.cli_pill.configure(fg_color=GOOD_SOFT, border_color=GOOD_LINE)
            self.cli_dot.configure(text_color=GOOD)
            self.cli_text.configure(text=t("cli_ready"), text_color=GOOD_TEXT)
            self.rail_dot.configure(text_color=GOOD)
            if hasattr(self, "worker") and not self.worker.running:
                self.worker.cli_cmd = path
        else:
            self.cli_pill.configure(fg_color=BAD_SOFT, border_color=BAD_LINE)
            self.cli_dot.configure(text_color=BAD)
            self.cli_text.configure(text=t("cli_missing"), text_color=BAD_TEXT)
            self.rail_dot.configure(text_color=BAD)
        return path

    def focus_cli_entry(self):
        if resolve_cli(self.entry_cli.get()):
            return
        if not self.sidebar_open:
            self.toggle_sidebar()
        self.toggle_timing(True)
        try:
            self.sidebar_scroll._parent_canvas.yview_moveto(1.0)
        except Exception:
            pass
        self.entry_cli.focus_set()
        self.entry_cli.configure(border_color=BAD)
        self.toast(t("set_cli_path"), "warn")

    def browse_cli(self):
        types = [("windscribe-cli", "windscribe-cli.exe"), (vis(t("all_files")), "*.*")] if IS_WINDOWS \
            else [(vis(t("all_files")), "*")]
        path = filedialog.askopenfilename(title=vis(t("locate_cli")), filetypes=types)
        if path:
            self.set_entry(self.entry_cli, os.path.normpath(path))
            self.entry_cli.configure(border_color=BORDER_2)
            if self.refresh_cli_status():
                self.toast(t("cli_found"), "success", ms=2200)

    # ---------------- config / profiles ----------------
    @staticmethod
    def set_entry(widget, value):
        widget.delete(0, "end")
        widget.insert(0, str(value))

    def set_profile_placeholder(self):
        self.combo_profiles.set(vis(t("choose_profile") if self.saved_profiles else t("no_profiles")))

    def apply_iran_preset(self):
        """Configures protocols, ports, HTTP verification, and 15s Anti-DPI stability hold for Iranian networks."""
        if self.worker_running():
            self.toast(t("wait_run"), "warn")
            return
        self.priority_order = list(IRAN_PRIORITY_ORDER)
        for proto, cfg in IRAN_PROTOCOL_CONFIG.items():
            if proto in self.protocol_vars:
                self.protocol_vars[proto].set(cfg["enabled"])
                active_ports = set(cfg["ports"])
                for p, p_var in self.port_vars[proto].items():
                    p_var.set(p in active_ports)
        self.set_entry(self.entry_timeout, "30")
        self.set_entry(self.entry_settle, "3")
        self.set_entry(self.entry_hold, "15")
        self.set_entry(self.entry_ping_count, "4")
        self.sw_anti_dpi_hold.select()
        self.sw_watchdog.select()
        self.sw_fast_skip.select()
        self.sw_smart_ai.select()
        self.sw_auto_pilot.select()
        self.sw_speed_burst.select()
        self.sw_http_check.select()
        self.sw_dedup_cities.select()
        self.refresh_protocol_list()
        self.update_timing_summary()
        self.update_scope_preview(user_change=True)
        self.save_all_config()
        self.log_message("Applied Iran Anti-DPI Preset (WStunnel -> Stealth -> TCP -> WireGuard, 15s stability hold, HTTP check).", "HEADER")
        self.toast(t("iran_preset_applied"), "success", ms=4500)

    def apply_config_to_ui(self, s):
        self.set_entry(self.entry_timeout, s.get("timeout", "25"))
        self.set_entry(self.entry_settle, s.get("settle", "2"))
        self.set_entry(self.entry_hold, s.get("hold_seconds", "15"))
        self.set_entry(self.entry_ping_host, s.get("ping_host", "1.1.1.1"))
        self.set_entry(self.entry_ping_count, s.get("ping_count", "5"))
        self.set_entry(self.entry_http_url, s.get("http_url", HttpChecker.DEFAULT_URL))
        self.update_timing_summary()

        for sw, key in ((self.sw_resume, "resume"),
                        (self.sw_anti_dpi_hold, "anti_dpi_hold"),
                        (self.sw_watchdog, "watchdog"),
                        (self.sw_fast_skip, "fast_skip"),
                        (self.sw_smart_ai, "smart_ai"),
                        (self.sw_auto_pilot, "auto_pilot"),
                        (self.sw_speed_burst, "speed_burst"),
                        (self.sw_free_only, "free_only"),
                        (self.sw_dedup_cities, "dedup_cities"),
                        (self.sw_keep_firewall, "keep_firewall"),
                        (self.sw_http_check, "http_check"),
                        (self.sw_random_cities, "random_cities"),
                        (self.sw_chaos, "chaos_mode"),
                        (self.sw_stop_success, "stop_on_success")):
            sw.select() if s.get(key, False) else sw.deselect()

        keys = set(s.get("selected") or [])
        if not keys:
            # Settings from older versions stored a Region / City / Node filter instead.
            region, city, node = (s.get("filter_continent", "All"), s.get("filter_city", "All"),
                                  s.get("filter_location", "All"))
            if (region, city, node) != ("All", "All", "All"):
                keys = {loc_key(l) for l in self.locations if matches_region(l, region)
                        and city in ("All", l["city"]) and node in ("All", l["location"])}
        keys &= self.all_keys
        self.selected_keys = set() if keys == self.all_keys else keys

        for proto, settings in s.get("protocols", {}).items():
            if proto in self.protocol_vars:
                self.protocol_vars[proto].set(settings.get("enabled", True))
                for port, enabled in settings.get("ports", {}).items():
                    try:
                        port_int = int(port)
                    except ValueError:
                        continue
                    if port_int in self.port_vars[proto]:
                        self.port_vars[proto][port_int].set(enabled)

        self.priority_order = self.sanitize_priority(s.get("priority_order"))
        self.refresh_protocol_list()

    def gather_config_data(self):
        data = {
            "timeout": self.entry_timeout.get().strip(),
            "settle": self.entry_settle.get().strip(),
            "hold_seconds": self.entry_hold.get().strip() or "15",
            "ping_host": self.entry_ping_host.get().strip(),
            "ping_count": self.entry_ping_count.get().strip(),
            "http_url": self.entry_http_url.get().strip() or HttpChecker.DEFAULT_URL,
            "resume": bool(self.sw_resume.get()),
            "anti_dpi_hold": bool(self.sw_anti_dpi_hold.get()),
            "watchdog": bool(self.sw_watchdog.get()),
            "fast_skip": bool(self.sw_fast_skip.get()),
            "smart_ai": bool(self.sw_smart_ai.get()),
            "auto_pilot": bool(self.sw_auto_pilot.get()),
            "speed_burst": bool(self.sw_speed_burst.get()),
            "free_only": bool(self.sw_free_only.get()),
            "dedup_cities": bool(self.sw_dedup_cities.get()),
            "keep_firewall": bool(self.sw_keep_firewall.get()),
            "http_check": bool(self.sw_http_check.get()),
            "selected": sorted(self.selected_keys),
            "random_cities": bool(self.sw_random_cities.get()),
            "chaos_mode": bool(self.sw_chaos.get()),
            "stop_on_success": bool(self.sw_stop_success.get()),
            "priority_order": list(self.priority_order),
            "protocols": {},
        }
        for proto, p_var in self.protocol_vars.items():
            data["protocols"][proto] = {
                "enabled": bool(p_var.get()),
                "ports": {str(p): bool(v.get()) for p, v in self.port_vars[proto].items()},
            }
        return data

    def save_all_config(self):
        self.config_data["last_settings"] = self.gather_config_data()
        self.config_data["cli_path"] = self.entry_cli.get().strip()
        self.config_data["sidebar_open"] = self.sidebar_open
        ConfigManager.save_config(self.config_data)

    def ask_profile_name(self):
        d = ctk.CTkToplevel(self)
        d.title(vis(t("save_profile")))
        place_dialog(d, self, 380, 210, top=140)
        d.resizable(False, False)
        label(d, t("save_profile"), 16, bold=True).pack(fill="x", padx=18, pady=(16, 0))
        label(d, t("save_profile_hint"), 11, MUTED, wraplength=340).pack(fill="x", padx=18)
        e = entry(d, height=38, size=13, placeholder_text=t("profile_name"))
        e.pack(fill="x", padx=18, pady=(12, 0))
        if self.current_profile_name != "Manual":
            e.insert(0, self.current_profile_name)

        def ok():
            name = e.get().strip()
            if not name:
                e.configure(border_color=BAD)
                return
            d.grab_release()
            d.destroy()
            self.save_profile(name)

        row = frame(d)
        row.pack(fill="x", padx=18, pady=14)
        primary_button(row, t("save"), ok, width=max(90, self.text_width(t("save"), sans(13, True)) + 32),
                       height=34).pack(side=end())
        ghost_button(row, t("cancel"), d.destroy, width=max(80, self.text_width(t("cancel"), sans(12)) + 28),
                     height=34).pack(side=end(), padx=pads(0, 8))
        e.bind("<Return>", lambda _e: ok())
        d.bind("<Escape>", lambda _e: d.destroy())
        d.after(200, e.focus_set)

    def save_profile(self, name):
        self.saved_profiles[name] = self.gather_config_data()
        self.config_data["saved_profiles"] = self.saved_profiles
        self.save_all_config()
        self.combo_profiles.configure(values=list(self.saved_profiles.keys()))
        self.combo_profiles.set(name)
        self.current_profile_name = name
        self.log_message(f"Saved profile: {name}", "INFO")
        self.toast(t("profile_saved", n=name), "success")

    def load_profile(self, choice=None):
        name = choice or self.combo_profiles.get()
        if name in self.saved_profiles:
            self.apply_config_to_ui(self.saved_profiles[name])
            self.current_profile_name = name
            self.log_message(f"Loaded profile: {name}", "INFO")
            self.toast(t("profile_loaded", n=name), "info", ms=2200)

    def delete_profile(self):
        name = self.combo_profiles.get()
        if name not in self.saved_profiles:
            self.toast(t("choose_to_delete"), "warn")
            return
        if not ask_yes_no(self, t("delete_profile"), t("delete_profile_q", n=name)):
            return
        del self.saved_profiles[name]
        self.config_data["saved_profiles"] = self.saved_profiles
        ConfigManager.save_config(self.config_data)
        self.combo_profiles.configure(values=list(self.saved_profiles.keys()))
        self.set_profile_placeholder()
        self.current_profile_name = "Manual"
        self.log_message(f"Deleted profile: {name}", "WARN")
        self.toast(t("profile_deleted", n=name), "info")

    # ---------------- job control ----------------
    def get_plan(self):
        plan = {}
        for proto in self.priority_order:
            if self.protocol_vars[proto].get():
                ports = [p for p, v in self.port_vars[proto].items() if v.get()]
                if ports:
                    plan[proto] = ports
        return plan

    def read_number(self, widget, name_key, minimum, maximum):
        try:
            value = int(widget.get().strip())
            if not minimum <= value <= maximum:
                raise ValueError
            return value
        except ValueError:
            self.flag_invalid(widget, t("must_be_number", name=t(name_key), a=minimum, b=maximum))
            return None

    def flag_invalid(self, widget, msg):
        if not self.sidebar_open:
            self.toggle_sidebar()
        self.toggle_timing(True)
        widget.configure(border_color=BAD)
        widget.focus_set()
        self.toast(msg, "error")

    def set_running_ui(self, running, stoppable=True):
        if running:
            self.btn_start.grid_remove()
            self.btn_stop.grid()
            self.btn_stop.configure(state="normal" if stoppable else "disabled", text=t("stop"))
        else:
            self.btn_stop.grid_remove()
            self.btn_start.grid()
            self.update_scope_preview()
        self.btn_disconnect.configure(state="disabled" if running else "normal")

    def start_job(self):
        if self.worker.running:
            return
        plan = self.get_plan()
        if not plan and bool(self.sw_auto_pilot.get()):
            plan = {p: list(DEFAULT_PROTOCOLS[p]) for p in self.priority_order if p in DEFAULT_PROTOCOLS}
        if not plan:
            self.toast(t("need_protocol"), "warn")
            return
        cli = self.refresh_cli_status()
        if not cli:
            self.focus_cli_entry()
            return
        timeout = self.read_number(self.entry_timeout, "name_timeout", 3, 300)
        if timeout is None:
            return
        settle = self.read_number(self.entry_settle, "name_settle", 0, 60)
        if settle is None:
            return
        anti_dpi_hold = bool(self.sw_anti_dpi_hold.get())
        hold_seconds = 15
        if anti_dpi_hold:
            hold_seconds = self.read_number(self.entry_hold, "name_hold", 5, 120)
            if hold_seconds is None:
                return
        ping_count = self.read_number(self.entry_ping_count, "name_pings", 1, 20)
        if ping_count is None:
            return
        host = self.entry_ping_host.get().strip()
        if not host or " " in host:
            self.flag_invalid(self.entry_ping_host, t("bad_host"))
            return
        http_check = bool(self.sw_http_check.get())
        http_url = self.entry_http_url.get().strip() or HttpChecker.DEFAULT_URL
        if http_check and not (http_url.startswith("http://") or http_url.startswith("https://")):
            self.flag_invalid(self.entry_http_url, t("bad_http_url"))
            return

        resume = bool(self.sw_resume.get())
        stored = self.worker.db.get_row_count()
        if not resume and stored and not ask_yes_no(self, t("start_fresh"), t("start_fresh_q", n=num(stored))):
            return

        self.save_all_config()
        if not resume:
            self.worker.db.clear_db()
        self.reload_results_table()

        profile_name = self.current_profile_name or "Manual"
        scope_title, _ = self.scope_summary()
        self.run = {"kind": "job", "scope": scope_title, "profile": profile_name,
                    "started": datetime.datetime.now(), "started_ts": time.time(), "stopped": False,
                    "current": 0, "total": self.test_count()}
        self.step = None
        self.set_connected(None)
        opts = {
            "keys": set(self.selected_keys), "resume": resume, "timeout": timeout, "settle": settle,
            "ping_count": ping_count, "ping_host": host,
            "anti_dpi_hold": anti_dpi_hold, "hold_seconds": hold_seconds,
            "fast_skip": bool(self.sw_fast_skip.get()),
            "smart_ai": bool(self.sw_smart_ai.get()),
            "auto_pilot": bool(self.sw_auto_pilot.get()),
            "priority_order": list(self.priority_order),
            "speed_burst": bool(self.sw_speed_burst.get()),
            "free_only": bool(self.sw_free_only.get()),
            "dedup_cities": bool(self.sw_dedup_cities.get()),
            "keep_firewall": bool(self.sw_keep_firewall.get()),
            "http_check": http_check, "http_url": http_url,
            "random_cities": bool(self.sw_random_cities.get()), "chaos_mode": bool(self.sw_chaos.get()),
            "stop_on_success": bool(self.sw_stop_success.get()), "profile_name": profile_name,
        }
        self.worker.cli_cmd = cli
        self.worker.keep_firewall = bool(self.sw_keep_firewall.get())
        self.worker.start(plan, opts)
        self.set_running_ui(True)
        self.show_hero("live")
        self.lbl_caption.configure(text=t("cap_starting").upper(), text_color=ACCENT)
        self.lbl_prog_left.configure(text=t("preparing"))
        self.lbl_prog_right.configure(text="")
        self.progress_bar.show(0)
        self.render_header()
        self.render_insights()
        self.set_view("Results")

    def reverify_best_routes(self):
        """Re-tests only the routes that previously succeeded (Best routes) without erasing the database."""
        if self.worker.running:
            self.toast(t("wait_run"), "warn")
            return
        working = self.best_routes()
        if not working:
            self.toast(t("no_best_to_reverify"), "warn")
            return
        cli = self.refresh_cli_status()
        if not cli:
            self.focus_cli_entry()
            return
        timeout = self.read_number(self.entry_timeout, "name_timeout", 3, 300)
        if timeout is None:
            return
        settle = self.read_number(self.entry_settle, "name_settle", 0, 60)
        if settle is None:
            return
        anti_dpi_hold = bool(self.sw_anti_dpi_hold.get())
        hold_seconds = 15
        if anti_dpi_hold:
            hold_seconds = self.read_number(self.entry_hold, "name_hold", 5, 120)
            if hold_seconds is None:
                return
        ping_count = self.read_number(self.entry_ping_count, "name_pings", 1, 20)
        if ping_count is None:
            return
        host = self.entry_ping_host.get().strip() or "1.1.1.1"
        http_check = bool(self.sw_http_check.get())
        http_url = self.entry_http_url.get().strip() or HttpChecker.DEFAULT_URL

        explicit_tasks = []
        for r in working:
            loc_dict = {"city": r["city"], "location": r["node"], "country": r["country"],
                        "continent": "", "is_premium": False}
            explicit_tasks.append((loc_dict, r["proto"], r["port"]))

        profile_name = self.current_profile_name or "Manual"
        scope_title = t("reverify_scope", n=num(len(explicit_tasks)))
        self.run = {"kind": "job", "scope": scope_title, "profile": profile_name,
                    "started": datetime.datetime.now(), "started_ts": time.time(), "stopped": False,
                    "current": 0, "total": len(explicit_tasks)}
        self.step = None
        self.set_connected(None)
        opts = {
            "keys": set(), "explicit_tasks": explicit_tasks,
            "resume": False, "timeout": timeout, "settle": settle,
            "ping_count": ping_count, "ping_host": host,
            "anti_dpi_hold": anti_dpi_hold, "hold_seconds": hold_seconds,
            "fast_skip": False, "speed_burst": bool(self.sw_speed_burst.get()),
            "free_only": False, "dedup_cities": False,
            "keep_firewall": bool(self.sw_keep_firewall.get()),
            "http_check": http_check, "http_url": http_url,
            "random_cities": False, "chaos_mode": False,
            "stop_on_success": bool(self.sw_stop_success.get()), "profile_name": profile_name,
        }
        self.worker.cli_cmd = cli
        self.worker.keep_firewall = bool(self.sw_keep_firewall.get())
        self.worker.start({}, opts)
        self.set_running_ui(True)
        self.show_hero("live")
        self.lbl_caption.configure(text=t("cap_starting").upper(), text_color=ACCENT)
        self.lbl_prog_left.configure(text=t("preparing"))
        self.lbl_prog_right.configure(text="")
        self.progress_bar.show(0)
        self.render_header()

    def stop_job(self):
        if not self.worker.running:
            return
        self.worker.stop()
        self.btn_stop.configure(state="disabled", text=t("stopping"))
        self.lbl_caption.configure(text=t("cap_stopping").upper(), text_color=WARN)

    def job_finished(self, kept_connection, ok, fail, kept_route=None):
        stopped = self.worker.stop_event.is_set()
        if self.run:
            self.run.update(finished=datetime.datetime.now(), stopped=stopped, kept=kept_connection)
        self.title(APP_NAME)
        self.set_running_ui(False)
        self.render_header()
        self.render_data()
        if kept_connection:
            self.connected_route = kept_route or self.best_result()
            self._last_watchdog_ts = time.time()
            self.set_connected(kept_connection)
            self.log_message("Job finished (connection kept).", "HEADER")
            self.toast(t("connected_to", x=kept_connection), "success")
        else:
            self.log_message("Job finished.", "HEADER")
            if not stopped and self.results:
                self.toast(t("finished_toast", ok=num(ok), fail=num(fail)), "success",
                           action=lambda: self.set_view("Best routes"), action_text=t("tab_best"), ms=7000)
        self.bell()

    def connect_selected(self, tree):
        self.connect_result(self.selected_result(tree))

    def connect_result(self, r):
        if not r:
            return
        if self.worker.running:
            self.toast(t("wait_run"), "warn")
            return
        cli = self.refresh_cli_status()
        if not cli:
            self.focus_cli_entry()
            return
        try:
            timeout = max(3, min(300, int(self.entry_timeout.get().strip())))
        except ValueError:
            timeout = 25
        self.worker.cli_cmd = cli
        self.worker.keep_firewall = bool(self.sw_keep_firewall.get())
        self.set_connected(None)
        self.worker.connect_to(r, timeout)
        self.set_running_ui(True)
        self.show_hero("live")
        self.set_target("cap_connecting", r["city"], r["node"], r["country"], f"{r['proto']}:{r['port']}")
        self.progress_bar.show(0)
        self.lbl_prog_left.configure(text=t("manual_connection"))
        self.lbl_prog_right.configure(text="")

    def manual_connect_finished(self, r, connected, dropped_by_dpi=False):
        self.set_running_ui(False)
        route = f"{r['proto']}:{r['port']}"
        where = loc_name(r["city"], r["node"])
        if connected:
            self.connected_route = r
            self._last_watchdog_ts = time.time()
            ip_tag = f" ({r['vpn_ip']})" if r.get("vpn_ip") else ""
            self.set_connected(f"{where} · {route}{ip_tag}")
            self.render_data()
            self.toast(t("connected_via", w=where, r=route), "success")
        elif dropped_by_dpi:
            r["status"] = "DPI_RESET"
            self.worker.db.record_result(
                r.get("node", ""), r["city"], r["country"], r["proto"], r["port"],
                "DPI_RESET", r.get("duration", 0), r.get("ping"), r.get("loss"),
                self.current_profile_name or "Manual", r.get("http_ms")
            )
            self.render_data()
            self.toast(t("manual_dropped", w=where, r=route), "error", ms=6500)
        else:
            self.toast(t("could_not_connect", w=where, r=route), "error")
        self.render_hero()

    def disconnect_vpn(self):
        if self.worker.running:
            return
        cli = self.refresh_cli_status()
        if not cli:
            self.focus_cli_entry()
            return
        self.worker.cli_cmd = cli
        self.worker.keep_firewall = bool(self.sw_keep_firewall.get())
        self.worker.disconnect()
        self.set_running_ui(True, stoppable=False)
        self.btn_stop.configure(text=t("disconnecting"))

    def disconnect_finished(self, done):
        self.set_running_ui(False)
        if done:
            self.connected_route = None
            self.set_connected(None)
        self.toast(t("disconnected") if done else t("could_not_disconnect"), "info" if done else "error", ms=2200)

    def export_csv(self):
        count, path = self.worker.db.export_to_csv(self.current_profile_name)
        if count == -1:
            self.toast(t("csv_failed", e=path), "error", ms=6000)
        else:
            self.toast(t("exported", n=num(count), f=os.path.basename(path)), "success",
                       action=lambda: open_path(REPORTS_DIR), action_text=t("open_folder"), ms=7000)

    # ---------------- window ----------------
    def bind_shortcuts(self):
        self.bind("<Control-Return>", lambda _e: self.start_job())
        self.bind("<F5>", lambda _e: self.start_job())
        self.bind("<Escape>", lambda _e: self.stop_job())
        self.bind("<Control-e>", lambda _e: self.export_csv())
        self.bind("<Control-s>", lambda _e: self.ask_profile_name())
        self.bind("<Control-l>", lambda _e: self.open_location_picker())
        self.bind("<Control-b>", lambda _e: self.toggle_sidebar())
        self.bind("<Control-f>", lambda _e: (self.set_view("Results"), self.entry_search.focus_set()))
        self.bind("<Control-r>", lambda _e: self.reverify_best_routes())

    def restore_window(self):
        geo = self.config_data.get("window") or ""
        if re.fullmatch(r"\d+x\d+[+-]-?\d+[+-]-?\d+", geo):
            try:
                self.geometry(geo)
            except tk.TclError:
                pass

    def on_close(self):
        if self.worker.running:
            if not ask_yes_no(self, t("quit"), t("quit_q")):
                return
            self.worker.stop_event.set()
            try:
                if not self.worker.keep_firewall:
                    self.worker.run_cli(["firewall", "off"], timeout=4)
                self.worker.run_cli(["disconnect"], timeout=5)
            except Exception:
                pass
        try:
            if self.state() == "normal":
                self.config_data["window"] = self.geometry()
            self.save_all_config()
        except Exception as e:
            print(f"Close Error: {e}")
        try:
            self.worker.db.conn.close()
        except Exception:
            pass
        self.destroy()


def restart():
    """Starts a fresh copy of the app (used after changing the language)."""
    env = os.environ.copy()
    if getattr(sys, "frozen", False):
        cmd = [sys.executable] + sys.argv[1:]
        # A one-file build unpacks itself to a temporary folder that is deleted when this process exits.
        # Without this the new process would reuse that folder (and its Tcl/Tk paths) and fail to start.
        env["PYINSTALLER_RESET_ENVIRONMENT"] = "1"
        for var in ("TCL_LIBRARY", "TK_LIBRARY", "_MEIPASS2", "_PYI_APPLICATION_HOME_DIR", "_PYI_ARCHIVE_FILE",
                    "_PYI_PARENT_PROCESS_LEVEL"):
            env.pop(var, None)
    else:
        target = os.path.abspath(sys.argv[0])
        if not os.path.exists(target) and os.path.isfile(os.path.dirname(os.path.abspath(__file__))):
            target = os.path.dirname(os.path.abspath(__file__))
        cmd = [sys.executable, target] + sys.argv[1:]
    subprocess.Popen(cmd, cwd=APP_PATH, env=env)


def main():
    app = App()
    app.mainloop()
    if app.relaunch:
        # The new language changes the whole layout direction, so the window is rebuilt from scratch.
        restart()


if __name__ == "__main__":
    main()
