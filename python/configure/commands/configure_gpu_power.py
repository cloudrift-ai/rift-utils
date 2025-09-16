import os
import subprocess
from typing import Any, Dict
from .cmd import BaseCmd
from .utils import run

UDEV_RULE_FILE = '/etc/udev/rules.d/99-vfio-nvidia-power.rules'
MODPROBE_CONF_FILE = '/etc/modprobe.d/vfio-pci-power.conf'

def create_gpu_power_udev_rule():
    """
    Creates udev rule to prevent NVIDIA GPU from going into deep D3 state.
    """
    udev_rule_content = '''# Keep all NVIDIA PCI functions in D0 (no runtime suspend / no D3cold)
ACTION=="add",   SUBSYSTEM=="pci", ATTR{vendor}=="0x10de", ENV{DEVTYPE}=="pci_device", \\
  RUN+="/bin/sh -c 'echo on > /sys$devpath/power/control; echo 0 > /sys$devpath/d3cold_allowed 2>/dev/null || true'"

ACTION=="change", SUBSYSTEM=="pci", ATTR{vendor}=="0x10de", ENV{DEVTYPE}=="pci_device", \\
  RUN+="/bin/sh -c 'echo on > /sys$devpath/power/control; echo 0 > /sys$devpath/d3cold_allowed 2>/dev/null || true'"
'''

    try:
        # Check if rule already exists and has same content
        if os.path.exists(UDEV_RULE_FILE):
            with open(UDEV_RULE_FILE, 'r') as f:
                existing_content = f.read()
                if existing_content == udev_rule_content:
                    print(f"Udev rule {UDEV_RULE_FILE} already exists with correct content.")
                    return False

        # Write the udev rule
        with open(UDEV_RULE_FILE, 'w') as f:
            f.write(udev_rule_content)
        print(f"Created/updated udev rule: {UDEV_RULE_FILE}")

        # Reload udev rules
        run(['sudo', 'udevadm', 'control', '--reload'], check=True)
        print("Reloaded udev rules.")

        # Trigger udev for existing devices
        run(['sudo', 'udevadm', 'trigger', '--subsystem-match=pci', '--attr-match=vendor=0x10de'], check=False)
        print("Triggered udev for existing NVIDIA devices.")

        return True
    except IOError as e:
        print(f"Error writing udev rule to {UDEV_RULE_FILE}: {e}")
        return False
    except subprocess.CalledProcessError as e:
        print(f"Error reloading udev rules: {e}")
        return False

def create_vfio_pci_power_conf():
    """
    Creates modprobe configuration to disable idle D3 for vfio-pci.
    """
    conf_content = "options vfio-pci disable_idle_d3=1\n"

    try:
        # Check if conf already exists and has same content
        if os.path.exists(MODPROBE_CONF_FILE):
            with open(MODPROBE_CONF_FILE, 'r') as f:
                existing_content = f.read()
                if existing_content == conf_content:
                    print(f"Modprobe conf {MODPROBE_CONF_FILE} already exists with correct content.")
                    return False

        # Write the modprobe conf
        with open(MODPROBE_CONF_FILE, 'w') as f:
            f.write(conf_content)
        print(f"Created/updated modprobe conf: {MODPROBE_CONF_FILE}")

        return True
    except IOError as e:
        print(f"Error writing modprobe conf to {MODPROBE_CONF_FILE}: {e}")
        return False

