#!/usr/bin/env python3
# tool by : Golu Molu
# team : Fk Unknwon Team

import socket
import subprocess
import ipaddress
import concurrent.futures
import time
import json
import platform
import os
import re
import sys
import http.server
import urllib.request
import urllib.error
import webbrowser
import threading
from pathlib import Path


try:
    from colorama import Fore, Style, init as _colorama_init
    _colorama_init(autoreset=True)
except ImportError:
    class _Fore:
        RED = GREEN = YELLOW = CYAN = MAGENTA = WHITE = BLUE = ""
    class _Style:
        RESET_ALL = BRIGHT = DIM = ""
    Fore  = _Fore()
    Style = _Style()

try:
    import netifaces as _netifaces
    HAS_NETIFACES = True
except ImportError:
    HAS_NETIFACES = False


try:
    import speedtest as _speedtest_module
    HAS_SPEEDTEST = True
except ImportError:
    HAS_SPEEDTEST = False

try:
    import requests as _requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False


_CYAN    = "\033[96m"
_GREEN   = "\033[92m"
_YELLOW  = "\033[93m"
_RED     = "\033[91m"
_MAGENTA = "\033[95m"
_BOLD    = "\033[1m"
_DIM     = "\033[2m"
_RESET   = "\033[0m"

if os.name == "nt":
    try:
        import ctypes
        ctypes.windll.kernel32.SetConsoleMode(
            ctypes.windll.kernel32.GetStdHandle(-11), 7)
    except Exception:
        _CYAN = _GREEN = _YELLOW = _RED = _MAGENTA = _BOLD = _DIM = _RESET = ""


BASE_DIR           = Path(__file__).resolve().parent
HTML_TEMPLATE_PATH = BASE_DIR / "index.html"
RESULTS_JSON_PATH  = BASE_DIR / "net_results.json"

RESULTS_LOCK = threading.Lock()
RESULTS: dict = {
    "status":     "starting",
    "updated_at": time.time(),
    "connection": {},
    "wifi":       {},
    "health":     {},
    "speed":      {},
}

# ── Speed-test config ─────────────────────────────────────────────────────────
DOWNLOAD_SIZE = 25_000_000   # bytes per stream (for {size} template URLs)
UPLOAD_SIZE   = 10_000_000   # bytes per stream
NUM_STREAMS   = 4
WARMUP_SIZE   = 1_000_000    # bytes, Cloudflare warm-up only
CHUNK         = 131_072      # 128 KB read chunks


DOWNLOAD_SOURCES = [
    ("TEL2",         "http://speedtest.tele2.net/10MB.zip",               False),
    ("FSN1 ",    "https://fsn1-speed.hetzner.com/100MB.bin",  True),
    ("Github",      "https://github.com/szalony9szymek/large/releases/download/free/large",        False),
    ("Realme",      "https://download.c.realme.com/flash/Rollbackpack/realme_Narzo_50/oplus_ota_downgrade.zip",            False),
    ("SIN",         "https://sin-speed.hetzner.com/100MB.bin",                  False),
    ("OVH FR",            "http://proof.ovh.net/files/10Mb.dat",               False),
]

# Upload endpoints — tried in order on failure / rate-limit
UPLOAD_ENDPOINTS = [
    ("Cloudflare", "https://speed.cloudflare.com/__up"),
    ("httpbin",    "https://httpbin.org/post"),
]

# Ping targets — tried in order, uses first that responds >= 3 samples
PING_TARGETS = [
    ("Cloudflare",     "https://speed.cloudflare.com/__down?bytes=0"),
    ("Google",         "https://www.google.com"),
    ("Cloudflare DNS", "https://1.1.1.1"),
]

# =============================================================================
# Utilities
# =============================================================================

def _clear_screen():
    try:
        os.system("cls" if platform.system().lower() == "windows" else "clear")
    except Exception:
        pass


def _deep_merge(dst: dict, src: dict):
    for k, v in (src or {}).items():
        if isinstance(v, dict) and isinstance(dst.get(k), dict):
            _deep_merge(dst[k], v)
        else:
            dst[k] = v


def update_results(partial: dict):
    with RESULTS_LOCK:
        _deep_merge(RESULTS, partial)
        RESULTS["updated_at"] = time.time()
        try:
            RESULTS_JSON_PATH.write_text(json.dumps(RESULTS, indent=2), encoding="utf-8")
        except Exception:
            pass


def get_results_snapshot() -> dict:
    with RESULTS_LOCK:
        return json.loads(json.dumps(RESULTS))

# =============================================================================
# Logo / Banner
# =============================================================================

def print_logo():
    cyan   = "\033[36m"
    blue   = "\033[34m"
    green  = "\033[32m"
    yellow = "\033[33m"
    reset  = "\033[0m"
    bold   = "\033[1m"

    rows = [
        f"{cyan}     /\\      {blue}_   _  _____ _______  {green}_______",
        f"{cyan}    /  \\    {blue}| \\ | ||  __ \\_   _|  {green}__   __|",
        f"{cyan}   / /\\ \\   {blue}|  \\| || |  | || |      {green}| |   ",
        f"{cyan}  / ____ \\  {blue}| . ` || |  | || |      {green}| |   ",
        f"{cyan} /_/    \\_\\ {blue}|_|\\_||_|  |_||_|      {green}|_|   ",
    ]
    W = 50
    print(f"\n{cyan}╔{'═'*(W+2)}╗{reset}")
    for row in rows:
        plain = re.sub(r"\033\[[0-9;]*m", "", row)
        pad   = W - len(plain)
        print(f"{cyan}║ {row}{' '*max(pad,0)}{cyan} ║{reset}")
    footer = "=== Advanced Network Analysis Tool ==="
    fp = (W - len(footer)) // 2
    print(f"{cyan}╠{'═'*(W+2)}╣{reset}")
    print(f"{cyan}║{' '*fp}{bold}{yellow}{footer}{' '*(W-fp-len(footer))}{cyan} ║{reset}")
    print(f"{cyan}╚{'═'*(W+2)}╝{reset}\n")

