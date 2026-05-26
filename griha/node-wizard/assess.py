"""Hardware Assessment — scans Pi capabilities to inform role assignment."""
import os, subprocess
from pathlib import Path

KNOWN_USB_DEVICES = {
    "10c4:ea60": {"name": "Sonoff Zigbee Dongle Plus", "capability": "zigbee"},
    "1cf1:0030": {"name": "Conbee II (Zigbee)", "capability": "zigbee"},
    "0658:0200": {"name": "Aeotec Z-Wave Stick Gen5", "capability": "zwave"},
    "10c4:8a2a": {"name": "HUSBZB-1 (Zigbee + Z-Wave)", "capability": "zigbee_zwave"},
    "1a86:7523": {"name": "CH340 Zigbee Dongle", "capability": "zigbee"},
    "10c4:ea71": {"name": "Sonoff Zigbee Dongle E", "capability": "zigbee"},
    "0403:6001": {"name": "FTDI Z-Wave USB", "capability": "zwave"},
    "03e7:2485": {"name": "Intel NCS2 (AI Accelerator)", "capability": "ncs2"},
}

def scan_hardware() -> dict:
    hw = {"ram_gb": _get_ram_gb(), "cpu_cores": os.cpu_count() or 1, "model": _get_pi_model(),
          "storage_gb": _get_storage_gb(), "usb_devices": _scan_usb(), "has_camera": _check_camera(),
          "has_microphone": _check_microphone(), "wired_active": _check_wired(),
          "wireless_present": _check_wireless(), "hailo_present": _check_hailo(), "capabilities": []}
    for dev in hw["usb_devices"]:
        if (cap := dev.get("capability")) and cap not in hw["capabilities"]:
            hw["capabilities"].append(cap)
    if hw["has_camera"]: hw["capabilities"].append("camera")
    if hw["has_microphone"]: hw["capabilities"].append("microphone")
    if hw["hailo_present"]: hw["capabilities"].append("hailo_present")  # Note: 8L excluded from LLM roles
    if hw["ram_gb"] >= 8: hw["capabilities"].append("ram_8gb")
    if hw["ram_gb"] >= 4: hw["capabilities"].append("ram_4gb")
    return hw

def _get_ram_gb() -> float:
    try:
        with open("/proc/meminfo") as f:
            for line in f:
                if line.startswith("MemTotal"):
                    return round(int(line.split()[1]) / 1024 / 1024, 1)
    except: pass
    return 0.0

def _get_pi_model() -> str:
    try: return Path("/proc/device-tree/model").read_text().replace("\x00","").strip()
    except: pass
    return "Unknown"

def _get_storage_gb() -> float:
    try:
        result = subprocess.run(["df", "/", "--output=size", "-BG"], capture_output=True, text=True)
        return float(result.stdout.strip().split("\n")[1].replace("G","").strip())
    except: return 0.0

def _scan_usb() -> list:
    found = []
    try:
        for line in subprocess.run(["lsusb"], capture_output=True, text=True).stdout.splitlines():
            for part in line.split():
                if ":" in part and len(part) == 9 and (vid_pid := part.lower()) in KNOWN_USB_DEVICES:
                    device = {**KNOWN_USB_DEVICES[vid_pid], "id": vid_pid}
                    if device not in found: found.append(device)
    except: pass
    return found

def _check_camera() -> bool: return Path("/dev/video0").exists()

def _check_microphone() -> bool:
    try: return "card" in subprocess.run(["arecord","-l"],capture_output=True,text=True).stdout.lower()
    except: return Path("/dev/snd/pcmC0D0c").exists()

def _check_wired() -> bool:
    try: return "UP" in subprocess.run(["ip","link","show","eth0"],capture_output=True,text=True).stdout
    except: return False

def _check_wireless() -> bool: return Path("/sys/class/net/wlan0").exists()

def _check_hailo() -> bool:
    try: return "hailo" in subprocess.run(["lspci"],capture_output=True,text=True).stdout.lower()
    except: pass
    try: return subprocess.run(["hailortcli","fw-control","identify"],capture_output=True).returncode == 0
    except: return False
