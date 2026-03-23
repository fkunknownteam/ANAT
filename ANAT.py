#!/usr/bin/env python3
# tool by : Golu Molu
# team    : Fk Unknown Team



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

# =============================================================================
# Optional dependencies
# =============================================================================

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

# =============================================================================
# ANSI colors (fallback if colorama missing)
# =============================================================================

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
            ctypes.windll.kernel32.GetStdHandle(-11), 7
        )
    except Exception:
        _CYAN = _GREEN = _YELLOW = _RED = _MAGENTA = _BOLD = _DIM = _RESET = ""

# =============================================================================
# Paths & shared result store
# =============================================================================

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

# =============================================================================
# Speed-test configuration
# =============================================================================

DOWNLOAD_DURATION = 30
UPLOAD_SIZE       = 10_000_000
NUM_STREAMS       = 4
CHUNK             = 131_072

DOWNLOAD_SOURCES = [
    ("Cloudflare",      "https://speed.cloudflare.com/__down?bytes=104857600"),
    ("Github-large",    "https://github.com/szalony9szymek/large/releases/download/free/large"),
    ("Realme-Rollback", "https://download.c.realme.com/flash/Rollbackpack/realme_Narzo_50/oplus_ota_downgrade.zip"),
]

UPLOAD_ENDPOINTS = [
    ("Cloudflare", "https://speed.cloudflare.com/__up"),
    ("httpbin",    "https://httpbin.org/post"),
]

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


def _termux_request_location_once():
    try:
        subprocess.run(
            ["termux-location", "-p", "network", "-r", "once"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            text=True, timeout=8,
        )
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
            RESULTS_JSON_PATH.write_text(
                json.dumps(RESULTS, indent=2), encoding="utf-8"
            )
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
    print(f"\n{cyan}╔{'═' * (W + 2)}╗{reset}")
    for row in rows:
        plain = re.sub(r"\033\[[0-9;]*m", "", row)
        pad   = W - len(plain)
        print(f"{cyan}║ {row}{' ' * max(pad, 0)}{cyan} ║{reset}")
    footer = "=== Advanced Network Analysis Tool ==="
    fp = (W - len(footer)) // 2
    print(f"{cyan}╠{'═' * (W + 2)}╣{reset}")
    print(
        f"{cyan}║{' ' * fp}{bold}{yellow}{footer}"
        f"{' ' * (W - fp - len(footer))}{cyan} ║{reset}"
    )
    print(f"{cyan}╚{'═' * (W + 2)}╝{reset}\n")

# =============================================================================
# Network info
# =============================================================================

def get_network_info():
    if HAS_NETIFACES:
        for iface in _netifaces.interfaces():
            addrs = _netifaces.ifaddresses(iface)
            if _netifaces.AF_INET in addrs:
                info = addrs[_netifaces.AF_INET][0]
                ip   = info.get("addr", "")
                nm   = info.get("netmask", "")
                if ip and not ip.startswith("127."):
                    return ip, nm
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
    if rssi >= -50:
        return "1–2 meters (Very close)"
    if rssi >= -60:
        return "2–4 meters"
    if rssi >= -70:
        return "4–8 meters"
    if rssi >= -80:
        return "8–15 meters"
    return "15+ meters (Weak or far)"


def get_wifi_info():
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
            out = subprocess.check_output(
                ["netsh", "wlan", "show", "interfaces"],
                stderr=subprocess.STDOUT, universal_newlines=True,
            )
            ssid = bssid = signal_pct = None
            for line in out.splitlines():
                if ":" not in line:
                    continue
                k, _, v = line.partition(":")
                k, v    = k.strip().lower(), v.strip()
                if k == "ssid" and not ssid:
                    ssid = v
                elif k == "bssid" and not bssid:
                    bssid = v
                elif k == "signal" and signal_pct is None:
                    m = re.search(r"(\d+)\s*%", v)
                    if m:
                        signal_pct = int(m.group(1))
            rssi = int(round((signal_pct / 2) - 100)) if signal_pct is not None else None
            return {
                "ssid": ssid or "Unknown",
                "bssid": bssid or "Unknown",
                "rssi": rssi,
                "signal_percent": signal_pct,
            }
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

def get_hostname(ip: str):
    try:
        hostname = socket.gethostbyaddr(ip)[0]
        return hostname if hostname != ip else None
    except Exception:
        return None

# =============================================================================
# Network scan
# =============================================================================

def ping_host(ip: str):
    try:
        if platform.system().lower() == "windows":
            subprocess.check_output(
                ["ping", "-n", "1", "-w", "1000", ip],
                stderr=subprocess.DEVNULL,
            )
        else:
            subprocess.check_output(
                ["ping", "-c", "1", "-W", "1", ip],
                stderr=subprocess.DEVNULL,
            )
        hostname = get_hostname(ip) or "Unknown"
        return ip, hostname, "Active"
    except subprocess.CalledProcessError:
        return ip, "Unknown", "Inactive"


def scan_network(network_range: str, router_ip: str) -> list:
    network   = ipaddress.IPv4Network(network_range)
    connected = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=100) as ex:
        futures = {
            ex.submit(ping_host, str(ip)): ip
            for ip in network.hosts()
            if str(ip) != router_ip
        }
        for fut in concurrent.futures.as_completed(futures):
            ip, hostname, status = fut.result()
            if status == "Active":
                connected.append((ip, hostname))
    return connected