# =============================================================================
# Network info
# =============================================================================

def get_network_info():
    """Return (local_ip, netmask). Uses netifaces if available, else socket fallback."""
    if HAS_NETIFACES:
        for iface in _netifaces.interfaces():
            addrs = _netifaces.ifaddresses(iface)
            if _netifaces.AF_INET in addrs:
                info = addrs[_netifaces.AF_INET][0]
                ip   = info.get("addr", "")
                nm   = info.get("netmask", "")
                if ip and not ip.startswith("127."):
                    return ip, nm
    # Fallback via socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip, "255.255.255.0"
    except Exception:
        return None, None


def get_network_range(ip: str, netmask: str) -> str:
    return str(ipaddress.IPv4Network(f"{ip}/{netmask}", strict=False))

# =============================================================================
# Wi-Fi info
# =============================================================================

def simple_distance_estimate(rssi: int) -> str:
    if rssi >= -50: return "1–2 meters (Very close)"
    if rssi >= -60: return "2–4 meters"
    if rssi >= -70: return "4–8 meters"
    if rssi >= -80: return "8–15 meters"
    return "15+ meters (Weak or far)"


def get_wifi_info() -> dict | None:
    # Termux (Android)
    try:
        r = subprocess.run(
            ["termux-wifi-connectioninfo"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        )
        if r.returncode == 0 and r.stdout.strip():
            return json.loads(r.stdout)
    except Exception:
        pass

    # Windows via netsh
    if platform.system().lower() == "windows":
        try:
            out  = subprocess.check_output(
                ["netsh", "wlan", "show", "interfaces"],
                stderr=subprocess.STDOUT, universal_newlines=True,
            )
            ssid = bssid = signal_pct = None
            for line in out.splitlines():
                if ":" not in line:
                    continue
                k, _, v = line.partition(":")
                k, v    = k.strip().lower(), v.strip()
                if   k == "ssid"   and not ssid:       ssid       = v
                elif k == "bssid"  and not bssid:      bssid      = v
                elif k == "signal" and signal_pct is None:
                    m = re.search(r"(\d+)\s*%", v)
                    if m:
                        signal_pct = int(m.group(1))
            rssi = int(round((signal_pct / 2) - 100)) if signal_pct is not None else None
            return {"ssid": ssid or "Unknown", "bssid": bssid or "Unknown",
                    "rssi": rssi, "signal_percent": signal_pct}
        except Exception:
            return None

    # Linux nmcli fallback
    try:
        out = subprocess.check_output(
            ["nmcli", "-t", "-f", "active,ssid,bssid,signal", "dev", "wifi"],
            stderr=subprocess.DEVNULL, universal_newlines=True,
        )
        for line in out.splitlines():
            if line.startswith("yes:"):
                parts = line.split(":")
                if len(parts) >= 4:
                    ssid  = parts[1]
                    bssid = parts[2]
                    sig   = int(parts[3]) if parts[3].isdigit() else None
                    rssi  = int(round((sig / 2) - 100)) if sig is not None else None
                    return {"ssid": ssid, "bssid": bssid, "rssi": rssi, "signal_percent": sig}
    except Exception:
        pass

    return None

# =============================================================================
# Hostname lookup
# =============================================================================

def get_hostname(ip: str) -> str | None:
    
        hostname = socket.gethostbyaddr(ip)[0]
        return hostname if hostname != ip else None
    except Exception:
        return None

# =============================================================================
# Network scan
# =============================================================================

def ping_host(ip: str):
    """Ping a single host; return (ip, hostname, status)."""
    try:
        if platform.system().lower() == "windows":
            subprocess.check_output(
                ["ping", "-n", "1", "-w", "1000", ip], stderr=subprocess.DEVNULL)
        else:
            subprocess.check_output(
                ["ping", "-c", "1", "-W", "1", ip], stderr=subprocess.DEVNULL)
        hostname = get_hostname(ip) or "Unknown"
        return ip, hostname, "Active"
    except subprocess.CalledProcessError:
        return ip, "Unknown", "Inactive"


def scan_network(network_range: str, router_ip: str) -> list:
    network   = ipaddress.IPv4Network(network_range)
    connected = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=100) as ex:
        futures = {ex.submit(ping_host, str(ip)): ip
                   for ip in network.hosts() if str(ip) != router_ip}
        for fut in concurrent.futures.as_completed(futures):
            ip, hostname, status = fut.result()
            if status == "Active":
                connected.append((ip, hostname))
    return connected

# =============================================================================
# Ping helpers
# =============================================================================

def ping_detailed(host: str, count: int = 5, timeout_ms: int = 1000) -> dict | None:
    """Cross-platform ping returning min/avg/max/jitter/loss stats."""
    try:
        if platform.system().lower() == "windows":
            output = subprocess.check_output(
                ["ping", "-n", str(count), "-w", str(timeout_ms), host],
                stderr=subprocess.STDOUT, universal_newlines=True,
            )
            loss_pct = None
            m = re.search(r"Lost\s*=\s*\d+.*\((\d+)\s*% loss\)", output, re.IGNORECASE)
            if m:
                loss_pct = float(m.group(1))
            min_ms = avg_ms = max_ms = jitter_ms = None
            m2 = re.search(
                r"Minimum\s*=\s*(\d+)\s*ms.*Maximum\s*=\s*(\d+)\s*ms.*Average\s*=\s*(\d+)\s*ms",
                output, re.IGNORECASE,
            )
            if m2:
                min_ms    = float(m2.group(1))
                max_ms    = float(m2.group(2))
                avg_ms    = float(m2.group(3))
                jitter_ms = max_ms - min_ms
            return {"host": host, "min_ms": min_ms, "avg_ms": avg_ms, "max_ms": max_ms,
                    "jitter_ms": jitter_ms, "loss_pct": loss_pct, "duplicates": 0}
        else:
            # BUGFIX-09: int(timeout_ms/1000) → 0 when timeout_ms < 1000.
            # Clamp to minimum 1 second so ping doesn't crash.
            timeout_sec = max(1, int(timeout_ms / 1000))
            output = subprocess.check_output(
                ["ping", "-c", str(count), "-W", str(timeout_sec), host],
                stderr=subprocess.STDOUT, universal_newlines=True,
            )
            loss_pct = None
            m = re.search(r"(\d+\.?\d*)%\s*packet loss", output, re.IGNORECASE)
            if m:
                loss_pct = float(m.group(1))
            min_ms = avg_ms = max_ms = jitter_ms = None
            m2 = re.search(r"rtt [^=]*=\s*([\d.]+)/([\d.]+)/([\d.]+)/([\d.]+)", output)
            if m2:
                min_ms, avg_ms, max_ms, jitter_ms = (float(m2.group(i)) for i in range(1, 5))
            dup = 0
            md = re.search(r"(\d+)\s+duplicates", output, re.IGNORECASE)
            if md:
                dup = int(md.group(1))
            return {"host": host, "min_ms": min_ms, "avg_ms": avg_ms, "max_ms": max_ms,
                    "jitter_ms": jitter_ms, "loss_pct": loss_pct, "duplicates": dup}
    except subprocess.CalledProcessError:
        return None
    except Exception:
        return None


