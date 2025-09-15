#!/usr/bin/env python3

import os
import re
import sys
import subprocess
import argparse
from typing import Dict, Any
from commands.utils import run
from commands.configure_memory import configure_memory
from commands.nvidia import RemoveNvidiaDriverCmd, remove_nvidia_driver, check_nvidia
from commands.configure_disks import configure_disks
from commands.apt_install import AptInstallCmd
from commands.configure_libvirt import ConfigureLibvirtCmd, CheckVirtualizationCmd
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
        run(["reboot"])
    else:
        print("Please reboot at your convenience to apply the changes.")

NODE_COMMANDS = [
    CheckVirtualizationCmd(),
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

def list_commands():
    """
    List all available configuration commands.
    """
    print("=" * 60)
    print("📋 AVAILABLE CONFIGURATION COMMANDS")
    print("=" * 60)
    
    for i, command in enumerate(NODE_COMMANDS, start=1):
        print(f"  {i}. {command.name()}")
        print(f"     └─ {command.description()}")
    print("=" * 60)
    print(f"Total: {len(NODE_COMMANDS)} commands available")

def execute_specific_command(command_identifier):
    """
    Execute a specific command by index or name.
    """
    if os.geteuid() != 0:
        print("This script must be run with sudo.")
        sys.exit(1)

    env = {}  # Shared environment dictionary
    command_to_execute = None
    command_index = None

    # Try to parse as index first
    try:
        index = int(command_identifier) - 1  # Convert to 0-based index
        if 0 <= index < len(NODE_COMMANDS):
            command_to_execute = NODE_COMMANDS[index]
            command_index = index + 1
    except ValueError:
        # Not a number, try to find by name
        for i, command in enumerate(NODE_COMMANDS):
            if command.name().lower() == command_identifier.lower():
                command_to_execute = command
                command_index = i + 1
                break

    if command_to_execute is None:
        print(f"❌ Command '{command_identifier}' not found.")
        print("Use --list to see available commands.")
        sys.exit(1)

    print("=" * 60)
    print("🔧 EXECUTING SPECIFIC COMMAND")
    print("=" * 60)
    print(f"🚀 Executing command {command_index}: {command_to_execute.name()}")
    print(f"📝 Description: {command_to_execute.description()}")
    print(f"⏳ Executing...")
    
    try:
        success = command_to_execute.execute(env)
        if success:
            print(f"✅ Command completed successfully!")
        else:
            print(f"❌ Command failed!")
            sys.exit(1)
    except Exception as e:
        print(f"❌ Command failed with exception!")
        print(f"💥 Error: {str(e)}")
        sys.exit(1)
    
    print("🎉 Command execution completed!")
    print("=" * 60)

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

def main():
    """
    Parse command line arguments and execute appropriate action.
    """
    parser = argparse.ArgumentParser(
        description="Configure your system for server use with QEMU/KVM virtualization.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python configure.py                    # Run all configuration commands
  python configure.py --list            # List all available commands
  python configure.py --command 3       # Execute command #3 only
  python configure.py --command "Remove Nvidia Driver"  # Execute by name
        """
    )
    
    parser.add_argument(
        "--list", 
        action="store_true",
        help="List all available configuration commands"
    )
    
    parser.add_argument(
        "--command", 
        metavar="ID_OR_NAME",
        help="Execute only the specified command (by number or name)"
    )
    
    args = parser.parse_args()
    
    if args.list:
        list_commands()
    elif args.command:
        execute_specific_command(args.command)
    else:
        configure_node()

if __name__ == "__main__":
    main()
