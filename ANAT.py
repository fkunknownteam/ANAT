import socket
import struct
import speedtest
import subprocess
import netifaces
import ipaddress
import concurrent.futures
import time
import requests
import json
from colorama import Fore, Style, init
import platform
import os
import pyfiglet
import speedtest
from colorama import Fore, Style
import re

# Initialize colorama for cross-platform colored output
init()

def simple_distance_estimate(rssi):
    if rssi >= -50:
        return "1–2 meters (Very close)"
    elif rssi >= -60:
        return "2–4 meters"
    elif rssi >= -70:
        return "4–8 meters"
    elif rssi >= -80:
        return "8–15 meters"
    else:
        return "15+ meters (Weak or far)"

def get_wifi_info():
    try:
        result = subprocess.run(
            ['termux-wifi-connectioninfo'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        if result.returncode != 0:
            print("Error running termux-wifi-connectioninfo. Make sure Termux:API is installed.")
            return None
        
        data = json.loads(result.stdout)
        return data

    except Exception as e:
        print("Error getting WiFi info:", e)
        return None

def ping_router():
    print("Pinging router at 192.168.55.1...\n")
    try:
        result = subprocess.run(
            ['ping', '-c', '10', '192.168.55.1'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        output = result.stdout
        match = re.search(r'rtt min/avg/max/mdev = ([\d\.]+)/([\d\.]+)/([\d\.]+)/([\d\.]+)', output)
        if match:
            avg_ping = float(match.group(2))
           
            if avg_ping < 5:
                status = f"{Fore.GREEN}Excellent{Style.RESET_ALL}"
            elif avg_ping < 15:
                status = f"{Fore.CYAN}Good{Style.RESET_ALL}"
            elif avg_ping < 30:
                status = f"{Fore.YELLOW}Average{Style.RESET_ALL}"
            else:
                status = f"{Fore.RED}Poor or Unstable{Style.RESET_ALL}"

            print(f"{Fore.YELLOW} \n=== Ping Report ==={Style.RESET_ALL}")
            
            print(f"Average Ping Time: {avg_ping} ms")
            print(f"Connection Status: {status}")
        else:
            print("Could not parse ping results.")

    except Exception as e:
        print("An error occurred during ping:", e)

# Define package speeds (in MBps)
PACKAGE_SPEED_MBPS = 1  # Example package speed, adjust as needed
os.system("clear")
def print_logo():
    # Define ANSI escape codes for colors
    cyan = "\033[36m"
    blue = "\033[34m"
    green = "\033[32m"
    red = "\033[31m"
    yellow = "\033[33m"
    reset = "\033[0m"
    bold = "\033[1m"

    logo = f"""
{cyan}     /\\     {blue} _   _  _____ _______{green}_______{red}
{cyan}    /  \\    {blue}| \\ | ||  __ \\_   _|{green}__   __|{red}
{cyan}   / /\\ \\   {blue}|  \\| || |  | || |  {green}  | |   {red}
{cyan}  / ____ \\  {blue}| . ` || |  | || |  {green}  | |   {red}
{cyan} /_/    \\_\\ {blue}|_|\\_||_|  |_||_|  {green}  |_|   {red}
    """

    footer = f"{yellow}=== Advanced Network Analysis Tool ==={reset}"

    # Calculate width of the logo
    logo_lines = logo.split('\n')
    logo_width = max(len(line) for line in logo_lines)
    footer_padding = (logo_width - len(footer)) // 2

    # Create bordered logo with footer
    bordered_logo = f"{cyan}╔{'═' * (logo_width + 2)}╗{reset}\n"
    for line in logo_lines:
        if line.strip():
            bordered_logo += f"{cyan}║ {line.ljust(logo_width)}{cyan} ║{reset}\n"
    bordered_logo += f"{cyan}╠{'═' * (logo_width + 2)}╣{reset}\n"
    bordered_logo += f"{cyan}║{' ' * footer_padding}{bold}{footer}{' ' * footer_padding}{cyan}║{reset}\n"
    bordered_logo += f"{cyan}╚{'═' * (logo_width + 2)}╝{reset}"

    # Print bordered logo
    print(bordered_logo)

def get_network_info():
    """Get the local IP address and subnet mask."""
    for interface in netifaces.interfaces():
        addrs = netifaces.ifaddresses(interface)
        if netifaces.AF_INET in addrs:
            ip_info = addrs[netifaces.AF_INET][0]
            if 'addr' in ip_info and 'netmask' in ip_info:
                return ip_info['addr'], ip_info['netmask']
    return None, None

def get_network_range(ip, netmask):
    """Get the network range based on IP and subnet mask."""
    network = ipaddress.IPv4Network(f"{ip}/{netmask}", strict=False)
    return str(network)

def get_hostname(ip):
    """Get the hostname for a given IP address."""
    try:
        hostname = socket.gethostbyname_ex(ip)[0]
        return hostname if hostname != ip else None
    except socket.herror:
        return None

def ping_host(ip):
    """Ping a single host and return its status."""
    try:
        subprocess.check_output(["ping", "-c", "1", "-W", "1", ip], stderr=subprocess.DEVNULL)
        hostname = get_hostname(ip)
        return ip, hostname if hostname else "Unknown", "Active"
    except subprocess.CalledProcessError:
        return ip, "Unknown", "Inactive"

def scan_network(network_range, router_ip):
    """Scan the network and return a list of connected devices."""
    network = ipaddress.IPv4Network(network_range)
    connected_devices = []
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=100) as executor:
        future_to_ip = {executor.submit(ping_host, str(ip)): ip for ip in network.hosts() if str(ip) != router_ip}
        for future in concurrent.futures.as_completed(future_to_ip):
            ip, hostname, status = future.result()
            if status == "Active":
                connected_devices.append((ip, hostname))
    
    return connected_devices

def speed_test():
    """Perform a speed test and return download and upload speeds."""
    try:
        st = speedtest.Speedtest()
        print("Testing download speed...")
        download_speed_bps = st.download()
        print("Testing upload speed...")
        upload_speed_bps = st.upload()
        
        # Convert to MBps
        download_speed_MBps = download_speed_bps / 8_000_000
        upload_speed_MBps = upload_speed_bps / 8_000_000
        
        return download_speed_MBps, upload_speed_MBps
    except Exception as e:
        print(f"{Fore.RED}Speed test failed: {str(e)}{Style.RESET_ALL}")
        return None, None
 
# raw speed check 
def measure_download_speed(duration=20):
    
    url = "https://download.c.realme.com/flash/Rollbackpack/realme_Narzo_50/oplus_ota_downgrade.zip" 
    chunk_size = 1024 * 64
    max_speed_MBps = 0 

    try:
        response = requests.get(url, stream=True)
        response.raise_for_status()

        print(f"{Fore.YELLOW} \nTry to enhance and find out your packages ({duration} seconds)...{Style.RESET_ALL}")


        start_time = time.time()
        last_time = start_time
        last_downloaded = 0
        total_downloaded = 0

        for chunk in response.iter_content(chunk_size=chunk_size):
            if not chunk:
                continue

            total_downloaded += len(chunk)
            now = time.time()
            elapsed = now - last_time
            total_elapsed = now - start_time

            if elapsed >= 1:
                downloaded = total_downloaded - last_downloaded
                instant_speed = downloaded / elapsed / (1024 * 1024)  # Convert to MBps
                avg_speed = total_downloaded / total_elapsed / (1024 * 1024)  # MBps
                if instant_speed > max_speed_MBps:
                    max_speed_MBps = instant_speed

                last_time = now
                last_downloaded = total_downloaded

            if total_elapsed >= duration:
                break

        # Print only the highest download speed encountered
        print(f"Your package is likely nearby :{max_speed_MBps * 8:.2f} Mbps 😎")

    except requests.exceptions.RequestException as e:
        print(f"\nError during download: {e}")
    except Exception as e:
        print(f"\nUnexpected error: {e}")

def bdix_speed_test():
    """Perform a BDIX speed test using Speedtest CLI with BDIX servers."""
    try:
        st = speedtest.Speedtest()
        st.get_servers()
        all_servers = st.get_servers()
       
        bdix_server = None
        for server_list in all_servers.values():
            for server in server_list:
                if 'bdix' in server['sponsor'].lower() or 'bangladesh' in server['country'].lower():
                    bdix_server = server
                    break
            if bdix_server:
                break

        if not bdix_server:
            print(f"{Fore.YELLOW}No BDIX server found. Using best available server.{Style.RESET_ALL}")
            st.get_best_server()
        else:
            print(f"{Fore.GREEN}Using BDIX Server: {bdix_server['sponsor']} - {bdix_server['name']}{Style.RESET_ALL}")
            st.get_best_server([bdix_server])
        
        download = st.download() / 1_000_000  # Mbps
        upload = st.upload() / 1_000_000  # Mbps

        print(f"{Fore.CYAN}Download Speed: {download:.2f} Mbps{Style.RESET_ALL}")
        print(f"{Fore.CYAN}Upload Speed: {upload:.2f} Mbps{Style.RESET_ALL}")
        
        return download  # Or return both if needed

    except Exception as e:
        print(f"{Fore.RED}BDIX speed test failed: {str(e)}{Style.RESET_ALL}")
        return None


def ping_test(host):
    """Perform a ping test to the specified host."""
    try:
        if platform.system().lower() == "windows":
            output = subprocess.check_output(["ping", "-n", "4", host], stderr=subprocess.STDOUT, universal_newlines=True)
        else:
            output = subprocess.check_output(["ping", "-c", "4", host], stderr=subprocess.STDOUT, universal_newlines=True)
        lines = output.split("\n")
        avg_ping = float(lines[-2].split("=")[-1].split("/")[1])
        return avg_ping
    except subprocess.CalledProcessError:
        return None

def print_speed_comparison(download_speed, upload_speed):
    """Print speed comparison with package speed."""
    if download_speed is None or upload_speed is None:
        print(f"{Fore.RED}Unable to perform speed comparison due to failed speed test.{Style.RESET_ALL}")
        return

    total_speed = download_speed + upload_speed
    percentage = (total_speed / PACKAGE_SPEED_MBPS) * 100
    if percentage >= 90:
        color = Fore.GREEN
    elif percentage >= 70:
        color = Fore.YELLOW
    else:
        color = Fore.RED
    print(f"Download speed: {download_speed:.2f} MBps")
    print(f"Upload speed: {upload_speed:.2f} MBps")
    print(f"{color}Total speed: Your package may be closer to {total_speed:.2f} Mbps 😬{Style.RESET_ALL}")

import subprocess
import json
from colorama import Fore, Style, init

init(autoreset=True)

def get_current_connection():
    """Fetch current Wi-Fi connection info (BSSID and frequency)."""
    try:
        output = subprocess.check_output(["termux-wifi-connectioninfo"], universal_newlines=True)
        return json.loads(output)
    except Exception as e:
        print(f"{Fore.RED}Failed to get current connection: {e}{Style.RESET_ALL}")
        return None


def analyze_wifi_channels_termux():
    """Analyze Wi-Fi channels using termux-wifi-scaninfo command.""" 
    try:
        # Get current connection info
        current_output = subprocess.check_output(["termux-wifi-connectioninfo"], universal_newlines=True)
        current_data = json.loads(current_output)
        current_bssid = current_data.get("bssid")

        # Scan available networks
        output = subprocess.check_output(["termux-wifi-scaninfo"], universal_newlines=True)
        wifi_data = json.loads(output)
        
        channels = {}
        current_network = None
        for network in wifi_data:
            frequency = network['frequency_mhz']
            ssid = network['ssid']
            bssid = network['bssid']
            rssi = network['rssi']
            
            # Convert frequency to channel
            if 2412 <= frequency <= 2484:
                channel = (frequency - 2412) // 5 + 1
            elif 5170 <= frequency <= 5825:
                channel = (frequency - 5170) // 5 + 34
            else:
                continue  # Skip if frequency is out of known ranges
            
            if channel not in channels:
                channels[channel] = []
            channels[channel].append((ssid, bssid, rssi))
            
            # Match with current network using BSSID
            if bssid == current_bssid:
                current_network = (ssid, channel, rssi)
        
        return channels, current_network
    except Exception as e:
        print(f"{Fore.RED}Wi-Fi channel analysis failed: {str(e)}{Style.RESET_ALL}")
        return None, None

def is_channel_overlapping(channel):
    """Check if a channel is overlapping in the 2.4 GHz band."""
    non_overlapping_24 = [1, 6, 11]
    return channel <= 14 and channel not in non_overlapping_24

def print_wifi_analysis_results(channels, current_network):
    """Print the Wi-Fi analysis results focusing on the current network."""
    if current_network is None:
        print(f"{Fore.RED}Unable to identify your current Wi-Fi network.{Style.RESET_ALL}")
        return

    ssid, channel, rssi = current_network
    print(f"\n{Fore.CYAN}=== Your Wi-Fi Network Analysis ==={Style.RESET_ALL}")
    print(f"SSID: {ssid}")
    print(f"Channel: {channel}")
    print(f"Signal Strength: {rssi} dBm")

    if is_channel_overlapping(channel):
        print(f"\n{Fore.YELLOW}Your Wi-Fi channel is overlapping with other channels.{Style.RESET_ALL}")
        print("Suggestion: Change your Wi-Fi channel to reduce interference.")
        print("Recommended non-overlapping channels for 2.4 GHz: 1, 6, or 11")
    else:
        print(f"\n{Fore.GREEN}Your Wi-Fi channel is not overlapping.{Style.RESET_ALL}")
        print("Your router is already on a non-overlapping channel.")

    suggest_best_channel(channels, current_network)

def suggest_best_channel(channels, current_network):
    """Suggest the best Wi-Fi channel based on analysis."""
    if not channels:
        print(f"{Fore.RED}No Wi-Fi channels detected.{Style.RESET_ALL}")
        return

    ssid, current_channel, _ = current_network
    
    # Define non-overlapping channels
    non_overlapping_24 = [1, 6, 11]
    non_overlapping_5 = [36, 40, 44, 48, 52, 56, 60, 64, 100, 104, 108, 112, 116, 120, 124, 128, 132, 136, 140, 144, 149, 153, 157, 161, 165]
    
    if current_channel <= 14:  # 2.4 GHz
        best_channels = non_overlapping_24
    else:  # 5 GHz
        best_channels = non_overlapping_5
    
    # Find the least crowded channel
    least_crowded = min(best_channels, key=lambda x: len(channels.get(x, [])))
    
    print(f"\n{Fore.CYAN}Channel Recommendation:{Style.RESET_ALL}")
    if least_crowded == current_channel:
        print(f"Your current channel ({current_channel}) is already optimal.")
    else:
        print(f"Consider switching to channel {least_crowded} for potentially better performance.")
    
    print("\nSuggestions to improve Wi-Fi performance:")
    print("1. Keep your router's firmware up to date.")
    print("2. Position your router in a central location, away from walls and obstructions.")
    print("3. Minimize interference from other electronic devices.")
    print("4. If possible, use the 5 GHz band for less interference and higher speeds.")
    print("5. Regularly check for new devices on your network and remove any unauthorized ones.")


def detect_network_problems(download_speed, upload_speed, ping, devices):
    """Detect potential network problems and provide tips."""
    problems = []
    tips = []

    if download_speed is not None and upload_speed is not None:
        total_speed = download_speed + upload_speed
        if total_speed < PACKAGE_SPEED_MBPS * 0.7:
            problems.append("Low overall network speed")
            tips.append("Contact your ISP to check for service issues")
        
        if download_speed < upload_speed * 0.5:
            problems.append("Asymmetric network performance (low download)")
            tips.append("Check for background downloads or streaming on other devices")
        
        if upload_speed < download_speed * 0.2:
            problems.append("Asymmetric network performance (low upload)")
            tips.append("Check for large file uploads or backup processes")
    else:
        problems.append("Unable to perform speed test")
        tips.append("Check your internet connection and try again later")

    if ping is not None:
        if ping > 100:
            problems.append("High network latency")
            tips.append("Close bandwidth-heavy applications and try connecting via Ethernet")
        
        if ping > 200:
            problems.append("Severe network latency")
            tips.append("Check for network congestion or try changing your DNS server")
    else:
        problems.append("Unable to perform ping test")
        tips.append("Check your internet connection and try again later")

    if len(devices) > 10:
        problems.append("High number of connected devices")
        tips.append("Consider upgrading your router or implementing QoS settings")
   
    return problems, tips

def print_analysis_results(problems, tips):
    """Print the analysis results in a professional format."""
    
    print(f"\n{Fore.CYAN}=== Network Analysis Results ==={Style.RESET_ALL}")
    
    if not problems:
        print(f"{Fore.GREEN}✓ No significant network problems detected.{Style.RESET_ALL}")
    else:
        print(f"{Fore.YELLOW}Potential network issues detected:{Style.RESET_ALL}")
        for i, problem in enumerate(problems, 1):
            print(f"{Fore.RED}{i}. {problem}{Style.RESET_ALL}")
    
    print(f"\n{Fore.CYAN}Recommendations:{Style.RESET_ALL}")
    for i, tip in enumerate(tips, 1):
        print(f"{Fore.GREEN}{i}. {tip}{Style.RESET_ALL}")
    
    print(f"\n{Fore.CYAN}General tips for improving network performance:{Style.RESET_ALL}")
    general_tips = [
        "Regularly restart your router and modem",
        "Update your router's firmware",
        "Use a wired connection when possible",
        "Optimize router placement for better coverage",
        "Implement QoS (Quality of Service) settings on your router",
        "Consider upgrading to a mesh network system for larger areas",
        "Use a network analyzer app to find less congested Wi-Fi channels",
        "Limit the number of devices connected to your network",
        "Enable WPA3 security if supported by your router",
        "Contact your ISP if problems persist"
    ]
    for i, tip in enumerate(general_tips, 1):
        print(f"{Fore.YELLOW}{i}. {tip}{Style.RESET_ALL}")
        
  
#Ping Test to Router 
        
def ping_router():
    local_ip, netmask = get_network_info()
    if not local_ip or not netmask:
        print(f"{Fore.RED}Could not detect network information automatically.{Style.RESET_ALL}")
        return
  
    network_range = get_network_range(local_ip, netmask)
    wifi_info = get_wifi_info()
    router_ip = network_range.split('/')[0][:-1] + '1' 
    print(f"Pinging router at {router_ip}...\n")
    try:
        result = subprocess.run(
        ['ping', '-c', '10', router_ip], 
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
        )

        output = result.stdout
        match = re.search(r'rtt min/avg/max/mdev = ([\d\.]+)/([\d\.]+)/([\d\.]+)/([\d\.]+)', output)
        if match:
            avg_ping = float(match.group(2))
           
            if avg_ping < 5:
                status = f"{Fore.GREEN}Excellent{Style.RESET_ALL}"
            elif avg_ping < 15:
                status = f"{Fore.CYAN}Good{Style.RESET_ALL}"
            elif avg_ping < 30:
                status = f"{Fore.YELLOW}Average{Style.RESET_ALL}"
            else:
                status = f"{Fore.RED}Poor or Unstable{Style.RESET_ALL}"

            print(f"{Fore.YELLOW} \n=== Ping Report ==={Style.RESET_ALL}")
            
            print(f"Average Ping Time: {avg_ping} ms")
            print(f"Connection Status: {status}")
        else:
            print("Could not parse ping results.")

    except Exception as e:
        print("An error occurred during ping:", e)

def main():
    print_logo()
    
    # Get local IP and subnet mask
    local_ip, netmask = get_network_info()
    if not local_ip or not netmask:
        print(f"{Fore.RED}Could not detect network information automatically.{Style.RESET_ALL}")
        return
  
    network_range = get_network_range(local_ip, netmask)
    wifi_info = get_wifi_info()
    router_ip = network_range.split('/')[0][:-1] + '1' 
    
    print(f"\n{Fore.CYAN}=== Router Information ==={Style.RESET_ALL}")
    print(f"{Fore.YELLOW}Local IP        : {Fore.GREEN}{local_ip}")
    print(f"{Fore.YELLOW}Subnet Mask     : {Fore.GREEN}{netmask}")
    print(f"{Fore.YELLOW}Network Range   : {Fore.GREEN}{network_range}")
    print(f"{Fore.YELLOW}Assumed Gateway : {Fore.GREEN}{router_ip}")
    
    if wifi_info:
        
        print(f"{Fore.YELLOW}SSID            : {Fore.GREEN}{wifi_info.get('ssid', 'Unknown')}")
        print(f"{Fore.YELLOW}BSSID           : {Fore.GREEN}{wifi_info.get('bssid', 'Unknown')}")
        rssi = wifi_info.get('rssi')
        if rssi is not None:
            print(f"{Fore.YELLOW}RSSI            : {Fore.GREEN}{rssi} dBm")
            print(f"{Fore.YELLOW}Estimated Dist. : {Fore.GREEN}{simple_distance_estimate(rssi)}")
        else:
            print(f"{Fore.RED}RSSI data not available.{Style.RESET_ALL}")
    else:
        print(f"{Fore.RED}Could not retrieve WiFi information.{Style.RESET_ALL}")
    
    print()
    ping_router()

    
    # 1. Scan for connected devices
    print(f"\n{Fore.YELLOW}Scanning network {network_range}...{Style.RESET_ALL}")
    start_time = time.time()
    devices = scan_network(network_range, router_ip)
    end_time = time.time()
    
    print(f"\n{Fore.GREEN}Devices connected to the network: {len(devices)}{Style.RESET_ALL}")
    for ip, hostname in devices:
        print(f"IP: {ip}, Hostname: {hostname}")
    
    print(f"\nScan completed in {end_time - start_time:.2f} seconds")
    
    # 2. Speed Test
    print(f"\n{Fore.YELLOW}Performing speed test...{Style.RESET_ALL}")
    download_MBps, upload_MBps = speed_test()
    print_speed_comparison(download_MBps, upload_MBps)
    measure_download_speed() 
    
    print(f"\n{Fore.YELLOW}Performing BDIX speed test...{Style.RESET_ALL}")
    bdix_MBps = bdix_speed_test()
    if bdix_MBps is not None:
        print(f"BDIX Download speed: {bdix_MBps:.2f} MBps")
    
    # 3. Ping Test
    print(f"\n{Fore.YELLOW}Performing ping tests...{Style.RESET_ALL}")
    hosts_to_ping = ["google.com", "facebook.com", "youtube.com","instagram.com","messenger.com","tiktok.com","ff.garena.com"," 9.9.9.9"]
    avg_ping = 0
    ping_count = 0
    for host in hosts_to_ping:
        print(f"Pinging {host}...")
        result = ping_test(host)
        if result is not None:
            avg_ping += result
            ping_count += 1
            if result < 50:
                color = Fore.GREEN
            elif result < 100:
                color = Fore.YELLOW
            else:
                color = Fore.RED
            print(f"Result: {color}{result:.2f} ms{Style.RESET_ALL}")
        else:
            print(f"{Fore.RED}Ping failed{Style.RESET_ALL}")
    
    if ping_count > 0:
        avg_ping /= ping_count
    else:
        avg_ping = None
    
    # 4. Wi-Fi Channel Analysis
    print(f"\n{Fore.YELLOW}Analyzing Wi-Fi channels...{Style.RESET_ALL}")
    channels, current_network = analyze_wifi_channels_termux()
    
    if channels is not None and current_network is not None:
        print_wifi_analysis_results(channels, current_network)
    else:
        print(f"{Fore.RED}Unable to perform Wi-Fi analysis. Please check your permissions and try again.{Style.RESET_ALL}")
    
    # 5. Network Problem Detection and Tips
    problems, tips = detect_network_problems(download_MBps, upload_MBps, avg_ping, devices)
    print_analysis_results(problems, tips)

if __name__ == "__main__":
    main()