def ping_test(host: str) -> float | None:
    stats = ping_detailed(host, count=5)
    return stats.get("avg_ms") if stats else None

# =============================================================================
# Router ping
# BUGFIX-10: There were TWO ping_router() definitions. The first (lines 103-134)
# used a hardcoded IP "192.168.55.1" and raw subprocess regex — removed.
# The second (correct, dynamic) version is kept below.
# =============================================================================

def ping_router():
    local_ip, netmask = get_network_info()
    if not local_ip or not netmask:
        print(f"{Fore.RED}Could not detect network information.{Style.RESET_ALL}")
        return
    network_range = get_network_range(local_ip, netmask)
    router_ip     = network_range.split("/")[0][:-1] + "1"
    print(f"Pinging router at {router_ip}...\n")
    try:
        avg_ping = ping_test(router_ip)
        if avg_ping is None:
            print(f"{Fore.RED}Ping failed or could not be parsed.{Style.RESET_ALL}")
            return
        if   avg_ping < 5:  status = f"{Fore.GREEN}Excellent{Style.RESET_ALL}"
        elif avg_ping < 15: status = f"{Fore.CYAN}Good{Style.RESET_ALL}"
        elif avg_ping < 30: status = f"{Fore.YELLOW}Average{Style.RESET_ALL}"
        else:               status = f"{Fore.RED}Poor or Unstable{Style.RESET_ALL}"
        print(f"{Fore.YELLOW}\n=== Health status ==={Style.RESET_ALL}")
        print(f"Average Ping Time : {avg_ping:.2f} ms")
        print(f"Connection Status : {status}")
    except Exception as e:
        print(f"Error during ping: {e}")

# =============================================================================
# ISP local hub discovery
# =============================================================================

def ping_isp_local(dest: str = "8.8.8.8") -> str | None:
    def is_private(ip):
        try:
            return ipaddress.IPv4Address(ip).is_private
        except Exception:
            return False

    try:
        if platform.system().lower() == "windows":
            tr = subprocess.check_output(
                ["tracert", "-d", dest],
                stderr=subprocess.STDOUT, universal_newlines=True,
            )
        else:
            tr = subprocess.check_output(
                ["traceroute", "-n", dest],
                stderr=subprocess.STDOUT, universal_newlines=True,
            )
    except Exception as e:
        print(f"{Fore.RED}Traceroute failed: {e}{Style.RESET_ALL}")
        return None

    ips       = re.findall(r"\d+\.\d+\.\d+\.\d+", tr)
    router_ip = isp_ip = None
    for ip in ips:
        if is_private(ip):
            if   router_ip is None: router_ip = ip
            elif isp_ip    is None: isp_ip    = ip; break

    print(f"Your Router IP : {router_ip}")
    print(f"ISP Local IP   : {isp_ip}")

    if isp_ip:
        print("\nPinging ISP local...\n")
        ping_detailed(isp_ip, count=5)
        return isp_ip
    else:
        print("ISP IP not found!")
        return None

# =============================================================================
# Speed-test spinner helpers
# =============================================================================

_stop_spin = threading.Event()

def _spin_worker(msg: str):
    frames = ["⠋","⠙","⠹","⠸","⠼","⠴","⠦","⠧","⠇","⠏"]
    i = 0
    while not _stop_spin.is_set():
        sys.stdout.write(f"\r  {_CYAN}{frames[i % len(frames)]}{_RESET}  {msg}   ")
        sys.stdout.flush()
        time.sleep(0.08)
        i += 1
    sys.stdout.write("\r" + " " * 70 + "\r")
    sys.stdout.flush()

def _spin_start(msg: str) -> threading.Thread:
    _stop_spin.clear()
    t = threading.Thread(target=_spin_worker, args=(msg,), daemon=True)
    t.start()
    return t

def _spin_stop(t: threading.Thread):
    _stop_spin.set()
    t.join()

# =============================================================================
# Speed test bar / rating helpers
# =============================================================================

def _bar(value: float, max_val: float, width: int = 26, high_good: bool = True) -> str:
    ratio  = min(value, max_val) / max_val if max_val else 0
    filled = int(ratio * width)
    b      = "█" * filled + "░" * (width - filled)
    if high_good:
        color = _GREEN if ratio >= 0.5 else _YELLOW if ratio >= 0.1 else _RED
    else:
        color = _GREEN if ratio <= 0.15 else _YELLOW if ratio <= 0.45 else _RED
    return f"{color}{b}{_RESET}"

