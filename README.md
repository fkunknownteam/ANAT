# ANAT — Advanced Network Analysis Tool

```
     /\       _   _  _____  _______   _______
    /  \     | \ | ||  __ \|__   __|  |__   __|
   / /\ \    |  \| || |  | |  | |        | |
  / ____ \   | . ` || |  | |  | |        | |
 /_/    \_\  |_|\_||_|  |_|  |_|        |_|
```

> **by Golu Molu · FK Unknown Team**  
> https://github.com/fkunknownteam/ANAT

![Platform](https://img.shields.io/badge/platform-Android%20%2F%20Termux-brightgreen)
![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![License](https://img.shields.io/badge/license-MIT-orange)

---

## What is ANAT?

ANAT is a full network analysis tool built for **Termux on Android**.  
Run it once and it automatically produces a complete network report — no config needed.

| Feature | Details |
|---|---|
| Wi-Fi Info | SSID, BSSID, signal strength (dBm), estimated distance to router |
| Speed Test | 30-second timed download · upload · ping with auto server fallback |
| Location | GPS coordinates via `termux-location` to tag your report |
| Device Scan | Live scan of every device on your subnet with hostnames |
| Channel Analysis | Detects Wi-Fi channel overlap and recommends best channel |
| Ping Tests | Router · ISP hub · Cloudflare · Meta · Singapore with jitter and loss |
| BDIX Test | Bangladesh local network speed test (optional) |
| Dashboard | Live web dashboard at `http://127.0.0.1:8000/` |
| Problem Detection | Flags issues automatically and prints fix tips |

---

## Tested Devices

| Device | Android Version | Status |
|---|---|---|
| Realme Narzo 50 | Android 13 | Working |
| Samsung Galaxy S20 5G | Android 13 | Working | 
| Xperia 1 III | Android 11 | Working |

---

## Requirements

- Android phone running **Termux** (install from F-Droid, not Play Store)
- **Termux:API** app installed from F-Droid
- Internet connection

---

## Installation

### Step 1 — Install F-Droid

F-Droid is required to get the full, unrestricted version of Termux.

```
https://f-droid.org/F-Droid.apk
```

Download and install the APK, open F-Droid, let it finish the repository update, then search for **Termux** and install it.

> Do **not** use the Play Store version of Termux — it is outdated and restricted.

---

### Step 2 — Install Termux:API

Open F-Droid, tap the search icon, search **Termux API**, and install it.

This companion app is required for:
- Reading Wi-Fi connection info (SSID, BSSID, signal strength)
- Scanning nearby Wi-Fi channels
- Fetching your GPS location via `termux-location`

> Installing the `termux-api` package inside Termux is **not enough** on its own.  
> You must also install the **Termux:API** Android app from F-Droid.

---

### Step 3 — Run these commands inside Termux

```bash
# Update packages
apt update && apt upgrade -y

# Install required tools
pkg install termux-api python git -y

# install required tools
pkg install traceroute

# Grant location permission — Android will show a permission dialog, tap Allow
termux-location

# Clone ANAT
git clone https://github.com/fkunknownteam/ANAT

# Enter the folder
cd ANAT

# allow
chmod +x ANAT.py

# Install optional Python packages
pip install -r requirements.txt

# Run ANAT
python ANAT.py
```

> **Why run `termux-location` before cloning?**  
> Running it once triggers Android's location permission dialog.  
> Accepting it now means ANAT can read your GPS coordinates automatically when it runs,  
> without interrupting the analysis mid-way. If you skip this step, the location section  
> will show a permission error and be skipped — everything else still works normally.

---

## What ANAT Does — Step by Step

ANAT performs all steps automatically in order when you run it.

### Step 1 · Connection Info

Detects your local IP, subnet mask, network range, and gateway IP.  
Runs a traceroute to discover your ISP's local hub IP.

### Step 2 · Location

Calls `termux-location` to fetch your GPS coordinates — latitude, longitude, altitude, and accuracy radius.  
This tags your saved report with where the test was run.  
Skipped gracefully if the location permission has not been granted.

### Step 3 · Wi-Fi Info

Reads your SSID, BSSID, signal strength in dBm and as a percentage, and estimates your distance from the router:

| Signal | Estimated Distance |
|---|---|
| -50 dBm or better | 1–2 meters (very close) |
| -51 to -60 dBm | 2–4 meters |
| -61 to -70 dBm | 4–8 meters |
| -71 to -80 dBm | 8–15 meters |
| Below -80 dBm | 15+ meters (weak or far) |

### Step 4 · Router Ping

Pings your gateway and rates connection quality:

| Ping | Rating |
|---|---|
| Under 5 ms | Excellent |
| 5 – 14 ms | Good |
| 15 – 29 ms | Average |
| 30 ms and above | Poor or Unstable |