# =============================================================================
# Ping helpers
# =============================================================================

def ping_detailed(host: str, count: int = 5, timeout_ms: int = 1000):
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
            return {
                "host": host, "min_ms": min_ms, "avg_ms": avg_ms,
                "max_ms": max_ms, "jitter_ms": jitter_ms,
                "loss_pct": loss_pct, "duplicates": 0,
            }
        else:
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
            return {
                "host": host, "min_ms": min_ms, "avg_ms": avg_ms,
                "max_ms": max_ms, "jitter_ms": jitter_ms,
                "loss_pct": loss_pct, "duplicates": dup,
            }
    except Exception:
        return None


def ping_test(host: str):
    stats = ping_detailed(host, count=5)
    return stats.get("avg_ms") if stats else None

# =============================================================================
# Router ping
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
        if avg_ping < 5:
            status = f"{Fore.GREEN}Excellent{Style.RESET_ALL}"
        elif avg_ping < 15:
            status = f"{Fore.CYAN}Good{Style.RESET_ALL}"
        elif avg_ping < 30:
            status = f"{Fore.YELLOW}Average{Style.RESET_ALL}"
        else:
            status = f"{Fore.RED}Poor or Unstable{Style.RESET_ALL}"
        print(f"{Fore.YELLOW}\n=== Health status ==={Style.RESET_ALL}")
        print(f"Average Ping Time : {avg_ping:.2f} ms")
        print(f"Connection Status : {status}")
    except Exception as e:
        print(f"Error during ping: {e}")

# =============================================================================
# ISP local hub discovery
# =============================================================================

def ping_isp_local(dest: str = "8.8.8.8"):
    def is_private(ip):
        try:
            return ipaddress.IPv4Address(ip).is_private
        except Exception:
            return False

    try:
        if platform.system().lower() == "windows":
            tr = subprocess.check_output(
                ["tracert", "-d", dest], stderr=subprocess.STDOUT, universal_newlines=True,
            )
        else:
            tr = subprocess.check_output(
                ["traceroute", "-n", dest], stderr=subprocess.STDOUT, universal_newlines=True,
            )
    except Exception as e:
        print(f"{Fore.RED}Traceroute failed: {e}{Style.RESET_ALL}")
        return None

    ips       = re.findall(r"\d+\.\d+\.\d+\.\d+", tr)
    router_ip = isp_ip = None
    for ip in ips:
        if is_private(ip):
            if router_ip is None:
                router_ip = ip
            elif isp_ip is None:
                isp_ip = ip
                break

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
# Speed test spinner helpers
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
# Speed test rating helper
# =============================================================================

def _rating(dl: float, ul: float, ping: float) -> str:
    score  = (3 if dl   >= 100 else 2 if dl   >= 25 else 1)
    score += (3 if ul   >= 50  else 2 if ul   >= 10 else 1)
    score += (3 if ping <= 20  else 2 if ping <= 60 else 1)
    if score >= 8:
        return f"{_GREEN}{_BOLD}★★★  Excellent{_RESET}"
    if score >= 5:
        return f"{_YELLOW}{_BOLD}★★☆  Good{_RESET}"
    return f"{_RED}{_BOLD}★☆☆  Poor{_RESET}"