def _rating(dl: float, ul: float, ping: float) -> str:
    score  = (3 if dl   >= 100 else 2 if dl   >= 25 else 1)
    score += (3 if ul   >= 50  else 2 if ul   >= 10 else 1)
    score += (3 if ping <= 20  else 2 if ping <= 60 else 1)
    if score >= 8: return f"{_GREEN}{_BOLD}★★★  Excellent{_RESET}"
    if score >= 5: return f"{_YELLOW}{_BOLD}★★☆  Good{_RESET}"
    return          f"{_RED}{_BOLD}★☆☆  Poor{_RESET}"

def _cf_req(url: str, data=None, method: str = "GET", timeout: int = 30):
    headers = {
        "User-Agent":      "Mozilla/5.0 (CK-SpeedTest/3.3)",
        "Cache-Control":   "no-cache, no-store",
        "Pragma":          "no-cache",
        "Connection":      "keep-alive",
        "Accept-Encoding": "identity",   # disable compression — we measure raw bytes
    }
    if data is not None:
        headers["Content-Type"]   = "application/octet-stream"
        headers["Content-Length"] = str(len(data))
    r = urllib.request.Request(url, data=data, headers=headers, method=method)
    return urllib.request.urlopen(r, timeout=timeout)

def _is_rate_limited(err_str: str) -> bool:
    return "429" in err_str or "Too Many" in err_str or "403" in err_str

# =============================================================================
# Speed test — multi-stream Cloudflare
# BUGFIX-11: Original speed_test() returned nothing (no return statement).
# main() referenced download_MBps / upload_MBps causing NameError crash.
# Fixed: speed_test() now returns (download_mbps, upload_mbps, ping_ms).
# =============================================================================

def _download_stream(url: str, results: list, idx: int, errors: dict):
    """
    Download url fully and measure sustained throughput.
    Requires ≥0.5 s elapsed and ≥1 KB received to count as a real measurement
    (guards against instant cache hits or HTTP redirects that return near-zero bytes).
    Stores bytes/sec in results[idx]; error string in errors[idx] on failure.
    """
    total = 0
    try:
        t0 = time.perf_counter()
        with _cf_req(url, timeout=60) as resp:
            while True:
                chunk = resp.read(CHUNK)
                if not chunk:
                    break
                total += len(chunk)
        elapsed = time.perf_counter() - t0
        if elapsed >= 0.5 and total >= 1024:
            results[idx] = total / elapsed          # bytes/sec
        else:
            errors[idx] = (
                f"suspicious result: {total} B in {elapsed:.2f}s "
                f"(cache hit or redirect?)"
            )
    except Exception as e:
        errors[idx] = str(e)


