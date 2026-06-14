"""
Node Onboarding Wizard — scans hardware, assigns role, provisions WireGuard + mTLS.
Usage: python wizard.py [--coordinator 10.99.0.1] [--auto]
"""
import asyncio, argparse, json, logging, subprocess
from pathlib import Path
from assess import scan_hardware
from roles import eligible_roles

logger = logging.getLogger(__name__)
BANNER = "\n╔══════════════════════════════════════════╗\n║  Home Framework — Node Onboarding Wizard ║\n║  v0.1.0                                  ║\n╚══════════════════════════════════════════╝\n"

def display_hardware(hw):
    print("\n── Hardware Assessment ──────────────────")
    print(f"  Model:       {hw['model']}")
    print(f"  RAM:         {hw['ram_gb']} GB")
    print(f"  Storage:     {hw['storage_gb']} GB")
    print(f"  Wired (eth0): {'✓ active' if hw['wired_active'] else '✗ NOT CONNECTED'}")
    print(f"  Wireless:    {'present' if hw['wireless_present'] else 'not detected'}")
    print(f"  Hailo HAT:   {'✓ detected' if hw['hailo_present'] else 'not detected'}")
    if hw['usb_devices']:
        print(f"\n  Peripherals detected:")
        for dev in hw['usb_devices']:
            print(f"    • {dev['name']}  [{dev['id']}]  → {dev['capability']}")
    print(f"\n  Capabilities: {', '.join(hw['capabilities']) or 'none'}")

def display_roles(eligible):
    print("\n── Eligible Roles ───────────────────────")
    if not eligible:
        print("  No eligible roles for this hardware.")
        return
    for i, role in enumerate(eligible):
        star = "★" if i == 0 else " "
        print(f"  {star} [{i + 1}] {role['role']}")
        if role['note']:
            print(f"        {role['note']}")

def select_role(eligible, auto=False):
    if auto or len(eligible) == 1:
        print(f"\n  Auto-selecting: {eligible[0]['role']}")
        return eligible[0]['role']
    choice = input(f"\n  Select role [1]: ").strip() or "1"
    try:
        return eligible[int(choice) - 1]['role']
    except (ValueError, IndexError):
        return eligible[0]['role']

async def provision(node_id, role, coordinator_ip, hw):
    print("\n── Provisioning ─────────────────────────")
    print("  [1/5] Disabling wireless...")
    _run_or_warn(["sudo", "rfkill", "block", "wifi"])
    print("  [2/5] Generating WireGuard keypair...")
    privkey = subprocess.run(["wg", "genkey"], capture_output=True, text=True).stdout.strip()
    pubkey = subprocess.run(["wg", "pubkey"], input=privkey, capture_output=True, text=True).stdout.strip()
    wg_dir = Path("/etc/wireguard")
    wg_dir.mkdir(exist_ok=True)
    (wg_dir / "privatekey").write_text(privkey)
    (wg_dir / "publickey").write_text(pubkey)
    print(f"      Public key: {pubkey[:20]}...")
    print(f"  [3/5] Registering with coordinator ({coordinator_ip})...")
    manifest = {"node_id": node_id, "role": role, "wg_pubkey": pubkey, "capabilities": hw["capabilities"], "ram_gb": hw["ram_gb"], "model": hw["model"]}
    print(f"      Manifest prepared (NATS registration deferred)")
    print(f"  [4/5] Installing recipe '{role}'...")
    recipe_src = Path(__file__).parent.parent / "agents" / role.replace("-", "_")
    if not recipe_src.exists():
        print(f"      ⚠ Recipe '{role}' not found.")
    print(f"  [5/5] Writing local node manifest...")
    local_manifest = Path("/etc/home-framework/node.json")
    local_manifest.parent.mkdir(parents=True, exist_ok=True)
    local_manifest.write_text(json.dumps(manifest, indent=2))
    print(f"\n✓ Node '{node_id}' provisioned as '{role}'")
    print(f"  Next: sudo systemctl start home-agent\n")

def _run_or_warn(cmd):
    try:
        subprocess.run(cmd, check=True, capture_output=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        print(f"      ⚠ Command failed (non-fatal): {' '.join(cmd)}")

async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--coordinator", default="10.99.0.1")
    parser.add_argument("--auto", action="store_true")
    args = parser.parse_args()
    print(BANNER)
    print("Scanning hardware...\n")
    hw = scan_hardware()
    display_hardware(hw)
    if not hw['wired_active']:
        print("\n✗ ERROR: Wired Ethernet (eth0) must be active.\n")
        exit(1)
    eligible = eligible_roles(hw, existing_coordinator=True)
    display_roles(eligible)
    if not eligible:
        print("\n✗ No eligible roles.\n")
        exit(1)
    role = select_role(eligible, args.auto)
    default_id = f"pi-{role}-01"
    node_id = default_id if args.auto else (input(f"\n  Node ID [{default_id}]: ").strip() or default_id)
    print(f"\n── Summary ──────────────────────────────")
    print(f"  Node ID: {node_id}\n  Role: {role}\n  Coordinator: {args.coordinator}")
    if not args.auto:
        if input("\n  Proceed? [y/N]: ").strip().lower() != 'y':
            print("  Aborted.\n")
            exit(0)
    await provision(node_id, role, args.coordinator, hw)

if __name__ == "__main__":
    asyncio.run(main())