def _cf_req(url: str, data=None, method: str = "GET", timeout: int = 30):
    headers = {
        "User-Agent":      "Mozilla/5.0 (CK-SpeedTest/3.3)",
        "Cache-Control":   "no-cache, no-store",
        "Pragma":          "no-cache",
        "Connection":      "keep-alive",
        "Accept-Encoding": "identity",
    }
    if data is not None:
        headers["Content-Type"]   = "application/octet-stream"
        headers["Content-Length"] = str(len(data))
    r = urllib.request.Request(url, data=data, headers=headers, method=method)
    return urllib.request.urlopen(r, timeout=timeout)


def _is_rate_limited(err_str: str) -> bool:
    return "429" in err_str or "Too Many" in err_str or "403" in err_str

# =============================================================================
# Speed test
# =============================================================================

def _download_timed_stream(url: str, duration: float, results: list, idx: int, errors: dict):
    total    = 0
    t0       = time.perf_counter()
    deadline = t0 + duration
    try:
        with _cf_req(url, timeout=int(duration) + 15) as resp:
            while time.perf_counter() < deadline:
                chunk = resp.read(CHUNK)
                if not chunk:
                    break
                total += len(chunk)
        elapsed = time.perf_counter() - t0
        if elapsed >= 2.0 and total >= 65_536:
            results[idx] = total / elapsed
        else:
            errors[idx] = f"too little data: {total} B in {elapsed:.2f}s"
    except Exception as e:
        errors[idx] = str(e)