def _upload_stream_worker(url: str, size: int, results: list, idx: int, errors: dict):
    """Upload `size` random bytes and measure throughput."""
    block = os.urandom(65_536)
    data  = (block * ((size + 65_535) // 65_536))[:size]
    try:
        t0 = time.perf_counter()
        with _cf_req(url, data=data, method="POST", timeout=60):
            pass
        elapsed = time.perf_counter() - t0
        if elapsed >= 0.5:
            results[idx] = size / elapsed
        else:
            errors[idx] = f"upload too fast ({elapsed:.2f}s) — likely dropped/cached"
    except Exception as e:
        errors[idx] = str(e)


def _measure_ping_http(attempts: int = 10) -> float | None:
    """
    Measure HTTP RTT using a 0-byte endpoint (no payload = pure network RTT).
    Tries each PING_TARGET in order; returns trimmed-median ms or None.
    """
    for _name, url in PING_TARGETS:
        times = []
        for _ in range(attempts):
            try:
                t0 = time.perf_counter()
                with _cf_req(url, timeout=5):
                    pass
                times.append((time.perf_counter() - t0) * 1000)
            except Exception:
                pass
            time.sleep(0.05)
        if len(times) >= 3:
            times.sort()
            trimmed = times[:max(2, int(len(times) * 0.8))]   # drop top 20% spikes
            return trimmed[len(trimmed) // 2]
    return None


def _measure_download(streams: int = NUM_STREAMS, size: int = DOWNLOAD_SIZE) -> tuple:
    """
    Try each server in DOWNLOAD_SOURCES.
    No pre-probe (avoids 429) — stream-0 acts as a canary instead.
    If canary succeeds → launch remaining streams in parallel.
    Returns (Mbps: float, server_name: str) or (None, error_summary: str).
    """
    all_errors = []

    for name, template, do_warmup in DOWNLOAD_SOURCES:
        url = template.format(size=size) if "{size}" in template else template

        # Warm-up for Cloudflare only (escapes TCP slow-start, irrelevant for CDN files)
        if do_warmup:
            try:
                wu = template.format(size=WARMUP_SIZE)
                with _cf_req(wu, timeout=12) as r:
                    while r.read(CHUNK):
                        pass
            except Exception:
                pass   # non-fatal — proceed to canary anyway

        # ── Canary stream (stream 0 alone) ───────────────────────────────
        can_res = [0.0]
        can_err: dict = {}
        ct = threading.Thread(
            target=_download_stream, args=(url, can_res, 0, can_err), daemon=True)
        ct.start()
        ct.join(timeout=20)

        if 0 in can_err:
            all_errors.append(f"{name}: {can_err[0]}")
            continue

        if can_res[0] == 0:
            all_errors.append(f"{name}: canary returned no usable data")
            continue

        # ── Remaining parallel streams ───────────────────────────────────
        rest_res = [0.0] * (streams - 1)
        rest_err: dict = {}
        rts = [
            threading.Thread(
                target=_download_stream, args=(url, rest_res, i, rest_err), daemon=True)
            for i in range(streams - 1)
        ]
        for t in rts: t.start()
        for t in rts: t.join()

        total_bps = can_res[0] + sum(rest_res)
        if total_bps > 0:
            return (total_bps * 8) / 1_000_000, name   # → Mbps

        all_errors.append(f"{name}: all parallel streams returned 0")

    return None, " | ".join(all_errors) or "All servers failed"


def _measure_upload(streams: int = NUM_STREAMS, size: int = UPLOAD_SIZE) -> tuple:
    """
    Try each UPLOAD_ENDPOINT in order.
    Returns (Mbps: float, name: str) or (None, error: str).
    """
    last_errors: dict = {}
    for name, url in UPLOAD_ENDPOINTS:
        results = [0.0] * streams
        errors: dict = {}
        threads = [
            threading.Thread(
                target=_upload_stream_worker,
                args=(url, size, results, i, errors), daemon=True)
            for i in range(streams)
        ]
        for t in threads: t.start()
        for t in threads: t.join()
        total_bps = sum(results)
        if total_bps > 0:
            return (total_bps * 8) / 1_000_000, name
        last_errors = errors

    errs = [str(v) for v in last_errors.values()]
    return None, "; ".join(errs[:2]) or "All upload endpoints failed"


def speed_test() -> tuple[float, float, float]:
    print(f"\n{_BOLD}{_CYAN}=== Wi-Fi Speed Test (Auto-Fallback) ==={_RESET}")
    print(f"  {_DIM}Streams : {NUM_STREAMS} parallel TCP connections{_RESET}")
    print(f"  {_DIM}Download: {len(DOWNLOAD_SOURCES)} servers, stops at first success{_RESET}")
    print(f"  {_DIM}Upload  : {UPLOAD_SIZE // 1_000_000} MB × {NUM_STREAMS} streams{_RESET}\n")

    # ── Ping ─────────────────────────────────────────────────────────────────
    t       = _spin_start("Measuring ping (10 samples, trimmed median)...")
    ping_ms = _measure_ping_http()
    _spin_stop(t)
    if ping_ms is None:
        print(f"  {_RED}✗ Ping failed — check connection.{_RESET}")
        ping_ms = 0.0
    else:
        print(f"  {_MAGENTA}Ping    :{_RESET}  {ping_ms:>6.1f} ms   {_bar(ping_ms, 150, high_good=False)}")

    # ── Download ──────────────────────────────────────────────────────────────
    t = _spin_start(f"Download — canary + {NUM_STREAMS} streams, auto-fallback on 429...")
    dl_mbps, dl_info = _measure_download()
    _spin_stop(t)

    if dl_mbps is not None and dl_mbps > 0:
        print(f"  {_GREEN}↓ Download:{_RESET}  {dl_mbps:>7.2f} Mbps  {_bar(dl_mbps, 500)}  {_DIM}via {dl_info}{_RESET}")
    else:
        print(f"  {_RED}✗ Download failed — tried all {len(DOWNLOAD_SOURCES)} servers:{_RESET}")
        for part in (dl_info or "").split(" | ")[:5]:
            print(f"    {_DIM}{part}{_RESET}")
        dl_mbps = 0.0

    # ── Upload ────────────────────────────────────────────────────────────────
    t = _spin_start(f"Upload — {NUM_STREAMS} streams, auto-fallback...")
    ul_mbps, ul_info = _measure_upload()
    _spin_stop(t)

    if ul_mbps is not None and ul_mbps > 0:
        print(f"  {_YELLOW}↑ Upload  :{_RESET}  {ul_mbps:>7.2f} Mbps  {_bar(ul_mbps, 500)}  {_DIM}via {ul_info}{_RESET}")
    else:
        print(f"  {_RED}✗ Upload failed:{_RESET} {ul_info}")
        ul_mbps = 0.0

    # ── Summary ───────────────────────────────────────────────────────────────
    print(f"\n  {_BOLD}{_CYAN}{'─'*46}{_RESET}")
    print(f"  {_BOLD}Download  : {dl_mbps:.2f} Mbps{_RESET}")
    print(f"  {_BOLD}Upload    : {ul_mbps:.2f} Mbps{_RESET}")
    print(f"  {_BOLD}Ping      : {ping_ms:.1f} ms{_RESET}")
    if dl_mbps > 0 and ul_mbps > 0:
        print(f"  {_BOLD}Rating    : {_rating(dl_mbps, ul_mbps, ping_ms)}{_RESET}")
    else:
        print(f"  {_YELLOW}  Rating skipped — partial results{_RESET}")
    print(f"  {_BOLD}{_CYAN}{'─'*46}{_RESET}\n")

    return dl_mbps, ul_mbps, ping_ms


# =============================================================================
# BDIX speed test
# BUGFIX-13: get_servers() was called twice redundantly — removed duplicate call.
# =============================================================================

def bdix_speed_test() -> float | None:
    if not HAS_SPEEDTEST:
        print(f"{Fore.YELLOW}speedtest-cli not installed — skipping BDIX test.{Style.RESET_ALL}")
        return None
    try:
        st         = _speedtest_module.Speedtest()
        all_servers = st.get_servers()  # BUGFIX-13: called only once now
        bdix_server = None
        for server_list in all_servers.values():
            for server in server_list:
                sponsor = server.get("sponsor", "").lower()
                country = server.get("country", "").lower()
                if "bdix" in sponsor or "bangladesh" in country:
                    bdix_server = server
                    break
            if bdix_server:
                break

        if not bdix_server:
            print(f"{Fore.YELLOW}No BDIX server found. Using best available.{Style.RESET_ALL}")
            st.get_best_server()
        else:
            print(f"{Fore.GREEN}BDIX Server: {bdix_server['sponsor']} — {bdix_server['name']}{Style.RESET_ALL}")
            st.get_best_server([bdix_server])

        download = st.download() / 1_000_000
        upload   = st.upload()   / 1_000_000
        print(f"{Fore.CYAN}BDIX Download : {download:.2f} Mbps{Style.RESET_ALL}")
        print(f"{Fore.CYAN}BDIX Upload   : {upload:.2f} Mbps{Style.RESET_ALL}")
        return download
    except Exception as e:
        print(f"{Fore.RED}BDIX speed test failed: {e}{Style.RESET_ALL}")
        return None

# =============================================================================
# Wi-Fi channel analysis
# BUGFIX-14: get_current_connection() defined twice — duplicate removed.
# BUGFIX-15: freq_to_channel() defined twice — duplicate removed.
# =============================================================================

def freq_to_channel(freq: int) -> int | None:
    if 2412 <= freq <= 2484: return (freq - 2412) // 5 + 1
    if 5170 <= freq <= 5825: return (freq - 5170) // 5 + 34
    return None


def analyze_wifi_channels_termux():
    try:
        current_bssid      = ""
        current_link_speed = None
        try:
            out = subprocess.check_output(["termux-wifi-connectioninfo"], universal_newlines=True)
            if out.strip():
                d                  = json.loads(out)
                current_bssid      = d.get("bssid", "").lower()
                current_link_speed = d.get("link_speed_mbps")
        except Exception:
            pass

        try:
            out = subprocess.check_output(["termux-wifi-scaninfo"], universal_newlines=True)
            if not out.strip():
                return {}, None
            wifi_data = json.loads(out)
        except Exception:
            return {}, None

        channels:        dict = {}
        current_network: dict | None = None

        for net in wifi_data:
            freq      = net.get("frequency_mhz", 0)
            ssid      = net.get("ssid", "Hidden")
            bssid     = net.get("bssid", "").lower()
            rssi      = net.get("rssi", 0)
            bandwidth = net.get("channel_bandwidth_mhz", 20)
            channel   = freq_to_channel(freq)
            if not channel:
                continue
            info = {"ssid": ssid, "bssid": bssid, "rssi": rssi, "bandwidth": bandwidth}
            channels.setdefault(channel, []).append(info)
            if current_bssid and bssid == current_bssid:
                current_network = {"ssid": ssid, "channel": channel, "rssi": rssi,
                                   "bandwidth": bandwidth, "link_speed_mbps": current_link_speed}
        return channels, current_network

    except Exception as e:
        print(f"Wi-Fi channel analysis failed: {e}")
        return {}, None


def check_link_speed(interface: str = "wlan0") -> str:
    try:
        out = subprocess.check_output(
            ["iwconfig", interface], text=True, stderr=subprocess.DEVNULL)
        m = re.search(r"Bit Rate[:=]([0-9.]+\s*Mb/s)", out)
        return m.group(1) if m else "N/A"
    except Exception:
        return "N/A"


def is_channel_overlapping(channel: int) -> bool:
    return channel <= 14 and channel not in (1, 6, 11)


def print_wifi_analysis_results(channels: dict, current_network: dict):
    if not current_network:
        print(f"{Fore.RED}Unable to identify your current Wi-Fi network.{Style.RESET_ALL}")
        return
    ssid       = current_network["ssid"]
    channel    = current_network["channel"]
    rssi       = current_network["rssi"]
    bandwidth  = current_network["bandwidth"]
    link_speed = current_network.get("link_speed_mbps")
    link_str   = f"{link_speed} Mbps" if link_speed is not None else check_link_speed()

    print(f"\n{Fore.CYAN}=== Your Wi-Fi Network Analysis ==={Style.RESET_ALL}")
    print(f"SSID            : {ssid}")
    print(f"Channel         : {channel}")
    print(f"Signal Strength : {rssi} dBm")
    print(f"Channel Width      : {bandwidth} MHz")
    print(f"Link Speed      : {link_str}")

    if is_channel_overlapping(channel):
        print(f"\n{Fore.YELLOW}Warning: Channel overlaps. Recommended 2.4 GHz channels: 1, 6, or 11.{Style.RESET_ALL}")
    else:
        print(f"\n{Fore.GREEN}Your Wi-Fi channel is non-overlapping.{Style.RESET_ALL}")

    suggest_best_channel(channels, current_network)  # BUGFIX-16: was commented out


def suggest_best_channel(channels: dict, current_network: dict):
    if not channels:
        print(f"{Fore.RED}No Wi-Fi channels detected.{Style.RESET_ALL}")
        return
    ch         = current_network["channel"]
    candidates = ([1, 6, 11] if ch <= 14 else [
        36, 40, 44, 48, 52, 56, 60, 64,
        100, 104, 108, 112, 116, 120, 124, 128,
        132, 136, 140, 144, 149, 153, 157, 161, 165,
    ])
    best = min(candidates, key=lambda x: len(channels.get(x, [])))
    print(f"\n{Fore.CYAN}Channel Recommendation:{Style.RESET_ALL}")
    if best == ch:
        print(f"  Channel {ch} is already optimal.")
    else:
        print(f"  Consider switching to channel {best} for less interference.")
    print("\n  Wi-Fi tips:")
    for i, tip in enumerate([
        "Keep router firmware up to date.",
        "Place router centrally, away from walls.",
        "Minimise interference from other electronics.",
        "Use 5 GHz band for less interference and higher speeds.",
        "Regularly audit devices and remove unauthorised ones.",
    ], 1):
        print(f"    {i}. {tip}")

# =============================================================================
# Network problem detection
# BUGFIX-17: ping > 100 check came before ping > 200 — both would fire for
# severe latency. Reordered so severe is checked first (most severe wins).
# =============================================================================

def detect_network_problems(download_mbps, upload_mbps, ping, devices):
    """
    Analyse speed/ping results and return (problems, tips) lists.
    download_mbps / upload_mbps are in Mbps (not MBps).
    """
    problems, tips = [], []

    if download_mbps is not None and upload_mbps is not None:
        # Flag very slow overall speed (below 5 Mbps combined is poor for any plan)
        if (download_mbps + upload_mbps) < 5:
            problems.append("Very low overall network speed")
            tips.append("Contact your ISP to check for service issues or throttling")

        # Asymmetry checks — use Mbps directly (values already in Mbps)
        if download_mbps > 0 and upload_mbps < download_mbps * 0.05:
            problems.append("Severely low upload speed relative to download")
            tips.append("Check for large file uploads or backup processes running in background")
        elif download_mbps > 0 and upload_mbps < download_mbps * 0.1:
            problems.append("Low upload speed relative to download")
            tips.append("Limit background upload tasks or check your ISP upload allocation")

        if upload_mbps > 0 and download_mbps < upload_mbps * 0.5:
            problems.append("Unusually low download speed relative to upload")
            tips.append("Check for background downloads or streaming on other devices")
    else:
        problems.append("Unable to perform speed test")
        tips.append("Check your internet connection and try again later")

    if ping is not None:
        if ping > 200:
            problems.append("Severe network latency (>200 ms)")
            tips.append("Check for network congestion or try changing your DNS server")
        elif ping > 100:
            problems.append("High network latency (>100 ms)")
            tips.append("Close bandwidth-heavy applications; consider wired connection")
    else:
        problems.append("Unable to perform ping test")
        tips.append("Check your internet connection and try again later")

    if len(devices) > 10:
        problems.append(f"High number of connected devices ({len(devices)})")
        tips.append("Consider implementing QoS settings on your router")

    return problems, tips


def print_analysis_results(problems: list, tips: list):
    print(f"\n{Fore.CYAN}=== Network Analysis Results ==={Style.RESET_ALL}")
    if not problems:
        print(f"{Fore.GREEN}✓ No significant network problems detected.{Style.RESET_ALL}")
    else:
        print(f"{Fore.YELLOW}Potential network issues detected:{Style.RESET_ALL}")
        for i, p in enumerate(problems, 1):
            print(f"  {Fore.RED}{i}. {p}{Style.RESET_ALL}")
    print(f"\n{Fore.CYAN}Recommendations:{Style.RESET_ALL}")
    for i, t in enumerate(tips, 1):
        print(f"  {Fore.GREEN}{i}. {t}{Style.RESET_ALL}")
    print(f"\n{Fore.CYAN}General tips:{Style.RESET_ALL}")
    for i, tip in enumerate([
        "Regularly restart your router and modem",
        "Update your router's firmware",
        "Use a wired connection when possible",
        "Optimise router placement for better coverage",
        "Implement QoS settings on your router",
        "Consider upgrading to a mesh network for larger areas",
        "Use a network analyser to find less congested Wi-Fi channels",
        "Limit the number of connected devices",
        "Enable WPA3 security if supported by your router",
        "Contact your ISP if problems persist",
    ], 1):
        print(f"  {Fore.YELLOW}{i}. {tip}{Style.RESET_ALL}")

# =============================================================================
# Local dashboard
# BUGFIX-18: Dashboard served FileNotFoundError if index.html missing.
#            Now returns a friendly placeholder page instead of crashing.
# =============================================================================

def start_local_dashboard(port: int = 8000):
    class DashboardHandler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(BASE_DIR), **kwargs)

        def do_GET(self):
            if self.path in ("/",) or self.path.startswith("/?"):
                try:
                    if HTML_TEMPLATE_PATH.exists():
                        content = HTML_TEMPLATE_PATH.read_text(encoding="utf-8")
                    else:
                       
                        content = (
                            "<html><head><title>CK Network Dashboard</title></head>"
                            "<body style='font-family:monospace;padding:2em'>"
                            "<h2>📡 CK Network Dashboard</h2>"
                            "<p><b>index.html</b> not found next to this script.</p>"
                            "<p>Place your dashboard HTML file as <code>index.html</code> "
                            "in the same directory.</p>"
                            f"<p>Results JSON: <a href='/api/results'>/api/results</a></p>"
                            "</body></html>"
                        )
                    b = content.encode("utf-8")
                    self.send_response(200)
                    self.send_header("Content-Type",   "text/html; charset=utf-8")
                    self.send_header("Cache-Control",  "no-store")
                    self.send_header("Content-Length", str(len(b)))
                    self.end_headers()
                    self.wfile.write(b)
                except Exception:
                    self.send_error(500, "Failed to load dashboard")
                return

            if self.path.startswith("/api/results"):
                payload = json.dumps(get_results_snapshot()).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type",   "application/json; charset=utf-8")
                self.send_header("Cache-Control",  "no-store")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)
                return

            return super().do_GET()

        def log_message(self, *_):
            pass  

    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", port), DashboardHandler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{port}/"
    print(f"{Fore.CYAN}Local dashboard: {url}{Style.RESET_ALL}")
    try:
        webbrowser.open(url)
    except Exception:
        pass
    return httpd

# =============================================================================
# Main
# =============================================================================

def main():
    _clear_screen()
    print_logo()

    update_results({"status": "running"})
    start_local_dashboard(port=8000)

    local_ip, netmask = get_network_info()
    if not local_ip or not netmask:
        print(f"{Fore.RED}Could not detect network information automatically.{Style.RESET_ALL}")
        update_results({"status": "error", "error": "Could not detect network information automatically"})
        return

    network_range = get_network_range(local_ip, netmask)
    wifi_info     = get_wifi_info()
    router_ip     = network_range.split("/")[0][:-1] + "1"
    isp_local_ip  = ping_isp_local()

    update_results({"connection": {
        "local_ip":      local_ip,
        "netmask":       netmask,
        "network_range": network_range,
        "gateway":       router_ip,
        "isp_local_ip":  isp_local_ip,
    }})

    print(f"\n{Fore.CYAN}=== Connection Details ==={Style.RESET_ALL}")
    print(f"{Fore.YELLOW}Local IP        : {Fore.GREEN}{local_ip}")
    print(f"{Fore.YELLOW}Subnet Mask     : {Fore.GREEN}{netmask}")
    print(f"{Fore.YELLOW}Network Range   : {Fore.GREEN}{network_range}")
    print(f"{Fore.YELLOW}Assumed Gateway : {Fore.GREEN}{router_ip}")

    if wifi_info:
        print(f"{Fore.YELLOW}SSID            : {Fore.GREEN}{wifi_info.get('ssid', 'Unknown')}")
        print(f"{Fore.YELLOW}BSSID           : {Fore.GREEN}{wifi_info.get('bssid', 'Unknown')}")
        rssi = wifi_info.get("rssi")
        if rssi is not None:
            print(f"{Fore.YELLOW}RSSI            : {Fore.GREEN}{rssi} dBm")
            print(f"{Fore.YELLOW}Estimated Dist. : {Fore.GREEN}{simple_distance_estimate(rssi)}")
        else:
            print(f"{Fore.RED}RSSI data not available.{Style.RESET_ALL}")
    else:
        print(f"{Fore.RED}Could not retrieve Wi-Fi information.{Style.RESET_ALL}")

    rssi           = wifi_info.get("rssi")           if wifi_info else None
    signal_percent = wifi_info.get("signal_percent") if wifi_info else None
    if signal_percent is None and rssi is not None:
        signal_percent = int(max(0, min(100, (rssi + 100) * 2)))

    update_results({"wifi": {
        "ssid":               (wifi_info.get("ssid")  if wifi_info else None) or "Unknown",
        "bssid":              (wifi_info.get("bssid") if wifi_info else None) or "Unknown",
        "rssi":               rssi,
        "rssi_text":          (f"{rssi} dBm" if rssi is not None else "N/A"),
        "estimated_distance": (simple_distance_estimate(rssi) if rssi is not None else "Unknown"),
        "signal_percent":     signal_percent,
    }})

    print()
    ping_router()

    # 1. Network scan
    print(f"\n{Fore.YELLOW}Scanning network {network_range}...{Style.RESET_ALL}")
    t0      = time.time()
    devices = scan_network(network_range, router_ip)
    elapsed = time.time() - t0

    update_results({"devices": {
        "count":        len(devices),
        "items":        [{"ip": ip, "hostname": hn} for ip, hn in devices],
        "scan_seconds": round(elapsed, 2),
    }})

    print(f"\n{Fore.GREEN}Devices connected to the network: {len(devices)}{Style.RESET_ALL}")
    for ip, hostname in devices:
        print(f"  IP: {ip}  Hostname: {hostname}")
    print(f"\nScan completed in {elapsed:.2f} seconds")

    # 2. Speed test
    print(f"\n{Fore.YELLOW}Performing speed test...{Style.RESET_ALL}")
    dl_mbps, ul_mbps, _ping = speed_test()
    download_MBps = dl_mbps / 8
    upload_MBps   = ul_mbps / 8

    # 3. BDIX speed test
    print(f"\n{Fore.YELLOW}Performing BDIX speed test...{Style.RESET_ALL}")
    bdix_MBps = bdix_speed_test()
    if bdix_MBps is not None:
        print(f"BDIX Download speed: {bdix_MBps:.2f} Mbps")

    update_results({"speed": {
        "download_mbps": dl_mbps,
        "upload_mbps":   ul_mbps,
        "bdix_mbps":     bdix_MBps,
    }})

    # 4. Ping tests
    print(f"\n{Fore.YELLOW}Performing ping tests...{Style.RESET_ALL}")
    isp_target   = isp_local_ip or router_ip or "1.1.1.1"
    ping_targets = [
        ("local_isp",  isp_target),
        ("bdix",       "9.9.9.9"),
        ("cloudflare", "1.1.1.1"),
        ("meta",       "edge-mqtt.facebook.com"),
        ("singapore",  "142.250.199.78"),
    ]
    ping_results = {}
    for key, host in ping_targets:
        print(f"  Pinging {host} ({key})...")
        stats = ping_detailed(host, count=5)
        if stats and stats.get("avg_ms") is not None:
            ping_results[key] = stats
            avg_ms = stats["avg_ms"]
            color  = Fore.GREEN if avg_ms < 50 else Fore.YELLOW if avg_ms < 100 else Fore.RED
            print(f"  Result: {color}{avg_ms:.2f} ms{Style.RESET_ALL}")
        else:
            print(f"  {Fore.RED}Ping failed{Style.RESET_ALL}")

    gateway_stats  = ping_detailed(router_ip, count=5) if router_ip else None
    gateway_ping   = gateway_stats.get("avg_ms") if gateway_stats else None
    internet_stats = ping_detailed("8.8.8.8",   count=5)
    internet_avg   = internet_stats.get("avg_ms") if internet_stats else None

    connection_status = "Unknown"
    if gateway_ping is not None:
        if   gateway_ping < 5:  connection_status = "Excellent"
        elif gateway_ping < 15: connection_status = "Good"
        elif gateway_ping < 30: connection_status = "Average"
        else:                   connection_status = "Poor or Unstable"

    update_results({
        "router": {"ping_ms": gateway_ping, "status": connection_status},
        "health": {
            "gateway":            gateway_stats,
            "internet":           internet_stats,
            "gateway_ping_ms":    gateway_ping,
            "internet_latency_ms": internet_avg,
            "pings":              ping_results,
        },
    })

    # 5. Wi-Fi channel analysis
    print(f"\n{Fore.YELLOW}Analyzing Wi-Fi channels...{Style.RESET_ALL}")
    channels, current_network = analyze_wifi_channels_termux()
    if channels and current_network:
        link_speed     = current_network.get("link_speed_mbps")
        link_speed_str = f"{link_speed} Mbps" if link_speed is not None else check_link_speed()
        update_results({"wifi_analysis": {
            "ssid":      current_network["ssid"],
            "channel":   current_network["channel"],
            "rssi":      current_network["rssi"],
            "bandwidth": current_network["bandwidth"],
            "link_speed": link_speed_str,
        }})
        print_wifi_analysis_results(channels, current_network)
    else:
        print(f"{Fore.RED}Unable to perform Wi-Fi analysis (needs Termux or Linux with nmcli).{Style.RESET_ALL}")

    # 6. Problem detection — pass Mbps values directly
    problems, tips = detect_network_problems(dl_mbps, ul_mbps, internet_avg, devices)
    print_analysis_results(problems, tips)

    update_results({"status": "complete", "analysis": {"problems": problems, "tips": tips}})
    print(f"\n{Fore.CYAN}Dashboard still running → http://127.0.0.1:8000/{Style.RESET_ALL}")
    try:
        input("Press Enter to stop the local dashboard and exit...")
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