### Step 5 · Network Device Scan

Scans every IP address on your subnet in parallel using 100 threads.  
Lists all active devices with their IP addresses and hostnames.

### Step 6 · Speed Test

Runs a **30-second timed download** across 4 parallel TCP streams, then an upload test.  
Uses a canary probe first to verify each server before committing all streams.  
Automatically falls back to the next server if one fails or rate-limits.

### Step 7 · BDIX Speed Test

Tests Bangladesh local network speed using `speedtest-cli`.  
Skipped automatically if `speedtest-cli` is not installed.

### Step 8 · Ping Tests

Pings 5 targets and reports min / avg / max / jitter / packet loss for each:

| Target | Address |
|---|---|
| Your ISP hub | detected via traceroute |
| Quad9 DNS | 9.9.9.9 |
| Cloudflare DNS | 1.1.1.1 |
| Meta edge server | edge-mqtt.facebook.com |
| Google Singapore | 142.250.199.78 |

### Step 9 · Wi-Fi Channel Analysis

Scans all nearby Wi-Fi networks using `termux-wifi-scaninfo`, detects channel overlap and interference, and recommends the least congested channel for your band (2.4 GHz or 5 GHz).

### Step 10 · Problem Detection

Automatically flags issues and prints fix tips for:
- Very slow overall speed
- Low upload speed relative to download
- High or severe latency
- Too many devices on the network

### Step 11 · Dashboard

All results are served live at `http://127.0.0.1:8000/api/results` as JSON and saved to `net_results.json`, updated after every step.

---

## Speed Test Details

ANAT uses **4 parallel TCP streams** to saturate your connection — the same method used by browser-based speed tests.

**How it works:**

1. Sends a 3-second canary probe to verify the server actually delivers bytes
2. Launches all 4 streams simultaneously for a full 30-second window
3. Measures total bytes received divided by elapsed time for sustained throughput
4. Falls back to the next server if the canary fails

**Download servers tried in order:**

| # | Server |
|---|---|
| 1 | Cloudflare CDN — `speed.cloudflare.com` |
| 2 | Github Large File |
| 3 | Realme Rollback CDN |

**Speed rating:**

| Rating | Download | Upload | Ping |
|---|---|---|---|
| 3 stars — Excellent | 100 Mbps or above | 50 Mbps or above | 20 ms or below |
| 2 stars — Good | 25 Mbps or above | 10 Mbps or above | 60 ms or below |
| 1 star — Poor | below the above | below the above | above the above |

The result always shows which server was actually used, for example: `via Cloudflare CDN`.

---

## Python Packages

| Package | Status | Purpose |
|---|---|---|
| `colorama` | Optional | Coloured terminal output |
| `netifaces` | Optional | More accurate network interface detection |
| `speedtest-cli` | Optional | BDIX speed test |
| `requests` | Optional | Reserved for future features |

Everything else uses Python built-in libraries only — no extra installs are needed to run the speed test, ping, scan, or dashboard.

Install all optional packages at once:

```bash
pip install -r requirements.txt
```

---

## Dashboard and Results File

A local web server starts automatically when ANAT runs:

```
http://127.0.0.1:8000/             main dashboard page
http://127.0.0.1:8000/api/results  live JSON of all results
```

Results are also written to `net_results.json` in the ANAT folder and updated after every step — you can monitor progress in real time from another device on the same network.

To use a custom dashboard, place an `index.html` file in the ANAT folder.  
If no `index.html` is present, a placeholder page is shown with a link to the JSON API.

---

## File Structure

```
ANAT/
├── ANAT.py            main script — run this
├── requirements.txt   optional Python dependencies
├── index.html         optional custom dashboard page
├── net_results.json   auto-created, updated live
└── README.md
```

---

## Troubleshooting

**Location shows permission denied**

Run `termux-location` once and accept the Android permission dialog:
```bash
termux-location
```
If the dialog never appears, go to Android Settings → Apps → Termux:API → Permissions → Location → Allow.

**Wi-Fi info shows Unknown**

Both the `termux-api` Termux package and the Termux:API Android app must be installed.
```bash
pkg install termux-api
```
Then install the app from F-Droid — search **Termux API**.

**Download test fails**

The tool prints each server's exact error message so you can see why.  
Check whether your network blocks outbound HTTP or whether you need a VPN.

**BDIX test is skipped**

Install speedtest-cli:
```bash
pip install speedtest-cli
```

**Traceroute failed at startup**

Some Android devices do not have `traceroute` available.  
The ISP hub detection step is skipped and all other tests run normally.

**Storage or permission error**

Run this once to grant Termux storage access:
```bash
termux-setup-storage
```

---

## License

MIT — free to use, modify, and share.

---

Made by Golu Molu · FK Unknown Team  
https://github.com/fkunknownteam/ANAT