def _upload_stream_worker(url: str, size: int, results: list, idx: int, errors: dict):
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
            trimmed = times[:max(2, int(len(times) * 0.8))]
            return trimmed[len(trimmed) // 2]
    return None


def _measure_download(streams: int = NUM_STREAMS, duration: float = DOWNLOAD_DURATION) -> tuple:
    all_errors = []
    for name, url, *_ in DOWNLOAD_SOURCES:
        can_res  = [0.0]
        can_err: dict = {}
        ct = threading.Thread(
            target=_download_timed_stream,
            args=(url, 3.0, can_res, 0, can_err), daemon=True,
        )
        ct.start()
        ct.join(timeout=18)
        if 0 in can_err:
            all_errors.append(f"{name}: {can_err[0]}")
            continue
        if can_res[0] == 0:
            all_errors.append(f"{name}: canary returned no usable data")
            continue
        results = [0.0] * streams
        errors: dict = {}
        threads = [
            threading.Thread(
                target=_download_timed_stream,
                args=(url, duration, results, i, errors), daemon=True,
            )
            for i in range(streams)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=duration + 20)
        total_bps = sum(results)
        if total_bps > 0:
            return (total_bps * 8) / 1_000_000, name
        all_errors.append(f"{name}: all parallel streams returned 0")
    return None, " | ".join(all_errors) or "All servers failed"


def _measure_upload(streams: int = NUM_STREAMS, size: int = UPLOAD_SIZE) -> tuple:
    last_errors: dict = {}
    for name, url in UPLOAD_ENDPOINTS:
        results = [0.0] * streams
        errors: dict = {}
        threads = [
            threading.Thread(
                target=_upload_stream_worker,
                args=(url, size, results, i, errors), daemon=True,
            )
            for i in range(streams)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        total_bps = sum(results)
        if total_bps > 0:
            return (total_bps * 8) / 1_000_000, name
        last_errors = errors
    errs = [str(v) for v in last_errors.values()]
    return None, "; ".join(errs[:2]) or "All upload endpoints failed"


def speed_test() -> tuple[float, float, float]:
    print(f"\n{_BOLD}{_CYAN}=== Wi-Fi Speed Test (Auto-Fallback) ==={_RESET}")
    print(f"  {_DIM}Streams  : {NUM_STREAMS} parallel TCP connections{_RESET}")
    print(f"  {_DIM}Download : {DOWNLOAD_DURATION}s timed window across {len(DOWNLOAD_SOURCES)} servers{_RESET}")
    print(f"  {_DIM}Upload   : {UPLOAD_SIZE // 1_000_000} MB × {NUM_STREAMS} streams{_RESET}\n")

    t       = _spin_start("Measuring ping (10 samples, trimmed median)...")
    ping_ms = _measure_ping_http()
    _spin_stop(t)
    if ping_ms is None:
        print(f"  {_RED}✗ Ping failed — check connection.{_RESET}")
        ping_ms = 0.0
    else:
        print(f"  {_MAGENTA}Ping    :{_RESET}  {ping_ms:>6.1f} ms")

    print(f"  {_DIM}Starting {DOWNLOAD_DURATION}s download test...{_RESET}")
    _countdown_done = threading.Event()

    def _countdown_display():
        for remaining in range(DOWNLOAD_DURATION, 0, -1):
            if _countdown_done.is_set():
                break
            sys.stdout.write(
                f"\r  {_CYAN}⠿{_RESET}  Downloading...  {_BOLD}{remaining:>2}s remaining{_RESET}   "
            )
            sys.stdout.flush()
            time.sleep(1)
        sys.stdout.write("\r" + " " * 60 + "\r")
        sys.stdout.flush()

    cd_thread = threading.Thread(target=_countdown_display, daemon=True)
    cd_thread.start()
    dl_mbps, dl_info = _measure_download()
    _countdown_done.set()
    cd_thread.join()

    if dl_mbps is not None and dl_mbps > 0:
        print(f"  {_GREEN}↓ Download:{_RESET}  {dl_mbps:>7.2f} Mbps  {_DIM}via {dl_info}{_RESET}")
    else:
        print(f"  {_RED}✗ Download failed — tried all {len(DOWNLOAD_SOURCES)} servers:{_RESET}")
        for part in (dl_info or "").split(" | ")[:5]:
            print(f"    {_DIM}{part}{_RESET}")
        dl_mbps = 0.0

    t = _spin_start(f"Upload — {NUM_STREAMS} streams, auto-fallback...")
    ul_mbps, ul_info = _measure_upload()
    _spin_stop(t)

    if ul_mbps is not None and ul_mbps > 0:
        print(f"  {_YELLOW}↑ Upload  :{_RESET}  {ul_mbps:>7.2f} Mbps  {_DIM}via {ul_info}{_RESET}")
    else:
        print(f"  {_RED}✗ Upload failed:{_RESET} {ul_info}")
        ul_mbps = 0.0

    print(f"\n  {_BOLD}{_CYAN}{'─' * 40}{_RESET}")
    print(f"  {_BOLD}Download  : {dl_mbps:.2f} Mbps{_RESET}")
    print(f"  {_BOLD}Upload    : {ul_mbps:.2f} Mbps{_RESET}")
    print(f"  {_BOLD}Ping      : {ping_ms:.1f} ms{_RESET}")
    if dl_mbps > 0 and ul_mbps > 0:
        print(f"  {_BOLD}Rating    : {_rating(dl_mbps, ul_mbps, ping_ms)}{_RESET}")
    else:
        print(f"  {_YELLOW}  Rating skipped — partial results{_RESET}")
    print(f"  {_BOLD}{_CYAN}{'─' * 40}{_RESET}\n")

    return dl_mbps, ul_mbps, ping_ms

# =============================================================================
# BDIX speed test
# =============================================================================

def bdix_speed_test() -> float | None:
    if not HAS_SPEEDTEST:
        print(f"{Fore.YELLOW}speedtest-cli not installed — skipping BDIX test.{Style.RESET_ALL}")
        return None
    try:
        st          = _speedtest_module.Speedtest()
        all_servers = st.get_servers()
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
# Wi-Fi channel analysis — KEY FIX: BSSID-exact MAC match
# =============================================================================

def freq_to_channel(freq: int):
    """Convert MHz frequency to Wi-Fi channel number."""
    if 2412 <= freq <= 2484:
        return (freq - 2412) // 5 + 1
    if 5170 <= freq <= 5825:
        return (freq - 5170) // 5 + 34
    return None


def freq_to_band(freq: int) -> str:
    """Return human-readable band string from MHz frequency."""
    if 2400 <= freq <= 2500:
        return "2.4 GHz"
    if 5000 <= freq <= 6000:
        return "5 GHz"
    return "Unknown"


def _normalise_mac(mac: str) -> str:
    """Lowercase colon-separated MAC for consistent comparison."""
    mac = (mac or "").strip().lower()
    digits = re.sub(r"[^0-9a-f]", "", mac)
    if len(digits) == 12:
        return ":".join(digits[i:i+2] for i in range(0, 12, 2))
    return mac  # return as-is if not standard length


def _is_unknown_ssid(ssid: str) -> bool:
    return not ssid or ssid.strip().lower() in (
        "<unknown ssid>", "unknown ssid", "", "null"
    )


def check_link_speed(interface: str = "wlan0") -> str:
    try:
        out = subprocess.check_output(
            ["iwconfig", interface], text=True, stderr=subprocess.DEVNULL,
        )
        m = re.search(r"Bit Rate[:=]([0-9.]+\s*Mb/s)", out)
        return m.group(1) if m else "N/A"
    except Exception:
        return "N/A"


def is_channel_overlapping(channel: int) -> bool:
    """Only 2.4 GHz channels can overlap; 5 GHz channels never do."""
    return channel is not None and channel <= 14 and channel not in (1, 6, 11)


def analyze_wifi_channels_termux():
    """
    Returns (channels: dict, current_network: dict | None).

    Match priority (highest → lowest):
      1. Exact BSSID match          — most reliable, finds correct radio
      2. Adjacent BSSID match       — catches the other radio on dual-band routers
                                      (router MACs typically differ by ±1..4 on last byte)
      3. Best-RSSI SSID match       — same SSID, pick strongest signal
      4. Connectioninfo frequency   — derive channel from reported freq directly
      5. Strongest scanned AP       — last resort so something is always shown
    """
    MAX_SCAN_ATTEMPTS = 5

    # ── Step 1: get connection info ───────────────────────────────────────────
    conn_bssid      = ""
    conn_ssid       = ""
    conn_link_speed = None
    conn_rssi       = None
    conn_freq       = None

    for attempt in range(3):
        try:
            subprocess.run(
                ["termux-location", "-p", "network", "-r", "once"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                text=True, timeout=8,
            )
        except Exception:
            pass
        try:
            out = subprocess.check_output(
                ["termux-wifi-connectioninfo"],
                universal_newlines=True, timeout=10,
            )
            if out.strip():
                d               = json.loads(out)
                conn_bssid      = _normalise_mac(d.get("bssid") or "")
                conn_ssid       = (d.get("ssid") or "").strip()
                conn_link_speed = d.get("link_speed_mbps")
                conn_rssi       = d.get("rssi")
                conn_freq       = d.get("frequency_mhz") or d.get("frequency")
                break
        except Exception:
            time.sleep(0.5 * (attempt + 1))

    # Build set of candidate BSSIDs — exact + adjacent (±4) on last byte.
    # Dual-band routers share the same OUI; radios differ on last octet only.
    candidate_bssids: set[str] = set()
    if conn_bssid and len(conn_bssid) == 17:
        candidate_bssids.add(conn_bssid)
        parts = conn_bssid.split(":")
        last  = int(parts[-1], 16)
        for delta in range(-4, 5):
            adj = parts[:-1] + [f"{(last + delta) & 0xFF:02x}"]
            candidate_bssids.add(":".join(adj))

    # ── Step 2: scan with retries ─────────────────────────────────────────────
    wifi_data = []
    for attempt in range(MAX_SCAN_ATTEMPTS):
        try:
            out = subprocess.check_output(
                ["termux-wifi-scaninfo"],
                universal_newlines=True, timeout=15,
            )
            if out.strip():
                parsed = json.loads(out)
                if isinstance(parsed, list) and parsed:
                    wifi_data = parsed
                    break
        except Exception:
            pass
        delay = 0.5 * (attempt + 1)
        print(
            f"{Fore.YELLOW}  Wi-Fi scan attempt {attempt + 1}/{MAX_SCAN_ATTEMPTS} "
            f"returned no data — retrying in {delay:.1f}s…{Style.RESET_ALL}"
        )
        time.sleep(delay)

    # Scan completely failed — minimal result from connectioninfo
    if not wifi_data:
        print(f"{Fore.YELLOW}  Scan returned no APs. Using connection-info only.{Style.RESET_ALL}")
        ch  = freq_to_channel(int(conn_freq)) if conn_freq else None
        bnd = freq_to_band(int(conn_freq))    if conn_freq else "Unknown"
        ls  = f"{conn_link_speed} Mbps" if conn_link_speed is not None else check_link_speed()
        if conn_bssid or conn_ssid:
            return {}, {
                "ssid":            conn_ssid or "Unknown",
                "bssid":           conn_bssid or "Unknown",
                "channel":         ch,
                "band":            bnd,
                "rssi":            conn_rssi,
                "bandwidth":       None,
                "link_speed_mbps": conn_link_speed,
                "link_speed_str":  ls,
                "source":          "connectioninfo-only (no scan data)",
            }
        return {}, None

    # ── Step 3: build channel map & score every scanned AP ───────────────────
    channels: dict = {}
    exact_match    = None   # priority 1
    adjacent_match = None   # priority 2
    ssid_matches   = []     # priority 3 — all APs with matching SSID
    best_network   = None   # priority 5 — strongest RSSI of all APs

    for net in wifi_data:
        raw_freq  = net.get("frequency_mhz") or net.get("frequency") or 0
        freq      = int(raw_freq)
        ssid      = (net.get("ssid") or "Hidden").strip()
        bssid     = _normalise_mac(net.get("bssid") or "")
        rssi      = net.get("rssi", -100)
        bandwidth = net.get("channel_bandwidth_mhz", 20)
        channel   = freq_to_channel(freq)
        band      = freq_to_band(freq)
        if not channel:
            continue

        channels.setdefault(channel, []).append(
            {"ssid": ssid, "bssid": bssid, "rssi": rssi, "bandwidth": bandwidth}
        )

        entry = {
            "ssid": ssid, "bssid": bssid, "channel": channel, "band": band,
            "rssi": rssi, "bandwidth": bandwidth,
            "link_speed_mbps": conn_link_speed,
        }

        # Priority 5 — global best signal fallback
        if best_network is None or rssi > best_network.get("rssi", -999):
            best_network = dict(entry, source="strongest-ap-fallback")

        # Priority 1 — exact BSSID
        if conn_bssid and bssid == conn_bssid:
            if exact_match is None or rssi > exact_match.get("rssi", -999):
                exact_match = dict(entry, source="bssid-exact-match ✓")

        # Priority 2 — adjacent BSSID (other radio, same physical router)
        elif bssid in candidate_bssids:
            if adjacent_match is None or rssi > adjacent_match.get("rssi", -999):
                adjacent_match = dict(entry, source="bssid-adjacent-match (other radio)")

        # Priority 3 — SSID match
        if (not _is_unknown_ssid(conn_ssid)
                and not _is_unknown_ssid(ssid)
                and ssid == conn_ssid):
            ssid_matches.append(entry)

    # ── Step 4: pick best match in priority order ─────────────────────────────
    current_network = None

    if exact_match:
        current_network = exact_match
    elif adjacent_match:
        current_network = adjacent_match
    elif ssid_matches:
        best_ssid = max(ssid_matches, key=lambda e: e.get("rssi", -999))
        current_network = dict(best_ssid, source="ssid-best-rssi-match")
    elif conn_freq:
        # Priority 4 — derive channel from connectioninfo frequency
        ch  = freq_to_channel(int(conn_freq))
        bnd = freq_to_band(int(conn_freq))
        current_network = {
            "ssid":            conn_ssid or "Unknown",
            "bssid":           conn_bssid or "Unknown",
            "channel":         ch,
            "band":            bnd,
            "rssi":            conn_rssi,
            "bandwidth":       None,
            "link_speed_mbps": conn_link_speed,
            "source":          "connectioninfo-frequency-derived",
        }
    elif best_network:
        current_network = best_network
    elif conn_bssid or conn_ssid:
        current_network = {
            "ssid":            conn_ssid or "Unknown",
            "bssid":           conn_bssid or "Unknown",
            "channel":         None,
            "band":            "Unknown",
            "rssi":            conn_rssi,
            "bandwidth":       None,
            "link_speed_mbps": conn_link_speed,
            "source":          "connectioninfo-no-scan-match",
        }

    # ── Step 5: fill in missing fields ───────────────────────────────────────
    if current_network:
        # Use connectioninfo RSSI if scan returned -100 (absent)
        if current_network.get("rssi") is None or current_network.get("rssi", -100) <= -100:
            current_network["rssi"] = conn_rssi
        ls = current_network.get("link_speed_mbps")
        current_network["link_speed_str"] = (
            f"{ls} Mbps" if ls is not None else check_link_speed()
        )
        current_network.setdefault("bssid", conn_bssid or "Unknown")
        current_network.setdefault("band",  "Unknown")

    return channels, current_network


def _print_general_wifi_tips():
    print(f"\n{Fore.CYAN}General Wi-Fi tips:{Style.RESET_ALL}")
    tips = [
        "Keep router firmware up to date.",
        "Place router centrally, elevated, away from walls & appliances.",
        "Minimise interference: keep away from microwaves, cordless phones.",
        "Use the 5 GHz band for less congestion and higher throughput.",
        "Use non-overlapping 2.4 GHz channels: 1, 6, or 11.",
        "Regularly audit connected devices and remove unauthorised ones.",
        "Enable WPA3 if your router supports it.",
    ]
    for i, tip in enumerate(tips, 1):
        print(f"  {i}. {tip}")


def print_wifi_analysis_results(channels: dict, current_network: dict):
    if not current_network:
        print(f"{Fore.RED}Unable to identify your current Wi-Fi network.{Style.RESET_ALL}")
        return

    ssid      = current_network.get("ssid") or "Unknown"
    bssid     = current_network.get("bssid") or "Unknown"
    channel   = current_network.get("channel")
    band      = current_network.get("band") or "Unknown"
    rssi      = current_network.get("rssi")
    bandwidth = current_network.get("bandwidth")
    link_str  = current_network.get("link_speed_str") or check_link_speed()
    source    = current_network.get("source", "")

    print(f"\n{Fore.CYAN}=== Your Wi-Fi Network Analysis ==={Style.RESET_ALL}")

    if _is_unknown_ssid(ssid):
        print(
            f"SSID            : {Fore.YELLOW}<hidden — grant Precise Location "
            f"permission to Termux>{Style.RESET_ALL}"
        )
    else:
        print(f"SSID            : {ssid}")

    print(f"BSSID           : {bssid}")
    print(f"Band            : {band}")
    print(f"Channel         : {channel if channel is not None else 'N/A'}")
    print(f"Signal Strength : {f'{rssi} dBm' if rssi is not None else 'N/A'}")
    print(f"Channel Width   : {f'{bandwidth} MHz' if bandwidth is not None else 'N/A'}")
    print(f"Link Speed      : {link_str}")
    if source:
        print(f"{Fore.CYAN}  (match method: {source}){Style.RESET_ALL}")

    if channel is not None:
        if band == "5 GHz":
            # 5 GHz channels are non-overlapping by design
            print(f"\n{Fore.GREEN}✓ 5 GHz band — channels never overlap. No interference concern.{Style.RESET_ALL}")
        elif is_channel_overlapping(channel):
            print(
                f"\n{Fore.YELLOW}⚠ Channel {channel} (2.4 GHz) overlaps with neighbours. "
                f"Recommended channels: 1, 6, or 11.{Style.RESET_ALL}"
            )
        else:
            print(f"\n{Fore.GREEN}✓ Channel {channel} is non-overlapping — good choice.{Style.RESET_ALL}")
        suggest_best_channel(channels, current_network)
    else:
        print(f"\n{Fore.YELLOW}Channel details could not be determined.{Style.RESET_ALL}")
        print(f"{Fore.CYAN}How to fix:{Style.RESET_ALL}")
        print("  1. Grant Termux Precise Location permission:")
        print("     Android Settings → Apps → Termux → Permissions → Location → Allow (Precise)")
        print("  2. Enable device Location / GPS.")
        print("  3. Test:  termux-wifi-scaninfo")
        print("  4. Toggle Wi-Fi off/on then re-run.")
        _print_general_wifi_tips()


def suggest_best_channel(channels: dict, current_network: dict):
    if not channels:
        print(f"{Fore.RED}No Wi-Fi channels detected in scan.{Style.RESET_ALL}")
        return

    ch   = current_network.get("channel")
    band = current_network.get("band", "Unknown")
    if ch is None:
        return

    # Non-overlapping candidate channels per band
    if band == "5 GHz" or ch > 14:
        # UNII-3 first (no DFS needed), then UNII-1, then DFS bands
        candidates = [
            149, 153, 157, 161, 165,          # UNII-3 — best for most home routers
            36, 40, 44, 48,                    # UNII-1 — indoor safe, no DFS
            52, 56, 60, 64,                    # UNII-2A — DFS
            100, 104, 108, 112, 116, 120,      # UNII-2C — DFS
            124, 128, 132, 136, 140, 144,
        ]
    else:
        candidates = [1, 6, 11]

    best    = min(candidates, key=lambda x: (len(channels.get(x, [])), x))
    crowded = {k: len(v) for k, v in channels.items()}

    print(f"\n{Fore.CYAN}Channel Recommendation:{Style.RESET_ALL}")
    print(f"  Channels in use : { {k: v for k, v in sorted(crowded.items())} }")
    if best == ch:
        print(f"  ✓ Channel {ch} already has the least congestion — no change needed.")
    else:
        print(
            f"  → Consider switching to channel {best} "
            f"({len(channels.get(best, []))} APs) "
            f"vs your current channel {ch} ({len(channels.get(ch, []))} APs)."
        )
    _print_general_wifi_tips()

# =============================================================================
# Network problem detection
# =============================================================================

def detect_network_problems(download_mbps, upload_mbps, ping, devices):
    problems, tips = [], []

    if download_mbps is not None and upload_mbps is not None:
        if (download_mbps + upload_mbps) < 5:
            problems.append("Very low overall network speed")
            tips.append("Contact your ISP to check for service issues or throttling")
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
    for i, tip in enumerate(
        [
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
        ],
        1,
    ):
        print(f"  {Fore.YELLOW}{i}. {tip}{Style.RESET_ALL}")

# =============================================================================
# Local dashboard
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
                            "<p>Results JSON: <a href='/api/results'>/api/results</a></p>"
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

    _termux_request_location_once()
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

    update_results({
        "connection": {
            "local_ip":      local_ip,
            "netmask":       netmask,
            "network_range": network_range,
            "gateway":       router_ip,
            "isp_local_ip":  isp_local_ip,
        }
    })

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

    update_results({
        "wifi": {
            "ssid":               (wifi_info.get("ssid") if wifi_info else None) or "Unknown",
            "bssid":              (wifi_info.get("bssid") if wifi_info else None) or "Unknown",
            "rssi":               rssi,
            "rssi_text":          (f"{rssi} dBm" if rssi is not None else "N/A"),
            "estimated_distance": simple_distance_estimate(rssi) if rssi is not None else "Unknown",
            "signal_percent":     signal_percent,
        }
    })

    print()
    ping_router()

    # 1. Network scan
    print(f"\n{Fore.YELLOW}Scanning network {network_range}...{Style.RESET_ALL}")
    t0      = time.time()
    devices = scan_network(network_range, router_ip)
    elapsed = time.time() - t0

    update_results({
        "devices": {
            "count":        len(devices),
            "items":        [{"ip": ip, "hostname": hn} for ip, hn in devices],
            "scan_seconds": round(elapsed, 2),
        }
    })

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

    update_results({
        "speed": {
            "download_mbps": dl_mbps,
            "upload_mbps":   ul_mbps,
            "download_MBps": download_MBps,
            "upload_MBps":   upload_MBps,
            "bdix_mbps":     bdix_MBps,
        }
    })

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
    internet_stats = ping_detailed("8.8.8.8", count=5)
    internet_avg   = internet_stats.get("avg_ms") if internet_stats else None

    connection_status = "Unknown"
    if gateway_ping is not None:
        if gateway_ping < 5:
            connection_status = "Excellent"
        elif gateway_ping < 15:
            connection_status = "Good"
        elif gateway_ping < 30:
            connection_status = "Average"
        else:
            connection_status = "Poor or Unstable"

    update_results({
        "router": {"ping_ms": gateway_ping, "status": connection_status},
        "health": {
            "gateway":             gateway_stats,
            "internet":            internet_stats,
            "gateway_ping_ms":     gateway_ping,
            "internet_latency_ms": internet_avg,
            "pings":               ping_results,
        },
    })

    # 5. Wi-Fi channel analysis
    print(f"\n{Fore.YELLOW}Analyzing Wi-Fi channels...{Style.RESET_ALL}")
    channels, current_network = analyze_wifi_channels_termux()
    if current_network:
        link_speed_str = current_network.get("link_speed_str") or check_link_speed()
        update_results({
            "wifi_analysis": {
                "ssid":       current_network.get("ssid"),
                "bssid":      current_network.get("bssid"),
                "band":       current_network.get("band"),
                "channel":    current_network.get("channel"),
                "rssi":       current_network.get("rssi"),
                "bandwidth":  current_network.get("bandwidth"),
                "link_speed": link_speed_str,
                "source":     current_network.get("source"),
            }
        })
        print_wifi_analysis_results(channels, current_network)
    else:
        print(f"{Fore.RED}Unable to perform Wi-Fi analysis (needs Termux API + location permission).{Style.RESET_ALL}")
        print("  Run:  termux-wifi-scaninfo  to verify scan is working.")

    # 6. Problem detection
    problems, tips = detect_network_problems(dl_mbps, ul_mbps, internet_avg, devices)
    print_analysis_results(problems, tips)

    update_results({
        "status": "complete",
        "analysis": {"problems": problems, "tips": tips},
    })

    print(f"\n{Fore.CYAN}Dashboard still running → http://127.0.0.1:8000/{Style.RESET_ALL}")
    try:
        input("Press Enter to stop the local dashboard and exit...")
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
