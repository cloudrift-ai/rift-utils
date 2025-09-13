#!/usr/bin/env python3

import os
import re
import sys
import subprocess
from typing import Dict, Any
from commands.utils import run
from commands.setup_virtualization import setup_virtualization
from commands.configure_memory import configure_memory
from commands.nvidia import RemoveNvidiaDriverCmd, remove_nvidia_driver, check_nvidia
from commands.configure_disks import configure_disks
from commands.apt_install import AptInstallCmd
from commands.configure_libvirt import ConfigureLibvirtCmd
from commands.configure_grub import ReadGrubCmd, GetIommuTypeCmd, GetGpuPciIdsCmd, AddGrubVirtualizationOptionsCmd, CreateGrubOverrideCmd
from commands.configure_initramfs import UpdateInitramfsModulesCmd
from commands.configure_modprobe import CreateVfioConfCmd
from commands.configure_memory import ConfigureMemoryCmd
from commands.configure_disks import ConfigureDisksCmd

GRUB_MAIN_FILE = '/etc/default/grub'
GRUB_D_DIR = '/etc/default/grub.d'
VFIO_GRUB_FILE = os.path.join(GRUB_D_DIR, '99-cloudrift.cfg')


REQUIRED_PACKAGES = [
    "qemu-kvm",
    "libvirt-daemon-system",
    "genisoimage",
    "whois",
    "mdadm"  # RAID devices
]

def reboot_server():
    """
    Prompts the user to reboot and provides verification instructions.
    """
    print("\n--- Reboot and Verify ---")
    print("The configuration is complete. You need to reboot for the changes to take effect.")
    print("After rebooting, you can verify the configuration by running the following commands:")
    print("  grep -i huge /proc/meminfo")
    print("  grep hugetlbfs /proc/mounts")
    print("\nReboot now? (y/N)")
    if (input() or 'n').lower() == 'y':
        print("Rebooting...")
        run("sudo reboot")
    else:
        print("Please reboot at your convenience to apply the changes.")

NODE_COMMANDS = [
    RemoveNvidiaDriverCmd(),
    AptInstallCmd(REQUIRED_PACKAGES),
    ConfigureLibvirtCmd(),
    ReadGrubCmd(),
    GetIommuTypeCmd(),
    GetGpuPciIdsCmd(),
    AddGrubVirtualizationOptionsCmd(),
    UpdateInitramfsModulesCmd(),
    CreateVfioConfCmd(),
    ConfigureMemoryCmd(),
    ConfigureDisksCmd(),
    CreateGrubOverrideCmd()
]

def configure_node():
    """
    Main function to orchestrate the script's execution.
    """
    if os.geteuid() != 0:
        print("This script must be run with sudo.")
        sys.exit(1)

    print("=" * 60)
    print("🔧 NODE CONFIGURATION SCRIPT")
    print("=" * 60)
    print("This script will configure your system for server use.")
    print("It adds the necessary kernel parameters to /etc/default/grub.d/99-cloudrift.cfg,")
    print("/etc/initramfs-tools/modules, and /etc/modprobe.d/vfio.conf.")
    print()

    total_commands = len(NODE_COMMANDS)
    print(f"📋 Found {total_commands} configuration command(s) to execute:")
    print("-" * 60)
    
    # Print overview of all commands first
    for i, command in enumerate(NODE_COMMANDS, start=1):
        print(f"  {i}. {command.name()}")
        print(f"     └─ {command.description()}")
    print("-" * 60)
    print()

    env = {}  # Shared environment dictionary for commands

    # Execute commands with enhanced output
    for i, command in enumerate(NODE_COMMANDS, start=1):
        print(f"🚀 Step {i}/{total_commands}: {command.name()}")
        print(f"📝 Description: {command.description()}")
        print(f"⏳ Executing...")
        
        try:
            success = command.execute(env)
            if success:
                print(f"✅ Step {i}/{total_commands} completed successfully!")
            else:
                print(f"❌ Step {i}/{total_commands} failed!")
                print(f"💥 Command '{command.name()}' encountered an error. Exiting.")
                sys.exit(1)
        except Exception as e:
            print(f"❌ Step {i}/{total_commands} failed with exception!")
            print(f"💥 Error: {str(e)}")
            print(f"🛑 Command '{command.name()}' failed. Exiting.")
            sys.exit(1)
        
        print("-" * 40)
        print()

    print("🎉 All configuration commands completed successfully!")
    print("=" * 60)

    reboot_server()

if __name__ == "__main__":
    configure_node()
