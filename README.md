<div align="center">

# AutoScribe v1.7.2

**Find the Windscribe servers and protocols that actually work on your network.**

**This branch is a fork of rasool-mrr/AutoScribe**

**English** · [فارسی](README.fa.md) · [Русский](README.ru.md)

</div>

---

AutoScribe is a desktop app that drives the official **Windscribe CLI** for you. It works through every
server, protocol and port you pick, connects to each one, measures ping, packet loss, and optional HTTP/HTTPS web
connectivity through the tunnel, and ranks the combinations that work best. It also includes a built-in
**AI Adaptive Engine & Auto-Pilot** (`ai_engine.py`) and **Windscribe Log Diagnostics** analyzer (`config/log.bin`, `config.ovpn`, `wireguard_service.log`) to diagnose WireGuard/AmneziaWG handshake timeouts and DPI blocks.

## What's New in v1.7.2

- **AI Adaptive Learning (DPI Feedback)** – Lightweight zero-dependency engine (`ai_engine.py`) using a time-decayed Thompson Sampling Bandit scheduler, `NetworkProfiler` (local IP, gateway, ARP MAC, Wi-Fi SSID/BSSID), `SocketProber` pre-flight RST/Drop detection, and `FailureClassifier` to learn what works on your current network.
- **AI Auto-Pilot** – Automatically selects and escalates anti-censorship strategy profiles (Direct, TLS Obfuscation, L1 Cold-Start to L4) and port priorities.
- **Anti-DPI Stability Hold & Speed Burst** – Keeps the tunnel open and probes in multiple waves to catch delayed DPI resets, plus a 150 KB payload mini speed & throttle test.
- **Auto-Failover Watchdog** – Continuously monitors your active VPN connection every 25s; rotates VPN IP or switches to a working fallback route if the tunnel drops or freezes.
- **AI Diagnostic Snapshot** – Generate and copy a structured diagnostic snapshot to paste into ChatGPT/Gemini/Claude, and apply AI-suggested configurations directly.

## Core Features

- **Automatic testing** – server × protocol × port, with WireGuard, IKEv2, UDP, TCP, Stealth and WStunnel.
- **Node-level targeting & One server per city** – Connect to specific server nicknames and optionally deduplicate multi-node cities.
- **Free servers only filter** – Skip Pro-only locations and mark `[FREE]` nodes in the location picker.
- **Keep Windscribe firewall option** – Preserve Windscribe's firewall/Kill Switch between tests.
- **Ping, packet loss & HTTP web check** through the tunnel (`http://cp.cloudflare.com/generate_204` by default).
- **Best routes** – Live leaderboard of the fastest working routes. Double-click a route to connect to it.
- **Searchable location picker & Up-to-date server list** – Filter by region, spot `[FREE]` servers, or refresh from windscribe.com.
- **Resume & Stop on first success** – Skip already-tested combinations or stop as soon as one route works.
- **Profiles & Built-in Diagnostics tab** – Save/load settings (including the included `Iran Anti-DPI` profile) and inspect `config/log.bin` & `config.ovpn`.
- **CSV export** of all results to the `reports/` folder.
- **Three languages** – English, Farsi (fully right-to-left) and Russian.

## Requirements

- **Windows 10/11** (Linux and macOS work too if `windscribe-cli` is on your `PATH`)
- **Python 3.9+** with Tkinter and `customtkinter`
- **Windscribe desktop app**, signed in (`C:\Program Files\Windscribe\windscribe-cli.exe`).

## Installation & Running

```bash
pip install -r requirements.txt
python main.py
```

On Windows, you can also double-click `run_autoscribe.bat`.

## Building a standalone .exe

Run `build_standalone_exe.bat` on Windows, or build manually:

```bash
pip install pyinstaller
pyinstaller --noconfirm --clean --onefile --noconsole --name AutoScribe --collect-data customtkinter main.py
```

Put `locations.json` and `config.json` in the same folder as `dist\AutoScribe.exe`.

## License

Released under the **MIT License with a removal-on-request condition**. See [LICENSE](LICENSE).
