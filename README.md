# ANAT -- Advanced Network Analysis Tool

```
     /\       _   _  _____  _______   _______
    /  \     | \ | ||  __ \|__   __|  |__   __|
   / /\ \    |  \| || |  | |  | |        | |
  / ____ \   | . ` || |  | |  | |        | |
 /_/    \_\  |_|\_||_|  |_|  |_|        |_|
```

by Golu Molu -- FK Unknown Team

---

## What is ANAT?

ANAT is a network analysis tool that runs inside Termux on Android.
Run it once and it automatically performs a full network report:

- Wi-Fi signal strength, SSID, BSSID, and estimated distance to router
- Real download and upload speed test with 8 server fallbacks
- Ping and jitter to your router, ISP hub, Cloudflare, Google, Meta, and Singapore
- Live scan of every device connected to your network
- Wi-Fi channel analysis with interference detection and channel recommendation
- BDIX speed test for Bangladesh local network (optional)
- Local web dashboard at http://127.0.0.1:8000/ with all results
- Automatic problem detection with fix tips

---

## Requirements

- Android phone with Termux installed from F-Droid
- Termux:API app installed from F-Droid (required for Wi-Fi info and channel scan)
- Internet connection

---

## Installation

### Step 1 -- Install F-Droid

F-Droid is needed to get the full version of Termux.

Download: https://f-droid.org/F-Droid.apk

Install the APK, open F-Droid, let it finish updating, then search for
Termux and install it from there. Do not use the Play Store version.

### Step 2 -- Install Termux:API

Open F-Droid, tap the search icon, search "Termux API" and install it.
This app gives ANAT access to Wi-Fi scan data on your device.

### Step 3 -- Run these commands inside Termux

```
apt update && apt upgrade -y

pkg install termux-api python git -y

termux-location

git clone https://github.com/fkunknownteam/ANAT

cd ANAT

pip install -r requirements.txt

python ANAT.py
```

---

## What ANAT Does -- Step by Step

When you run ANAT it performs these steps automatically in order.

Step 1 -- Connection Info
Detects your local IP, subnet mask, network range, gateway IP, and your
ISP hub IP via traceroute.

Step 2 -- Wi-Fi Info
Reads your SSID, BSSID, signal strength in dBm, signal percentage, and
estimates how far you are from the router.

Step 3 -- Router Ping
Pings your gateway and rates the connection quality:

    Under 5 ms    Excellent
    Under 15 ms   Good
    Under 30 ms   Average
    30 ms and up  Poor or Unstable

Step 4 -- Network Device Scan
Scans every IP address on your subnet in parallel and lists all active
devices with their hostnames.

Step 5 -- Speed Test
Downloads from up to 8 CDN servers with automatic fallback if one fails
or rate-limits. Uploads to Cloudflare. Shows Mbps with a visual bar and
a quality rating.

Step 6 -- BDIX Speed Test
Tests Bangladesh local network speed using speedtest-cli.
Skipped automatically if speedtest-cli is not installed.

Step 7 -- Ping Tests
Pings 5 targets and reports min / avg / max / jitter / packet loss:

    Your ISP hub
    Quad9 DNS        9.9.9.9
    Cloudflare DNS   1.1.1.1
    Meta edge server
    Google Singapore

Step 8 -- Wi-Fi Channel Analysis
Scans all nearby networks, detects channel overlap and interference, and
recommends the best available channel for 2.4 GHz or 5 GHz.

Step 9 -- Problem Detection
Automatically flags issues and prints fix tips for:

    Very slow overall speed
    Low upload speed relative to download
    High or severe latency
    Too many devices on the network

Step 10 -- Dashboard
Results are served live at http://127.0.0.1:8000/api/results as JSON
and saved to net_results.json in the ANAT folder.

---

## Speed Test Details

ANAT uses 4 parallel TCP streams to saturate your connection, the same
way a browser-based speed test works. It sends a canary stream first to
detect rate-limits (HTTP 429) before launching the remaining streams.

Download servers tried in order (stops at first success):

    1  Cloudflare       speed.cloudflare.com
    2  Tele2 CDN
    3  Hetzner FSN1     Germany
    4  Hetzner NBG1     Germany
    5  OVH              France
    6  ThinkBroadband
    7  CacheFly CDN
    8  Leaseweb         Netherlands

The result always shows which server was actually used, for example:
"via Tele2 CDN"

Speed rating:

    3 stars  Excellent   Download >= 100 Mbps  Upload >= 50 Mbps  Ping <= 20 ms
    2 stars  Good        Download >= 25 Mbps   Upload >= 10 Mbps  Ping <= 60 ms
    1 star   Poor        Below the thresholds above

---

## Python Packages

    colorama       Optional   Coloured output in terminal
    netifaces      Optional   More accurate network interface detection
    speedtest-cli  Optional   BDIX speed test (Bangladesh local network)
    requests       Optional   Reserved for future features

Everything else uses Python built-in libraries only -- no extra installs
are needed to run the speed test, ping, scan, or dashboard.

Install all optional packages at once:

```
pip install -r requirements.txt
```

---

## Dashboard and Results File

A local web server starts automatically when ANAT runs:

    http://127.0.0.1:8000/             main dashboard page
    http://127.0.0.1:8000/api/results  live JSON of all results

Results are also written to net_results.json in the ANAT folder and
updated after every step so you can monitor progress in real time.

To use a custom dashboard, place an index.html file in the ANAT folder.
If no index.html is present, a placeholder page is shown with a link to
the JSON API.

---

## File Structure

    ANAT/
    ├── ANAT.py            main script, run this
    ├── requirements.txt   Python dependencies
    ├── index.html         optional, your custom dashboard page
    ├── net_results.json   auto-created, live results output
    └── README.md

---

## Troubleshooting

Download test fails
    All 8 servers were unreachable. The tool prints each server's error
    message so you can see exactly why. Check whether your network blocks
    outbound HTTP or if you need a VPN.

Wi-Fi info shows Unknown
    Both the termux-api package and the Termux:API app must be installed.
    The package alone is not enough.

    Install the package inside Termux:
        pkg install termux-api

    Install the app: open F-Droid and search "Termux API"

BDIX test is skipped
    Install speedtest-cli:
        pip install speedtest-cli

Traceroute failed at startup
    Some Android devices do not have traceroute available. The ISP hub
    detection step is skipped and all other tests still run normally.

Storage or permission error
    Run this once to grant storage access:
        termux-setup-storage

---

Made by Golu Molu -- FK Unknown Team
https://github.com/fkunknownteam/ANAT