def verify_gpu_power_state():
    """
    Verifies that GPU power management is correctly configured.
    """
    print("\nVerifying GPU power state configuration...")
    verification_passed = True

    # Check if udev rule exists
    if os.path.exists(UDEV_RULE_FILE):
        print(f"✓ Udev rule exists: {UDEV_RULE_FILE}")
    else:
        print(f"✗ Udev rule missing: {UDEV_RULE_FILE}")
        verification_passed = False

    # Check if modprobe conf exists
    if os.path.exists(MODPROBE_CONF_FILE):
        print(f"✓ Modprobe conf exists: {MODPROBE_CONF_FILE}")
    else:
        print(f"✗ Modprobe conf missing: {MODPROBE_CONF_FILE}")
        verification_passed = False

    # Check current GPU power states
    try:
        # Find NVIDIA GPU devices
        lspci_output = subprocess.check_output(['lspci', '-d', '10de:', '-D'], text=True)
        nvidia_devices = []
        for line in lspci_output.strip().split('\n'):
            if line:
                # Extract PCI address (e.g., 0000:01:00.0)
                pci_addr = line.split()[0]
                nvidia_devices.append(pci_addr)

        if nvidia_devices:
            print(f"\nFound {len(nvidia_devices)} NVIDIA device(s):")
            for device in nvidia_devices:
                # Check power control
                power_control_path = f'/sys/bus/pci/devices/{device}/power/control'
                d3cold_path = f'/sys/bus/pci/devices/{device}/d3cold_allowed'

                if os.path.exists(power_control_path):
                    with open(power_control_path, 'r') as f:
                        power_state = f.read().strip()
                    print(f"  {device}: power/control = {power_state}", end='')
                    if power_state != 'on':
                        print(" (WARNING: should be 'on')")
                        verification_passed = False
                    else:
                        print(" ✓")

                if os.path.exists(d3cold_path):
                    with open(d3cold_path, 'r') as f:
                        d3cold_state = f.read().strip()
                    print(f"           d3cold_allowed = {d3cold_state}", end='')
                    if d3cold_state != '0':
                        print(" (WARNING: should be '0')")
                        verification_passed = False
                    else:
                        print(" ✓")
        else:
            print("\nNo NVIDIA devices found in the system.")
    except subprocess.CalledProcessError as e:
        print(f"\nError checking GPU devices: {e}")
        verification_passed = False
    except IOError as e:
        print(f"\nError reading power state files: {e}")
        verification_passed = False

    return verification_passed

class CreateGpuPowerUdevRuleCmd(BaseCmd):
    """Command to create udev rule for GPU power management."""

    def name(self) -> str:
        return "Create GPU Power Udev Rule"

    def description(self) -> str:
        return "Creates udev rule to prevent NVIDIA GPUs from entering D3 power state."

    def execute(self, env: Dict[str, Any]) -> bool:
        try:
            create_gpu_power_udev_rule()
            return True
        except Exception as e:
            print(f"Error creating GPU power udev rule: {e}")
            return False

class CreateVfioPciPowerConfCmd(BaseCmd):
    """Command to create vfio-pci power configuration."""

    def name(self) -> str:
        return "Create VFIO PCI Power Config"

    def description(self) -> str:
        return "Creates modprobe configuration to disable idle D3 for vfio-pci."

    def execute(self, env: Dict[str, Any]) -> bool:
        try:
            create_vfio_pci_power_conf()
            return True
        except Exception as e:
            print(f"Error creating vfio-pci power conf: {e}")
            return False

class VerifyGpuPowerStateCmd(BaseCmd):
    """Command to verify GPU power state configuration."""

    def name(self) -> str:
        return "Verify GPU Power State"

    def description(self) -> str:
        return "Verifies that GPU power management is correctly configured."

    def execute(self, env: Dict[str, Any]) -> bool:
        return verify_gpu_power_state()

class ConfigureGpuPowerCmd(BaseCmd):
    """Combined command to configure GPU power management."""

    def name(self) -> str:
        return "Configure GPU Power Management"

    def description(self) -> str:
        return "Configures udev rules and modprobe settings to prevent GPUs from entering D3 state."

    def execute(self, env: Dict[str, Any]) -> bool:
        success = True

        # Create udev rule
        if not create_gpu_power_udev_rule():
            print("Note: Udev rule was already up to date or had minor issues.")

        # Create modprobe conf
        if not create_vfio_pci_power_conf():
            print("Note: Modprobe conf was already up to date.")

        # Verify configuration
        if not verify_gpu_power_state():
            print("\nWarning: Some verification checks failed. You may need to reboot for changes to take full effect.")
            success = False
        else:
            print("\nAll GPU power management configurations verified successfully!")

        return success